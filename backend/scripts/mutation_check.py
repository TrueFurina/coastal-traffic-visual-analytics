"""变异验证（mutation testing）——证明"测试全绿"不是"测试有效"。

测试全部通过并不代表它能抓住真实缺陷。本脚本刻意把实现改错，
再确认对应的测试会转红；若改错后测试仍通过（漏网），说明该测试是空的，
需要在 CHANGELOG 里修正后再提交。

用法：
    python scripts/mutation_check.py            # 全部变异
    python scripts/mutation_check.py M2 M4      # 只跑指定编号

安全约定：每一步都在 try/finally 中恢复原文件，即使中途异常也不会
留下被污染的实现（历史上用临时脚本做过变异，崩溃后残留未被发现）。
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY_BIN = sys.executable

# (编号, 说明, 相对路径, 原串, 变异串, 期望转红的测试)
MUTATIONS = [
    ("M1", "KDE 高斯核退化为常数（带宽失效）", "app/services/kde.py",
     "    sigma_bins = bw / step",
     "    sigma_bins = 1.0",
     "tests/test_kde_metrics.py::test_larger_bandwidth_smoother"),

    ("M2", "meta 泄漏 numpy 标量（去掉 float()）", "app/services/kde.py",
     '"bandwidth_km": round(float(bw * km_per_deg_lon_here), 3),',
     '"bandwidth_km": np.float64(bw * km_per_deg_lon_here),',
     "tests/test_kde_metrics.py::test_kde_meta_native_types_only"),

    ("M3", "信息熵丢失负号（熵值变负）", "app/services/metrics.py",
     "return float(-(p * np.log2(p)).sum())",
     "return float((p * np.log2(p)).sum())",
     "tests/test_kde_metrics.py::test_metrics_bounded_indicators_in_range"),

    ("M4", "12 项指标体系被删掉一项", "app/services/metrics.py",
     '("congestion_ratio", "拥堵指数"',
     '#("congestion_ratio", "拥堵指数"',
     "tests/test_kde_metrics.py::test_metrics_has_exactly_twelve_indicators"),

    ("M5", "参数校验被 falsy 吞掉（0 变默认值）", "app/services/kde.py",
     "    bw = 0.02 if bandwidth_deg is None else float(bandwidth_deg)",
     "    bw = float(bandwidth_deg) if bandwidth_deg else 0.02",
     "tests/test_kde_metrics.py::test_kde_rejects_bad_bandwidth"),

    ("M6", "变异系数与标准差/均值脱钩", "app/services/metrics.py",
     "    cv = std_speed / avg_speed if avg_speed > 0 else 0.0",
     "    cv = std_speed * avg_speed if avg_speed > 0 else 0.0",
     "tests/test_kde_metrics.py::test_metrics_speed_cv_consistency"),

    # ---- L2 交互感知层：历史上真实出过 bug 的四个判据 ----

    ("M7", "追越方向判反（本船追越 ↔ 被追越 互换）", "app/services/colregs.py",
     "if rb <= _FORWARD_ARC or rb >= 360.0 - _FORWARD_ARC:",
     "if _OVERTAKE_ARC <= rb <= 360.0 - _OVERTAKE_ARC:",
     "tests/test_interaction.py::test_overtake_direction_forward_means_own_is_overtaking"),

    ("M8", "对遇退回受相对方位限制（Rule 14 被窄化）", "app/services/colregs.py",
     'if hd > 180.0 - _COURSE_TOL:\n        return "对遇"',
     'if hd > 180.0 - _COURSE_TOL and (rb <= 5.0 or rb >= 355.0):\n        return "对遇"',
     "tests/test_interaction.py::test_head_on_by_heading_diff_regardless_of_bearing"),

    ("M9", "取消重叠样本排除（合成数据假会遇混入）", "app/services/interaction.py",
     'hit = base & (p["d0"] >= min_distance_nm)',
     "hit = base",
     "tests/test_interaction.py::test_encounters_on_real_data"),

    ("M10", "船头间距回退为 numpy 标量（类型泄漏）", "app/services/domain.py",
     '"along_nm": round(float(d0 * np.cos(np.radians(rb))), 4),',
     '"along_nm": round(d0 * np.cos(np.radians(rb)), 4),',
     "tests/test_interaction.py::test_domain_violations_native_types_only"),

    ("M11", "KDE 抽样去掉固定种子（结果不可复现）", "app/services/kde.py",
     "USING SAMPLE reservoir({int(sample_limit)} ROWS) REPEATABLE ({config.SEED})",
     "USING SAMPLE reservoir({int(sample_limit)} ROWS)",
     "tests/test_kde_metrics.py::test_kde_is_reproducible_across_calls"),

    ("M12", "航向环绕折叠去掉 +540（350°→10° 算成 -340°）", "app/services/rot.py",
     'return f"(({diff_sql} + 540) % 360) - 180"',
     'return f"({diff_sql} % 360) - 180"',
     "tests/test_rot.py::test_wrap_folding_handles_course_crossing"),

    ("M13", "ROT 取消 dt<=0 过滤（除零/负间隔混入）", "app/services/rot.py",
     "WHERE dt_s > {lo} AND dt_s <= {hi}",
     "WHERE dt_s <= {hi}",
     "tests/test_rot.py::test_valid_cte_filters_nonpositive_and_huge_dt"),

    ("M14", "ROT 抽样改回 USING SAMPLE（GROUP BY 后行序不定，结果不可复现）",
     "app/services/rot.py",
     'return f"ORDER BY hash(mmsi, hour, longitude, latitude, {int(seed)}) LIMIT {int(n)}"',
     'return f"USING SAMPLE reservoir({int(n)} ROWS) REPEATABLE ({int(seed)})"',
     "tests/test_rot.py::test_rot_samples_are_reproducible_and_finite"),
]


def _run(test_id):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
    env["PYTHONIOENCODING"] = "utf-8"
    r = subprocess.run(
        [PY_BIN, "-m", "pytest", test_id, "-q", "-p", "no:warnings"],
        cwd=str(ROOT), capture_output=True, env=env,
    )
    out = (r.stdout or b"").decode("utf-8", "replace").strip().splitlines()
    return r.returncode, (out[-1] if out else "no output")


def main(selected=None):
    caught, escaped, skipped = [], [], []
    for no, desc, relpath, old, new, test_id in MUTATIONS:
        if selected and no not in selected:
            continue
        f = ROOT / relpath
        original = f.read_text(encoding="utf-8")
        if old not in original:
            skipped.append((no, desc, "锚点未命中，实现可能已变更"))
            continue
        try:
            f.write_text(original.replace(old, new, 1), encoding="utf-8",
                         newline="")
            rc, last = _run(test_id)
            if rc != 0:
                caught.append((no, desc, last[:50]))
            else:
                escaped.append((no, desc, "❗测试未转红"))
        finally:
            f.write_text(original, encoding="utf-8", newline="")

    print("=" * 66)
    print("变异验证报告")
    print("=" * 66)
    for no, desc, note in caught:
        print(f"  [通过] {no} {desc}  →  测试如期转红")
    for no, desc, note in escaped:
        print(f"  [漏网] {no} {desc}  →  {note}（该测试无效，需改写）")
    for no, desc, note in skipped:
        print(f"  [跳过] {no} {desc}  →  {note}")
    print("-" * 66)

    rc, last = _run("tests")
    print(f"  恢复后全量回归: {last[:60]}")
    print("=" * 66)
    return 1 if (escaped or rc != 0) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or None))
