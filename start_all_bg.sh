#!/usr/bin/env bash
# 一键后台启动所有服务 (数据库 + 前端 UI)。
# Background launcher: starts the optional databases, then the Streamlit web app
# in the background. Unlike a bare `streamlit run`, this delegates UI launch to
# scripts/minicrew-app (which sets PYTHONPATH and the headless flags) and only
# reports success after the app is actually reachable.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

PORT="${MINICREW_PORT:-8501}"
VENV="$HERE/minicrew/.venv"

# 0. preflight: the dedicated venv must have streamlit, or the UI can't start.
if [ ! -x "$VENV/bin/streamlit" ]; then
  echo "❌ 未找到 streamlit: $VENV/bin/streamlit" >&2
  echo "   先创建虚拟环境: python3 -m venv $VENV && $VENV/bin/pip install streamlit pyyaml requests" >&2
  exit 1
fi

# 1. 后端数据库 (可选 — distill/chat/discuss 无需数据库; 仅文献检索需要)
if command -v docker >/dev/null 2>&1; then
  echo "正在启动后端数据库 (Docker)..."
  if docker compose -f minicrew/docker-compose.yml up -d >/dev/null 2>&1; then
    echo "  ✓ 数据库已启动"
  else
    echo "  ⚠ docker compose 失败 — 文献检索不可用 (其余功能正常)"
  fi
else
  echo "  ⚠ 未找到 docker — 跳过数据库 (文献检索不可用)"
fi

# 2. 杀掉旧的前端进程（防止端口被占用）
if [ -f minicrew_ui.pid ]; then
  old_pid="$(cat minicrew_ui.pid)"
  kill "$old_pid" 2>/dev/null || true
  rm -f minicrew_ui.pid
fi

# 3. 后台启动前端，日志输出到 minicrew_ui.log。
# scripts/minicrew-app `exec`s streamlit, so $! stays the live streamlit PID.
echo "正在后台启动 Streamlit 前端 (端口 $PORT)..."
nohup scripts/minicrew-app --server.port "$PORT" > minicrew_ui.log 2>&1 &
ui_pid=$!
echo "$ui_pid" > minicrew_ui.pid

# 4. 等待前端真正可访问后再报告成功（最多 ~30s）。
ready=0
for _ in $(seq 1 30); do
  if ! kill -0 "$ui_pid" 2>/dev/null; then
    break          # process died — fall through to the failure path
  fi
  if curl -s -o /dev/null "http://localhost:$PORT" 2>/dev/null; then
    ready=1
    break
  fi
  sleep 1
done

if [ "$ready" != "1" ]; then
  echo "======================================" >&2
  echo "❌ 前端启动失败或未能在 30s 内响应。" >&2
  echo "📄 查看日志: tail -n 50 minicrew_ui.log" >&2
  echo "======================================" >&2
  tail -n 20 minicrew_ui.log >&2 || true
  exit 1
fi

echo "======================================"
echo "✅ 所有服务启动完毕并已挂载到后台！"
echo "🌐 访问地址: http://localhost:$PORT"
echo "📄 查看运行日志: tail -f minicrew_ui.log"
echo "🛑 停止前端命令: kill \$(cat minicrew_ui.pid)"
echo "======================================"
