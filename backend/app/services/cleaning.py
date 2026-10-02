"""AIS 轨迹清洗管道：去重 / 越界 / 超速 / 跳点。

输入：行列表（dict，键含 mmsi, timestamp, longitude, latitude, speed ...）
输出：(清洗后行, 清洗报告)
所有阈值来自 app.core.config。
"""
from app.core import config

# 清洗用宽松边界（研究水域外扩，容忍航道边界船）
CLEAN_BOUNDS = {
    "min_lon": config.STUDY_AREA["min_lon"] - 0.3,
    "max_lon": config.STUDY_AREA["max_lon"] + 0.3,
    "min_lat": config.STUDY_AREA["min_lat"] - 0.3,
    "max_lat": config.STUDY_AREA["max_lat"] + 0.3,
}


def _to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _parse_ts(v):
    """返回 epoch 秒；失败返回 None。"""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        # 是否为毫秒时间戳
        return v / 1000.0 if v > 1e12 else float(v)
    s = str(v).strip()
    # 纯数字
    if s.replace(".", "", 1).isdigit():
        f = float(s)
        return f / 1000.0 if f > 1e12 else f
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            from datetime import datetime
            return datetime.fromisoformat(s).timestamp()
        except Exception:
            continue
    return None


def _haversine_km(lon1, lat1, lon2, lat2):
    import numpy as np
    r = 6371.0
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = np.sin(dlat / 2) ** 2 + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def clean_trajectories(rows):
    report = {
        "total_in": len(rows),
        "parsed": 0, "dropped_missing": 0, "dropped_bounds": 0,
        "dropped_dup": 0, "dropped_speed": 0, "dropped_jump": 0,
        "total_out": 0,
    }
    norm = []
    for r in rows:
        mmsi = r.get("mmsi")
        ts = _parse_ts(r.get("timestamp"))
        lon = _to_float(r.get("longitude"))
        lat = _to_float(r.get("latitude"))
        if mmsi in (None, "") or ts is None or lon is None or lat is None:
            report["dropped_missing"] += 1
            continue
        spd = _to_float(r.get("speed"))
        crs = _to_float(r.get("course"))
        nm = r.get("name") or ""
        stype = r.get("ship_type") or ""
        norm.append({
            "mmsi": int(mmsi), "timestamp": float(ts),
            "longitude": lon, "latitude": lat,
            "speed": 0.0 if spd is None else spd,
            "course": 0.0 if crs is None else crs,
            "ship_type": stype, "name": nm,
        })
    report["parsed"] = len(norm)

    # 越界过滤
    b = CLEAN_BOUNDS
    kept = []
    for r in norm:
        if not (b["min_lon"] <= r["longitude"] <= b["max_lon"]
                and b["min_lat"] <= r["latitude"] <= b["max_lat"]):
            report["dropped_bounds"] += 1
            continue
        kept.append(r)

    # 去重 (mmsi + timestamp)
    seen = set()
    dedup = []
    for r in kept:
        key = (r["mmsi"], r["timestamp"])
        if key in seen:
            report["dropped_dup"] += 1
            continue
        seen.add(key)
        dedup.append(r)

    # 超速过滤
    speed_ok = []
    for r in dedup:
        if r["speed"] > config.MAX_SPEED_KN:
            report["dropped_speed"] += 1
            continue
        speed_ok.append(r)

    # 跳点过滤：同船相邻点推算速度过大
    speed_ok.sort(key=lambda x: (x["mmsi"], x["timestamp"]))
    last = {}
    jump_ok = []
    for r in speed_ok:
        m = r["mmsi"]
        if m in last:
            dt = r["timestamp"] - last[m]["timestamp"]
            if dt > 0:
                dist = _haversine_km(last[m]["longitude"], last[m]["latitude"],
                                    r["longitude"], r["latitude"])
                implied = (dist / dt * 3600.0) if dt > 0 else 0.0  # km/h
                if implied > config.JUMP_SPEED_KN * 1.852:  # kn -> km/h
                    report["dropped_jump"] += 1
                    last[m] = r  # 以当前点作为新基准
                    continue
        last[m] = r
        jump_ok.append(r)

    report["total_out"] = len(jump_ok)
    return jump_ok, report
