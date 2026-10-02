'use client';
import { useEffect, useRef } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { MapboxOverlay } from '@deck.gl/mapbox';
import { buildLayers } from './layers';
import { STUDY_AREA, useAppStore } from '@/store/useAppStore';
import { useBoxSelect } from '@/hooks/useBoxSelect';
import {
  useConflicts,
  useCorridors,
  useDensity,
  useDomainViolations,
  useEncounters,
  useOD,
  useRotGrid,
  useSnapshot,
  useTrajectory,
} from '@/hooks/useData';
import { shipColor, situationColor } from './layers';

const BASE_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  glyphs: 'https://fonts.openmaptiles.org/{fontstack}/{range}.pbf',
  sources: {
    carto: {
      type: 'raster',
      tiles: [
        'https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png',
        'https://b.basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png',
        'https://c.basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png',
      ],
      tileSize: 256,
      attribution: '© OpenStreetMap contributors © CARTO',
    },
    seamark: {
      type: 'raster',
      tiles: ['https://tiles.openseamap.org/seamark/{z}/{x}/{y}.png'],
      tileSize: 256,
      attribution: '© OpenSeaMap',
    },
  },
  layers: [
    { id: 'bg', type: 'background', paint: { 'background-color': '#dce7f2' } },
    { id: 'carto', type: 'raster', source: 'carto' },
    {
      id: 'seamark',
      type: 'raster',
      source: 'seamark',
      paint: { 'raster-opacity': 0.85 },
    },
  ],
} as unknown as maplibregl.StyleSpecification;

export default function TrafficMap() {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const overlayRef = useRef<MapboxOverlay | null>(null);

  const density = useDensity();
  const snapshot = useSnapshot();
  const corridors = useCorridors();
  const od = useOD();

  const selectedShip = useAppStore((s) => s.selectedShip);
  const trajectory = useTrajectory(selectedShip);
  const bbox = useAppStore((s) => s.bbox);
  const gridSize = useAppStore((s) => s.gridSize);
  const shipTypes = useAppStore((s) => s.shipTypes);
  const flags = useAppStore((s) => s.layers);
  // 交互层三接口成本较高，仅在对应图层开启时才请求
  const encounters = useEncounters(flags.encounters);
  const conflicts = useConflicts(flags.conflicts);
  const domainV = useDomainViolations(flags.domain);
  const rotGrid = useRotGrid(flags.rot);
  const section = useAppStore((s) => s.section);
  const selectShip = useAppStore((s) => s.selectShip);
  const filterByViewport = useAppStore((s) => s.filterByViewport);
  const setViewportBbox = useAppStore((s) => s.setViewportBbox);
  const drawMode = useAppStore((s) => s.drawMode);
  const setDrawMode = useAppStore((s) => s.setDrawMode);
  const drawnBbox = useAppStore((s) => s.drawnBbox);
  const setDrawnBbox = useAppStore((s) => s.setDrawnBbox);

  // 框选完成后自动退出绘制模式，避免后续拖拽误改选区
  const drawRect = useBoxSelect(mapRef, containerRef, drawMode, (b) => {
    setDrawnBbox(b);
    setDrawMode(false);
  });

  // 初始化 MapLibre + deck.gl 叠加层
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: BASE_STYLE,
      center: [(STUDY_AREA.min_lon + STUDY_AREA.max_lon) / 2, (STUDY_AREA.min_lat + STUDY_AREA.max_lat) / 2],
      zoom: 7.6,
    });
    map.addControl(new maplibregl.AttributionControl({ compact: true }), 'bottom-right');
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'top-right');
    map.addControl(new maplibregl.ScaleControl({ maxWidth: 120, unit: 'nautical' }), 'bottom-left');
    map.fitBounds(
      [
        [STUDY_AREA.min_lon, STUDY_AREA.min_lat],
        [STUDY_AREA.max_lon, STUDY_AREA.max_lat],
      ],
      { padding: 40 },
    );

    const overlay = new MapboxOverlay({
      interleaved: true,
      layers: [],
      getTooltip: ({
        object,
        layer,
      }: {
        object?: Record<string, unknown> | null;
        layer?: { id?: string } | null;
      }) => {
        if (!object || !layer) return null;
        if (layer.id === 'ships') {
          const c = shipColor(object.ship_type as string);
          return {
            html: `<div style="font-size:12px;line-height:1.5">
              <b>${(object.name as string) || '——'}</b> · ${(object.ship_type as string) ?? ''}<br/>
              MMSI ${object.mmsi as string}<br/>
              航速 ${Number(object.speed ?? 0).toFixed(1)} kn · 航向 ${Number(object.course ?? 0).toFixed(0)}°
            </div>`,
            style: { backgroundColor: '#fff', color: '#111827', borderLeft: `4px solid rgb(${c.join(',')})` },
          };
        }
        if (layer.id === 'density') {
          return {
            html: `<div style="font-size:12px">网格报文数：<b>${object.density as number}</b></div>`,
            style: { backgroundColor: '#fff', color: '#111827' },
          };
        }
        if (layer.id === 'od') {
          return {
            html: `<div style="font-size:12px">OD 流量：<b>${object.count as number}</b> 艘次</div>`,
            style: { backgroundColor: '#fff', color: '#111827' },
          };
        }
        if (layer.id === 'encounters') {
          const c = situationColor(object.situation as string);
          return {
            html: `<div style="font-size:12px;line-height:1.5">
              <b>${object.situation as string}</b>会遇 · DCPA ${Number(object.dcpa_nm).toFixed(3)} nm<br/>
              TCPA ${Number(object.tcpa_min).toFixed(1)} min · 当前距 ${Number(object.distance_nm).toFixed(2)} nm<br/>
              <span style="color:#475569">${object.responsibility as string}</span>
            </div>`,
            style: { backgroundColor: '#fff', color: '#111827', borderLeft: `4px solid rgb(${c.join(',')})` },
          };
        }
        if (layer.id === 'conflicts') {
          return {
            html: `<div style="font-size:12px;line-height:1.5">
              热点网格：<b>${object.count as number}</b> 起会遇<br/>
              其中严重 ${object.severe_count as number} 起 · 平均 DCPA ${Number(object.mean_dcpa_nm).toFixed(3)} nm
            </div>`,
            style: { backgroundColor: '#fff', color: '#111827' },
          };
        }
        if (layer.id === 'domain') {
          return {
            html: `<div style="font-size:12px;line-height:1.5">
              领域侵犯 · 侵入比 <b>${(Number(object.penetration_ratio) * 100).toFixed(0)}%</b><br/>
              船头间距 ${Number(object.along_nm).toFixed(3)} nm · 横向 ${Number(object.cross_nm).toFixed(3)} nm<br/>
              <span style="color:#475569">领域半径 ${Number(object.domain_radius_nm).toFixed(3)} nm</span>
            </div>`,
            style: { backgroundColor: '#fff', color: '#111827', borderLeft: '4px solid rgb(220,38,38)' },
          };
        }
        if (layer.id === 'rot') {
          return {
            html: `<div style="font-size:12px;line-height:1.5">
              转向强度网格 · 样本 <b>${object.samples as number}</b> 对<br/>
              平均 |ROT| <b>${Number(object.mean_abs_rot).toFixed(2)}</b> °/min<br/>
              <span style="color:#475569">机动率 ${(Number(object.maneuver_ratio) * 100).toFixed(0)}%</span>
            </div>`,
            style: { backgroundColor: '#fff', color: '#111827', borderLeft: '4px solid rgb(251,30,40)' },
          };
        }
        return null;
      },
    });
    map.addControl(overlay);
    mapRef.current = map;
    overlayRef.current = overlay;

    return () => {
      overlay.finalize();
      map.remove();
      mapRef.current = null;
      overlayRef.current = null;
    };
  }, []);

  // 数据变化 → 更新 deck.gl 图层
  useEffect(() => {
    if (!overlayRef.current) return;
    overlayRef.current.setProps({
      layers: buildLayers({
        bbox,
        gridSize,
        density: density.data,
        ships: snapshot.data,
        shipTypes,
        trajectory: trajectory.data,
        corridors: corridors.data,
        od: od.data,
        encounters: encounters.data?.encounters ?? [],
        conflicts: conflicts.data?.cells ?? [],
        conflictsGridSize: conflicts.data?.grid_size ?? 40,
        domainViolations: domainV.data?.violations ?? [],
        rotCells: rotGrid.data?.cells ?? [],
        rotGridSize: rotGrid.data?.grid_size ?? 40,
        drawnBbox,
        flags: flags as unknown as Record<string, boolean>,
        section,
        onSelectShip: selectShip,
      }),
    });
  }, [
    bbox,
    gridSize,
    density.data,
    snapshot.data,
    shipTypes,
    trajectory.data,
    corridors.data,
    od.data,
    encounters.data,
    conflicts.data,
    domainV.data,
    rotGrid.data,
    drawnBbox,
    flags,
    section,
    selectShip,
  ]);

  // 视野变化 → 可选按视野过滤
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const handler = () => {
      const b = map.getBounds();
      if (!b) return;
      setViewportBbox({
        min_lon: b.getWest(),
        min_lat: b.getSouth(),
        max_lon: b.getEast(),
        max_lat: b.getNorth(),
      });
    };
    map.on('moveend', handler);
    return () => {
      map.off('moveend', handler);
    };
  }, [setViewportBbox, filterByViewport]);

  return (
    <div className="map-wrap">
      <div
        ref={containerRef}
        className={`map-canvas ${drawMode ? 'map-draw-active' : ''}`}
      />
      {drawRect && (
        <div
          className="map-draw-rect"
          style={{
            left: drawRect.left,
            top: drawRect.top,
            width: drawRect.width,
            height: drawRect.height,
          }}
        />
      )}
      {drawMode && <div className="map-draw-hint">按住左键拖出分析区域</div>}
    </div>
  );
}
