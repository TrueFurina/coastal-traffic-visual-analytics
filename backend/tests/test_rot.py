"""航向角变化率（ROT）单元测试 + 集成冒烟。

守门重点是三处「错了也不报错、只会让数字悄悄失真」的地方：
  1. 航向环绕：350°→10° 必须算成 +20°，而不是 -340°
  2. 时间间隔：dt <= 0 会让 ROT 除零，dt 过大则是丢包造成的伪转向
  3. 尺度依赖：窗口口径必须显著小于逐点口径（否则说明噪声没被压掉）
"""
import math
import duckdb
import pytest
from app.services import rot, multivariate

T0, T1 = "2024-06-01 00:00:00", "2024-06-01 06:00:00"
SMALL = dict(min_lon=122.0, min_lat=30.5, max_lon=122.6, max_lat=31.0)


def _val(d, key):
    return next(i["value"] for i in d["indicators"] if i["key"] == key)


def test_wrap_folding_handles_course_crossing():
    """环绕折叠。实现与测试共用 rot._wrap，改坏表达式必被抓到。"""
    cases = [(-340, 20), (340, -20), (0, 0), (20, 20), (-20, -20),
             (179, 179), (-179, -179), (180, -180), (-180, -180)]
    for d, want in cases:
        got = float(duckdb.query(f"SELECT {rot._wrap(str(d))}").fetchone()[0])
        assert abs(got - want) < 1e-9, f"d={d} got={got} want={want}"


def test_valid_cte_filters_nonpositive_and_huge_dt():
    """dt <= 0 与 dt 超上界的样本必须被剔除（用构造表实测过滤行为）。"""
    sql = (
        "WITH g AS (SELECT * FROM (VALUES (0.0, 10.0), (-5.0, 10.0), "
        f"(99999.0, 10.0), (60.0, 30.0)) AS t(dt_s, d_course)) {rot._valid_cte(600, 0)}"
    )
    rows = duckdb.query(sql).fetchall()
    assert len(rows) == 1, f"应只剩 dt=60 一行，实际 {len(rows)} 行"
    assert abs(float(rows[0][-1]) - 30.0) < 1e-9, "rot 应为 30 °/min"


@pytest.mark.integration
def test_window_scale_suppresses_pointwise_noise():
    """窗口口径的转向强度必须显著低于逐点口径 —— 这是噪声主导的判据。"""
    w = rot.rot_statistics(start=T0, end=T1, window_min=15)
    p = rot.rot_statistics(start=T0, end=T1, window_min=0)
    wm, pm = _val(w, "mean_abs_rot"), _val(p, "mean_abs_rot")
    assert w["count"] > 0 and p["count"] > 0
    assert wm < pm, f"窗口口径({wm}) 应低于逐点({pm})"
    assert w["diagnostics"]["noise_amplification"] > 1


@pytest.mark.integration
def test_rot_statistics_native_types_only():
    """原生类型护栏：JSON 序列化前的老坑，numpy 标量泄漏会带出 NaN/类型错。"""
    d = rot.rot_statistics(start=T0, end=T1)
    assert d["count"] > 0
    for i in d["indicators"]:
        v = i["value"]
        assert type(v) in (int, float) and not isinstance(v, bool), i["key"]
        assert math.isfinite(float(v)), f"{i['key']} 非有限值: {v}"
        assert isinstance(i["unit"], str) and i["desc"]


@pytest.mark.integration
def test_rot_respects_bbox():
    """框选必须真的缩小样本，否则前端框选是假的。"""
    full = rot.rot_statistics(start=T0, end=T1)["count"]
    small = rot.rot_statistics(start=T0, end=T1, **SMALL)["count"]
    assert 0 < small < full, f"small={small} full={full}"


@pytest.mark.integration
def test_rot_grid_and_by_type_structure():
    g = rot.rot_grid(start=T0, end=T1, grid_size=10)
    assert g["count"] > 0
    c = g["cells"][0]
    assert 0.0 <= c["maneuver_ratio"] <= 1.0
    assert math.isfinite(c["mean_abs_rot"])
    t = rot.rot_by_ship_type(start=T0, end=T1)
    assert t["count"] > 0
    for r in t["rows"]:
        assert 0.0 <= r["maneuver_ratio"] <= 1.0
        assert type(r["mean_abs_rot"]) in (int, float)


@pytest.mark.integration
def test_rot_distribution_bins_cover_all_samples():
    d = rot.rot_distribution(start=T0, end=T1, bins=8)
    assert d["count"] > 0 and len(d["bins"]) == 8
    assert sum(b["count"] for b in d["bins"]) == d["count"]


@pytest.mark.integration
def test_multivariate_includes_rot_axis_and_is_reproducible():
    """D1 闭环判据：平行坐标必须真的带上转向率这一维。"""
    m = multivariate.multivariate_sample(50, start=T0, end=T1)
    assert "rot" in [a["key"] for a in m["axes"]]
    assert m["count"] > 0 and all("rot" in r for r in m["rows"])
    assert m["ranges"]["rot"][0] <= m["ranges"]["rot"][1]
    m2 = multivariate.multivariate_sample(50, start=T0, end=T1)
    assert m["rows"][0]["mmsi"] == m2["rows"][0]["mmsi"], "seed 固定应可复现"


@pytest.mark.integration
def test_rot_samples_are_reproducible_and_finite():
    s = rot.rot_samples(30, start=T0, end=T1)
    assert s["count"] > 0
    assert all(math.isfinite(r["rot"]) for r in s["rows"])
    s2 = rot.rot_samples(30, start=T0, end=T1)
    assert s["rows"][0]["mmsi"] == s2["rows"][0]["mmsi"]
