"""Mock 数据路由：从真实数据集返回样本，供前端即时可视化。"""
from fastapi import APIRouter, Query
from app.services import ais_store

router = APIRouter(prefix="/mock_data", tags=["mock_data"])


@router.get("/ships")
def mock_ships(
    limit: int = Query(500, ge=1, le=2000),
    min_lon: float = None, min_lat: float = None,
    max_lon: float = None, max_lat: float = None,
):
    # 直接复用真实船舶列表（含最新位置）
    return ais_store.list_ships(limit, 0, min_lon, min_lat, max_lon, max_lat)


@router.get("/trajectories")
def mock_trajectories(
    limit: int = Query(20, ge=1, le=200),
    max_points: int = Query(200, ge=1, le=2000),
):
    ships = ais_store.list_ships(limit, 0)
    result = {}
    for s in ships:
        pts = ais_store.get_ship_trajectory(s["mmsi"], max_points)
        if not pts:
            continue
        result[s["mmsi"]] = [
            {**p, "status": "航行中"} for p in pts
        ]
    return result
