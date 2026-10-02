'use client';
import { useAppStore } from '@/store/useAppStore';
import { SHIP_TYPE_COLORS } from '@/components/map/layers';
import type { LayerFlags, TrajMode } from '@/store/useAppStore';

// 单一真值源：图层键直接取自 store 的 LayerFlags，避免两处硬编码不一致
// （新增图层只改 store 一处，漏改会在这里变成类型错误而不是静默失效）
type LayerKey = keyof LayerFlags;

const LAYER_LABELS: { key: LayerKey; label: string }[] = [
  { key: 'density', label: '密度网格' },
  { key: 'ships', label: '船舶位置' },
  { key: 'corridors', label: '主航线' },
  { key: 'od', label: 'OD 流量' },
  { key: 'trajectory', label: '选中轨迹' },
];

/** 交互层：开启后才会向后端请求对应分析（计算成本高于普通聚合）。 */
const INTERACTION_LAYERS: { key: LayerKey; label: string }[] = [
  { key: 'encounters', label: '会遇点' },
  { key: 'conflicts', label: '冲突热点' },
  { key: 'domain', label: '领域侵犯' },
  { key: 'rot', label: '转向强度' },
];

const TRAJ_MODES: { key: TrajMode; label: string }[] = [
  { key: 'raw', label: '原始' },
  { key: 'simplified', label: '抽稀' },
  { key: 'smoothed', label: '平滑' },
];

export default function FilterPanel({
  shipTypeStats,
}: {
  shipTypeStats: Record<string, number>;
}) {
  const layers = useAppStore((s) => s.layers);
  const toggleLayer = useAppStore((s) => s.toggleLayer);
  const shipTypes = useAppStore((s) => s.shipTypes);
  const toggleShipType = useAppStore((s) => s.toggleShipType);
  const gridSize = useAppStore((s) => s.gridSize);
  const setGridSize = useAppStore((s) => s.setGridSize);
  const filterByViewport = useAppStore((s) => s.filterByViewport);
  const setFilterByViewport = useAppStore((s) => s.setFilterByViewport);
  const trajMode = useAppStore((s) => s.trajMode);
  const setTrajMode = useAppStore((s) => s.setTrajMode);
  const drawMode = useAppStore((s) => s.drawMode);
  const setDrawMode = useAppStore((s) => s.setDrawMode);
  const drawnBbox = useAppStore((s) => s.drawnBbox);
  const setDrawnBbox = useAppStore((s) => s.setDrawnBbox);

  const types = Object.keys(shipTypeStats).filter(Boolean);

  return (
    <div className="card">
      <div className="card-title">图层与筛选</div>

      <div className="check-group">
        {LAYER_LABELS.map((l) => (
          <label key={l.key} className="check-item">
            <input
              type="checkbox"
              checked={layers[l.key]}
              onChange={() => toggleLayer(l.key)}
            />
            <span>{l.label}</span>
          </label>
        ))}
      </div>

      <div className="divider" />

      <div className="field-title">船舶交互层（L2）</div>
      <div className="check-group">
        {INTERACTION_LAYERS.map((l) => (
          <label key={l.key} className="check-item">
            <input
              type="checkbox"
              checked={layers[l.key]}
              onChange={() => toggleLayer(l.key)}
            />
            <span>{l.label}</span>
          </label>
        ))}
      </div>
      <div className="muted text-xs mt-6">
        开启即在当前时间窗内计算，可在「船舶交互」面板调节判据
      </div>

      <div className="divider" />

      <div className="field-title">船舶类型（不选 = 全部）</div>
      <div className="check-group">
        {types.map((t) => (
          <label key={t} className="check-item">
            <input
              type="checkbox"
              checked={shipTypes.includes(t)}
              onChange={() => toggleShipType(t)}
            />
            <span
              className="dot"
              style={{ background: `rgb(${(SHIP_TYPE_COLORS[t] ?? SHIP_TYPE_COLORS['其他']).join(',')})` }}
            />
            <span>{t}</span>
            <span className="muted text-xs">{shipTypeStats[t]}</span>
          </label>
        ))}
        {!types.length && <div className="muted text-xs">加载中…</div>}
      </div>

      <div className="divider" />

      <label className="field">
        <span>密度网格精度</span>
        <input
          className="slider"
          type="range"
          min={20}
          max={120}
          step={10}
          value={gridSize}
          onChange={(e) => setGridSize(Number(e.target.value))}
        />
        <span className="muted text-xs">{gridSize} × {gridSize}</span>
      </label>

      <div className="field-title">分析区域</div>
      <div className="seg-group">
        <button
          className={`seg-btn ${drawMode ? 'seg-active' : ''}`}
          onClick={() => setDrawMode(!drawMode)}
        >
          {drawMode ? '绘制中（再点取消）' : '框选绘制'}
        </button>
        <button
          className="seg-btn"
          onClick={() => {
            setDrawnBbox(null);
            setDrawMode(false);
          }}
          disabled={!drawnBbox}
        >
          清除选区
        </button>
      </div>
      {drawnBbox ? (
        <div className="muted text-xs mt-6">
          手绘选区 {drawnBbox.min_lon.toFixed(2)}°E,{drawnBbox.min_lat.toFixed(2)}°N →{' '}
          {drawnBbox.max_lon.toFixed(2)}°E,{drawnBbox.max_lat.toFixed(2)}°N（优先于视野筛选）
        </div>
      ) : (
        <div className="muted text-xs mt-6">未设置选区，默认使用研究区全域</div>
      )}

      <label className="check-item mt-6">
        <input
          type="checkbox"
          checked={filterByViewport}
          onChange={(e) => setFilterByViewport(e.target.checked)}
        />
        <span>仅统计当前视野范围</span>
      </label>

      <div className="divider" />

      <div className="field-title">轨迹处理</div>
      <div className="seg-group">
        {TRAJ_MODES.map((m) => (
          <button
            key={m.key}
            className={`seg-btn ${trajMode === m.key ? 'seg-active' : ''}`}
            onClick={() => setTrajMode(m.key)}
          >
            {m.label}
          </button>
        ))}
      </div>
    </div>
  );
}
