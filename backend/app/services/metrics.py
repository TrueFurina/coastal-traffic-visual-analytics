"""交通流 12 项特征参数评估体系 —— 对应申报书创新点 3.3。

把「定性描述」转成可复算的定量指标，每项对外同时给出：
    value      数值
    unit       单位（无量纲指标记为 "-"）
    desc       计算口径一句话说明（可直接用于论文/结题报告）

指标集合（12 项）：
    1  ship_count           船舶总数
    2  point_count          轨迹点总数
    3  avg_speed_kn         平均航速
    4  speed_std_kn         速度离散度
    5  speed_cv             速度变异系数
    6  speed_p95_kn         航速 95 分位
    7  avg_density_nm2      平均船舶密度
    8  max_density_nm2      峰值船舶密度
    9  flow_balance         流量均衡度
    10 course_entropy_bits  航向熵
    11 route_concentration  航路集中度
    12 congestion_ratio     拥堵指数
"""
import numpy as np
from app.core import config, db
from app.services import kde as kde_mod
from app.services.traffic import _region_where, _time_where


def _agg(min_lon, min_lat, max_lon, max_lat, start, end):
    """一次性向 DuckDB 要全部基础聚合量，避免多次全表扫描。"""
    conn = db.get_conn()
    rw = _region_where(min_lon, min_lat, max_lon, max_lat)
    tw = _time_where(start, end)
    base = f"read_parquet('{config.TRAJECTORY_PARQUET}') WHERE 1=1 {rw} {tw}"
    row = conn.execute(
        f"""SELECT count(*), count(DISTINCT mmsi), avg(speed), stddev(speed),
                   quantile_cont(speed, 0.95),
                   avg(CASE WHEN speed < 3.0 THEN 1.0 ELSE 0.0 END)
            FROM {base}"""
    ).fetchone()
    hist = conn.execute(
        f"""SELECT CAST(floor((COALESCE(course, 0) % 360) / 22.5) AS INT) AS sec,
                   count(*) FROM {base} GROUP BY sec ORDER BY sec"""
    ).fetchall()
    return row, hist


def _entropy_bits(counts):
    p = np.asarray(counts, dtype=float)
    p = p[p > 0]
    if p.size == 0:
        return 0.0
    p = p / p.sum()
    return float(-(p * np.log2(p)).sum())


def traffic_metrics(min_lon=None, min_lat=None, max_lon=None, max_lat=None,
                    start=None, end=None, bandwidth_deg=0.02):
    row, hist = _agg(min_lon, min_lat, max_lon, max_lat, start, end)
    point_count, ship_count = int(row[0] or 0), int(row[1] or 0)
    if point_count == 0:
        return {"count": 0, "indicators": [], "note": "所选时空范围内无轨迹点"}

    avg_speed = float(row[2] or 0.0)
    std_speed = float(row[3] or 0.0)
    p95 = float(row[4] or 0.0)
    congestion = float(row[5] or 0.0)

    sec_counts = np.zeros(16)
    for sec, c in hist:
        if 0 <= int(sec) < 16:
            sec_counts[int(sec)] = int(c)
    entropy = _entropy_bits(sec_counts)
    flow_balance = entropy / np.log2(16) if sec_counts.sum() else 0.0

    surface = kde_mod.kde_surface(bandwidth_deg=bandwidth_deg, grid_size=80,
                                  min_lon=min_lon, min_lat=min_lat,
                                  max_lon=max_lon, max_lat=max_lat,
                                  start=start, end=end)
    meta = surface.get("meta", {})
    densities = np.array([c["density"] for c in surface["cells"]], dtype=float)
    if densities.size:
        sorted_desc = np.sort(densities)[::-1]
        top_k = max(1, int(len(sorted_desc) * 0.05))
        route_conc = float(sorted_desc[:top_k].sum() / sorted_desc.sum())
    else:
        route_conc = 0.0

    cv = std_speed / avg_speed if avg_speed > 0 else 0.0

    raw = [
        ("ship_count", "船舶总数", ship_count, "艘",
         "统计窗口内出现过的唯一 MMSI 数量"),
        ("point_count", "轨迹点总数", point_count, "点",
         "AIS 报文记录数"),
        ("avg_speed_kn", "平均航速", round(avg_speed, 3), "kn",
         "全部轨迹点航速的算术平均"),
        ("speed_std_kn", "速度离散度", round(std_speed, 3), "kn",
         "航速标准差，反映水域内速度分化程度"),
        ("speed_cv", "速度变异系数", round(cv, 4), "-",
         "标准差/均值，消除量纲后比较不同水域"),
        ("speed_p95_kn", "航速 95 分位", round(p95, 3), "kn",
         "95% 的船舶航速低于该值，用于识别超速尾部"),
        ("avg_density_nm2", "平均船舶密度", meta.get("mean_density_nm2", 0.0),
         meta.get("unit", "艘/nmile²"),
         "核密度曲面全域均值（累计报文密度口径）"),
        ("max_density_nm2", "峰值船舶密度", meta.get("bin_peak_density_nm2", 0.0),
         meta.get("unit", "艘/nmile²"),
         "核密度曲面全分辨率峰值，用于定位最繁忙网格"),
        ("flow_balance", "流量均衡度", round(float(flow_balance), 4), "-",
         "航向 16 扇区分布的归一化熵，1 表示各方向完全均衡"),
        ("course_entropy_bits", "航向熵", round(float(entropy), 4), "bit",
         "航向分布的信息熵，越低说明航向越集中于主航路"),
        ("route_concentration", "航路集中度", round(route_conc, 4), "-",
         "密度最高的 5% 网格承载的密度占比，反映航路成带程度"),
        ("congestion_ratio", "拥堵指数", round(congestion, 4), "-",
         "航速 < 3kn 的点位数占比，表征低速拥堵程度"),
    ]

    return {
        "count": point_count,
        "bandwidth_deg": bandwidth_deg,
        "time_window": {"start": start, "end": end},
        "density_semantics": meta.get("density_semantics", ""),
        "indicators": [
            {"key": k, "name": name, "value": v, "unit": u, "desc": d}
            for k, name, v, u, d in raw
        ],
    }
