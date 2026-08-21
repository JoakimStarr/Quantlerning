<script setup lang="ts">
import { computed, defineAsyncComponent, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowRight, PlayCircle, Sparkles, Target } from 'lucide-vue-next'
import { fetchCourses, streamPlan, streamReview } from '@/api'
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

// 真实学习统计（学习天数 / 沙箱运行 / 练习提交）
const days = computed(() => learningDays())
const runs = computed(() => sandboxRunCount())
const exercises = computed(() => totalExercises())

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
        </div>
      </div>

      <!-- hero-visual：真实学习进度（数字全部来自进度存储，非示意） -->
      <div class="hero-visual">
        <div class="hv-head">
          <span class="hv-title">学习总进度</span>
          <span class="badge" :class="overall.pct >= 100 ? 'badge-success' : 'badge-primary'">
            {{ overall.pct >= 100 ? '已完成' : '进行中' }}
          </span>
        </div>
        <div class="hv-val num">{{ overall.pct }}%</div>
        <div class="hv-bar"><div class="hv-fill" :style="{ width: overall.pct + '%' }"></div></div>
        <div class="hv-sub">{{ overall.done }} / {{ overall.total }} 课完成</div>
        <div class="hv-mini">
          <div class="mini"><b class="num">{{ days }}</b><span>学习天数</span></div>
          <div class="mini"><b class="num">{{ runs }}</b><span>沙箱运行</span></div>
          <div class="mini"><b class="num">{{ exercises }}</b><span>练习提交</span></div>
        </div>
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
/* ============ 组件内设计 token（对齐设计包 tokens.css，作用域仅本组件） ============ */
.home2 {
  --bg-subtle: var(--bg-hover);
  --primary-active: var(--primary-hover);
  --fs-xs: 0.75rem;
  --fs-sm: 0.8125rem;
  --fs-base: 0.9375rem;
  --fs-md: 1.0625rem;
  --fs-lg: clamp(1.15rem, 1.05rem + 0.4vw, 1.375rem);
  --fs-xl: clamp(1.4rem, 1.2rem + 0.9vw, 1.875rem);
  --fs-2xl: clamp(1.6rem, 1.25rem + 1.6vw, 2.4rem);
  --fs-3xl: clamp(2rem, 1.5rem + 2.4vw, 3rem);
  --fs-num: clamp(1.6rem, 1.2rem + 1.6vw, 2.4rem);
  --sp-5: 24px;
  --r-sm: 8px;
  --r-md: 12px;
  --r-lg: 16px;
  --r-xl: 22px;
  --r-pill: 999px;
  --ease-out: cubic-bezier(0.22, 1, 0.36, 1);
  --shadow-xs: 0 1px 2px rgba(16, 24, 40, 0.05);
  --shadow-lg: 0 18px 40px rgba(16, 24, 40, 0.12), 0 6px 14px rgba(16, 24, 40, 0.07);
  /* 图表调色板（浅色） */
  --chart-1: #2f6ae8;
  --chart-2: #7c3aed;
  --chart-3: #0891b2;
  --chart-4: #d97706;
  --chart-5: #e03131;
  --chart-6: #db2777;

  max-width: 1080px;
  margin: 0 auto;
}

/* 深色主题下的本地图表色（跟随 html[data-theme]） */
[data-theme="dark"] .home2 {
  --chart-1: #5c93f5;
  --chart-2: #a78bfa;
  --chart-3: #22d3ee;
  --chart-4: #fbbf24;
  --chart-5: #f87171;
  --chart-6: #f472b6;
  --shadow-lg: 0 18px 40px rgba(0, 0, 0, 0.55), 0 6px 14px rgba(0, 0, 0, 0.36);
}

/* 等宽数字（对齐 tabular-nums） */
.num { font-family: var(--font-mono); font-variant-numeric: tabular-nums; font-feature-settings: "tnum" 1; }

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
