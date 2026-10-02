"""Pydantic 响应/请求模型。"""
from typing import Dict, List, Optional
from pydantic import BaseModel


class ShipOut(BaseModel):
    id: str
    mmsi: str
    name: str
    ship_type: str
    length: float
    width: float
    longitude: Optional[float] = None
    latitude: Optional[float] = None
    speed: Optional[float] = None
    course: Optional[float] = None
    status: Optional[str] = None
    lastUpdated: Optional[str] = None


class TrajectoryPointOut(BaseModel):
    id: str
    ship_id: str
    timestamp: str
    latitude: float
    longitude: float
    speed: float
    course: float
    heading: float


class SmoothedResponse(BaseModel):
    points: List[TrajectoryPointOut]


class DensityResponse(BaseModel):
    density_data: List[Dict[str, float]]


class StatisticsOut(BaseModel):
    total_ships: int
    total_trajectory_points: int
    average_points_per_ship: float
    time_range: Optional[Dict] = None
    ship_type_distribution: Optional[Dict] = None


class CleaningReport(BaseModel):
    total_in: int
    parsed: int
    dropped_missing: int
    dropped_bounds: int
    dropped_dup: int
    dropped_speed: int
    dropped_jump: int
    total_out: int


class ImportResult(BaseModel):
    message: str
    imported_count: int
    cleaning_report: Optional[CleaningReport] = None
