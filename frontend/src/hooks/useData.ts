'use client';
import { useEffect, useRef, useState } from 'react';
import * as api from '@/lib/api';
import { useAppStore } from '@/store/useAppStore';

/** 通用异步取数：带防抖 + 丢弃过期响应。enabled=false 时跳过请求。 */
function useAsyncData<T>(
  loader: () => Promise<T>,
  deps: unknown[],
  initial: T,
  debounceMs = 200,
  enabled = true,
) {
  const [data, setData] = useState<T>(initial);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const token = useRef(0);

  useEffect(() => {
    if (!enabled) return;
    const id = ++token.current;
    setLoading(true);
    const timer = setTimeout(() => {
      loader()
        .then((res) => {
          if (token.current === id) {
            setData(res);
            setError(null);
          }
        })
        .catch((e: unknown) => {
          if (token.current === id) setError(e instanceof Error ? e.message : String(e));
        })
        .finally(() => {
          if (token.current === id) setLoading(false);
        });
    }, debounceMs);
    return () => clearTimeout(timer);
  }, [...deps, enabled]);

  return { data, loading, error };
}

/** 当前分析时间窗（后端字符串格式）。 */
function useWindowStrings() {
  const cursor = useAppStore((s) => s.cursor);
  const windowMinutes = useAppStore((s) => s.windowMinutes);
  const start = cursor ? api.toApiTime(cursor) : undefined;
  const end = cursor ? api.toApiTime(cursor + windowMinutes * 60_000) : undefined;
  return { start, end };
}

export function useStatistics() {
  return useAsyncData<api.Statistics | null>(
    () => api.fetchStatistics(),
    [],
    null,
    0,
  );
}

/** 时间窗末端的船舶位置快照（时间回放主力数据）。 */
export function useSnapshot() {
  const bbox = useAppStore((s) => s.bbox);
  const windowMinutes = useAppStore((s) => s.windowMinutes);
  const cursor = useAppStore((s) => s.cursor);
  const { end } = useWindowStrings();
  return useAsyncData<api.ShipSnapshot[]>(
    () => api.fetchSnapshot(end ?? '', bbox),
    [cursor, windowMinutes, bbox.min_lon, bbox.min_lat, bbox.max_lon, bbox.max_lat],
    [],
  );
}

export function useDensity() {
  const bbox = useAppStore((s) => s.bbox);
  const gridSize = useAppStore((s) => s.gridSize);
  const cursor = useAppStore((s) => s.cursor);
  const windowMinutes = useAppStore((s) => s.windowMinutes);
  const { start, end } = useWindowStrings();
  return useAsyncData<api.DensityCell[]>(
    () => api.fetchDensity(bbox, gridSize, start, end),
    [
      cursor,
      windowMinutes,
      gridSize,
      bbox.min_lon,
      bbox.min_lat,
      bbox.max_lon,
      bbox.max_lat,
    ],
    [],
  );
}

export function useSpeedCourse() {
  const bbox = useAppStore((s) => s.bbox);
  const cursor = useAppStore((s) => s.cursor);
  const windowMinutes = useAppStore((s) => s.windowMinutes);
  const { start, end } = useWindowStrings();
  return useAsyncData<api.SpeedCourseOut | null>(
    () => api.fetchSpeedCourse(bbox, start, end),
    [
      cursor,
      windowMinutes,
      bbox.min_lon,
      bbox.min_lat,
      bbox.max_lon,
      bbox.max_lat,
    ],
    null,
    300,
  );
}

export function useSectionalFlow() {
  const section = useAppStore((s) => s.section);
  const cursor = useAppStore((s) => s.cursor);
  const windowMinutes = useAppStore((s) => s.windowMinutes);
  const { start, end } = useWindowStrings();
  return useAsyncData<api.SectionalFlowOut | null>(
    () =>
      api.fetchSectionalFlow(
        section.lon1,
        section.lat1,
        section.lon2,
        section.lat2,
        start,
        end,
      ),
    [cursor, windowMinutes, section.lon1, section.lat1, section.lon2, section.lat2],
    null,
    400,
  );
}

export function useCorridors() {
  const gridSize = useAppStore((s) => s.gridSize);
  const cursor = useAppStore((s) => s.cursor);
  const windowMinutes = useAppStore((s) => s.windowMinutes);
  const { start, end } = useWindowStrings();
  return useAsyncData<api.Corridor[]>(
    () => api.fetchCorridors(gridSize, start, end),
    [cursor, windowMinutes, gridSize],
    [],
    400,
  );
}

/** 平行坐标用多维样本（抽样量固定，避免时间窗变化触发重算抖动）。 */
export function useMultivariate(n = 1200) {
  const bbox = useAppStore((s) => s.bbox);
  const cursor = useAppStore((s) => s.cursor);
  const windowMinutes = useAppStore((s) => s.windowMinutes);
  const { start, end } = useWindowStrings();
  return useAsyncData<api.MultivariateOut | null>(
    () => api.fetchMultivariate(n, bbox, start, end),
    [
      n,
      cursor,
      windowMinutes,
      bbox.min_lon,
      bbox.min_lat,
      bbox.max_lon,
      bbox.max_lat,
    ],
    null,
    400,
  );
}

export function useOD() {
  const cursor = useAppStore((s) => s.cursor);
  const windowMinutes = useAppStore((s) => s.windowMinutes);
  const { start, end } = useWindowStrings();
  return useAsyncData<api.ODItem[]>(
    () => api.fetchOD(15, start, end),
    [cursor, windowMinutes],
    [],
    400,
  );
}

/* ---------- L2 船舶交互层 ---------- */
// 这三个接口需要在时间窗内做两两组合计算，成本高于普通聚合，
// 因此默认关闭（enabled=false），仅在打开「船舶交互」面板或开启对应图层时才请求。
// 另：cursor 未初始化（0）时时间窗为空，会退化成全表两两计算（千万级），故一并拦掉。
function interactionEnabled(active: boolean, cursor: number) {
  return active && cursor > 0;
}

export function useEncounters(enabled = false, limit = 500) {
  const bbox = useAppStore((s) => s.bbox);
  const cursor = useAppStore((s) => s.cursor);
  const windowMinutes = useAppStore((s) => s.windowMinutes);
  const dcpaNm = useAppStore((s) => s.encDcpaNm);
  const { start, end } = useWindowStrings();
  return useAsyncData<api.EncountersOut | null>(
    () => api.fetchEncounters(start, end, bbox, { dcpaNm, limit }),
    [
      cursor,
      windowMinutes,
      dcpaNm,
      limit,
      bbox.min_lon,
      bbox.min_lat,
      bbox.max_lon,
      bbox.max_lat,
    ],
    null,
    400,
    interactionEnabled(enabled, cursor),
  );
}

export function useConflicts(enabled = false, topN = 30) {
  const bbox = useAppStore((s) => s.bbox);
  const cursor = useAppStore((s) => s.cursor);
  const windowMinutes = useAppStore((s) => s.windowMinutes);
  const dcpaNm = useAppStore((s) => s.encDcpaNm);
  const { start, end } = useWindowStrings();
  return useAsyncData<api.ConflictsOut | null>(
    () => api.fetchConflicts(start, end, bbox, { topN, dcpaNm }),
    [
      cursor,
      windowMinutes,
      dcpaNm,
      topN,
      bbox.min_lon,
      bbox.min_lat,
      bbox.max_lon,
      bbox.max_lat,
    ],
    null,
    400,
    interactionEnabled(enabled, cursor),
  );
}

export function useDomainViolations(enabled = false, limit = 500) {
  const bbox = useAppStore((s) => s.bbox);
  const cursor = useAppStore((s) => s.cursor);
  const windowMinutes = useAppStore((s) => s.windowMinutes);
  const model = useAppStore((s) => s.domainModel);
  const scale = useAppStore((s) => s.domainScale);
  const { start, end } = useWindowStrings();
  return useAsyncData<api.DomainOut | null>(
    () => api.fetchDomainViolations(start, end, bbox, { model, scale, limit }),
    [
      cursor,
      windowMinutes,
      model,
      scale,
      limit,
      bbox.min_lon,
      bbox.min_lat,
      bbox.max_lon,
      bbox.max_lat,
    ],
    null,
    400,
    interactionEnabled(enabled, cursor),
  );
}

/* ---------- 航向角变化率（D1）---------- */

// 转向率默认走 15 分钟窗口口径：逐点差分会把位置噪声放大成伪转向，
// 实测逐点均值约为窗口口径的 7~23 倍（具体倍数由接口 diagnostics 给出）。
export function useRotStatistics(enabled = false) {
  const bbox = useAppStore((s) => s.bbox);
  const cursor = useAppStore((s) => s.cursor);
  const windowMinutes = useAppStore((s) => s.windowMinutes);
  const rotWindowMin = useAppStore((s) => s.rotWindowMin);
  const rotManeuver = useAppStore((s) => s.rotManeuver);
  const { start, end } = useWindowStrings();
  return useAsyncData<api.RotStatisticsOut | null>(
    () => api.fetchRotStatistics(start, end, bbox,
      { windowMin: rotWindowMin, maneuverRot: rotManeuver }),
    [cursor, windowMinutes, rotWindowMin, rotManeuver,
     bbox.min_lon, bbox.min_lat, bbox.max_lon, bbox.max_lat],
    null,
    400,
    interactionEnabled(enabled, cursor),
  );
}

export function useRotByType(enabled = false) {
  const bbox = useAppStore((s) => s.bbox);
  const cursor = useAppStore((s) => s.cursor);
  const windowMinutes = useAppStore((s) => s.windowMinutes);
  const rotWindowMin = useAppStore((s) => s.rotWindowMin);
  const { start, end } = useWindowStrings();
  return useAsyncData<api.RotByTypeOut | null>(
    () => api.fetchRotByType(start, end, bbox, { windowMin: rotWindowMin }),
    [cursor, windowMinutes, rotWindowMin,
     bbox.min_lon, bbox.min_lat, bbox.max_lon, bbox.max_lat],
    null,
    400,
    interactionEnabled(enabled, cursor),
  );
}

export function useRotDistribution(enabled = false) {
  const bbox = useAppStore((s) => s.bbox);
  const cursor = useAppStore((s) => s.cursor);
  const windowMinutes = useAppStore((s) => s.windowMinutes);
  const rotWindowMin = useAppStore((s) => s.rotWindowMin);
  const { start, end } = useWindowStrings();
  return useAsyncData<api.RotDistributionOut | null>(
    () => api.fetchRotDistribution(start, end, bbox, { windowMin: rotWindowMin }),
    [cursor, windowMinutes, rotWindowMin,
     bbox.min_lon, bbox.min_lat, bbox.max_lon, bbox.max_lat],
    null,
    400,
    interactionEnabled(enabled, cursor),
  );
}

export function useRotGrid(enabled = false, gridSize = 40) {
  const bbox = useAppStore((s) => s.bbox);
  const cursor = useAppStore((s) => s.cursor);
  const windowMinutes = useAppStore((s) => s.windowMinutes);
  const rotWindowMin = useAppStore((s) => s.rotWindowMin);
  const { start, end } = useWindowStrings();
  return useAsyncData<api.RotGridOut | null>(
    () => api.fetchRotGrid(start, end, bbox, { gridSize, windowMin: rotWindowMin }),
    [cursor, windowMinutes, rotWindowMin, gridSize,
     bbox.min_lon, bbox.min_lat, bbox.max_lon, bbox.max_lat],
    null,
    400,
    interactionEnabled(enabled, cursor),
  );
}

export function useTrajectory(mmsi: string | null) {
  const mode = useAppStore((s) => s.trajMode);
  const cursor = useAppStore((s) => s.cursor);
  const windowMinutes = useAppStore((s) => s.windowMinutes);
  const { start, end } = useWindowStrings();
  return useAsyncData<api.TrajectoryPoint[]>(
    () => (mmsi ? api.fetchTrajectory(mmsi, mode, start, end) : Promise.resolve([])),
    [mmsi, mode, cursor, windowMinutes],
    [],
    150,
  );
}
