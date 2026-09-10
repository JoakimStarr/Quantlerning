# 贡献指南

欢迎一起学习、一起优化 Quantlerning。这个项目是**渐进式量化学习网站**：55 课、75+ 交互模拟器、真实 A 股数据、代码沙箱。你的任何改进——修一个数据错误、加一课、写一个模拟器、补一道题——都会让更多人受益。

## 先跑起来（10 分钟）

```bash
# 1. 安装依赖
python -m venv .venv && .venv/bin/pip install -r backend/requirements.txt
cd frontend && npm install && cd ..

# 2. 导入最小数据集（无需连接原始 quantlab 库）
createdb quantlab
gunzip -c data/quantlerning_sample.sql.gz | psql -d quantlab

# 3. 配置连接 backend/.env（参考 backend/.env.example）
#    POSTGRES_USER / POSTGRES_PASSWORD / POSTGRES_DB / POSTGRES_HOST / POSTGRES_PORT

# 4. 启动（后台运行，停止用 ./start.sh stop）
./start.sh dev
```

> 没有 `data/quantlerning_sample.sql.gz`？说明尚未发布，可先在 issue 里说明，或用 `python scripts/export_sample.py --universe 800` 从你自己的库导出。

## 目录速览

```
backend/app/content/      # 课程内容（Markdown，phase0~6）
backend/app/services/     # 内容加载、数据查询、沙箱执行
frontend/src/views/       # 页面（课程、实验室、数据浏览器）
frontend/src/components/
  lesson/                 # 课程渲染、vizRegistry（模拟器注册表）
  simulators/             # 75+ 交互模拟器（Vue + ECharts）
frontend/src/utils/       # 纯函数库（策略/组合/ML）
scripts/export_sample.py  # 最小数据集导出脚本
```

## 可以贡献什么

| 类型 | 说明 | 难度 |
|---|---|---|
| 修数据/内容错误 | 课程里的数字、LaTeX、练习编号 | 低 |
| 修模拟器 bug | 前视偏差、口径错误、NaN 渲染 | 中 |
| 加一道 quiz / 练习 | 选择题（Q/选项/A/E）或应用题 | 低 |
| 加一课 | 新概念 + 模拟器 + 练习 | 高 |
| 加一个模拟器 | 在 `simulators/` 写 Vue 组件并注册 | 中 |
| 文档 / 基建 | README、测试框架、CI | 低 |

## 修改内容（Markdown）

课程文件在 `backend/app/content/phase*/p*-l*.md`，用这些标记：

- `:::quiz` 选择题：`Q:` 题干、`- ` 选项、`A:` 答案序号、`E:` 解析
- `:::exercise` 应用题：`T:` 题干、`(1)(2)(3)...` 子问
- `:::viz 组件名 caption=图注` 嵌入模拟器，组件名必须在 `vizRegistry.ts` 注册

**改内容必须核对真实数据**：项目铁律是「数据真实性」。正文里的数字（如茅台 2024 复利累计 -6.24%）要在沙箱里用 `get_daily` 跑出来一致才可写死。口径约定：复权 `pct_chg` 连乘、**不含首日**、`ddof=1`、几何年化。

## 修改前端

- 模拟器组件在 `frontend/src/components/simulators/`，注册到 `components/lesson/vizRegistry.ts`（74 个已注册）
- 新增模拟器若想出现在「实验室」页，还要在 `views/LabView.vue` 的 `KEY_PHASE` 里加映射
- 纯函数（策略/组合/统计）放 `frontend/src/utils/`

## 自检（提交前必跑）

```bash
# 前端类型检查 + 构建
cd frontend && npx vue-tsc --noEmit && npm run build

# 后端语法
cd backend && ../.venv/bin/python -m py_compile app/api/*.py app/services/sandbox/*.py

# 内容完整性：55 课全部加载、quiz 格式合法、:::viz 组件名均已注册
cd backend && ../.venv/bin/python -c "from app.services.content.phase_loader import get_content; print(len(get_content()))"
```

## 提交流程

1. Fork 仓库 → 新建分支 → 修改 → 提交
2. 自检通过后提 PR，说明：改了什么、为什么、如何验证
3. 内容类改动会在 `CONTENT_REVIEW.md` 记录审核状态；数据类改动请附沙箱验证输出

不会写代码？**提 issue 也行**：报告一个数据错误、一个模拟器 bug、或一个想学但没覆盖的概念，都会进入 `PLAN.md` 的待办。