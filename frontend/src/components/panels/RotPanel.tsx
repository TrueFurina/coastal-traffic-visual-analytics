'use client';
import { BarChart } from '@/components/charts/MiniCharts';
import { useRotByType, useRotDistribution, useRotStatistics } from '@/hooks/useData';
import { useAppStore } from '@/store/useAppStore';

/** 聚合窗口选项：0 表示逐点差分（噪声最大，仅作对照）。 */
const WINDOW_OPTIONS = [
  { v: 0, label: '逐点' },
  { v: 5, label: '5min' },
  { v: 15, label: '15min' },
  { v: 30, label: '30min' },
];

/** 要展示的指标（后端返回 11 项，面板只呈现判读所需的 8 项）。 */
const SHOWN = [
  'rot_sample_count',
  'mean_abs_rot',
  'rot_p95',
  'maneuver_ratio',
  'turn_left_ratio',
  'turn_right_ratio',
  'steady_ratio',
  'mean_rot_signed',
];

const TYPE_COLORS: Record<string, string> = {
  散货: '#2563eb',
  集装箱: '#7c3aed',
  油轮: '#b45309',
  渔船: '#0f766e',
  客船: '#be123c',
};

export default function RotPanel() {
  const windowMin = useAppStore((s) => s.rotWindowMin);
  const setWindowMin = useAppStore((s) => s.setRotWindowMin);
  const maneuver = useAppStore((s) => s.rotManeuver);
  const setManeuver = useAppStore((s) => s.setRotManeuver);

  // 面板打开即请求；三个接口都已在 store 里按当前时间窗与框选区域传参
  const stats = useRotStatistics(true);
  const dist = useRotDistribution(true);
  const byType = useRotByType(true);

  const d = stats.data;
  const shown = (d?.indicators ?? []).filter((i) => SHOWN.includes(i.key));
  const bins = (dist.data?.bins ?? []).map((b) => ({
    label: `${b.from}~${b.to}`,
    value: b.count,
  }));
  const typeRows = (byType.data?.rows ?? []).map((r) => ({
    label: r.ship_type,
    value: Number(r.mean_abs_rot.toFixed(2)),
    color: TYPE_COLORS[r.ship_type] ?? '#64748b',
  }));

  return (
    <div>
      <div className="field-title">聚合窗口（决定数值口径）</div>
      <div className="seg-group">
        {WINDOW_OPTIONS.map((o) => (
          <button
            key={o.v}
            className={`seg-btn ${windowMin === o.v ? 'seg-active' : ''}`}
            onClick={() => setWindowMin(o.v)}
          >
            {o.label}
          </button>
        ))}
      </div>

      <div className="field-title mt-6">机动判定阈值 |ROT| ≥ {maneuver.toFixed(1)} °/min</div>
      <input
        className="slider"
        type="range"
        min={0.5}
        max={10}
        step={0.5}
        value={maneuver}
        onChange={(e) => setManeuver(Number(e.target.value))}
      />

      {d?.diagnostics && (
        <div className="muted text-xs mt-6">
          口径 {d.diagnostics.scale}
          {d.diagnostics.noise_amplification
            ? ` · 逐点口径约为其 ${d.diagnostics.noise_amplification.toFixed(1)} 倍（位置噪声放大，仅作对照）`
            : ''}
        </div>
      )}

      {stats.loading && <div className="muted text-xs mt-6">计算中…</div>}
      {stats.error && <div className="muted text-xs mt-6">加载失败：{stats.error}</div>}

      <div className="stat-grid mt-6">
        {shown.map((i) => (
          <div className="stat" key={i.key} title={i.desc}>
            <span>{i.name}</span>
            <b>
              {i.value}
              <span className="text-xs muted"> {i.unit}</span>
            </b>
          </div>
        ))}
      </div>

      <div className="divider" />

      <div className="field-title">|ROT| 分布（°/min）</div>
      {bins.length ? (
        <BarChart items={bins} color="#0891b2" height={170} />
      ) : (
        <div className="muted text-xs">暂无数据</div>
      )}

      <div className="divider" />

      <div className="field-title">分船型平均 |ROT|（°/min）</div>
      {typeRows.length ? (
        <BarChart items={typeRows} height={140} />
      ) : (
        <div className="muted text-xs">暂无数据</div>
      )}

      <div className="muted text-xs mt-6">
        口径说明：航向角变化率由同船相邻/同窗观测的航向差折算，已做 360° 环绕折叠。
        本数据集航向由带噪声的位置反算，逐点差分受噪声主导，故默认采用 15 分钟窗口口径。
      </div>
    </div>
  );
}
