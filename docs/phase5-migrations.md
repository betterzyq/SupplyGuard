# P5 数据库迁移、备份与恢复

本次从`e5f6a7b8c9d0`升级至`f6a7b8c9d0e1`。只新增9个`sg5_`表、约束及索引，不改旧业务表结构，不重置账号、图谱或向量。实体表、引用表、任务、批次、报告、幂等记录、业务审计、本地事件及订阅均带tenant。

迁移定义是版本目录固定SQL快照`phase5_schema.sql`，避免未来ORM变化偷偷改写历史迁移。后续字段更改必须新增revision。

## 已完成的验证

1. 在本工具创建的独立PostgreSQL库执行upgrade head→downgrade e5→upgrade head，验证新增9表正确移除/重建，旧表集合保留。
2. 对项目`supplyguard`库运行本地既有pg_dump，完整custom格式备份，权限0600，校验大小、SHA256和pg_restore目录。
3. 仅在原项目revision正确且隔离验证通过后应用新增迁移。
4. 将备份实际恢复到另一个新建独立库，验证原e5版本、旧表及非空核心数据。没有在项目库尝试恢复或回退。

证据位于`.local/acceptance/phase-5/migration-test.json`、`migration-apply.json`、`backup-restore.json`。其中保存备份路径/哈希与测试库名，不包含数据库密码；原始备份可能含项目私有内容，不上传或公开下载。

## 日常验收

```bash
cd /root/autodl-tmp/SupplyGuard
make phase5-check
make phase5-audit
```

`phase5-check`创建自己命名的独立测试库，进行完整迁移与真实事务/API测试，不重建项目库。测试库保留以供审计，不清理共享数据库或终止他人连接。

当前项目迁移已应用；`make phase5-db-apply`会检测版本并返回已应用，不会重复建表。未来新副本需先验证相同初始版本/专属环境，再按`phase5-check`→`phase5-db-apply`执行；该动作包含自动备份。备用手工`alembic upgrade head`不替代本阶段的备份验证入口。

## 回滚操作（仅说明，不在本次项目库执行）

回退会移除新增P5表及其中数据，必须先停止本项目验收写入、备份当前数据库并校验，保存P5业务数据后再人工决定。不要把迁移前备份直接覆盖到已有新业务的项目库。

```bash
# 只停止本项目验收进程，先确认没有其他项目/业务连接受影响。
make acceptance-down
# 先完成当前项目库备份及新增数据保留；不要跳过该步骤。
# 确认需要移除P5数据时，在本项目专属环境执行已验证的降级：
DEBUG=false .venv/bin/alembic downgrade e5f6a7b8c9d0
```

代码也应回到已保存的P4工作区版本后再启动；不能用`git reset --hard`丢弃原有人工作区修改。恢复全库备份应先还原到新的独立库核对，再根据人工运维决定切换，不对在线项目库执行drop/recreate。需要恢复P5时使用其当前备份，不用迁移前备份冒充包含新增记录。
