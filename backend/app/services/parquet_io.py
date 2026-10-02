"""Parquet 读写层：表构造、去重合并、CSV 导入追加。

与 ais_store.py（查询层）分离，保持单文件体量可控。
"""
import os
import pyarrow as pa
import pyarrow.parquet as pq
from datetime import datetime
from app.core import config, db

TRAJ = lambda: config.TRAJECTORY_PARQUET
SHIPS = lambda: config.SHIPS_PARQUET

TRAJ_SCHEMA = pa.schema([
    ("mmsi", pa.int64()),
    ("timestamp", pa.timestamp("s")),
    ("longitude", pa.float64()),
    ("latitude", pa.float64()),
    ("speed", pa.float64()),
    ("course", pa.float64()),
    ("ship_type", pa.string()),
    ("name", pa.string()),
])
SHIPS_SCHEMA = pa.schema([
    ("mmsi", pa.int64()),
    ("name", pa.string()),
    ("ship_type", pa.string()),
    ("length", pa.float64()),
    ("width", pa.float64()),
])


def _build_traj_table(rows):
    from app.services.cleaning import _parse_ts
    mmsi = [int(r["mmsi"]) for r in rows]
    ts = [datetime.fromtimestamp(_parse_ts(r.get("timestamp"))) for r in rows]
    return pa.table({
        "mmsi": pa.array(mmsi, type=pa.int64()),
        "timestamp": pa.array(ts, type=pa.timestamp("s")),
        "longitude": pa.array([float(r["longitude"]) for r in rows], pa.float64()),
        "latitude": pa.array([float(r["latitude"]) for r in rows], pa.float64()),
        "speed": pa.array([float(r.get("speed", 0) or 0) for r in rows], pa.float64()),
        "course": pa.array([float(r.get("course", 0) or 0) for r in rows], pa.float64()),
        "ship_type": pa.array([str(r.get("ship_type", "") or "") for r in rows], pa.string()),
        "name": pa.array([str(r.get("name", "") or "") for r in rows], pa.string()),
    }, schema=TRAJ_SCHEMA)


def _build_ships_table(rows):
    return pa.table({
        "mmsi": pa.array([int(r["mmsi"]) for r in rows], type=pa.int64()),
        "name": pa.array([str(r.get("name", "") or "") for r in rows], pa.string()),
        "ship_type": pa.array([str(r.get("ship_type", "") or "") for r in rows], pa.string()),
        "length": pa.array([float(r.get("length", 0) or 0) for r in rows], pa.float64()),
        "width": pa.array([float(r.get("width", 0) or 0) for r in rows], pa.float64()),
    }, schema=SHIPS_SCHEMA)


def _merge_write(new_table, path, part_cols):
    """将新表与已有 Parquet 合并，按 part_cols 去重（保留新数据）。"""
    conn = db.get_conn()
    if not os.path.exists(path):
        pq.write_table(new_table, path)
        return
    tmp = path + ".tmp.parquet"
    pq.write_table(new_table, tmp)
    part = ", ".join(part_cols)
    sql = f"""
        COPY (
            SELECT * FROM (
                SELECT *, 1 AS pri FROM read_parquet('{path}')
                UNION ALL
                SELECT *, 2 AS pri FROM read_parquet('{tmp}')
            )
            QUALIFY row_number() OVER (PARTITION BY {part} ORDER BY pri DESC) = 1
        ) TO '{path}' (FORMAT PARQUET)
    """
    try:
        conn.execute(sql)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def append_trajectories(rows):
    _merge_write(_build_traj_table(rows), TRAJ(), ["mmsi", "timestamp"])


def append_ships(rows):
    _merge_write(_build_ships_table(rows), SHIPS(), ["mmsi"])
