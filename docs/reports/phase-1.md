# P1 实测报告

开发自测：通过。用户人工验收：已通过（2026-10-17 对话确认）。P2：已获授权开始。

记录时间：2026-10-16T21:56:17+08:00（北京时间）。基础提交：`321c240`，本次代码位于未提交工作区。源文件快照：`049871083edfe226a1e2ef9b8df4a5acf6c6a7790b0fbb0c11038105b85226ef`。

## 已交付
- 需求基线、六阶段开发/测试说明、统一测试规范、人工验收步骤及项目隔离约束。
- 经营总览、风险研判、业务导航、两类登录入口、企业知识库共享说明；技术诊断入口供管理员使用。
- admin/enterprise 生效角色；旧内部岗位映射；旧供应商和无有效角色账号拒绝访问；本企业文档共享，保留 tenant 与个人会话边界。
- 修复审计列表与 trace 聚合查询缺少 tenant 过滤的问题；基准结果通过父运行记录限定租户。
- 版本化合成制造数据：6 供应商、10 站点、6 物料、4 产品、12 订单、8 运输批次、4 风险事件、3 场景。首页和风险页共用同一数据，金额使用 Decimal 去重计算。
- 隔离构建、自测、增量账号准备、专用验收服务及仅操作自有进程的关闭工具。旧 seed 脚本未运行。

## 实测结果
| 检查 | 命令/方法 | 结果 |
|---|---|---|
| 权限、契约、金额、API、运行器和数据库保护 | `make phase1-check` 中 pytest | 43 passed |
| Python lint | `make phase1-check` 中 Ruff，最终稳定目标再次核验 | 通过 |
| TypeScript | `tsc --project tsconfig.acceptance.json --noEmit` | 通过 |
| 生产构建 | `.next-check` 与 `.next-acceptance` 分别构建 | 18 个页面生成通过 |
| 真实接口 | `make phase1-smoke`，通过 3100 同源代理 | 两类登录、三场景金额、管理员边界、旧账号兼容通过 |
| 浏览器 | `make phase1-browser` | 18 项通过，无未捕获浏览器异常 |
| 分辨率 | Chromium，1366×768 / 1920×1080 | 无整页横向溢出，订单表允许内部滚动 |
| 安全关闭 | `acceptance-down` 后 `acceptance-status` | 8100/3100 释放；只向登记并核验身份的进程组发信号 |
| 端口占用 | 用本项目测试 socket 占用 8100 后启动 | 启动拒绝，原监听仍存活 |
| 幂等准备 | 重复 `acceptance-up` 的账号准备 | admin/enterprise 已有账号与密码保留 |
| 差异检查 | `git diff --check` | 通过 |

43 项测试覆盖：内部旧岗位统一权限、未知/旧供应商不升级、同租户文档共享、跨租户拒绝（含管理员）、Qdrant 租户约束、全部业务图查询与工具权限、伪造旧 token 角色不能覆盖数据库角色、审计和 trace 查询租户条件、无效数据引用/坐标/金额/时间拒绝、订单去重及精确金额、非法场景 404、无认证 401、错误数据库/生产环境拒绝演示准备、端口/进程身份保护。

本次有 1 条 Starlette TestClient/httpx 兼容弃用提示，不影响测试退出码；未为消除此提示改动共享或项目 Python 依赖。

## 机器证据与截图
- [检查结果](../../.local/acceptance/phase-1/checks.json)、[Python 测试日志](../../.local/acceptance/phase-1/python-tests.log)
- [真实 HTTP 检查](../../.local/acceptance/phase-1/http-smoke.json)、[浏览器检查](../../.local/acceptance/phase-1/browser.json)
- [端口保护检查](../../.local/acceptance/phase-1/port-guard.json)、[源码快照](../../.local/acceptance/phase-1/source-snapshot.json)
- [登录页](../../.local/acceptance/phase-1/login-1366.png)、[经营总览 1366](../../.local/acceptance/phase-1/overview-1366.png)、[经营总览 1920](../../.local/acceptance/phase-1/overview-1920.png)、[管理员评测页](../../.local/acceptance/phase-1/admin-benchmarks-1920.png)

这些文件仅保留在本机被 Git 忽略的 `.local/`；可提交的结果摘要为本报告。

## 数据库及环境影响
- 仅对本项目现有 `demo-mfg` 租户增量创建缺少的 enterprise 角色和 `enterprise@example.com` 账号；原 admin 及旧岗位记录、密码保留。
- 真实登录检查写入本项目原有登录审计和最近登录时间，管理员拒绝检查写权限审计。未迁移数据库结构、未重置图谱、未摄取或删除文档/向量。
- Python/Node 使用原 SupplyGuard 专属环境；无 pip/uv 同步、无系统包安装、无 CUDA/驱动/全局代理修改、无 GPU 使用。
- 浏览器工具与缺失系统运行库只下载/解包在 `.local/browser-qa`、`.local/qa-browsers`。无 `apt install`，未写系统库。
- 构建与验收进程绑定可用 CPU 的前两核，低调度优先级；Node 堆上限 1536 MB，验收 Python API 地址空间上限 3 GiB。以上不等同于操作系统级总 RSS 容器限额。
- 未读取、写入、启停或引用 `risk_vlm_inference`、`risk_vlm_eval` 的资源。未对原 8000/3000 端口或数据库基础设施执行启停。

## 当前运行与人审
交付时专用验收 API `127.0.0.1:8100`、Web `127.0.0.1:3100` 保持运行，便于人工验收。浏览器打开 `http://localhost:3100`；远程服务器需按手册做 SSH 端口转发。

账号：`enterprise@example.com`、`admin@example.com`，本机演示密码均已验证为 `password123`。该值仅限本地演示，不代表更改过原账号密码。

按 [人工验收手册](../manual-acceptance.md) 的 H1—H10 操作并填写结论。关闭使用 `make acceptance-down`；重新启动使用 `make acceptance-up`。修改代码后先关闭再启动，避免使用旧进程。

## 限制与后续
- 所有经营数据是共享的合成模板，响应绑定当前租户上下文；尚未接入真实企业数据。新增业务对象持久化与导入在 P5 交付。
- 场景的受影响订单关系是明确的演示设定，当前敞口不是模型预测概率或损失，不包含库存与恢复时间传播计算。
- 新嵌入式地图/物流回放 P2、库存约束模拟 P3、公开数据模型与新评测 P4、任务持久化/真实报告下载 P5。
- 供应网络仍是独立的旧 Neo4j 技术演示，界面已标明。旧岗位权限基准不适用于新策略；页面提供提示，旧结果不能用作本版本风险预测证明。
- 旧报告工具返回 `not_implemented` 和预览计数，未伪装为成功下载，也不再要求角色逐项审批。
- P2 尚未开始；等待本阶段人工验收意见。


## 2026-10-17 远程浏览器访问排查
- 用户已在 AutoDL 运行完整检查；贴出的 43 项单测、HTTP 和 18 项浏览器检查均通过。
- 再次确认服务器的 `/login` 返回 HTTP 200、根路径返回 307；8100/3100 均为已核验的 SupplyGuard 验收进程。
- 服务器内 Playwright 测试不验证用户电脑的 localhost；电脑访问需要 VS Code Remote-SSH 端口转发或在电脑本地建立 SSH 隧道。
- 已补充 [电脑访问 AutoDL 的完整步骤](../manual-acceptance.md#从自己的电脑访问-autodl)，启动和状态命令也会显示提示。
- 本次仅修改访问说明与运行器提示；4 项运行器回归测试、Ruff 和 `git diff --check` 通过。未重启服务或修改业务逻辑，未重新构建前端。
- [服务器连通性证据](../../.local/acceptance/phase-1/access-diagnostic.json)。用户电脑端隧道及页面打开仍待用户验证，不将服务器测试等同于人工验收通过。
