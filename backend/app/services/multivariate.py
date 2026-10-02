"""多维样本抽样 —— 为平行坐标可视化供数。

平行坐标需要「一艘船一次观测 = 一条折线」的多维记录。
这里以「船 × 时间窗」为一条观测（而非单条报文），这样才能同时带上
航向角变化率 —— 转向率必须基于相邻/同窗观测差分得到，单条报文算不出来。
"""
from app.core import config, db
from app.services import rot as rot_mod

# 平行坐标轴定义：(字段名, 中文名, 量纲说明, 是否为类别轴)
AXES = [
    ("speed", "航速", "kn", False),
    ("course", "航向", "°", False),
    ("rot", "转向率", "°/min", False),
    ("longitude", "经度", "°E", False),
    ("latitude", "纬度", "°N", False),
    ("hour", "时段", "时", False),
    ("ship_type", "船型", "-", True),
]


def multivariate_sample(n=1500, min_lon=None, min_lat=None, max_lon=None,
                        max_lat=None, start=None, end=None, seed=42,
                        window_min=rot_mod._DEFAULT_WINDOW_MIN):
    """抽取 n 条多维观测记录（船 × 时间窗）。

    转向率必须先由窗口差分算出再抽样 —— 若先抽样再取 LAG，抽到的点在
    时间上并不相邻，得到的是跨时段伪转向率。

    seed 固定，保证同一参数下多次请求结果一致（便于截图复现与论文引用）。
    """
    n = max(1, min(int(n), 20000))
    conn = db.get_conn()
    b = rot_mod._resolve(min_lon, min_lat, max_lon, max_lat)
    wm = int(window_min or 0)
    sql = (
        f"""{rot_mod._base_cte(b, start, end, wm)},
            v AS ({rot_mod._valid_cte(rot_mod._MAX_GAP_S, rot_mod._sec(wm))})
            SELECT mmsi, ship_type, speed, course, longitude, latitude, hour, rot
            FROM v {rot_mod._sample_tail(n, seed)}"""
    )
    rows = conn.execute(sql).fetchall()

    out = []
    for mmsi, stype, speed, course, lon, lat, hour, r in rows:
        if None in (speed, course, lon, lat, hour, r):
            continue
        out.append({
            "mmsi": str(mmsi),
            "ship_type": stype or "未知",
            "speed": round(float(speed), 2),
            "course": round(float(course) % 360.0, 1),
            "longitude": round(float(lon), 4),
            "latitude": round(float(lat), 4),
            "hour": int(hour),
            "rot": round(float(r), 3),
        })

    ranges = {}
    for key, _, _, categorical in AXES:
        if categorical:
            ranges[key] = sorted({r[key] for r in out})
            continue
        vals = [r[key] for r in out]
        ranges[key] = [min(vals), max(vals)] if vals else [0, 0]

    return {
        "count": len(out),
        "sample_size": n,
        "window_min": wm,
        "rows": out,
        "axes": [{"key": k, "name": nm, "unit": u, "categorical": c}
                 for k, nm, u, c in AXES],
        "ranges": ranges,
    }
