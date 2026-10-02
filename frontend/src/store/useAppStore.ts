'use client';
import { create } from 'zustand';
import type { BBox } from '@/lib/api';

export const STUDY_AREA: BBox = {
  min_lon: 121.4,
  min_lat: 29.7,
  max_lon: 123.2,
  max_lat: 31.5,
};

export type TrajMode = 'raw' | 'simplified' | 'smoothed';

export interface LayerFlags {
  density: boolean;
  ships: boolean;
  corridors: boolean;
  od: boolean;
  trajectory: boolean;
  encounters: boolean;
  conflicts: boolean;
  domain: boolean;
  rot: boolean;
}

export type DomainModel = 'fujii' | 'goodwin';

interface AppState {
  // 时间
  timeMin: number;
  timeMax: number;
  cursor: number; // 当前时间窗起点（ms）
  windowMinutes: number;
  playing: boolean;
  speed: number; // 播放倍速
  stepMinutes: number;

  // 空间与筛选
  bbox: BBox;
  viewportBbox: BBox | null;
  filterByViewport: boolean;
  shipTypes: string[];
  /** 用户手绘的框选区域，优先级高于视野筛选。 */
  drawnBbox: BBox | null;
  drawMode: boolean;

  // 图层与选中
  layers: LayerFlags;
  selectedShip: string | null;
  trajMode: TrajMode;
  gridSize: number;
  section: { lon1: number; lat1: number; lon2: number; lat2: number };

  // L2 船舶交互层参数
  encDcpaNm: number; // 会遇判据：最近会遇距离阈值（海里）
  domainModel: DomainModel; // 船舶领域模型
  domainScale: number; // 领域尺度缩放
  rotWindowMin: number; // 转向率聚合窗口（分钟），0 = 逐点差分
  rotManeuver: number; // 机动判定阈值（°/min）

  // actions
  setTimeRange: (min: number, max: number) => void;
  setCursor: (ms: number) => void;
  advance: (minutes: number) => void;
  setWindowMinutes: (m: number) => void;
  togglePlay: () => void;
  setSpeed: (s: number) => void;
  setStepMinutes: (m: number) => void;
  setViewportBbox: (b: BBox) => void;
  setFilterByViewport: (v: boolean) => void;
  setDrawnBbox: (b: BBox | null) => void;
  setDrawMode: (v: boolean) => void;
  toggleShipType: (t: string) => void;
  toggleLayer: (k: keyof LayerFlags) => void;
  selectShip: (mmsi: string | null) => void;
  setTrajMode: (m: TrajMode) => void;
  setGridSize: (n: number) => void;
  setSection: (s: AppState['section']) => void;
  setEncDcpaNm: (v: number) => void;
  setDomainModel: (m: DomainModel) => void;
  setDomainScale: (v: number) => void;
  setRotWindowMin: (v: number) => void;
  setRotManeuver: (v: number) => void;
}

const DEFAULT_SECTION = { lon1: 122.0, lat1: 30.8, lon2: 123.0, lat2: 30.8 };

/** 生效范围优先级：手绘框选 > 当前视野 > 研究区全域。 */
function effectiveBbox(s: {
  drawnBbox: BBox | null;
  filterByViewport: boolean;
  viewportBbox: BBox | null;
}): BBox {
  if (s.drawnBbox) return s.drawnBbox;
  if (s.filterByViewport) return s.viewportBbox ?? STUDY_AREA;
  return STUDY_AREA;
}

export const useAppStore = create<AppState>((set, get) => ({
  timeMin: 0,
  timeMax: 0,
  cursor: 0,
  windowMinutes: 360,
  playing: false,
  speed: 1,
  stepMinutes: 30,

  bbox: STUDY_AREA,
  viewportBbox: null,
  filterByViewport: false,
  shipTypes: [],
  drawnBbox: null,
  drawMode: false,

  layers: {
    density: true,
    ships: true,
    corridors: false,
    od: false,
    trajectory: true,
    encounters: false,
    conflicts: false,
    domain: false,
    rot: false,
  },
  selectedShip: null,
  trajMode: 'simplified',
  gridSize: 60,
  section: DEFAULT_SECTION,
  encDcpaNm: 1.0,
  domainModel: 'fujii',
  domainScale: 1.0,
  rotWindowMin: 15,
  rotManeuver: 3.0,

  setTimeRange: (min, max) =>
    set({ timeMin: min, timeMax: max, cursor: get().cursor || min }),
  setCursor: (ms) => {
    const { timeMin, timeMax, windowMinutes } = get();
    const maxStart = Math.max(timeMin, timeMax - windowMinutes * 60_000);
    set({ cursor: Math.min(Math.max(ms, timeMin), maxStart) });
  },
  advance: (minutes) => {
    const { cursor, timeMin, timeMax, windowMinutes } = get();
    const maxStart = Math.max(timeMin, timeMax - windowMinutes * 60_000);
    let next = cursor + minutes * 60_000;
    if (next > maxStart) next = timeMin; // 到末尾回到起点
    set({ cursor: next });
  },
  setWindowMinutes: (m) => set({ windowMinutes: m }),
  togglePlay: () => set((s) => ({ playing: !s.playing })),
  setSpeed: (s) => set({ speed: s }),
  setStepMinutes: (m) => set({ stepMinutes: m }),

  setViewportBbox: (b) =>
    set((s) => {
      const next = { ...s, viewportBbox: b };
      return { viewportBbox: b, bbox: effectiveBbox(next) };
    }),
  setFilterByViewport: (v) =>
    set((s) => {
      const next = { ...s, filterByViewport: v };
      return { filterByViewport: v, bbox: effectiveBbox(next) };
    }),
  setDrawnBbox: (b) =>
    set((s) => {
      const next = { ...s, drawnBbox: b };
      return { drawnBbox: b, bbox: effectiveBbox(next) };
    }),
  setDrawMode: (v) => set({ drawMode: v }),
  toggleShipType: (t) =>
    set((s) => ({
      shipTypes: s.shipTypes.includes(t)
        ? s.shipTypes.filter((x) => x !== t)
        : [...s.shipTypes, t],
    })),

  toggleLayer: (k) => set((s) => ({ layers: { ...s.layers, [k]: !s.layers[k] } })),
  selectShip: (mmsi) => set({ selectedShip: mmsi }),
  setTrajMode: (m) => set({ trajMode: m }),
  setGridSize: (n) => set({ gridSize: n }),
  setSection: (sec) => set({ section: sec }),
  setEncDcpaNm: (v) => set({ encDcpaNm: v }),
  setDomainModel: (m) => set({ domainModel: m }),
  setDomainScale: (v) => set({ domainScale: v }),
  setRotWindowMin: (v) => set({ rotWindowMin: v }),
  setRotManeuver: (v) => set({ rotManeuver: v }),
}));

// 派生：当前分析时间窗
export function useTimeWindow() {
  const { cursor, windowMinutes } = useAppStore();
  return { start: cursor, end: cursor + windowMinutes * 60_000 };
}
