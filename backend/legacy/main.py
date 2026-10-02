import os
import sys
import io
# 强制设置UTF-8编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
# 设置环境变量确保UTF-8支持
os.environ['PYTHONUTF8'] = '1'
os.environ['PYTHONIOENCODING'] = 'utf-8'

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from prisma import Prisma
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 初始化FastAPI应用
app = FastAPI(
    title="船舶交通流可视化系统API",
    description="提供船舶交通流数据的管理、查询和分析接口",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 配置CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应限制允许的源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化Prisma客户端
prisma = Prisma()

# 依赖项：获取数据库连接
async def get_db():
    try:
        await prisma.connect()
        yield prisma
    finally:
        await prisma.disconnect()

# 根路径端点
@app.get("/", status_code=status.HTTP_200_OK)
async def root():
    return {"message": "船舶交通流可视化系统API", "version": "1.0.0", "docs_url": "/docs"}

# 健康检查端点
@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    return {"status": "healthy", "message": "船舶交通流可视化系统API运行正常"}

# 船舶数据模型
class ShipBase(BaseModel):
    name: str
    mmsi: str
    imo: Optional[str] = None
    ship_type: Optional[str] = None
    length: Optional[float] = None
    width: Optional[float] = None
    draft: Optional[float] = None

class ShipCreate(ShipBase):
    pass

class Ship(ShipBase):
    id: int
    created_at: str
    updated_at: Optional[str] = None

    class Config:
        orm_mode = True

# 船舶轨迹数据模型
class ShipTrackBase(BaseModel):
    ship_id: int
    timestamp: str
    longitude: float
    latitude: float
    course: Optional[float] = None
    speed: Optional[float] = None
    heading: Optional[float] = None
    status: Optional[str] = None

class ShipTrackCreate(ShipTrackBase):
    pass

class ShipTrack(ShipTrackBase):
    id: int

    class Config:
        orm_mode = True

# 船舶API路由
@app.post("/ships", response_model=Ship, status_code=status.HTTP_201_CREATED)
async def create_ship(ship: ShipCreate, db: Prisma = Depends(get_db)):
    """创建新船舶"""
    try:
        new_ship = await db.ship.create(
            data={
                "name": ship.name,
                "mmsi": ship.mmsi,
                "imo": ship.imo,
                "ship_type": ship.ship_type,
                "length": ship.length,
                "width": ship.width,
                "draft": ship.draft
            }
        )
        return new_ship
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"创建船舶失败: {str(e)}")

@app.get("/ships", response_model=List[Ship])
async def get_ships(skip: int = 0, limit: int = 100, db: Prisma = Depends(get_db)):
    """获取船舶列表"""
    ships = await db.ship.find_many(skip=skip, take=limit)
    return ships

@app.get("/ships/{ship_id}", response_model=Ship)
async def get_ship(ship_id: int, db: Prisma = Depends(get_db)):
    """获取单艘船舶详情"""
    ship = await db.ship.find_unique(where={"id": ship_id})
    if not ship:
        raise HTTPException(status_code=404, detail="船舶不存在")
    return ship

@app.put("/ships/{ship_id}", response_model=Ship)
async def update_ship(ship_id: int, ship: ShipCreate, db: Prisma = Depends(get_db)):
    """更新船舶信息"""
    existing_ship = await db.ship.find_unique(where={"id": ship_id})
    if not existing_ship:
        raise HTTPException(status_code=404, detail="船舶不存在")
    try:
        updated_ship = await db.ship.update(
            where={"id": ship_id},
            data={
                "name": ship.name,
                "mmsi": ship.mmsi,
                "imo": ship.imo,
                "ship_type": ship.ship_type,
                "length": ship.length,
                "width": ship.width,
                "draft": ship.draft
            }
        )
        return updated_ship
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"更新船舶失败: {str(e)}")

@app.delete("/ships/{ship_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ship(ship_id: int, db: Prisma = Depends(get_db)):
    """删除船舶"""
    existing_ship = await db.ship.find_unique(where={"id": ship_id})
    if not existing_ship:
        raise HTTPException(status_code=404, detail="船舶不存在")
    await db.ship.delete(where={"id": ship_id})
    return None

# 船舶轨迹API路由
@app.post("/tracks", response_model=ShipTrack, status_code=status.HTTP_201_CREATED)
async def create_track(track: ShipTrackCreate, db: Prisma = Depends(get_db)):
    """创建船舶轨迹点"""
    # 检查船舶是否存在
    ship = await db.ship.find_unique(where={"id": track.ship_id})
    if not ship:
        raise HTTPException(status_code=404, detail="船舶不存在")
    try:
        new_track = await db.shiptrack.create(
            data={
                "ship_id": track.ship_id,
                "timestamp": track.timestamp,
                "longitude": track.longitude,
                "latitude": track.latitude,
                "course": track.course,
                "speed": track.speed,
                "heading": track.heading,
                "status": track.status
            }
        )
        return new_track
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"创建轨迹点失败: {str(e)}")

@app.get("/tracks/ship/{ship_id}", response_model=List[ShipTrack])
async def get_ship_tracks(ship_id: int, start_time: Optional[str] = None, end_time: Optional[str] = None, db: Prisma = Depends(get_db)):
    """获取船舶轨迹"""
    # 检查船舶是否存在
    ship = await db.ship.find_unique(where={"id": ship_id})
    if not ship:
        raise HTTPException(status_code=404, detail="船舶不存在")
    
    # 构建查询条件
    where = {"ship_id": ship_id}
    if start_time and end_time:
        where["timestamp"] = {"gte": start_time, "lte": end_time}
    elif start_time:
        where["timestamp"] = {"gte": start_time}
    elif end_time:
        where["timestamp"] = {"lte": end_time}
    
    tracks = await db.shiptrack.find_many(where=where, order={"timestamp": "asc"})
    return tracks

@app.get("/tracks/ship/{ship_id}/smoothed")
async def get_smoothed_ship_tracks(ship_id: int, start_time: Optional[str] = None, end_time: Optional[str] = None, db: Prisma = Depends(get_db)):
    """获取平滑处理后的船舶轨迹"""
    from utils.trajectory_processor import TrajectoryProcessor
    
    # 获取原始轨迹数据
    raw_tracks = await get_ship_tracks(ship_id, start_time, end_time, db)
    
    # 提取经纬度坐标
    points = [(track.longitude, track.latitude) for track in raw_tracks]
    
    # 平滑处理
    smoothed_points = TrajectoryProcessor.smooth_trajectory(points)
    
    # 转换为前端需要的格式
    return [{"longitude": lon, "latitude": lat} for lon, lat in smoothed_points]

@app.get("/tracks/density")
async def get_tracks_density(start_time: Optional[str] = None, end_time: Optional[str] = None, db: Prisma = Depends(get_db)):
    """获取轨迹密度分布"""
    from utils.trajectory_processor import TrajectoryProcessor
    
    # 获取所有轨迹点
    where = {}
    if start_time and end_time:
        where["timestamp"] = {"gte": start_time, "lte": end_time}
    elif start_time:
        where["timestamp"] = {"gte": start_time}
    elif end_time:
        where["timestamp"] = {"lte": end_time}
    
    tracks = await db.shiptrack.find_many(where=where)
    
    # 提取经纬度坐标
    points = [(track.longitude, track.latitude) for track in tracks]
    
    # 计算密度分布
    density = TrajectoryProcessor.calculate_density(points)
    
    # 转换为前端需要的格式
    return [{"longitude": lon, "latitude": lat, "count": count} for (lon, lat), count in density.items()]

# 数据统计API
@app.get("/statistics/ship-count")
async def get_ship_count(db: Prisma = Depends(get_db)):
    """获取船舶总数"""
    count = await db.ship.count()
    return {"count": count}

@app.get("/statistics/track-count")
async def get_track_count(db: Prisma = Depends(get_db)):
    """获取轨迹点总数"""
    count = await db.shiptrack.count()
    return {"count": count}

# 启动应用
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)