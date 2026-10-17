# P5 企业工作区：数据、任务、报告与本地事件

P4已获人工验收通过。本阶段将处置与数据接入持久化到PostgreSQL，仍然只有admin与enterprise两类角色。本企业业务记录、任务与报告共享；跨租户始终拒绝。P3个人模拟文件继续按用户隔离，只有本人主动点击归档后才产生企业共享副本。

## 数据边界与对象

持久化对象为站点、订单、运输批次、风险事件、历史预测归档、模拟归档、处置任务、导入批次、报告、业务审计与本地事件订阅。

四种可导入对象使用显式Pydantic字段模型和统一`sg5_records`实体表，以kind区分；数据库唯一键为(tenant,kind,code)。`sg5_links`用同租户复合外键连接对象，避免JSON引用只有前端校验。预测/模拟仅通过受控归档创建，不能随意上传一个“模型概率”冒充实际推理。

| 来源 | 含义 | 能用于什么 |
|---|---|---|
| synthetic | 版本化演示或明确选择的模拟内容 | 企业协作演示、仿真与流程验收；不能证明真实收益 |
| enterprise_uploaded | 用户确认上传的业务内容，未经外部真实性核验 | 关联处置任务、报表、企业API读取；不是实时ERP接入证明 |
| public_historical | P4 DataCo固定模型历史样例及版本 | 独立预测验证归档；制造业迁移未验证 |

企业上传数据在“企业数据”页使用，不会悄悄替换控制塔/物流演示图或套用零售模型。任务完成表示人工处置记录经验证完成，不会自动把订单改为已交付、认定风险解除或执行真实采购。

## 导入约定

支持UTF-8 CSV和单工作表XLSX，最多2MiB、1,000条非空数据行（物理行上限10,000）、40列、单值2,000字符；压缩后工作簿还限制展开大小10MiB及文件数100。XLS/多表/公式单元格拒绝。XLSX按只读模式读取，CSV/XLSX导出转义公式前缀，不执行输入表达式。

1. 下载模板，按站点→订单→批次/事件顺序准备。订单只能使用人民币且保留分；时间必须带时区，例如`2026-11-01T09:00:00+08:00`。
2. 读取表头，将业务字段映射到源列。映射方向为`目标字段:源列名`，不读取未映射列，不接受任意tenant字段。
3. 运行预检，保存原文件SHA256、文件名、映射、规范化行与逐行错误。此时只写预检记录，不写业务实体。
4. 预检全部通过后主动确认；确认时再次校验同租户引用、编号冲突，并在一个事务中保存所有实体、引用、审计和事件。

| 对象 | 字段 | 引用 |
|---|---|---|
| site | code,name,site_type,latitude,longitude,country | site_type=factory/warehouse/port/supplier；经纬度范围校验 |
| order | code,name,destination_site_code,product_code,customer,amount_cny,currency,promised_at,status | destination_site_code需已存在；产品编码为本次业务标签，未创建虚构产品图 |
| shipment | code,name,origin_site_code,destination_site_code,order_codes,mode,eta | 两站点和每笔订单均需已存在；mode=ocean/road/rail/air |
| event | code,name,site_codes,order_codes,severity,description,detected_at | 站点、订单需已存在；severity=medium/high/critical |

多引用以`;`分隔，不允许空项或重复项。代码允许字母/数字及`_.:-`，最大100字符。同一编号相同规范化内容和来源可跳过，已有不同内容/来源时整批拒绝，不覆盖历史。所有导入是新增模式；本阶段不提供任意更新、删除或ERP双向同步。

预检有效期24小时。相同文件/映射/校验结果/当天窗口复用已有批次；引用修复后新建预检可得到新的结果。过期确认410，重新运行预检；当同一页面出现老请求状态时可刷新后读取表头并重新预检。无效批次保留供审计，不产生部分业务行。

## 任务状态与审计

`open 待认领 → in_progress 处理中 → pending_verification 待验证 → completed 已完成`；非关闭状态可取消。待验证可填写原因退回处理中。关闭后不能直接重开或改派；如需后续行动创建新任务，保留原记录。

- 创建：关联本企业任一工作区记录、任务名称、带时区期限；可预分配本企业有效成员。两类角色均可协作，不按部门设壁垒。
- 开始：需要责任人和措施。
- 提交验证：需要结果与明确费用（可为0）；金额是人工填报，不等于已验证财务实付。
- 验证完成、退回或取消：需要本次说明；每次操作保存actor、前后状态、费用、结果、版本和时间。
- 每次更新必须提交expected_version。同版本并发仅一个成功，另一个409 version_conflict；不能静默覆盖他人改动。

任务历史属于企业业务审计，不开放完整管理员审计页。变更也追加到既有AuditLog，保留管理员查询与tenant约束。

## 报告与下载

风险报告从当前工作区快照生成：事件→affects→订单引用去重，排除已交付/已取消订单，按Decimal累计风险敞口。敞口不是预计损失或已节省金额。XLSX包含Summary、Orders、Events、Actions、Lineage；Actions包含记录ID、来源类型与人工填报费用。货币以精确两位小数字符串导出以保留分，Excel需要运算时可显式转换数值。

公开评测报告读取P4实际固定实验，保留适用域、版本、协议/数据哈希、基线和失败样例。指定历史benchmark_run_id仅管理员可导出本租户旧记录，并明确旧岗位口径废弃，不把历史分数当成新准确率。

每份报告有固定字节、SHA256及24小时下载有效期，保存在项目PostgreSQL。下载需本企业有效身份，管理员也不能跨租户；过期410，重新生成即可。过期只撤销下载，不自动抹掉审计和存档。不存在公开无鉴权URL或任意文件路径下载。

旧MCP `export_risk_report`、`export_benchmark_results`现在调用同一真实导出服务，返回ready与鉴权下载地址，不再以stub预览当成功。

## 企业API

基础路径`/api/v1/workspace`，认证延续现有Bearer登录。`GET /openapi`返回经认证的企业OpenAPI，可从工作区下载，包含工作区与登录接口，不开放管理员业务数据。

| 方法/路径 | 功能 |
|---|---|
| GET /schema；GET /templates/{kind}?format=csv/xlsx | 字段、限制与真实模板 |
| POST /imports/inspect；POST /imports/preview | multipart读取表头/预检，preview须带kind、source_type、mapping、file |
| GET /imports；POST /imports/{id}/confirm | 查看批次与原子确认 |
| GET /records；GET /records/{id} | kind/source_type/q过滤，limit1..100、offset分页 |
| POST /demo-scenario | 主动保存指定演示场景，来源始终synthetic |
| POST /captures | kind=simulation/prediction、identifier、share_with_tenant=true |
| GET /members | 当前企业有效成员，不含旧供应商账号 |
| GET/POST /tasks；GET/PATCH /tasks/{id}；GET /tasks/{id}/history | 状态过滤、创建、版本化变更、审计分页 |
| GET/POST /reports；GET /reports/{id}/download | 真实生成与鉴权字节下载 |
| GET/POST /subscriptions；GET /subscriptions/{id}/events | 本地订阅与after游标重放 |

业务写接口要求`Idempotency-Key`（1..100字母数字及`-_.:`）。服务按tenant+操作+键保存请求指纹与原响应；同键相同请求返回原响应，不重复写入/发事件；同键不同请求409 idempotency_conflict。网络超时可用同键重试，状态变更还需版本检查。业务对象更新用tenant事务锁和数据库约束串行保护，等待超时返回503，可用同键重试。预检确认结果幂等，重复文件和相同编号另有语义去重。

业务错误形态：

```json
{"error":{"code":"version_conflict","message":"Task changed; reload and review before retrying"}}
```

常见码：not_found(404)、preview_invalid/existing_code_conflict/version_conflict/idempotency_conflict(409)、preview_expired/report_expired(410)、invalid_file/invalid_mapping/invalid_assignee(422)、storage_unavailable(503)。认证/框架字段校验保留既有401/403/422 `detail`格式，不误称全部接口错误结构已统一。

每次报告生成上限10,000实体/任务及10MiB成品。没有大规模导出队列、外部Webhook投递或第三方系统写入。

## 本地事件订阅

topic支持task.created、task.updated、record.created、import.confirmed、report.created。业务写入和事件同事务提交；没有“写入成功但通知事件丢失”的双写间隙。订阅保存于企业内，可用`after`和`limit`读取；相同游标可重放，使用next_cursor继续。游标是有序事件序号，不是已发送外部消息数量。

当前仅本地轮询、可回放，不接受目标URL、不外发消息、不宣称Webhooks已接通。真实外发和采购执行仍需另行授权。

技术依据：[PostgreSQL16事务锁](https://www.postgresql.org/docs/16/explicit-locking.html)、[SQLAlchemy2.0异步会话](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)、[openpyxl只读/只写模式](https://openpyxl.readthedocs.io/en/stable/optimized.html)。使用既有专属环境，没有升级这些依赖。

## 可运行的本机客户端例子

专用服务运行时，以下命令使用演示企业账号做模拟文件预检，默认不确认业务入库，不输出Bearer token：

```bash
.venv/bin/python scripts/workspace_api_example.py \
  --kind site --file data/examples/phase5/site.csv
```

需要确认该模拟样例时加`--confirm`；其余类型按依赖顺序替换kind/file。密码沿用`SUPPLYGUARD_DEMO_PASSWORD`配置，示例仅访问本机3100与项目内指定文件。源码展示了真实登录、字段映射、multipart上传、幂等键与错误处理，不调用外部系统。
