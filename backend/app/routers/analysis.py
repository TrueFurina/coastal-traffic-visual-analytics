"""分析路由：密度热图 + 统计 + 交通流算法 + 船舶交互感知。"""
from fastapi import APIRouter, Query, HTTPException
from typing import List, Optional, Tuple
from app.core import config
from app.services import ais_store, traffic, kde, metrics
from app.schemas import DensityResponse, StatisticsOut
from app.services import kde as kde_mod
from app.services import metrics as metrics_mod
from app.services import multivariate as multivariate_mod
from app.services import interaction as interaction_mod
from app.services import domain as domain_mod

router = APIRouter(tags=["analysis"])

SA = config.STUDY_AREA


@router.get("/density/heatmap", response_model=DensityResponse)
def density_heatmap(
    min_lon: float = Query(SA["min_lon"]),
    min_lat: float = Query(SA["min_lat"]),
    max_lon: float = Query(SA["max_lon"]),
    max_lat: float = Query(SA["max_lat"]),
    grid_size: int = Query(50, ge=1, le=200),
    start: str = None, end: str = None,
    ship_type: str = None,
):
    cells = ais_store.grid_density(
        min_lon, min_lat, max_lon, max_lat, grid_size, start, end, ship_type)
    return {"density_data": cells}


@router.get("/data/statistics", response_model=StatisticsOut)
def data_statistics(
    min_lon: float = None, min_lat: float = None,
    max_lon: float = None, max_lat: float = None,
    start: str = None, end: str = None,
):
    return ais_store.statistics(min_lon, min_lat, max_lon, max_lat, start, end)


@router.get("/analysis/speed-course")
def speed_course(
    min_lon: float = SA["min_lon"], min_lat: float = SA["min_lat"],
    max_lon: float = SA["max_lon"], max_lat: float = SA["max_lat"],
    start: str = None, end: str = None,
):
    return traffic.speed_course_distribution(min_lon, min_lat, max_lon, max_lat, start, end)


@router.get("/analysis/sectional-flow")
def sectional(
    lon1: float = Query(122.0), lat1: float = Query(30.8),
    lon2: float = Query(123.0), lat2: float = Query(30.8),
    start: str = None, end: str = None,
):
    barrier = [(lon1, lat1), (lon2, lat2)]
    return traffic.sectional_flow(barrier, start=start, end=end)


@router.get("/analysis/snapshot")
def snapshot(
    at: str,
    min_lon: float = None, min_lat: float = None,
    max_lon: float = None, max_lat: float = None,
    limit: int = Query(5000, ge=1, le=20000),
):
    return {"ships": traffic.snapshot(at, min_lon, min_lat, max_lon, max_lat, limit)}


@router.get("/analysis/corridors")
def corridors(
    grid_size: int = Query(60, ge=10, le=200),
    threshold_ratio: float = Query(0.5, ge=0.0, le=1.0),
    start: str = None, end: str = None,
):
    return {"corridors": traffic.extract_corridors(grid_size, threshold_ratio, start, end)}


@router.get("/analysis/od")
def od(
    grid_size: int = Query(20, ge=5, le=100),
    top_n: int = Query(20, ge=1, le=100),
    start: str = None, end: str = None,
):
    return {"od": traffic.od_matrix(grid_size, start, end, top_n)}


@router.get("/ships/{ship_id}/trajectories/simplified")
def simplified(
    ship_id: str,
    tolerance: float = Query(0.002, ge=0.0001, le=0.05),
    limit: int = Query(config.TRAJ_POINT_LIMIT, ge=1, le=50000),
    start: str = None, end: str = None,
):
    return {"points": traffic.simplify_trajectory(ship_id, tolerance, limit, start, end)}


@router.get("/analysis/kde")
def kde(
    bandwidth_deg: float = Query(0.02, ge=0.002, le=0.2),
    grid_size: int = Query(80, ge=10, le=200),
    min_lon: float = None, min_lat: float = None,
    max_lon: float = None, max_lat: float = None,
    start: str = None, end: str = None,
):
    return kde_mod.kde_surface(bandwidth_deg, grid_size, None,
                               min_lon, min_lat, max_lon, max_lat, start, end)


@router.get("/analysis/hotspots")
def hotspots(
    top_n: int = Query(10, ge=1, le=100),
    bandwidth_deg: float = Query(0.02, ge=0.002, le=0.2),
    start: str = None, end: str = None,
):
    return kde_mod.peak_locations(top_n, bandwidth_deg=bandwidth_deg,
                                  start=start, end=end)


@router.get("/analysis/multivariate")
def multivariate(
    n: int = Query(1500, ge=10, le=20000),
    min_lon: float = None, min_lat: float = None,
    max_lon: float = None, max_lat: float = None,
    start: str = None, end: str = None,
):
    return multivariate_mod.multivariate_sample(
        n, min_lon, min_lat, max_lon, max_lat, start, end)


@router.get("/analysis/metrics")
def metrics(
    bandwidth_deg: float = Query(0.02, ge=0.002, le=0.2),
    min_lon: float = None, min_lat: float = None,
    max_lon: float = None, max_lat: float = None,
    start: str = None, end: str = None,
):
    return metrics_mod.traffic_metrics(min_lon, min_lat, max_lon, max_lat,
                                       start, end, bandwidth_deg)


def _bbox(min_lon, min_lat, max_lon, max_lat):
    """四个边界全给才构成有效范围，否则返回 None（表示不限区域）。"""
    if None in (min_lon, min_lat, max_lon, max_lat):
        return None
    return (min_lon, min_lat, max_lon, max_lat)


# ---------- 多智能体交互感知层（L2） ----------


@router.get("/analysis/encounters")
def encounters(
    start: str = None, end: str = None,
    dcpa_nm: float = Query(1.0, ge=0.05, le=5.0),
    lookahead_min: float = Query(30.0, ge=1.0, le=120.0),
    min_distance_nm: float = Query(0.1, ge=0.0, le=1.0),
    limit: int = Query(500, ge=1, le=5000),
    min_lon: float = None, min_lat: float = None,
    max_lon: float = None, max_lat: float = None,
):
    """船舶会遇检测：CPA/TCPA + COLREGs 局面与让路责任。"""
    return interaction_mod.detect_encounters(
        start, end, _bbox(min_lon, min_lat, max_lon, max_lat),
        dcpa_nm, lookahead_min, 6.0, limit, min_distance_nm)


@router.get("/analysis/conflicts")
def conflicts(
    grid_size: int = Query(40, ge=5, le=200),
    top_n: int = Query(30, ge=1, le=200),
    dcpa_nm: float = Query(1.0, ge=0.05, le=5.0),
    lookahead_min: float = Query(30.0, ge=1.0, le=120.0),
    start: str = None, end: str = None,
    min_lon: float = None, min_lat: float = None,
    max_lon: float = None, max_lat: float = None,
):
    """会遇事件的网格热点聚合，可直接叠加地图；bbox 决定网格划分范围。"""
    return interaction_mod.conflict_hotspots(
        start, end, _bbox(min_lon, min_lat, max_lon, max_lat),
        grid_size, dcpa_nm, lookahead_min, top_n)


@router.get("/analysis/domain-violations")
def domain_violations(
    model: str = Query("fujii"),
    scale: float = Query(1.0, ge=0.1, le=5.0),
    limit: int = Query(500, ge=1, le=5000),
    start: str = None, end: str = None,
    min_lon: float = None, min_lat: float = None,
    max_lon: float = None, max_lat: float = None,
):
    """船舶领域侵犯检测，并输出船头间距(along)与横向间距(cross)。"""
    try:
        return domain_mod.violations(
            start, end, _bbox(min_lon, min_lat, max_lon, max_lat),
            model, scale, limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
