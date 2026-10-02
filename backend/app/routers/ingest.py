"""导入路由：CSV -> 清洗 -> 追加 Parquet。"""
import csv
import io
from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services import ais_store, cleaning
from app.schemas import ImportResult

router = APIRouter(prefix="/import", tags=["import"])


def _read_csv(file: UploadFile):
    content = file.file.read().decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))
    return [dict(r) for r in reader]


@router.post("/ships", response_model=ImportResult)
async def import_ships(file: UploadFile = File(...)):
    if not (file.filename or "").lower().endswith((".csv", ".json")):
        raise HTTPException(status_code=400, detail="仅支持 CSV 文件")
    rows = _read_csv(file)
    cleaned = []
    for r in rows:
        if r.get("mmsi") and r.get("name"):
            cleaned.append({
                "mmsi": int(float(r["mmsi"])),
                "name": r.get("name", ""),
                "ship_type": r.get("ship_type", ""),
                "length": float(r.get("length", 0) or 0),
                "width": float(r.get("width", 0) or 0),
            })
    ais_store.append_ships(cleaned)
    return ImportResult(message="船舶数据导入成功", imported_count=len(cleaned))


@router.post("/trajectories", response_model=ImportResult)
async def import_trajectories(file: UploadFile = File(...)):
    if not (file.filename or "").lower().endswith((".csv", ".json")):
        raise HTTPException(status_code=400, detail="仅支持 CSV 文件")
    rows = _read_csv(file)
    cleaned, report = cleaning.clean_trajectories(rows)
    ais_store.append_trajectories(cleaned)
    return ImportResult(
        message="轨迹数据导入成功", imported_count=len(cleaned),
        cleaning_report=report)
