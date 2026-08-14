@echo off
setlocal EnableExtensions

set "ROOT=%~dp0.."
for %%I in ("%ROOT%") do set "ROOT=%%~fI"

if not defined QUOTAHUB_DATA set "QUOTAHUB_DATA=%ROOT%\data"
if not exist "%QUOTAHUB_DATA%" mkdir "%QUOTAHUB_DATA%"

if not defined QUOTAHUB_LISTEN_HOST set "QUOTAHUB_LISTEN_HOST=127.0.0.1"
if not defined QUOTAHUB_LISTEN_PORT set "QUOTAHUB_LISTEN_PORT=8788"

where uv >nul 2>&1
if errorlevel 1 (
  echo 未找到 uv，请先安装: https://docs.astral.sh/uv/getting-started/installation/
  exit /b 1
)

cd /d "%ROOT%\backend"
uv sync --no-dev --frozen
if errorlevel 1 exit /b 1

".venv\Scripts\uvicorn.exe" app.main:app --host "%QUOTAHUB_LISTEN_HOST%" --port "%QUOTAHUB_LISTEN_PORT%"
exit /b %ERRORLEVEL%
