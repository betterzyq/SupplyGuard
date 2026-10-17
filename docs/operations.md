# SupplyGuard P6 运行与交付手册

适用本仓库的验收实例，前置P1–P5已通过，数据库已位于`f6a7b8c9d0e1`。P6无DDL、无新依赖、无模型重训。全部操作限定SupplyGuard；不运行原8000/3000实例的控制命令，不改共享环境或GPU。

## 启动、更新与关闭

```bash
cd /root/autodl-tmp/SupplyGuard
make acceptance-status
make acceptance-up
```

API与Web仅监听服务器`127.0.0.1:8100/3100`。电脑通过VS Code Remote-SSH的Ports面板转发3100，打开面板实际显示的本地地址。SSH主机/端口从AutoDL实例SSH连接信息取得；不要猜22或把服务器localhost当电脑地址。完整说明见[人工验收](manual-acceptance.md)。已有演示账号不改密码；默认enterprise@example.com与admin@example.com，初始演示密码password123，已改密码时使用已有密码。

源文件变化后，先完成自测，再执行以下仅作用于启动器已验证进程的命令。不要同时运行两个Next生产构建。

```bash
make acceptance-down
make acceptance-up
make acceptance-status
```

端口被未归属进程占用会失败，不会停止占用者。PID/启动时间/工作目录/进程组/启动标识均核验；不能使用killall/pkill。停止不会停止PostgreSQL/Neo4j/Redis/Qdrant，也不会删业务数据。运行日志在`.local/acceptance/services/`，错误排查只看本项目日志，勿展示.env/token。

## 依赖与离线范围

- 登录和工作区持久化依赖本地API及PostgreSQL；浏览器导入/任务/报告/订阅均须服务可用。
- 核心地图的GeoJSON、字体、样式均为本地资源，MapLibre软件WebGL可测；不能用离线缓存代替在线鉴权。
- 核心三故事/仿真不调用外部服务；历史预测需要已有P4锁定数据/模型与本地依赖。全新机器首次安装与数据下载需要网络。
- 浏览器完全断网时只允许已缓存合成地图/轨迹；其他页面解释离线受限，不能写入。无Service Worker，不保证离线首次加载/刷新未缓存页面。
- 决策助手、语义检索仍需配置对应LLM/embedding与向量/图服务；此次未做付费在线问答性能/精度验证，不是断网核心演示依赖。

## 数据与备份

P3原始模拟快照在`.local/simulation-runs`，按租户/个人隔离；主动共享后P5另存企业副本。P4数据在`data/external/dataco-v5`，固定模型由`.local/prediction/active.json`引用。企业数据、任务、审计、导入批次、报告字节、本地事件在PostgreSQL `sg5_*`；企业知识库仍由原文档/向量/图流程管理。

P6更新前已将**上一人工通过的生产前端产物**和项目库备份保存至`.local/releases/p5-accepted/`。`checkpoint.json`记录哈希及前端指纹，`web-build.tar.gz`不含构建cache。`before-p6.dump`是新增P6验收记录前的完整项目库备份，已核对pg_restore目录；这个新备份没有声称做过实际恢复。P5原始迁移备份已在独立库真实恢复，见[迁移记录](phase5-migrations.md)。备份含本企业数据，权限0600，不作公开竞赛素材。

P6源码交付包`.local/releases/p6-source.tar.gz`及`.local/acceptance/phase-6/source-snapshot.json`覆盖可版本化文件、文件SHA、Git基线和前端构建指纹。当前工作树未提交，不伪造版本标签。包排除.env、私钥、软链接、.local、依赖、外部原始数据；**它不是完整运行环境/数据库/文档库备份**。迁移前P5源码并无完整归档，只保存了当时清单和生产前端；不能声称支持一键完整回滚。

## 回退原则

P6无数据库变更；首选保留当前数据库、停验收实例，修复或撤回P6新增页面/导航，再构建。不得git reset --hard或覆盖用户改动。需要临时展示旧前端时，可在单独目录人工检验并解包保留的P5生产产物，使用相同依赖和受控启动流程；当前`acceptance-up`会按当前源码重建，不能只替换BUILD_ID或篡改指纹伪装回滚。生产前端备份不是自动恢复命令。

数据库恢复必须先再做当前备份，恢复到**新的SupplyGuard专用库**并核验租户、任务、报告与版本，确认后安排切换；不要在现有库执行pg_restore --clean/降级。恢复旧备份会失去之后的业务变更，P6不自动执行。详细隔离恢复程序沿用P5手册。

## 日常维护与未交付能力

报告24小时有效，到期生成新报告；当前保留审计字节，无自动清理作业。验收会新建明确标记P6/P5的模拟任务/报告/测试库，不删除历史。容量增长时需制定备份保留、工作区归档和测试库清理策略，再由维护人员处理自己确认归属的对象。

真实ERP/承运商、外部Webhook投递、实际采购执行、收费、生产HA/SLA、制造业模型迁移、全量在线RAG金标评测未交付。上传不会自动替换模拟地图；模型未超越所有基线；1000站点/2000路线是几何交互负载，不是企业并发容量。最终性能数据见[P6实测报告](reports/phase-6.md)。
