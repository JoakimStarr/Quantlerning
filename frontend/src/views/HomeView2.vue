<script setup lang="ts">
import { computed, defineAsyncComponent, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowRight, PlayCircle, Sparkles, Target } from 'lucide-vue-next'
import { fetchCourses, fetchBacktests, streamPlan, streamReview, type BacktestResult } from '@/api'
import { getProgress, isCompleted, learningDays, sandboxRunCount, totalExercises } from '@/stores/progress'
import { linkifyCourses } from '@/utils/linkifyCourses'
import { chapterLabel, PHASE_STATUS as phaseStatus } from '@/utils/chapter'
import AppSpinner from '@/components/common/AppSpinner.vue'
import AppError from '@/components/common/AppError.vue'

// AI 规划/复习结果懒加载渲染（避免 markdown-it/KaTeX 进首屏，仅生成后加载）
const PlanCard = defineAsyncComponent(() => import('@/components/common/PlanCard.vue'))

const router = useRouter()
const phases = ref<any[]>([])
const loading = ref(true)
const error = ref('')

// 继续上次学习：读取 App.vue 写入的 ql:lastPath，解析出课程
const LAST_PATH_KEY = 'ql:lastPath'
const lastPath = ref('')

// AI 学习规划
const plan = ref('')
const planBusy = ref(false)
const planError = ref('')

// 错题弱项复习
const review = ref('')
const reviewBusy = ref(false)
const reviewError = ref('')

// 掌握标记：随堂测验答错后「变式题再练」答对自动标记（QuizBlock 写入 ql:mastered:{lessonId}）
function readMastered(lessonId: string): Record<string, boolean> {
  try {
    return JSON.parse(localStorage.getItem(`ql:mastered:${lessonId}`) ?? '{}') || {}
  } catch {
    return {}
  }
}

// 随堂测验每题最佳分（ql:quizResults）：读错题清单
function readQuizWrong(lessonId: string): string[] {
  let map: Record<string, number> = {}
  try {
    map = JSON.parse(localStorage.getItem(`ql:quizResults:${lessonId}`) ?? '{}') || {}
  } catch {
    map = {}
  }
  return Object.keys(map).filter((q) => Number(map[q]) < 100)
}

function buildProgressSummary(): string {
  const lines: string[] = []
  lines.push(
    `学习天数 ${learningDays()} 天；沙箱运行 ${sandboxRunCount()} 次；应用题提交 ${totalExercises()} 次。`,
  )
  lines.push('各课进度：')
  for (const p of phases.value) {
    for (const l of p.lessons) {
      const pr = getProgress(l.id)
      if (!pr) continue
      const parts = [`《${l.title}》`]
      if (pr.completed) parts.push('已完成')
      if (pr.quizScore != null && pr.quizzesTotal != null) parts.push(`测验 ${pr.quizScore}/${pr.quizzesTotal}`)
      // 错题 + 变式题掌握情况：供规划端识别薄弱知识点
      const wrong = readQuizWrong(l.id)
      if (wrong.length) {
        const mastered = wrong.filter((q) => readMastered(l.id)[q]).length
        parts.push(`测验错 ${wrong.length} 题${mastered ? `（变式题已掌握 ${mastered}）` : ''}`)
      }
      if (pr.exercises) parts.push(`应用题 ${pr.exercises} 次`)
      if (pr.reads) parts.push(`阅读 ${pr.reads} 次`)
      lines.push(`- ${parts.join('；')}`)
    }
  }
  return lines.join('\n')
}

async function getPlan() {
  if (planBusy.value) return
  plan.value = ''
  planError.value = ''
  planBusy.value = true
  try {
    const result = await streamPlan({ summary: buildProgressSummary() }, (d) => {
      plan.value += d
    })
    if (result.error) planError.value = result.error
  } catch {
    // 中止等：忽略
  } finally {
    planBusy.value = false
  }
}

// 错题汇总：读各课随堂测验每题最佳分（ql:quizResults）+ 应用题批改得分（exerciseScores）
function buildReviewSummary(): string {
  const lines: string[] = []
  let wrongCount = 0
  const wrongLessons: string[] = []
  const weakExercises: string[] = []
  for (const p of phases.value) {
    for (const l of p.lessons) {
      const wrong = readQuizWrong(l.id)
      if (wrong.length) {
        wrongCount += wrong.length
        const mastered = wrong.filter((q) => readMastered(l.id)[q]).length
        const titles = wrong
          .slice(0, 15)
          .map((q) => (q.length > 120 ? `${q.slice(0, 120)}…` : q))
        wrongLessons.push(
          `《${l.title}》：${titles.join(' | ')}${mastered ? `（其中 ${mastered} 题变式题已掌握）` : ''}`,
        )
      }
      // 应用题低分（<60）也是弱项
      const scores = (getProgress(l.id)?.exerciseScores ?? []).filter((s) => s < 60)
      if (scores.length) {
        weakExercises.push(`《${l.title}》应用题最近得分 ${scores[scores.length - 1]}（共 ${scores.length} 次低分）`)
      }
    }
  }
  lines.push(`错题数：${wrongCount} 题（随堂测验每题最佳分未满分）。`)
  lines.push(wrongLessons.length ? `错题清单：\n${wrongLessons.map((x) => `- ${x}`).join('\n')}` : '暂无错题。')
  if (weakExercises.length) {
    lines.push(`应用题弱项：\n${weakExercises.map((x) => `- ${x}`).join('\n')}`)
  }
  lines.push('')
  lines.push('学习进度概览：')
  lines.push(buildProgressSummary())
  return lines.join('\n')
}

async function getReview() {
  if (reviewBusy.value) return
  review.value = ''
  reviewError.value = ''
  reviewBusy.value = true
  try {
    const result = await streamReview(buildReviewSummary(), (d) => {
      review.value += d
    })
    if (result.error) reviewError.value = result.error
  } catch {
    // 中止等：忽略
  } finally {
    reviewBusy.value = false
  }
}

// 全部课程（title→id），供 AI 输出里的课程名渲染成可点击链接
const allLessons = computed(() =>
  phases.value.flatMap((p) => p.lessons.map((l: any) => ({ title: l.title, id: l.id }))),
)
const planLinked = computed(() => linkifyCourses(plan.value, allLessons.value))
const reviewLinked = computed(() => linkifyCourses(review.value, allLessons.value))

async function load() {
  loading.value = true
  error.value = ''
  try {
    phases.value = await fetchCourses()
  } catch (e: any) {
    error.value = e.message || '加载课程失败'
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  try {
    lastPath.value = localStorage.getItem(LAST_PATH_KEY) ?? ''
  } catch {
    lastPath.value = ''
  }
  await load()
  loadBacktest()
})

const resume = computed(() => {
  const p = lastPath.value
  if (!p || !p.startsWith('/lesson/')) return null
  const id = p.slice('/lesson/'.length).split('?')[0]
  for (const ph of phases.value) {
    const l = ph.lessons.find((x: any) => x.id === id)
    if (l) return { id, title: l.title, path: p }
  }
  return null
})

function phaseProgress(p: any): { done: number; total: number } {
  const total = p.lessons.length
  const done = p.lessons.filter((l: any) => isCompleted(l.id)).length
  return { done, total }
}

function progressPct(p: any): number {
  const { done, total } = phaseProgress(p)
  return total ? Math.round((done / total) * 100) : 0
}

function goPhase(p: any) {
  if (p.lessons.length) router.push(`/phase/${p.phase}`)
}

// Hero「开始学习」：有上次学习记录则续读，否则从第一章入口开始
function startLearning() {
  router.push(resume.value?.path ?? '/phase/0')
}

// 学习总进度
const overall = computed(() => {
  let done = 0, total = 0
  for (const p of phases.value) {
    const t = phaseProgress(p)
    done += t.done; total += t.total
  }
  return { done, total, pct: total ? Math.round((done / total) * 100) : 0 }
})

// 真实学习统计（学习天数 / 沙箱运行 / 练习提交）已移至「我的」页（MyView）

// ---------- Hero 组合净值 · 回测（真实回测净值曲线） ----------
let backtestsCache: BacktestResult[] | null = null
const backtest = ref<BacktestResult | null>(null)

async function loadBacktest() {
  try {
    // 取夏普最高的回测展示（真实数据：组合净值 / 基准净值）
    if (!backtestsCache) backtestsCache = await fetchBacktests(20)
    const withNav = (backtestsCache ?? []).filter(
      (r) => r.nav && r.nav.dates.length > 1 && r.nav.portfolio.length > 1 && r.nav.benchmark.length > 1,
    )
    withNav.sort((a, b) => (b.sharpe ?? -Infinity) - (a.sharpe ?? -Infinity))
    backtest.value = withNav[0] ?? null
  } catch {
    backtest.value = null
  }
}

const navData = computed(() => backtest.value?.nav ?? null)

// 区间累计收益（净值末/首 - 1）
const cumReturn = computed(() => {
  const nav = navData.value
  if (!nav || !nav.portfolio.length) return 0
  const p = nav.portfolio
  return (p[p.length - 1] / p[0] - 1) * 100
})
const benchReturn = computed(() => {
  const nav = navData.value
  if (!nav || !nav.benchmark.length) return 0
  const b = nav.benchmark
  return (b[b.length - 1] / b[0] - 1) * 100
})
const beatBench = computed(() => cumReturn.value > benchReturn.value)
const cumText = computed(() => {
  const v = cumReturn.value
  return `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`
})

// 等宽采样到 ≤100 点，保持两条曲线对齐
function downsample(arr: number[], max = 100): number[] {
  if (arr.length <= max) return arr
  const step = (arr.length - 1) / (max - 1)
  const out: number[] = []
  for (let i = 0; i < max; i++) out.push(arr[Math.round(i * step)])
  return out
}

// 组合/基准同尺度折线 + 组合面积填充
const chartPaths = computed(() => {
  const nav = navData.value
  if (!nav) return { port: '', bench: '', area: '' }
  const W = 320, H = 120, PAD = 8
  const p = downsample(nav.portfolio)
  const b = downsample(nav.benchmark)
  const all = [...p, ...b]
  const min = Math.min(...all)
  const max = Math.max(...all)
  const range = max - min || 1
  const x = (i: number, n: number) => PAD + (i / (n - 1)) * (W - 2 * PAD)
  const y = (v: number) => H - PAD - ((v - min) / range) * (H - 2 * PAD)
  const line = (arr: number[]) =>
    arr.map((v, i) => `${i ? 'L' : 'M'}${x(i, arr.length).toFixed(1)} ${y(v).toFixed(1)}`).join(' ')
  const port = line(p)
  const bench = line(b)
  const area = `${port} L${x(p.length - 1, p.length).toFixed(1)} ${H} L${x(0, p.length).toFixed(1)} ${H} Z`
  return { port, bench, area }
})

// 横轴刻度：起 / 中 / 末（YYYY-MM）
const xLabels = computed(() => {
  const nav = navData.value
  if (!nav || !nav.dates.length) return ['', '', '']
  const d = nav.dates
  return [d[0], d[Math.floor(d.length / 2)], d[d.length - 1]].map((s) => s.slice(0, 7))
})

const BENCH_NAMES: Record<string, string> = {
  SH000300: '沪深300',
  SH000905: '中证500',
  SH000852: '中证1000',
  SH000016: '上证50',
  SH000688: '科创50',
  SZ399006: '创业板指',
}
const benchmarkName = computed(() => {
  const b = backtest.value?.benchmark ?? ''
  return BENCH_NAMES[b] || b
})

const METHOD_NAMES: Record<string, string> = {
  equal_weight: '等权组合',
  value_weight: '市值加权',
  ic_weight: 'IC 加权',
  max_sharpe: '最大夏普组合',
  risk_parity: '风险平价',
}
const methodName = computed(
  () => METHOD_NAMES[backtest.value?.combination_method ?? ''] || backtest.value?.combination_method || '多因子组合',
)

const periodText = computed(() => {
  const nav = navData.value
  if (!nav || !nav.dates.length) return ''
  return `${nav.dates[0].slice(0, 7)} → ${nav.dates[nav.dates.length - 1].slice(0, 7)}`
})

// 精选模拟器：目标指向真实课程（装饰性 mini 图为示意，非数据）
interface FeaturedSim { title: string; desc: string; to: string; svg: string }
const featuredSims: FeaturedSim[] = [
  {
    title: 'BS 期权定价',
    desc: '看波动率如何影响期权价格。',
    to: '/lesson/p5-l2',
    svg: `<svg viewBox="0 0 200 100" preserveAspectRatio="none"><path d="M0 70 Q50 20 100 60 T200 40" fill="none" stroke="var(--chart-1)" stroke-width="3" stroke-linecap="round"/><path d="M0 80 Q50 50 100 75 T200 65" fill="none" stroke="var(--chart-3)" stroke-width="2.5" opacity="0.7"/></svg>`,
  },
  {
    title: '蒙特卡洛模拟',
    desc: '路径模拟与分布收敛。',
    to: '/lesson/p5-l3',
    svg: `<svg viewBox="0 0 200 100" preserveAspectRatio="none"><g fill="var(--chart-2)"><rect x="12" y="58" width="16" height="30" rx="2"/><rect x="40" y="38" width="16" height="50" rx="2"/><rect x="68" y="52" width="16" height="36" rx="2"/><rect x="96" y="22" width="16" height="66" rx="2"/><rect x="124" y="46" width="16" height="42" rx="2"/><rect x="152" y="14" width="16" height="74" rx="2"/></g></svg>`,
  },
  {
    title: '有效前沿',
    desc: '风险与收益的权衡边界。',
    to: '/lesson/p7-l1',
    svg: `<svg viewBox="0 0 200 100" preserveAspectRatio="none"><path d="M8 88 Q90 55 192 12" fill="none" stroke="var(--chart-4)" stroke-width="2.5" stroke-dasharray="4 4" opacity="0.6"/><circle cx="30" cy="78" r="4" fill="var(--chart-3)" opacity="0.5"/><circle cx="52" cy="70" r="4" fill="var(--chart-3)" opacity="0.5"/><circle cx="78" cy="58" r="4" fill="var(--chart-3)" opacity="0.5"/><circle cx="118" cy="36" r="5" fill="var(--chart-4)"/><circle cx="150" cy="24" r="5" fill="var(--chart-4)"/><circle cx="176" cy="14" r="5" fill="var(--chart-4)"/></svg>`,
  },
  {
    title: '梯度下降',
    desc: '直观感受学习率的选择。',
    to: '/lesson/p0-l4',
    svg: `<svg viewBox="0 0 200 100" preserveAspectRatio="none"><path d="M10 16 L66 42 L116 60 L158 72 L192 82" fill="none" stroke="var(--chart-6)" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/><circle cx="10" cy="16" r="5" fill="var(--chart-6)"/><circle cx="192" cy="82" r="6" fill="var(--chart-6)"/></svg>`,
  },
  {
    title: '杜邦分解',
    desc: '拆开 ROE，看懂盈利的引擎。',
    to: '/lesson/p2-l2',
    svg: `<svg viewBox="0 0 200 100" preserveAspectRatio="none"><rect x="16" y="20" width="120" height="14" rx="3" fill="var(--chart-1)"/><rect x="16" y="46" width="84" height="14" rx="3" fill="var(--chart-2)"/><rect x="16" y="72" width="102" height="14" rx="3" fill="var(--chart-3)"/></svg>`,
  },
  {
    title: '配对交易',
    desc: '协整价差与均值回复。',
    to: '/lesson/p7-l2',
    svg: `<svg viewBox="0 0 200 100" preserveAspectRatio="none"><path d="M10 24 Q100 40 190 28" fill="none" stroke="var(--chart-1)" stroke-width="2.5"/><path d="M10 76 Q100 62 190 72" fill="none" stroke="var(--chart-5)" stroke-width="2.5"/><path d="M10 50 Q70 20 120 78 T190 50" fill="none" stroke="var(--chart-3)" stroke-width="2" stroke-dasharray="4 3"/></svg>`,
  },
]

function keyEnter(e: KeyboardEvent, fn: () => void) {
  e.preventDefault()
  fn()
}

function goResume() {
  if (resume.value) router.push(resume.value.path)
}
</script>

<template>
  <div class="home2">
    <!-- HERO：开场 + CTA + 统计 + 真实学习进度卡（借鉴设计包 home.html） -->
    <section class="hero">
      <div class="hero-main">
        <span class="eyebrow">渐进式量化学习</span>
        <h1>从 0 到量化高手</h1>
        <p class="lead">{{ overall.total }} 课系统课程 · 75+ 交互模拟器 · 10 年真实 A 股数据。每个核心概念都看得见、摸得着，学完即用。</p>
        <div class="hero-cta">
          <button class="btn btn-primary btn-lg" @click="startLearning">开始学习</button>
          <button class="btn btn-outline btn-lg" @click="router.push('/data-browser')">浏览数据</button>
        </div>
        <div class="hero-stats">
          <div class="hs"><b class="num">{{ overall.total }}</b><span>系统课程</span></div>
          <div class="hs"><b class="num">75<span class="unit">+</span></b><span>交互模拟器</span></div>
          <div class="hs"><b class="num">10<span class="unit">年</span></b><span>真实数据</span></div>
          <div class="hs"><b class="num">{{ overall.pct }}<span class="unit">%</span></b><span>你的进度</span></div>
        </div>
      </div>

      <!-- hero-visual：组合净值 · 回测（真实回测净值曲线；数据不可用时兜底为学习进度） -->
      <div class="hero-visual">
        <template v-if="backtest && navData">
          <div class="hv-head">
            <span class="hv-title">组合净值 · 回测</span>
            <span class="badge badge-dot" :class="beatBench ? 'badge-success' : 'badge-danger'">
              {{ beatBench ? '跑赢基准' : '跑输基准' }}
            </span>
          </div>
          <div class="hv-val" :class="cumReturn >= 0 ? 'up' : 'down'">{{ cumText }}</div>
          <svg class="hv-chart" viewBox="0 0 320 120" width="100%" height="120" preserveAspectRatio="none" aria-hidden="true">
            <defs>
              <linearGradient id="hv-grad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0" style="stop-color: var(--chart-1); stop-opacity: 0.28" />
                <stop offset="1" style="stop-color: var(--chart-1); stop-opacity: 0" />
              </linearGradient>
            </defs>
            <path :d="chartPaths.area" fill="url(#hv-grad)" />
            <path :d="chartPaths.port" fill="none" stroke="var(--chart-1)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" />
            <path :d="chartPaths.bench" fill="none" stroke="var(--chart-3)" stroke-width="1.8" stroke-dasharray="4 3" opacity="0.85" />
          </svg>
          <div class="hv-x">
            <span>{{ xLabels[0] }}</span><span>{{ xLabels[1] }}</span><span>{{ xLabels[2] }}</span>
          </div>
          <div class="hv-legend">
            <span class="lg"><i class="lgt c1"></i>组合</span>
            <span class="lg"><i class="lgt c3"></i>{{ benchmarkName }}</span>
          </div>
          <div class="hv-meta">{{ methodName }} · {{ periodText }}</div>
        </template>

        <!-- 回测数据不可用时的占位（学习总进度已移至「我的」页） -->
        <template v-else>
          <div class="hv-head">
            <span class="hv-title">组合净值 · 回测</span>
            <span class="badge">数据暂不可用</span>
          </div>
          <div class="hv-empty">回测数据加载中…</div>
        </template>
      </div>
    </section>

    <AppSpinner v-if="loading" text="加载课程…" />
    <AppError v-else-if="error" :message="error" @retry="load" />

    <template v-else>
      <!-- 继续上次学习（显式入口，置于阶段列表上方，不遮挡全局进度） -->
      <section
        v-if="resume"
        class="resume-card"
        role="button"
        tabindex="0"
        @click="goResume"
        @keydown.enter="keyEnter($event, goResume)"
        @keydown.space.prevent="keyEnter($event, goResume)"
      >
        <div class="resume-info">
          <div class="resume-label"><PlayCircle :size="13" /> 继续上次学习</div>
          <div class="resume-title">{{ resume.title }}</div>
        </div>
        <span class="resume-arrow"><ArrowRight :size="18" /></span>
      </section>

      <!-- 课程地图 -->
      <section class="section">
        <div class="section-head">
          <div>
            <h2>课程地图</h2>
            <p>七个阶段，从数学基础一路走到组合优化。</p>
          </div>
          <button class="btn btn-ghost btn-sm" @click="router.push('/phase/0')">查看全部 →</button>
        </div>
        <div class="phases">
          <div
            v-for="p in phases"
            :key="p.phase"
            class="card card-hover phase"
            role="button"
            tabindex="0"
            @click="goPhase(p)"
            @keydown.enter="keyEnter($event, () => goPhase(p))"
            @keydown.space.prevent="keyEnter($event, () => goPhase(p))"
          >
            <div class="top">
              <div class="no">{{ chapterLabel(p.phase) }}</div>
              <div class="txt">
                <h4>{{ p.title }}</h4>
                <div class="sub">{{ p.subtitle }}</div>
              </div>
            </div>
            <div class="progress bar"><i :style="{ width: progressPct(p) + '%' }"></i></div>
            <div class="foot">
              <span>{{ phaseProgress(p).done }}/{{ phaseProgress(p).total }} 课</span>
              <span class="badge" :class="phaseStatus[p.status]?.cls || 'badge'">{{ phaseStatus[p.status]?.label || p.status }}</span>
            </div>
          </div>
        </div>
      </section>

      <!-- 精选交互模拟器 -->
      <section class="section">
        <div class="section-head">
          <div>
            <h2>精选交互模拟器</h2>
            <p>拖动参数，立即看到现象变化。</p>
          </div>
          <button class="btn btn-ghost btn-sm" @click="router.push('/lab')">去实验室 →</button>
        </div>
        <div class="sims">
          <div
            v-for="s in featuredSims"
            :key="s.title"
            class="card card-hover sim"
            role="button"
            tabindex="0"
            @click="router.push(s.to)"
            @keydown.enter="keyEnter($event, () => router.push(s.to))"
            @keydown.space.prevent="keyEnter($event, () => router.push(s.to))"
          >
            <div class="viz" v-html="s.svg"></div>
            <h4>{{ s.title }}</h4>
            <p>{{ s.desc }}</p>
          </div>
        </div>
      </section>

      <!-- AI 学习助手 -->
      <section class="section">
        <div class="section-head">
          <div>
            <h2>AI 学习助手</h2>
            <p>根据你的学习进度，生成复习重点与下一步路径。</p>
          </div>
        </div>
        <div class="ai-grid">
          <div class="card ai-card">
            <div class="ai-head">
              <div>
                <div class="ai-title"><Sparkles :size="15" /> AI 学习规划</div>
                <div class="ai-sub">推荐复习重点与下一步路径</div>
              </div>
              <button class="btn btn-primary btn-sm" :disabled="planBusy" @click="getPlan">
                {{ planBusy ? '生成中…' : '生成规划' }}
              </button>
            </div>
            <div v-if="planError" class="ai-error">{{ planError }}</div>
            <PlanCard v-if="plan" :plan="planLinked" />
          </div>

          <div class="card ai-card">
            <div class="ai-head">
              <div>
                <div class="ai-title"><Target :size="15" /> 错题弱项复习</div>
                <div class="ai-sub">针对测验错题与应用题低分给建议</div>
              </div>
              <button class="btn btn-primary btn-sm" :disabled="reviewBusy" @click="getReview">
                {{ reviewBusy ? '生成中…' : '生成复习建议' }}
              </button>
            </div>
            <div v-if="reviewError" class="ai-error">{{ reviewError }}</div>
            <PlanCard v-if="review" :plan="reviewLinked" />
          </div>
        </div>
      </section>

      <!-- CTA 收尾带 -->
      <section class="section">
        <div class="cta-band">
          <div>
            <h2>今天，搞懂一个量化概念</h2>
            <p>从一节 15 分钟的小课开始，配套模拟器与即时测验，让知识真正可用。</p>
          </div>
          <button class="cta-btn" @click="startLearning">免费开始</button>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
/* 设计 token 全部来自全局 main.css（已按设计包 tokens.css 落地）；
   本组件只做布局与组件样式 */
.home2 {
  max-width: 1080px;
  margin: 0 auto;
}

/* ============ Hero（对齐设计包 home.html） ============ */
.hero {
  display: grid;
  grid-template-columns: 1.1fr 0.9fr;
  gap: 40px;
  align-items: center;
  padding: clamp(28px, 5vw, 64px) 0 clamp(24px, 4vw, 40px);
}
.hero .eyebrow {
  display: inline-block;
  font-family: var(--font-mono);
  font-size: var(--fs-xs);
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--primary);
  font-weight: 600;
  margin-bottom: 16px;
}
.hero h1 { font-size: var(--fs-3xl); margin-bottom: 16px; max-width: 14ch; letter-spacing: -0.02em; }
.hero .lead { color: var(--text-2); font-size: var(--fs-md); max-width: 46ch; margin-bottom: 26px; line-height: 1.8; }
.hero-cta { display: flex; gap: 12px; flex-wrap: wrap; }
.hero-stats { display: flex; gap: 28px; margin-top: 32px; flex-wrap: wrap; }
.hs b { font-family: var(--font-mono); font-size: var(--fs-lg); font-weight: 600; line-height: 1.15; display: block; }
.hs .unit { font-size: 0.6em; }
.hs span:not(.unit) { font-size: var(--fs-xs); color: var(--text-3); }

/* hero-visual：真实进度卡 */
.hero-visual {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--r-xl);
  padding: 24px;
  box-shadow: var(--shadow-md);
}
.hv-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
.hv-title { font-family: var(--font-mono); font-size: var(--fs-xs); color: var(--text-3); letter-spacing: 0.06em; }
.hv-val { font-family: var(--font-mono); font-size: var(--fs-num); font-weight: 600; line-height: 1.1; letter-spacing: -0.02em; }
.hv-val.up { color: var(--up); }
.hv-val.down { color: var(--down); }
.hv-chart { display: block; margin-top: 8px; }
.hv-x {
  display: flex; justify-content: space-between;
  font-family: var(--font-mono); font-size: var(--fs-xs); color: var(--text-3);
  margin-top: 8px;
}
.hv-legend { display: flex; gap: 16px; margin-top: 12px; font-size: var(--fs-xs); color: var(--text-2); }
.hv-legend .lg { display: inline-flex; align-items: center; gap: 6px; }
.hv-legend .lgt { width: 14px; height: 3px; border-radius: 2px; display: inline-block; }
.hv-legend .lgt.c1 { background: var(--chart-1); }
.hv-legend .lgt.c3 { background: var(--chart-3); }
.hv-meta { margin-top: 8px; font-size: var(--fs-xs); color: var(--text-3); }
.hv-bar { height: 8px; border-radius: var(--r-pill); background: var(--bg-hover); overflow: hidden; margin: 12px 0 6px; }
.hv-fill { height: 100%; border-radius: var(--r-pill); background: var(--primary); transition: width 0.4s var(--ease-out); }
.hv-sub { font-size: var(--fs-sm); color: var(--text-3); }
.hv-mini {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-top: 18px;
  padding-top: 16px;
  border-top: 1px solid var(--border);
}
.hv-mini .mini b { font-family: var(--font-mono); font-size: var(--fs-md); font-weight: 600; display: block; line-height: 1.2; }
.hv-mini .mini span { font-size: var(--fs-xs); color: var(--text-3); }

/* ============ 按钮（对齐设计包 components.css） ============ */
.btn {
  display: inline-flex; align-items: center; justify-content: center; gap: 8px;
  padding: 10px 18px;
  font-family: var(--font-base); font-size: var(--fs-base); font-weight: 600; line-height: 1;
  color: var(--text-1); background: var(--bg-card);
  border: 1px solid var(--border-strong); border-radius: var(--r-sm);
  cursor: pointer; user-select: none; white-space: nowrap;
  transition: background 0.16s var(--ease-out), border-color 0.16s var(--ease-out),
              transform 0.16s var(--ease-out), box-shadow 0.16s var(--ease-out);
}
.btn:hover { transform: translateY(-1px); }
.btn:active { transform: translateY(0); }
.btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
.btn-primary { background: var(--primary); border-color: var(--primary); color: #fff; }
.btn-primary:hover { background: var(--primary-hover); border-color: var(--primary-hover); box-shadow: var(--shadow-md); }
.btn-outline { background: transparent; border-color: var(--primary); color: var(--primary); }
.btn-outline:hover { background: var(--primary-soft); }
.btn-ghost { background: transparent; border-color: transparent; color: var(--text-2); }
.btn-ghost:hover { background: var(--bg-hover); color: var(--text-1); }
.btn-sm { padding: 7px 13px; font-size: var(--fs-sm); }
.btn-lg { padding: 13px 24px; font-size: var(--fs-md); }

/* ============ 区块节奏 ============ */
.section { padding: clamp(36px, 5vw, 64px) 0; }
.section-head { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; margin-bottom: var(--sp-5); flex-wrap: wrap; }
.section-head h2 { font-size: var(--fs-2xl); letter-spacing: -0.01em; }
.section-head p { color: var(--text-3); font-size: var(--fs-sm); margin-top: 6px; }

/* ============ 卡片（对齐设计包 components.css） ============ */
.card {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: var(--r-lg); box-shadow: var(--shadow-xs); padding: 24px;
  transition: border-color 0.24s var(--ease-out), transform 0.24s var(--ease-out), box-shadow 0.24s var(--ease-out);
}
.card-hover:hover { border-color: color-mix(in srgb, var(--primary) 45%, var(--border)); transform: translateY(-3px); box-shadow: var(--shadow-md); }
.card-hover:focus-visible { outline: 2px solid var(--primary); outline-offset: 2px; }

/* ============ 课程地图（对齐设计包 home.html 的 phase 卡） ============ */
.phases { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 24px; }
.phase { display: flex; flex-direction: column; gap: 12px; cursor: pointer; }
.phase .top { display: flex; align-items: center; gap: 12px; }
.phase .no {
  min-width: 46px; height: 46px; padding: 0 10px; flex: none;
  border-radius: var(--r-md);
  background: var(--primary-soft); color: var(--primary);
  font-family: var(--font-display); font-weight: 700; font-size: 13px; letter-spacing: 0.5px;
  display: grid; place-content: center;
}
.phase .txt { min-width: 0; }
.phase h4 { font-size: var(--fs-md); }
.phase .sub { font-size: var(--fs-sm); color: var(--text-3); }
.phase .bar { margin-top: auto; }
.phase .foot { display: flex; align-items: center; justify-content: space-between; font-size: var(--fs-xs); color: var(--text-3); }

/* 进度条 */
.progress { height: 7px; border-radius: var(--r-pill); background: var(--bg-hover); overflow: hidden; }
.progress i { display: block; height: 100%; border-radius: var(--r-pill); background: var(--primary); transition: width 0.4s var(--ease-out); }

/* ============ 精选模拟器（对齐设计包 home.html） ============ */
.sims { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 24px; }
.sim { display: flex; flex-direction: column; gap: 10px; cursor: pointer; }
.sim .viz {
  height: 110px;
  border-radius: var(--r-md);
  background: var(--bg-subtle);
  overflow: hidden;
  display: grid; place-items: center;
}
.sim .viz :deep(svg) { width: 100%; height: 100%; display: block; }
.sim h4 { font-size: var(--fs-md); }
.sim p { font-size: var(--fs-sm); color: var(--text-3); }

/* ============ 继续上次学习 ============ */
.resume-card {
  display: flex; align-items: center; justify-content: space-between; gap: 16px;
  background: var(--bg-card); border: 1px solid var(--primary);
  border-radius: var(--r-lg); padding: 16px 20px;
  cursor: pointer; box-shadow: var(--shadow-sm);
  transition: all 0.15s var(--ease-out); margin-bottom: 4px;
}
.resume-card:hover { box-shadow: var(--shadow-md); background: var(--primary-soft); }
.resume-card:focus-visible { outline: 2px solid var(--primary); outline-offset: 2px; }
.resume-label { font-size: var(--fs-xs); color: var(--primary); font-weight: 600; margin-bottom: 2px; display: flex; align-items: center; gap: 6px; }
.resume-title { font-size: 16px; font-weight: 600; color: var(--text-1); }
.resume-arrow { color: var(--primary); flex-shrink: 0; display: flex; }

/* ============ AI 学习助手 ============ */
.ai-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
.ai-card { padding: 20px 24px; }
.ai-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; }
.ai-title { font-size: 15px; font-weight: 600; color: var(--primary); display: flex; align-items: flex-start; gap: 8px; }
.ai-title svg { margin-top: 2px; flex-shrink: 0; }
.ai-sub { font-size: var(--fs-xs); color: var(--text-3); margin-top: 2px; }
.ai-error {
  margin-top: 12px; font-size: 13px; color: var(--danger, #dc2626);
  background: color-mix(in srgb, var(--danger, #dc2626) 8%, transparent);
  border-radius: 6px; padding: 8px 12px; line-height: 1.6;
}

/* ============ CTA 收尾带（对齐设计包 home.html） ============ */
.cta-band {
  background: var(--primary);
  border-radius: var(--r-xl);
  padding: clamp(28px, 5vw, 52px);
  color: #fff;
  display: flex; align-items: center; justify-content: space-between;
  gap: 24px; flex-wrap: wrap;
}
.cta-band h2 { color: #fff; font-size: var(--fs-2xl); }
.cta-band p { color: color-mix(in srgb, #fff 82%, transparent); margin-top: 8px; max-width: 44ch; }
.cta-btn {
  background: #fff; color: var(--primary);
  border: none; cursor: pointer;
  padding: 13px 26px; font-size: var(--fs-md); font-weight: 600;
  border-radius: var(--r-sm);
  transition: transform 0.16s var(--ease-out), box-shadow 0.16s var(--ease-out);
}
.cta-btn:hover { transform: translateY(-1px); box-shadow: var(--shadow-lg); }

/* ============ 响应式（对齐设计包 home.html） ============ */
@media (max-width: 820px) {
  .hero { grid-template-columns: 1fr; gap: 28px; }
  .hero-visual { order: -1; }
  .ai-grid { grid-template-columns: 1fr; }
}
@media (max-width: 640px) {
  .hero-stats { gap: 20px; }
}
</style>
