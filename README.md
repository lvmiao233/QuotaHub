# QuotaHub

由于 OpenCode Go 和 Ollama 多账号使用时查看额度不太方便，Vibe了一个小工具从各平台 Dashboard 抓取并展示账号额度。


## 致谢

感谢 [LinuxDo](https://linux.do) 社区佬友们的交流与分享；

OpenCode Go 额度查询功能的实现参考了 [opencode-cc](https://github.com/Kiowx/opencode-cc)（[@Kiowx](https://github.com/Kiowx)）。


## 获取与部署

| 方式 | 适合谁 | 说明 |
|------|--------|------|
| [GitHub Release](https://github.com/lvmiao233/QuotaHub/releases) | 大多数用户 | 提供 Docker 镜像、UV 运行时包、源码包，Release 页有详细说明 |
| Docker | 已有 Docker 的环境 | 见下文 |
| UV 运行时包 | 已安装 [uv](https://docs.astral.sh/uv/) | 解压后 `scripts/start.sh`（Linux/macOS）或 `scripts\start.bat`（Windows） |
| 源码包 / Git 克隆 | 需要改代码或自行构建 | 需 uv；改前端时另需 pnpm |


## Docker 部署

**使用 Release 镜像（推荐）：**

```bash
docker pull ghcr.io/lvmiao233/quotahub:latest
docker run -d --name quotahub \
  -p 28787:8788 \
  -v ./data:/data \
  ghcr.io/lvmiao233/quotahub:latest
```

**本地构建：**

```bash
cp docker-compose.yml.example docker-compose.yml
docker compose up -d --build --force-recreate
```

浏览器打开 http://localhost:28787 （端口由 `QUOTAHUB_LISTEN_PORT` 决定）

数据目录默认为 `./data`，内含 SQLite 数据库 `quotahub.db` 与服务设置。


## 直接运行（无需 Docker）

### 从 Release 下载 UV 包

要求：Python >= 3.11，已安装 [uv](https://docs.astral.sh/uv/getting-started/installation/)。

```bash
unzip quotahub-v0.3.0-uv.zip
cd quotahub-v0.3.0
./scripts/start.sh
```

Windows（PowerShell）：

```powershell
Expand-Archive quotahub-v0.3.0-uv.zip
cd quotahub-v0.3.0
scripts\start.bat
```

默认监听 http://127.0.0.1:8788 ，数据目录为 `./data`。

常用环境变量：

| 变量 | 默认 | 说明 |
|------|------|------|
| `QUOTAHUB_DATA` | `./data` | SQLite 与数据文件目录 |
| `QUOTAHUB_LISTEN_HOST` | `127.0.0.1` | 监听地址 |
| `QUOTAHUB_LISTEN_PORT` | `8788` | 监听端口 |


### 从源码运行

```bash
git clone https://github.com/lvmiao233/QuotaHub.git
cd QuotaHub

# 构建前端
cd frontend && corepack enable && pnpm install --frozen-lockfile && pnpm build && cd ..

# 启动（Linux / macOS）
./scripts/start.sh
```

Windows：

```bat
git clone https://github.com/lvmiao233/QuotaHub.git
cd QuotaHub
cd frontend && corepack enable && pnpm install --frozen-lockfile && pnpm build && cd ..
scripts\start.bat
```


### 从 v0.1 升级

首次升级可**临时**挂载旧 `config.json`，自动导入账号与设置后写入数据库：

```yaml
environment:
  QUOTAHUB_CONFIG: /data/config.json
volumes:
  - ./data:/data
  - ./config.json:/data/config.json:ro
```

若曾在设置页保存过配置，同目录下的 `service.json` 也会一并迁移（`service.json` 优先级更高）。

导入完成后可去掉 `config.json` 挂载；账号与设置在 SQLite 中维护，不再依赖配置文件。


### 从 v0.2.x 升级

数据库结构无变更。升级到 **v0.3.0** 后请在「账号管理」中检查并更新账号凭证（见下文），否则额度或调用日志可能拉取失败。

- **OpenCode Go**：必须填写 Console 的 `__Host-console_session` 与 `wrk_…` 组织 ID；仅保存旧版 `auth=` 已无法使用。
- **Ollama**：若额度解析失败，确认 Cookie 仍有效；settings 页 DOM 变更已在 v0.3.0 适配。


## 配置说明

运行时**不再依赖** `config.json`，配置在「设置」页面修改，后续变更将保存到 SQLite。

| 来源 | 说明 |
|------|------|
| 环境变量 `QUOTAHUB_LISTEN_HOST` / `QUOTAHUB_LISTEN_PORT` | 监听地址（优先） |
| 环境变量 `QUOTAHUB_DATA` | 数据目录，默认 `/data` |
| SQLite `service_settings` | 刷新间隔、同步参数等 |
| `config.json`（可选，仅迁移用） | 首次导入账号与旧版设置 |

`import_accounts` 块或顶层账号字段仅在首次导入时读取，完成后写入 `/data/.imported`。


### OpenCode Go 账号（UI：账号 → OpenCode）

在 [OpenCode Console](https://opencode.ai) 登录后，打开对应组织的 Go 页面（地址形如 `https://opencode.ai/console/wrk_…/go`）。

| 字段 | 填写内容 |
|------|--------|
| 组织 ID（`wrk_…`） | 地址栏里的 `wrk_` 开头 ID，与 Console 请求头 `x-org-id` 一致 |
| Console Cookie | 至少包含 `__Host-console_session=st_…`。浏览器 F12 → Network → 任意 `console/api` 请求 → 复制 Cookie 中该字段即可（可附带 `auth=`，非必须） |

保存后可用「测试连接」或刷新额度验证。Session 过期后需重新复制 Cookie。


### Ollama 账号（UI：账号 → Ollama）

| 字段 | 填什么 |
|------|--------|
| Session Cookie | 登录 [ollama.com/settings](https://ollama.com/settings) 后，复制 `aid=…` 与 `__Secure-session=…`（整段 Cookie 或仅 session 值均可） |


## API 概览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/quota` | 所有 OpenCode 账号额度 |
| GET | `/api/ollama/quota` | 所有 Ollama 账号额度 |
| GET/POST | `/api/accounts/opencode` | OpenCode 账号列表 / 新增 |
| PUT/DELETE | `/api/accounts/opencode/{id}` | 更新 / 删除 |
| GET | `/api/accounts/opencode/{id}/usage` | 读本地使用记录 |
| POST | `/api/accounts/opencode/{id}/usage/sync` | 增量同步 |
| POST | `/api/accounts/opencode/{id}/usage/backfill` | 补拉历史 |
| GET/POST | `/api/accounts/ollama` | Ollama 账号 CRUD |
| GET/PUT | `/api/config` | 读取 / 更新服务设置 |

完整 UI：数据概览、账号额度、调用日志、账号管理、设置。


## 技术栈

- 后端：Python 3.11+、FastAPI、httpx、SQLite、uv
- 前端：Vite、React、react-router-dom、Tailwind CSS
- 部署：Docker / uv 直接运行
