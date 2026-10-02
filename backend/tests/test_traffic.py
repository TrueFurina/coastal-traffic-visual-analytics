"""交通流算法单元测试 + 数据层集成冒烟。"""
import os
import numpy as np
import pytest
import duckdb
from app.core import config
from app.services import traffic

HERE = os.path.dirname(os.path.abspath(__file__))


# ---------- 纯函数单元测试（不依赖数据集） ----------

def test_dp_simplify_straight_line():
    pts = np.array([[0.0, 0.0], [0.001, 0.0001], [0.002, 0.0],
                    [0.003, -0.0001], [0.004, 0.0]], dtype=float)
    out = traffic._dp_simplify(pts, 0.0005)
    # 直线应被抽稀为端点
    assert len(out) == 2
    assert np.allclose(out[0], [0.0, 0.0])
    assert np.allclose(out[-1], [0.004, 0.0])


def test_dp_simplify_keeps_corner():
    pts = np.array([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0]], dtype=float)
    out = traffic._dp_simplify(pts, 0.01)
    assert len(out) == 3  # 转角必须保留


def test_seg_intersect_crossing():
    # 水平线 (0,0)-(0,1) 与竖直线 (-1,0.5)-(1,0.5) 相交
    s = traffic._seg_intersect((-1.0, 0.5), (1.0, 0.5),
                               (0.0, 0.0), (0.0, 1.0))
    assert s != 0


def test_seg_intersect_parallel():
    s = traffic._seg_intersect((0.0, 0.0), (1.0, 0.0),
                               (0.0, 1.0), (1.0, 1.0))
    assert s == 0


def test_speed_course_bins_sum():
    rows = [(5.0, 90.0), (0.1, 200.0), (15.0, 0.0), (3.5, 350.0)]
    # 用内存 DuckDB 造小表测试分布统计的 bin/course/behavior 逻辑
    con = duckdb.connect(":memory:")
    con.execute(
        "CREATE TABLE t(speed DOUBLE, course DOUBLE); "
        "INSERT INTO t VALUES (5.0,90.0),(0.1,200.0),(15.0,0.0),(3.5,350.0)")
    spd = np.array([r[0] for r in con.execute("SELECT speed FROM t").fetchall()])
    crs = np.array([(r[0] or 0) % 360 for r in con.execute("SELECT course FROM t").fetchall()])
    hist, _ = np.histogram(spd, bins=traffic.SPEED_BINS)
    assert hist.sum() == 4
    sector = (np.floor(crs / 22.5).astype(int) % 16)
    assert int(np.bincount(sector, minlength=16).sum()) == 4


# ---------- 集成冒烟（需要 data/ais 下已生成数据集） ----------

def _dataset_ready():
    return (os.path.exists(config.TRAJECTORY_PARQUET)
            and os.path.exists(config.SHIPS_PARQUET))


@pytest.mark.skipif(not _dataset_ready(), reason="需先运行 scripts/generate_dataset.py")
def test_speed_course_integration():
    d = traffic.speed_course_distribution()
    # 期望点数与数据集真值对齐（不硬编码，防数据集再生成后漂移）
    total = duckdb.query(
        f"SELECT count(*) FROM read_parquet('{config.TRAJECTORY_PARQUET}')"
    ).fetchone()[0]
    assert d["count"] == total
    b = d["behavior"]
    assert b["anchored"] + b["maneuvering"] + b["underway"] == total


@pytest.mark.skipif(not _dataset_ready(), reason="需先运行 scripts/generate_dataset.py")
def test_corridors_integration():
    corr = traffic.extract_corridors(grid_size=60, threshold_ratio=0.5)
    assert len(corr) >= 1  # 至少一条主航道被识别


@pytest.mark.skipif(not _dataset_ready(), reason="需先运行 scripts/generate_dataset.py")
def test_sectional_flow_integration():
    r = traffic.sectional_flow([(122.0, 30.8), (123.0, 30.8)])
    assert "total" in r and "seaward" in r and "landward" in r
    assert r["seaward"] + r["landward"] == r["total"]


@pytest.mark.skipif(not _dataset_ready(), reason="需先运行 scripts/generate_dataset.py")
def test_od_integration():
    od = traffic.od_matrix(grid_size=20, top_n=10)
    assert len(od) >= 1
    assert "origin" in od[0] and "destination" in od[0] and "count" in od[0]


@pytest.mark.skipif(not _dataset_ready(), reason="需先运行 scripts/generate_dataset.py")
def test_simplify_integration():
    # 取任意一艘船做抽稀，点应少于原始点数或相等（短轨迹）
    ships = duckdb.query(
        f"SELECT mmsi FROM read_parquet('{config.SHIPS_PARQUET}') LIMIT 1"
    ).fetchone()[0]
    pts = traffic.simplify_trajectory(str(ships), tolerance_deg=0.003, limit=5000)
    assert isinstance(pts, list) and len(pts) >= 2
