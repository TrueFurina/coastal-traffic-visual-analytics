"""船舶领域（Ship Domain）模型与侵犯检测。

领域侵犯与会遇(CPA)是互补的两类交互度量：CPA 衡量「按当前运动趋势未来
会接近到什么程度」，领域衡量「此刻是否已侵入他船的安全空间」。本模块同时
输出沿航向分量 along（即申报书所称的船头间距）与横向分量 cross。

两个模型均以**单一真值源**实现：`_radii` 是向量版，`domain_radius_nm`
只是它的标量包装，避免同一公式在两处漂移。
"""
import numpy as np
from app.core import config, db
from app.services import interaction as I

_NM = 1852.0
MODELS = ("fujii", "goodwin")

# Fujii & Tanaka (1974) 开阔水域：椭圆长轴 8L、短轴 3.2L，即半轴 4L / 1.6L
_FUJII_A, _FUJII_B = 4.0, 1.6
# Goodwin (1975) 三扇区圆域(nm)：首部 ±60° / 右舷 / 左舷，左右不对称
_GOODWIN_NM = (0.85, 0.70, 0.45)


def _radii(length_m, rb, model="fujii"):
    """各相对方位上的领域半径（nm）。length_m、rb 可为数组。"""
    if model == "goodwin":
        rb = np.asarray(rb, dtype=float)
        r = np.where(rb < 180.0, _GOODWIN_NM[1], _GOODWIN_NM[2])
        return np.where((rb <= 60.0) | (rb >= 300.0), _GOODWIN_NM[0], r)
    a = _FUJII_A * np.asarray(length_m, dtype=float)
    b = _FUJII_B * np.asarray(length_m, dtype=float)
    t = np.radians(np.asarray(rb, dtype=float))
    # 椭圆极坐标半径  r = ab / sqrt((b·cosθ)² + (a·sinθ)²)
    return (a * b) / np.sqrt((b * np.cos(t))**2 + (a * np.sin(t))**2) / _NM


def domain_radius_nm(length_m, rb, model="fujii"):
    """标量版领域半径（nm），供外部查询使用。"""
    return float(_radii(np.array([length_m]), np.array([rb]), model)[0])


def _ship_lengths():
    rows = db.get_conn().execute(
        f"SELECT mmsi, length FROM read_parquet('{config.SHIPS_PARQUET}')"
    ).fetchall()
    return {str(m): float(l or 0.0) for m, l in rows}


def violations(start=None, end=None, bbox=None, model="fujii",
               scale=1.0, limit=500):
    """扫描时间桶，返回船舶领域侵犯事件，按侵入深度排序。

    model: fujii(随船长缩放) | goodwin(固定 nm 扇区)
    scale: 领域缩放系数，用于敏感性分析
    """
    if model not in MODELS:
        raise ValueError(f"未知领域模型: {model}，可选 {MODELS}")
    data = I._load_buckets(start, end, bbox)
    if data is None:
        return {"count": 0, "violations": [], "parameters": {"model": model}}
    lengths = _ship_lengths()
    lat0 = float(data["lat"].mean())
    events, per_ship = [], {}
    overlap = 0
    for b in np.unique(data["b"]):
        idx = np.flatnonzero(data["b"] == b)
        if len(idx) < 2:
            continue
        sel = {k: v[idx] for k, v in data.items() if k != "b"}
        own_len = np.array([lengths.get(str(m), 0.0) for m in sel["mmsi"]])
        p = I._bucket_pairs(sel, lat0)
        if p["i"].size == 0:
            continue
        i, j = p["i"], p["j"]
        rad = _radii(own_len[i], p["rb"], model) * scale
        hit = (p["d0"] <= rad) & (p["d0"] > 0) & (own_len[i] > 0)
        for k in np.flatnonzero(hit):
            r = float(rad[k])
            d0 = float(p["d0"][k])
            rb = float(p["rb"][k])
            if d0 < 0.05:      # < 93 m，已达船体尺度量级的重叠
                overlap += 1
            events.append({
                "bucket_minutes": int(b) * I._BUCKET_SEC // 60,
                "own_mmsi": str(sel["mmsi"][i[k]]),
                "target_mmsi": str(sel["mmsi"][j[k]]),
                "longitude": round(float(sel["lon"][i[k]]), 5),
                "latitude": round(float(sel["lat"][i[k]]), 5),
                "distance_nm": round(d0, 4),
                "domain_radius_nm": round(r, 4),
                "penetration_ratio": round(1.0 - d0 / r, 4) if r > 0 else 0.0,
                # np.cos/sin 返回 np.float64，必须显式转回原生 float，
                # 否则 numpy 标量会泄漏到 API 返回值（历史坑）
                "along_nm": round(float(d0 * np.cos(np.radians(rb))), 4),
                "cross_nm": round(float(d0 * np.sin(np.radians(rb))), 4),
                "relative_bearing_deg": round(rb, 1),
                "_rank": 1.0 - d0 / r if r > 0 else 0.0,
            })
            per_ship[str(sel["mmsi"][i[k]])] = \
                per_ship.get(str(sel["mmsi"][i[k]]), 0) + 1
    events.sort(key=lambda e: -e["_rank"])
    for e in events:
        del e["_rank"]
    top_ships = sorted(per_ship.items(), key=lambda x: -x[1])[:10]
    return {
        "count": len(events),
        "returned": len(events[:int(limit)]),
        "violations": events[:int(limit)],
        "most_violated_ships": [{"mmsi": m, "count": c} for m, c in top_ships],
        "diagnostics": {
            "overlap_lt_0.05nm": overlap,
            "note": "距离小于 0.05 nm(约 93 m)已达船体尺度量级的重叠，属合成"
                    "数据保真度缺陷；此处如实报告数量而不剔除，因领域侵犯的"
                    "语义本就包含「已经很近」的情形",
        },
        "parameters": {"model": model, "scale": scale,
                       "axes_L": {"fujii_a": _FUJII_A, "fujii_b": _FUJII_B,
                                  "goodwin_nm": list(_GOODWIN_NM)}},
        "time_window": {"start": start, "end": end},
    }
