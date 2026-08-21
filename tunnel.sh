#!/usr/bin/env bash
# Quantlerning 内网穿透（cloudflared quick tunnel）
# 把前端 5173（Vite 代理 /api → 8100）暴露到公网临时地址 https://xxx.trycloudflare.com
# 注意：quick tunnel 域名每次重启都会变化，仅适合临时演示/自用。
#
# 用法：
#   ./tunnel.sh            开启穿透（后台运行）
#   ./tunnel.sh --stop     停止穿透
#   ./tunnel.sh --status   查看状态与外网地址
#   ./tunnel.sh -h         查看帮助

set -e

RUN_DIR="/tmp/quantlerning"
PID_FILE="$RUN_DIR/tunnel.pid"
LOG_FILE="$RUN_DIR/tunnel.log"
TARGET_URL="http://localhost:5173"
CF_BIN="${CLOUDFLARED_BIN:-$(command -v cloudflared || echo "$HOME/.local/bin/cloudflared")}"

mkdir -p "$RUN_DIR"

usage() {
  cat <<'EOF'
Quantlerning 内网穿透（cloudflared quick tunnel）

用法：
  ./tunnel.sh            开启穿透（后台运行）
  ./tunnel.sh --stop     停止穿透
  ./tunnel.sh --status   查看状态与外网地址
  ./tunnel.sh -h         查看帮助

说明：
  - 把前端 5173（/api 由 Vite 代理到 8100）暴露为公网临时地址
  - quick tunnel 域名每次重启变化，如需固定域名请改用 cloudflared named tunnel 或花生壳
EOF
}

is_running() {
  [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null
}

# 从日志提取外网地址
tunnel_url() {
  grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG_FILE" 2>/dev/null | head -1 || true
}

start() {
  if is_running; then
    echo "内网穿透已在运行：$(tunnel_url)"
    return 0
  fi
  echo "启动内网穿透（${TARGET_URL} → 公网）..."
  nohup "$CF_BIN" tunnel --url "$TARGET_URL" --no-autoupdate \
    >"$LOG_FILE" 2>&1 &
  echo $! > "$PID_FILE"

  # 等待隧道建立，最多 15 秒
  local url="" i=0
  while [ $i -lt 15 ]; do
    url="$(tunnel_url)"
    [ -n "$url" ] && break
    sleep 1
    i=$((i + 1))
  done

  if [ -n "$url" ]; then
    echo "✅ 已开启内网穿透：$url"
  else
    echo "⚠️  隧道进程已启动，但暂未拿到外网地址。查看日志：$LOG_FILE"
    exit 1
  fi
}

stop() {
  if ! is_running; then
    echo "内网穿透未在运行"
    rm -f "$PID_FILE"
    return 0
  fi
  kill "$(cat "$PID_FILE")" 2>/dev/null || true
  rm -f "$PID_FILE"
  echo "已停止内网穿透"
}

status() {
  if is_running; then
    echo "状态：运行中（PID $(cat "$PID_FILE")）"
    echo "外网地址：$(tunnel_url)"
    echo "目标：$TARGET_URL"
  else
    echo "状态：未运行"
  fi
}

case "${1:-}" in
  -h|--help) usage ;;
  --stop) stop ;;
  --status) status ;;
  "") start ;;
  *) echo "未知参数：$1（-h 查看帮助）" >&2; exit 1 ;;
esac
