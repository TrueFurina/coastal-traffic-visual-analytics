# 沿海水域船舶交通流可视分析系统

> **状态：已收口归档（2026-10-02）。** 本项目作为「沿海水域交通流可视分析 + 船舶会遇风险感知」工程系统**已完成并可用**；作为「MARL 避碰」科研课题经评估边际价值不足，故**收口、不再追加开发**。收口口径（交付清单 / 核心资产 / 诚信披露 / 解冻条件）见 [`plans/项目收口说明.md`](plans/项目收口说明.md)。

基于 AIS 船舶轨迹大数据的沿海水域交通流可视分析平台：后端用 DuckDB 直接对 Parquet 做列存聚合分析，前端用 deck.gl（WebGL）渲染百万级轨迹，支持时间回放、密度网格、断面流量、主航线提取、OD 分析、**会遇冲突感知**等多视图联动。

研究水域：**长江口—舟山海域**（经度 121.4–123.2，纬度 29.7–31.5）。

---

## 一、技术栈

| 层 | 选型 | 说明 |
|---|---|---|
| 前端 | Next.js 14 + React 18 + TypeScript（渐进迁移） | 新模块全部 TS，旧原型代码已清理 |
| 地图 | MapLibre GL v5 + deck.gl 9.4（MapboxOverlay 交错渲染） | 无需底图密钥：Carto 栅格 + OpenSeaMap 航标层 |
| 状态 | zustand | 时间窗 / 筛选 / 图层 / 选中船全局联动 |
| 后端 | FastAPI | `routers / services / core` 分层 |
| 数据层 | **DuckDB + Parquet** | 免数据库服务，直接对 AIS 列存聚合（已弃用 Prisma，旧文件归档在 `backend/legacy/`） |

## 二、快速开始

### 方式 1：一键启动（Windows，推荐）

双击项目根目录 `start_system_fixed.bat`，依次拉起：

- 后端 FastAPI：<http://localhost:8000>（接口文档 <http://localhost:8000/docs>）
- 前端 Next.js：<http://localhost:3000>

### 方式 2：手动启动

```bash
# 后端
cd backend
venv\Scripts\python.exe -m pip install -r requirements.txt
venv\Scripts\python.exe -m uvicorn app.main:app --port 8000 --reload

# 前端（另一个终端）
cd frontend
npm install
npm run dev
```

前端默认请求 `http://localhost:8000`，可用 `.env.local` 的 `NEXT_PUBLIC_API_BASE_URL` 覆盖。

## 三、数据

### 数据集现状

| 指标 | 值 |
|---|---|
| AIS 报文 | 1,200,001 条 |
| 船舶 | 1,200 艘（散货 / 集装箱 / 油轮 / 渔船 / 客船） |
| 时间跨度 | 2024-06-01 00:01 → 2024-06-02 23:57（48 小时） |
| 落盘 | `backend/data/ais/trajectories.parquet`（约 45 MB）+ `ships.parquet`（船舶维表） |

### 重新生成数据集

```bash
cd backend
venv\Scripts\python.exe scripts\generate_dataset.py
```

生成器按长江口—舟山真实航道走向与船型航速分布合成报文，固定随机种子，结果可复现。

### 导入真实 AIS（CSV）

字段：`mmsi, timestamp, longitude, latitude, speed, course`（可选 `ship_type, name`）。

`POST /import/trajectories` 会先跑清洗管道（`app/services/cleaning.py`）：去重（mmsi+timestamp）→ 水域越界剔除 → 异常航速剔除（>40 kn）→ 相邻点跳点剔除，并返回各规则剔除数量。

## 四、分析能力

| 分析 | 接口 | 界面位置 | 算法要点 |
|---|---|---|---|
| 时空密度网格 | `GET /density/heatmap` | 地图「密度网格」图层 | DuckDB 网格分组聚合，支持时间窗 / 区域 / 网格精度 |
| 时刻快照（时间回放） | `GET /analysis/snapshot` | 左栏「时间回放」 | `arg_max` 取每船指定时刻最新报文 |
| 航速 / 航向分布 + 行为分类 | `GET /analysis/speed-course` | 右栏「航速航向」 | 8 档航速直方图、16 扇区航向玫瑰图、锚泊 / 机动 / 在航分类 |
| 断面流量 | `GET /analysis/sectional-flow` | 右栏「断面流量」 | 线段相交判定 + 双向计数 + 逐小时序列 |
| 主航线提取 | `GET /analysis/corridors` | 右栏「主航线」 | 高密度网格 4-连通分量 |
| OD 分析 | `GET /analysis/od` | 右栏「OD」 | 首末点网格化，Top-N 流向统计 |
| **会遇检测（CPA/TCPA）** | `GET /analysis/encounters` | 地图「会遇」图层 | 分桶配对求最近会遇点；COLREGs 局面分类（交叉/对遇/追越，**100% 覆盖**） |
| **冲突热点 / 船舶领域** | `GET /analysis/conflicts`、`/analysis/domain-violations` | 地图「冲突」/「领域」图层 | 网格聚合热点；Fujii/Goodwin 船舶领域 + 船头间距 |
| **航向角变化率（ROT）** | `GET /analysis/rot/{statistics,by-type,grid,distribution}` | 右栏「ROT」 | 窗口口径 + 360° 环绕折叠 + 噪声放大诊断 |
| 轨迹抽稀 / 平滑 | `GET /ships/{mmsi}/trajectories/simplified`、`/smoothed` | 左栏「轨迹处理」 | Douglas-Peucker 抽稀、移动平均 / B 样条平滑 |

## 五、目录结构

```
backend/
  app/
    main.py                FastAPI 装配
    core/                  config.py（路径/水域/阈值）· db.py（DuckDB 连接）
    routers/               ships · trajectories · analysis · rot · ingest · mock_data · export
    services/              ais_store（Parquet 查询）· cleaning（清洗）· parquet_io
                           traffic（交通流算法）· kde · metrics · multivariate（分析）
                           interaction（CPA/TCPA 会遇）· colregs（局面判定）· domain（船舶领域）· rot（航向变化率）
                           generator（合成数据）· smoothing（平滑）
  scripts/    generate_dataset.py（生成数据集）· smoke.py（端到端冒烟，25 项）· mutation_check.py（变异验证，14 项）
  tests/      test_traffic · test_interaction · test_kde_metrics · test_rot（共 53 项）
  data/ais/   trajectories.parquet · ships.parquet
  legacy/     已弃用的 Prisma 版本（main.py / prisma / generate_*.py 等）
frontend/
  pages/index.tsx          工作台页面（原 534 行单文件已拆分）
  src/lib/api.ts           后端 API 客户端与类型定义
  src/store/useAppStore.ts zustand 联动状态（时间窗 / 筛选 / 图层 / 框选）
  src/hooks/useData.ts     取数 hooks（防抖 + 丢弃过期响应）
  src/hooks/useBoxSelect.ts 地图区域框选绘制
  src/components/map/      TrafficMap.tsx（MapLibre + deck.gl）· layers.ts（密度/轨迹/会遇/领域/ROT 图层）
  src/components/panels/   TimeController · FilterPanel · ShipDetail · AnalysisPanel（7 页签）· InteractionPanel · RotPanel
  src/components/charts/   轻量 SVG 图表（柱状 / 玫瑰 / 折线 / 平行坐标）
plans/current.md            改造总体规划与进度记录
plans/项目收口说明.md        收口口径单一真值源（交付清单 / 资产去向 / 诚信披露）
```

## 六、测试与验证

```bash
# 后端算法单测
cd backend && venv\Scripts\python.exe -m pytest tests -q

# 端到端接口冒烟（需后端已启动，25 项校验）
venv\Scripts\python.exe scripts\smoke.py

# 变异验证（确认测试真的能捕获错误，14 项）
venv\Scripts\python.exe scripts\mutation_check.py

# 前端构建（含 TS 类型检查）
cd frontend && npx next build
```

`smoke.py` 逐条校验接口返回结构，打印耗时与响应体积，失败以非零码退出。

## 七、已知限制

- 断面流量为 Python 逐点遍历，全量 120 万点约 2.7 s；后续可改为 SQL 预筛后再算交点。
- `docker-compose.yml` 保留为非主路径（DuckDB 方案不需要数据库服务），本地优先用 `start_system_fixed.bat`。
- 地图密度柱高按「当前时间窗最大值」归一化，跨时间窗比较需注意这一点。
- 当前数据集为按真实航道分布合成的 AIS 数据；接入真实 AIS 走 `POST /import/trajectories` 即可，分析链路无需改动。
- ⚠️ **数据为合成、非实船**，且有两个已实测硬伤（详见 [`plans/项目收口说明.md`](plans/项目收口说明.md) 第五节）：多船**穿模**（6h 窗口 **36 起 <0.05nm 假会遇**）、`course` 由带 ~89m 噪声的位置反算（逐点 ROT **79.9°/min**，约为真值的 23 倍）。**任何"实船验证"表述均不成立。**
- ⚠️ L2 交互层为**离线 DuckDB 批处理**，非在线逐步仿真；若要进 RL 环境，复用的是**公式**而非代码。
- 收口后本项目**不再追加开发**；源码与数据按原样归档，供复用与史料留存。
