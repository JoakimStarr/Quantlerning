<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { AlertTriangle, ArrowRight, BookOpen, CheckCircle2, Clock, PlayCircle, Target, Trophy } from 'lucide-vue-next'
import { fetchCourses } from '@/api'
import { getProgress, isCompleted, learningDays, sandboxRunCount, totalExercises, totalQuizPassed } from '@/stores/progress'
import { chapterLabel } from '@/utils/chapter'
import AppSpinner from '@/components/common/AppSpinner.vue'
import PageBreadcrumb from '@/components/common/PageBreadcrumb.vue'

// 「我的」个人学习页：总进度 + 统计 + 各阶段进度 + 错题弱项 + 已完成清单。
// 数据全部来自前端 localStorage（stores/progress + ql:quizResults / ql:mastered / ql:lastPath）。

const router = useRouter()
const phases = ref<any[]>([])
const loading = ref(true)

onMounted(async () => {
  try {
    lastPath.value = localStorage.getItem(LAST_PATH_KEY) ?? ''
  } catch {
    lastPath.value = ''
  }
  try {
    phases.value = await fetchCourses()
  } finally {
    loading.value = false
  }
})

const allLessons = computed(() => phases.value.flatMap((p: any) => p.lessons))

// ---------- 总进度 ----------
const done = computed(() => allLessons.value.filter((l: any) => isCompleted(l.id)).length)
const total = computed(() => allLessons.value.length)
const pct = computed(() => (total.value ? Math.round((done.value / total.value) * 100) : 0))

// ---------- 学习统计 ----------
const days = computed(() => learningDays())
const runs = computed(() => sandboxRunCount())
const exercises = computed(() => totalExercises())
const quizPassed = computed(() => totalQuizPassed())

const stats = computed(() => [
  { label: '已完成课程', value: `${done.value}/${total.value}`, hint: '阅读即完成', icon: BookOpen },
  { label: '完成率', value: `${pct.value}%`, hint: '总体进度', icon: Target },
  { label: '学习天数', value: `${days.value}`, hint: '有学习活动的天数', icon: Clock },
  { label: '沙箱运行', value: `${runs.value}`, hint: '代码练习次数', icon: Trophy },
  { label: '练习提交', value: `${exercises.value}`, hint: '测验+应用题+沙箱', icon: CheckCircle2 },
  { label: '测验通过', value: `${quizPassed.value}`, hint: '已答对的知识点测验', icon: Target },
])

// ---------- 继续上次学习 ----------
const LAST_PATH_KEY = 'ql:lastPath'
const lastPath = ref('')
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

function goResume() {
  if (resume.value) router.push(resume.value.path)
}

// ---------- 错题与弱项 ----------
// 掌握标记：变式题答对写入 ql:mastered:{lessonId}
function readMastered(lessonId: string): Record<string, boolean> {
  try {
    return JSON.parse(localStorage.getItem(`ql:mastered:${lessonId}`) ?? '{}') || {}
  } catch {
    return {}
  }
}
// 随堂测验每题最佳分（ql:quizResults）：<100 视为错题
function readQuizWrong(lessonId: string): string[] {
  let map: Record<string, number> = {}
  try {
    map = JSON.parse(localStorage.getItem(`ql:quizResults:${lessonId}`) ?? '{}') || {}
  } catch {
    map = {}
  }
  return Object.keys(map).filter((q) => Number(map[q]) < 100)
}

const weakLessons = computed(() =>
  allLessons.value
    .map((l: any) => {
      const wrong = readQuizWrong(l.id)
      const mastered = wrong.filter((q) => readMastered(l.id)[q]).length
      const lowScores = (getProgress(l.id)?.exerciseScores ?? []).filter((s) => s < 60)
      return { lesson: l, wrong, mastered, lowScores }
    })
    .filter((x) => x.wrong.length || x.lowScores.length),
)
const wrongTotal = computed(() => weakLessons.value.reduce((n, x) => n + x.wrong.length, 0))
const masteredTotal = computed(() => weakLessons.value.reduce((n, x) => n + x.mastered, 0))
const lowScoreTotal = computed(() => weakLessons.value.reduce((n, x) => n + x.lowScores.length, 0))

// ---------- 已完成课程（按阶段） ----------
const completedByPhase = computed(() =>
  phases.value
    .map((p: any) => ({ ...p, lessons: p.lessons.filter((l: any) => isCompleted(l.id)) }))
    .filter((p: any) => p.lessons.length),
)

// 各阶段进度
function phaseProgress(p: any): { done: number; total: number } {
  return { done: p.lessons.filter((l: any) => isCompleted(l.id)).length, total: p.lessons.length }
}

function goPhase(p: any) {
  if (p.lessons.length) router.push(`/phase/${p.phase}`)
}
</script>

<template>
  <div class="my">
    <AppSpinner v-if="loading" text="加载学习数据…" />

    <template v-else>
      <!-- 页头 -->
      <header class="page-head">
        <PageBreadcrumb current="我的" />
        <span class="eyebrow">我的学习</span>
        <h1>学习总览</h1>
        <p class="lead">进度、活跃度与薄弱点，都记在本地。已完成 {{ total }} 课中的 {{ done }} 课，继续加油。</p>
      </header>

      <!-- 总进度 hero 卡 -->
      <section class="hero-card">
        <div class="hero-main">
          <span class="hv-title">总进度</span>
          <div class="hv-val num">{{ pct }}%</div>
          <div class="hv-bar"><div class="hv-fill" :style="{ width: pct + '%' }"></div></div>
          <div class="hv-sub">{{ done }} / {{ total }} 课完成</div>
        </div>
        <div class="hero-mini">
          <div class="mini"><b class="num">{{ days }}</b><span>学习天数</span></div>
          <div class="mini"><b class="num">{{ runs }}</b><span>沙箱运行</span></div>
          <div class="mini"><b class="num">{{ exercises }}</b><span>练习提交</span></div>
        </div>
      </section>

      <!-- 继续上次学习 -->
      <section v-if="resume" class="section">
        <div class="section-head">
          <div>
            <h2>继续上次学习</h2>
            <p>上次停在《{{ resume.title }}》</p>
          </div>
        </div>
        <div class="resume-card" role="button" tabindex="0" @click="goResume" @keydown.enter="goResume" @keydown.space.prevent="goResume">
          <div class="resume-info">
            <div class="resume-label"><PlayCircle :size="13" /> 接着读</div>
            <div class="resume-title">{{ resume.title }}</div>
          </div>
          <span class="resume-arrow"><ArrowRight :size="18" /></span>
        </div>
      </section>

      <!-- 学习统计 -->
      <section class="section">
        <div class="section-head">
          <div>
            <h2>学习统计</h2>
            <p>活跃度与练习量</p>
          </div>
        </div>
        <div class="stat-grid">
          <div v-for="s in stats" :key="s.label" class="stat-card">
            <component :is="s.icon" :size="16" class="stat-icon" />
            <div class="stat-value num">{{ s.value }}</div>
            <div class="stat-label">{{ s.label }}</div>
            <div class="stat-hint">{{ s.hint }}</div>
          </div>
        </div>
      </section>

      <!-- 各阶段进度 -->
      <section class="section">
        <div class="section-head">
          <div>
            <h2>各阶段进度</h2>
            <p>按阶段查看完成情况</p>
          </div>
        </div>
        <div class="phase-list">
          <div v-for="p in phases" :key="p.phase" class="phase-row" role="button" tabindex="0" @click="goPhase(p)" @keydown.enter="goPhase(p)">
            <div class="phase-name">
              <span class="phase-no">{{ chapterLabel(p.phase) }}</span>
              <div class="phase-txt">
                <div class="phase-title">{{ p.title }}</div>
                <div class="phase-sub">{{ phaseProgress(p).done }}/{{ phaseProgress(p).total }} 课</div>
              </div>
            </div>
            <div class="bar-track">
              <div class="bar-fill" :style="{ width: phaseProgress(p).total ? (phaseProgress(p).done / phaseProgress(p).total) * 100 + '%' : '0%' }"></div>
            </div>
            <span class="phase-pct num">{{ phaseProgress(p).total ? Math.round((phaseProgress(p).done / phaseProgress(p).total) * 100) : 0 }}%</span>
          </div>
        </div>
      </section>

      <!-- 错题与弱项 -->
      <section class="section">
        <div class="section-head">
          <div>
            <h2>错题与弱项</h2>
            <p>随堂测验错题、变式题掌握与应用题低分</p>
          </div>
        </div>

        <div class="weak-grid">
          <div class="weak-card"><AlertTriangle :size="15" class="wk danger" /><b class="num">{{ wrongTotal }}</b><span>测验错题</span></div>
          <div class="weak-card"><CheckCircle2 :size="15" class="wk success" /><b class="num">{{ masteredTotal }}</b><span>变式题已掌握</span></div>
          <div class="weak-card"><Target :size="15" class="wk warn" /><b class="num">{{ lowScoreTotal }}</b><span>应用题低分</span></div>
        </div>

        <div v-if="weakLessons.length" class="weak-list">
          <div v-for="w in weakLessons" :key="w.lesson.id" class="weak-item">
            <span class="weak-lesson">{{ w.lesson.title }}</span>
            <div class="weak-tags">
              <span v-if="w.wrong.length" class="tag danger">错 {{ w.wrong.length }} 题<template v-if="w.mastered">（已掌握 {{ w.mastered }}）</template></span>
              <span v-if="w.lowScores.length" class="tag warn">应用题 {{ w.lowScores[w.lowScores.length - 1] }} 分</span>
            </div>
            <RouterLink class="weak-go" :to="`/lesson/${w.lesson.id}`">去复习 →</RouterLink>
          </div>
        </div>
        <p v-else class="empty-hint">暂无错题，测验全对，保持。</p>
      </section>

      <!-- 已完成课程 -->
      <section class="section">
        <div class="section-head">
          <div>
            <h2>已完成课程</h2>
            <p>阅读过即算完成</p>
          </div>
        </div>
        <div v-if="completedByPhase.length" class="done-list">
          <div v-for="p in completedByPhase" :key="p.phase" class="done-phase">
            <span class="done-phase-label">{{ chapterLabel(p.phase) }}</span>
            <div class="done-chips">
              <RouterLink v-for="l in p.lessons" :key="l.id" class="chip" :to="`/lesson/${l.id}`">{{ l.title }}</RouterLink>
            </div>
          </div>
        </div>
        <p v-else class="empty-hint">还没有完成的课程，去读第一课吧。</p>
      </section>
    </template>
  </div>
</template>

<style scoped>
/* 设计 token 全部来自全局 main.css，与 HomeView2 / PhaseView2 一致 */
.my {
  max-width: 1080px;
  margin: 0 auto;
}

/* ============ 页头 ============ */
.page-head { padding: clamp(20px, 4vw, 40px) 0 clamp(16px, 3vw, 28px); }
.page-head .eyebrow {
  display: inline-block;
  font-family: var(--font-mono);
  font-size: var(--fs-xs);
  font-weight: 600;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--primary);
  margin-bottom: 12px;
}
.page-head h1 {
  font-size: var(--fs-2xl);
  letter-spacing: -0.02em;
  line-height: 1.15;
  margin: 0;
}
.page-head .lead {
  color: var(--text-2);
  font-size: var(--fs-md);
  line-height: 1.7;
  margin-top: 10px;
  max-width: 56ch;
}

/* ============ 总进度 hero 卡 ============ */
.hero-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 32px;
  flex-wrap: wrap;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--r-xl);
  padding: clamp(20px, 3vw, 32px);
  box-shadow: var(--shadow-md);
}
.hero-main { flex: 1; min-width: 240px; }
.hv-title { font-family: var(--font-mono); font-size: var(--fs-xs); color: var(--text-3); letter-spacing: 0.06em; }
.hv-val { font-family: var(--font-mono); font-size: var(--fs-num); font-weight: 600; line-height: 1.1; letter-spacing: -0.02em; color: var(--primary); margin: 8px 0 12px; }
.hv-bar { height: 10px; border-radius: var(--r-pill); background: var(--bg-hover); overflow: hidden; }
.hv-fill { height: 100%; border-radius: var(--r-pill); background: var(--primary); transition: width 0.4s var(--ease-out); }
.hv-sub { font-size: var(--fs-sm); color: var(--text-3); margin-top: 8px; }
.hero-mini {
  display: grid;
  grid-template-columns: repeat(3, minmax(96px, 1fr));
  gap: 12px;
}
.hero-mini .mini {
  background: var(--bg-subtle);
  border-radius: var(--r-lg);
  padding: 16px 18px;
  text-align: center;
}
.hero-mini .mini b { font-family: var(--font-mono); font-size: var(--fs-lg); font-weight: 600; display: block; line-height: 1.2; }
.hero-mini .mini span { font-size: var(--fs-xs); color: var(--text-3); }

/* ============ 区块节奏 ============ */
.section { padding: clamp(28px, 5vw, 48px) 0 0; }
.section-head { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; margin-bottom: var(--sp-5); flex-wrap: wrap; }
.section-head h2 { font-size: var(--fs-xl); letter-spacing: -0.01em; margin: 0; }
.section-head p { color: var(--text-3); font-size: var(--fs-sm); margin: 6px 0 0; }

/* ============ 继续上次学习 ============ */
.resume-card {
  display: flex; align-items: center; justify-content: space-between; gap: 16px;
  background: var(--bg-card); border: 1px solid var(--primary);
  border-radius: var(--r-lg); padding: 16px 20px;
  cursor: pointer; box-shadow: var(--shadow-sm);
  transition: all 0.15s var(--ease-out);
}
.resume-card:hover { box-shadow: var(--shadow-md); background: var(--primary-soft); }
.resume-card:focus-visible { outline: 2px solid var(--primary); outline-offset: 2px; }
.resume-label { font-size: var(--fs-xs); color: var(--primary); font-weight: 600; margin-bottom: 2px; display: flex; align-items: center; gap: 6px; }
.resume-title { font-size: 16px; font-weight: 600; color: var(--text-1); }
.resume-arrow { color: var(--primary); flex-shrink: 0; display: flex; }

/* ============ 统计卡 ============ */
.stat-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 14px; }
.stat-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--r-lg);
  box-shadow: var(--shadow-xs);
  padding: 18px;
  text-align: left;
  position: relative;
}
.stat-icon { position: absolute; top: 14px; right: 14px; color: var(--text-3); }
.stat-value { font-size: 26px; font-weight: 700; color: var(--text-1); line-height: 1.15; margin-bottom: 4px; }
.stat-label { font-size: 13px; color: var(--text-2); }
.stat-hint { font-size: 12px; color: var(--text-3); margin-top: 2px; }

/* ============ 各阶段进度 ============ */
.phase-list {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--r-lg);
  box-shadow: var(--shadow-xs);
  padding: 8px 20px;
}
.phase-row {
  display: flex; align-items: center; gap: 16px;
  padding: 14px 0; cursor: pointer;
  border-bottom: 1px solid var(--border);
}
.phase-row:last-child { border-bottom: none; }
.phase-row:hover .phase-title { color: var(--primary); }
.phase-name { display: flex; align-items: center; gap: 12px; width: 300px; flex-shrink: 0; min-width: 0; }
.phase-no {
  min-width: 40px; height: 40px; padding: 0 8px; flex: none;
  border-radius: var(--r-md);
  background: var(--primary-soft); color: var(--primary);
  font-family: var(--font-display); font-weight: 700; font-size: 12px;
  display: grid; place-content: center;
}
.phase-txt { min-width: 0; }
.phase-title { font-size: var(--fs-md); font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; transition: color 0.15s; }
.phase-sub { font-size: var(--fs-xs); color: var(--text-3); }
.bar-track { flex: 1; height: 8px; background: var(--bg-hover); border-radius: var(--r-pill); overflow: hidden; }
.bar-fill { height: 100%; background: var(--primary); border-radius: var(--r-pill); transition: width 0.4s var(--ease-out); }
.phase-pct { font-size: var(--fs-xs); color: var(--text-3); width: 40px; text-align: right; flex-shrink: 0; }

/* ============ 错题与弱项 ============ */
.weak-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 14px; margin-bottom: 14px; }
.weak-card {
  display: flex; align-items: center; gap: 10px;
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: var(--r-lg); box-shadow: var(--shadow-xs);
  padding: 16px 18px;
}
.weak-card b { font-family: var(--font-mono); font-size: var(--fs-lg); font-weight: 600; }
.weak-card span { font-size: var(--fs-xs); color: var(--text-3); }
.wk.danger { color: var(--danger, #e03131); }
.wk.success { color: var(--success, #16a34a); }
.wk.warn { color: var(--warning, #d97706); }

.weak-list { display: flex; flex-direction: column; gap: 8px; }
.weak-item {
  display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: var(--r-md); padding: 10px 16px;
}
.weak-lesson { font-size: var(--fs-sm); font-weight: 600; min-width: 180px; flex: 1; }
.weak-tags { display: flex; gap: 8px; flex-wrap: wrap; }
.tag { font-size: var(--fs-xs); padding: 3px 10px; border-radius: var(--r-pill); }
.tag.danger { background: color-mix(in srgb, var(--danger, #e03131) 10%, transparent); color: var(--danger, #e03131); }
.tag.warn { background: color-mix(in srgb, var(--warning, #d97706) 10%, transparent); color: var(--warning, #d97706); }
.weak-go { font-size: var(--fs-xs); color: var(--primary); text-decoration: none; white-space: nowrap; }
.weak-go:hover { text-decoration: underline; }

/* ============ 已完成课程 ============ */
.done-list { display: flex; flex-direction: column; gap: 14px; }
.done-phase { display: flex; gap: 12px; align-items: flex-start; }
.done-phase-label {
  font-family: var(--font-mono); font-size: var(--fs-xs);
  color: var(--primary); font-weight: 600;
  padding-top: 4px; width: 72px; flex-shrink: 0;
}
.done-chips { display: flex; flex-wrap: wrap; gap: 8px; }
.chip {
  font-size: var(--fs-sm);
  color: var(--text-2);
  background: var(--bg-subtle);
  padding: 5px 12px;
  border-radius: var(--r-pill);
  text-decoration: none;
  transition: background 0.15s, color 0.15s;
}
.chip:hover { background: var(--primary-soft); color: var(--primary); }

/* ============ 空态 ============ */
.empty-hint { font-size: var(--fs-sm); color: var(--text-3); padding: 12px 4px; }

/* ============ 响应式 ============ */
@media (max-width: 820px) {
  .hero-card { flex-direction: column; align-items: stretch; }
  .hero-mini { grid-template-columns: repeat(3, 1fr); }
  .phase-name { width: 100%; }
  .phase-row { flex-wrap: wrap; }
  .phase-pct { display: none; }
}
</style>
