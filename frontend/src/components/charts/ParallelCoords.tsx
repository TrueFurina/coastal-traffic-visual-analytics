'use client';
import { useMemo, useState } from 'react';
import type { MultivariateOut, MultivariateRow } from '@/lib/api';

/** 船型配色（与研究系统其它图表保持一致的冷色调）。 */
const TYPE_COLORS: Record<string, string> = {
  散货: '#2563eb',
  集装箱: '#7c3aed',
  油轮: '#b45309',
  渔船: '#0f766e',
  客船: '#be123c',
};
const FALLBACK = '#64748b';

const W = 660;
const H = 300;
const PAD_L = 38;
const PAD_R = 38;
const PAD_T = 28;
const PAD_B = 34;

/** 把一个字段值归一化到 [0,1]（0 在轴底，1 在轴顶）。 */
function normalize(row: MultivariateRow, key: string,
                   ranges: MultivariateOut['ranges']): number {
  const r = ranges[key];
  if (!r || r.length === 0) return 0.5;
  const v = row[key as keyof MultivariateRow];
  if (typeof r[0] === 'string') {
    const i = (r as string[]).indexOf(String(v));
    const n = (r as string[]).length;
    return n <= 1 ? 0.5 : i / (n - 1);
  }
  const [lo, hi] = r as number[];
  if (hi === lo) return 0.5;
  return (Number(v) - lo) / (hi - lo);
}

export default function ParallelCoords({
  data,
  maxLines = 1000,
}: {
  data: MultivariateOut | null;
  maxLines?: number;
}) {
  const [hover, setHover] = useState<string | null>(null);

  const geo = useMemo(() => {
    if (!data || !data.axes.length) return null;
    const axes = data.axes;
    const innerW = W - PAD_L - PAD_R;
    const innerH = H - PAD_T - PAD_B;
    const xOf = (i: number) =>
      PAD_L + (axes.length <= 1 ? innerW / 2 : (innerW * i) / (axes.length - 1));
    const yOf = (t: number) => PAD_T + (1 - t) * innerH;
    return { axes, xOf, yOf, innerH };
  }, [data]);

  if (!data || !geo) {
    return <div className="muted text-xs">暂无多维样本数据</div>;
  }

  const rows = data.rows.slice(0, maxLines);
  const legend = Object.keys(
    rows.reduce<Record<string, 1>>((acc, r) => {
      acc[r.ship_type] = 1;
      return acc;
    }, {}),
  );

  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H}
           style={{ display: 'block', overflow: 'visible' }}>
        {/* 轴线与轴名 */}
        {geo.axes.map((a, i) => {
          const x = geo.xOf(i);
          const r = data.ranges[a.key];
          const label = Array.isArray(r) && typeof r[0] === 'string'
            ? `${(r as string[]).length} 类`
            : `${Number((r as number[])[0]).toFixed(1)} ~ ${Number((r as number[])[1]).toFixed(1)}`;
          return (
            <g key={a.key}>
              <line x1={x} y1={PAD_T} x2={x} y2={PAD_T + geo.innerH}
                    stroke="#cbd5e1" strokeWidth={1} />
              <text x={x} y={PAD_T - 12} textAnchor="middle"
                    fontSize={11} fill="#334155" fontWeight={600}>
                {a.name}
              </text>
              <text x={x} y={H - PAD_B + 16} textAnchor="middle"
                    fontSize={9.5} fill="#94a3b8">
                {a.unit}
              </text>
              <text x={x} y={H - PAD_B + 28} textAnchor="middle"
                    fontSize={9} fill="#cbd5e1">
                {label}
              </text>
            </g>
          );
        })}

        {/* 每条观测一条折线 */}
        {rows.map((row) => {
          const pts = geo.axes
            .map((a, i) => `${geo.xOf(i)},${geo.yOf(normalize(row, a.key, data.ranges))}`)
            .join(' ');
          const color = TYPE_COLORS[row.ship_type] ?? FALLBACK;
          const dim = hover !== null && hover !== row.ship_type;
          return (
            <polyline
              key={`${row.mmsi}-${row.hour}-${row.speed}-${row.course}-${row.rot}`}
              points={pts}
              fill="none"
              stroke={color}
              strokeWidth={dim ? 0.5 : 1.1}
              opacity={dim ? 0.06 : 0.28}
            />
          );
        })}
      </svg>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, marginTop: 6 }}>
        {legend.map((t) => (
          <button
            key={t}
            onClick={() => setHover(hover === t ? null : t)}
            onMouseEnter={() => setHover(t)}
            onMouseLeave={() => setHover(null)}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 5,
              background: 'transparent', border: 'none', cursor: 'pointer',
              fontSize: 11, color: '#475569', padding: 0,
              opacity: hover && hover !== t ? 0.45 : 1,
            }}
          >
            <span style={{
              width: 10, height: 10, borderRadius: 2,
              background: TYPE_COLORS[t] ?? FALLBACK, display: 'inline-block',
            }} />
            {t}
          </button>
        ))}
      </div>

      <div className="muted text-xs" style={{ marginTop: 6 }}>
        抽样 {rows.length} / {data.sample_size} 条观测 · 点击图例可单独查看某船型
      </div>
    </div>
  );
}
