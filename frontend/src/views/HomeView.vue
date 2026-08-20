<script setup lang="ts">
import { computed, defineAsyncComponent, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowRight, PlayCircle, Target } from 'lucide-vue-next'
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
</script>

<template>
  <div class="page">
    <!-- Hero：开场 + CTA + 统计 + 总进度（借鉴设计包 home.html） -->
    <section class="hero">
      <div class="hero-main">
        <span class="eyebrow">渐进式量化学习</span>
        <h1>从 0 到量化高手</h1>
        <p class="lead">63 课系统课程 · 75+ 交互模拟器 · 10 年真实 A 股数据。每个核心概念都看得见、摸得着，学完即用。</p>
        <div class="hero-cta">
          <button class="btn btn-primary btn-lg" @click="startLearning">开始学习</button>
          <button class="btn btn-outline btn-lg" @click="router.push('/data-browser')">浏览数据</button>
        </div>
        <div class="hero-stats">
          <div class="hs"><b>{{ overall.total }}</b><span>系统课程</span></div>
          <div class="hs"><b>75+</b><span>交互模拟器</span></div>
          <div class="hs"><b>10<span class="hs-unit">年</span></b><span>真实数据</span></div>
        </div>
      </div>
      <div class="overall-card">
        <div class="overall-label">总进度</div>
        <div class="overall-num">{{ overall.pct }}%</div>
        <div class="overall-bar"><div class="bar-fill" :style="{ width: overall.pct + '%' }"></div></div>
        <div class="faint overall-detail">{{ overall.done }}/{{ overall.total }} 课</div>
      </div>
    </section>

    <AppSpinner v-if="loading" text="加载课程…" />
    <AppError v-else-if="error" :message="error" @retry="load" />

    <template v-else>
      <!-- 继续上次学习（显式入口，置于阶段列表上方，不遮挡全局进度） -->
      <div v-if="resume" class="resume-card" role="button" tabindex="0" @click="router.push(resume.path)" @keydown.enter="router.push(resume.path)" @keydown.space.prevent="router.push(resume.path)">
        <div class="resume-info">
          <div class="resume-label"><PlayCircle :size="13" /> 继续上次学习</div>
          <div class="resume-title">{{ resume.title }}</div>
        </div>
        <span class="resume-arrow"><ArrowRight :size="18" /></span>
      </div>

      <!-- 阶段列表 -->
      <div class="phase-list">
      <!-- AI 学习规划 -->
      <div class="plan-card">
        <div class="plan-head">
          <div>
            <div class="plan-title">AI 学习规划</div>
            <div class="plan-sub">根据你的学习进度，推荐复习重点与下一步路径</div>
          </div>
          <button class="btn btn-primary" :disabled="planBusy" @click="getPlan">
            {{ planBusy ? '生成中…' : '生成规划' }}
          </button>
        </div>
        <div v-if="planError" class="plan-error">{{ planError }}</div>
        <PlanCard v-if="plan" :plan="planLinked" />
      </div>

      <!-- 错题弱项复习 -->
      <div class="plan-card">
        <div class="plan-head">
          <div class="plan-title-row">
            <Target :size="15" />
            <div>
              <div class="plan-title">错题弱项复习</div>
              <div class="plan-sub">根据随堂测验错题与应用题低分，分析薄弱点并给出复习建议</div>
            </div>
          </div>
          <button class="btn btn-primary" :disabled="reviewBusy" @click="getReview">
            {{ reviewBusy ? '生成中…' : '生成复习建议' }}
          </button>
        </div>
        <div v-if="reviewError" class="plan-error">{{ reviewError }}</div>
        <PlanCard v-if="review" :plan="reviewLinked" />
      </div>

      <div v-for="p in phases" :key="p.phase" class="phase-card" :class="{ active: p.status === 'in_progress' }" @click="goPhase(p)">
        <div class="phase-top">
          <span class="phase-no">{{ chapterLabel(p.phase) }}</span>
          <div class="phase-txt">
            <h2 class="phase-title">{{ p.title }}</h2>
            <p class="muted phase-subtitle">{{ p.subtitle }}</p>
          </div>
          <span class="phase-badge" :class="phaseStatus[p.status]?.cls || 'badge'">{{ phaseStatus[p.status]?.label || p.status }}</span>
        </div>

        <!-- 进度条（有课程时显示） -->
        <div v-if="p.lessons.length" class="mini-progress">
          <div class="mini-bar"><div class="bar-fill" :style="{ width: progressPct(p) + '%' }"></div></div>
          <span class="faint mini-text">{{ phaseProgress(p).done }}/{{ phaseProgress(p).total }} 课</span>
        </div>

        <!-- 课程标签 -->
        <div v-if="p.lessons.length" class="chips">
          <span v-for="l in p.lessons" :key="l.id" class="chip" :class="{ done: isCompleted(l.id) }">
            {{ l.title }}
          </span>
        </div>
      </div>
      </div>
    </template>

    <!-- CTA 收尾带（借鉴设计包 home.html） -->
    <section class="cta-band">
      <div>
        <h2>今天，搞懂一个量化概念</h2>
        <p>从一节 15 分钟的小课开始，配套模拟器与即时测验，让知识真正可用。</p>
      </div>
      <button class="cta-btn" @click="startLearning">免费开始</button>
    </section>
  </div>
</template>

<style scoped>
.page { max-width: 960px; margin: 0 auto; }
/* ---------- Hero（借鉴设计包 home.html） ---------- */
.hero {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 32px;
  padding: 16px 0 32px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 24px;
}
.hero-main { flex: 1; min-width: 0; }
.eyebrow {
  display: inline-block;
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--primary);
  font-weight: 600;
  margin-bottom: 12px;
}
.hero h1 { font-size: 30px; font-weight: 700; letter-spacing: -0.01em; margin-bottom: 10px; }
.hero .lead { color: var(--text-2); font-size: 15px; line-height: 1.8; max-width: 52ch; }
.hero-cta { display: flex; gap: 10px; margin-top: 18px; flex-wrap: wrap; }
.hero-cta .btn-lg { padding: 11px 22px; font-size: 15px; }
.hero-cta .btn-outline {
  background: transparent;
  border-color: var(--border-strong);
  color: var(--text-2);
}
.hero-cta .btn-outline:hover { border-color: var(--primary); color: var(--primary); }
.hero-stats { display: flex; gap: 28px; margin-top: 24px; flex-wrap: wrap; }
.hs b { font-family: var(--font-mono); font-size: 22px; font-weight: 600; line-height: 1.15; display: block; }
.hs .hs-unit { font-size: 0.6em; }
.hs span { font-size: 12px; color: var(--text-3); }

.overall-card { width: 200px; flex-shrink: 0; background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius-md); padding: 16px 18px; box-shadow: var(--shadow-sm); }
.overall-label { font-size: 12px; color: var(--text-3); }
.overall-num { font-size: 26px; font-weight: 700; color: var(--primary); margin: 2px 0 8px; }
.overall-bar { height: 6px; background: var(--bg-hover); border-radius: 3px; overflow: hidden; margin-bottom: 4px; }
.bar-fill { height: 100%; background: var(--primary); border-radius: 3px; transition: width 0.3s; }
.overall-detail { font-size: 12px; }

.status { padding: 40px; text-align: center; }

.resume-card {
  display: flex; align-items: center; justify-content: space-between; gap: 16px;
  background: var(--bg-card); border: 1px solid var(--primary);
  border-radius: var(--radius-md); padding: 16px 20px;
  cursor: pointer; box-shadow: var(--shadow-sm);
  transition: all 0.15s; margin-bottom: 20px;
}
.resume-card:hover { box-shadow: var(--shadow-md); background: var(--primary-soft); }
.resume-card:focus-visible { outline: 2px solid var(--primary); outline-offset: 2px; }
.resume-label { font-size: 12px; color: var(--primary); font-weight: 600; margin-bottom: 2px; }
.resume-title { font-size: 16px; font-weight: 600; color: var(--text-1); }
.resume-arrow { font-size: 20px; color: var(--primary); flex-shrink: 0; }

.phase-list { display: flex; flex-direction: column; gap: 14px; }

.plan-card {
  background: var(--bg-card); border: 1px solid var(--primary);
  border-radius: var(--radius-md); padding: 16px 20px;
  box-shadow: var(--shadow-sm);
}
.plan-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; }
.plan-title { font-size: 15px; font-weight: 600; color: var(--primary); }
.plan-title-row { display: flex; align-items: flex-start; gap: 8px; }
.plan-title-row > svg { color: var(--primary); margin-top: 2px; flex-shrink: 0; }
.plan-sub { font-size: 12px; color: var(--text-3); margin-top: 2px; }
.plan-error {
  margin-top: 12px; font-size: 13px; color: var(--danger, #dc2626);
  background: color-mix(in srgb, var(--danger, #dc2626) 8%, transparent);
  border-radius: var(--radius-sm); padding: 8px 12px; line-height: 1.6;
}
.phase-card {
  background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius-md);
  padding: 20px 24px; cursor: pointer; transition: all 0.15s; box-shadow: var(--shadow-sm);
}
.phase-card:hover { border-color: var(--border-strong); box-shadow: var(--shadow-md); }
.phase-card.active { border-color: var(--primary); }
/* 阶段卡头部：序号方块 + 标题 + 状态徽章（借鉴设计包 home.html 的 phase 卡） */
.phase-top { display: flex; align-items: center; gap: 14px; margin-bottom: 10px; }
.phase-no {
  width: 46px; height: 46px; border-radius: 10px; flex-shrink: 0;
  background: var(--primary-soft); color: var(--primary);
  display: flex; align-items: center; justify-content: center;
  font-size: 13px; font-weight: 700; letter-spacing: 0.5px;
}
.phase-txt { flex: 1; min-width: 0; }
.phase-badge { margin-left: auto; flex-shrink: 0; }
.phase-title { font-size: 18px; margin-bottom: 2px; }
.phase-subtitle { font-size: 13px; }

.mini-progress { display: flex; align-items: center; gap: 10px; margin: 12px 0; }
.mini-bar { flex: 1; max-width: 200px; height: 6px; background: var(--bg-hover); border-radius: 3px; overflow: hidden; }
.mini-text { font-size: 12px; flex-shrink: 0; }

.chips { display: flex; flex-wrap: wrap; gap: 6px; }
.chip { font-size: 12px; padding: 3px 10px; border-radius: 999px; background: var(--bg-hover); color: var(--text-2); }
.chip.done { background: var(--success-soft); color: var(--success); }

/* CTA 收尾带（借鉴设计包 home.html） */
.cta-band {
  margin-top: 36px;
  background: var(--primary);
  border-radius: 16px;
  padding: 30px 34px;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  flex-wrap: wrap;
}
.cta-band h2 { color: #fff; font-size: 20px; }
.cta-band p { color: rgba(255, 255, 255, 0.85); font-size: 13px; margin-top: 6px; max-width: 46ch; }
.cta-btn {
  background: #fff; color: var(--primary);
  border: none; cursor: pointer;
  padding: 12px 26px; font-size: 15px; font-weight: 600;
  border-radius: var(--radius-sm);
  transition: transform 0.15s, box-shadow 0.15s;
}
.cta-btn:hover { transform: translateY(-1px); box-shadow: var(--shadow-md); }

/* 移动端：Hero 纵向堆叠，总进度卡占满 */
@media (max-width: 640px) {
  .hero { flex-direction: column; align-items: stretch; }
  .overall-card { width: 100%; }
  .hero-stats { gap: 20px; }
}

</style>
