#!/usr/bin/env bash
set -euo pipefail

version="${1:?用法: render-release-notes.sh <version> [from-tag] <image>}"
from_tag="${2:-}"
image_repo="${3:?用法: render-release-notes.sh <version> [from-tag] <image>}"
image="${image_repo}:${version#v}"

cat <<EOF
## 下载说明

本 Release 提供三种分发形式，按你的环境选择其一即可。

### Docker 镜像

适合已有 Docker 的环境，跨平台一致、便于长期运行与升级。

\`\`\`bash
docker pull ${image}
docker run -d --name quotahub \\
  -p 28787:8788 \\
  -v ./data:/data \\
  -e QUOTAHUB_LISTEN_PORT=8788 \\
  -e QUOTAHUB_ADMIN_TOKEN='<必填：至少 32 字符>' \\
  -e QUOTAHUB_ENCRYPTION_KEY='<必填：Fernet 密钥>' \\
  -e QUOTAHUB_COOKIE_SECURE=false \\
  ${image}
\`\`\`

也可使用仓库中的 \`docker-compose.yml.example\`，将 \`image\` 改为 \`${image}\` 后 \`docker compose up -d\`。

### UV 运行时包：\`quotahub-${version}-uv.zip\`

**推荐给已安装 [uv](https://docs.astral.sh/uv/) 的用户。** 包内已包含构建好的前端，不含虚拟环境，首次启动时由本机 uv 按平台自动安装 Python 依赖。

要求：Python >= 3.11，已安装 uv。

Linux / macOS：

\`\`\`bash
unzip quotahub-${version}-uv.zip
cd quotahub-${version}
export QUOTAHUB_ADMIN_TOKEN='<必填：至少 32 字符>'
export QUOTAHUB_ENCRYPTION_KEY='<必填：Fernet 密钥>'
export QUOTAHUB_COOKIE_SECURE=false
./scripts/start.sh
\`\`\`

Windows（PowerShell）：

\`\`\`powershell
Expand-Archive quotahub-${version}-uv.zip
cd quotahub-${version}
\$env:QUOTAHUB_ADMIN_TOKEN='<必填：至少 32 字符>'
\$env:QUOTAHUB_ENCRYPTION_KEY='<必填：Fernet 密钥>'
\$env:QUOTAHUB_COOKIE_SECURE='false'
scripts\\start.bat
\`\`\`

默认监听 \`http://127.0.0.1:8788\`，数据目录为包内 \`./data\`。可通过环境变量 \`QUOTAHUB_LISTEN_HOST\`、\`QUOTAHUB_LISTEN_PORT\`、\`QUOTAHUB_DATA\` 调整。

### 源码包：\`quotahub-${version}-source.zip\`

**适合需要阅读、修改或自行构建前端的用户。** 包含完整后端与前端源码；若 Release 构建时附带 \`frontend/dist\`，也可直接运行而无需 Node.js。

从源码运行（需 uv + pnpm）：

\`\`\`bash
unzip quotahub-${version}-source.zip
cd quotahub-${version}
cd frontend && corepack enable && pnpm install --frozen-lockfile && pnpm build && cd ..
export QUOTAHUB_ADMIN_TOKEN='<必填：至少 32 字符>'
export QUOTAHUB_ENCRYPTION_KEY='<必填：Fernet 密钥>'
export QUOTAHUB_COOKIE_SECURE=false
./scripts/start.sh          # Linux / macOS
\`\`\`

若包内已有 \`frontend/dist\`，可省略前端构建步骤，直接运行 \`./scripts/start.sh\` 或 \`scripts\\start.bat\`。

---

生产 HTTPS 部署请将 QUOTAHUB_COOKIE_SECURE 设为 true。Fernet 密钥必须长期稳定；升级前停止全部旧实例并备份 SQLite，完成 0.3.0 迁移后再扩容，禁止新旧版本同时运行。

Windows 源码运行请按上方 UV 包示例设置三个必填环境变量。

## 校验

Release 附件附带 \`SHA256SUMS\`，可用以下命令校验：

\`\`\`bash
sha256sum -c SHA256SUMS
\`\`\`

---

## 更新日志

EOF

if [[ -n "$from_tag" ]]; then
  git log --pretty=format:'- %h %s' "${from_tag}..HEAD"
else
  git log --pretty=format:'- %h %s' -20
fi

echo
