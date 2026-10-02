#!/usr/bin/env python
"""CLI：生成合成 AIS 数据集并落盘为 Parquet。

用法:
    python scripts/generate_dataset.py [--ships 1200] [--points 1200000] [--seed 42]
"""
import argparse
import time
import duckdb
from app.core import config
from app.services import generator


def main():
    ap = argparse.ArgumentParser(description="生成合成 AIS 数据集")
    ap.add_argument("--ships", type=int, default=1200)
    ap.add_argument("--points", type=int, default=1_200_000)
    ap.add_argument("--seed", type=int, default=config.SEED)
    args = ap.parse_args()

    t0 = time.time()
    stats = generator.generate_dataset(
        n_ships=args.ships, n_points=args.points, seed=args.seed)
    elapsed = time.time() - t0

    # 用 DuckDB 校验点数
    n = duckdb.query(
        f"SELECT count(*) FROM read_parquet('{stats['traj_file']}')").fetchone()[0]
    ships = duckdb.query(
        f"SELECT count(*) FROM read_parquet('{stats['ships_file']}')").fetchone()[0]
    size = __import__("os").path.getsize(stats["traj_file"]) / 1e6

    print(f"\n生成完成：")
    print(f"  船舶数      : {ships}")
    print(f"  轨迹点数    : {n:,} (目标 {args.points:,})")
    print(f"  耗时        : {elapsed:.1f}s")
    print(f"  Parquet 大小: {size:.1f} MB")
    print(f"  轨迹文件    : {stats['traj_file']}")
    print(f"  船舶文件    : {stats['ships_file']}")


if __name__ == "__main__":
    main()
