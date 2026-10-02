"""端到端冒烟：对运行中的后端逐条验证 API 契约，失败即非零退出。

用法：python scripts/smoke.py [base_url]   （默认 http://127.0.0.1:8000）
"""
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
results = []


def get(path, params=None, timeout=60, raw=False):
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    t0 = time.time()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            body = r.read()
            payload = body.decode("utf-8", "ignore") if raw else json.loads(body)
            return r.status, payload, time.time() - t0, len(body)
    except urllib.error.HTTPError as e:
        return e.code, None, time.time() - t0, 0


def check(name, path, params=None, validate=None, raw=False):
    status, data, dt, size = get(path, params, raw=raw)
    ok = status == 200 and (validate is None or validate(data))
    results.append((ok, name, path, status, dt, size))
    return data


print(f"冒烟目标：{BASE}\n")

stats = check(
    "统计概览", "/data/statistics", None,
    lambda d: isinstance(d, dict) and d.get("total_trajectory_points", 0) > 0,
)
mmsi = None
if stats:
    print(f"  数据集：{stats['total_ships']} 船 / {stats['total_trajectory_points']} 点 / "
          f"{stats['time_range']['start']} → {stats['time_range']['end']}")

ships = check("船舶列表", "/mock_data/ships", {"limit": 5},
              lambda d: isinstance(d, list) and len(d) > 0)
if ships:
    mmsi = str(ships[0]["mmsi"])
    print(f"  示例船舶：{ships[0].get('name')} / {ships[0].get('ship_type')} / MMSI {mmsi}")

check("轨迹样本", "/mock_data/trajectories", {"limit": 3, "max_points": 20},
      lambda d: isinstance(d, dict) and len(d) > 0)
check("密度网格", "/density/heatmap", {"grid_size": 50},
      lambda d: isinstance(d, dict) and len(d.get("density_data", [])) > 0)
check("时刻快照", "/analysis/snapshot", {"at": "2024-06-01T12:00:00", "limit": 100},
      lambda d: isinstance(d, dict) and len(d.get("ships", [])) > 0)
check("航速航向分布", "/analysis/speed-course", None,
      lambda d: isinstance(d, dict) and len(d.get("speed_hist", [])) > 0)
check("主航线提取", "/analysis/corridors", {"grid_size": 60},
      lambda d: isinstance(d, dict) and len(d.get("corridors", [])) >= 0)
check("OD 分析", "/analysis/od", {"top_n": 10},
      lambda d: isinstance(d, dict) and len(d.get("od", [])) > 0)
check("KDE 核密度曲面", "/analysis/kde", {"bandwidth_deg": 0.03, "grid_size": 40},
      lambda d: isinstance(d, dict) and len(d.get("cells", [])) > 0
      and "bandwidth_km" in d.get("meta", {}))
check("密度热点", "/analysis/hotspots", {"top_n": 5},
      lambda d: isinstance(d, dict) and len(d.get("hotspots", [])) == 5)
check("12 项交通流指标", "/analysis/metrics", None,
      lambda d: isinstance(d, dict) and len(d.get("indicators", [])) == 12)
check("多维样本（平行坐标）", "/analysis/multivariate", {"n": 300},
      lambda d: isinstance(d, dict) and len(d.get("rows", [])) > 0
      and len(d.get("axes", [])) == 7
      and "rot" in [a["key"] for a in d["axes"]])
check("断面流量", "/analysis/sectional-flow",
      {"lon1": 122.0, "lat1": 30.8, "lon2": 123.0, "lat2": 30.8},
      lambda d: isinstance(d, dict) and "total" in d)
# ---- L2 交互感知层 ----
check(
    "船舶会遇检测", "/analysis/encounters",
    {"start": "2024-06-01 00:00:00", "end": "2024-06-01 02:00:00", "limit": 20},
    lambda d: d.get("count", 0) > 0
    and "其他" not in d.get("situation_stats", {})      # 分类必须 100% 覆盖
    and sum(d["situation_stats"].values()) == d["count"]
    and all(e["distance_nm"] >= 0.1 for e in d["encounters"]),  # 重叠样本已排除
)
check(
    "会遇冲突热点", "/analysis/conflicts",
    {"top_n": 10, "start": "2024-06-01 00:00:00", "end": "2024-06-01 02:00:00"},
    lambda d: d.get("count", 0) > 0 and len(d.get("cells", [])) > 0,
)
check(
    "船舶领域侵犯", "/analysis/domain-violations",
    {"limit": 20, "start": "2024-06-01 00:00:00", "end": "2024-06-01 02:00:00"},
    lambda d: d.get("count", 0) > 0
    and all(v["distance_nm"] <= v["domain_radius_nm"] for v in d["violations"]),
)
# ---- 航向角变化率（D1） ----
_W = {"start": "2024-06-01 00:00:00", "end": "2024-06-01 02:00:00"}
check(
    "航向变化率统计", "/analysis/rot/statistics", {**_W, "window_min": 15},
    lambda d: d.get("count", 0) > 0
    and any(i["key"] == "mean_abs_rot" for i in d["indicators"])
    and d["diagnostics"]["noise_amplification"] > 1,
)
check(
    "转向率空间网格", "/analysis/rot/grid", {**_W, "grid_size": 12},
    lambda d: d.get("count", 0) > 0
    and all(0.0 <= c["maneuver_ratio"] <= 1.0 for c in d["cells"]),
)
check(
    "转向率分船型", "/analysis/rot/by-type", _W,
    lambda d: d.get("count", 0) > 0 and all(r["samples"] > 0 for r in d["rows"]),
)
check(
    "转向率分布", "/analysis/rot/distribution", {**_W, "bins": 10},
    lambda d: d.get("count", 0) > 0
    and sum(b["count"] for b in d["bins"]) == d["count"],
)
check(
    "导出船舶 CSV", "/export/ships", None,    lambda d: isinstance(d, str) and d.startswith("mmsi"), raw=True,
)
check(
    "导出轨迹 CSV", "/export/trajectories", None,
    lambda d: isinstance(d, str) and len(d.splitlines()) > 100, raw=True,
)

if mmsi:
    check("单船轨迹", f"/ships/{mmsi}/trajectories", None,
          lambda d: isinstance(d, list) and len(d) > 0)
    check("轨迹抽稀", f"/ships/{mmsi}/trajectories/simplified", {"tolerance": 0.002},
          lambda d: isinstance(d, dict) and len(d.get("points", [])) > 0)
    check("轨迹平滑", f"/ships/{mmsi}/trajectories/smoothed", None,
          lambda d: isinstance(d, dict) and len(d.get("points", [])) > 0)

print("\n%-14s %-34s %6s %8s %10s" % ("结果", "接口", "状态", "耗时", "响应字节"))
print("-" * 78)
for ok, name, path, status, dt, size in results:
    print("%-14s %-34s %6s %7.2fs %10s" % (
        "PASS" if ok else "FAIL", path, status, dt, f"{size:,}"))

failed = [r for r in results if not r[0]]
print("-" * 78)
print(f"合计 {len(results)} 项，通过 {len(results) - len(failed)}，失败 {len(failed)}")
sys.exit(1 if failed else 0)
