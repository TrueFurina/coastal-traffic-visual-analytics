'use client';
import { useEffect, useMemo } from 'react';
import { useAppStore } from '@/store/useAppStore';
import { formatTs, toApiTime } from '@/lib/api';

const WINDOW_OPTIONS = [60, 180, 360, 720, 1440];
const STEP_OPTIONS = [15, 30, 60, 180];
const SPEED_OPTIONS = [1, 2, 4, 8];

export default function TimeController() {
  const timeMin = useAppStore((s) => s.timeMin);
  const timeMax = useAppStore((s) => s.timeMax);
  const cursor = useAppStore((s) => s.cursor);
  const windowMinutes = useAppStore((s) => s.windowMinutes);
  const playing = useAppStore((s) => s.playing);
  const speed = useAppStore((s) => s.speed);
  const stepMinutes = useAppStore((s) => s.stepMinutes);
  const setCursor = useAppStore((s) => s.setCursor);
  const advance = useAppStore((s) => s.advance);
  const setWindowMinutes = useAppStore((s) => s.setWindowMinutes);
  const togglePlay = useAppStore((s) => s.togglePlay);
  const setSpeed = useAppStore((s) => s.setSpeed);
  const setStepMinutes = useAppStore((s) => s.setStepMinutes);

  const maxStart = Math.max(timeMin, timeMax - windowMinutes * 60_000);

  // 播放循环：每 1000/speed 毫秒推进 stepMinutes
  useEffect(() => {
    if (!playing || !timeMax) return;
    const id = setInterval(() => advance(stepMinutes), 1000 / speed);
    return () => clearInterval(id);
  }, [playing, stepMinutes, speed, advance, timeMax]);

  const windowLabel = useMemo(() => {
    if (!cursor) return '等待数据…';
    return `${formatTs(cursor)} → ${formatTs(cursor + windowMinutes * 60_000)}`;
  }, [cursor, windowMinutes]);

  return (
    <div className="card">
      <div className="card-title">
        时间回放
        <span className="muted text-xs">（窗内数据实时聚合）</span>
      </div>

      <div className="time-window-label">{windowLabel}</div>

      <input
        className="slider"
        type="range"
        min={timeMin}
        max={maxStart}
        step={15 * 60_000}
        value={Math.min(cursor, maxStart)}
        onChange={(e) => setCursor(Number(e.target.value))}
      />

      <div className="row gap-6 wrap">
        <button className={`btn ${playing ? 'btn-danger' : 'btn-primary'}`} onClick={togglePlay}>
          {playing ? '暂停' : '播放'}
        </button>
        <button className="btn btn-ghost" onClick={() => setCursor(timeMin)}>
          回到起点
        </button>
      </div>

      <div className="grid-2 mt-8">
        <label className="field">
          <span>时间窗</span>
          <select
            className="select"
            value={windowMinutes}
            onChange={(e) => setWindowMinutes(Number(e.target.value))}
          >
            {WINDOW_OPTIONS.map((m) => (
              <option key={m} value={m}>
                {m < 1440 ? `${m / 60} 小时` : '24 小时'}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>步进</span>
          <select
            className="select"
            value={stepMinutes}
            onChange={(e) => setStepMinutes(Number(e.target.value))}
          >
            {STEP_OPTIONS.map((m) => (
              <option key={m} value={m}>
                {m} 分钟
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>倍速</span>
          <select
            className="select"
            value={speed}
            onChange={(e) => setSpeed(Number(e.target.value))}
          >
            {SPEED_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {s}×
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>跳至</span>
          <input
            className="input"
            type="datetime-local"
            value={cursor ? toApiTime(cursor).slice(0, 16) : ''}
            min={toApiTime(timeMin).slice(0, 16)}
            max={toApiTime(timeMax).slice(0, 16)}
            onChange={(e) => {
              const v = e.target.value;
              if (v) setCursor(new Date(v.replace('T', ' ')).getTime());
            }}
          />
        </label>
      </div>
    </div>
  );
}
