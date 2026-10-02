"""单船轨迹路由：原始抽稀轨迹与平滑轨迹。"""
from fastapi import APIRouter, HTTPException, Query
from app.core import config
from app.services import ais_store, smoothing
from app.schemas import TrajectoryPointOut, SmoothedResponse

router = APIRouter(tags=["trajectories"])


@router.get("/ships/{ship_id}/trajectories", response_model=list[TrajectoryPointOut])
def ship_trajectories(
    ship_id: str,
    limit: int = Query(config.TRAJ_POINT_LIMIT, ge=1, le=20000),
    start: str = None, end: str = None,
):
    pts = ais_store.get_ship_trajectory(ship_id, limit, start, end)
    if pts is None:
        raise HTTPException(status_code=404, detail="船舶不存在")
    return pts


@router.get("/ships/{ship_id}/trajectories/smoothed", response_model=SmoothedResponse)
def ship_trajectories_smoothed(
    ship_id: str,
    limit: int = Query(config.TRAJ_POINT_LIMIT, ge=1, le=20000),
    window: int = Query(5, ge=2, le=31),
    start: str = None, end: str = None,
):
    pts = ais_store.get_ship_trajectory(ship_id, limit, start, end)
    if pts is None:
        raise HTTPException(status_code=404, detail="船舶不存在")
    smoothed = smoothing.smooth_points(pts, window)
    return {"points": smoothed}
