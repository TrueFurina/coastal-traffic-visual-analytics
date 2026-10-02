"""轨迹平滑（从 utils/trajectory_processor.py 迁入，纯 numpy 实现）。

提供移动平均平滑，用于 /ships/{id}/trajectories/smoothed 接口。
"""
import numpy as np


def smooth_points(points, window=5):
    """对轨迹点列表做经纬度移动平均平滑，保留其余字段。

    points: list[dict]，每点含 latitude/longitude。
    返回平滑后的同名结构列表（仅 latitude/longitude 被改写）。
    """
    if len(points) < window or window < 2:
        return points
    lats = np.array([p["latitude"] for p in points], dtype=float)
    lons = np.array([p["longitude"] for p in points], dtype=float)
    half = window // 2
    slat = np.empty_like(lats)
    slon = np.empty_like(lons)
    n = len(lats)
    for i in range(n):
        s = max(0, i - half)
        e = min(n, i + half + 1)
        slat[i] = lats[s:e].mean()
        slon[i] = lons[s:e].mean()
    out = []
    for i, p in enumerate(points):
        q = dict(p)
        q["latitude"] = float(slat[i])
        q["longitude"] = float(slon[i])
        out.append(q)
    return out
