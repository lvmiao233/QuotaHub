# QuotaHub

QuotaHub 是一个自托管额度看板，支持 OpenCode Go、Ollama Cloud，以及多个
CLIProxyAPI（CPA）渠道。所有额度由后端按间隔采集到 SQLite；浏览器刷新和轮询只读
本地快照，不会直接请求上游。

公开用户只能查看数据概览和账号额度。账号、CPA 渠道、使用记录与采集设置位于独立的
管理员后台。

## 致谢

本项目在 [QuotaHub](https://github.com/lvmiao233/QuotaHub) 基础上扩展，感谢原项目作者的开源贡献。

感谢 [LinuxDo](https://linux.do) 社区佬友们的交流与分享。

OpenCode Go 额度查询功能参考了
[opencode-cc](https://github.com/Kiowx/opencode-cc)（[@Kiowx](https://github.com/Kiowx)）。

## 启动前必填

QuotaHub 启动时必须提供以下两个环境变量；缺失、格式错误或无法解密已有数据时会拒绝启动。

| 变量 | 要求 | 说明 |
|------|------|------|
| `QUOTAHUB_ADMIN_TOKEN` | 至少 32 字符 | 管理员登录令牌，仅保存在部署环境中 |
| `QUOTAHUB_ENCRYPTION_KEY` | Fernet 密钥 | 加密 OpenCode/Ollama Cookie 与 CPA 管理密钥 |

生成示例：

```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

请把生成结果放进密码管理器或部署平台的 Secret。主密钥必须长期稳定；丢失后无法恢复已加密凭证。

生产 HTTPS 还应设置：

```bash
QUOTAHUB_COOKIE_SECURE=true
```

本地 HTTP 保持 `false`。管理员 Cookie 使用 `HttpOnly`、`SameSite=Strict`，服务端最长有效 24 小时。

## Docker 部署

使用 Release 镜像：

```bash
docker pull ghcr.io/haoyang7/quotahub:latest
docker run -d --name quotahub \
  -p 28787:8788 \
  -v ./data:/data \
  -e QUOTAHUB_ADMIN_TOKEN='替换为至少32字符的随机令牌' \
  -e QUOTAHUB_ENCRYPTION_KEY='替换为Fernet密钥' \
  -e QUOTAHUB_COOKIE_SECURE=false \
  -e QUOTAHUB_LOG_LEVEL=INFO \
  ghcr.io/haoyang7/quotahub:latest
```

本地构建：

```bash
cp .env.example .env
# 编辑 .env，填写两个必填 Secret
cp docker-compose.yml.example docker-compose.yml
docker compose up -d --build --force-recreate
```

浏览器打开 `http://localhost:28787`。公开页右上角的管理图标进入 `/admin/login`。

数据目录默认为 `./data`，SQLite 数据库为 `data/quotahub.db`。不要提交 `.env`、`data/`、数据库或真实配置。

## 直接运行

要求 Python 3.11+ 与 [uv](https://docs.astral.sh/uv/getting-started/installation/)。

```bash
export QUOTAHUB_ADMIN_TOKEN='替换为至少32字符的随机令牌'
export QUOTAHUB_ENCRYPTION_KEY='替换为Fernet密钥'
export QUOTAHUB_COOKIE_SECURE=false
export QUOTAHUB_LOG_LEVEL=INFO
./scripts/start.sh
```

默认监听 `http://127.0.0.1:8788`，数据目录为 `./data`。

通过 Git clone 获取的源码不包含 `frontend/dist`，必须先构建前端：

```bash
cd frontend
corepack enable
corepack pnpm@10.33.0 install --frozen-lockfile
corepack pnpm@10.33.0 build
cd ..
./scripts/start.sh
```

Release 的 UV 包和源码附件已包含 `frontend/dist`，可以配置环境变量后直接运行。

常用环境变量：

| 变量 | 默认 | 说明 |
|------|------|------|
| `QUOTAHUB_DATA` | `./data`，Docker 为 `/data` | SQLite 与运行数据目录 |
| `QUOTAHUB_LISTEN_HOST` | `127.0.0.1` | 监听地址 |
| `QUOTAHUB_LISTEN_PORT` | `8788` | 监听端口 |
| `QUOTAHUB_CONFIG` | 无 | 仅升级时指定旧 `config.json` |
| `QUOTAHUB_COOKIE_SECURE` | `false` | HTTPS 部署时设为 `true` |
| `QUOTAHUB_LOG_LEVEL` | `INFO` | `DEBUG`、`INFO`、`WARNING` 或 `ERROR` |

应用日志以单行文本写入 stdout，由 Docker 或宿主系统负责保存和轮转。实际执行的额度与使用记录
周期会记录调度器、随机运行 ID、渠道/账号内部 ID、任务数量、耗时和结果；没有到期任务的轮询仅在
`DEBUG` 级别出现。日志不会记录 Cookie、管理密钥、管理员令牌、`auth_index`、原始账号或上游响应正文。
Uvicorn 的默认访问日志已关闭，避免其直接输出客户端 IP；管理员登录事件改为记录不可逆的来源 HMAC。

## CPA / CLIProxyAPI 配置

管理员后台的「账号管理 → CPA / CLIProxyAPI」支持配置多个渠道。每个渠道包含名称、URL、管理密钥、
启用状态和独立采集间隔；默认 30 分钟，后端最短 5 分钟。密钥只提交一次并使用 Fernet 加密，API
不会返回密钥、掩码或“已配置”标记。

CLIProxyAPI 需要允许 QuotaHub 所在机器访问管理 API：

```yaml
remote-management:
  allow-remote: true
  secret-key: "使用高强度管理密钥"
```

如果 QuotaHub 与 CLIProxyAPI 在同一主机且通过 `127.0.0.1` 访问，可按实际网络拓扑保留更严格配置。
QuotaHub 固定使用：

- `GET /v0/management/auth-files` 发现启用的 Codex 账号；
- `GET /v0/management/monitoring/header-snapshots?days=30&limit=1000` 优先读取
  CLIProxyAPI 已被动记录的响应头额度；
- 只有被动快照缺失、无效、过期或接口不受支持时，才通过
  `POST /v0/management/api-call` 代请求 `https://chatgpt.com/backend-api/wham/usage`。

前端不能自定义上游方法、URL 或请求头。账号只保存脱敏显示名、不可逆内部指纹和随机公开 ID；
原始邮箱、账号 ID、文件名和 `auth_index` 不会返回前端。

## 采集行为

- OpenCode、Ollama 使用服务级间隔；CPA 每个渠道独立配置。
- 新增、更新凭证或重新启用后会排入后台采集，不提供手动上游刷新接口。
- 全局单实例串行采集，并在账号间节流，避免频繁请求导致封号风险。
- CPA 被动快照按文件名和 `auth_index` 严格匹配；不能匹配时不会使用其他账号或渠道首条记录。
- 监控接口仍检索最近 30 天记录，但只有最近 6 小时且不超前超过 5 分钟的观测可直接作为当前额度。
- CPA 主动兜底对每个账号最多 12 小时尝试一次，成功和失败都会进入同一节流窗口。
- 失败后等待完整间隔；保留上次成功额度并标记为“缓存已陈旧”。
- 禁用账号或渠道后停止采集、公开页隐藏，但保留快照；删除时级联删除快照。

## 从旧版本升级到 0.3.0

1. 停止所有旧实例并备份 SQLite。升级迁移期间禁止新旧版本同时运行，并预留至少一个数据库文件
   大小的额外空间；凭证加密迁移会安全重写 SQLite，清除旧页面中的明文残留：

   ```bash
   cp data/quotahub.db "data/quotahub.db.backup-$(date +%Y%m%d-%H%M%S)"
   ```

2. 一次性配置稳定的 `QUOTAHUB_ADMIN_TOKEN` 与 `QUOTAHUB_ENCRYPTION_KEY`。
   CPA 账号身份会升级为包含稳定账号主体的 HMAC；首次升级后个别 CPA 公开 ID 可能重新生成，
   以避免同一认证文件位置换号后继承旧额度和主动查询节流。
3. 若需要导入旧 `config.json`，临时设置 `QUOTAHUB_CONFIG=/data/config.json` 或挂载：

   ```yaml
   environment:
     QUOTAHUB_CONFIG: /data/config.json
   volumes:
     - ./data:/data
     - ./config.json:/data/config.json:ro
   ```

4. 先启动单个 0.3.0 实例，确认数据库迁移完成、账号已导入、凭证可解密且可以登录后台，再按需扩容。
5. 由部署者移除旧 `config.json` 挂载及其中的明文凭证。导入通过 `.imported` 标记保持幂等。

升级前请先备份。Fernet 主密钥错误或旧密文无法解密时，QuotaHub 会拒绝启动，不会静默覆盖数据。

## API 概览

公开只读：

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/public/quota` | OpenCode、Ollama、CPA 的本地额度快照 |
| GET | `/api/public/overview` | 基于快照的概览 |
| GET | `/api/public/analytics/opencode/daily` | SQLite 日统计 |
| GET | `/api/public/analytics/opencode/daily/models` | SQLite 模型日统计 |
| GET | `/api/health` | 健康检查 |

管理员接口统一位于 `/api/admin/*`，包括认证、账号、CPA 渠道、使用记录和设置。所有写请求需要登录
会话与 CSRF 校验。旧 `/api/quota`、`/api/ollama/quota` 和分析路径仅保留一版只读快照兼容入口，
并已标记弃用。

## 技术栈

- 后端：Python 3.11+、FastAPI、httpx、SQLite、cryptography/Fernet、uv
- 前端：React 19、TypeScript、Vite、Tailwind CSS
- 部署：Docker 或 uv
