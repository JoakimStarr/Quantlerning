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

echo "── 已启动 ──"
echo "  前端: http://localhost:5173"
echo "  后端 API 文档: http://localhost:8100/docs"
echo "  停止: Ctrl+C"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
wait
