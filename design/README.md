# Quantlerning · 设计语言规范（Design Language）

> 调性：**极简精修 + 深邃蓝** · 一套统一的设计令牌（token）与组件库，覆盖色彩 / 字体 / 间距 / 圆角 / 阴影 / 交互，保证首页、课程、数据、设置各页面视觉协调、体验一致。
> 本目录为**独立预览包**，不修改你的仓库代码。确认方向后，可让我把 token 落地到 `frontend/src/styles/main.css` 与 `frontend/src/utils/theme.ts`。

---

## 1. Design Context（设计决策来源）

| 维度 | 结论 |
|---|---|
| **用户** | 量化金融学习者：在校生、转行从业者、爱好者。在「系统补课」情境下使用，目标是把抽象公式变成可看可练的直觉。 |
| **品牌个性** | 严谨但不高冷、专业却有温度。三词：**清晰 / 可信 / 进阶**。情绪目标：学习时的「确定感」与「成就感」。 |
| **视觉方向** | 极简精修 + 深邃蓝。克制留白、几何秩序、数据可读。参照优秀教育产品与金融终端的干净感；**规避**霓虹渐变、毛玻璃滥用、千篇一律的 AI 蓝青。 |
| **设计原则** | ① 一致性优先 ② 数据永远可读（tabular 数字）③ 反馈即时且不喧哗 ④ 移动端不阉割功能 ⑤ 主题只是换肤，结构不变。 |

---

## 2. 文件结构

```
quantlerning-design/
├── assets/
│   ├── tokens.css      # 设计令牌：色彩 / 字体 / 间距 / 圆角 / 阴影 / 动效 + 深浅主题
│   ├── components.css  # 统一组件：按钮/卡片/徽章/表单/顶栏/侧栏/表/进度/Toast/空态…
│   ├── app.js          # 轻交互：主题切换 / 移动抽屉 / Toast / 标签页（无依赖）
│   ├── icon.svg        # 主推图标（深蓝渐变 tile + 白线 Q）
│   ├── icon-b.svg      # 备选 B：求和 Σ
│   ├── icon-c.svg      # 备选 C：进阶路径
│   └── icon-mark.svg   # 单色降级版（currentColor）
├── icons.html          # 图标方案预览（概念/尺寸/深浅/单色/文字标）
├── design-system.html  # 设计系统总览（实时切主题看全部 token 与组件）
├── home.html           # 首页 · 课程地图 + 模拟器 + CTA
├── lesson.html         # 课程学习 · 侧栏 + 可视化交互 + 测验 + AI 追问
├── data.html           # 数据展示 · KPI + 图表 + 数据表 + 因子
└── settings.html       # 设置 · 外观/学习/账户/关于
```

打开任意 `.html` 即可在浏览器预览；右上角按钮实时切换深 / 浅主题。

---

## 3. 色彩（oklch 感知均匀色阶）

所有组件**只引用语义变量**，不直接写色值。

```css
--primary        /* 主操作/链接  oklch(0.612 0.176 256) */
--primary-hover  /* 悬停        oklch(0.548 0.180 258) */
--bg-page        /* 页面背景    oklch(0.970 0.005 256) */
--bg-card        /* 卡片表面    oklch(0.992 0.002 256) */
--text-1/2/3     /* 主/次/弱文字 */
--border         /* 描边        oklch(0.906 0.009 256) */
--success/warning/danger  /* UI 状态色 */
--up / --down    /* 金融涨跌：A股惯例「涨红跌绿」 */
--chart-1..6     /* 图表调色板（克制低饱和） */
```

- **主色**：深蓝梯度 `--blue-300 → --blue-800`，标准主色 `--blue-500`（`#2F6AE8` 附近）。
- **中性灰**：带冷调（微偏蓝），与蓝主色同源，避免纯灰的廉价感。
- **关键约定**：金融数据涨跌使用 `--up`(红)/`--down`(绿)，与 UI 语义 `--success`(绿)/`--danger`(红) **刻意区分**——市场数据遵循 A 股「涨红跌绿」，非市场反馈（如测验对错）用语义色。

---

## 4. 字体层级

| 角色 | 字体 | 用途 |
|---|---|---|
| 展示 / 标题 / 大数字 | **Space Grotesk** | h1–h5、KPI 数值、品牌字 |
| 正文 | **Manrope** | 段落、按钮、导航 |
| 等宽 / 数据 / 代码 | **JetBrains Mono** | 行情、公式、代码块（tabular-nums） |

```css
--fs-3xl … --fs-xs   /* 流体字号：clamp() 随视口缩放，比例≈1.25 */
.num                 /* 等宽 + tabular-nums，所有数字对齐 */
```

> 中文自动回退到 `PingFang SC / Microsoft YaHei`，无需额外中文字体。

---

## 5. 间距 / 圆角 / 阴影 / 动效

- **间距**：4px 基准（`--sp-1` 4px … `--sp-9` 96px），区块节奏 `--section-y: clamp(48px,6vw,96px)`。
- **圆角**：`--r-xs` 6 → `--r-sm` 8 → `--r-md` 12 → `--r-lg` 16 → `--r-xl` 22 → `--r-pill` 999。
- **阴影**：低透明度、分层、柔和（`--shadow-xs → --shadow-lg`）；**不滥用发光**。
- **动效**：指数缓动 `--ease-out` (quart) / `--ease-out-soft` (expo)，**禁用回弹**；`prefers-reduced-motion` 自动降级。

---

## 6. 图标 / 品牌

- **主推 A「学习曲线 Q」**：Q 字母 = Quantlerning，碗内上升折线 = 数据/学习曲线，自带深蓝渐变，16–256px 全程可识别，深浅主题通用。
- **备选 B「求和 Σ」**（更学术）、**C「进阶路径」**（强调循序渐进）。
- 交付：`icon.svg`（彩色 tile）、`icon-mark.svg`（单色 currentColor，用于单色场景/文字标）、`icons.html`（方案预览）。
- 用法：favicon 导出 16/32/48/180 多尺寸 + `mask-icon` 用单色 mark；顶栏与页脚用「图标 + 文字标」lockup。

---

## 7. 与现有前端（Vue 3）的落地映射

现有 `frontend/src/styles/main.css` 已有一套蓝调 token。落地时**替换/扩充**为上面的 oklch 语义变量即可，组件 class 名基本一致，迁移成本低：

| 现有 `main.css` | 建议映射 |
|---|---|
| `--primary: #2563eb` | `--primary: oklch(0.612 0.176 256)`（更深邃） |
| `--bg-page: #f6f7f9` | `--bg-page: oklch(0.970 0.005 256)`（冷调中性） |
| `--text-1/2/3` | 保留语义，改用 oklch 值 |
| `.btn / .btn-primary / .card / .badge` | 直接替换为 `components.css` 对应类（已含 hover/focus 微交互） |
| `[data-theme="dark"]` | 保留切换机制，`theme.ts` 无需改；`tokens.css` 已写好双主题变量 |

- **图表（ECharts）**：`frontend/src/utils/chartTheme.ts` 的系列色改为 `--chart-1..6` 的取值（深蓝为主，紫/青/琥珀/红/玫为辅），保持与 UI 同源。
- **字体**：在 `index.html` 引入 Space Grotesk / Manrope / JetBrains Mono（已含中文字体回退），并把 `--font-display/body/mono` 应用到 `main.css`。
- **响应式**：`components.css` 已用容器查询思路 + 900px 断点把侧栏收为抽屉，可直接套用。

> 需要我把这套 token 与组件**直接落地**到 `Quantlerning/frontend`（重构 main.css、补充页面级样式）时，告诉我一声即可。

---

## 8. 可访问性

- 键盘焦点可见：`--focus-ring` + `:focus-visible`。
- 色彩对比满足 WCAG AA；涨跌色在深浅主题下均带 soft 底色辅助辨识。
- `prefers-reduced-motion` 下关闭过渡/动画。
- 移动端不隐藏关键功能，仅将侧栏转为抽屉。
