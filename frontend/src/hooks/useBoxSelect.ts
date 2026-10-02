'use client';
import { useEffect, useRef, useState } from 'react';
import type { RefObject } from 'react';
import type maplibregl from 'maplibre-gl';
import type { BBox } from '@/lib/api';

export interface ScreenRect {
  left: number;
  top: number;
  width: number;
  height: number;
}

/** 小于该像素视为误点，不产生选区。 */
const MIN_DRAG_PX = 8;

/**
 * 地图矩形框选：按住左键拖出选框，松开后回调经纬度范围。
 * 开启期间禁用地图平移与 shift 框选缩放，避免手势冲突。
 * 不引入 terra-draw / mapbox-gl-draw 等额外依赖。
 */
export function useBoxSelect(
  mapRef: RefObject<maplibregl.Map | null>,
  containerRef: RefObject<HTMLDivElement | null>,
  enabled: boolean,
  onComplete: (bbox: BBox) => void,
): ScreenRect | null {
  const [rect, setRect] = useState<ScreenRect | null>(null);
  const startRef = useRef<{ x: number; y: number } | null>(null);
  // 回调放进 ref，避免父组件每次重渲染都重挂事件
  const doneRef = useRef(onComplete);
  doneRef.current = onComplete;

  useEffect(() => {
    const map = mapRef.current;
    const el = containerRef.current;
    if (!map || !el) return;

    if (!enabled) {
      map.dragPan.enable();
      map.boxZoom.enable();
      return;
    }
    map.dragPan.disable();
    map.boxZoom.disable();

    const toLocal = (e: PointerEvent) => {
      const r = el.getBoundingClientRect();
      return { x: e.clientX - r.left, y: e.clientY - r.top };
    };

    const onDown = (e: PointerEvent) => {
      if (e.button !== 0) return;
      const p = toLocal(e);
      startRef.current = p;
      setRect({ left: p.x, top: p.y, width: 0, height: 0 });
      el.setPointerCapture(e.pointerId);
    };

    const onMove = (e: PointerEvent) => {
      const s = startRef.current;
      if (!s) return;
      const p = toLocal(e);
      setRect({
        left: Math.min(s.x, p.x),
        top: Math.min(s.y, p.y),
        width: Math.abs(p.x - s.x),
        height: Math.abs(p.y - s.y),
      });
    };

    const onUp = (e: PointerEvent) => {
      const s = startRef.current;
      if (!s) return;
      startRef.current = null;
      const p = toLocal(e);
      const w = Math.abs(p.x - s.x);
      const h = Math.abs(p.y - s.y);
      setRect(null);
      if (el.hasPointerCapture(e.pointerId)) el.releasePointerCapture(e.pointerId);
      if (w < MIN_DRAG_PX || h < MIN_DRAG_PX) return;
      // 屏幕 y 小 = 北 = 纬度大，两端各取 min/max 即可，无需手工翻转
      const a = map.unproject([Math.min(s.x, p.x), Math.min(s.y, p.y)]);
      const b = map.unproject([Math.max(s.x, p.x), Math.max(s.y, p.y)]);
      doneRef.current({
        min_lon: Math.min(a.lng, b.lng),
        max_lon: Math.max(a.lng, b.lng),
        min_lat: Math.min(a.lat, b.lat),
        max_lat: Math.max(a.lat, b.lat),
      });
    };

    el.addEventListener('pointerdown', onDown);
    el.addEventListener('pointermove', onMove);
    el.addEventListener('pointerup', onUp);
    el.addEventListener('pointercancel', onUp);
    return () => {
      el.removeEventListener('pointerdown', onDown);
      el.removeEventListener('pointermove', onMove);
      el.removeEventListener('pointerup', onUp);
      el.removeEventListener('pointercancel', onUp);
      map.dragPan.enable();
      map.boxZoom.enable();
    };
  }, [enabled, mapRef, containerRef]);

  return rect;
}
