"""合成 AIS 生成器：长江口—舟山海域，确定性随机种子，输出 Parquet。

航道折线 + 锚地区域，numpy 向量化沿航道往返巡航 + 噪声，
少量船在锚地低速漂移。生成 mmsi 9 位、2xx/3xx/4xx 开头。
"""
import os
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from datetime import datetime, timezone

from app.core import config

# 主航道折线（经, 纬），坐标落在研究水域内
FAIRWAYS = {
    "长江口北槽": [(121.50, 31.40), (121.80, 31.35), (122.10, 31.25),
                (122.40, 31.15), (122.80, 31.05), (123.05, 30.95)],
    "长江口南槽": [(121.60, 31.00), (121.90, 30.90), (122.20, 30.80),
                (122.50, 30.70), (122.80, 30.60)],
    "舟山进港主航道": [(122.00, 30.20), (122.30, 30.30), (122.60, 30.40),
                   (122.90, 30.50), (123.10, 30.60)],
    "洋山杭州湾航道": [(121.50, 30.60), (121.80, 30.50), (122.10, 30.40),
                   (122.40, 30.30)],
    "舟山西航道": [(121.90, 29.90), (122.20, 30.00), (122.50, 30.10),
                (122.80, 30.20)],
    "虾峙门航道": [(122.40, 29.80), (122.70, 29.90), (123.00, 30.00)],
    "绿华山航道": [(122.50, 30.80), (122.80, 30.90), (123.10, 31.00)],
    "吴淞口航道": [(121.50, 31.35), (121.70, 31.40), (121.90, 31.42)],
}
ANCHORAGES = {
    "绿华山锚地": (122.65, 30.85, 0.08),
    "马迹山锚地": (122.10, 30.10, 0.06),
}

SHIP_TYPES = {
    "散货": dict(code="BULK", spd=(8, 12), ln=(150, 300), wd=(25, 50)),
    "集装箱": dict(code="CONT", spd=(12, 18), ln=(180, 400), wd=(30, 60)),
    "油轮": dict(code="TANK", spd=(8, 13), ln=(120, 330), wd=(20, 55)),
    "渔船": dict(code="FISH", spd=(3, 6), ln=(20, 80), wd=(6, 14)),
    "客船": dict(code="PASS", spd=(10, 20), ln=(100, 300), wd=(20, 45)),
}
TYPE_WEIGHTS = [0.30, 0.25, 0.20, 0.18, 0.07]  # 散货/集装箱/油轮/渔船/客船
FINE_SPACING = 0.0004  # 航道重采样间距（度），需小于最慢船每报文位移以区分船速


def _resample(pts, spacing=FINE_SPACING):
    pts = np.asarray(pts, dtype=float)
    seg = np.diff(pts, axis=0)
    seg_len = np.hypot(seg[:, 0], seg[:, 1])
    cum = np.concatenate([[0.0], np.cumsum(seg_len)])
    n = max(2, int(np.ceil(cum[-1] / spacing)) + 1)
    new_cum = np.linspace(0, cum[-1], n)
    lon = np.interp(new_cum, cum, pts[:, 0])
    lat = np.interp(new_cum, cum, pts[:, 1])
    return np.column_stack([lon, lat])


def _racetrack(poly):
    """往返赛道：正向 + 反向，使船在航道内来回。"""
    p = _resample(poly)
    return np.vstack([p, p[-2:0:-1]])


def _mmsi(rng):
    prefix = rng.choice([2, 3, 4])
    return int(prefix) * 100_000_000 + rng.integers(0, 100_000_000)


def _bearing(dlon, dlat):
    return (np.degrees(np.arctan2(dlon, dlat)) + 360.0) % 360.0


def generate_dataset(n_ships=1200, n_points=1_200_000, seed=config.SEED,
                     out_dir=config.AIS_DIR, progress=True):
    rng = np.random.default_rng(seed)
    tracks = [_racetrack(v) for v in FAIRWAYS.values()]
    fnames = list(FAIRWAYS.keys())
    anames = list(ANCHORAGES.keys())

    # 每船点数（均匀 + 余数补偿）
    base = n_points // n_ships
    k_per = np.full(n_ships, base, dtype=int)
    k_per[: n_points - base * n_ships] += 1

    mmsi = np.empty(n_ships, dtype=np.int64)
    sname = np.empty(n_ships, dtype=object)
    stype = np.empty(n_ships, dtype=object)
    slen = np.empty(n_ships, dtype=float)
    swid = np.empty(n_ships, dtype=float)

    # 轨迹列预分配
    tm = np.empty(n_points, dtype=np.int64)        # epoch seconds
    tl = np.empty(n_points, dtype=np.float64)
    tt = np.empty(n_points, dtype=np.float64)
    ts = np.empty(n_points, dtype=np.float64)
    tc = np.empty(n_points, dtype=np.float64)
    tms = np.empty(n_points, dtype=np.int64)
    tnm = np.empty(n_points, dtype=object)
    tty = np.empty(n_points, dtype=object)         # 每点船型

    t0 = datetime(2024, 6, 1, tzinfo=timezone.utc).timestamp()
    span = 48 * 3600  # 48h 时间跨度

    for s in range(n_ships):
        k = int(k_per[s])
        typ = rng.choice(list(SHIP_TYPES.keys()), p=TYPE_WEIGHTS)
        spec = SHIP_TYPES[typ]
        code = spec["code"]
        spd = float(rng.uniform(*spec["spd"]))
        length = float(rng.uniform(*spec["ln"]))
        width = float(rng.uniform(*spec["wd"]))
        m = _mmsi(rng)
        nm = f"{code}{rng.integers(1, 9999):04d}"
        mmsi[s], sname[s], stype[s], slen[s], swid[s] = m, nm, typ, length, width

        # 时间戳：随机起点 + 30-60s 间隔
        interval = float(rng.integers(30, 61))
        offset = float(rng.uniform(0, max(1, span - k * interval)))
        t = (t0 + offset + np.arange(k) * interval).astype(np.int64)

        is_anchor = rng.random() < 0.08
        if is_anchor:
            ac, alat, arad = ANCHORAGES[rng.choice(anames)]
            walk = rng.normal(0, 0.0006, (k, 2)).cumsum(axis=0)
            pos = np.array([ac, alat]) + walk
            # 半径约束
            d = np.hypot(pos[:, 0] - ac, pos[:, 1] - alat)
            mask = d > arad
            pos[mask] = np.array([ac, alat]) + (pos[mask] - np.array([ac, alat])) * (arad / d[mask, None])
            lon_s, lat_s = pos[:, 0], pos[:, 1]
            spd_s = rng.uniform(0.2, 1.5, k)
        else:
            R = tracks[rng.integers(0, len(tracks))]
            L = len(R)
            stride = max(1, int(round(spd * (interval / 3600) / 60 / FINE_SPACING)))
            start = int(rng.integers(0, L))
            idx = (start + np.arange(k) * stride) % L
            pts = R[idx]
            lon_s = pts[:, 0] + rng.normal(0, 0.0008, k)
            lat_s = pts[:, 1] + rng.normal(0, 0.0008, k)
            spd_s = np.clip(spd + rng.normal(0, 0.5, k), 0, None)

        crs = np.empty(k)
        dlon = lon_s[1:] - lon_s[:-1]
        dlat = lat_s[1:] - lat_s[:-1]
        crs[1:] = _bearing(dlon, dlat)
        crs[0] = crs[1] if k > 1 else 0.0

        a = int(k_per[:s].sum())
        b = a + k
        tm[a:b], tl[a:b], tt[a:b] = t, lat_s, lon_s
        ts[a:b], tc[a:b], tms[a:b], tnm[a:b], tty[a:b] = spd_s, crs, m, nm, typ
        if progress and (s + 1) % 200 == 0:
            print(f"  generated {s + 1}/{n_ships} ships ...", flush=True)

    # 写出 Parquet
    os.makedirs(out_dir, exist_ok=True)
    traj_tbl = pa.table({
        "mmsi": pa.array(tms),
        "timestamp": pa.array(tm, type=pa.timestamp("s")),
        "longitude": pa.array(tt),
        "latitude": pa.array(tl),
        "speed": pa.array(ts),
        "course": pa.array(tc),
        "ship_type": pa.array(tty),
        "name": pa.array(tnm),
    })
    ships_tbl = pa.table({
        "mmsi": pa.array(mmsi),
        "name": pa.array(sname),
        "ship_type": pa.array(stype),
        "length": pa.array(slen),
        "width": pa.array(swid),
    })
    pq.write_table(traj_tbl, config.TRAJECTORY_PARQUET)
    pq.write_table(ships_tbl, config.SHIPS_PARQUET)
    return dict(ships=n_ships, points=n_points,
                traj_file=config.TRAJECTORY_PARQUET,
                ships_file=config.SHIPS_PARQUET)
