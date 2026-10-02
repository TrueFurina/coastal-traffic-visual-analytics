'use client';
import type { ReactElement } from 'react';

export interface BarItem {
  label: string;
  value: number;
  /** 逐项配色（优先级高于统一 color），用于分类语义着色。 */
  color?: string;
}

export function BarChart({
  items,
  color = '#2563eb',
  height = 150,
}: {
  items: BarItem[];
  color?: string;
  height?: number;
}): ReactElement {
  const max = items.reduce((m, i) => Math.max(m, i.value), 0) || 1;
  return (
    <div className="chart-bars" style={{ height }}>
      {items.map((it) => (
        <div className="chart-bar-row" key={it.label}>
          <span className="chart-bar-label" title={it.label}>
            {it.label}
          </span>
          <div className="chart-bar-track">
            <div
              className="chart-bar-fill"
              style={{ width: `${(it.value / max) * 100}%`, background: it.color ?? color }}
            />
          </div>
          <span className="chart-bar-value">{it.value}</span>
        </div>
      ))}
    </div>
  );
}

export function RoseChart({
  items,
  size = 170,
}: {
  items: BarItem[];
  size?: number;
}): ReactElement {
  const max = items.reduce((m, i) => Math.max(m, i.value), 0) || 1;
  const cx = size / 2;
  const cy = size / 2;
  const r = size / 2 - 12;
  const n = items.length || 1;
  const step = 360 / n;
  return (
    <svg width={size} height={size} className="chart-rose" role="img">
      <circle cx={cx} cy={cy} r={r} fill="#f8fafc" stroke="#e2e8f0" />
      {items.map((it, i) => {
        const len = (it.value / max) * r;
        const ang = (i * step - 90) * (Math.PI / 180);
        const x2 = cx + Math.cos(ang) * len;
        const y2 = cy + Math.sin(ang) * len;
        return (
          <line
            key={it.label}
            x1={cx}
            y1={cy}
            x2={x2}
            y2={y2}
            stroke="#0ea5e9"
            strokeWidth={Math.max(2, (size / n) * 0.55)}
            strokeLinecap="round"
          >
            <title>{`${it.label}: ${it.value}`}</title>
          </line>
        );
      })}
      <circle cx={cx} cy={cy} r={3} fill="#0f172a" />
      <text x={cx} y={12} textAnchor="middle" fontSize={10} fill="#64748b">
        N
      </text>
    </svg>
  );
}

export function LineChart({
  items,
  height = 130,
}: {
  items: BarItem[];
  height?: number;
}): ReactElement {
  if (!items.length) return <div className="chart-empty">暂无数据</div>;
  const w = 100;
  const max = items.reduce((m, i) => Math.max(m, i.value), 0) || 1;
  const min = items.reduce((m, i) => Math.min(m, i.value), 0);
  const pts = items.map((it, i) => {
    const x = (i / Math.max(1, items.length - 1)) * w;
    const y = height - ((it.value - min) / Math.max(1, max - min)) * (height - 14) - 7;
    return `${x.toFixed(2)},${y.toFixed(2)}`;
  });
  return (
    <svg
      viewBox={`0 0 ${w} ${height}`}
      preserveAspectRatio="none"
      className="chart-line"
      height={height}
    >
      <polyline points={pts.join(' ')} fill="none" stroke="#f97316" strokeWidth={1.2} />
      <polyline
        points={`0,${height} ${pts.join(' ')} ${w},${height}`}
        fill="rgba(249,115,22,0.12)"
        stroke="none"
      />
    </svg>
  );
}
