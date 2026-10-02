import {
  ScatterplotLayer,
  GridCellLayer,
  PathLayer,
  ArcLayer,
  LineLayer,
  PolygonLayer,
} from '@deck.gl/layers';
import type {
  BBox,
  DensityCell,
  ShipSnapshot,
  TrajectoryPoint,
  Corridor,
  ODItem,
  EncounterItem,
  ConflictCell,
  DomainViolation,
  RotGridOut,
} from '@/lib/api';

export type RGB = [number, number, number];

export const SHIP_TYPE_COLORS: Record<string, RGB> = {
  散货: [37, 99, 235],
  集装箱: [217, 119, 6],
  油轮: [220, 38, 38],
  渔船: [5, 150, 105],
  客船: [124, 58, 237],
  其他: [107, 114, 128],
};

export function shipColor(t?: string): RGB {
  return SHIP_TYPE_COLORS[t ?? '其他'] ?? SHIP_TYPE_COLORS['其他'];
}

/** COLREGs 会遇局面配色：对遇最危险（红）、交叉次之（紫）、追越（橙）。 */
export const SITUATION_COLORS: Record<string, RGB> = {
  对遇: [220, 38, 38],
  交叉: [124, 58, 237],
  追越: [245, 158, 11],
};

export function situationColor(s?: string): RGB {
  return SITUATION_COLORS[s ?? ''] ?? [107, 114, 128];
}

/** 领域侵犯配色：侵入越深越红（penetration_ratio 0→1）。 */
export function penetrationColor(ratio: number): [number, number, number, number] {
  const t = Math.min(1, Math.max(0, ratio));
  return [255, Math.round(210 - 180 * t), Math.round(110 - 85 * t), 235];
}

/** 转向强度配色：机动率由低到高映射为青 → 红（越高说明越频繁操舵）。 */
export function rotColor(ratio: number): RGB {
  const t = Math.min(1, Math.max(0, ratio));
  return [
    Math.round(46 + 205 * t),
    Math.round(180 - 150 * t),
    Math.round(170 - 130 * t),
  ];
}

/** 密度色带：浅黄 → 橙 → 深红（0..max 线性插值）。 */
const RAMP: RGB[] = [
  [255, 255, 204],
  [255, 222, 145],
  [253, 180, 98],
  [247, 132, 60],
  [215, 48, 39],
];

export function densityColor(value: number, max: number): RGB {
  const t = max > 0 ? Math.min(1, Math.max(0, value / max)) : 0;
  const seg = (RAMP.length - 1) * t;
  const i = Math.min(RAMP.length - 2, Math.floor(seg));
  const f = seg - i;
  const a = RAMP[i];
  const b = RAMP[i + 1];
  return [
    Math.round(a[0] + (b[0] - a[0]) * f),
    Math.round(a[1] + (b[1] - a[1]) * f),
    Math.round(a[2] + (b[2] - a[2]) * f),
  ];
}

const M_PER_DEG_LAT = 111_320;

function cellMeters(bbox: BBox, gridSize: number) {
  const dLon = (bbox.max_lon - bbox.min_lon) / gridSize;
  const dLat = (bbox.max_lat - bbox.min_lat) / gridSize;
  const midLat = (bbox.max_lat + bbox.min_lat) / 2;
  return {
    width: dLon * M_PER_DEG_LAT * Math.cos((midLat * Math.PI) / 180),
    height: dLat * M_PER_DEG_LAT,
  };
}

export interface LayerInput {
  bbox: BBox;
  gridSize: number;
  density: DensityCell[];
  ships: ShipSnapshot[];
  shipTypes: string[];
  trajectory: TrajectoryPoint[];
  corridors: Corridor[];
  od: ODItem[];
  encounters: EncounterItem[];
  conflicts: ConflictCell[];
  conflictsGridSize: number;
  domainViolations: DomainViolation[];
  rotCells: RotGridOut['cells'];
  rotGridSize: number;
  drawnBbox: BBox | null;
  flags: Record<string, boolean>;
  section: { lon1: number; lat1: number; lon2: number; lat2: number };
  onSelectShip: (mmsi: string) => void;
}

export function buildLayers(inp: LayerInput) {
  const layers = [];
  const { width: cw, height: ch } = cellMeters(inp.bbox, inp.gridSize);
  const maxDensity = inp.density.reduce((m, d) => Math.max(m, d.density), 0);

  if (inp.flags.density && inp.density.length) {
    layers.push(
      new GridCellLayer<DensityCell>({
        id: 'density',
        data: inp.density,
        getPosition: (d: DensityCell) => [d.longitude, d.latitude],
        getFillColor: (d: DensityCell) => densityColor(d.density, maxDensity),
        getElevation: (d: DensityCell) =>
          maxDensity > 0 ? (d.density / maxDensity) * 4000 : 0,
        extruded: true,
        elevationScale: 1,
        cellSize: Math.max(cw, ch),
        coverage: 0.92,
        opacity: 0.55,
        pickable: true,
        material: { ambient: 1, diffuse: 1, shininess: 0, specularColor: [60, 64, 70] },
      }),
    );
  }

  // 会遇热点网格：网格边长由后端 grid_size 在当前生效 bbox 上换算得到。
  // 必须用 inp.bbox（而非研究区全域）—— 框选/视野筛选后后端也按同一 bbox 划分网格，
  // 若此处仍按全域计算，格子会被画大，与实际聚合范围错位。
  if (inp.flags.conflicts && inp.conflicts.length) {
    const g = inp.conflictsGridSize || 40;
    const hot = cellMeters(inp.bbox, g);
    const maxCount = inp.conflicts.reduce((m, c) => Math.max(m, c.count), 0) || 1;
    const maxSevere = inp.conflicts.reduce((m, c) => Math.max(m, c.severe_count), 0) || 1;
    layers.push(
      new GridCellLayer<ConflictCell>({
        id: 'conflicts',
        data: inp.conflicts,
        getPosition: (d: ConflictCell) => [d.longitude, d.latitude],
        getFillColor: (d: ConflictCell) => densityColor(d.severe_count, maxSevere),
        getElevation: (d: ConflictCell) => (d.count / maxCount) * 4000,
        extruded: true,
        elevationScale: 1,
        cellSize: Math.max(hot.width, hot.height),
        coverage: 0.9,
        opacity: 0.6,
        pickable: true,
        material: { ambient: 1, diffuse: 1, shininess: 0, specularColor: [60, 64, 70] },
      }),
    );
  }

  // 转向强度网格：高度=样本量、颜色=机动率，用于定位弯道与交汇水域。
  if (inp.flags.rot && inp.rotCells.length) {
    const rc = cellMeters(inp.bbox, inp.rotGridSize || 40);
    const maxSamples = inp.rotCells.reduce((m, c) => Math.max(m, c.samples), 0) || 1;
    layers.push(
      new GridCellLayer<RotGridOut['cells'][number]>({
        id: 'rot',
        data: inp.rotCells,
        getPosition: (d: RotGridOut['cells'][number]) => [d.lon, d.lat],
        getFillColor: (d: RotGridOut['cells'][number]) => rotColor(d.maneuver_ratio),
        getElevation: (d: RotGridOut['cells'][number]) => (d.samples / maxSamples) * 4000,
        extruded: true,
        elevationScale: 1,
        cellSize: Math.max(rc.width, rc.height),
        coverage: 0.85,
        opacity: 0.55,
        pickable: true,
        material: { ambient: 1, diffuse: 1, shininess: 0, specularColor: [60, 64, 70] },
      }),
    );
  }

  if (inp.flags.corridors && inp.corridors.length) {
    const cells = inp.corridors.flatMap((c) =>
      c.centers.map((p) => ({ ...p, cell_count: c.cell_count })),
    );
    layers.push(
      new GridCellLayer({
        id: 'corridors',
        data: cells,
        getPosition: (d: { longitude: number; latitude: number }) => [
          d.longitude,
          d.latitude,
        ],
        getFillColor: [124, 58, 237, 90],
        cellSize: Math.max(cw, ch),
        coverage: 0.95,
        extruded: false,
        pickable: false,
      }),
    );
  }

  if (inp.flags.od && inp.od.length) {
    const maxCount = inp.od.reduce((m, o) => Math.max(m, o.count), 0) || 1;
    layers.push(
      new ArcLayer<ODItem>({
        id: 'od',
        data: inp.od,
        getSourcePosition: (d: ODItem) => [d.origin.longitude, d.origin.latitude],
        getTargetPosition: (d: ODItem) => [d.destination.longitude, d.destination.latitude],
        getSourceColor: [249, 115, 22, 200],
        getTargetColor: [234, 88, 12, 220],
        getWidth: (d: ODItem) => 1 + (d.count / maxCount) * 4,
        getHeight: 0.35,
        pickable: true,
      }),
    );
  }

  if (inp.flags.trajectory && inp.trajectory.length > 1) {
    layers.push(
      new PathLayer({
        id: 'trajectory',
        data: [{ path: inp.trajectory.map((p) => [p.longitude, p.latitude]) }],
        getPath: (d: { path: [number, number][] }) => d.path,
        getColor: [2, 132, 199],
        widthMinPixels: 2.5,
        capRounded: true,
        jointRounded: true,
      }),
    );
  }

  if (inp.flags.ships && inp.ships.length) {
    const filtered = inp.shipTypes.length
      ? inp.ships.filter((s) => inp.shipTypes.includes(s.ship_type ?? '其他'))
      : inp.ships;
    layers.push(
      new ScatterplotLayer<ShipSnapshot>({
        id: 'ships',
        data: filtered,
        getPosition: (d: ShipSnapshot) => [d.longitude, d.latitude],
        getFillColor: (d: ShipSnapshot) => shipColor(d.ship_type),
        getRadius: 260,
        radiusUnits: 'meters',
        radiusMinPixels: 3,
        radiusMaxPixels: 9,
        stroked: true,
        getLineColor: [255, 255, 255],
        getLineWidth: 1,
        lineWidthUnits: 'pixels',
        pickable: true,
        onClick: ({ object }: { object?: ShipSnapshot }) => {
          if (object?.mmsi) inp.onSelectShip(object.mmsi);
          return true;
        },
      }),
    );
  }

  // 会遇事件点：按 COLREGs 局面着色
  if (inp.flags.encounters && inp.encounters.length) {
    layers.push(
      new ScatterplotLayer<EncounterItem>({
        id: 'encounters',
        data: inp.encounters,
        getPosition: (d: EncounterItem) => [d.longitude, d.latitude],
        getFillColor: (d: EncounterItem) => situationColor(d.situation),
        getRadius: 300,
        radiusUnits: 'meters',
        radiusMinPixels: 3,
        radiusMaxPixels: 10,
        stroked: true,
        getLineColor: [255, 255, 255],
        getLineWidth: 1,
        lineWidthUnits: 'pixels',
        pickable: true,
      }),
    );
  }

  // 船舶领域侵犯点：半径与颜色均反映侵入深度
  if (inp.flags.domain && inp.domainViolations.length) {
    layers.push(
      new ScatterplotLayer<DomainViolation>({
        id: 'domain',
        data: inp.domainViolations,
        getPosition: (d: DomainViolation) => [d.longitude, d.latitude],
        getFillColor: (d: DomainViolation) => penetrationColor(d.penetration_ratio),
        getRadius: (d: DomainViolation) => 200 + d.penetration_ratio * 700,
        radiusUnits: 'meters',
        radiusMinPixels: 4,
        radiusMaxPixels: 14,
        stroked: true,
        getLineColor: [127, 29, 29],
        getLineWidth: 1,
        lineWidthUnits: 'pixels',
        pickable: true,
      }),
    );
  }

  // 用户手绘的框选分析区域（优先级高于视野筛选）
  if (inp.drawnBbox) {
    const b = inp.drawnBbox;
    layers.push(
      new PolygonLayer({
        id: 'drawn-bbox',
        data: [{ id: 'sel' }],
        getPolygon: () => [
          [b.min_lon, b.min_lat],
          [b.max_lon, b.min_lat],
          [b.max_lon, b.max_lat],
          [b.min_lon, b.max_lat],
        ],
        filled: true,
        stroked: true,
        getFillColor: [15, 118, 110, 28],
        getLineColor: [15, 118, 110],
        getLineWidth: 2,
        lineWidthUnits: 'pixels',
        pickable: false,
      }),
    );
  }

  // 断面线（始终显示，便于对照断面流量统计）
  layers.push(
    new LineLayer({
      id: 'section',
      data: [inp.section],
      getSourcePosition: (d: { lon1: number; lat1: number }) => [d.lon1, d.lat1],
      getTargetPosition: (d: { lon2: number; lat2: number }) => [d.lon2, d.lat2],
      getColor: [17, 24, 39],
      getWidth: 2,
      widthUnits: 'pixels',
    }),
  );

  return layers;
}
