# SupplyGuard 无 Docker 本地环境

当前服务器使用独立 Conda 环境 `supplyguard`。Python 3.11.17、uv、
Node.js 22.21.1、npm 和后端开发依赖已安装；前端依赖按
`apps/web/package-lock.json` 安装到该目录的 `node_modules`。

## 使用环境

```bash
cd /root/autodl-tmp/SupplyGuard
conda activate supplyguard
```

如果新终端尚未加载 Conda，先运行：

```bash
source /root/miniconda3/etc/profile.d/conda.sh
conda activate supplyguard
```

项目 `.venv` 是指向 `/root/miniconda3/envs/supplyguard` 的软链接，
现有 `uv run`、`make migrate` 等命令会使用这个独立环境。
不要删除或重建 `.venv`。环境激活钩子会暂时取消服务器的
`DEBUG=release`，使项目读取 `.env` 的布尔配置；退出环境时恢复原值。
`socksio` 已加入依赖，支持服务器继承的 SOCKS 代理设置。

后续同步 Python 依赖时使用：

```bash
uv sync --locked --inexact
```

`--inexact` 保留 Conda 环境中的 uv、pip 等额外工具。

## 本地基础设施

在项目目录使用以下命令（当前服务器用户为 root）：

```bash
make local-up       # 启动；重复执行不会重复创建进程
make local-status   # 查看状态
make local-restart  # 重启本项目服务
make local-down    # 停止本项目服务，保留数据
```

原有 `make up`、`make down`、`make logs` 仍对应 Docker Compose，
这台服务器请使用上述 `local-*` 命令。

| 服务 | 版本 | 本机端口 |
| --- | --- | --- |
| PostgreSQL | 16.15 | 5432 |
| Redis | 7.4.7 | 6379 |
| Qdrant | 1.19.2，静态 musl 构建 | 6333；gRPC 6334 |
| Neo4j Community + APOC | 5.26.32；Java 21 | HTTP 7474；Bolt 7687 |
| MinIO | RELEASE.2025-09-07T16-13-09Z | API 9000；控制台 9001 |

五项服务都仅绑定 `127.0.0.1`，运行账户为 `supplyguard-svc`。
Qdrant、Neo4j 和 MinIO 限制了线程/CPU 使用，数据库配置用于本地开发。
开发数据库密码沿用 `.env.example`，不要直接作为公网生产部署使用。

运行时、数据和日志存放在数据盘的 `.local/`，已经加入 Git 忽略规则：

- `.local/runtime/`：基础设施可执行文件；`/opt/supplyguard-runtime` 为兼容软链接。
- `.local/data/`：持久化数据；`/var/lib/supplyguard` 为兼容软链接。
- `.local/logs/`：服务日志；`/var/log/supplyguard` 为兼容软链接。
- `/etc/supplyguard/`：Redis 和 Neo4j 配置。
- `/run/supplyguard/`：PID 和进程身份记录。

为了让服务账户访问项目内运行时，`/root` 对 `supplyguard-svc` 添加了
仅目录穿越权限的 ACL，没有向它授予 `/root` 的目录列举权限。
无需修改 `base`、`FinRisk` 或其他项目环境。

实例重启后需要重新执行 `make local-up`；未配置系统自启动。
停止服务不会删除 PostgreSQL、Redis、Qdrant、Neo4j 或 MinIO 的数据。

## 已完成的初始化与验证

数据库迁移已到 `e5f6a7b8c9d0`，演示数据已写入。
Neo4j 演示图已建好：5 个供应商、4 种物料、3 个产品、10 个订单、
3 个客户、44 条关系。Qdrant 的 `supplyguard_chunks` 集合已创建，
向量维度为 `.env` 的 4096；文档向量尚未摄取。

后端启动、前端生产构建（18 个页面）、通过前端代理登录并查询图谱、
授权回归检查均已验证。登录示例：
`procurement_manager@example.com` / `password123`。

`.env` 权限为 `0600`，JWT 密钥已随机生成。请自行填写真实的
`DEEPSEEK_API_KEY` 和 `EMBEDDING_API_KEY`。

```bash
make dev-check
```

未填写上述 Key 时，该命令的 LLM、Embedding 两项会失败，并返回
非零退出码；五项基础设施检查应通过。填写 Key 后可以执行：

```bash
make ingest-seed-docs
```

更换 Embedding 模型时需同时确认 `EMBEDDING_MODEL`、`EMBEDDING_DIM`
与现有 Qdrant 集合维度相符。

## 启动应用

两个终端分别激活 `supplyguard` 环境后执行：

```bash
cd /root/autodl-tmp/SupplyGuard
make api           # 后端 8000
```

```bash
cd /root/autodl-tmp/SupplyGuard
make web           # 前端 3000
```

先确认端口空闲。前端配置默认代理到 `http://127.0.0.1:8000`。
本次验证使用的前后端进程会在交付前停止；基础设施保持运行。

再次构建前端时可限制资源占用：

```bash
cd apps/web
CIRCLE_NODE_TOTAL=3 NEXT_TELEMETRY_DISABLED=1 OMP_NUM_THREADS=2 \
  taskset -c 0,1 nice -n 10 npm run build
```
