'use client';
import { useAppStore } from '@/store/useAppStore';
import type { DomainModel } from '@/store/useAppStore';
import { useConflicts, useDomainViolations, useEncounters } from '@/hooks/useData';
import { BarChart } from '@/components/charts/MiniCharts';
import { SITUATION_COLORS } from '@/components/map/layers';
import type { BarItem } from '@/components/charts/MiniCharts';
import type { DomainViolation } from '@/lib/api';

const SITUATION_ORDER = ['对遇', '交叉', '追越'];

const DOMAIN_MODELS: { key: DomainModel; label: string }[] = [
  { key: 'fujii', label: '藤井（随船长）' },
  { key: 'goodwin', label: 'Goodwin（固定）' },
];

function rgbCss(c: [number, number, number]) {
  return `rgb(${c.join(',')})`;
}

/** 船头间距分档（nm）：按绝对值统计，负值表示目标位于本船船尾方向。 */
const HEADWAY_BINS: { label: string; lo: number; hi: number }[] = [
  { label: '< 0.05', lo: 0, hi: 0.05 },
  { label: '0.05–0.1', lo: 0.05, hi: 0.1 },
  { label: '0.1–0.2', lo: 0.1, hi: 0.2 },
  { label: '0.2–0.5', lo: 0.2, hi: 0.5 },
  { label: '≥ 0.5', lo: 0.5, hi: Infinity },
];

function headwayHist(violations: DomainViolation[]): BarItem[] {
  return HEADWAY_BINS.map((b) => ({
    label: b.label,
    value: violations.filter((v) => {
      const a = Math.abs(v.along_nm ?? 0);
      return a >= b.lo && a < b.hi;
    }).length,
  }));
}

function Loading({ on }: { on?: boolean }) {
  return on ? <div className="muted text-xs">计算中…</div> : null;
}

export default function InteractionPanel() {
  const encDcpaNm = useAppStore((s) => s.encDcpaNm);
  const setEncDcpaNm = useAppStore((s) => s.setEncDcpaNm);
  const domainModel = useAppStore((s) => s.domainModel);
  const setDomainModel = useAppStore((s) => s.setDomainModel);
  const domainScale = useAppStore((s) => s.domainScale);
  const setDomainScale = useAppStore((s) => s.setDomainScale);

  const encounters = useEncounters(true);
  const conflicts = useConflicts(true);
  const domain = useDomainViolations(true);

  const enc = encounters.data;
  const conf = conflicts.data;
  const dom = domain.data;

  const situationItems: BarItem[] = SITUATION_ORDER.map((s) => ({
    label: s,
    value: enc?.situation_stats?.[s] ?? 0,
    color: rgbCss(SITUATION_COLORS[s] ?? [107, 114, 128]),
  }));

  const worstPenetration = dom?.violations?.length
    ? dom.violations.reduce((m, v) => Math.max(m, v.penetration_ratio), 0)
    : 0;

  return (
    <div>
      <div className="field-title">判据参数</div>
      <label className="field">
        <span>会遇判据 DCPA 阈值</span>
        <input
          className="slider"
          type="range"
          min={0.2}
          max={3}
          step={0.1}
          value={encDcpaNm}
          onChange={(e) => setEncDcpaNm(Number(e.target.value))}
        />
        <span className="muted text-xs">{encDcpaNm.toFixed(1)} nm</span>
      </label>

      <div className="field-title mt-8">船舶领域模型</div>
      <div className="seg-group">
        {DOMAIN_MODELS.map((m) => (
          <button
            key={m.key}
            className={`seg-btn ${domainModel === m.key ? 'seg-active' : ''}`}
            onClick={() => setDomainModel(m.key)}
          >
            {m.label}
          </button>
        ))}
      </div>
      <label className="field mt-6">
        <span>领域尺度缩放</span>
        <input
          className="slider"
          type="range"
          min={0.5}
          max={2}
          step={0.1}
          value={domainScale}
          onChange={(e) => setDomainScale(Number(e.target.value))}
        />
        <span className="muted text-xs">×{domainScale.toFixed(1)}</span>
      </label>

      <div className="divider" />

      <div className="field-title">会遇检测（COLREGs 局面判定）</div>
      <Loading on={encounters.loading} />
      {encounters.error && <div className="muted text-xs">加载失败：{encounters.error}</div>}
      {enc && (
        <>
          <div className="stat-grid">
            <div className="stat">
              <span>会遇事件</span>
              <b>{enc.count.toLocaleString()}</b>
            </div>
            <div className="stat">
              <span>已返回</span>
              <b>{enc.returned.toLocaleString()}</b>
            </div>
            <div className="stat">
              <span>重叠剔除</span>
              <b>{enc.diagnostics?.degenerate_overlap_excluded ?? 0}</b>
            </div>
          </div>
          <div className="field-title mt-8">局面构成</div>
          <BarChart items={situationItems} height={96} />
          {enc.diagnostics?.note && (
            <div className="muted text-xs mt-6">{enc.diagnostics.note}</div>
          )}
        </>
      )}

      <div className="divider" />

      <div className="field-title">冲突热点（网格聚合 Top10）</div>
      <Loading on={conflicts.loading} />
      {conflicts.error && <div className="muted text-xs">加载失败：{conflicts.error}</div>}
      {conf && (
        <>
          <div className="muted text-xs">
            共 {conf.count} 个热点网格，覆盖 {conf.total_encounters.toLocaleString()} 起会遇
          </div>
          <BarChart
            items={conf.cells.slice(0, 10).map((c) => ({
              label: `${c.latitude.toFixed(2)},${c.longitude.toFixed(2)}`,
              value: c.count,
            }))}
            color="#dc2626"
            height={190}
          />
        </>
      )}

      <div className="divider" />

      <div className="field-title">船舶领域侵犯</div>
      <Loading on={domain.loading} />
      {domain.error && <div className="muted text-xs">加载失败：{domain.error}</div>}
      {dom && (
        <>
          <div className="stat-grid">
            <div className="stat">
              <span>侵犯事件</span>
              <b>{dom.count.toLocaleString()}</b>
            </div>
            <div className="stat">
              <span>最深侵入</span>
              <b>{(worstPenetration * 100).toFixed(0)}%</b>
            </div>
            <div className="stat">
              <span>重叠样本</span>
              <b>{Number(dom.diagnostics?.['overlap_lt_0.05nm'] ?? 0)}</b>
            </div>
          </div>

          <div className="field-title mt-8">船头间距分布（nm）</div>
          <BarChart items={headwayHist(dom.violations)} color="#ea580c" height={150} />
          <div className="muted text-xs mt-6">
            按 |along_nm| 分档；负值表示目标位于本船船尾方向
          </div>

          <div className="field-title mt-8">侵犯次数最多的船舶 Top10</div>
          <BarChart
            items={(dom.most_violated_ships ?? []).map((s) => ({
              label: s.mmsi,
              value: s.count,
            }))}
            color="#7c3aed"
            height={190}
          />
          {dom.diagnostics?.note && (
            <div className="muted text-xs mt-6">{dom.diagnostics.note}</div>
          )}
        </>
      )}

      <div className="muted text-xs mt-8">
        在左侧「图层与筛选」中开启「会遇点」「冲突热点」「领域侵犯」可在地图上叠加显示
      </div>
    </div>
  );
}
