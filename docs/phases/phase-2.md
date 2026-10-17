# P2：嵌入式地图与物流跟踪

## 需求
GEO-01、LOG-01；前置 P1 人工通过。风险控制塔与物流跟踪使用统一站点、订单、批次和时钟。

## 开发
1. 锁定 MapLibre/deck.gl 的兼容版本；地图仅在客户端加载。准备有授权的底图、字形、sprite、署名和离线资源清单。
2. 扩展路线折线、运输方式、站点类型、风险覆盖区、里程碑与带时间戳轨迹。国内外数据源坐标处理须统一，不能混用坐标。
3. 风险地图包含聚合、筛选、详情抽屉、风险图例、订单联动和图谱钻取；高亮当前选择，避免全部节点持续闪烁。
4. 物流页支持订单/批次搜索，计划与实际进度、ETA 与来源、轨迹播放；插值模拟位置明确标注。
5. 统一查询参数和场景状态；新增 business/network、shipments、shipment detail 契约，保留 tenant 限制。地图不能依赖外部 LLM。
6. WebGL 不可用时给出明确提示及可操作列表，断网时核心地图/业务层仍可使用。

## 测试与人工操作
先选港口拥堵场景，点击事件→站点→运输批次→订单，核对详情一致；拖动时钟检查未来轨迹不出现；筛选后 KPI 与列表一致；切换场景无残留选择。断网刷新已准备离线资源的页面，检查底图、字体和交互。

自动检查坐标/轨迹时序/引用，浏览器检查缩放、点击、筛选和两个视口；固定 1,000 站点/2,000 路线记录首屏、交互和内存。记录硬件与最终实测，不宣称未测规模。

## 交付与回滚
提交地图与轨迹截图/录像、资源来源清单、规模报告、当阶段可执行命令。新资源和 API 可单独回退，P1 首页与权限保持可用。用户确认地图可用且数据语义正确后进入 P3。

## 实现索引与验收入口

| 范围 | 实现 |
|---|---|
| 回放数据与约束 | `data/demo/network-v1.json`、`packages/business/network.py` |
| 业务接口 | `apps/api/routers/v1/business.py`，network / shipments / shipment detail |
| 共用控制塔 | `apps/web/src/components/control-tower/ControlTower.tsx` |
| 地图与依赖图 | 同目录 `NetworkMap.tsx`、`DependencyGraph.tsx` |
| 筛选、回放投影与离线准备 | `apps/web/src/lib/network.ts`，与 P1 场景状态共用 |
| 离线公共资源 | `apps/web/public/map-sw.js`、`public/maps/manifest.json` |
| 专项自动检查 | `tests/phase2/`、`scripts/phase2_check.py`、`phase2_smoke.py`、`phase2_browser.mjs` |

`make phase2-check` → `make acceptance-up` → `make phase2-smoke` → `make phase2-browser`。已有旧验收进程时更新前先安全执行 `make acceptance-down`。详细界面步骤与预期见 [人工验收手册 P2-H1—H14](../manual-acceptance.md)，来源见 [地图资源说明](../map-assets.md)，结论与限制见 [P2 实测报告](../reports/phase-2.md)。

P2 展示固定关系的风险影响，不包含库存约束传播与措施收益计算；这些按已审批计划在 P3 实现。P2 人工验收前不启动 P3。
