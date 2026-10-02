"""船舶交互感知层（L2）的守门测试。

这一段历史上出过三类真实 bug，测试必须能抓住它们：
1. 追越判定方向反了（把「本船是追越船」判成「本船被追越」）—— 对称性测试守住；
2. 交叉的左右舷边界误用了对遇参数，导致 39% 落到「其他」—— 覆盖率测试守住；
3. 合成数据的多船重叠被当成真实会遇 —— 退化样本排除的断言守住。
另含 CPA 解析解校验与领域模型标定值校验（防公式漂移）。
"""
import numpy as np
import pytest
from app.services import interaction as I
from app.services import domain as D
from app.services.colregs import classify

_NM = 1852.0


# ---------- COLREGs：追越方向（历史 bug #1） ----------

def test_overtake_direction_forward_means_own_is_overtaking():
    """目标在本船正前方、航向一致 → 本船是追越船，必须让路。"""
    sit, duty = classify(rb=0.0, hd=0.0)
    assert sit == "追越"
    assert "让路" in duty


def test_overtake_direction_astern_means_own_is_stand_on():
    """目标在本船正横后 → 是目标在追本船，本船为直航船（曾判反）。"""
    sit, duty = classify(rb=180.0, hd=0.0)
    assert sit == "追越"
    assert "直航" in duty


def test_overtake_symmetry_reverses_responsibility():
    """同一追越局面换视角看，责任必须相反 —— 对称性护栏。"""
    rb, hd = 30.0, 5.0
    a = classify(rb, hd)
    b = classify((rb + 180.0) % 360.0, hd)
    assert a[0] == b[0] == "追越"
    assert ("让路" in a[1]) != ("让路" in b[1]), "双方不能同时让路或同时直航"


def test_overtake_beam_band_decided_by_speed():
    """正横带无法靠方位区分时，由航速高低裁决。"""
    fast = classify(rb=90.0, hd=5.0, own_speed_kn=15.0, target_speed_kn=5.0)
    slow = classify(rb=90.0, hd=5.0, own_speed_kn=5.0, target_speed_kn=15.0)
    assert "让路" in fast[1]
    assert "直航" in slow[1]


# ---------- COLREGs：局面覆盖率（历史 bug #2） ----------

def test_head_on_by_heading_diff_regardless_of_bearing():
    """航向差 >157.5° 一律判对遇，不再看相对方位（Rule 14）。"""
    for rb in (0.0, 45.0, 90.0, 135.0, 180.0, 270.0, 359.0):
        assert classify(rb, 170.0)[0] == "对遇", f"rb={rb} 应判对遇"


def test_crossing_right_side_gives_way():
    """航向交叉时：目标在右舷(0<rb<180) 本船让路；左舷 本船直航。"""
    assert "让路" in classify(rb=45.0, hd=90.0)[1]
    assert "直航" in classify(rb=225.0, hd=90.0)[1]
    assert classify(rb=45.0, hd=90.0)[0] == "交叉"
    assert classify(rb=225.0, hd=90.0)[0] == "交叉"


def test_situation_covers_nearly_all_bearing_space():
    """任意相对方位 × 典型航向差，「其他」只能是 rb=0/180 的边界奇点。"""
    other = 0
    total = 0
    for hd in (0.0, 30.0, 60.0, 90.0, 120.0, 150.0, 170.0, 180.0):
        for rb in range(0, 360):
            total += 1
            if classify(float(rb), hd)[0] == "其他":
                other += 1
                # 「其他」只允许出现在正前/正后两个奇点上
                assert rb in (0, 180), f"hd={hd} rb={rb} 不该落到其他"
    assert other / total < 0.01, f"未分类比例过高: {other}/{total}"


# ---------- CPA：解析解校验 ----------

def _sel(lons, lats, speeds, courses):
    return {
        "mmsi": np.array([str(i) for i in range(len(lons))]),
        "lon": np.array(lons, dtype=float),
        "lat": np.array(lats, dtype=float),
        "sp": np.array(speeds, dtype=float),
        "co": np.array(courses, dtype=float),
    }


def test_head_on_cpa_matches_analytic_solution():
    """对遇几何：DCPA≈0，TCPA = 距离 / 相对速度（解析可算）。"""
    lat0, lat1 = 30.0, 30.01           # 相差约 1112 m
    sel = _sel([122.0, 122.0], [lat0, lat1], [10.0, 10.0], [0.0, 180.0])
    p = I._bucket_pairs(sel, 30.005)
    dist_m = (lat1 - lat0) * I._MPD_LAT
    closing = 2 * 10.0 * I._KN2MS      # 相对接近速度 m/s
    expect_min = dist_m / closing / 60.0
    assert abs(float(p["tcpa"][0]) - expect_min) < 0.02, "TCPA 与解析解不符"
    assert float(p["dcpa"][0]) < 1e-6, "对遇的 DCPA 应为 0"


def test_parallel_same_course_is_not_an_encounter():
    """同向同速并行：相对速度≈0，不得产出有效 TCPA。"""
    sel = _sel([122.0, 122.01], [30.0, 30.0], [10.0, 10.0], [0.0, 0.0])
    p = I._bucket_pairs(sel, 30.0)
    assert not np.isfinite(p["tcpa"][0]), "相对静止不该给出有限 TCPA"


def test_relative_bearing_is_measured_from_own_heading():
    """目标在正东、本船航向 90°(向东) → 相对方位 0；本船向北 → 相对方位 90。"""
    east = _sel([122.0, 122.01], [30.0, 30.0], [10.0, 10.0], [90.0, 90.0])
    assert abs(float(I._bucket_pairs(east, 30.0)["rb"][0])) < 1e-6
    north = _sel([122.0, 122.01], [30.0, 30.0], [10.0, 10.0], [0.0, 0.0])
    assert abs(float(I._bucket_pairs(north, 30.0)["rb"][0]) - 90.0) < 1e-6


# ---------- 船舶领域模型：标定值（防公式漂移） ----------

def test_fujii_domain_axes_equal_four_and_1p6_lengths():
    """Fujii 开阔水域：船首 4L、正横 1.6L（200 m 船 → 0.432/0.173 nm）。"""
    ahead = D.domain_radius_nm(200.0, 0.0, "fujii")
    beam = D.domain_radius_nm(200.0, 90.0, "fujii")
    assert abs(ahead - 4 * 200.0 / _NM) < 1e-6
    assert abs(beam - 1.6 * 200.0 / _NM) < 1e-6
    assert abs(ahead - 0.4320) < 0.001
    assert abs(beam - 0.1728) < 0.001


def test_goodwin_domain_is_asymmetric_three_sectors():
    """Goodwin 三扇区：首 0.85 / 右舷 0.70 / 左舷 0.45 nm，左右不对称。"""
    assert D.domain_radius_nm(200.0, 0.0, "goodwin") == 0.85
    assert D.domain_radius_nm(200.0, 90.0, "goodwin") == 0.70
    assert D.domain_radius_nm(200.0, 270.0, "goodwin") == 0.45


def test_domain_scales_linearly_with_ship_length():
    """同一方位下，领域半径随船长线性缩放。"""
    assert abs(D.domain_radius_nm(400.0, 0.0, "fujii")
               - 2 * D.domain_radius_nm(200.0, 0.0, "fujii")) < 1e-9


def test_unknown_domain_model_rejected():
    with pytest.raises(ValueError):
        D.violations(model="not-a-model")


# ---------- 集成冒烟（依赖 data/ais 数据集） ----------

def _dataset_ready():
    from app.core import config
    import os
    return os.path.exists(config.TRAJECTORY_PARQUET)


@pytest.mark.skipif(not _dataset_ready(), reason="需先运行 scripts/generate_dataset.py")
def test_encounters_on_real_data():
    r = I.detect_encounters("2024-06-01 00:00:00", "2024-06-01 02:00:00",
                            None, 1.0, 30.0, 6.0, 50, 0.1)
    assert r["count"] > 0, "6 小时窗口内应存在会遇"
    # 分类必须 100% 覆盖，不允许退回「其他」
    assert "其他" not in r["situation_stats"], "出现未分类局面，判据有缺口"
    assert sum(r["situation_stats"].values()) == r["count"]
    for e in r["encounters"]:
        assert e["dcpa_nm"] <= 1.0, "超出阈值不应作为会遇返回"
        assert e["tcpa_min"] > 0, "只返回未来会遇"
        assert e["distance_nm"] >= 0.1, "退化的重叠样本必须被排除"


@pytest.mark.skipif(not _dataset_ready(), reason="需先运行 scripts/generate_dataset.py")
def test_encounters_sorted_by_risk():
    r = I.detect_encounters("2024-06-01 00:00:00", "2024-06-01 02:00:00",
                            None, 1.0, 30.0, 6.0, 50, 0.1)
    keys = [e["dcpa_nm"] + e["tcpa_min"] / 60.0 for e in r["encounters"]]
    assert keys == sorted(keys), "会遇事件必须按风险递增排序"


@pytest.mark.skipif(not _dataset_ready(), reason="需先运行 scripts/generate_dataset.py")
def test_conflict_hotspots_inside_bbox():
    r = I.conflict_hotspots("2024-06-01 00:00:00", "2024-06-01 02:00:00",
                            None, 40, 1.0, 30.0, 10)
    assert r["count"] > 0
    assert r["total_encounters"] >= max(c["count"] for c in r["cells"])
    for c in r["cells"]:
        assert 121.0 <= c["longitude"] <= 124.0
        assert 29.0 <= c["latitude"] <= 32.0


@pytest.mark.skipif(not _dataset_ready(), reason="需先运行 scripts/generate_dataset.py")
def test_domain_violations_on_real_data():
    r = D.violations("2024-06-01 00:00:00", "2024-06-01 02:00:00",
                     None, "fujii", 1.0, 50)
    assert r["count"] > 0
    for v in r["violations"]:
        assert v["distance_nm"] <= v["domain_radius_nm"], "未侵入却被判侵犯"
        assert 0.0 <= v["penetration_ratio"] <= 1.0
        # 沿航向分量（船头间距）不能超过实际距离
        assert abs(v["along_nm"]) <= v["distance_nm"] + 1e-6


# ---------- 护栏：numpy 标量不得泄漏到 API 返回值 ----------

_NATIVE = (int, float, str, bool, type(None))


def _assert_native(obj, path="root"):
    if isinstance(obj, dict):
        for k, v in obj.items():
            _assert_native(k, f"{path}.key")
            _assert_native(v, f"{path}.{k}")
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            _assert_native(v, f"{path}[{i}]")
    else:
        assert not isinstance(obj, np.generic), \
            f"{path} 泄漏 numpy 标量: {type(obj).__name__}"
        assert isinstance(obj, _NATIVE), \
            f"{path} 非原生 JSON 类型: {type(obj).__name__}"


@pytest.mark.skipif(not _dataset_ready(), reason="需先运行 scripts/generate_dataset.py")
def test_encounters_native_types_only():
    _assert_native(I.detect_encounters("2024-06-01 00:00:00",
                                       "2024-06-01 02:00:00",
                                       None, 1.0, 30.0, 6.0, 20, 0.1))


@pytest.mark.skipif(not _dataset_ready(), reason="需先运行 scripts/generate_dataset.py")
def test_domain_violations_native_types_only():
    _assert_native(D.violations("2024-06-01 00:00:00",
                                "2024-06-01 02:00:00", None, "fujii", 1.0, 20))
