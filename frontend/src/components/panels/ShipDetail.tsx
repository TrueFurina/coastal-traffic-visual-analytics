'use client';
import { useAppStore } from '@/store/useAppStore';
import { useSnapshot } from '@/hooks/useData';

export default function ShipDetail() {
  const selectedShip = useAppStore((s) => s.selectedShip);
  const selectShip = useAppStore((s) => s.selectShip);
  const { data: ships } = useSnapshot();
  const ship = ships.find((s) => s.mmsi === selectedShip);

  if (!selectedShip) {
    return (
      <div className="card">
        <div className="card-title">船舶详情</div>
        <div className="muted text-xs">点击地图上的船舶圆点查看轨迹</div>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="card-title">
        船舶详情
        <button className="btn btn-ghost btn-xs" onClick={() => selectShip(null)}>
          清除
        </button>
      </div>
      <div className="kv-list">
        <div className="kv">
          <span>船名</span>
          <b>{ship?.name || '——'}</b>
        </div>
        <div className="kv">
          <span>MMSI</span>
          <b>{selectedShip}</b>
        </div>
        <div className="kv">
          <span>类型</span>
          <b>{ship?.ship_type || '——'}</b>
        </div>
        <div className="kv">
          <span>航速</span>
          <b>{ship ? `${Number(ship.speed ?? 0).toFixed(1)} kn` : '——'}</b>
        </div>
        <div className="kv">
          <span>航向</span>
          <b>{ship ? `${Number(ship.course ?? 0).toFixed(0)}°` : '——'}</b>
        </div>
        <div className="kv">
          <span>位置</span>
          <b>
            {ship
              ? `${Number(ship.latitude).toFixed(3)}°N ${Number(ship.longitude).toFixed(3)}°E`
              : '——'}
          </b>
        </div>
      </div>
    </div>
  );
}
