"""交通流分析算法层（研究核心）。

包含：航速/航向分布 + 行为分类、断面流量、轨迹抽稀(Douglas-Peucker)、
主航线/走廊提取（密度网格连通分量）、OD 分析。
全部基于 DuckDB 直接读 Parquet，无额外 ML 依赖。
"""
import numpy as np
from app.core import config, db

SA = config.STUDY_AREA


def _region_where(min_lon, min_lat, max_lon, max_lat, alias=""):
    p = f"{alias}." if alias else ""
    if None in (min_lon, min_lat, max_lon, max_lat):
        return ""
    return (f" AND {p}longitude BETWEEN {min_lon} AND {max_lon}"
            f" AND {p}latitude BETWEEN {min_lat} AND {max_lat}")


def _ts(value):
    if not value:
        return None
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return f"TIMESTAMP '{dt.strftime('%Y-%m-%d %H:%M:%S')}'"
    except Exception:
        return None


def _time_where(start, end, alias=""):
    p = f"{alias}." if alias else ""
    conds = []
    s = _ts(start)
    if s:
        conds.append(f"{p}timestamp >= {s}")
    e = _ts(end)
    if e:
        conds.append(f"{p}timestamp <= {e}")
    return (" AND " + " AND ".join(conds)) if conds else ""


# ---------- 2.3 航速/航向分布 + 行为分类 ----------

SPEED_BINS = [0.0, 0.5, 2.0, 5.0, 8.0, 12.0, 16.0, 25.0, 40.0]
SPEED_LABELS = ["停泊(<0.5)", "低速(0.5-2)", "机动(2-5)", "慢速(5-8)",
                "常速(8-12)", "较快(12-16)", "高速(16-25)", "超速(>25)"]


def speed_course_distribution(min_lon=None, min_lat=None, max_lon=None,
                              max_lat=None, start=None, end=None):
    conn = db.get_conn()
    rw = _region_where(min_lon, min_lat, max_lon, max_lat)
    tw = _time_where(start, end)
    rows = conn.execute(
        f"SELECT speed, course FROM read_parquet('{config.TRAJECTORY_PARQUET}') "
        f"WHERE 1=1 {rw} {tw}"
    ).fetchall()
    if not rows:
        return {"count": 0, "speed_hist": [], "course_hist": [],
                "behavior": {"anchored": 0, "maneuvering": 0, "underway": 0}}
    spd = np.array([r[0] for r in rows], dtype=float)
    crs = np.array([(r[1] or 0.0) for r in rows], dtype=float) % 360.0

    hist, _ = np.histogram(spd, bins=SPEED_BINS)
    speed_hist = [{"label": SPEED_LABELS[i], "count": int(hist[i])}
                  for i in range(len(SPEED_BINS) - 1)]

    sector = (np.floor(crs / 22.5).astype(int) % 16)
    cc = np.bincount(sector, minlength=16)
    course_hist = [{"sector_deg": i * 22.5, "count": int(cc[i])}
                   for i in range(16)]

    anchored = int((spd < 0.5).sum())          # 锚泊/停泊
    maneuvering = int(((spd >= 0.5) & (spd < 3.0)).sum())  # 机动/进出港
    underway = int((spd >= 3.0).sum())          # 在航
    return {"count": len(rows), "speed_hist": speed_hist,
            "course_hist": course_hist,
            "behavior": {"anchored": anchored, "maneuvering": maneuvering,
                         "underway": underway}}


# ---------- 2.2 断面流量 ----------

def _seg_intersect(p1, p2, p3, p4):
    """判断线段 p1p2 与 p3p4 是否相交，返回方向符号（+1/-1/0）。"""
    x1, y1, x2, y2 = p1[0], p1[1], p2[0], p2[1]
    x3, y3, x4, y4 = p3[0], p3[1], p4[0], p4[1]
    d = (x2 - x1) * (y4 - y3) - (y2 - y1) * (x4 - x3)
    if abs(d) < 1e-15:
        return 0
    t = ((x3 - x1) * (y4 - y3) - (y3 - y1) * (x4 - x3)) / d
    u = ((x3 - x1) * (y2 - y1) - (y3 - y1) * (x2 - x1)) / d
    if 0.0 <= t <= 1.0 and 0.0 <= u <= 1.0:
        return 1 if d > 0 else -1
    return 0


def sectional_flow(barrier, min_lon=None, min_lat=None, max_lon=None,
                   max_lat=None, start=None, end=None, cell=0.1):
    """统计穿越断面线(barrier: [(lon1,lat1),(lon2,lat2)]) 的船舶流量。

    返回：双向计数、按网格(约 cell 度)分区的交点、时间序列。
    """
    conn = db.get_conn()
    rw = _region_where(min_lon, min_lat, max_lon, max_lat)
    tw = _time_where(start, end)
    rows = conn.execute(
        f"SELECT mmsi, timestamp, longitude, latitude FROM "
        f"read_parquet('{config.TRAJECTORY_PARQUET}') WHERE 1=1 {rw} {tw} "
        f"ORDER BY mmsi, timestamp"
    ).fetchall()

    A = np.array(barrier[0], dtype=float)
    B = np.array(barrier[1], dtype=float)
    crossings = []
    prev = None
    for mmsi, ts, lon, lat in rows:
        cur = (float(lon), float(lat))
        if prev and prev[0] == mmsi:
            sgn = _seg_intersect(prev[1], cur, A, B)
            if sgn != 0:
                crossings.append({"mmsi": str(mmsi), "timestamp": str(ts),
                                  "direction": "seaward" if sgn > 0 else "landward"})
        prev = (mmsi, cur)

    n = len(crossings)
    seaward = sum(1 for c in crossings if c["direction"] == "seaward")
    landward = n - seaward

    # 时间序列：按小时桶
    import collections
    from datetime import datetime
    buckets = collections.Counter()
    for c in crossings:
        dt = datetime.fromisoformat(str(c["timestamp"]).replace("Z", "+00:00"))
        buckets[dt.strftime("%Y-%m-%d %H:00")] += 1
    ts_series = [{"hour": h, "count": v} for h, v in sorted(buckets.items())]
    return {"total": n, "seaward": seaward, "landward": landward,
            "crossings": crossings[:500], "timeseries": ts_series}


# ---------- 2.4 轨迹抽稀（Douglas-Peucker） ----------

def _dp_simplify(pts, tol):
    """迭代式 Douglas-Peucker 抽稀，pts: Nx2 numpy。"""
    n = len(pts)
    if n <= 2:
        return pts
    keep = np.zeros(n, dtype=bool)
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    while stack:
        i, j = stack.pop()
        if j - i < 2:
            continue
        a, b = pts[i], pts[j]
        d = b - a
        seg_len = np.hypot(d[0], d[1])
        if seg_len < 1e-12:
            continue
        # 垂线距离
        v = pts[i + 1:j] - a
        cross = abs(v[:, 0] * d[1] - v[:, 1] * d[0]) / seg_len
        k = np.argmax(cross) + (i + 1)
        if cross[k - (i + 1)] > tol:
            keep[k] = True
            stack.append((i, k))
            stack.append((k, j))
    return pts[keep]


def simplify_trajectory(mmsi, tolerance_deg=0.002, limit=config.TRAJ_POINT_LIMIT,
                        start=None, end=None):
    conn = db.get_conn()
    tw = _time_where(start, end)
    rows = conn.execute(
        f"SELECT longitude, latitude FROM read_parquet('{config.TRAJECTORY_PARQUET}') "
        f"WHERE mmsi = {int(mmsi)} {tw} ORDER BY timestamp LIMIT {int(limit)}"
    ).fetchall()
    if len(rows) < 3:
        return [{"longitude": r[0], "latitude": r[1]} for r in rows]
    pts = np.array([[r[0], r[1]] for r in rows], dtype=float)
    simp = _dp_simplify(pts, tolerance_deg)
    return [{"longitude": float(p[0]), "latitude": float(p[1])} for p in simp]


# ---------- 2.5 主航线/走廊提取（密度网格连通分量） ----------

def extract_corridors(grid_size=60, threshold_ratio=0.5, start=None, end=None):
    """高于密度阈值的网格做 4-连通分量标注，输出每条走廊的网格中心序列。"""
    conn = db.get_conn()
    min_lon, min_lat = SA["min_lon"], SA["min_lat"]
    max_lon, max_lat = SA["max_lon"], SA["max_lat"]
    cell_lon = (max_lon - min_lon) / grid_size
    cell_lat = (max_lat - min_lat) / grid_size
    tw = _time_where(start, end)
    rows = conn.execute(
        f"SELECT floor((longitude - {min_lon}) / {cell_lon}) gx, "
        f"floor((latitude - {min_lat}) / {cell_lat}) gy, count(*) c "
        f"FROM read_parquet('{config.TRAJECTORY_PARQUET}') "
        f"WHERE longitude BETWEEN {min_lon} AND {max_lon} "
        f"AND latitude BETWEEN {min_lat} AND {max_lat} {tw} GROUP BY gx, gy"
    ).fetchall()
    if not rows:
        return []
    cells = {(int(gx), int(gy)): int(c) for gx, gy, c in rows}
    thr = threshold_ratio * np.mean(list(cells.values()))
    hot = {k for k, v in cells.items() if v >= thr}

    # 4-连通分量
    seen = set()
    components = []
    for seed in hot:
        if seed in seen:
            continue
        comp = []
        stack = [seed]
        seen.add(seed)
        while stack:
            cx, cy = stack.pop()
            comp.append((cx, cy))
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nb = (cx + dx, cy + dy)
                if nb in hot and nb not in seen:
                    seen.add(nb)
                    stack.append(nb)
        if len(comp) >= 3:
            components.append(comp)

    corridors = []
    for comp in components:
        lngs = [min_lon + (gx + 0.5) * cell_lon for gx, _ in comp]
        lats = [min_lat + (gy + 0.5) * cell_lat for _, gy in comp]
        corridors.append({
            "cell_count": len(comp),
            "centers": [{"longitude": float(lo), "latitude": float(la)}
                        for lo, la in zip(lngs, lats)],
        })
    corridors.sort(key=lambda c: c["cell_count"], reverse=True)
    return corridors


# ---------- 2.6 时刻快照（时间回放用） ----------

def snapshot(at, min_lon=None, min_lat=None, max_lon=None, max_lat=None,
             limit=5000):
    """返回指定时刻每艘船的最新一条 AIS 报文（位置/航速/航向/船名/船型）。"""
    conn = db.get_conn()
    ts = _ts(at)
    if not ts:
        return []
    rw = _region_where(min_lon, min_lat, max_lon, max_lat)
    rows = conn.execute(
        f"WITH p AS ("
        f"  SELECT CAST(mmsi AS VARCHAR) mmsi, "
        f"         arg_max(longitude, timestamp) lon, "
        f"         arg_max(latitude, timestamp) lat, "
        f"         arg_max(speed, timestamp) spd, "
        f"         arg_max(course, timestamp) crs, "
        f"         max(timestamp) ts "
        f"  FROM read_parquet('{config.TRAJECTORY_PARQUET}') "
        f"  WHERE timestamp <= {ts} {rw} GROUP BY mmsi"
        f") "
        f"SELECT p.mmsi, s.name, s.ship_type, p.lon, p.lat, p.spd, p.crs, p.ts "
        f"FROM p LEFT JOIN read_parquet('{config.SHIPS_PARQUET}') s "
        f"ON p.mmsi = CAST(s.mmsi AS VARCHAR) "
        f"LIMIT {int(limit)}"
    ).fetchall()
    return [{
        "mmsi": r[0], "name": r[1] or "", "ship_type": r[2] or "其他",
        "longitude": float(r[3]), "latitude": float(r[4]),
        "speed": float(r[5] or 0.0), "course": float(r[6] or 0.0),
        "timestamp": str(r[7]),
    } for r in rows]


# ---------- 2.5 OD 分析 ----------

def od_matrix(grid_size=20, start=None, end=None, top_n=20):
    """每艘船取时间窗内首末点，映射到网格，统计 OD 流量。"""
    conn = db.get_conn()
    min_lon, min_lat = SA["min_lon"], SA["min_lat"]
    max_lon, max_lat = SA["max_lon"], SA["max_lat"]
    cell_lon = (max_lon - min_lon) / grid_size
    cell_lat = (max_lat - min_lat) / grid_size
    tw = _time_where(start, end)
    rows = conn.execute(
        f"SELECT mmsi, longitude, latitude, timestamp FROM "
        f"read_parquet('{config.TRAJECTORY_PARQUET}') WHERE 1=1 {tw} "
        f"ORDER BY mmsi, timestamp"
    ).fetchall()

    def cell(lon, lat):
        gx = int((lon - min_lon) / cell_lon)
        gy = int((lat - min_lat) / cell_lat)
        return (gx, gy)

    first, last = {}, {}
    for mmsi, lon, lat, ts in rows:
        m = int(mmsi)
        if m not in first:
            first[m] = cell(lon, lat)
        last[m] = cell(lon, lat)

    from collections import Counter
    cnt = Counter((first[m], last[m]) for m in first)
    out = []
    for (o, d), c in cnt.most_common(top_n):
        out.append({
            "origin": {"longitude": min_lon + (o[0] + 0.5) * cell_lon,
                       "latitude": min_lat + (o[1] + 0.5) * cell_lat},
            "destination": {"longitude": min_lon + (d[0] + 0.5) * cell_lon,
                            "latitude": min_lat + (d[1] + 0.5) * cell_lat},
            "count": int(c),
        })
    return out
