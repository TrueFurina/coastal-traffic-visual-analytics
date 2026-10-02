// 后端 API 客户端：所有请求集中在此，组件只关心类型。
export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

export interface ShipSnapshot {
  mmsi: string;
  name?: string;
  ship_type?: string;
  longitude: number;
  latitude: number;
  speed?: number;
  course?: number;
  timestamp?: string;
  status?: string;
}

export interface DensityCell {
  longitude: number;
  latitude: number;
  density: number;
}

export interface TrajectoryPoint {
  longitude: number;
  latitude: number;
  speed?: number;
  course?: number;
  timestamp?: string;
}

export interface Statistics {
  total_ships: number;
  total_trajectory_points: number;
  average_points_per_ship: number;
  time_range: { start: string; end: string };
  ship_type_distribution: Record<string, number>;
}

export interface SpeedCourseOut {
  count: number;
  speed_hist: { label: string; count: number }[];
  course_hist: { sector_deg: number; count: number }[];
  behavior: { anchored: number; maneuvering: number; underway: number };
}

export interface SectionalFlowOut {
  total: number;
  seaward: number;
  landward: number;
  crossings: { mmsi: string; timestamp: string; direction: string }[];
  timeseries: { hour: string; count: number }[];
}

export interface Corridor {
  cell_count: number;
  centers: { longitude: number; latitude: number }[];
}

export interface ODItem {
  origin: { longitude: number; latitude: number };
  destination: { longitude: number; latitude: number };
  count: number;
}

/** 平行坐标用：一条记录 = 一艘船的一次 AIS 观测 = 图中一条折线。 */
export interface MultivariateRow {
  mmsi: string;
  ship_type: string;
  speed: number;
  course: number;
  longitude: number;
  latitude: number;
  hour: number;
  /** 航向角变化率（°/min），口径由 window_min 决定 */
  rot: number;
}

export interface MultivariateAxis {
  key: string;
  name: string;
  unit: string;
  categorical: boolean;
}

export interface MultivariateOut {
  count: number;
  sample_size: number;
  /** 转向率聚合窗口（分钟），0 表示逐点差分 */
  window_min: number;
  rows: MultivariateRow[];
  axes: MultivariateAxis[];
  ranges: Record<string, number[] | string[]>;
}

/* ---------- 航向角变化率（D1）：统计 / 分船型 / 网格 / 分布 ---------- */

export interface RotIndicator {
  key: string;
  name: string;
  value: number;
  unit: string;
  desc: string;
}

export interface RotStatisticsOut {
  count: number;
  parameters: { window_min: number; maneuver_rot: number; steady_rot: number; max_gap_s: number };
  time_window: { start?: string; end?: string };
  region: BBox;
  diagnostics: {
    scale: string;
    window_min: number;
    pointwise_mean_abs_rot?: number;
    noise_amplification?: number | null;
    note: string;
  };
  indicators: RotIndicator[];
}

export interface RotGridOut {
  count: number;
  grid_size: number;
  window_min: number;
  bbox: BBox;
  maneuver_rot: number;
  cells: {
    gx: number; gy: number; samples: number;
    mean_abs_rot: number; maneuver_ratio: number;
    lon: number; lat: number;
  }[];
}

export interface RotByTypeOut {
  count: number;
  window_min: number;
  maneuver_rot: number;
  rows: {
    ship_type: string; samples: number;
    mean_abs_rot: number; rot_p95: number; maneuver_ratio: number;
  }[];
}

export interface RotDistributionOut {
  count: number;
  unit: string;
  window_min: number;
  note: string;
  bins: { from: number; to: number; count: number }[];
}

/* ---------- L2 船舶交互层：会遇 / 冲突热点 / 船舶领域 ---------- */

/** 一次会遇事件：本船与目标船的 CPA 结果 + COLREGs 局面判定。 */
export interface EncounterItem {
  bucket_minutes: number;
  own_mmsi: string;
  target_mmsi: string;
  longitude: number;
  latitude: number;
  own_speed_kn: number;
  target_speed_kn: number;
  distance_nm: number;
  dcpa_nm: number;
  tcpa_min: number;
  relative_bearing_deg: number;
  heading_diff_deg: number;
  situation: string; // 对遇 / 交叉 / 追越
  responsibility: string;
}

export interface EncountersOut {
  count: number;
  returned: number;
  encounters: EncounterItem[];
  situation_stats: Record<string, number>;
  diagnostics: { degenerate_overlap_excluded: number; note: string };
  parameters: Record<string, number>;
  time_window: { start?: string; end?: string };
}

/** 会遇事件的网格热点聚合。 */
export interface ConflictCell {
  longitude: number;
  latitude: number;
  count: number;
  severe_count: number;
  mean_dcpa_nm: number;
}

export interface ConflictsOut {
  count: number;
  grid_size: number;
  total_encounters: number;
  cells: ConflictCell[];
}

/** 船舶领域侵犯事件：along_nm 即申报书所称「船头间距」。 */
export interface DomainViolation {
  bucket_minutes: number;
  own_mmsi: string;
  target_mmsi: string;
  longitude: number;
  latitude: number;
  distance_nm: number;
  domain_radius_nm: number;
  penetration_ratio: number;
  along_nm: number;
  cross_nm: number;
  relative_bearing_deg: number;
}

export interface DomainOut {
  count: number;
  returned: number;
  violations: DomainViolation[];
  most_violated_ships: { mmsi: string; count: number }[];
  // 后端 diagnostics 的键含点号（overlap_lt_0.05nm），用索引签名兜住
  diagnostics: { note: string } & Record<string, number | string>;
  parameters: Record<string, unknown>;
  time_window: { start?: string; end?: string };
}

export interface BBox {
  min_lon: number;
  min_lat: number;
  max_lon: number;
  max_lat: number;
}

type Params = Record<string, string | number | undefined | null>;

function buildQuery(params: Params = {}): string {
  const usp = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') usp.set(k, String(v));
  });
  const s = usp.toString();
  return s ? `?${s}` : '';
}

async function getJSON<T>(path: string, params: Params = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}${buildQuery(params)}`);
  if (!res.ok) throw new Error(`${path} -> HTTP ${res.status}`);
  return (await res.json()) as T;
}

export const fetchStatistics = (bbox?: Partial<BBox>) =>
  getJSON<Statistics>('/data/statistics', { ...bbox });

export const fetchSnapshot = (at: string, bbox?: Partial<BBox>, limit = 5000) =>
  getJSON<{ ships: ShipSnapshot[] }>('/analysis/snapshot', {
    at,
    limit,
    ...bbox,
  }).then((r) => r.ships ?? []);

export const fetchDensity = (
  bbox: BBox,
  gridSize: number,
  start?: string,
  end?: string,
) =>
  getJSON<{ density_data: DensityCell[] }>('/density/heatmap', {
    ...bbox,
    grid_size: gridSize,
    start,
    end,
  }).then((r) => r.density_data ?? []);

export const fetchSpeedCourse = (bbox: BBox, start?: string, end?: string) =>
  getJSON<SpeedCourseOut>('/analysis/speed-course', { ...bbox, start, end });

export const fetchSectionalFlow = (
  lon1: number,
  lat1: number,
  lon2: number,
  lat2: number,
  start?: string,
  end?: string,
) =>
  getJSON<SectionalFlowOut>('/analysis/sectional-flow', {
    lon1,
    lat1,
    lon2,
    lat2,
    start,
    end,
  });

export const fetchCorridors = (gridSize: number, start?: string, end?: string) =>
  getJSON<{ corridors: Corridor[] }>('/analysis/corridors', {
    grid_size: gridSize,
    start,
    end,
  }).then((r) => r.corridors ?? []);

export const fetchMultivariate = (
  n: number,
  bbox?: Partial<BBox>,
  start?: string,
  end?: string,
) =>
  getJSON<MultivariateOut>('/analysis/multivariate', {
    n,
    ...bbox,
    start,
    end,
  });

export const fetchOD = (topN: number, start?: string, end?: string) =>
  getJSON<{ od: ODItem[] }>('/analysis/od', { top_n: topN, start, end }).then(
    (r) => r.od ?? [],
  );

export const fetchEncounters = (
  start?: string,
  end?: string,
  bbox?: Partial<BBox>,
  opts: { dcpaNm?: number; lookaheadMin?: number; minDistanceNm?: number; limit?: number } = {},
) =>
  getJSON<EncountersOut>('/analysis/encounters', {
    start,
    end,
    ...bbox,
    dcpa_nm: opts.dcpaNm ?? 1.0,
    lookahead_min: opts.lookaheadMin ?? 30,
    min_distance_nm: opts.minDistanceNm ?? 0.1,
    limit: opts.limit ?? 500,
  });

export const fetchConflicts = (
  start?: string,
  end?: string,
  bbox?: Partial<BBox>,
  opts: { gridSize?: number; topN?: number; dcpaNm?: number; lookaheadMin?: number } = {},
) =>
  getJSON<ConflictsOut>('/analysis/conflicts', {
    start,
    end,
    ...bbox,
    grid_size: opts.gridSize ?? 40,
    top_n: opts.topN ?? 30,
    dcpa_nm: opts.dcpaNm ?? 1.0,
    lookahead_min: opts.lookaheadMin ?? 30,
  });

export const fetchDomainViolations = (
  start?: string,
  end?: string,
  bbox?: Partial<BBox>,
  opts: { model?: string; scale?: number; limit?: number } = {},
) =>
  getJSON<DomainOut>('/analysis/domain-violations', {
    start,
    end,
    ...bbox,
    model: opts.model ?? 'fujii',
    scale: opts.scale ?? 1.0,
    limit: opts.limit ?? 500,
  });

export const fetchRotStatistics = (
  start?: string,
  end?: string,
  bbox?: Partial<BBox>,
  opts: { windowMin?: number; maneuverRot?: number; steadyRot?: number } = {},
) =>
  getJSON<RotStatisticsOut>('/analysis/rot/statistics', {
    start,
    end,
    ...bbox,
    window_min: opts.windowMin ?? 15,
    maneuver_rot: opts.maneuverRot ?? 3.0,
    steady_rot: opts.steadyRot ?? 0.5,
  });

export const fetchRotByType = (
  start?: string,
  end?: string,
  bbox?: Partial<BBox>,
  opts: { windowMin?: number; maneuverRot?: number } = {},
) =>
  getJSON<RotByTypeOut>('/analysis/rot/by-type', {
    start,
    end,
    ...bbox,
    window_min: opts.windowMin ?? 15,
    maneuver_rot: opts.maneuverRot ?? 3.0,
  });

export const fetchRotGrid = (
  start?: string,
  end?: string,
  bbox?: Partial<BBox>,
  opts: { gridSize?: number; windowMin?: number; maneuverRot?: number } = {},
) =>
  getJSON<RotGridOut>('/analysis/rot/grid', {
    start,
    end,
    ...bbox,
    grid_size: opts.gridSize ?? 40,
    window_min: opts.windowMin ?? 15,
    maneuver_rot: opts.maneuverRot ?? 3.0,
  });

export const fetchRotDistribution = (
  start?: string,
  end?: string,
  bbox?: Partial<BBox>,
  opts: { windowMin?: number; bins?: number } = {},
) =>
  getJSON<RotDistributionOut>('/analysis/rot/distribution', {
    start,
    end,
    ...bbox,
    window_min: opts.windowMin ?? 15,
    bins: opts.bins ?? 24,
  });

export const fetchTrajectory = (
  mmsi: string,
  mode: 'raw' | 'simplified' | 'smoothed' = 'simplified',
  start?: string,
  end?: string,
) => {
  const suffix = mode === 'raw' ? '' : `/${mode}`;
  return getJSON<{ points: TrajectoryPoint[] } | TrajectoryPoint[]>(
    `/ships/${mmsi}/trajectories${suffix}`,
    { start, end },
  ).then((r) => (Array.isArray(r) ? r : r.points ?? []));
};

// 时间解析：后端返回 "YYYY-MM-DD HH:mm:ss"，统一转时间戳（毫秒）
export function parseTs(s: string): number {
  if (!s) return NaN;
  return new Date(s.replace(' ', 'T')).getTime();
}

export function formatTs(ms: number, withDate = true): string {
  const d = new Date(ms);
  const p = (n: number) => String(n).padStart(2, '0');
  const hm = `${p(d.getHours())}:${p(d.getMinutes())}`;
  return withDate
    ? `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${hm}`
    : hm;
}

export function toApiTime(ms: number): string {
  return formatTs(ms).replace('T', ' ');
}
