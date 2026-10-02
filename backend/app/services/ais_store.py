"""AIS 数据访问层：DuckDB 直接查询 Parquet。

查询封装：船舶列表（分页带最新位置）、单船轨迹（时间窗+抽稀）、
网格密度聚合、统计。CSV 导入追加见 parquet_io.py。
"""
import os
import pyarrow as pa
import pyarrow.parquet as pq
from datetime import datetime
from app.core import config, db
from app.services.parquet_io import append_ships, append_trajectories

TRAJ = lambda: config.TRAJECTORY_PARQUET
SHIPS = lambda: config.SHIPS_PARQUET


def _ts_sql(value):
    """将 ISO 时间转为 DuckDB TIMESTAMP 字面量，失败返回 None。"""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return f"TIMESTAMP '{dt.strftime('%Y-%m-%d %H:%M:%S')}'"
    except Exception:
        return None


def _esc(s):
    return str(s).replace("'", "''")


def _region_where(min_lon, min_lat, max_lon, max_lat, alias=""):
    p = f"{alias}." if alias else ""
    if None in (min_lon, min_lat, max_lon, max_lat):
        return ""
    return (f" AND {p}longitude BETWEEN {min_lon} AND {max_lon}"
            f" AND {p}latitude BETWEEN {min_lat} AND {max_lat}")


def _time_where(start, end, alias=""):
    p = f"{alias}." if alias else ""
    conds = []
    ts = _ts_sql(start)
    if ts:
        conds.append(f"{p}timestamp >= {ts}")
    ts = _ts_sql(end)
    if ts:
        conds.append(f"{p}timestamp <= {ts}")
    return (" AND " + " AND ".join(conds)) if conds else ""


# ---------- 查询 ----------

def list_ships(limit=config.SHIP_LIST_LIMIT, offset=0, min_lon=None,
               min_lat=None, max_lon=None, max_lat=None, ship_type=None):
    conn = db.get_conn()
    where = _region_where(min_lon, min_lat, max_lon, max_lat, "l")
    if ship_type:
        where += f" AND s.ship_type = '{_esc(ship_type)}'"
    sql = f"""
        WITH latest AS (
            SELECT mmsi, longitude, latitude, speed, course, timestamp,
                   row_number() OVER (PARTITION BY mmsi ORDER BY timestamp DESC) rn
            FROM read_parquet('{TRAJ()}')
        )
        SELECT s.mmsi, s.name, s.ship_type, s.length, s.width,
               l.longitude, l.latitude, l.speed, l.course, l.timestamp
        FROM read_parquet('{SHIPS()}') s
        LEFT JOIN (SELECT * FROM latest WHERE rn=1) l ON s.mmsi = l.mmsi
        WHERE 1=1 {where}
        ORDER BY s.mmsi
        LIMIT {int(limit)} OFFSET {int(offset)}
    """
    rows = conn.execute(sql).fetchall()
    out = []
    for m, nm, st, ln, wd, lon, lat, sp, cr, ts in rows:
        speed = sp if sp is not None else 0.0
        out.append({
            "id": str(m), "mmsi": str(m), "name": nm or "",
            "ship_type": st or "", "length": ln or 0.0, "width": wd or 0.0,
            "longitude": lon, "latitude": lat, "speed": speed,
            "course": cr or 0.0,
            "status": "锚泊" if speed < 0.5 else "航行中",
            "lastUpdated": str(ts) if ts is not None else None,
        })
    return out


def get_ship(mmsi):
    conn = db.get_conn()
    rows = conn.execute(
        f"SELECT mmsi, name, ship_type, length, width "
        f"FROM read_parquet('{SHIPS()}') WHERE mmsi = {int(mmsi)}"
    ).fetchall()
    if not rows:
        return None
    m, nm, st, ln, wd = rows[0]
    return {"mmsi": str(m), "name": nm, "ship_type": st,
            "length": ln, "width": wd}


def get_ship_trajectory(mmsi, limit=config.TRAJ_POINT_LIMIT, start=None, end=None):
    conn = db.get_conn()
    if get_ship(mmsi) is None:
        return None
    tw = _time_where(start, end)
    total = conn.execute(
        f"SELECT count(*) FROM read_parquet('{TRAJ()}') "
        f"WHERE mmsi = {int(mmsi)} {tw}"
    ).fetchone()[0]
    if total == 0:
        return []
    step = max(1, (total + limit - 1) // limit) if total > limit else 1
    sql = f"""
        WITH ranked AS (
            SELECT *, row_number() OVER (ORDER BY timestamp) rn
            FROM read_parquet('{TRAJ()}')
            WHERE mmsi = {int(mmsi)} {tw}
        )
        SELECT mmsi, timestamp, longitude, latitude, speed, course
        FROM ranked WHERE (rn - 1) % {step} = 0
        ORDER BY timestamp
    """
    rows = conn.execute(sql).fetchall()
    return [_point(r) for r in rows]


def _point(r):
    mmsi, ts, lon, lat, sp, cr = r
    return {
        "id": f"{mmsi}_{int(ts.timestamp()) if hasattr(ts,'timestamp') else ts}",
        "ship_id": str(mmsi),
        "timestamp": str(ts),
        "longitude": lon, "latitude": lat,
        "speed": sp, "course": cr, "heading": cr,
    }


def grid_density(min_lon, min_lat, max_lon, max_lat, grid_size=50,
                 start=None, end=None, ship_type=None):
    conn = db.get_conn()
    cell_lon = (max_lon - min_lon) / grid_size
    cell_lat = (max_lat - min_lat) / grid_size
    tw = _time_where(start, end)
    extra = ""
    if ship_type:
        extra = f" AND ship_type = '{_esc(ship_type)}'"
    sql = f"""
        SELECT floor((longitude - {min_lon}) / {cell_lon}) gx,
               floor((latitude - {min_lat}) / {cell_lat}) gy,
               count(*) density
        FROM read_parquet('{TRAJ()}')
        WHERE longitude BETWEEN {min_lon} AND {max_lon}
          AND latitude BETWEEN {min_lat} AND {max_lat} {tw} {extra}
        GROUP BY gx, gy
    """
    rows = conn.execute(sql).fetchall()
    out = []
    for gx, gy, d in rows:
        out.append({
            "longitude": min_lon + (gx + 0.5) * cell_lon,
            "latitude": min_lat + (gy + 0.5) * cell_lat,
            "density": int(d),
        })
    return out


def statistics(min_lon=None, min_lat=None, max_lon=None, max_lat=None,
              start=None, end=None):
    conn = db.get_conn()
    rw = _region_where(min_lon, min_lat, max_lon, max_lat)
    tw = _time_where(start, end)
    base = (f"FROM read_parquet('{TRAJ()}') WHERE 1=1 {rw} {tw}")
    tot = conn.execute(f"SELECT count(*), count(DISTINCT mmsi), "
                       f"min(timestamp), max(timestamp) {base}").fetchone()
    points, ships, tmin, tmax = tot
    avg = (points / ships) if ships else 0.0
    dist = {}
    if ships:
        dr = conn.execute(
            f"SELECT ship_type, count(DISTINCT mmsi) {base} GROUP BY ship_type"
        ).fetchall()
        dist = {st: int(c) for st, c in dr}
    return {
        "total_ships": int(ships),
        "total_trajectory_points": int(points),
        "average_points_per_ship": round(avg, 2),
        "time_range": {
            "start": str(tmin) if tmin is not None else None,
            "end": str(tmax) if tmax is not None else None,
        },
        "ship_type_distribution": dist,
    }
