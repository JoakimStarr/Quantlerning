# Quantlerning — 从 0 到量化高手的可视化学习网站

渐进式量化学习网站：从数学基础、统计推断到机器学习、组合优化，每个核心概念都配**交互式可视化**、Python 练习与测验。数据复用 QuantLab 的 PostgreSQL（10 年真实 A 股数据），学完即用，边学边练。

## ✨ 特色

- **64 课系统课程**（Phase 0~7），覆盖数学基础 → 财务指标 → 回测 → 因子分析 → 期权定价 → 机器学习 → 组合优化与实盘
- **90+ 交互模拟器**（ECharts / Canvas），每个核心概念都有可视化，随手拖动参数即可观察现象
- **6 个可运行代码沙箱**：真实行情 + 可折叠「预期输出」自检；全部练习题（134 道）附可折叠参考答案要点
- **内容质量有 CI 把关**：每次推送自动运行 `scripts/check_content.py`（quiz 合法性 / 组件注册 / 断句与裸 LaTeX 扫描 / 纯数学沙箱重放）与连库沙箱实测
- **真实数据驱动**：回测、因子、指标全部基于 10 年真实 A 股数据，而非玩具数据
- **Python 在线练习 + 测验**：代码沙箱实时运行，练习自动判题，测验立即反馈
- **AI 追问助手**：看不懂的内容随时追问，AI 结合当前课程上下文作答（可选功能，需在 `backend/.env` 配置 `OPENCODEZEN_API_KEY`，留空时该功能提示未配置）
- **深色/浅色主题**、**移动端适配**、**学习进度本地持久化**

## 🚀 快速启动

```bash
./start.sh dev        # 开发模式（Vite HMR），后台运行不占用终端
```

- 前端: http://localhost:5173
- 后端 API 文档: http://localhost:8100/docs
- 停止 `./start.sh stop` ｜ 重启 `./start.sh restart` ｜ 状态 `./start.sh status`

> 其他命令：`./start.sh start` 生产模式（`npm run build` 后用 vite preview 服务构建产物）；`./start.sh help` 查看全部。

> 依赖：PostgreSQL、Python 3.11（`.venv`）、Node.js

### 数据：用最小数据集（推荐）

站点依赖真实 A 股数据。**不需要连接原始 quantlab 库**——用导出的最小数据集即可跑通全部课程、模拟器与代码沙箱：

```bash
# 1. 建库并导入（约 80MB，含 5 只核心股全历史 + 800 只横截面股票池 + 宏观/因子/回测数据）
createdb quantlab
gunzip -c data/quantlerning_sample.sql.gz | psql -d quantlab

# 2. 配置连接（backend/.env）
#    POSTGRES_USER / POSTGRES_PASSWORD / POSTGRES_DB=quantlab / POSTGRES_HOST / POSTGRES_PORT

# 3. 启动
./start.sh dev
```

数据范围与口径见 [scripts/export_sample.py](scripts/export_sample.py)。若你有完整 quantlab 库，也可跳过导入直接使用。

### 重新生成数据集（维护者）

```bash
python scripts/export_sample.py --universe 800   # 输出 data/quantlerning_sample.sql.gz
```

## 端口规划（避免冲突）

| 端口 | 服务 |
|---|---|
| 5432 | PostgreSQL（quantlab 库，只读） |
| 8000 | QuantLab 后端 |
| 8100 | Quantlerning 后端 |
| 5173 | Quantlerning 前端（Vite） |

## 🛠 技术栈

- **后端**: FastAPI + SQLAlchemy(async) + PostgreSQL（只读连接 quantlab 库）
- **前端**: Vue 3 + TypeScript + Vite + ECharts + Vue Router + markdown-it + KaTeX
- **Python 环境**: `.venv`（Python 3.11，独立于 QuantLab）

## 📁 目录结构

```
backend/
  app/
    main.py          # FastAPI 入口 (8100)
    core/            # 配置 / 只读 DB 连接
    api/             # courses / data / compute / chat / exec 路由
    services/        # 课程内容 / 数据查询 / 金融计算 / 沙箱
    content/         # 课程 Markdown（phase0~phase7）
frontend/
  src/
    views/           # Home / Phase / Lesson / Lab / DataBrowser / Factors / Stats / Settings
    components/
      simulators/    # 75+ 交互模拟器（ECharts / Canvas）
      lesson/        # 练习 / 测验 / AI 追问 / Markdown 渲染
    utils/           # 主题、图表色板等
    stores/          # 学习进度 (localStorage)
    api/             # axios 封装
```

## 📚 课程体系

| Phase | 主题 | 状态 |
|---|---|---|
| Phase 0 | 数学与编程基础 | ✅ 完成 |
| Phase 1 | 金融市场基础 + 金融学 + 数据获取 | ✅ 完成 |
| Phase 2 | 基本面分析 | ✅ 完成 |
| Phase 3 | 量化策略入门 + 回测 | ✅ 完成 |
| Phase 4 | 因子投资与选股模型 | ✅ 完成 |
| Phase 5 | 衍生品定价与风险管理 | ✅ 完成 |
| Phase 6 | 机器学习量化 | ✅ 完成 |
| Phase 7 | 组合优化 + 实盘 | ✅ 完成 |

详情见 [PLAN.md](PLAN.md)，内容质量审核见 [CONTENT_REVIEW.md](CONTENT_REVIEW.md)。

## 🏆 里程碑

| 里程碑 | 内容 | 状态 |
|---|---|---|
| M0 | 项目骨架：前后端跑通、DB 只读连接、课程地图 | ✅ |
| M1 | Phase 1 课程 + Sharpe/回撤/MACD/RSI 模拟器 | ✅ |
| M2 | Phase 2 回测可视化 | ✅ |
| M3 | Phase 3 真实因子分析可视化 | ✅ |
| M4 | Phase 4 期权定价模拟器 | ✅ |
| M5 | Phase 5 ML 可视化 | ✅ |
| M6 | Phase 6 组合优化 + 完整站点 | ✅ |

## 🤝 欢迎参与：一起把知识做对、做全

本项目是**开源、免费**的量化学习资料，初衷是「让每一个量化概念都看得见、摸得着」。我们深知量化领域知识点多、口径杂（指标计算公式、回测细节、参数假设……），**单靠几个人很难保证零错误**。因此，我们诚邀每一位学习者共同维护这份内容：

- 🐛 **发现错误，欢迎修正**：无论是公式、数值、术语翻译，还是课程里的错别字，都可以提 Issue 或直接 PR。**纠错是最受欢迎的贡献**。
- 📖 **补充内容，一起做全**：觉得某课讲得太浅？某概念缺可视化？某个新知识点值得加一课？欢迎补充内容或新增模拟器。
- 💬 **参与讨论**：对某个指标的口径、某种策略的细节有疑问，欢迎开 Issue 讨论，把「不确定」变成「讲清楚」。
- 📢 **分享给需要的同学**：把这个项目转发给正在入门量化、或想系统补课的朋友。

**贡献方式很简单**：Fork → 修改 → Pull Request。改代码、改 Markdown 课程内容、写新模拟器、修文档，都欢迎。我们会在 [CONTENT_REVIEW.md](CONTENT_REVIEW.md) 记录审核状态，保证合入的内容质量。

> 学习不是为了考试，是为了让知识真实可用。欢迎加入，一起把量化讲清楚。
