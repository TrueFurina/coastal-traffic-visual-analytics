import os
import sys
import io
import json
import random
import csv
from datetime import datetime, timedelta
import numpy as np

# 强制设置UTF-8编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
# 设置环境变量确保UTF-8支持
os.environ['PYTHONUTF8'] = '1'
os.environ['PYTHONIOENCODING'] = 'utf-8'

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

# 创建FastAPI应用
app = FastAPI(title="船舶交通流可视化系统")

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 模拟数据库 - 使用内存中的字典存储数据
mock_db = {
    "ships": [],
    "trajectories": [],
    "density_data": []
}

# 数据模型
class ShipBase(BaseModel):
    mmsi: str
    name: str
    ship_type: str
    length: float
    width: float
    draught: float

class ShipCreate(ShipBase):
    pass

class Ship(ShipBase):
    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

class TrajectoryPoint(BaseModel):
    ship_id: str
    timestamp: datetime
    latitude: float
    longitude: float
    speed: float
    course: float
    heading: float

class TrajectoryCreate(TrajectoryPoint):
    pass

class TrajectoryPointOut(TrajectoryPoint):
    id: str

    class Config:
        orm_mode = True

# 生成随机ID
def generate_id():
    return f"{random.randint(100000, 999999)}"

# 生成模拟船舶数据
def generate_mock_ships(count: int = 10):
    ships = []
    ship_types = ["货船", "油轮", "集装箱船", "散货船", "客船"]
    for i in range(count):
        ship = {
            "id": generate_id(),
            "mmsi": f"{random.randint(100000000, 999999999)}",
            "name": f"船舶{i+1}",
            "ship_type": random.choice(ship_types),
            "length": round(random.uniform(50, 300), 2),
            "width": round(random.uniform(10, 50), 2),
            "draught": round(random.uniform(3, 15), 2),
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
        ships.append(ship)
    return ships

# 生成模拟轨迹数据
def generate_mock_trajectories(ships, points_per_ship: int = 50):
    trajectories = []
    # 上海附近海域范围
    base_latitude = 31.23
    base_longitude = 121.47
    
    for ship in ships:
        # 为每个船舶生成轨迹点
        latitude = base_latitude + random.uniform(-0.5, 0.5)
        longitude = base_longitude + random.uniform(-0.5, 0.5)
        
        for i in range(points_per_ship):
            # 每个轨迹点稍微移动一点
            latitude += random.uniform(-0.005, 0.005)
            longitude += random.uniform(-0.005, 0.005)
            
            point = {
                "id": generate_id(),
                "ship_id": ship["id"],
                "timestamp": datetime.now() - timedelta(minutes=i*10),
                "latitude": round(latitude, 6),
                "longitude": round(longitude, 6),
                "speed": round(random.uniform(0, 25), 2),
                "course": round(random.uniform(0, 360), 2),
                "heading": round(random.uniform(0, 360), 2)
            }
            trajectories.append(point)
    
    return trajectories

# 初始化模拟数据
mock_db["ships"] = generate_mock_ships(15)
mock_db["trajectories"] = generate_mock_trajectories(mock_db["ships"], 30)

# API端点
@app.get("/ships", response_model=List[Ship])
async def get_ships():
    return mock_db["ships"]

@app.get("/ships/{ship_id}", response_model=Ship)
async def get_ship(ship_id: str):
    for ship in mock_db["ships"]:
        if ship["id"] == ship_id:
            return ship
    raise HTTPException(status_code=404, detail="船舶不存在")

@app.post("/ships", response_model=Ship)
async def create_ship(ship: ShipCreate):
    new_ship = {
        "id": generate_id(),
        "mmsi": ship.mmsi,
        "name": ship.name,
        "ship_type": ship.ship_type,
        "length": ship.length,
        "width": ship.width,
        "draught": ship.draught,
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    }
    mock_db["ships"].append(new_ship)
    return new_ship

@app.put("/ships/{ship_id}", response_model=Ship)
async def update_ship(ship_id: str, ship: ShipCreate):
    for i, s in enumerate(mock_db["ships"]):
        if s["id"] == ship_id:
            mock_db["ships"][i].update({
                "mmsi": ship.mmsi,
                "name": ship.name,
                "ship_type": ship.ship_type,
                "length": ship.length,
                "width": ship.width,
                "draught": ship.draught,
                "updated_at": datetime.now()
            })
            return mock_db["ships"][i]
    raise HTTPException(status_code=404, detail="船舶不存在")

@app.delete("/ships/{ship_id}")
async def delete_ship(ship_id: str):
    for i, ship in enumerate(mock_db["ships"]):
        if ship["id"] == ship_id:
            del mock_db["ships"][i]
            # 同时删除该船舶的所有轨迹点
            mock_db["trajectories"] = [t for t in mock_db["trajectories"] if t["ship_id"] != ship_id]
            return {"message": "船舶删除成功"}
    raise HTTPException(status_code=404, detail="船舶不存在")

@app.post("/trajectories", response_model=TrajectoryPointOut)
async def create_trajectory_point(point: TrajectoryCreate):
    # 检查船舶是否存在
    ship_exists = any(ship["id"] == point.ship_id for ship in mock_db["ships"])
    if not ship_exists:
        raise HTTPException(status_code=404, detail="船舶不存在")
    
    new_point = {
        "id": generate_id(),
        "ship_id": point.ship_id,
        "timestamp": point.timestamp,
        "latitude": point.latitude,
        "longitude": point.longitude,
        "speed": point.speed,
        "course": point.course,
        "heading": point.heading
    }
    mock_db["trajectories"].append(new_point)
    return new_point

@app.get("/ships/{ship_id}/trajectories", response_model=List[TrajectoryPointOut])
async def get_ship_trajectories(ship_id: str):
    # 检查船舶是否存在
    ship_exists = any(ship["id"] == ship_id for ship in mock_db["ships"])
    if not ship_exists:
        raise HTTPException(status_code=404, detail="船舶不存在")
    
    # 获取该船舶的所有轨迹点，并按时间戳排序
    ship_trajectories = [t for t in mock_db["trajectories"] if t["ship_id"] == ship_id]
    ship_trajectories.sort(key=lambda x: x["timestamp"])
    return ship_trajectories

# 轨迹平滑处理函数
@app.get("/ships/{ship_id}/trajectories/smoothed")
async def get_smoothed_trajectories(ship_id: str):
    # 检查船舶是否存在
    ship_exists = any(ship["id"] == ship_id for ship in mock_db["ships"])
    if not ship_exists:
        raise HTTPException(status_code=404, detail="船舶不存在")
    
    # 获取该船舶的所有轨迹点，并按时间戳排序
    ship_trajectories = [t for t in mock_db["trajectories"] if t["ship_id"] == ship_id]
    ship_trajectories.sort(key=lambda x: x["timestamp"])
    
    if not ship_trajectories:
        return {"points": []}
    
    # 简单的平滑处理：使用移动平均
    latitudes = [p["latitude"] for p in ship_trajectories]
    longitudes = [p["longitude"] for p in ship_trajectories]
    
    # 移动平均滤波
    window_size = 3
    if len(latitudes) >= window_size:
        smoothed_latitudes = []
        smoothed_longitudes = []
        
        for i in range(len(latitudes)):
            start = max(0, i - window_size // 2)
            end = min(len(latitudes), i + window_size // 2 + 1)
            smoothed_latitudes.append(sum(latitudes[start:end]) / (end - start))
            smoothed_longitudes.append(sum(longitudes[start:end]) / (end - start))
        
        # 创建平滑后的轨迹点
        smoothed_points = []
        for i in range(len(ship_trajectories)):
            point = ship_trajectories[i].copy()
            point["latitude"] = smoothed_latitudes[i]
            point["longitude"] = smoothed_longitudes[i]
            smoothed_points.append(point)
        
        return {"points": smoothed_points}
    
    return {"points": ship_trajectories}

# 轨迹密度分布函数
@app.get("/trajectories/density")
async def get_trajectory_density(min_lat: float = 30.5, max_lat: float = 32.0,
                               min_lon: float = 120.5, max_lon: float = 122.5,
                               grid_size: int = 50):
    # 提取所有轨迹点的经纬度
    latitudes = [p["latitude"] for p in mock_db["trajectories"]]
    longitudes = [p["longitude"] for p in mock_db["trajectories"]]
    
    if not latitudes:
        return {"density_data": []}
    
    # 创建二维直方图计算密度
    hist, xedges, yedges = np.histogram2d(
        longitudes, latitudes,
        bins=grid_size,
        range=[[min_lon, max_lon], [min_lat, max_lat]]
    )
    
    # 将密度数据转换为前端可用的格式
    density_data = []
    for i in range(grid_size):
        for j in range(grid_size):
            if hist[i, j] > 0:
                # 计算网格中心坐标
                lon = (xedges[i] + xedges[i+1]) / 2
                lat = (yedges[j] + yedges[j+1]) / 2
                density_data.append({
                    "longitude": lon,
                    "latitude": lat,
                    "density": int(hist[i, j])
                })
    
    return {"density_data": density_data}

# 数据统计API
@app.get("/statistics")
async def get_statistics():
    return {
        "total_ships": len(mock_db["ships"]),
        "total_trajectory_points": len(mock_db["trajectories"]),
        "average_points_per_ship": len(mock_db["trajectories"]) / len(mock_db["ships"]) if mock_db["ships"] else 0
    }

# 文件上传API
@app.post("/import/ships")
async def import_ships(file: UploadFile = File(...)):
    try:
        # 读取文件内容
        content = await file.read()
        
        # 根据文件扩展名决定如何处理
        if file.filename.endswith('.csv'):
            # 处理CSV文件
            # 将字节转换为字符串
            content_str = content.decode('utf-8')
            # 使用csv模块解析
            reader = csv.DictReader(content_str.splitlines())
            imported_count = 0
            
            for row in reader:
                # 检查必要字段
                if 'mmsi' in row and 'name' in row and 'ship_type' in row:
                    # 检查船舶是否已存在
                    existing_ship = next((s for s in mock_db["ships"] if s["mmsi"] == row["mmsi"]), None)
                    
                    if existing_ship:
                        # 更新现有船舶
                        existing_ship.update({
                            "name": row["name"],
                            "ship_type": row["ship_type"],
                            "length": float(row.get("length", 0)),
                            "width": float(row.get("width", 0)),
                            "draught": float(row.get("draught", 0)),
                            "updated_at": datetime.now()
                        })
                    else:
                        # 创建新船舶
                        new_ship = {
                            "id": generate_id(),
                            "mmsi": row["mmsi"],
                            "name": row["name"],
                            "ship_type": row["ship_type"],
                            "length": float(row.get("length", 0)),
                            "width": float(row.get("width", 0)),
                            "draught": float(row.get("draught", 0)),
                            "created_at": datetime.now(),
                            "updated_at": datetime.now()
                        }
                        mock_db["ships"].append(new_ship)
                    
                    imported_count += 1
                    
        elif file.filename.endswith('.json'):
            # 处理JSON文件
            ships_data = json.loads(content)
            imported_count = 0
            
            for ship_data in ships_data:
                # 检查必要字段
                if 'mmsi' in ship_data and 'name' in ship_data and 'ship_type' in ship_data:
                    # 检查船舶是否已存在
                    existing_ship = next((s for s in mock_db["ships"] if s["mmsi"] == ship_data["mmsi"]), None)
                    
                    if existing_ship:
                        # 更新现有船舶
                        existing_ship.update({
                            "name": ship_data["name"],
                            "ship_type": ship_data["ship_type"],
                            "length": float(ship_data.get("length", 0)),
                            "width": float(ship_data.get("width", 0)),
                            "draught": float(ship_data.get("draught", 0)),
                            "updated_at": datetime.now()
                        })
                    else:
                        # 创建新船舶
                        new_ship = {
                            "id": generate_id(),
                            "mmsi": ship_data["mmsi"],
                            "name": ship_data["name"],
                            "ship_type": ship_data["ship_type"],
                            "length": float(ship_data.get("length", 0)),
                            "width": float(ship_data.get("width", 0)),
                            "draught": float(ship_data.get("draught", 0)),
                            "created_at": datetime.now(),
                            "updated_at": datetime.now()
                        }
                        mock_db["ships"].append(new_ship)
                    
                    imported_count += 1
        else:
            raise HTTPException(status_code=400, detail="不支持的文件格式，仅支持CSV和JSON文件")
        
        return {"message": "船舶数据导入成功", "imported_count": imported_count}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")

@app.post("/import/trajectories")
async def import_trajectories(file: UploadFile = File(...)):
    try:
        # 读取文件内容
        content = await file.read()
        
        # 根据文件扩展名决定如何处理
        if file.filename.endswith('.csv'):
            # 处理CSV文件
            # 将字节转换为字符串
            content_str = content.decode('utf-8')
            # 使用csv模块解析
            reader = csv.DictReader(content_str.splitlines())
            imported_count = 0
            
            for row in reader:
                # 检查必要字段
                if 'ship_id' in row or 'mmsi' in row:
                    # 如果提供的是mmsi，需要查找对应的船舶ID
                    ship_id = row.get('ship_id')
                    if not ship_id and 'mmsi' in row:
                        # 查找对应mmsi的船舶
                        ship = next((s for s in mock_db["ships"] if s["mmsi"] == row["mmsi"]), None)
                        if ship:
                            ship_id = ship["id"]
                        else:
                            continue  # 找不到对应的船舶，跳过
                    
                    if ship_id:
                        # 创建新的轨迹点
                        new_point = {
                            "id": generate_id(),
                            "ship_id": ship_id,
                            "timestamp": datetime.fromisoformat(row.get("timestamp", datetime.now().isoformat())),
                            "latitude": float(row.get("latitude", 0)),
                            "longitude": float(row.get("longitude", 0)),
                            "speed": float(row.get("speed", 0)),
                            "course": float(row.get("course", 0)),
                            "heading": float(row.get("heading", 0))
                        }
                        mock_db["trajectories"].append(new_point)
                        imported_count += 1
                        
        elif file.filename.endswith('.json'):
            # 处理JSON文件
            trajectories_data = json.loads(content)
            imported_count = 0
            
            for trajectory_data in trajectories_data:
                # 检查必要字段
                if 'ship_id' in trajectory_data or 'mmsi' in trajectory_data:
                    # 如果提供的是mmsi，需要查找对应的船舶ID
                    ship_id = trajectory_data.get('ship_id')
                    if not ship_id and 'mmsi' in trajectory_data:
                        # 查找对应mmsi的船舶
                        ship = next((s for s in mock_db["ships"] if s["mmsi"] == trajectory_data["mmsi"]), None)
                        if ship:
                            ship_id = ship["id"]
                        else:
                            continue  # 找不到对应的船舶，跳过
                    
                    if ship_id:
                        # 创建新的轨迹点
                        new_point = {
                            "id": generate_id(),
                            "ship_id": ship_id,
                            "timestamp": datetime.fromisoformat(trajectory_data.get("timestamp", datetime.now().isoformat())),
                            "latitude": float(trajectory_data.get("latitude", 0)),
                            "longitude": float(trajectory_data.get("longitude", 0)),
                            "speed": float(trajectory_data.get("speed", 0)),
                            "course": float(trajectory_data.get("course", 0)),
                            "heading": float(trajectory_data.get("heading", 0))
                        }
                        mock_db["trajectories"].append(new_point)
                        imported_count += 1
        else:
            raise HTTPException(status_code=400, detail="不支持的文件格式，仅支持CSV和JSON文件")
        
        return {"message": "轨迹数据导入成功", "imported_count": imported_count}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")

# 提供模拟数据的API，便于前端调试
@app.get("/mock_data/ships")
async def get_mock_ships():
    # 返回格式化后的船舶数据，包含位置信息
    ships_with_position = []
    for ship in mock_db["ships"]:
        # 找到该船舶最新的轨迹点作为当前位置
        latest_position = None
        for point in mock_db["trajectories"]:
            if point["ship_id"] == ship["id"]:
                if latest_position is None or point["timestamp"] > latest_position["timestamp"]:
                    latest_position = point
        
        ship_with_position = ship.copy()
        if latest_position:
            ship_with_position.update({
                "id": ship["id"],
                "mmsi": ship["mmsi"],
                "name": ship["name"],
                "latitude": latest_position["latitude"],
                "longitude": latest_position["longitude"],
                "speed": latest_position["speed"],
                "course": latest_position["course"],
                "heading": latest_position["heading"],
                "status": "航行中",  # 添加状态字段
                "lastUpdated": latest_position["timestamp"],
                "ship_type": ship["ship_type"],
                "length": ship["length"],
                "width": ship["width"],
                "draught": ship["draught"]
            })
        else:
            # 如果没有轨迹数据，使用默认位置
            ship_with_position.update({
                "id": ship["id"],
                "mmsi": ship["mmsi"],
                "name": ship["name"],
                "latitude": 31.2304 + random.uniform(-0.1, 0.1),
                "longitude": 121.4737 + random.uniform(-0.1, 0.1),
                "speed": 0,
                "course": 0,
                "heading": 0,
                "status": "停航",
                "lastUpdated": datetime.now(),
                "ship_type": ship["ship_type"],
                "length": ship["length"],
                "width": ship["width"],
                "draught": ship["draught"]
            })
        ships_with_position.append(ship_with_position)
    
    return ships_with_position

@app.get("/mock_data/trajectories")
async def get_mock_trajectories():
    # 返回所有轨迹数据，但按照船舶ID分组
    trajectories_by_ship = {}
    for point in mock_db["trajectories"]:
        if point["ship_id"] not in trajectories_by_ship:
            trajectories_by_ship[point["ship_id"]] = []
        
        # 格式化轨迹点数据，确保包含所有必要字段
        formatted_point = {
            "id": point["id"],
            "ship_id": point["ship_id"],
            "timestamp": point["timestamp"],
            "latitude": point["latitude"],
            "longitude": point["longitude"],
            "speed": point["speed"],
            "course": point["course"],
            "heading": point["heading"],
            "status": "航行中"  # 添加状态字段
        }
        trajectories_by_ship[point["ship_id"]].append(formatted_point)
    
    # 对每个船舶的轨迹点按时间排序
    for ship_id in trajectories_by_ship:
        trajectories_by_ship[ship_id].sort(key=lambda x: x["timestamp"])
    
    return trajectories_by_ship

@app.get("/")
async def root():
    return {
        "message": "船舶交通流可视化系统API",
        "version": "1.0",
        "endpoints": [
            "/ships - 船舶管理",
            "/trajectories - 轨迹管理",
            "/statistics - 数据统计",
            "/mock_data - 模拟数据（用于前端调试）"
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)