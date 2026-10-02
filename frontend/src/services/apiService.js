// API服务文件 - 封装所有后端API调用

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

// 获取所有船舶数据
export const getShips = async () => {
  try {
    const response = await fetch(`${BASE_URL}/mock_data/ships`);
    if (!response.ok) {
      throw new Error(`HTTP error! Status: ${response.status}`);
    }
    const data = await response.json();
    return data;
  } catch (error) {
    console.error('获取船舶数据失败:', error);
    throw error;
  }
};

// 获取所有轨迹数据
export const getTrajectories = async () => {
  try {
    const response = await fetch(`${BASE_URL}/mock_data/trajectories`);
    if (!response.ok) {
      throw new Error(`HTTP error! Status: ${response.status}`);
    }
    const data = await response.json();
    return data;
  } catch (error) {
    console.error('获取轨迹数据失败:', error);
    throw error;
  }
};

// 获取船舶密度热图数据
export const getDensityHeatmap = async (params = {}) => {
  try {
    const queryParams = new URLSearchParams(params).toString();
    const response = await fetch(`${BASE_URL}/density/heatmap?${queryParams}`);
    if (!response.ok) {
      throw new Error(`HTTP error! Status: ${response.status}`);
    }
    const data = await response.json();
    return data;
  } catch (error) {
    console.error('获取密度热图数据失败:', error);
    throw error;
  }
};

// 获取统计数据
export const getStatistics = async (params = {}) => {
  try {
    const queryParams = new URLSearchParams(params).toString();
    const response = await fetch(`${BASE_URL}/data/statistics?${queryParams}`);
    if (!response.ok) {
      throw new Error(`HTTP error! Status: ${response.status}`);
    }
    const data = await response.json();
    return data;
  } catch (error) {
    console.error('获取统计数据失败:', error);
    throw error;
  }
};

// 获取特定船舶的轨迹
export const getShipTrajectory = async (shipId) => {
  try {
    const response = await fetch(`${BASE_URL}/ships/${shipId}/trajectories`);
    if (!response.ok) {
      throw new Error(`HTTP error! Status: ${response.status}`);
    }
    const data = await response.json();
    return data;
  } catch (error) {
    console.error(`获取船舶 ${shipId} 轨迹失败:`, error);
    throw error;
  }
};

// 获取特定船舶的平滑轨迹
export const getSmoothedShipTrajectory = async (shipId) => {
  try {
    const response = await fetch(`${BASE_URL}/ships/${shipId}/trajectories/smoothed`);
    if (!response.ok) {
      throw new Error(`HTTP error! Status: ${response.status}`);
    }
    const data = await response.json();
    return data;
  } catch (error) {
    console.error(`获取船舶 ${shipId} 平滑轨迹失败:`, error);
    throw error;
  }
};

// 导入船舶数据
export const importShipsData = async (file) => {
  try {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await fetch(`${BASE_URL}/import/ships`, {
      method: 'POST',
      body: formData
    });
    
    if (!response.ok) {
      throw new Error(`HTTP error! Status: ${response.status}`);
    }
    
    const data = await response.json();
    return data;
  } catch (error) {
    console.error('导入船舶数据失败:', error);
    throw error;
  }
};

// 导入轨迹数据
export const importTrajectoriesData = async (file) => {
  try {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await fetch(`${BASE_URL}/import/trajectories`, {
      method: 'POST',
      body: formData
    });
    
    if (!response.ok) {
      throw new Error(`HTTP error! Status: ${response.status}`);
    }
    
    const data = await response.json();
    return data;
  } catch (error) {
    console.error('导入轨迹数据失败:', error);
    throw error;
  }
};

// 导出船舶数据
export const exportShipsData = async () => {
  try {
    const response = await fetch(`${BASE_URL}/export/ships`);
    if (!response.ok) {
      throw new Error(`HTTP error! Status: ${response.status}`);
    }
    
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'ships_data.csv';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
  } catch (error) {
    console.error('导出船舶数据失败:', error);
    throw error;
  }
};

// 导出轨迹数据
export const exportTrajectoriesData = async () => {
  try {
    const response = await fetch(`${BASE_URL}/export/trajectories`);
    if (!response.ok) {
      throw new Error(`HTTP error! Status: ${response.status}`);
    }
    
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'trajectories_data.csv';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
  } catch (error) {
    console.error('导出轨迹数据失败:', error);
    throw error;
  }
};