# Quantlerning — 从 0 到量化高手的可视化学习网站

渐进式量化学习网站。每个核心概念配**交互可视化**、Python 练习与测验。数据复用 QuantLab 的 PostgreSQL（10 年真实 A 股数据）。

## 快速启动

```bash
./start.sh
```

- 前端: http://localhost:5173
- 后端 API 文档: http://localhost:8100/docs

## 端口规划（避免冲突）

| 端口 | 服务 |
|---|---|
| 5432 | PostgreSQL（quantlab 库，只读） |
| 8000 | QuantLab 后端 |
| 8100 | Quantlerning 后端 |
| 5173 | Quantlerning 前端（Vite） |

## 技术栈

- 后端: FastAPI + SQLAlchemy(async) + PostgreSQL（只读连接 quantlab 库）
- 前端: Vue 3 + TypeScript + Vite + ECharts + Vue Router
- Python 环境: `.venv`（Python 3.11，独立于 QuantLab）

## 目录结构

```
backend/
  app/
    main.py          # FastAPI 入口 (8100)
    core/            # 配置 / 只读 DB 连接
    api/             # courses / data / compute 路由
    services/        # 课程内容 / 数据查询 / 金融计算
    content/         # 课程 Markdown（各 phase 目录）
frontend/
  src/
    views/           # Home / Phase / Lesson / Lab
    components/      # charts(ECharts) + simulators(Canvas) 待建
    api/             # axios 封装
    stores/          # 学习进度 (localStorage)
```

## 课程体系

见 [PLAN.md](PLAN.md) — Phase 0~6 共 62 课。

## 里程碑

- M0 ✅ 项目骨架：前后端跑通、DB 只读连接、课程地图
- M1 ✅ Phase 1 课程 + Sharpe/回撤/MACD/RSI 模拟器
- M2 ✅ Phase 2 回测可视化
- M3 ✅ Phase 3 真实因子分析可视化
- M4 Phase 4 期权定价模拟器
- M5 Phase 5 ML 可视化
- M6 Phase 6 组合优化 + 完整站点
