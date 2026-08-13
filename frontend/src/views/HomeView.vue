<script setup lang="ts">
import { computed, defineAsyncComponent, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowRight, PlayCircle } from 'lucide-vue-next'
import { fetchCourses, streamPlan } from '@/api'
import { getProgress, isCompleted, learningDays, sandboxRunCount, totalExercises } from '@/stores/progress'
import { chapterLabel } from '@/utils/chapter'
import AppSpinner from '@/components/common/AppSpinner.vue'
import AppError from '@/components/common/AppError.vue'

// AI 规划结果懒加载渲染（避免 markdown-it/KaTeX 进首屏，仅生成后加载）
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

const phaseStatus: Record<string, { label: string; cls: string }> = {
  prereq: { label: '前置知识', cls: 'badge' },
  completed: { label: '已完成', cls: 'badge badge-success' },
  in_progress: { label: '进行中', cls: 'badge badge-primary' },
  planned: { label: '计划中', cls: 'badge' },
}

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
    <!-- 头部 -->
    <div class="page-head">
      <div>
        <h1>从 0 到量化高手</h1>
        <p class="muted">渐进式学习路径 · 每个概念都能看见、能动手</p>
      </div>
      <div class="overall-card">
        <div class="overall-label">总进度</div>
        <div class="overall-num">{{ overall.pct }}%</div>
        <div class="overall-bar"><div class="bar-fill" :style="{ width: overall.pct + '%' }"></div></div>
        <div class="faint overall-detail">{{ overall.done }}/{{ overall.total }} 课</div>
      </div>
    </div>

    <AppSpinner v-if="loading" text="加载课程…" />
    <AppError v-else-if="error" :message="error" @retry="load" />

    <!-- 继续上次学习（显式入口，替代自动跳转） -->
    <div v-else-if="resume" class="resume-card" role="button" tabindex="0" @click="router.push(resume.path)" @keydown.enter="router.push(resume.path)">
      <div class="resume-info">
        <div class="resume-label"><PlayCircle :size="13" /> 继续上次学习</div>
        <div class="resume-title">{{ resume.title }}</div>
      </div>
      <span class="resume-arrow"><ArrowRight :size="18" /></span>
    </div>

    <!-- 阶段列表 -->
    <div v-else class="phase-list">
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
        <PlanCard v-if="plan" :plan="plan" />
      </div>

      <div v-for="p in phases" :key="p.phase" class="phase-card" :class="{ active: p.status === 'in_progress' }" @click="goPhase(p)">
        <div class="phase-row">
          <span class="phase-num">{{ chapterLabel(p.phase) }}</span>
          <span :class="phaseStatus[p.status]?.cls || 'badge'">{{ phaseStatus[p.status]?.label || p.status }}</span>
        </div>
        <h2 class="phase-title">{{ p.title }}</h2>
        <p class="muted phase-subtitle">{{ p.subtitle }}</p>

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
  </div>
</template>

<style scoped>
.page { max-width: 960px; margin: 0 auto; }
.page-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 24px; margin-bottom: 28px; }
.page-head h1 { font-size: 26px; margin-bottom: 4px; }

.overall-card { width: 180px; background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius-md); padding: 14px 16px; box-shadow: var(--shadow-sm); }
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
.phase-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.phase-num { font-weight: 700; color: var(--primary); font-size: 13px; letter-spacing: 1px; }
.phase-title { font-size: 18px; margin-bottom: 2px; }
.phase-subtitle { font-size: 13px; }

.mini-progress { display: flex; align-items: center; gap: 10px; margin: 12px 0; }
.mini-bar { flex: 1; max-width: 200px; height: 6px; background: var(--bg-hover); border-radius: 3px; overflow: hidden; }
.mini-text { font-size: 12px; flex-shrink: 0; }

.chips { display: flex; flex-wrap: wrap; gap: 6px; }
.chip { font-size: 12px; padding: 3px 10px; border-radius: 999px; background: var(--bg-hover); color: var(--text-2); }
.chip.done { background: var(--success-soft); color: var(--success); }
</style>
