# 船舶轨迹大数据交通流可视分析系统 —— 深度改造总体规划

> 版本：v1.1（2026-10-02）｜状态：**已转方向**（见下方「方向变更」）
> 定位：本文件是本项目**执行层**计划源；**上位权威源 = `E:\Program\多智能体主线全貌_资产地图.md`**，冲突时以上位为准。

---

## 方向变更（2026-10-02 用户确认）

**大创申报未通过** → 本项目**不废弃**，转入多智能体主线「LLM 决策 + MARL 执行 + 链上可信」。

| 项 | 内容 |
|---|---|
| 上位权威源 | `E:\Program\多智能体主线全貌_资产地图.md`（主线唯一索引） |
| 主线定位 | **MARL 执行层 · 海上域**（L2 感知 CPA/COLREGs/领域 → 避碰决策） |
| Q4 范围 | **Phase S1（避碰环境）+ S2（MARL 训练起步）**；S3/S4 外移 |
| 执行方案 | `plans/marl_避碰扩展规划.md`（已按上位范围收窄至 S1-S2） |
| 旧验收约束 | `doc/申报书承诺-系统实现对照表.md` 转为**历史记录**，不再作为主业验收口径 |

**关键技术风险（决定 S1 环境能否成立；均出自本项目实测，非推测）**
1. **合成数据多船会互相穿过**（6h 窗口 36 起 <0.05nm 假会遇）→ 训练环境里他船会穿模本船。S1 必须先做**轨迹一致性修正 / 碰撞样本剔除**，否则学的是"躲一个不会避让的幽灵船"。
2. 数据 `course` 由带 ~89m 噪声的位置反算 → 他船航向观测噪声主导（逐点 ROT 79.9 °/min）。需窗口平滑后再进观测。
3. 「感知层已就绪」表述需修正：L2 是**离线 DuckDB 批处理**，RL env 需**在线逐步仿真** → 复用的是**公式**（colregs/domain 为纯函数），`interaction.py` 的批查询需重写为 numpy 逐步环境。

---

## 一、现状诊断（探索代理实测，含证据）

### 1.1 后端 = 演示原型，数据链路断裂
- **实际运行的是内存 mock**：`start_system_fixed.bat` 启动 `simplified_main.py`（622 行上帝文件），数据存 dict，启动时随机生成 15 船 × 30 点，**进程重启即丢**。
- **Prisma 链路已废弃**：中文路径导致 Prisma 生成器编码失败（`generate_client.py` 等 4 个一次性绕行脚本为证），`main.py`（270 行 Prisma 版）从未成功跑起来；`prisma/dev.db` 仅 40KB 空库。
- **无大数据能力**：轨迹查询全量拉取、密度计算在内存做、无分页/抽样/聚合/批量写入/分区索引，百万级 AIS 数据无法支撑。
- **无分析算法**：仅 B 样条平滑 + 移动平均 + numpy 网格密度（`utils/trajectory_processor.py` 147 行），无清洗/去重/压缩/OD/断面流量/行为识别——**与"交通流可视分析研究"题目严重不匹配**。
- **质量信号**：零测试、无 requirements.txt、重复路由注册（L225/L268 同路径）、CORS `*`、占位密钥。

### 1.2 前端 = 能跑的单页原型，带致命 bug
- **致命 bug**：`pages/index.js:285-337` mock 数据 useEffect 每 5 秒用 2 艘假船**覆盖真实 API 数据**——系统永远显示假数据。
- **地图必然加载失败**：`ShipMap.js:107` 用 MapTiler 占位 key（`get_your_own_...`）。
- **大数据无性能方案**：MapLibre 原生 API + DOM Marker + line 图层，无 cluster/WebGL/deck.gl，万级轨迹点即卡死。
- **死代码成堆**：`DataImportForm.js`（533 行，零引用）、`ShipMapTemp.js`（调试残留）、双套并存轨迹逻辑（`ShipMap.drawTrajectories` 被注释 vs `ShipMapFix.fixTrajectoryEffect`）、根目录 `fix-shipmap.cjs` 一次性脚本。
- **工程化缺失**：纯 JS（TS 装了没用）、Tailwind 未生效（无 config，JSX 里工具类全是死代码）、echarts/recharts/radix 声明了但零引用、`papaparse` 幽灵依赖、无状态管理（index.js 606 行 useState 大杂烩）。

### 1.3 结论
当前系统 ≈ "UI 草图 + 内存 mock"。**题目宣称的三件事——轨迹大数据、交通流分析、可视分析——一件都没有真正实现**。改造不是优化，是重建核心链路。

---

## 二、目标定位

为大创/毕设交付一个**名实相符**的可视分析系统：

| 题目关键词 | 落地标准（验收口径） |
|---|---|
| 船舶轨迹大数据 | 真实 AIS 数据集（≥100 万轨迹点，公开数据源）入库，查询秒级响应 |
| 沿海水域 | 选定真实研究水域（建议：长江口—舟山海域），电子海图风格底图 + OpenSeaMap 航道图层 |
| 交通流 | 实现 ≥5 类交通流分析：网格密度、断面流量、航速/航向分布、OD/航线提取、时空热力 |
| 可视分析 | 地图 + 图表联动的分析界面（不是单纯展示）：时间回放、刷选过滤、下钻详情 |

---

## 三、目标架构

```
┌─────────────────────────────────────────────────────┐
│ 前端 Next.js + deck.gl（WebGL 大数据渲染）            │
│  MapView / AnalysisPanel / TimeController / 联动状态  │
└──────────────┬──────────────────────────────────────┘
               │ REST（分页/聚合后的小数据，不搬原始点）
┌──────────────▼──────────────────────────────────────┐
│ 后端 FastAPI（routers/services 分层）                 │
│  api/      ships · trajectories · analysis · ingest  │
│  services/ 清洗 · 压缩(DP) · 密度 · 断面流量 · OD聚类 │
│  core/     config · db · 日志                         │
└──────────────┬──────────────────────────────────────┘
               │
┌──────────────▼──────────────────────────────────────┐
│ 数据层（方案见 §四 决策点 D1）                         │
│  AIS 原始数据（Parquet/DB）+ 分析查询引擎              │
└─────────────────────────────────────────────────────┘
```

**关键设计原则**
1. **计算在后端，渲染在前端**：前端永远不拉原始轨迹点全量数据，后端按视野/时间窗/缩放级别返回聚合结果（网格密度、抽稀轨迹）。
2. **分层抽稀**：轨迹渲染按 zoom level 做 Douglas-Peucker 抽稀 + 服务端分页，百万点不卡。
3. **研究可复现**：每个分析算法有独立模块 + 最小测试 + 示例输出，论文截图可复现。

---

## 四、关键技术决策点（待用户拍板）

### D1 数据层方案
- **A. DuckDB + Parquet（推荐）**：列存分析引擎，直接 SQL 聚合百万级 AIS 点，免数据库服务，天然契合"轨迹大数据分析"研究场景；彻底解决中文路径 Prisma 问题。单机研究项目最优解。
- B. PostgreSQL + PostGIS：生产级、空间索引强，但要跑 Docker 服务，重装环境成本高。
- C. SQLite + SQLAlchemy：最保守，改动小，但分析查询性能弱于 A。

### D2 前端大数据渲染
- **A. 引入 deck.gl（推荐）**：WebGL 渲染，ScatterplotLayer/PathLayer/HeatmapLayer/GridLayer 直接对应交通流分析需求，10 万级点流畅。与 MapLibre 官方集成。
- B. 保持 MapLibre 原生 + cluster：改动小，但密度/热力/聚合要自己造轮子。

### D3 前端工程化路线
- **A. 渐进迁移 TS + 组件拆分（推荐）**：保留 Next.js，逐文件迁移 .ts，拆 ShipMap 为 layers/hooks，引入 zustand 管理联动状态。
- B. 纯 JS 只做清理：快但债留着。
- C. 换 Vite 重写：最干净但工作量翻倍，不推荐。

### D4 研究水域与数据
- **A. 长江口—舟山海域 + 公开 AIS 数据（推荐）**：NOAA MarineCadastre / 丹麦海事局公开 AIS，或按真实分布生成合成数据兜底；水域贴合"沿海"题目。
- B. 纯合成数据：可控但"大数据"说服力弱。

---

## 五、分阶段计划

### Phase 0 —— 止血修复（0.5 天，先做，不依赖任何决策）
| # | 任务 | 验收 |
|---|---|---|
| 0.1 | 删除 mock 覆盖 bug（index.js:285-337） | 前端显示后端真实数据 |
| 0.2 | 换无底图密钥方案（OSM/Carto raster style） | 地图无 key 正常加载 |
| 0.3 | 删死代码：DataImportForm/ShipMapTemp/fix-shipmap.cjs/废弃轨迹逻辑/幽灵依赖 | 构建无未用引用 |
| 0.4 | 补 requirements.txt，修重复路由，去重复 import | 一键可装依赖 |
| 0.5 | Tailwind 二选一：补 config 启用 or 删工具类换自定义类 | 样式无死代码 |

### Phase 1 —— 数据层重建（1-2 天，依赖 D1）
| # | 任务 | 验收 |
|---|---|---|
| 1.1 | 按选定方案重建数据层，废弃 Prisma 及 4 个绕行脚本 | AIS 点表 + 复合索引/分区 |
| 1.2 | AIS 导入管道：CSV→校验→清洗（去重/跳点/异常速度）→批量入库 | 100 万点导入 < 5 分钟，有清洗报告 |
| 1.3 | 获取/生成研究水域真实 AIS 数据集（≥100 万点） | 数据集落盘 + 元信息文档 |
| 1.4 | 后端重构：simplified_main 拆分为 routers/services/core | 单文件 < 200 行，接口契约不变 |

### Phase 2 —— 交通流分析算法层（2-3 天，研究核心）
| # | 任务 | 验收 |
|---|---|---|
| 2.1 | 时空网格密度（时间窗 × 网格 × 船型维度） | API 返回聚合网格，秒级 |
| 2.2 | 断面流量统计（自定义断面线，双向计数） | 断面定义 + 流量时序输出 |
| 2.3 | 航速/航向分布 + 船舶行为分类（航行/锚泊/滞航） | 统计接口 + 分布图数据 |
| 2.4 | 轨迹抽稀（DP）+ 航线提取（轨迹聚类 DBSCAN/HDBSCAN） | 主航道可视化结果 |
| 2.5 | OD 分析 / 热区识别 | 热区列表 + 图面表达 |
| 2.6 | 每个算法配最小单元测试 + 示例输出 | pytest 全绿 |

### Phase 3 —— 前端重构（2-3 天，依赖 D2/D3）
| # | 任务 | 验收 |
|---|---|---|
| 3.1 | ShipMap 拆分：layers/hooks/utils，引入 deck.gl | 单文件 < 250 行，10 万点流畅 |
| 3.2 | zustand 联动状态：时间窗/选中船/过滤器一处管理 | 地图↔图表双向联动 |
| 3.3 | 时间回放控制器（播放/倍速/区间循环） | 轨迹按时间流动画 |
| 3.4 | 分析面板：密度热力/断面流量/速度分布/航线图 多视图 | 每个 Phase 2 算法有对应视图 |
| 3.5 | 海图风格：OpenSeaMap seamarks 叠加 + 深色/浅色主题 | 沿海要素可见 |

### Phase 4 —— 整合交付（1 天）
| # | 任务 | 验收 |
|---|---|---|
| 4.1 | docker-compose 全链路修复或提供一键 bat | 一条命令起全系统 |
| 4.2 | README 重写（真实架构/数据/分析能力/复现步骤） | 与实现一致 |
| 4.3 | 端到端冒烟脚本（导入→分析→截图） | 可复现演示链路 |
| 4.4 | 整理 doc/ 参考论文与本系统功能对照（支撑申报书/论文素材） | 对照表产出 |

**里程碑**：M1（Phase 0+1）= 真数据真链路 → M2（Phase 2）= 研究内核成立 → M3（Phase 3+4）= 可演示可交付。

---

## 六、风险与对策
| 风险 | 对策 |
|---|---|
| 公开 AIS 数据下载慢/被墙 | 多源备选（NOAA/丹麦/合成生成器兜底），先下小样本验证管道 |
| 中文路径再次坑工具链 | 弃 Prisma 即除根；所有脚本路径用 ASCII 临时目录中转 |
| deck.gl 学习成本 | 只用官方示例覆盖的 4 个 Layer，不深入定制 |
| 贪大导致烂尾 | 严格按 Phase 推进，每 Phase 有独立验收，M1 未完成不进 Phase 2 |

## 进度记录
- 2026-10-01：完成现状诊断与总体规划 v1.0；用户确认 D1=DuckDB+Parquet、D2=deck.gl、D3=渐进 TS、节奏=Phase 0 起连续推进。
- 2026-10-01：Phase 0 完成（mock 覆盖 bug、Carto 无密钥底图、死代码清理、requirements.txt、重复路由、剥离失效 Tailwind 类），`next build` 通过。
- 2026-10-01/02：Phase 1 完成 —— backend/app 分层（routers/services/core）、弃 Prisma 归档 legacy/、DuckDB+Parquet 数据层、合成 AIS 数据集 1,200,001 点 / 1200 船 / 2024-06-01~06-02、清洗管道、start_system_fixed.bat 更新。
- 2026-10-02：Phase 2 完成 —— 交通流算法层 traffic.py（航速航向分布+行为分类、断面流量、DP 抽稀、主航线提取、OD、时刻快照），10 个 pytest 全绿；新增 /analysis/snapshot 支撑时间回放。
- 2026-10-02：Phase 2+ 补齐申报书三大创新点 —— KDE 核密度曲面（kde.py）、12 项交通流指标体系（metrics.py）、6 轴平行坐标（multivariate.py + frontend）；对照表 doc/申报书承诺-系统实现对照表.md 首次生成。
- 2026-10-02：Phase 3 前端完成 —— deck.gl(WebGL) 图层 + zustand 联动状态 + 时间回放控制器 + 分析面板（frontend/src/components/map|panels|charts）。
- 2026-10-02：**L2 多智能体交互感知层完成并挂路由** —— interaction.py(CPA/TCPA 会遇)、colregs.py(Rule 13/14/15 局面与责任)、domain.py(Fujii/Goodwin 船舶领域 + 船头间距)；新增 /analysis/encounters、/analysis/conflicts、/analysis/domain-violations。对照表 C4 由 ❌ 转 ✅，新增第六节。
- 2026-10-02：质量底座加固 —— 新增 tests/test_interaction.py（20 项），全量 44 项全绿；变异验证从 6 项扩到 11 项（含追越方向、对遇判据、重叠排除、类型泄漏、抽样种子），11/11 全部捕获；端到端冒烟 21/21（最慢 2.57s）。
- 2026-10-02：修复可复现性缺陷 —— DuckDB `USING SAMPLE` 无种子导致 KDE 同参数两次结果不同（峰值差 0.8%），已统一为 `USING SAMPLE reservoir(N ROWS) REPEATABLE (42)`（kde.py 与 multivariate.py 两套语法并存也一并统一）。
- 下一步建议（待拍板）：① 会遇/领域结果的前端视图与区域联动（后端已就绪，缺上图）② 航向角变化率指标（可让 D1 转 ✅）③ 真实 AIS 导入（P0，决定能否称"实船验证"）。
- 2026-10-02：Phase 3 完成 —— 前端重写为 deck.gl + zustand + TS（TrafficMap/layers/panels/charts/store/hooks），旧组件与 pages/index.js 删除，`next build` 通过、页面 SSR 正常。
- 2026-10-02：Phase 4 基本完成 —— README 全量重写、docker-compose 精简为 2 服务、backend Dockerfile 去 Prisma、`scripts/smoke.py` 端到端冒烟 14/14 PASS、package.json 依赖对齐（补 deck.gl/zustand，清 11 个幽灵依赖）。
- 2026-10-02：Phase 3.4+ 交互层前端视图完成 —— `src/lib/api.ts` 增 3 组类型与 fetch；`hooks/useData.ts` 增 useEncounters/useConflicts/useDomainViolations（useAsyncData 支持 enabled，且 cursor=0 时拦掉全表计算）；store 增 3 个图层开关与 encDcpaNm/domainModel/domainScale；`layers.ts` 增会遇点(按局面着色)/冲突热点(extruded 网格)/领域侵犯(按侵入深度)三图层 + 悬浮详情；新建 `panels/InteractionPanel.tsx`（判据可调 + 局面构成 + 热点 Top10 + 船头间距分布 + 侵犯 Top10）；MiniCharts 支持逐项配色。`tsc --noEmit` 零错误、`next build` 通过、SSR 产物含新 UI。
- 2026-10-02：交互层性能实测 —— 6h 窗口 encounters 0.05s；**无时间参数（全表）4.29s**，为带窗值的 85 倍，故前端在 cursor 未初始化时拦截请求（避免首屏无谓全量计算，非崩溃级风险）。
- 2026-10-02：B5 区域框选绘制完成 —— `hooks/useBoxSelect.ts`（零新增依赖，pointer 事件 + maplibre unproject，绘制期禁用 dragPan/boxZoom，<8px 视为误点）；store 增 drawnBbox/drawMode，范围优先级「手绘选区 > 视野 > 全域」；layers.ts 增 PolygonLayer 显示选区；FilterPanel 增框选/清除与当前范围读数。`tsc` 零错误、`next build` 通过、SSR 含新 UI。
- 2026-10-02：框选联动打通并修两个真 bug —— ① `/analysis/conflicts` 路由把 bbox 写死 `None`（底层支持却没接线），补参后 166格/1998 → 32格/77；② `layers.ts` 冲突网格边长按 STUDY_AREA 恒定计算，视野/框选后与实际聚合范围错位，改用当前生效 bbox。
- 2026-10-02：D1 航向角变化率完成，D1 由 ⚠️ 转 ✅ —— 新建 `services/rot.py`（11 项指标 + 网格 + 分船型 + 分布）与 `routers/rot.py`（4 端点，独立成文件因 analysis.py 已到 200 行上限）；`multivariate.py` 轴集 6→7 维新增 rot 轴，D1 三方（KDE/平行坐标/转向率）齐备。前端新建 `panels/RotPanel.tsx`（口径切换 + 阈值滑块 + 指标卡 + 分布/船型对比）并接入第 7 个页签；layers.ts 增转向强度网格图层。
- 2026-10-02：ROT 的**关键数据事实**（决定指标能否引用）—— 本数据集 course 由带 ~89m 噪声的位置反算，逐点差分被噪声主导：平均 |ROT| 逐点 79.9 °/min → 5min 7.4 → 15min 3.50 → 30min 1.91，单调衰减即噪声特征。故默认 15min 窗口口径，接口 diagnostics 同时返回逐点值作对照（放大 ~23 倍）。且 |ROT| 分布无双峰 → 机动阈值 3.0 是约定值，机动率仅可相对比较。
- 2026-10-02：修两个真 bug —— ① 窗口口径下 `_MAX_GAP_S=600` 误杀 15min 窗口样本（126 vs 应有 2246），改为上界取 max(max_gap, 窗口长)、下界要求覆盖 ≥50% 窗口；② **`USING SAMPLE ... REPEATABLE` 在 GROUP BY 之后不可复现**（行序不确定），rot 与 multivariate 均受影响，改用 `ORDER BY hash(...)` 确定性抽样。
- 尚未做：doc/ 参考论文与本系统功能对照表（申报书/论文素材），可在需要时补。
- 已知性能项：/analysis/sectional-flow 全量 2.6s（Python 逐点遍历），后续可用 SQL 预筛优化。
- 2026-10-02（下午）：**方向变更** —— 大创申报未通过，本项目转为主线「LLM 决策 + MARL 执行 + 链上可信」的**海上域 · MARL 执行层**（详见文件头「方向变更」）。上位权威源确认为 `多智能体主线全貌_资产地图.md`；`plans/marl_避碰扩展规划.md` 保留有效但**收窄为 Q4 只做 S1-S2**（S3/S4 外移）；并澄清 `Agent_x_MARL` 规划中「marl_避碰扩展规划.md 已作废标注」的说法不成立（实为范围收窄）。
- 2026-10-02：质量数字刷新（供主线资产地图对账用）—— 测试 **53 项全绿**、端到端冒烟 **25/25**、变异验证 **14/14**、平行坐标 7 轴（含 rot）、ROT 4 端点。资产地图所记「44 / 21 / 11」为旧值。
