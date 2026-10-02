"""DuckDB 连接管理：内存连接，直接查询 Parquet 文件。"""
import os
import duckdb
from app.core import config

_CONN = None


def get_conn() -> duckdb.DuckDBPyConnection:
    global _CONN
    if _CONN is None:
        _CONN = duckdb.connect(database=":memory:")
        # 现代 DuckDB 内置 parquet 支持，无需显式 LOAD
    return _CONN


def trajectories_exist() -> bool:
    return os.path.exists(config.TRAJECTORY_PARQUET)


def ships_exist() -> bool:
    return os.path.exists(config.SHIPS_PARQUET)
