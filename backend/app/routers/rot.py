"""航向角变化率（ROT）路由 —— 对应申报书创新点 3.1 的 D1。

独立成文件的原因：analysis.py 已达 200 行上限，再加端点需先拆。
"""
from fastapi import APIRouter, Query
from typing import Optional
from app.core import config
from app.services import rot as rot_mod

router = APIRouter(prefix="/analysis/rot", tags=["analysis"])

SA = config.STUDY_AREA
DEFAULT_WINDOW = rot_mod._DEFAULT_WINDOW_MIN


@router.get("/statistics")
def rot_statistics(
    min_lon: float = Query(SA["min_lon"]),
    min_lat: float = Query(SA["min_lat"]),
    max_lon: float = Query(SA["max_lon"]),
    max_lat: float = Query(SA["max_lat"]),
    start: Optional[str] = None,
    end: Optional[str] = None,
    window_min: int = Query(DEFAULT_WINDOW, ge=0, le=120,
                            description="聚合窗口分钟数，0 表示逐点差分"),
    maneuver_rot: float = Query(rot_mod._MANEUVER_ROT, ge=0.0, le=60.0),
    steady_rot: float = Query(rot_mod._STEADY_ROT, ge=0.0, le=10.0),
):
    return rot_mod.rot_statistics(
        min_lon, min_lat, max_lon, max_lat, start, end,
        window_min, maneuver_rot, steady_rot)


@router.get("/by-type")
def rot_by_ship_type(
    min_lon: float = Query(SA["min_lon"]),
    min_lat: float = Query(SA["min_lat"]),
    max_lon: float = Query(SA["max_lon"]),
    max_lat: float = Query(SA["max_lat"]),
    start: Optional[str] = None,
    end: Optional[str] = None,
    window_min: int = Query(DEFAULT_WINDOW, ge=0, le=120),
    maneuver_rot: float = Query(rot_mod._MANEUVER_ROT, ge=0.0, le=60.0),
):
    return rot_mod.rot_by_ship_type(
        min_lon, min_lat, max_lon, max_lat, start, end,
        window_min, maneuver_rot)


@router.get("/grid")
def rot_grid(
    min_lon: float = Query(SA["min_lon"]),
    min_lat: float = Query(SA["min_lat"]),
    max_lon: float = Query(SA["max_lon"]),
    max_lat: float = Query(SA["max_lat"]),
    start: Optional[str] = None,
    end: Optional[str] = None,
    grid_size: int = Query(40, ge=2, le=400),
    window_min: int = Query(DEFAULT_WINDOW, ge=0, le=120),
    maneuver_rot: float = Query(rot_mod._MANEUVER_ROT, ge=0.0, le=60.0),
):
    return rot_mod.rot_grid(
        min_lon, min_lat, max_lon, max_lat, start, end,
        grid_size, window_min, maneuver_rot)


@router.get("/distribution")
def rot_distribution(
    min_lon: float = Query(SA["min_lon"]),
    min_lat: float = Query(SA["min_lat"]),
    max_lon: float = Query(SA["max_lon"]),
    max_lat: float = Query(SA["max_lat"]),
    start: Optional[str] = None,
    end: Optional[str] = None,
    window_min: int = Query(DEFAULT_WINDOW, ge=0, le=120),
    bins: int = Query(24, ge=4, le=100),
):
    return rot_mod.rot_distribution(
        min_lon, min_lat, max_lon, max_lat, start, end,
        window_min, rot_mod._MAX_GAP_S, bins)
