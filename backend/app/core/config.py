"""应用配置：路径、端口、研究水域与默认参数。"""
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "data")
AIS_DIR = os.path.join(DATA_DIR, "ais")
RAW_DIR = os.path.join(DATA_DIR, "raw")

TRAJECTORY_PARQUET = os.path.join(AIS_DIR, "trajectories.parquet")
SHIPS_PARQUET = os.path.join(AIS_DIR, "ships.parquet")

PORT = 8000
SEED = 42

# 长江口—舟山研究水域
STUDY_AREA = {
    "min_lon": 121.4, "max_lon": 123.2,
    "min_lat": 29.7, "max_lat": 31.5,
}

# 清洗默认阈值
MAX_SPEED_KN = 40.0          # 超过视为异常
JUMP_SPEED_KN = 50.0         # 相邻点推算速度上限

# 默认上限，避免单次返回爆炸
SHIP_LIST_LIMIT = 500
TRAJ_POINT_LIMIT = 5000
HEATMAP_MAX_CELLS = 20000

os.makedirs(AIS_DIR, exist_ok=True)
os.makedirs(RAW_DIR, exist_ok=True)
