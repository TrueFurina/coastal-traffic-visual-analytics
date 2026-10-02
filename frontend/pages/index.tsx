import { useEffect } from 'react';
import dynamic from 'next/dynamic';
import { useAppStore } from '@/store/useAppStore';
import { useStatistics } from '@/hooks/useData';
import { parseTs, formatTs } from '@/lib/api';
import TimeController from '@/components/panels/TimeController';
import FilterPanel from '@/components/panels/FilterPanel';
import ShipDetail from '@/components/panels/ShipDetail';
import AnalysisPanel from '@/components/panels/AnalysisPanel';
import { SHIP_TYPE_COLORS } from '@/components/map/layers';

const TrafficMap = dynamic(() => import('@/components/map/TrafficMap'), {
  ssr: false,
  loading: () => <div className="map-loading">地图加载中…</div>,
});

export default function HomePage() {
  const stats = useStatistics();
  const setTimeRange = useAppStore((s) => s.setTimeRange);
  const density = useAppStore((s) => s.layers.density);

  useEffect(() => {
    const d = stats.data;
    if (!d?.time_range) return;
    const min = parseTs(d.time_range.start);
    const max = parseTs(d.time_range.end);
    if (Number.isFinite(min) && Number.isFinite(max)) setTimeRange(min, max);
  }, [stats.data, setTimeRange]);

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <h1>沿海水域船舶交通流可视分析</h1>
          <span className="muted text-xs">
            长江口—舟山海域 · AIS 轨迹大数据（DuckDB + deck.gl）
          </span>
        </div>
        <div className="header-stats">
          <span className="chip">
            船舶 {stats.data?.total_ships?.toLocaleString() ?? '—'}
          </span>
          <span className="chip">
            报文 {stats.data?.total_trajectory_points?.toLocaleString() ?? '—'}
          </span>
          <span className="chip">
            {stats.data
              ? `${formatTs(parseTs(stats.data.time_range.start), false)} 起 ${stats.data.time_range.start.slice(5, 10)}`
              : '时间范围 —'}
          </span>
          {stats.error && <span className="chip chip-danger">后端未连接</span>}
        </div>
      </header>

      {stats.error && (
        <div className="banner-danger">
          无法连接后端（{stats.error}）。请先启动后端：
          <code>backend\venv\Scripts\python.exe -m uvicorn app.main:app --port 8000</code>
        </div>
      )}

      <main className="app-main">
        <aside className="col-left">
          <TimeController />
          <FilterPanel shipTypeStats={stats.data?.ship_type_distribution ?? {}} />
          <ShipDetail />
        </aside>

        <section className="col-map">
          <TrafficMap />
          <div className="legend">
            {density && (
              <div className="legend-row">
                <span className="legend-title">密度</span>
                <span className="ramp" />
                <span className="muted text-xs">低 → 高</span>
              </div>
            )}
            <div className="legend-row wrap">
              {Object.entries(SHIP_TYPE_COLORS).map(([t, c]) => (
                <span className="legend-item" key={t}>
                  <i className="dot" style={{ background: `rgb(${c.join(',')})` }} />
                  {t}
                </span>
              ))}
            </div>
          </div>
        </section>

        <aside className="col-right">
          <AnalysisPanel />
        </aside>
      </main>
    </div>
  );
}
