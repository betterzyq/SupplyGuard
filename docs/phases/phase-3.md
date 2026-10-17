# P3：传播模拟与方案比较

## 需求
SIM-01/02；前置 P2 人工通过。区分拓扑依赖、规则暴露和业务约束下的实际模拟影响。

## 开发
1. 规范输入：事件站点、开始时间、停供/恢复天数、产能比例、需求、在库与在途、BOM 用量、替代认证与供货上限。
2. 按时间推进供需，计算可用库存、缺料、受影响生产与交付；订单和成本去重；限制循环和重复物料展开。
3. 模拟结果保存输入快照、版本、假设、结果区间及证据路径；前端展示基线与措施方案差异。
4. 约束下比较替代采购、库存调拨、加急运输与改道；拒绝负成本、超产能、尚未认证的替代方案。
5. 提供 simulation/run 与 comparison 契约；相同输入结果可复现。LLM 仅解释，不修改数字。
6. 随机模拟是可选项，须有分布说明、固定种子和样本量；缺少数据则保留确定性结果。

## 测试与人工操作
从库存 100、日需 20、停供 3 天开始手算，无缺料；改为停供 7 天应出现缺料。固定其他条件，增库存不得让缺料更早；补足有效替代供给不得增加缺口。同一订单两条传播路径只计一次金额。

在地图选择事件→设置时长→运行→展开依据→比较两项措施→核对成本/订单/时间。检测零需求、无替代、供应链环路、同区域多事件和容量不足。

## 交付与回滚
交付输入样例、手算对照、边界测试、方案比较界面和人审命令。清楚标注仿真收益。回滚新增模拟模块及页面，不改地图原始历史数据。人工通过后进入 P4。

## 本阶段实现与运行入口

| 范围 | 实现 |
|---|---|
| 合成排产与措施目录 | `data/demo/simulation-v1.json`，P1/P2 文件保持独立 |
| 输入与约束 | `packages/business/simulation_models.py`，有界参数、BOM DAG、认证、共享资源与批次冲突 |
| 仿真与比较 | `packages/business/simulation.py`，按日库存守恒、排产、交付、费用与证据 |
| 快照保存 | `packages/business/simulation_store.py`，项目内原子 JSON，租户+个人范围 |
| API | `apps/api/routers/v1/simulation.py`，templates / run / comparison / runs |
| 界面 | `/simulation`，`apps/web/src/components/simulation/`；从地图风险站点带事件与时点进入 |
| 测试 | `tests/phase3/`、`scripts/phase3_*.py`、`phase3_browser.mjs`、`inspect_simulation.py` |

执行 `make phase3-check`、`make acceptance-up`、`make phase3-smoke`、`make phase3-browser`；已运行旧验收服务时先安全关闭再启动。`make phase3-snapshot-check` 校验最近 smoke 保存内容，支持关闭/启动后再次读取。

算法口径及限制见 [仿真方法](../simulation-method.md)，人审步骤见 [P3-H1—H14](../manual-acceptance.md)，实测见 [P3 报告](../reports/phase-3.md)。没有引入随机模型或置信区间；确定性结果、未完成延误下界与未来无法判断的订单分开呈现。P3 人工通过后才进入 P4。
