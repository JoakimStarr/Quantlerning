#!/usr/bin/env bash
# Quantlerning 启动脚本
# 端口规划：5432 PG | 8000 QuantLab 后端 | 8100 Quantlerning 后端 | 5173 前端
#
# 用法：
#   ./start.sh            静默启动：后台运行、不占用终端（默认）
#   ./start.sh -f         前台启动：占用终端，Ctrl+C 停止
#   ./start.sh --stop     停止后台运行的后端/前端
#   ./start.sh --status   查看运行状态
#   ./start.sh -h         查看帮助
#
# 后台运行日志与 PID 文件位于 /tmp/quantlerning/

set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
RUN_DIR="/tmp/quantlerning"
BACKEND_LOG="$RUN_DIR/backend.log"
FRONTEND_LOG="$RUN_DIR/frontend.log"
BACKEND_PID_FILE="$RUN_DIR/backend.pid"
FRONTEND_PID_FILE="$RUN_DIR/frontend.pid"
BACKEND_URL="http://localhost:8100/api/v1/health"
FRONTEND_URL="http://localhost:5173"

mkdir -p "$RUN_DIR"

# 健康检查：curl 带超时，避免服务未响应时挂起
is_backend_up()  { curl -sf --connect-timeout 2 --max-time 3 "$BACKEND_URL"  >/dev/null 2>&1; }
is_frontend_up() { curl -sf --connect-timeout 2 --max-time 3 "$FRONTEND_URL" >/dev/null 2>&1; }

usage() {
  cat <<'EOF'
Quantlerning 启动脚本

用法：
  ./start.sh            静默启动：后台运行、不占用终端（默认）
  ./start.sh -f         前台启动：占用终端，Ctrl+C 停止
  ./start.sh --stop     停止后台运行的后端/前端
  ./start.sh --status   查看运行状态
  ./start.sh -h         查看帮助

后台运行日志与 PID 文件位于 /tmp/quantlerning/
EOF
}

status() {
  echo "── Quantlerning 状态 ──"
  if is_backend_up; then
    echo "  后端 8100: 运行中"
  else
    echo "  后端 8100: 未运行"
  fi
  if is_frontend_up; then
    echo "  前端 5173: 运行中"
  else
    echo "  前端 5173: 未运行"
  fi
}

# 停止后台进程：按 PID 文件杀对应进程组（setsid 后 leader 即 PID）
stop() {
  local f pid
  for f in "$BACKEND_PID_FILE" "$FRONTEND_PID_FILE"; do
    if [ -f "$f" ]; then
      pid="$(cat "$f" 2>/dev/null || true)"
      if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        echo "── 停止进程组 $pid ──"
        kill -TERM -- "-$pid" 2>/dev/null || true
      fi
      rm -f "$f"
    fi
  done
  sleep 1
  if is_backend_up || is_frontend_up; then
    echo "⚠ 仍有端口未释放，稍后可用 ./start.sh --status 复查"
  else
    echo "✓ 已全部停止"
  fi
}

wait_for_backend() {
  echo "── 等待后端就绪 ──"
  local i
  for i in $(seq 1 30); do
    if is_backend_up; then
      echo "✓ 后端健康检查通过"
      return 0
    fi
    sleep 1
  done
  echo "✗ 后端 30s 内未通过健康检查，请检查："
  echo "  1. PostgreSQL 是否已启动（quantlab 库是否可连接）"
  echo "  2. 依赖是否安装（backend/requirements 或 .venv）"
  echo "  3. 8100 端口是否被占用"
  return 1
}

wait_for_frontend() {
  local i
  for i in $(seq 1 15); do
    if is_frontend_up; then
      echo "✓ 前端就绪"
      return 0
    fi
    sleep 1
  done
  echo "⚠ 前端 15s 内未就绪，请查看 $FRONTEND_LOG"
  return 1
}

print_ready() {
  echo "── 已启动 ──"
  echo "  前端: http://localhost:5173"
  echo "  后端 API 文档: http://localhost:8100/docs"
}

# 静默启动：setsid 脱离会话 + 后台，不占用终端；日志写 /tmp/quantlerning
start_background() {
  if is_backend_up; then
    echo "✓ 后端 8100 已在运行，跳过"
  else
    echo "── 静默启动后端 (8100) ──"
    export BACKEND_PID_FILE ROOT
    setsid bash -c 'echo $$ > "$BACKEND_PID_FILE"; cd "$ROOT/backend" && exec "$ROOT/.venv/bin/python" -m uvicorn app.main:app --host 0.0.0.0 --port 8100 --reload' >>"$BACKEND_LOG" 2>&1 < /dev/null &
  fi

  if is_frontend_up; then
    echo "✓ 前端 5173 已在运行，跳过"
  else
    echo "── 静默启动前端 (5173) ──"
    export FRONTEND_PID_FILE ROOT
    setsid bash -c 'echo $$ > "$FRONTEND_PID_FILE"; cd "$ROOT/frontend" && exec npm run dev' >>"$FRONTEND_LOG" 2>&1 < /dev/null &
  fi
}

# 前台启动：保留终端，Ctrl+C 停止
start_foreground() {
  echo "── 启动后端 (8100) ──"
  (cd "$ROOT/backend" && "$ROOT/.venv/bin/python" -m uvicorn app.main:app --host 0.0.0.0 --port 8100 --reload) &
  BACKEND_PID=$!
  echo "── 启动前端 (5173) ──"
  (cd "$ROOT/frontend" && npm run dev) &
  FRONTEND_PID=$!
  trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT

  if ! wait_for_backend; then
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    exit 1
  fi
  wait_for_frontend || true
  print_ready
  echo "  停止: Ctrl+C"
  wait
}

case "${1:-}" in
  "")          start_background
               if ! wait_for_backend; then
                 stop
                 exit 1
               fi
               wait_for_frontend || true
               print_ready
               echo "  日志: $BACKEND_LOG | $FRONTEND_LOG"
               echo "  停止: ./start.sh --stop" ;;
  -f|--foreground) start_foreground ;;
  --stop)      stop ;;
  --status)    status ;;
  -h|--help)   usage ;;
  *)           echo "未知参数: $1" >&2; usage; exit 1 ;;
esac
