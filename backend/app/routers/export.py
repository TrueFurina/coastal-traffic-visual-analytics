"""导出路由：将 Parquet 数据导出为 CSV。"""
import os
from fastapi import APIRouter, Query
from fastapi.responses import FileResponse
from app.core import config, db

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/ships")
def export_ships():
    path = os.path.join(config.RAW_DIR, "ships_export.csv")
    db.get_conn().execute(
        f"COPY (SELECT * FROM read_parquet('{config.SHIPS_PARQUET}')) "
        f"TO '{path}' (FORMAT CSV, HEADER TRUE)")
    return FileResponse(path, media_type="text/csv", filename="ships_data.csv")


@router.get("/trajectories")
def export_trajectories(limit: int = Query(200000, ge=1, le=2000000)):
    path = os.path.join(config.RAW_DIR, "trajectories_export.csv")
    db.get_conn().execute(
        f"COPY (SELECT * FROM read_parquet('{config.TRAJECTORY_PARQUET}') "
        f"LIMIT {int(limit)}) TO '{path}' (FORMAT CSV, HEADER TRUE)")
    return FileResponse(path, media_type="text/csv", filename="trajectories_data.csv")
