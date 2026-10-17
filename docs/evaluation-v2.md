# P4 检索与权限评分修订

新评分器 `enterprise-scorer-v2` 和角色策略 `enterprise-v2` 独立版本化。旧 `data/eval/supplyguard_eval.jsonl` 及历史数据库分数原样保留，管理员页面明确废弃其岗位权限口径，不把旧分数重新贴成新策略效果。旧 Web 运行入口返回409，历史查询继续受管理员与租户约束。

## 修正内容

| 原问题 | 新行为 |
|---|---|
| 空金标准/无题目给1 | 对该指标返回 NA；逐项保存有效分母，异构任务不补0混算 |
| 重复结果给重复 NDCG/precision 信用 | 结果槽位保留；重复证据仅第一次得分，NDCG不超过1 |
| 引用用子串匹配，且把 recall 叫 accuracy | chunk ID 或 `document#index` 精确身份匹配；分别报告 citation_precision / citation_recall。旧 accuracy 名在新评分器中仅为 precision 兼容别名 |
| 路径包含任一节点就命中 | 完整、有向、带类型的节点序列一致；反向、部分、同前缀不同 ID、错类型、插入风险节点均不得分 |
| 无证据与拒绝合并，预期拒绝改变输出 | 实际观察结果是 allow / denied / no_evidence / error；不得读取 `should_be_blocked` 来决定检索答案。正确拒绝必须真的 denied，无证据和错误均不能算拒绝成功 |
| 内部岗位的敏感词视作越权 | 移除旧岗位内容黑名单；同租户两类成员共享业务文档，管理员也不能跨租户 |
| 把写入记忆种子当作命中 | 只能由实际 memory evidence 或明确观察到的 session hit 得分，不依据提示词/预期种子/“历史记忆”几个字得分 |
| 评测用户只按邮箱加载 | 每个执行用户查询追加发起管理员 tenant 条件，防止取到其他租户同邮箱用户 |

Precision@K 的分母是实际返回的前K个结果槽位数，不补满K；Recall 是金标准唯一证据数；NDCG 同一证据仅首次得分。必须保留这些定义，不能与其他分母的指标直接比较。

## 已交付的金标准

`data/eval/enterprise-v2.json` 有25项：

- 8 个图金标准：4 个供应商完整多跳影响、2 个实际延迟事件路径、2 个替代关系；来自当前 `graph_seed.json` 的精确连接，保存种子 SHA256。SUP-002 不再复制 SUP-001 的路径，交付延迟以 Supplier→DeliveryEvent→Order 描述。
- 6 个权限契约：admin/enterprise 各自测试同租户文档、跨租户文档、管理员功能；调用真实权限函数。
- 11 个评分契约：完整路径与负例、引用前缀/多引/少引、无证据/错误不算拒绝。

**17 个契约通过是评分逻辑与权限函数检查，不是实际 RAG 准确率；8 个图金标准尚未对当前在线 Neo4j 运行。** 不重建图谱、不假定线上数据库恰好等于种子文件。

`data/eval/graph-enterprise-v2.jsonl` 将8个图金标准转为可被现有评测器直接加载的带自然语言问题、查询类型、实体、完整路径和版本的逐题格式；显式 `--dataset` 选择后可在线运行，本次仍标记未实测。

`data/eval/rag-enterprise-v2.jsonl` 另外提供9个基于种子文档具体事实的问题，全部使用企业角色：报价门槛、复核频率、延误天数、罚款、财务折扣、质量合格率、分散供应商、两家供应商计划交付。每题保存具体证据文本、来源 slug 与文本哈希，避免泛泛的“主要内容”和“变体题”扩数量。当前默认数据集切到这一版本；不能用整份文档所有块作为已标定的证据。

在线运行会将 gold_span 严格解析为当前租户中实际包含该文本的 chunk ID；原文/当前分块不存在则明确 `annotation resolution failed`。本阶段没有付费嵌入、LLM裁判、向量重建或真实检索质量实测，因此页面不展示对应准确率。记忆评分逻辑已修正并有负例回归；尚未重新测量在线记忆检索命中率。

## 检查入口

```bash
cd /root/autodl-tmp/SupplyGuard
make phase4-check
make phase4-audit
```

管理员打开 `/benchmarks`，可查看契约结果与金标准待实测状态；企业用户仅能访问 `/prediction` 公开预测验证。离线契约 API `/api/v1/prediction/evaluation-contracts` 需要管理员权限。

在线检索实验使用明确的已审阅金标准文件与现有本租户索引，独立于本阶段默认验收命令。例如管理员维护时可使用：

```bash
DEBUG=false OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 .venv/bin/python scripts/run_benchmark.py \
  --dataset data/eval/rag-enterprise-v2.jsonl --mode secure_rag --limit 9
```

该命令会访问现有数据库、向量与配置的 embedding 服务，可能产生模型调用费用；本次未运行，不能将离线契约结果替代它。运行前应核对现有索引是否包含相同证据，避免为评测重置业务数据。新协议结果包含版本、逐项指标有效分母及观察决策；历史结果不混算。

如需以后对照现有租户图谱验证8题图金标准，可独立运行（本次未运行，不需重建图谱）：

```bash
DEBUG=false OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 .venv/bin/python scripts/run_benchmark.py \
  --dataset data/eval/graph-enterprise-v2.jsonl --mode graphrag --top-k 20 --limit 8
```
