"""
船舶轨迹数据处理工具
提供轨迹平滑、分布分析和可视化预处理功能
"""
from typing import List, Dict, Tuple
import numpy as np
from scipy.interpolate import splprep, splev

class TrajectoryProcessor:
    """
    船舶轨迹数据处理类
    提供轨迹平滑、分布分析和可视化预处理功能
    """
    
    @staticmethod
    def smooth_trajectory(points: List[Tuple[float, float]], smoothing_factor: float = 0.5) -> List[Tuple[float, float]]:
        """
        使用改进的样条插值平滑船舶轨迹
        
        参数:
            points: 轨迹点列表，每个点为(longitude, latitude)元组
            smoothing_factor: 平滑因子，值越小轨迹越接近原始轨迹
        
        返回:
            平滑后的轨迹点列表
        """
        if len(points) < 3:
            return points
            
        # 转换为numpy数组
        points_array = np.array(points)
        
        # 计算轨迹点间的累计距离作为参数
        distances = np.cumsum(np.sqrt(np.sum(np.diff(points_array, axis=0)**2, axis=1)))
        distances = np.insert(distances, 0, 0)
        
        try:
            # 使用更保守的平滑参数
            # 计算合适的平滑因子，避免过度平滑
            total_distance = distances[-1]
            adaptive_smoothing = smoothing_factor * total_distance / len(points)
            
            # 拟合B样条曲线
            tck, _ = splprep(points_array.T, u=distances, s=adaptive_smoothing, k=min(3, len(points)-1))
            
            # 生成平滑后的点，保持原始点数
            new_distances = np.linspace(0, distances[-1], len(points))
            smoothed_points = np.column_stack(splev(new_distances, tck))
            
            return [tuple(point) for point in smoothed_points]
        except Exception as e:
            print(f"轨迹平滑失败，使用移动平均: {e}")
            # 如果样条插值失败，使用移动平均作为备选方案
            return TrajectoryProcessor._moving_average_smooth(points)
    
    @staticmethod
    def _moving_average_smooth(points: List[Tuple[float, float]], window_size: int = 3) -> List[Tuple[float, float]]:
        """
        使用移动平均平滑轨迹
        
        参数:
            points: 轨迹点列表
            window_size: 移动平均窗口大小
        
        返回:
            平滑后的轨迹点列表
        """
        if len(points) < window_size:
            return points
            
        smoothed_points = []
        half_window = window_size // 2
        
        for i in range(len(points)):
            start_idx = max(0, i - half_window)
            end_idx = min(len(points), i + half_window + 1)
            
            window_points = points[start_idx:end_idx]
            avg_lon = sum(p[0] for p in window_points) / len(window_points)
            avg_lat = sum(p[1] for p in window_points) / len(window_points)
            
            smoothed_points.append((avg_lon, avg_lat))
            
        return smoothed_points
    
    @staticmethod
    def calculate_density(points: List[Tuple[float, float]], grid_size: float = 0.01) -> Dict[Tuple[float, float], int]:
        """
        计算轨迹点密度分布
        
        参数:
            points: 轨迹点列表
            grid_size: 网格大小(度)
        
        返回:
            密度字典，键为网格中心点，值为该网格内的点数
        """
        if not points:
            return {}
            
        # 转换为numpy数组
        points_array = np.array(points)
        
        # 计算网格边界
        min_lon, max_lon = np.min(points_array[:,0]), np.max(points_array[:,0])
        min_lat, max_lat = np.min(points_array[:,1]), np.max(points_array[:,1])
        
        # 创建网格
        lon_bins = np.arange(min_lon, max_lon + grid_size, grid_size)
        lat_bins = np.arange(min_lat, max_lat + grid_size, grid_size)
        
        # 计算二维直方图(密度分布)
        density, _, _ = np.histogram2d(
            points_array[:,0], points_array[:,1], 
            bins=[lon_bins, lat_bins]
        )
        
        # 转换为字典格式
        density_dict = {}
        for i in range(len(lon_bins)-1):
            for j in range(len(lat_bins)-1):
                if density[i,j] > 0:
                    center_lon = (lon_bins[i] + lon_bins[i+1]) / 2
                    center_lat = (lat_bins[j] + lat_bins[j+1]) / 2
                    density_dict[(center_lon, center_lat)] = int(density[i,j])
        
        return density_dict
    
    @staticmethod
    def preprocess_for_visualization(tracks: Dict[str, List[Dict]]) -> Dict[str, List[Tuple[float, float]]]:
        """
        预处理轨迹数据用于可视化
        
        参数:
            tracks: 原始轨迹数据，键为船舶ID，值为轨迹点列表
        
        返回:
            处理后的轨迹数据，键为船舶ID，值为(longitude, latitude)元组列表
        """
        processed = {}
        
        for ship_id, points in tracks.items():
            # 提取经纬度并平滑
            coords = [(p['longitude'], p['latitude']) for p in points]
            smoothed = TrajectoryProcessor.smooth_trajectory(coords)
            processed[ship_id] = smoothed
            
        return processed