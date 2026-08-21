# Quantlerning 可接入的免费开放能力 · 全景清单

> 调研时间：2026-08-20 ｜ 覆盖：国内外主流开放平台（不止阿里/华为）
> 说明：免费额度随官方活动变动，落地前以各平台「免费试用中心 / 定价页」实时为准。
> 目的：给你这个量化可视化学习站（Vue3 + FastAPI + PostgreSQL）找**白嫖也能上线**的外部能力。

---

## 0. 能力域速览（一句话地图）

| 能力域 | 最该用的免费平台 | 接到你站的哪 |
|---|---|---|
| 大模型 / 多模态 | 阿里百炼、智谱、硅基流动、火山豆包、DeepSeek、Gemini | AI 追问(chat)、内容生成 |
| **金融数据 API** | **AKShare、Baostock、Tushare**（免费档） | **data / compute 路由的数据源** |
| 语音 TTS / ASR | 阿里智能语音、Azure、讯飞 | 课程朗读、语音提问 |
| OCR / 文档解析 | 阿里 Document Mind、华为 OCR | 截图提问、课件识别 |
| 对象存储 / CDN | Cloudflare R2、阿里 OSS、CF Pages | 托管 dist、用户上传 |
| 数据库 / BaaS | Supabase、Neon、Turso、Upstash | 替代/补充 PostgreSQL、缓存、队列 |
| Serverless | 阿里 FC、CF Workers、华为 FunctionGraph | Python 沙箱(exec)上云 |
| 机器翻译 / NLP | 阿里 NLP、DeepL | 中英术语、双语字幕 |
| 内容安全 | 阿里 / 华为内容安全 | 审核 UGC |
| 智能 BI | 阿里 Quick BI、Metabase | data 页中文问数 |
| 认证 Auth | Supabase Auth、Clerk、Auth0 | 账号体系（若要做多用户） |
| 邮件 / 短信 / 推送 | Resend、Telegram Bot、阿里短信 | 通知、找回密码 |
| 监控 / 分析 | Sentry、Grafana Cloud、CF Analytics | 报错、可观测 |
| 图像 / 视频生成 | 阿里通义万相、腾讯混元视频、Cloudinary | 课程配图、讲解视频 |

---

## 1. 大模型 / 对话 / 多模态（增强 AI 追问 + 内容生成）

| 平台 | 免费额度（2026） | 特点 | 接入场景 |
|---|---|---|---|
| **阿里云百炼** | ~7000 万 tokens（90 天）；国际版(新加坡)每模型 100 万 | 兼容 OpenAI，Qwen 全系，可 RAG/联网 | 主力推荐，换 chat 路由 base_url |
| **智谱 AI** | 2000 万 tokens + GLM-4-Flash **永久免费** | 30 并发，国产合规 | 备选主力，长期免费 |
| **硅基流动** | 2000–3000 万 tokens + 9B 以下模型永久免费 | 聚合 100+ 模型，国内 CDN <100ms | 多模型 A/B |
| **火山引擎(豆包)** | **200 万 tokens/天**（按天重置） | 国内日额度最大，深度思考 | 高频轻量追问 |
| **腾讯混元** | 100 万 tokens/年 + Hunyuan-Lite 永久免费 | 腾讯自研，中文稳 | 轻量对话 |
| **DeepSeek** | 约 500 万 tokens（少量充值即送） | 推理强、极便宜 | 复杂推理题 |
| **Kimi(月之暗面)** | 超长上下文 256K+，网页端免费 | 整本教材/长代码问答 | 长文档学习 |
| **百度千帆** | 100 万/3 月 + ERNIE-3.5 永久(QPS50) | 合规首选 | 备选 |
| **讯飞星火** | Spark Lite **永久免费** | 中文语音强 | 语音结合 |
| 国外：Gemini / Groq / Cerebras / Cloudflare Workers AI / OpenRouter / NVIDIA NIM | Gemini 100 万上下文；Groq 极速；Cerebras 100 万/天；CF Workers AI 10K/天；OpenRouter 聚合 50+ 免费；NIM 无限次(40 RPM) | 速度/多模态/不出境可选自部署 | 多语言、极速、科研 |

> 落地提示：绝大多数兼容 OpenAI 协议，改 `base_url` + `api_key` 即可，且可**多厂商 fallback**（主用百炼，超限切智谱/硅基流动）。

---

## 2. 金融数据 API（量化站刚需！data / compute 的数据源）

> 你站当前用本地 PostgreSQL 样本（10 年 A 股）。要扩展实时/更广数据，免费源如下：

| 数据源 | 免费情况 | 覆盖 | 质量/稳定性 | 适合 |
|---|---|---|---|---|
| **AKShare** | **完全免费、无 token、无需注册**（MIT） | A股/港股/美股/基金/期货/期权/宏观/**另类(龙虎榜/北向/资金流/舆情)** | ⭐⭐⭐（爬虫，接口易变） | 快速原型、广度优先 |
| **Baostock** | **完全免费** | A股历史日线/分钟线(2019 起)、财务、复权 | ⭐⭐⭐⭐（最稳） | 历史回测基石 |
| **Tushare Pro** | 注册送 120 积分，基础接口免费（~500–1000 次/天，频率限） | A股日线/指数/财报/宏观/行业，**口径规范** | ⭐⭐⭐⭐⭐（生产级） | 质量优先、低频 |
| **yfinance** | 完全免费 | 美股/港股/数字货币（**不适用 A 股**） | ⭐⭐⭐⭐ | 海外资产 |
| **efinance** | 完全免费 | A股**实时秒级**行情 | ⭐⭐⭐ | 轻量实时监控 |
| 付费/进阶 | 聚宽 JoinQuant、RiceQuant、TickFlow、理杏仁 | 实时/分钟级/Level-2/财务最准 | 高 | 实盘、深度研究 |

**建议组合（零成本）：** AKShare/Baostock 拉历史做回测与因子 → Tushare 免费档取规范财务/宏观 → efinance 做轻量实时。**接法：** 在 `backend/app/services/data.py` 抽象一个数据适配层，优先本地 PG，缺失时回退到 AKShare/Baostock。

---

## 3. 语音（TTS 朗读 / ASR 语音提问）

- **阿里云智能语音交互**：100 万字符免费（1 年）+ 每月 5 万字符；新用户 100h 转写 + 50h TTS；50+ 中文音色、情感合成、长文本。
- **微软 Azure 语音**：每月 5 小时免费，国际化音色好。
- **讯飞 / 华为云**：中文语音识别（ASR）方言强，适合语音提问转文字。
- **OpenAI Whisper**：语音识别可本地/API，开源免费。
- 接入点：课程 Markdown「朗读」按钮；AI 追问悬浮窗加语音输入。

## 4. OCR / 文档解析

- **阿里云 Document Mind**：文档解析 3000 页/月、智能表格 100 页、PDF↔Word/Excel 1000 页（一次性）。
- **华为云 ModelArts OCR**：每日前 1000 次图像识别免费 / 新用户 2000 核时·月。
- **百度 OCR**：每日 500 次免费。
- 接入点：AI 追问「上传截图提问」；课件公式/图表识别。

## 5. 对象存储 / CDN / 静态托管

- **Cloudflare R2**：10 GB 存储 + 1000 万次读/月，**零出口费**（ Serve 全球免费，比 S3 省大钱）。
- **Cloudflare Pages / Workers**：Pages 无限带宽、Workers 10 万请求/天——**前端 dist 直接托管**。
- **阿里云 OSS**：5 GB 标准 + 5 GB 下行/月（6 个月）。
- **Vercel / Netlify**：100 GB 带宽，适合静态站/SSR。
- 接入点：`frontend/dist` → CF Pages/R2 或 OSS+CDN；用户上传存 R2/OSS。

## 6. 数据库 / 后端 BaaS（可整体替代现有 PG + 后端）

- **Supabase**：500 MB Postgres + Auth(5 万 MAU) + Storage(1 GB) + Edge Functions + 实时 + 向量。**近乎白送一整套后端**。
- **Neon**：0.5 GB serverless Postgres，缩到 0 计费，git 式分支——适合开发/预览。
- **Turso**：9 GB 边缘 SQLite，500 库，适合读多场景。
- **Upstash**：1 万 Redis 命令/天 + QStash 队列——缓存/异步任务。
- **Cloudflare D1 / MongoDB Atlas(512 MB)**。
- 接入点：学习进度（现用 localStorage）可迁 Supabase 做多端同步；缓存用 Upstash。

## 7. Serverless 计算（Python 沙箱上云）

- **阿里云函数计算 FC**：长期每月 100 万次调用 + 40 万 GB-秒免费；新用户 15 万 CU/月（3 月）。
- **华为云 FunctionGraph**：每月免调用次数。
- **Cloudflare Workers**（10 万/天）、Deno Deploy、Render、Fly.io。
- 接入点：`/api/exec` 沙箱迁 FC，隔离 + 弹性 + 免运维。

## 8. 机器翻译 / NLP

- **阿里云 NLP / 机器翻译**：基础文本服务（分词、实体、情感、词向量）**50 万次/天**免费。
- **DeepL / 腾讯翻译**：中英互译。
- 接入点：课程术语中英对照、双语朗读字幕、英文文献摘录翻译。

## 9. 内容安全 / 审核

- **阿里云内容安全 / 华为云**：审核 AI 追问输入、用户上传资料，防违规。
- 接入点：exec 沙箱输入、UGC 内容。

## 10. 智能 BI / 数据分析

- **阿里 Quick BI 智能小 Q**：1 个月免费、无限 Token，自然语言问数。
- **Metabase**：自托管永久免费，接 PostgreSQL 直接出图。
- 接入点：data 页支持「用中文问数据」。

## 11. 认证 Auth（若做多用户）

- **Supabase Auth**（5 万 MAU，随 DB 赠送）｜**Clerk**（1 万 MAU）｜**Auth0**（2.5 万 MAU）。

## 12. 邮件 / 短信 / 推送

- **Resend**：3000 邮件/月免费（事务邮件、找回密码）。
- **SendGrid**：100 封/天。
- **阿里/腾讯短信**：100 条试用。
- **Telegram Bot API**：完全免费、无限——做学习提醒/播报机器人极方便。

## 13. 监控 / 日志 / 分析

- **Sentry**：5000 错误/月免费——报错追踪。
- **Grafana Cloud**：1 万指标 + 50 GB 日志/月——可观测。
- **Cloudflare Web Analytics / PostHog(100 万事件)**：流量与产品分析。
- **Better Stack**：10 个 uptime 监控。

## 14. 图像 / 视频生成

- **阿里通义万相**：100 张图 + 50 秒视频免费（百炼礼包）。
- **腾讯混元文生视频**：在线免费。
- **Cloudinary**：25 GB 图片/视频处理 + CDN 免费。
- 接入点：课程配图、概念讲解短视频。

## 15. 地图 / 支付 / 其他

- 地图：**Mapbox**(5 万加载/月)、高德/腾讯地图（有限免费）——地理数据可视化。
- 支付（变现）：**Stripe**（无月费按交易）、微信支付/支付宝。
- 搜索：**Algolia**(1 万记录)、Meilisearch(自托管)。
- CI/CD：**GitHub Actions**(2000 分钟/月)。

---

## 16. 量化学习站「最该先接」优先级

| 优先级 | 能力 | 平台 | 成本 | 为什么 |
|---|---|---|---|---|
| **P0** | 金融数据 API | AKShare + Baostock（免费） | ¥0 | 你站 data/compute 的粮食，零成本扩数据面 |
| **P0** | 大模型对话 | 阿里百炼/智谱（免费档） | 免费千万 token | AI 追问直接升级，兼容 OpenAI |
| **P0** | Python 沙箱 | 阿里 FC（长期免费） | 免费额度 | exec 上云，隔离免运维 |
| **P1** | 课程朗读 | 阿里 TTS（100 万字符免费） | ¥0 | 听学体验 |
| **P1** | 前端托管 | Cloudflare Pages + R2（零出口费） | ¥0 | 稳定上线、全球加速 |
| **P1** | 数据库/进度 | Supabase（500MB 免费） | ¥0 | 多端进度同步、可加 Auth |
| **P2** | OCR 截图提问 | 阿里 Document Mind | 免费页 | 交互升级 |
| **P2** | 监控 | Sentry + CF Analytics | 免费 | 上线后必选项 |
| **P2** | 邮件/推送 | Resend + Telegram Bot | 免费 | 通知、找回密码 |

## 17. 注意事项

- **合规**：量化金融涉及数据合规，用户数据尽量不出境，优先国内节点；沙箱执行务必隔离防滥用。
- **地域**：阿里百炼免费额度仅部分地域（国际版新加坡区），北京区常无免费档，选型前确认。
- **额度时效**：多为 90 天 / 3 月 / 1 年，量产后评估按量成本（百炼输入低至 1 元/百万 tokens；AKShare/Baostock 无限制）。
- **免费层陷阱**：Supabase 免费项目 7 天不活跃会暂停；CF R2 超 10GB 才计费；设好预算告警。
- **多厂商 fallback**：大模型建议百炼(主)+智谱/硅基流动(备)，避免单点额度耗尽。
