"""FastAPI 应用装配：CORS + 路由注册。"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import ships, trajectories, analysis, ingest, mock_data, export, rot

app = FastAPI(title="船舶交通流可视化系统", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (ships.router, trajectories.router, analysis.router,
          ingest.router, mock_data.router, export.router, rot.router):
    app.include_router(r)


@app.get("/")
def root():
    return {
        "message": "船舶交通流可视化系统 API (DuckDB + Parquet)",
        "version": "2.0",
        "endpoints": [
            "/mock_data/ships", "/mock_data/trajectories",
            "/density/heatmap", "/data/statistics",
            "/ships/{id}/trajectories",
            "/ships/{id}/trajectories/smoothed",
            "/analysis/kde", "/analysis/hotspots", "/analysis/metrics",
            "/analysis/multivariate", "/analysis/snapshot",
            "/analysis/encounters", "/analysis/conflicts",
            "/analysis/domain-violations",
            "/import/*", "/export/*",
        ],
    }


if __name__ == "__main__":
    import uvicorn
    from app.core import config
    uvicorn.run(app, host="0.0.0.0", port=config.PORT)
