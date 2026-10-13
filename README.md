# 合同审查助手

Vue 3 + FastAPI + PostgreSQL 的合同审查工作台。当前版本已完成用户权限与管理员用户管理、配置驱动的合同审查闭环、审查记录与风险反馈，以及管理员维护的全局模型配置能力。

## 系统演示
- 工作台页面：
<img width="2772" height="1722" alt="image" src="https://github.com/user-attachments/assets/5440e73b-d81c-4260-be73-9d27a4cad2d1" />
<img width="2760" height="1716" alt="image" src="https://github.com/user-attachments/assets/cf6e4e7c-9c87-4a6e-ad8a-8bc562b96daa" />
<img width="2776" height="1724" alt="image" src="https://github.com/user-attachments/assets/6b283f35-07ee-4602-9b78-5c4e78ecd71c" />
<img width="2774" height="1712" alt="image" src="https://github.com/user-attachments/assets/9893fc12-a979-4237-bb23-ba715b03148b" />

- 审查配置页面：
<img width="2774" height="1724" alt="image" src="https://github.com/user-attachments/assets/8ee4ee12-19ea-4bde-80ba-7e4fc032d9e9" />
<img width="2784" height="1728" alt="image" src="https://github.com/user-attachments/assets/728ca6dc-3faf-4207-91cb-f9a73250dc12" />

- 系统配置页面：
<img width="2780" height="1726" alt="image" src="https://github.com/user-attachments/assets/f0d50db0-d147-49d9-a42b-d39218a432b8" />
<img width="2764" height="1728" alt="image" src="https://github.com/user-attachments/assets/d5b5d4b3-b73d-470c-907a-966ecf31c3db" />


## 已实现

- 上传 1 份主合同和最多 3 份附件，校验格式、数量、大小和空内容；
- 解析 TXT、DOCX、PDF，并在 macOS `textutil` 或 Linux `antiword` 可用时解析 DOC；扫描版 PDF 可通过 Poppler + Tesseract OCR 识别；
- 邮箱、密码和一次性图片数字验证码注册登录，使用 PBKDF2 密码摘要和数据库会话令牌；
- 普通用户可使用合同审查和本人审查记录；管理员额外管理系统模型、审查规则与场景；前端路由、导航和后端接口均执行角色校验；
- 管理员可分页查询用户，查看任务数量，调整角色和状态、重置他人密码；停用和重置密码会撤销目标用户会话，角色/状态/密码操作写入审计日志；
- 创建幂等审查任务，展示五个处理节点、进度、成功和失败状态；
- 业务层统一通过 `ModelService` 调用当前启用的模型 Provider；
- 校验模型 JSON、规则 ID、风险等级、重复项和原文定位；
- 在 PostgreSQL 保存任务快照、总结和风险明细；
- 按原型实现上传表单、原位进度切换、失败重试和响应式结果弹层；
- 展示风险统计、审查总结、合同原文高亮、规则引用、风险说明和修改建议；
- 合同原文按页延迟加载，可切换原版式页面和结构化风险文本；DOC/DOCX 以转换后的真实 PDF 页为边界，原版式模式保留段落和表格排版；
- PDF 页面保留原始页码，OCR 状态和文本来源随任务快照保存，风险卡片、原文标记和页码双向联动；
- 后端生成带高亮和风险批注的 PDF 标记版；PDF 直接保留原页，Office/TXT 先经 LibreOffice 转换；
- 提供审查规则的查询、新增、编辑、启停和删除能力；
- 提供审查场景的查询、新增、编辑、启停、删除和关联规则能力；
- 合同审查页面动态加载当前启用且包含启用规则的场景；
- 新任务将场景名称、System Prompt 和启用规则完整保存到任务快照，执行和重试只读取快照，后续配置修改不影响历史任务；
- 查询历史审查任务，支持按合同名称或任务编号搜索、按状态筛选、分页和直接查看历史结果；
- 结果页支持风险等级筛选、详情展开收起、风险与合同原文双向定位；
- 支持对单条风险提交“反馈有误”，反馈与任务、风险和规则关联保存；
- 提供 OpenAI、DeepSeek、Qwen 模型配置的查询、新增、编辑和启停能力，审查业务继续统一经过 `ModelService`；
- 全系统共用一套模型配置，仅管理员可维护；API Key 使用 Fernet 密文保存，列表接口只返回掩码；
- 全系统最多只有一个当前启用模型；默认 DeepSeek 配置仍可从环境变量读取 Key；
- 模型页支持管理员执行脱敏连接测试；Qwen 支持中国、新加坡和美国地域的百炼 OpenAI 兼容 Base URL；
- 新任务只保存 Provider、模型名称、API Base 和生成参数快照，不复制 API Key；
- DOCX 默认下载保留原格式的高亮批注版，PDF 默认下载带标记 PDF；DOCX 可额外导出 PDF；
- Prompt 由独立 Prompt 模块组装，业务层不直接调用具体模型 Provider。

## 本地 Docker 部署

本地和云服务器使用同一套镜像及 Compose 结构。后端镜像已包含 LibreOffice Writer、Poppler、Tesseract、`chi_sim`、`eng`、Noto CJK 字体和 `antiword`。

1. 创建本地配置：

```bash
cp .env.example .env
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

将生成值写入 `.env` 的 `MODEL_CONFIG_ENCRYPTION_KEY`，并设置非空的 `POSTGRES_PASSWORD`。本地初始化管理员示例为 `admin@local.test`，密码只写入未提交的 `.env`。`MODEL_API_KEY` 可作为默认 DeepSeek Key，也可留空并由管理员在模型配置页填写。`INITIAL_ADMIN_EMAIL` 和 `INITIAL_ADMIN_PASSWORD` 必须同时填写。

`COMPOSE_PROJECT_NAME` 用于隔离容器、网络和 PostgreSQL 命名卷。复制项目到新目录后，应为每个副本设置不同的值，避免多个同名目录意外复用同一个数据库卷。

2. 一键构建并启动：

```bash
docker compose up -d --build
docker compose ps
```

后端会在 PostgreSQL 健康后自动执行 `alembic upgrade head`，成功后再启动 FastAPI。前端等待后端健康后启动，Nginx 将浏览器的 `/api` 请求转发到 Compose 内部的 `backend:8000`。

访问 [http://localhost:8080](http://localhost:8080)，后端健康检查为 [http://localhost:8080/api/health/db](http://localhost:8080/api/health/db)。

查看日志与停止服务：

```bash
docker compose logs -f backend frontend postgres
docker compose down
```

`docker compose down` 不会删除 PostgreSQL 命名卷或 `./storage` 文件。不要在普通停服时使用 `docker compose down -v`。

当前最新迁移版本为 `20260806_0009`。模型配置为全局配置，审查记录及上传材料仍按用户隔离。

## 云服务器部署

1. 将代码和 `.env.example` 部署到服务器，复制为 `.env`，不要提交实际 `.env`。
2. 设置强随机 `POSTGRES_PASSWORD`、长期稳定的 `MODEL_CONFIG_ENCRYPTION_KEY`、正式管理员邮箱和密码。
3. 将 `CORS_ORIGINS` 改为正式 HTTPS 域名；按反向代理方案设置 `FRONTEND_PORT` 和绑定地址。
4. 执行 `docker compose up -d --build`，由容器自动等待 PostgreSQL、执行 Alembic 迁移并启动服务。
5. 为 PostgreSQL 命名卷和 `./storage` 配置持久磁盘、定期备份和恢复演练；生产环境通过反向代理终止 TLS。

同一套 Compose 不依赖宿主机绝对路径。容器间数据库和 API 通信使用服务名，浏览器统一通过前端域名的 `/api` 访问后端。

## 清理审查历史

清理脚本不会删除用户、模型、规则、场景或场景规则关联。先预览统计，再使用固定确认口令执行：

```bash
docker compose exec backend python -m scripts.cleanup_review_data --dry-run
docker compose exec backend python -m scripts.cleanup_review_data --confirm DELETE_REVIEW_HISTORY
```

脚本可重复执行；第二次执行会报告删除数量为零。它会删除审查任务、风险、反馈，并清空 `storage` 下的合同、附件、预览、标记版和任务临时目录。

## 宿主机开发（可选）

需要 Python 3.11+、Node.js 18+ 及本机 PostgreSQL。后端直接运行时使用 `backend/.env`，并手动执行 `alembic upgrade head`、`uvicorn app.main:app --reload`；前端使用 `npm run dev`。

首次启动时，`INITIAL_ADMIN_EMAIL` 和 `INITIAL_ADMIN_PASSWORD` 会创建或提升初始化管理员，并接管升级前没有用户归属的历史任务和反馈。生产环境应通过密钥管理服务注入这些变量，不要提交到仓库。

首次可使用以下命令生成 Fernet Key。该值必须长期稳定并妥善备份；更换或丢失后，数据库内已加密的模型 API Key 将无法解密。

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

后端默认读取：

```dotenv
MODEL_PROVIDER=deepseek
MODEL_NAME=deepseek-chat
MODEL_API_BASE=https://api.deepseek.com
MODEL_API_KEY=
MODEL_CONFIG_ENCRYPTION_KEY=
MODEL_REQUEST_TIMEOUT_SECONDS=300
INITIAL_ADMIN_EMAIL=
INITIAL_ADMIN_PASSWORD=
```

默认 DeepSeek API Key 从环境变量或管理员保存的全局模型配置读取。模型配置页面新增的 Key 仅以 Fernet 密文写入数据库。不要将真实 Key 或 Fernet Key 写入 `.env.example` 或源码。

macOS 本地运行 OCR 和版式转换前，请安装系统依赖：

```bash
brew install poppler tesseract tesseract-lang
brew install --cask libreoffice font-noto-sans-cjk-sc
tesseract --list-langs
```

`tesseract --list-langs` 应至少包含 `eng` 和 `chi_sim`。启动后可访问 `GET /api/health/runtime` 查看 OCR 组件和语言包的实际状态；组件缺失时服务仍可启动，扫描版 PDF 会记录 OCR 不可用原因并降级为人工核验。

## 测试

```bash
cd backend
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q app tests alembic

cd ../frontend
npm run build
```

真实 DeepSeek 冒烟会使用系统当前模型创建一条审查任务，并仅输出任务、模型、风险数量和安全校验状态。首次把环境 Key 写入全局加密模型配置时，可通过隐藏输入执行，Key 不会出现在命令行参数或终端回显中：

```bash
cd code/backend
read -s MODEL_API_KEY
export MODEL_API_KEY
.venv/bin/python -m scripts.deepseek_smoke --refresh-key-from-env
unset MODEL_API_KEY
```

全局模型配置已有加密 Key 后，直接执行 `.venv/bin/python -m scripts.deepseek_smoke --user-id <业务用户ID>` 即可。不要在 shell 命令、测试日志或文档中填写完整 Key。

启用管理员保存的 Qwen 配置后，可执行真实 Qwen 合同审查冒烟。脚本只输出 Provider、模型、任务状态、风险数量和密钥安全校验结果：

```bash
docker compose exec backend python -m scripts.qwen_smoke --user-id <业务用户ID>
```

核心接口：

- `GET /api/auth/captcha`：生成一次性数字验证码；
- `GET /api/health/runtime`：检查 Poppler、Tesseract 及中英文 OCR 语言包；
- `POST /api/auth/register`、`POST /api/auth/login`：注册和登录；
- `GET /api/auth/me`、`POST /api/auth/logout`：读取当前账号和退出；
- `POST /api/contracts/upload`：上传并解析材料；
- `POST /api/review/create`：创建审查任务，支持 `Idempotency-Key`；
- `GET /api/review/history`：按关键字、状态和分页查询审查记录；
- `GET /api/review/{task_id}/status`：查询进度；
- `GET /api/review/{task_id}/result`：读取结构化结果；
- `GET /api/review/{task_id}/document/pages/{page_number}`：按需读取一页结构化文本；
- `GET /api/review/{task_id}/document/pages/{page_number}/image`：按需渲染一页原版式 PNG；
- `GET /api/review/{task_id}/download`：按源格式下载 DOCX 或 PDF 标记版；`format=pdf` 可额外导出 PDF；
- `POST /api/review/{task_id}/retry`：重试失败任务；
- `POST /api/review/{task_id}/risks/{risk_id}/feedback`：提交单条风险反馈；
- `GET/POST /api/rules`：查询或创建审查规则；
- `PUT/DELETE /api/rules/{rule_id}`：编辑或删除审查规则；
- `PATCH /api/rules/{rule_id}/status`：启用或停用审查规则；
- `GET/POST /api/scenes`：查询或创建审查场景；
- `PUT/DELETE /api/scenes/{scene_id}`：编辑或删除审查场景；
- `PATCH /api/scenes/{scene_id}/status`：启用或停用审查场景；
- `GET /api/scenes/available`：读取合同审查可选择的启用场景；
- `GET/POST /api/models`：管理员查询或新增全局模型配置；
- `GET /api/models/active`：读取当前使用的模型配置；
- `PUT /api/models/{config_id}`：编辑模型配置；
- `PATCH /api/models/{config_id}/status`：启用或停用模型配置。
- `POST /api/models/{config_id}/test`：管理员使用密文 Key 执行脱敏连接测试。
- `GET /api/users`、`GET /api/users/{user_id}`：管理员分页查询用户和查看详情；
- `PATCH /api/users/{user_id}/status`：管理员二次确认后启用或停用用户；
- `PATCH /api/users/{user_id}/role`：管理员二次确认后调整用户角色；
- `POST /api/users/{user_id}/reset-password`：管理员为其他用户重置密码并撤销其会话。

## 本地与 Docker 差异

- Docker 后端镜像在构建阶段安装并校验 Poppler、Tesseract、`eng` 和 `chi_sim`；宿主机启动需按上述 macOS 命令自行安装。
- Docker 镜像包含 LibreOffice Writer；macOS 使用 cask 版本，首次运行可能需要在系统隐私与安全设置中允许该应用。
- 两种环境都会在服务启动时输出 OCR 状态，并通过 `/api/health/runtime` 提供相同的结构化检查结果。

## 已知问题

- 后台任务当前运行在 FastAPI 进程内；服务重启会把遗留的处理中任务标记为失败并保留重新审查入口，但无法从中断点续跑。生产部署仍需接入持久任务队列。
- OCR 依赖 Poppler、Tesseract 及对应语言包；缺失时任务会保留 `unavailable` 状态并提示人工核验。
- Linux 环境解析旧版 DOC 依赖 `antiword`，版式预览和非 PDF 标记版下载依赖 LibreOffice。
- PDF 高亮位置基于文本坐标匹配，复杂字体、扫描件或拆分文本可能只能生成页内风险批注，无法精确高亮原句。
- TXT 的文本分页按段落和字符数生成，不等同于打印排版页；DOC/DOCX 的文本模式来自转换后 PDF，复杂表格请以版式模式为准。
- 单次审查材料解析文本上限为 120,000 字符，避免超过模型上下文窗口。
- 模型调用暂未实现流式输出、自动重试、连通性预检、限流和费用统计。
- 当前仅有普通用户、管理员两类固定角色，未实现多租户、组织架构、短信或邮箱验证。
- 模型列表暂未分页，也未提供删除能力；管理员可停用全部模型，此时新审查任务会提示系统未配置可用模型。
- 当前未提供反馈列表、反馈处理状态和配置版本对比页面。
- 删除规则会同步移除场景关联；删除场景不会影响已有任务，但配置删除目前不可恢复。
