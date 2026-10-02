'use client';
import { useState } from 'react';
import { useAppStore } from '@/store/useAppStore';
import {
  useCorridors,
  useMultivariate,
  useOD,
  useSectionalFlow,
  useSpeedCourse,
  useStatistics,
} from '@/hooks/useData';
import { BarChart, LineChart, RoseChart } from '@/components/charts/MiniCharts';
import ParallelCoords from '@/components/charts/ParallelCoords';
import InteractionPanel from '@/components/panels/InteractionPanel';
import RotPanel from '@/components/panels/RotPanel';

type TabKey =
  | 'overview'
  | 'speed'
  | 'section'
  | 'od'
  | 'corridor'
  | 'interaction'
  | 'rot'
  | 'parallel';

const TABS: { key: TabKey; label: string }[] = [
  { key: 'overview', label: '概览' },
  { key: 'speed', label: '航速航向' },
  { key: 'section', label: '断面流量' },
  { key: 'od', label: 'OD' },
  { key: 'corridor', label: '主航线' },
  { key: 'interaction', label: '船舶交互' },
  { key: 'rot', label: '航向变化' },
  { key: 'parallel', label: '平行坐标' },
];

function Loading({ on }: { on?: boolean }) {
  return on ? <div className="muted text-xs">计算中…</div> : null;
}

export default function AnalysisPanel() {
  const [tab, setTab] = useState<TabKey>('overview');
  const stats = useStatistics();
  const speed = useSpeedCourse();
  const section = useSectionalFlow();
  const od = useOD();
  const corridors = useCorridors();
  const multivariate = useMultivariate();
  const sectionDef = useAppStore((s) => s.section);
  const setSection = useAppStore((s) => s.setSection);

  const behavior = speed.data?.behavior;
  const totalBehavior = behavior
    ? behavior.anchored + behavior.maneuvering + behavior.underway || 1
    : 1;

  return (
    <div className="card card-flex">
      <div className="tabs">
        {TABS.map((t) => (
          <button
            key={t.key}
            className={`tab ${tab === t.key ? 'tab-active' : ''}`}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="tab-body">
        {tab === 'overview' && (
          <>
            <div className="stat-grid">
              <div className="stat">
                <span>船舶数</span>
                <b>{stats.data?.total_ships?.toLocaleString() ?? '—'}</b>
              </div>
              <div className="stat">
                <span>AIS 报文</span>
                <b>{stats.data?.total_trajectory_points?.toLocaleString() ?? '—'}</b>
              </div>
              <div className="stat">
                <span>单船均值</span>
                <b>
                  {stats.data ? `${Math.round(stats.data.average_points_per_ship)}` : '—'}
                </b>
              </div>
            </div>
            <div className="field-title">船舶行为构成</div>
            <Loading on={speed.loading} />
            {behavior && (
              <BarChart
                items={[
                  { label: '在航', value: behavior.underway },
                  { label: '机动/进出港', value: behavior.maneuvering },
                  { label: '锚泊', value: behavior.anchored },
                ]}
                color="#0f766e"
                height={96}
              />
            )}
            {behavior && (
              <div className="muted text-xs mt-6">
                在航占比 {((behavior.underway / totalBehavior) * 100).toFixed(1)}%
              </div>
            )}
            <div className="field-title mt-8">船型分布</div>
            {stats.data && (
              <BarChart
                items={Object.entries(stats.data.ship_type_distribution)
                  .filter(([k]) => k)
                  .map(([k, v]) => ({ label: k, value: v }))}
                color="#2563eb"
                height={150}
              />
            )}
          </>
        )}

        {tab === 'speed' && (
          <>
            <div className="field-title">航速分布（节）</div>
            <Loading on={speed.loading} />
            {speed.data && (
              <>
                <BarChart
                  items={speed.data.speed_hist.map((s) => ({
                    label: s.label,
                    value: s.count,
                  }))}
                  color="#2563eb"
                  height={190}
                />
                <div className="field-title mt-8">航向玫瑰图</div>
                <div className="rose-wrap">
                  <RoseChart
                    items={speed.data.course_hist.map((c) => ({
                      label: `${c.sector_deg}°`,
                      value: c.count,
                    }))}
                  />
                  <div className="muted text-xs">
                    样本 {speed.data.count.toLocaleString()} 条报文
                  </div>
                </div>
              </>
            )}
          </>
        )}

        {tab === 'section' && (
          <>
            <div className="field-title">断面定义</div>
            <div className="grid-2">
              <label className="field">
                <span>起点经度</span>
                <input
                  className="input"
                  type="number"
                  step="0.05"
                  value={sectionDef.lon1}
                  onChange={(e) => setSection({ ...sectionDef, lon1: Number(e.target.value) })}
                />
              </label>
              <label className="field">
                <span>起点纬度</span>
                <input
                  className="input"
                  type="number"
                  step="0.05"
                  value={sectionDef.lat1}
                  onChange={(e) => setSection({ ...sectionDef, lat1: Number(e.target.value) })}
                />
              </label>
              <label className="field">
                <span>终点经度</span>
                <input
                  className="input"
                  type="number"
                  step="0.05"
                  value={sectionDef.lon2}
                  onChange={(e) => setSection({ ...sectionDef, lon2: Number(e.target.value) })}
                />
              </label>
              <label className="field">
                <span>终点纬度</span>
                <input
                  className="input"
                  type="number"
                  step="0.05"
                  value={sectionDef.lat2}
                  onChange={(e) => setSection({ ...sectionDef, lat2: Number(e.target.value) })}
                />
              </label>
            </div>
            <Loading on={section.loading} />
            {section.data && (
              <>
                <div className="stat-grid mt-8">
                  <div className="stat">
                    <span>穿越总数</span>
                    <b>{section.data.total}</b>
                  </div>
                  <div className="stat">
                    <span>向外海</span>
                    <b>{section.data.seaward}</b>
                  </div>
                  <div className="stat">
                    <span>向陆向</span>
                    <b>{section.data.landward}</b>
                  </div>
                </div>
                <div className="field-title mt-8">逐小时流量</div>
                <LineChart
                  items={section.data.timeseries.map((t) => ({
                    label: t.hour.slice(5),
                    value: t.count,
                  }))}
                />
                <div className="axis-labels">
                  <span>{section.data.timeseries[0]?.hour.slice(5) ?? ''}</span>
                  <span>
                    {section.data.timeseries[section.data.timeseries.length - 1]?.hour.slice(5) ?? ''}
                  </span>
                </div>
              </>
            )}
          </>
        )}

        {tab === 'od' && (
          <>
            <div className="field-title">主要 OD 流量（网格聚合 Top15）</div>
            <Loading on={od.loading} />
            {od.data && (
              <BarChart
                items={od.data.map((o) => ({
                  label: `${o.origin.latitude.toFixed(2)},${o.origin.longitude.toFixed(2)} → ${o.destination.latitude.toFixed(2)},${o.destination.longitude.toFixed(2)}`,
                  value: o.count,
                }))}
                color="#ea580c"
                height={220}
              />
            )}
            <div className="muted text-xs mt-6">开启「OD 流量」图层可在地图上看到流向弧线</div>
          </>
        )}

        {tab === 'corridor' && (
          <>
            <div className="field-title">主航线提取</div>
            <Loading on={corridors.loading} />
            {corridors.data && (
              <>
                <div className="muted text-xs">
                  网格阈值法识别到 {corridors.data.length} 条连通高密度走廊
                </div>
                <BarChart
                  items={corridors.data.slice(0, 10).map((c, i) => ({
                    label: `走廊 ${i + 1}`,
                    value: c.cell_count,
                  }))}
                  color="#7c3aed"
                  height={200}
                />
              </>
            )}
            <div className="muted text-xs mt-6">开启「主航线」图层可在地图上叠加显示</div>
          </>
        )}

        {/* 交互层面板自带取数 hook，条件渲染使其仅在选中时才请求后端 */}
        {tab === 'interaction' && <InteractionPanel />}

        {tab === 'rot' && <RotPanel />}

        {tab === 'parallel' && (
          <>
            <div className="field-title">多维平行坐标</div>
            <Loading on={multivariate.loading} />
            {multivariate.error && (
              <div className="muted text-xs">加载失败：{multivariate.error}</div>
            )}
            <ParallelCoords data={multivariate.data} />
            <div className="muted text-xs mt-6">
              每条折线为一艘船在某一时间窗内的一条观测（共 7 维，含航向角变化率），
              各维已按量程归一化；可识别如「渔船低速 + 高转向率」「集装箱高速 +
              低转向率 + 集中在主航段」等多维关联模式
            </div>
          </>
        )}
      </div>
    </div>
  );
}
