# CODEBUDDY.md

This file provides guidance to CodeBuddy Code when working with code in this repository.

## 项目概述

Quantlerning 是一个渐进式量化学习网站——「可视化动态的一本书」。课程内容以 Markdown 编写（支持 LaTeX 公式），可视化组件嵌入正文实现图文交融。数据只读复用 QuantLab 的 PostgreSQL（`quantlab` 库，10 年真实 A 股行情）。

**定位**：个人量化学习项目。真实性是最高原则——所有数据必须真实（来自 quantlab 库），教学示意需明确标注。

**注（2026-08-12）**：纯数学可视化（导数/分布/文氏图/泰勒/积分等抽象演示）的 caption 已按要求移除「（教学示意，非真实数据）」标注；但**真实数据模拟器**（用 quantlab 数据的图）仍必须真查询、不得编造数字。

## 常用命令

```bash
# 启动前后端（推荐）
./start.sh

# 后台稳定重启（直接 ./start.sh & 会让 vite 被进程组清理杀掉，务必用 setsid 脱离会话）
setsid nohup ./start.sh > /tmp/quantlerning-start.log 2>&1 < /dev/null &
# 停止：kill 掉 start.sh/uvicorn(8100)/vite(5173) 对应 PID，勿动 QuantLab(8000/3000)

# 或分别启动
cd backend && ../.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8100 --reload
cd frontend && npm run dev

# 前端类型检查（改前端后必跑）
cd frontend && npx vue-tsc --noEmit

# 后端 Python 语法检查
cd backend && ../.venv/bin/python -c "import ast; ast.parse(open('app/services/content/xxx.py').read())"

# 验证 API
curl http://localhost:8100/api/v1/health
```

**端口规划**（避免冲突）：`5432` PostgreSQL | `8000` QuantLab 后端 | `8100` 本项目后端 | `5173` 前端（Vite strictPort）。

**环境**：后端独立 venv（`.venv`，Python 3.11），前端 Vue3+Vite。后端依赖安装：`uv pip install -p .venv/bin/python -r backend/requirements.txt`。

## 架构

```
前端 Vue3+TS (5173)                 后端 FastAPI (8100)
┌──────────────────────┐           ┌──────────────────────────────┐
│ views/               │           │ app/api/                     │
│  Home/Phase/Lesson/  │  /api/v1  │  courses.py data.py chat.py  │
│  Lab/Cheatsheet/...  │ ────────► │  exec.py settings.py         │
│ components/lesson/   │           │ app/services/                │
│  MarkdownRenderer    │           │  content/(courses,loader)    │
│  VizBlock            │           │  data/queries.py             │
│ components/simulators│           │  sandbox/(runner,security)   │
│  DiscountCurve etc   │           │  ai/(chat,settings_store)    │
└──────────────────────┘           └──────────────┬───────────────┘
                                                  │ 只读 SQLAlchemy
                                          ┌───────▼───────┐
                                          │ quantlab 库(PG)│
                                          └───────────────┘
```

> 注意：夏普等金融指标**全在前端计算**（`useStockDaily`/各模拟器），后端无 `compute` 模块；后端只负责查询原始行情（`data/queries.py`）与沙箱/聊天。

### 内容管线（重点理解）

**课程元数据** `backend/app/services/content/courses.py`：定义 COURSES（phase 0-6，每课 id/title/concepts）。Phase 0 显示为「前言」，Phase 1 为「第一章」等。

**课程内容源**：内容以 **Markdown 文件**存放在 `backend/app/content/phase{0,1,...}/`，每课一个 `.md`。格式：

```markdown
---
id: p1-l10
summary: 一句话引言（渲染为蓝色引言框）
---

## 小节标题

正文 Markdown（支持 $LaTeX$、:::viz 块与 :::quiz 测验块）
```

- `phase_loader.py`（`services/content/phase_loader.py`）：模块加载时扫描 `content/**/*.md`，解析 frontmatter + 按 `##` 拆 sections。**代码块（``` 围栏）内的 `##` 不会被误当标题**
- 新增内容 = 直接放一个 `.md` 文件，无需注册；`courses.py` 通过 `ALL_CONTENT` 读取

**数据一致性**：第一章贯穿主线数据是**贵州茅台 SH600519 2024 全年**（真实行情，复权口径）。关键数字必须保持一致：
- 复利累计收益 -6.24%、年化 -6.51%、日波动 1.7353%、年化波动 27.55%
- 最大回撤 -27.28%（2024-05-07 峰值 1770.00 → 2024-09-19 谷底 1261.00）
- 单日最大涨 +9.29%、最大跌 -7.42%、夏普(rf=2%) -0.31

**官方口径（前后端统一）**：「pct_chg 复权连乘、不含首日（241 个收益）、ddof=1、几何年化」。具体：
- 复利累计 = ∏(1+pct_chg[1:]) − 1（不含首日，首日相对 2023-12-29 不计入）
- 年化收益 = (1+累计)^(252/241) − 1（几何，非算术）
- 日波动 = pct_chg[1:].std(ddof=1)；年化波动 = 日波动×√252
- 夏普 = (几何年化收益 − rf)/年化波动
- 实现位置：`frontend/src/composables/useStockDaily.ts`(nav)、`frontend/src/utils/portfolio.ts`、各模拟器（指标均前端计算，后端不重复实现）

### 前端渲染管线

**MarkdownRenderer.vue**（`frontend/src/components/lesson/MarkdownRenderer.vue`）：
- markdown-it + 自写 katex 插件（`utils/markdownMath.ts`，替代过时的 markdown-it-katex）渲染
- 支持 `$...$` 行内、`$$...$$` 块级 LaTeX；公式根节点带 `data-latex` 属性（供「选中问 AI」还原源码）
- 解析 `:::viz` 块与 `:::quiz` 测验块，切分 Markdown 片段与交互组件

**VizBlock.vue**：可视化组件注册表（`components/lesson/vizRegistry.ts`，组件名 → 组件）。注册表已全量激活（74 个组件，含各章模拟器），未实现的显示带 caption 占位。新增组件在 `vizRegistry.ts` 注册并放入 `components/simulators/`；`component` prop 类型收窄为注册表键名，md 里写错组件名 `vue-tsc` 即报错。图注行右侧有「↺ 重置」按钮（递增 `:key` 重挂载组件）。

**viz 嵌入语法**（写在课程 body 中）：
```
:::viz 组件名 caption=图注内容(可含空格，支持 LaTeX) 参数=值
:::
```

**quiz 测验语法**：
```
:::quiz
Q: 问题文本
- 选项1
- 选项2
A: 正确选项序号（1-based）
E: 解析
:::
```

**exercise 应用题语法**（`ExerciseBlock.vue`，提交后调 `POST /api/v1/chat/judge` AI 批改）：
```
:::exercise
T: 题目标题
Q: 题目正文（Markdown/LaTeX）
:::
```

**目录同步**：`App.vue` 左侧目录从课程 API 动态生成。子节 id 必须与 `LessonView.vue` 的 section id 对齐——两者都用 `sec-${i}`（0-based）。点击章节展开/再点收起。

### 交互功能（2026-08-12 起陆续加入）

- **AI 追问**（`components/lesson/AiAskPanel.vue` + 后端 `POST /api/v1/chat/stream`）：课程页右下角悬浮面板，围绕当前小节多轮对话、SSE 流式。对话按「课程+小节」存 localStorage（`aiask:v1:{lesson}:{section}`），重开/刷新自动恢复；AI 回答渲染 Markdown/LaTeX（归一化 `$$`/`\(`/`\[` 分隔符）
- **选中问 AI**（`LessonView.vue` + `utils/selectionToMarkdown.ts`）：选中正文文字弹「问 AI」按钮，katex 公式靠 `data-latex` 还原成 `$...$` 源码随问题发给 AI
- **阅读位置记忆**：`App.vue` 存 `ql:lastPath`（首页「继续学习」回到上次课程页）；页内滚动位置靠浏览器原生恢复（`main.ts` 设 `history.scrollRestoration='auto'`，body 滚动）。`LessonView.vue` 的滚动监听只用于**当前小节跟踪**（阅读进度条 + AI 追问上下文），不持久化
- **函数表达式解析**（`utils/mathExpr.ts`）：安全解析器（非 eval），支持 `x/y`、`+ - * / ^`、括号、隐式乘法（`2x`、`x(x+1)`、`2|x|`）、函数 sin/cos/tan/sqrt/log/ln/exp/abs、`|x|` 绝对值；含**符号微分** `differentiate(AST)`（泰勒系数/凹凸拐点用，比数值差分精确）与 `exprToLatex`（AST→LaTeX 公式展示）
- **主题跟随系统**（`App.vue` + `main.ts`）：`ql:theme` 未手动设置时跟随 `prefers-color-scheme`（matchMedia 监听）；手动切换后固定。`main.ts` 挂载前按「手动选择 > 系统偏好」初始化防闪烁
- **辅助页面包屑**（`components/common/PageBreadcrumb.vue`）：Lab/Cheatsheet/DataBrowser/Factors/Stats/Settings 六页顶部「学习地图 / 当前页」，解决工具页无返回入口
- **日线缓存统一**（`api/index.ts::fetchStockDaily`）：缓存下沉到 API 层（模块级 Map，key 用 code 小写归一化），`useStockDaily` / `usePortfolioDaily` / 各模拟器共享同一份，同股票不再重复请求
- **可视化重置**（`VizBlock.vue`）：图注行右侧「↺ 重置」按钮，点击递增 `:key` 强制重挂载模拟器组件回到初始值（不遮挡图表内容）

## 关键约定

1. **真实性原则（最高优先）**：数据必须真实。禁止为效果编造数字；真实数据不可用时显示「数据不可用」，不用假数字顶替。**注意（2026-08-12）**：纯数学可视化的 caption 已不再标注「非真实数据」；教学示意（如 DDM 例子的股息、ML 模型）可存在但内容上仍应合理，真实数据模拟器必须真查询
2. **公式一律 LaTeX**：不要用 Unicode 字符写公式（如 `σ²`、`√252`、`Pₜ`）。Markdown 文件中 LaTeX 反斜杠不需要转义（`\frac` 直接写），但 Python 字符串中要转义（`\\frac`）；中文语境引号用「」避免破坏 frontmatter；中文后半角冒号/逗号统一用全角（`：`、`，`）
3. **课程内容结构**：教科书式风格——定义 → 定理/公式 → 金融应用，**不要用「是什么 / 怎么做 / 长什么样」框架**。简洁 Markdown，不冗长；段落标签统一 `**标签：**`（全角冒号在粗体内）
4. **可视化嵌入正文**：不是单独占位块，而是像插图一样嵌在文字流中（figure+caption），图文交融
5. **前端改完跑 `vue-tsc --noEmit`**，后端内容文件改完跑 Python ast 检查
6. **不加「标记已完成」按钮**（已移除），进度靠阅读行为

## 数据 API

| 端点 | 说明 |
|---|---|
| `GET /api/v1/courses` | 课程地图（阶段+课程+进度） |
| `GET /api/v1/courses/{id}` | 课程详情（summary+sections+prev/next） |
| `GET /api/v1/data/search?q=` | 个股搜索（代码/名称，如 600519/茅台） |
| `GET /api/v1/data/stock/{code}/daily` | 个股日线（code 大小写不敏感，如 sh600519；前端有模块级缓存） |
| `GET /api/v1/data/indices` | 指数元数据清单 |
| `GET /api/v1/data/macro/indicators` | 宏观指标列表 |
| `GET /api/v1/data/macro/{indicator}` | 宏观指标序列 |
| `GET /api/v1/data/factors` | 因子库（真实 factor 表，支持 status/category/order_by 过滤） |
| `GET /api/v1/data/factors/summary` | 因子总数/活跃数/类别 |
| `GET /api/v1/data/factors/ic-distribution` | 161 因子 IC 直方图 |
| `GET /api/v1/data/factors/pe-layers` | 全市场 PE 分层收益热力图 |
| `GET /api/v1/data/factors/pe-ic` | PE 因子月度 Rank IC 序列 |
| `GET /api/v1/data/factors/industry-pe` | 行业 PE 中位数对比 |
| `GET /api/v1/data/market/pe-distribution` | 全市场某日 PE 分布 |
| `GET /api/v1/data/backtests` | QuantLab 多因子回测结果（含净值曲线） |
| `POST /api/v1/exec/run` | 练习沙箱：AST 白名单过滤 + 子进程隔离（python -I + 资源限制）执行，白名单库 + `get_daily` 只读真实行情（实现：`services/sandbox/`） |
| `POST /api/v1/chat/stream` | AI 追问（SSE 流式，围绕课程小节） |
| `POST /api/v1/chat/judge` | AI 批改应用题（SSE 流式） |
| `GET/PUT /api/v1/settings/ai` | AI 模型配置（base_url/model/api_key，密钥掩码存储） |

## 里程碑

> 实际进度（2026-08 验证）：内容分布 phase0=6 / phase1=11 / phase2=10 / phase3=7 / phase4=7 / phase5=8 / phase6=6 课；simulators 目录 74 个组件，vizRegistry 基本全量激活。

- M0 ✅ 骨架：前后端、课程地图、内容填充（前言+第一章）
- M1 ✅ 交互组件批量实现（sharpe/mdd/macd/rsi/capm 等）
- M2 ✅ 第二章回测内容与可视化（10 课）
- M3 ✅ 第三章因子内容与可视化（7 课 + ic_distribution / factor_ic / layer_returns / industry_pe / factor_backtest_dashboard）
- M4 ✅ 第四章衍生品内容与可视化（7 课 + random_walk / bs_price_slider / binomial_tree / monte_carlo_pricing / var_simulator）
- M5 ✅ 第五章 ML 内容与可视化（8 课 + label_design / overfit_demo / feature_importance / ml_backtest，复用 gradient_field 讲梯度下降）
- M6 🚧 第六章组合优化与实盘（6 课已写 + 5 模拟器已完成：frontier / risk_parity / black_litterman / pair_trading / portfolio_risk；剩余 4 课待补）

### 第四章真实锚点（模型 + 真实数据）

- σ：茅台 2024 年化波动 **27.55%**（quantlab 库，官方口径，与主线一致）
- r：LPR 1Y **3.0%**（macro_indicator，2026-07 快照）
- VaR：茅台 2024 真实日收益（参数法 -2.87% / 历史法 -2.42%，95% 置信度 1 日）
- BS/二叉树/MC 为模型计算（示意），输入锚定真实数据；quantlab 库无期权行情，波动率微笑课明确标注示意

### 第三章数据源（真实）

- `GET /api/v1/data/factors/ic-distribution` — 161 因子 IC 直方图
- `GET /api/v1/data/factors/pe-layers` — 全市场 PE 分层收益热力图（月末快照 + 下月收益）
- `GET /api/v1/data/factors/pe-ic` — PE 因子月度 Rank IC 序列
- `GET /api/v1/data/factors/industry-pe` — 行业 PE 中位数对比
- `GET /api/v1/data/backtests` — QuantLab 多因子回测结果（含净值曲线）

> 主线口径：2018-2026 全 A 横截面，PE 分层 Q1~Q5（月度末快照 + **下月前向收益**，LEAD 口径）。真实结果呈 **U 形非单调**：Q1（低估值）与 Q5（高估值）均高于中间三组，Q5 平均月收益 1.97%/复利 +446% 仅略高于 Q1 的 1.77%/+367%；PE 月度 rank IC 均值 0.016、ICIR 0.16（低于 0.3 稳定门槛）、IC>0 仅 53%。课程以此强调「因子方向与强度依赖区间、分层看单调性」。

### 第五章真实锚点（前端轻量 ML + 真实数据）

- 特征/标签/训练全部用**贵州茅台 SH600519 2024 真实日线**（复用 `useStockDaily`，复权口径）
- `utils/ml.ts`：纯 TS 手写标准化 / 逻辑回归（批量梯度下降 + L2 正则 + 验证早停）/ 多项式最小二乘 / 绩效指标，**无 sklearn 依赖**
- 特征 8 个（全部只用 t 及之前信息，杜绝前视）：mom5/mom10/mom20、vol20、rsi14、macd_hist、dist_ma20、turnover
- 标签 = 次日收益 > 0（分类）；切分一律**时间顺序**（训练前、测试后），测试集只评估一次
- 5 个可视化：`label_design`（标签分布）、`overfit_demo`（多项式过拟合+训练/验证误差）、`feature_importance`（特征重要度）、`ml_backtest`（ML vs 双均线 vs 买入持有）、复用 `gradient_field`（梯度下降）
- 教学定位：ML 模型为**教学示意**（单只股票逻辑回归，不代表可实盘），强调「模型有用 ≠ 策略赚钱」

### 第六章真实锚点（多股票组合 + 真实收益矩阵）

- 组合分析用**5 只真实 A 股 2024 全年日收益**（242 交易日）：贵州茅台 sh600519 / 五粮液 sz000858 / 宁德时代 sz300750 / 招商银行 sh600036 / 中国平安 sh601318
- `usePortfolioDaily.ts`：前端**并行拉取**多股日线 + 客户端按共同交易日对齐，输出同步收益矩阵（复用 fetchStockDaily 缓存）
- `utils/portfolio.ts`：纯 TS 手写协方差/相关系数、有效前沿（随机采样）、最小方差/最大夏普、风险平价（风险贡献迭代）、Black-Litterman（观点融合）、Engle-Granger 协整 ADF
- 真实配对：招商银行-兴业银行（协整 ADF≈-3.62）、茅台-泸州老窖（ADF≈-3.14）、茅台-五粮液（**不协整** ADF≈-1.62，教学对照）
- 5 个可视化：`frontier`（有效前沿）/ `risk_parity` / `black_litterman` / `pair_trading` / `portfolio_risk`
- 教学定位：有效前沿/风险平价/BL 输入用真实协方差；压力测试情景幅度（2008 腰斩等）为教学示意，明确标注
