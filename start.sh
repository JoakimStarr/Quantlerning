#!/usr/bin/env bash
# Quantlerning 启动脚本
# 端口规划：5432 PG | 8000 QuantLab 后端 | 8100 Quantlerning 后端 | 5173 前端
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "── 启动 Quantlerning 后端 (8100) ──"
(cd "$ROOT/backend" && "$ROOT/.venv/bin/python" -m uvicorn app.main:app --host 0.0.0.0 --port 8100 --reload) &
BACKEND_PID=$!

echo "── 启动 Quantlerning 前端 (5173) ──"
(cd "$ROOT/frontend" && npm run dev) &
FRONTEND_PID=$!

# 等待后端健康检查通过（最多 30s），失败时给出明确提示
echo "── 等待后端就绪 ──"
BACKEND_OK=0
for i in $(seq 1 30); do
  if curl -sf http://localhost:8100/api/v1/health >/dev/null 2>&1; then
    BACKEND_OK=1
    break
  fi
  sleep 1
done

if [ "$BACKEND_OK" != "1" ]; then
  echo "✗ 后端 30s 内未通过健康检查，请检查："
  echo "  1. PostgreSQL 是否已启动（quantlab 库是否可连接）"
  echo "  2. 依赖是否安装（backend/requirements 或 .venv）"
  echo "  3. 8100 端口是否被占用"
  kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
  exit 1
fi
echo "✓ 后端健康检查通过"

echo "── 已启动 ──"
echo "  前端: http://localhost:5173"
echo "  后端 API 文档: http://localhost:8100/docs"
echo "  停止: Ctrl+C"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
wait
