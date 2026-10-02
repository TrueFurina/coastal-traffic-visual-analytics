"""KDE 核密度与 12 项指标体系的单元测试 + 集成冒烟。

设计目标：这些测试必须能抓住真实缺陷，而不是"断言 True"。
其中 test_*_json_serializable 用于守住 numpy 标量泄漏 API 层这一历史坑。
"""
import json
import numpy as np
import pytest
from app.services import kde as kde_mod
from app.services import metrics as metrics_mod


# ---------- 纯函数：高斯核 ----------

def test_gaussian_kernel_normalized_and_symmetric():
    k = kde_mod._gaussian_kernel_1d(2.0)
    assert abs(k.sum() - 1.0) < 1e-9, "核必须归一化，否则密度总量会被缩放"
    assert len(k) % 2 == 1, "核应关于中心对称且为奇数长度"
    assert abs(k[0] - k[-1]) < 1e-12


def test_gaussian_kernel_zero_sigma_degenerate():
    k = kde_mod._gaussian_kernel_1d(0)
    assert list(k) == [1.0]


# ---------- 参数校验 ----------

def test_kde_rejects_bad_bandwidth():
    with pytest.raises(ValueError):
        kde_mod.kde_surface(bandwidth_deg=0)


def test_kde_rejects_inverted_bounds():
    with pytest.raises(ValueError):
        kde_mod.kde_surface(min_lon=123.0, max_lon=121.0,
                            min_lat=29.0, max_lat=31.0)


# ---------- 集成（依赖 data/ais 数据集）----------

@pytest.mark.integration
def test_kde_density_non_negative_and_hotspot_inside_area():
    s = kde_mod.kde_surface(bandwidth_deg=0.02, grid_size=40)
    assert s["count"] > 0
    assert len(s["cells"]) > 0
    for c in s["cells"]:
        assert c["density"] >= 0.0
        # 热点必须落在研究水域内
        assert 121.0 <= c["longitude"] <= 124.0
        assert 29.0 <= c["latitude"] <= 32.0


@pytest.mark.integration
def test_larger_bandwidth_smoother():
    """核心性质：带宽越大，密度场越平滑 —— 峰值降低、有效单元铺开。

    必须固定 bin_size，使「带宽」成为唯一变量；否则 bin 面积会随带宽变化，
    面积归一化效应会掩盖核本身的退化（曾导致该测试形同虚设）。
    """
    common = dict(grid_size=40, bin_size=0.005, min_lon=121.8, max_lon=122.6,
                  min_lat=30.2, max_lat=31.0)
    sharp = kde_mod.kde_surface(bandwidth_deg=0.005, **common)
    smooth = kde_mod.kde_surface(bandwidth_deg=0.05, **common)
    assert smooth["meta"]["bin_peak_density_nm2"] < \
        sharp["meta"]["bin_peak_density_nm2"], "同 bin 尺度下，大带宽必须削峰"
    assert len(smooth["cells"]) > len(sharp["cells"]), "大带宽应铺开更多单元"


@pytest.mark.integration
def test_bandwidth_actually_affects_kernel():
    """回归护栏：核宽度必须真正由带宽驱动（σ/bandwidth coupling）。"""
    common = dict(grid_size=40, bin_size=0.005, min_lon=121.8, max_lon=122.6,
                  min_lat=30.2, max_lat=31.0)
    a = kde_mod.kde_surface(bandwidth_deg=0.01, **common)
    b = kde_mod.kde_surface(bandwidth_deg=0.04, **common)
    pa = max(c["density"] for c in a["cells"])
    pb = max(c["density"] for c in b["cells"])
    assert abs(pa - pb) / max(pa, 1e-9) > 0.05, \
        "不同带宽竟产出相同密度场，说明 σ 未随带宽变化（核退化）"


@pytest.mark.integration
def test_hotspots_sorted_descending():
    r = kde_mod.peak_locations(top_n=5)
    ds = [c["density"] for c in r["hotspots"]]
    assert len(ds) == 5
    assert ds == sorted(ds, reverse=True)


@pytest.mark.integration
def test_kde_is_reproducible_across_calls():
    """研究可复现性护栏：同参数两次调用必须给出完全相同的密度场。

    DuckDB 的 reservoir 抽样若不带种子，每次抽到的样本不同，密度峰值会有
    约 0.8% 的随机漂移 —— 论文引用的数字和测试断言都将失去意义。
    """
    a = kde_mod.kde_surface(bandwidth_deg=0.02, grid_size=20)
    b = kde_mod.kde_surface(bandwidth_deg=0.02, grid_size=20)
    assert a["meta"]["bin_peak_density_nm2"] == b["meta"]["bin_peak_density_nm2"]
    assert [c["density"] for c in a["cells"]] == [c["density"] for c in b["cells"]]


@pytest.mark.integration
def test_metrics_has_exactly_twelve_indicators():
    m = metrics_mod.traffic_metrics()
    inds = m["indicators"]
    assert len(inds) == 12, "指标体系口径固定为 12 项"
    keys = [i["key"] for i in inds]
    assert len(set(keys)) == 12, "指标 key 不可重复"
    for i in inds:
        assert i["unit"] and i["desc"], "每项都要带单位和口径说明"


@pytest.mark.integration
def test_metrics_bounded_indicators_in_range():
    m = metrics_mod.traffic_metrics()
    by = {i["key"]: i["value"] for i in m["indicators"]}
    assert 0.0 <= by["flow_balance"] <= 1.0, "归一化熵必须在 [0,1]"
    assert 0.0 <= by["course_entropy_bits"] <= 4.0, "16 扇区熵上限 4 bit"
    assert 0.0 <= by["congestion_ratio"] <= 1.0
    assert 0.0 <= by["route_concentration"] <= 1.0
    assert by["ship_count"] > 0 and by["point_count"] > 0
    assert by["max_density_nm2"] >= by["avg_density_nm2"], "峰值不可能低于均值"


@pytest.mark.integration
def test_metrics_speed_cv_consistency():
    """变异系数必须与 标准差/均值 自洽（防止手改漂移）。"""
    m = metrics_mod.traffic_metrics()
    by = {i["key"]: i["value"] for i in m["indicators"]}
    expect = round(by["speed_std_kn"] / by["avg_speed_kn"], 4)
    assert abs(by["speed_cv"] - expect) < 1e-3


# ---------- 护栏：numpy 类型不得泄漏到 API 返回值 ----------
# 注意：np.float64 是 Python float 的子类，json.dumps 能直接处理，
# 所以只做 json.dumps 检查抓不到泄漏，必须显式校验原生类型。
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


@pytest.mark.integration
def test_kde_meta_native_types_only():
    """守住 np.float64/np.int64/np.ndarray 泄漏到 API 层。"""
    s = kde_mod.kde_surface(bandwidth_deg=0.03, grid_size=20)
    _assert_native(s)


@pytest.mark.integration
def test_metrics_native_types_only():
    m = metrics_mod.traffic_metrics()
    _assert_native(m)
