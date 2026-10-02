"""船舶路由：列表 / 详情。"""
from fastapi import APIRouter, HTTPException, Query
from typing import List
from app.core import config
from app.services import ais_store
from app.schemas import ShipOut

router = APIRouter(prefix="/ships", tags=["ships"])


@router.get("", response_model=List[ShipOut])
def get_ships(
    limit: int = Query(config.SHIP_LIST_LIMIT, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    min_lon: float = None, min_lat: float = None,
    max_lon: float = None, max_lat: float = None,
    ship_type: str = None,
):
    return ais_store.list_ships(limit, offset, min_lon, min_lat, max_lon, max_lat, ship_type)


@router.get("/{ship_id}", response_model=ShipOut)
def get_ship(ship_id: str):
    ship = ais_store.get_ship(ship_id)
    if ship is None:
        raise HTTPException(status_code=404, detail="船舶不存在")
    return ship
