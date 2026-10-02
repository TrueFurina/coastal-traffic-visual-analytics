"""航向角变化率（Rate of Turn, ROT）分析 —— 对应申报书创新点 3.1。

D1 要求「流量/速度/航向角变化率的时空关联分析」。本模块给出 ROT 的
统计量、分船型对比、空间网格聚合与平行坐标样本。

计算口径上有三个必须处理的点，否则结果不可用：
  1. 航向环绕：course 由 350° 变到 10°，直接相减得 -340°，实际是 +20°。
     用 ((d + 540) % 360) - 180 折叠到 (-180, 180]；d ∈ (-360, 360) 保证
     d + 540 > 0，避开各 SQL 方言对负数取模的行为差异。
  2. 报文间隔：dt <= 0（重复时间戳）会让 ROT 除零；dt 过大说明中间丢包，
     差分不代表真实转向。两者都剔除。
  3. 尺度依赖（合成数据的硬约束）：本数据集的 course 是相邻点位置反算的
     方位角，而位置带 ~89m 独立噪声（generator.py 的 rng.normal(0, 0.0008)）。
     船每 44s 仅前进 ~270m，逐点差分的角度误差可达 ~18°，导致逐点 ROT
     几乎全是噪声 —— 实测 p50 由逐点的 56°/min 降到 15min 窗口的 2.5°/min，
     呈单调衰减，正是噪声主导的特征。因此默认采用时间窗聚合口径，
     并在 diagnostics 中同时给出逐点值作为对照，二者之比即噪声放大因子。
"""
from app.core import config, db
from app.services.traffic import _region_where, _time_where

_MAX_GAP_S = 600      # 相邻报文间隔超过 10 分钟视为轨迹中断，不参与差分
_MANEUVER_ROT = 3.0   # 机动判定阈值，°/min
_STEADY_ROT = 0.5     # 直航判定阈值，|ROT| 低于此值视为保向，°/min
# 阈值口径说明：实测 15min 窗口下 |ROT| 分布单调递减、无双峰，
# 不存在天然的「直航/机动」分界点，故 _MANEUVER_ROT 是沿用商船正常转向率
# 量级的约定值而非数据驱动的分界值。因此「机动率」只适用于水域/船型/时段
# 之间的相对比较，不宜作为绝对判据单独引用。
_DEFAULT_WINDOW_MIN = 15   # 默认聚合窗口，分钟；0 表示逐点差分


def _resolve(min_lon, min_lat, max_lon, max_lat):
    """缺省 bbox 回退到研究区，返回 (min_lon, min_lat, max_lon, max_lat)。"""
    sa = config.STUDY_AREA
    return (
        float(min_lon if min_lon is not None else sa["min_lon"]),
        float(min_lat if min_lat is not None else sa["min_lat"]),
        float(max_lon if max_lon is not None else sa["max_lon"]),
        float(max_lat if max_lat is not None else sa["max_lat"]),
    )


def _sample_tail(n, seed=42):
    """确定性抽样：按 hash 排序取前 n 条。

    不能用 USING SAMPLE reservoir(...) REPEATABLE(...)：本模块的 CTE 经过
    GROUP BY，输出行序不确定，同一 seed 也会抽出不同样本，论文数字无法复现
    （实测连续四次首行 mmsi 各不相同）。hash 是行内容纯函数、与行序无关，
    故结果确定，且因 hash 分布均匀而近似无偏随机。
    """
    return f"ORDER BY hash(mmsi, hour, longitude, latitude, {int(seed)}) LIMIT {int(n)}"


def _wrap(diff_sql):
    """把角度差折叠到 (-180, 180]，处理 350°→10° 这类环绕。

    单独抽出来的原因：这是本模块最易写错、且错了不报错的一处（环绕会让
    相邻样本凭空多出 ±340°）。实现与测试共用同一表达式，保证变异可捕获。
    """
    return f"(({diff_sql} + 540) % 360) - 180"


def _base_cte(b, start, end, window_min):
    """产出统一结构的 g(mmsi, ship_type, longitude, latitude, speed, course,
    hour, dt_s, d_course)。window_min>0 走窗口聚合，否则走逐点 LAG。

    注意：窗口聚合必须先分组再取首尾，不能先抽样 —— 抽到的点在时间上
    并不相邻，算出来的是跨时段伪转向率。
    """
    rw = _region_where(*b)
    tw = _time_where(start, end)
    src = f"read_parquet('{config.TRAJECTORY_PARQUET}') WHERE 1=1 {rw} {tw}"
    wm = int(window_min or 0)
    if wm > 0:
        sec = max(60, wm * 60)
        return f"""WITH g AS (
            SELECT mmsi, CAST(floor(epoch(timestamp) / {sec}) AS BIGINT) AS grp,
                   arg_max(ship_type, timestamp) AS ship_type,
                   arg_max(longitude, timestamp) AS longitude,
                   arg_max(latitude, timestamp) AS latitude,
                   arg_max(speed, timestamp) AS speed,
                   arg_max(course, timestamp) AS course,
                   CAST(hour(max(timestamp)) AS INT) AS hour,
                   date_diff('second', min(timestamp), max(timestamp)) AS dt_s,
                   {_wrap('arg_max(course, timestamp) - arg_min(course, timestamp)')} AS d_course
            FROM {src} GROUP BY 1, 2)"""
    return f"""WITH seq AS (
        SELECT mmsi, ship_type, timestamp, longitude, latitude, speed, course,
               LAG(timestamp) OVER w AS pt, LAG(course) OVER w AS pc
        FROM {src}
        WINDOW w AS (PARTITION BY mmsi ORDER BY timestamp)), g AS (
        SELECT mmsi, ship_type, longitude, latitude, speed, course,
               CAST(hour(timestamp) AS INT) AS hour,
               date_diff('second', pt, timestamp) AS dt_s,
               {_wrap('course - pc')} AS d_course
        FROM seq WHERE pt IS NOT NULL)"""


def _valid_cte(max_gap_s, window_sec=0, min_cover=0.5):
    """过滤无效间隔并折算成 °/min。

    逐点模式：dt ∈ (0, max_gap_s]，上界用于剔除丢包造成的伪大间隔。
    窗口模式：上界放宽到窗口长度本身（否则窗口跨度会被逐点的 600s 误杀），
    下界要求窗口内实际覆盖 ≥ min_cover×窗口长，避免只有两三个靠得很近的
    点也被当成整窗转向率。
    """
    lo = int(window_sec * min_cover) if window_sec > 0 else 0
    hi = max(int(max_gap_s), int(window_sec))
    return (f"SELECT *, d_course / (dt_s / 60.0) AS rot FROM g "
            f"WHERE dt_s > {lo} AND dt_s <= {hi}")


def _query(sql):
    return db.get_conn().execute(sql).fetchone()


def _sec(window_min):
    return max(0, int(window_min or 0)) * 60


def _mean_abs_rot(b, start, end, window_min, max_gap_s):
    """取某口径下的平均 |ROT|，用于跨尺度对照。"""
    ws = _sec(window_min)
    sql = f"""{_base_cte(b, start, end, window_min)},
              v AS ({_valid_cte(max_gap_s, ws)})
              SELECT avg(abs(rot)) FROM v"""
    r = _query(sql)
    return float(r[0]) if r and r[0] is not None else 0.0


def rot_statistics(min_lon=None, min_lat=None, max_lon=None, max_lat=None,
                   start=None, end=None, window_min=_DEFAULT_WINDOW_MIN,
                   maneuver_rot=_MANEUVER_ROT, steady_rot=_STEADY_ROT,
                   max_gap_s=_MAX_GAP_S):
    """ROT 总体统计：转向强度、离散度、尾部、机动比与左右转构成。"""
    b = _resolve(min_lon, min_lat, max_lon, max_lat)
    wm = int(window_min or 0)
    thr, std = float(maneuver_rot), float(steady_rot)
    sql = f"""{_base_cte(b, start, end, wm)}, v AS ({_valid_cte(max_gap_s, _sec(window_min))})
      SELECT count(*), avg(abs(rot)), stddev(abs(rot)),
             quantile_cont(abs(rot), 0.95), max(abs(rot)),
             sum(CASE WHEN abs(rot) >= {thr} THEN 1 ELSE 0 END),
             sum(CASE WHEN rot <= {-std} THEN 1 ELSE 0 END),
             sum(CASE WHEN rot >= {std} THEN 1 ELSE 0 END),
             avg(rot), avg(dt_s)
      FROM v"""
    r = _query(sql)
    n = int(r[0] or 0)
    if n == 0:
        return {"count": 0, "note": "所选时空范围内无有效相邻报文对"}
    left, right = int(r[6] or 0), int(r[7] or 0)
    scale = f"{wm} 分钟窗口" if wm > 0 else "逐点差分"
    raw = [
        ("rot_sample_count", "有效转向样本数", n, "对",
         f"{scale}口径下 dt∈(0, {int(max_gap_s)}s] 的样本数"),
        ("mean_abs_rot", "平均绝对转向率", round(float(r[1]), 4), "°/min",
         f"|ROT| 的算术平均（{scale}）；有符号均值会左右抵消故取绝对值"),
        ("rot_std", "转向率离散度", round(float(r[2]), 4), "°/min",
         "|ROT| 的标准差，越大说明转向行为分化越明显"),
        ("rot_p95", "转向率 95 分位", round(float(r[3]), 4), "°/min",
         "95% 的转向低于该值，用于识别急转尾部风险"),
        ("max_abs_rot", "最大转向率", round(float(r[4]), 4), "°/min",
         "样本内最急的一次转向"),
        ("maneuver_ratio", "机动率", round(float(r[5]) / n, 4), "-",
         f"|ROT| ≥ {thr:g}°/min 的样本占比，反映频繁操舵程度"),
        ("turn_left_ratio", "左转占比", round(left / n, 4), "-",
         f"ROT ≤ -{std:g}°/min 的样本占比"),
        ("turn_right_ratio", "右转占比", round(right / n, 4), "-",
         f"ROT ≥ +{std:g}°/min 的样本占比，与左转占比之差反映航道转向偏好"),
        ("steady_ratio", "保向占比", round((n - left - right) / n, 4), "-",
         f"|ROT| < {std:g}°/min 的样本占比，越高说明航迹越平直"),
        ("mean_rot_signed", "平均有符号转向率", round(float(r[8]), 4), "°/min",
         "正负相抵后的净转向，可判别水域是否存在系统性单向绕行"),
        ("mean_dt_s", "平均观测间隔", round(float(r[9]), 2), "s",
         "样本的时间跨度均值，用于判断 ROT 的时间分辨率"),
    ]
    diag = {"scale": scale, "window_min": wm}
    if wm > 0:
        pw = _mean_abs_rot(b, start, end, 0, max_gap_s)
        cur = float(r[1] or 0.0)
        diag.update({
            "pointwise_mean_abs_rot": round(pw, 4),
            "noise_amplification": round(pw / cur, 2) if cur > 0 else None,
            "note": ("逐点口径受位置噪声放大，仅作对照，不可作为真实转向率引用；"
                     "引用请用本窗口口径"),
        })
    else:
        diag["note"] = "当前为逐点口径，数值含位置噪声放大效应，慎用于结论"
    return {
        "count": n,
        "parameters": {"window_min": wm, "maneuver_rot": thr,
                       "steady_rot": std, "max_gap_s": int(max_gap_s)},
        "time_window": {"start": start, "end": end},
        "region": {"min_lon": b[0], "min_lat": b[1], "max_lon": b[2], "max_lat": b[3]},
        "diagnostics": diag,
        "indicators": [
            {"key": k, "name": nm, "value": v, "unit": u, "desc": d}
            for k, nm, v, u, d in raw
        ],
    }


def rot_by_ship_type(min_lon=None, min_lat=None, max_lon=None, max_lat=None,
                     start=None, end=None, window_min=_DEFAULT_WINDOW_MIN,
                     maneuver_rot=_MANEUVER_ROT, max_gap_s=_MAX_GAP_S):
    """分船型的转向强度对比 —— 机动性差异是船型行为画像的关键维度。"""
    b = _resolve(min_lon, min_lat, max_lon, max_lat)
    thr = float(maneuver_rot)
    sql = f"""{_base_cte(b, start, end, int(window_min or 0))},
      v AS ({_valid_cte(max_gap_s, _sec(window_min))})
      SELECT COALESCE(ship_type, '未知'), count(*), avg(abs(rot)),
             quantile_cont(abs(rot), 0.95),
             sum(CASE WHEN abs(rot) >= {thr} THEN 1 ELSE 0 END)
      FROM v GROUP BY 1 ORDER BY count(*) DESC"""
    rows = db.get_conn().execute(sql).fetchall()
    return {
        "count": len(rows),
        "window_min": int(window_min or 0),
        "maneuver_rot": thr,
        "rows": [
            {"ship_type": r[0], "samples": int(r[1]),
             "mean_abs_rot": round(float(r[2]), 4),
             "rot_p95": round(float(r[3]), 4),
             "maneuver_ratio": round(float(r[4]) / int(r[1]), 4)}
            for r in rows
        ],
    }


def rot_grid(min_lon=None, min_lat=None, max_lon=None, max_lat=None,
             start=None, end=None, grid_size=40, window_min=_DEFAULT_WINDOW_MIN,
             maneuver_rot=_MANEUVER_ROT, max_gap_s=_MAX_GAP_S):
    """转向强度的空间网格聚合，可直接叠加地图定位弯道/交汇区。"""
    b = _resolve(min_lon, min_lat, max_lon, max_lat)
    thr = float(maneuver_rot)
    g = max(2, min(int(grid_size), 400))
    lon_w = (b[2] - b[0]) / g
    lat_h = (b[3] - b[1]) / g
    sql = f"""{_base_cte(b, start, end, int(window_min or 0))},
      v AS ({_valid_cte(max_gap_s, _sec(window_min))}),
      c AS (SELECT *, least({g - 1}, greatest(0,
                CAST(floor((longitude - {b[0]}) / {lon_w}) AS INT))) AS gx,
                least({g - 1}, greatest(0,
                CAST(floor((latitude - {b[1]}) / {lat_h}) AS INT))) AS gy FROM v)
      SELECT gx, gy, count(*), avg(abs(rot)),
             sum(CASE WHEN abs(rot) >= {thr} THEN 1 ELSE 0 END),
             avg(longitude), avg(latitude)
      FROM c GROUP BY gx, gy ORDER BY count(*) DESC"""
    rows = db.get_conn().execute(sql).fetchall()
    return {
        "count": len(rows),
        "grid_size": g,
        "window_min": int(window_min or 0),
        "bbox": {"min_lon": b[0], "min_lat": b[1], "max_lon": b[2], "max_lat": b[3]},
        "maneuver_rot": thr,
        "cells": [
            {"gx": int(r[0]), "gy": int(r[1]), "samples": int(r[2]),
             "mean_abs_rot": round(float(r[3]), 4),
             "maneuver_ratio": round(float(r[4]) / int(r[2]), 4),
             "lon": round(float(r[5]), 5), "lat": round(float(r[6]), 5)}
            for r in rows
        ],
    }


def rot_samples(n=1500, min_lon=None, min_lat=None, max_lon=None, max_lat=None,
                start=None, end=None, window_min=_DEFAULT_WINDOW_MIN,
                seed=42, max_gap_s=_MAX_GAP_S):
    """为平行坐标供数。先算转向率再抽样，保证 rot 是真实的相邻/同窗转向。"""
    n = max(1, min(int(n), 20000))
    b = _resolve(min_lon, min_lat, max_lon, max_lat)
    sql = f"""{_base_cte(b, start, end, int(window_min or 0))},
      v AS ({_valid_cte(max_gap_s, _sec(window_min))})
      SELECT mmsi, ship_type, speed, course, longitude, latitude, hour, rot
      FROM v {_sample_tail(n, seed)}"""
    rows = db.get_conn().execute(sql).fetchall()
    out = []
    for mmsi, stype, speed, course, lon, lat, hour, r in rows:
        if None in (speed, course, lon, lat, hour, r):
            continue
        out.append({"mmsi": str(mmsi), "ship_type": stype or "未知",
                    "speed": round(float(speed), 2),
                    "course": round(float(course) % 360.0, 1),
                    "longitude": round(float(lon), 4),
                    "latitude": round(float(lat), 4),
                    "hour": int(hour), "rot": round(float(r), 3)})
    vals = [o["rot"] for o in out]
    return {"count": len(out), "sample_size": n, "rows": out,
            "window_min": int(window_min or 0),
            "rot_range": [min(vals), max(vals)] if vals else [0, 0]}


def rot_distribution(min_lon=None, min_lat=None, max_lon=None, max_lat=None,
                     start=None, end=None, window_min=_DEFAULT_WINDOW_MIN,
                     max_gap_s=_MAX_GAP_S, bins=24):
    """|ROT| 直方图，用于校准机动阈值（阈值须由分布定，不能拍脑袋）。"""
    b = _resolve(min_lon, min_lat, max_lon, max_lat)
    sql = f"""{_base_cte(b, start, end, int(window_min or 0))},
      v AS ({_valid_cte(max_gap_s, _sec(window_min))})
      SELECT abs(rot) FROM v {_sample_tail(50000)}"""
    arr = [float(r[0]) for r in db.get_conn().execute(sql).fetchall()]
    if not arr:
        return {"count": 0, "bins": []}
    import numpy as np
    a = np.abs(np.array(arr, dtype=float))
    hi = float(np.percentile(a, 99))
    edges = np.linspace(0, max(hi, 1e-6), int(bins) + 1)
    # 超出 99 分位的样本 clip 进末桶而非丢弃，保证 sum(bins) == count
    counts, _ = np.histogram(np.clip(a, 0.0, edges[-1]), bins=edges)
    return {
        "count": int(a.size), "unit": "°/min",
        "window_min": int(window_min or 0),
        "note": "分桶上限取 99 分位（长尾影响可读性），超出部分并入末桶",
        "bins": [{"from": round(float(edges[i]), 3),
                  "to": round(float(edges[i + 1]), 3),
                  "count": int(counts[i])} for i in range(len(counts))],
    }
