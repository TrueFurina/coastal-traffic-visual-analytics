"""核密度估计（KDE）模块 —— 对应申报书创新点 3.1 / 3.2。

实现要点：
1. 先用 numpy.histogram2d 把轨迹点撒到细密统计网格（binning），
   把复杂度从 O(N×G) 降到 O(N + G×k)；
2. 再对计数矩阵做可分离高斯卷积（separable convolution），
   这在数学上等价于以高斯核对每个点做 KDE（Sheather-Jones 常用的快速近似）；
3. 最后用每个 bin 的真实面积把「核密度强度」换算成物理密度（艘/nmile²）。

带宽带宽单位统一用「度」入参，对外同时报告折算后的千米，便于论文引用。
"""
import numpy as np
from app.core import config, db

_KM_PER_DEG_LAT = 111.19
_NM_PER_KM = 1.0 / 1.852


def _deg_to_km(lat_center):
    """研究水域中心处 1 度折算的千米距离（经度随纬度收缩）。"""
    return np.cos(np.radians(lat_center)) * _KM_PER_DEG_LAT


def _gaussian_kernel_1d(sigma_bins):
    """一维离散高斯核，截断到 ±3σ，返回归一化后的核。"""
    if sigma_bins <= 0:
        return np.ones(1)
    half = int(np.ceil(3 * sigma_bins))
    x = np.arange(-half, half + 1, dtype=float)
    k = np.exp(-0.5 * (x / sigma_bins) ** 2)
    return k / k.sum()


def kde_surface(bandwidth_deg=0.02, grid_size=80, bin_size=None,
                min_lon=None, min_lat=None, max_lon=None, max_lat=None,
                start=None, end=None, sample_limit=800_000):
    """计算研究水域船舶位置的核密度曲面。

    返回 dict：网格单元列表 + 统计量 + 元信息（带宽/面积/样本数）。
    """
    from app.services.traffic import _region_where, _time_where  # 局部导入避免循环依赖

    # 注意：不能用 `if bandwidth_deg else`，0 是 falsy 会静默被默认值吞掉，
    # 导致非法带宽绕过参数校验。
    bw = 0.02 if bandwidth_deg is None else float(bandwidth_deg)
    if bw <= 0:
        raise ValueError("bandwidth_deg 必须为正")

    area = config.STUDY_AREA
    w = min_lon if min_lon is not None else area["min_lon"]
    s = min_lat if min_lat is not None else area["min_lat"]
    e = max_lon if max_lon is not None else area["max_lon"]
    n = max_lat if max_lat is not None else area["max_lat"]
    if not (w < e and s < n):
        raise ValueError("无效的研究区域边界")

    # bin 的边长默认取带宽的 1/3，保证卷积离散化误差 < 2%
    step = float(bin_size) if bin_size else bw / 3.0
    if step <= 0:
        raise ValueError("bin_size 必须为正")

    conn = db.get_conn()
    rw = _region_where(min_lon, min_lat, max_lon, max_lat)
    tw = _time_where(start, end)
    # 抽样必须带固定种子：无种子的 reservoir 抽样每次结果都不同，会让
    # 论文引用的密度数字和测试断言都不可复现（实测同参数两次峰值差 0.8%）。
    sql = (
        f"SELECT longitude, latitude FROM read_parquet('{config.TRAJECTORY_PARQUET}') "
        f"WHERE 1=1 {rw} {tw} "
        f"USING SAMPLE reservoir({int(sample_limit)} ROWS) REPEATABLE ({config.SEED})"
    )
    rows = conn.execute(sql).fetchall()
    if not rows:
        return {"count": 0, "cells": [], "meta": {}}

    pts = np.asarray(rows, dtype=float)
    lon = pts[:, 0]
    lat = pts[:, 1]

    # ---- 1. binning ----
    nx = max(2, int(round((e - w) / step)))
    ny = max(2, int(round((n - s) / step)))
    counts, xe, ye = np.histogram2d(lon, lat, bins=[nx, ny],
                                    range=[[w, e], [s, n]])

    # ---- 2. 可分离高斯卷积（等价于高斯核 KDE）----
    sigma_bins = bw / step
    kx = _gaussian_kernel_1d(sigma_bins)
    ky = _gaussian_kernel_1d(sigma_bins)
    tmp = np.apply_along_axis(lambda m: np.convolve(m, kx, mode="same"), 0, counts)
    smooth = np.apply_along_axis(lambda m: np.convolve(m, ky, mode="same"), 1, tmp)

    # ---- 3. 换算物理密度（艘 / nmile²）----
    lat_center = (s + n) / 2.0
    km_per_deg_lon_here = _deg_to_km(lat_center)
    bin_km_x = step * km_per_deg_lon_here
    bin_km_y = step * _KM_PER_DEG_LAT
    bin_nm_2 = (bin_km_x * _NM_PER_KM) * (bin_km_y * _NM_PER_KM)
    density = smooth / bin_nm_2 if bin_nm_2 > 0 else smooth

    # ---- 4. 重采样到输出网格 ----
    og = max(1, int(grid_size))
    fx = counts.shape[0] / og
    fy = counts.shape[1] / og
    ox = np.arange(og) * fx
    oy = np.arange(og) * fy
    ix = np.clip(ox.astype(int), 0, counts.shape[0] - 1)
    iy = np.clip(oy.astype(int), 0, counts.shape[1] - 1)
    out = density[np.ix_(ix, iy)]

    cells = []
    for i in range(og):
        for j in range(og):
            v = float(out[i, j])
            if v <= 1e-9:
                continue
            cells.append({
                "longitude": round(float((xe[ix[i]] + xe[ix[i] + 1]) / 2), 5),
                "latitude": round(float((ye[iy[j]] + ye[iy[j] + 1]) / 2), 5),
                "density": round(v, 6),
            })

    gpeak = round(float(out.max()), 4) if out.size else 0.0
    return {
        "count": int(len(rows)),
        "cells": cells,
        "meta": {
            "bandwidth_deg": bw,
            "bandwidth_km": round(float(bw * km_per_deg_lon_here), 3),
            "grid_size": og,
            "bin_count": int(counts.shape[0] * counts.shape[1]),
            "area_nm2": round(float((e - w) * km_per_deg_lon_here * _NM_PER_KM
                                    * (n - s) * _KM_PER_DEG_LAT * _NM_PER_KM), 1),
            # 全分辨率（步长=带宽/3）峰值，作为研究结论引用
            "bin_peak_density_nm2": round(float(density.max()), 4) if density.size else 0.0,
            # 输出网格（grid_size×grid_size）处的峰值，与前端渲染所见一致
            "grid_peak_density_nm2": gpeak,
            "mean_density_nm2": round(float(density.mean()), 6) if density.size else 0.0,
            "density_semantics": (
                "累计报文密度——对统计窗口内全部 AIS 报文点做 KDE，"
                "分子含同一艘船在不同时刻的重复计数；"
                "若要折算为瞬时船舶密度，需再除以窗口内的采样帧数。"
            ),
            "unit": "艘·报文/nmile²",
        },
    }


def peak_locations(top_n=10, **kwargs):
    """按核密度取前 N 个热点坐标（主航路交汇/密集区定位）。"""
    surface = kde_surface(**kwargs)
    cells = sorted(surface["cells"], key=lambda c: c["density"], reverse=True)
    return {"hotspots": cells[:int(top_n)], "meta": surface["meta"]}
