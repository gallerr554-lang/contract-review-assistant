# 合同审查助手云服务器部署

本目录是云服务器所需的最小部署包。服务器不需要项目源码、Node.js 或 Python，只需要 Docker Engine、Docker Compose v2，以及可以拉取配置镜像仓库的网络。

- `${BACKEND_IMAGE_REPOSITORY}:${BACKEND_IMAGE_TAG}`
- `${FRONTEND_IMAGE_REPOSITORY}:${FRONTEND_IMAGE_TAG}`
- `postgres:16-alpine`

前后端使用独立的镜像仓库与版本变量：`BACKEND_IMAGE_REPOSITORY`、`BACKEND_IMAGE_TAG`、`FRONTEND_IMAGE_REPOSITORY`、`FRONTEND_IMAGE_TAG`。生产部署应使用明确版本号，不要把 `latest` 作为正式版本依据。

## 1. 首次准备

将本目录中的三个文件上传到服务器同一目录，例如 `/opt/contract-review/`：

```text
compose.production.yml
.env.example
README.md
```

然后执行：

```bash
cd /opt/contract-review
cp .env.example .env
mkdir -p storage
```

编辑 `.env`，至少填写强随机数据库密码、长期稳定的 Fernet 加密密钥、初始化管理员账号密码、正式域名、镜像仓库和前后端明确版本。不要把 `.env` 提交到版本库或发送到不安全位置。

如果使用阿里云 ACR 私有仓库，由服务器管理员使用 ACR 登录用户名登录对应的公网或 VPC 地址。密码由命令交互输入，不应写入脚本或文档。

## 2. 配置检查与启动

完整 `docker compose config` 会展开环境变量和敏感值，建议静默检查：

```bash
docker compose --env-file .env -f compose.production.yml config >/dev/null
docker compose --env-file .env -f compose.production.yml pull
docker compose --env-file .env -f compose.production.yml up -d --no-build
docker compose --env-file .env -f compose.production.yml ps
```

后端会在 PostgreSQL 健康后自动执行 `alembic upgrade head`，然后启动 FastAPI。前端等待后端健康后启动，并通过 Nginx 把 `/api` 转发到内部服务 `backend:8000`。

只有前端端口会发布到宿主机。FastAPI 和 PostgreSQL 没有 `ports` 配置，不能从公网直接访问。

## 3. 访问与日志

若 `FRONTEND_PORT=8080`：

```text
http://服务器地址:8080
http://服务器地址:8080/api/health/db
http://服务器地址:8080/api/health/runtime
```

生产环境建议在云负载均衡或宿主机 HTTPS 反向代理后提供服务，并在安全组中仅开放必要的 HTTP/HTTPS 端口。

```bash
docker compose --env-file .env -f compose.production.yml logs --tail=200 postgres backend frontend
docker compose --env-file .env -f compose.production.yml logs -f backend
```

## 4. 数据持久化

- PostgreSQL：命名卷 `<COMPOSE_PROJECT_NAME>_postgres-data`。
- 合同、附件、预览和结果：当前部署目录下的 `./storage`，挂载到后端 `/app/storage`。

必须保持 `COMPOSE_PROJECT_NAME` 和部署目录稳定。数据库卷与 `storage` 必须一起备份和恢复。

正常停服可执行：

```bash
docker compose --env-file .env -f compose.production.yml down
```

该命令不会删除命名卷或 `storage`。禁止在日常更新中使用 `down -v`，也不要删除部署目录中的 `storage`。

## 5. 更新到新版本

先完成 PostgreSQL 与 `storage` 备份，再只修改需要升级的服务版本。例如仅升级前端时，把 `.env` 中 `FRONTEND_IMAGE_TAG` 从 `v1.0.0` 改为 `v1.0.1`，保持 `BACKEND_IMAGE_TAG` 不变：

```bash
docker compose --env-file .env -f compose.production.yml config >/dev/null
docker compose --env-file .env -f compose.production.yml pull frontend
docker compose --env-file .env -f compose.production.yml up -d --no-deps --no-build frontend
docker compose --env-file .env -f compose.production.yml ps
docker compose --env-file .env -f compose.production.yml logs --tail=200 frontend
```

`up -d --no-deps frontend` 只会重建前端容器，不会重建后端或 PostgreSQL，也不会删除 PostgreSQL 命名卷或 `./storage`。升级后端时才会在后端新容器启动时自动应用数据库迁移。

如需回滚前端，将 `FRONTEND_IMAGE_TAG` 改回上一个明确版本后重新执行前端 `pull` 和 `up -d --no-deps --no-build frontend`。若后端新版本包含不可逆数据库变更，应按发布说明和备份恢复流程处理，不能只回滚镜像。
