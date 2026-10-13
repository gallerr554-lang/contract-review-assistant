# 当前副本本地部署说明

> 本文仅针对当前目录中的代码和配置。不要依赖其他项目目录，也不要把真实密钥提交到版本库。

## 1. 环境要求

- Docker Desktop 或 Docker Engine，支持 Docker Compose v2。
- 建议至少 4 GB 可用内存和 5 GB 可用磁盘；首次构建需要拉取镜像和系统包。
- 本机端口默认使用：前端 `8080`、后端 `8000`、PostgreSQL `5432`。
- 访问外部模型 API 需要容器具备出站 HTTPS 网络。

宿主机不需要安装 Python、Node、LibreOffice、Poppler 或 Tesseract；后端镜像已包含文档转换、OCR、中文/英文字库和字体。

## 2. 环境配置

```bash
cp .env.example .env
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

把生成的 Fernet Key 写入 `.env`，并配置以下项目：

| 变量 | 要求 |
| --- | --- |
| `COMPOSE_PROJECT_NAME` | 每个项目副本必须唯一；决定容器、网络和 PostgreSQL 卷前缀 |
| `POSTGRES_DB`、`POSTGRES_USER` | 数据库名和账号 |
| `POSTGRES_PASSWORD` | 必填，生产使用强随机密码 |
| `MODEL_CONFIG_ENCRYPTION_KEY` | 必填、长期稳定；丢失后数据库内已加密模型 Key 无法恢复 |
| `INITIAL_ADMIN_EMAIL`、`INITIAL_ADMIN_PASSWORD` | 必须同时填写或同时留空；生产使用强密码 |
| `MODEL_PROVIDER/NAME/API_BASE/API_KEY` | 默认模型；Key 可先留空，管理员稍后在模型页保存 |
| `CORS_ORIGINS` | 浏览器允许来源，生产改为正式 HTTPS 域名 |
| `*_BIND_ADDRESS`、`*_PORT` | 端口和监听地址；数据库与后端默认只绑定 127.0.0.1 |
| `MAX_FILE_SIZE_MB`、`MAX_REVIEW_CHARACTERS` | 文件和解析文本上限 |
| `OCR_*` | OCR 语言、最小文本阈值和超时 |

根目录 `.env` 供 Docker Compose 使用；`backend/.env` 仅供宿主机直接运行后端使用。两者互不自动同步。不要在日志、截图或文档中输出完整密码、API Key 或 Fernet Key。

## 3. 启动与访问

先检查 Compose 展开是否有效。因为完整输出会展开敏感值，日常建议使用静默校验：

```bash
docker compose config >/dev/null
docker compose up -d --build
docker compose ps
```

访问地址：

- 前端和登录页：<http://localhost:8080>
- 经前端 Nginx 代理的数据库健康检查：<http://localhost:8080/api/health/db>
- OCR 运行时：<http://localhost:8080/api/health/runtime>
- 后端直连健康检查：<http://localhost:8000/api/health/db>

首次启动顺序为 PostgreSQL 健康 → 后端自动迁移并健康 → 前端启动。后端入口会校验数据库变量、Fernet Key 和初始化管理员变量组合。

## 4. 状态、日志与停止

```bash
docker compose ps
docker compose logs --tail=200 postgres backend frontend
docker compose logs -f backend
docker compose stop
docker compose start
docker compose down
```

`docker compose down` 删除容器和项目网络，但保留 PostgreSQL 命名卷和当前目录 `storage`。不要执行 `docker compose down -v`，除非已经确认要永久删除数据库且完成备份。

## 5. 数据持久化与副本隔离

### PostgreSQL

数据库位于 Docker 命名卷：

```text
<COMPOSE_PROJECT_NAME>_postgres-data
```

复制代码目录不会复制命名卷。若新副本沿用相同 `COMPOSE_PROJECT_NAME`，会复用同一批容器、网络和数据库卷；因此复制后第一项操作应是修改新副本的项目名。

本次检查中，修复前默认项目名 `code` 曾复用既有 `code_postgres-data`。该旧卷包含历史用户、任务、风险、规则、场景和模型配置，现仍保留且未删除。修复后当前副本创建 `contract-review-current_postgres-data`：初始化时任务和风险为 0；全链路验证后新增了 1 个测试任务和 6 条风险。

### 文件存储

```text
宿主机 ./storage  <->  容器 /app/storage
```

- `storage/contracts/<upload_id>/`：原件、附件、预览 PDF 和 `manifest.json`。
- `storage/results/<task_id>/`：带标记的 DOCX/PDF。
- `storage/temp`、`storage/tmp`：转换、渲染的临时工作文件。

当前目录复制时已有的文件仍存在，但新数据库不会自动获得与这些文件对应的任务记录。文件和数据库必须作为一组备份与恢复，否则会出现数据库记录缺文件或存储文件无数据库记录。

### 备份建议

生产环境至少同时备份：

1. PostgreSQL 逻辑备份（`pg_dump`）或卷快照；
2. 整个 `storage` 目录；
3. `.env` 中长期稳定的 `MODEL_CONFIG_ENCRYPTION_KEY`，存入密钥管理系统而非普通备份包。

恢复演练需验证迁移版本、用户登录、历史任务结果、原文页和下载文件。

## 6. Alembic 迁移

当前唯一 head：`20260806_0009`。后端容器每次启动会自动执行：

```bash
alembic upgrade head
```

检查迁移状态：

```bash
docker compose exec backend alembic current
docker compose exec backend alembic heads
```

空库会按 0001 → 0009 顺序创建表、默认 8 条规则、3 个场景、全局模型配置和用户管理操作日志表。迁移失败时后端不会启动，应先查看后端日志；不要手工跳过迁移版本或直接改 `alembic_version`。

## 7. 功能验证

基础验证：

```bash
curl -fsS http://localhost:8080/api/health/db
curl -fsS http://localhost:8080/api/health/runtime
```

代码验证：

```bash
cd frontend
npm ci
npm run build

cd ../backend
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q app tests alembic
```

本次实际结果：前端构建成功；后端 59 项测试通过；三个容器健康；自动迁移成功；管理员登录、用户管理权限与会话失效、活动模型读取、TXT 上传、真实 DeepSeek 审查、风险定位和 PDF 下载均成功。

## 8. 常见故障排查

### Compose 配置失败

- 检查 `.env` 是否存在；`POSTGRES_DB/USER/PASSWORD` 和 `MODEL_CONFIG_ENCRYPTION_KEY` 不能为空。
- 初始化管理员邮箱和密码必须同时存在。
- Fernet Key 必须由 `Fernet.generate_key()` 生成，不能使用普通字符串。

### 端口占用或启动了错误数据

- 用 `docker compose ps` 核对容器名前缀是否等于 `COMPOSE_PROJECT_NAME`。
- 每个复制目录设置唯一项目名。
- 修改端口或停止占用者，不要删除未知数据卷。

### 后端不健康

- 查看 `docker compose logs --tail=200 backend postgres`。
- 确认日志中出现 `Applying database migrations...`、迁移成功和 `Application startup complete`。
- 数据库密码修改后，旧卷内 PostgreSQL 账号密码不会自动改变；应按数据库变更流程处理。

### OCR 不可用

- 请求 `/api/health/runtime` 检查 `pdftoppm`、`tesseract`、`chi_sim`、`eng`。
- 官方后端镜像已安装这些组件；自定义基础镜像时必须保留 Dockerfile 的安装与构建校验。

### DOC/DOCX 预览或下载失败

- 检查后端日志中的 LibreOffice/soffice 错误。
- 确保 `storage` 可写且磁盘空间充足。
- 旧版 DOC 文本解析还依赖 `antiword`。

### 模型不可用

- 管理员在模型配置页确认只有一个启用模型，Provider、模型名、地域 Base URL 匹配。
- 列表中的 `api_key_source` 应为 `encrypted` 或 `environment`，不能为 `missing`。
- 检查云服务器出站 HTTPS、防火墙、DNS、API 配额和模型权限。
- 不要把完整 Key 打进命令行或日志；连接测试接口只应返回脱敏错误。

### 历史任务处理中断

任务运行于 FastAPI 进程内。服务重启后，启动逻辑会把遗留 `PROCESSING` 任务标为 `FAILED` 并允许重新审查；不会从中断位置继续。

## 9. 云服务器部署前清单

- 为服务器副本设置唯一且稳定的 `COMPOSE_PROJECT_NAME`。
- 替换本地数据库口令、管理员密码、模型 Key 和 Fernet Key；通过云密钥管理注入。
- 使用正式域名和 HTTPS 反向代理，收紧 `CORS_ORIGINS`；不要将 PostgreSQL 暴露公网。
- 将前端、后端端口按网络边界绑定，配置防火墙、安全组和 TLS。
- 为 PostgreSQL 卷和 `storage` 使用持久磁盘并建立定期备份、保留期和恢复演练。
- 配置容器日志收集、磁盘/内存/健康检查、模型调用失败率和费用监控。
- 评估将进程内后台任务迁移到持久任务队列，避免部署重启导致任务失败。
- 制定数据库迁移发布、密钥轮换、管理员账号、配置删除和审计流程。
- 对上传合同的敏感数据制定加密、访问控制、留存、清理和合规策略。
