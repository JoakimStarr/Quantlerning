<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, provide, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowUp, ChevronLeft, ChevronRight, RefreshCw, Sparkles } from 'lucide-vue-next'
import { fetchLesson, streamLessonSummary } from '@/api'
import MarkdownRenderer from '@/components/lesson/MarkdownRenderer.vue'
import AiAskPanel from '@/components/lesson/AiAskPanel.vue'
import AppSpinner from '@/components/common/AppSpinner.vue'
import AppError from '@/components/common/AppError.vue'
import { renderAiBubble } from '@/utils/aiBubble'
import { getSelectionMarkdown } from '@/utils/selectionToMarkdown'
import { ASK_AI_KEY } from '@/utils/aiAskKey'
import { recordLessonRead, recordQuizAttempt } from '@/stores/progress'

// 新版课程阅读页：与首页 HomeView2 / 课程页 PhaseView2 设计 token 对齐。
// 脚本逻辑与 LessonView.vue 完全一致，仅视觉层重构（hero 锚点 + 文档卡片 + 阅读进度）。

const route = useRoute()
const router = useRouter()

const lesson = ref<any>(null)
const loading = ref(true)
const error = ref('')

const sections = ref<any[]>([])
const currentSection = ref<{ index: number; title: string }>({ index: 0, title: '' })
const readingProgress = ref(0)

function scrollMainTop() {
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

// ---------- 选中文字 → 问 AI ----------
const askPanelRef = ref<{ ask: (text: string, context?: string) => void } | null>(null)
const articleRef = ref<HTMLElement | null>(null)
const selBox = reactive({ show: false, x: 0, y: 0, text: '' })

function askAi(text: string, context?: string) {
  askPanelRef.value?.ask(text, context)
}
provide(ASK_AI_KEY, askAi)

// ---------- 本节小结（AI 生成，localStorage 缓存）----------
const summary = ref('')
const summaryBusy = ref(false)
const summaryError = ref('')
const summaryCtrl = ref<AbortController | null>(null)
const SUMMARY_KEY = (id: string) => `ql:lessonSummary:${id}`

function resetSummary(id: string) {
  summaryCtrl.value?.abort()
  summaryCtrl.value = null
  summaryBusy.value = false
  summaryError.value = ''
  try {
    summary.value = localStorage.getItem(SUMMARY_KEY(id)) ?? ''
  } catch {
    summary.value = ''
  }
}

async function genSummary() {
  if (summaryBusy.value || !lesson.value) return
  summaryError.value = ''
  summary.value = ''
  summaryBusy.value = true
  const ctrl = new AbortController()
  summaryCtrl.value = ctrl
  try {
    const result = await streamLessonSummary(
      lesson.value.id,
      (d) => { summary.value += d },
      ctrl.signal,
    )
    if (result.error) {
      summaryError.value = result.error
    } else if (summary.value) {
      try {
        localStorage.setItem(SUMMARY_KEY(lesson.value.id), summary.value)
      } catch {
        // 存储不可用：忽略
      }
    }
  } catch {
    // 中止/切课：忽略
  } finally {
    summaryBusy.value = false
    summaryCtrl.value = null
  }
}

function onSelectionChange() {
  const sel = window.getSelection()
  const range = sel && !sel.isCollapsed && sel.rangeCount ? sel.getRangeAt(0) : null
  if (!range) {
    selBox.show = false
    return
  }
  const article = articleRef.value
  const anc = range.commonAncestorContainer
  const target = anc.nodeType === Node.ELEMENT_NODE ? (anc as HTMLElement) : anc.parentElement
  if (!article || !target || !article.contains(target)) {
    selBox.show = false
    return
  }
  const rect = range.getBoundingClientRect()
  if (rect.width < 4 || rect.height < 4) {
    selBox.show = false
    return
  }
  if (!selBox.show) {
    selBox.text = getSelectionMarkdown()
  }
  selBox.show = true
  selBox.x = Math.min(rect.right, window.innerWidth - 12)
  selBox.y = Math.max(10, rect.top - 38)
}

function hideSelBox() {
  selBox.show = false
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') hideSelBox()
  if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
    const t = e.target as HTMLElement
    if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) return
    if (!lesson.value) return
    const target = e.key === 'ArrowLeft' ? lesson.value.prev : lesson.value.next
    if (target) {
      e.preventDefault()
      router.push(`/lesson/${target.id}`)
    }
  }
}

function askSelected() {
  const text = selBox.text || getSelectionMarkdown()
  selBox.show = false
  selBox.text = ''
  window.getSelection()?.removeAllRanges()
  if (!text) return
  askPanelRef.value?.ask(`请解释我选中的这段话，讲清楚每个符号和概念的含义：\n${text}`)
}

async function load(id: string) {
  loading.value = true
  error.value = ''
  loadQuizResults(id)
  resetSummary(id)
  try {
    lesson.value = await fetchLesson(id)
    recordLessonRead(id)
    sections.value = lesson.value.sections?.length
      ? lesson.value.sections.map((s: any, i: number) => ({
          id: `sec-${i}`, title: s.title, body: s.body,
        }))
      : [{ id: 'sec-0', title: '概念讲解', body: lesson.value.content }]
    const sectionId = route.query.section
    if (sectionId) {
      setTimeout(() => {
        document.getElementById(String(sectionId))?.scrollIntoView({ behavior: 'smooth' })
      }, 100)
    }
    await nextTick()
    registerScroll()
  } catch (e: any) {
    error.value = e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

let scrollRaf = 0

function onScroll() {
  if (scrollRaf) return
  scrollRaf = requestAnimationFrame(() => {
    scrollRaf = 0
    const doc = document.documentElement
    const max = doc.scrollHeight - window.innerHeight
    readingProgress.value = max > 0 ? Math.min(1, Math.max(0, window.scrollY / max)) : 0
    let idx = 0
    const top = 80
    for (let i = 0; i < sections.value.length; i++) {
      const el = document.getElementById(sections.value[i].id)
      if (el && el.getBoundingClientRect().top <= top) idx = i
    }
    if (idx !== currentSection.value.index) {
      currentSection.value = { index: idx, title: sections.value[idx]?.title || '' }
    }
  })
}

function registerScroll() {
  currentSection.value = { index: 0, title: sections.value[0]?.title || '' }
  onScroll()
}

function attachScrollListeners() {
  document.addEventListener('scroll', onScroll, true)
}

onMounted(() => {
  load(String(route.params.id))
  attachScrollListeners()
  document.addEventListener('selectionchange', onSelectionChange)
  document.addEventListener('mouseup', onSelectionChange)
  window.addEventListener('scroll', hideSelBox, true)
  window.addEventListener('keydown', onKeydown)
})

onBeforeUnmount(() => {
  document.removeEventListener('scroll', onScroll, true)
  document.removeEventListener('selectionchange', onSelectionChange)
  document.removeEventListener('mouseup', onSelectionChange)
  window.removeEventListener('scroll', hideSelBox, true)
  window.removeEventListener('keydown', onKeydown)
  summaryCtrl.value?.abort()
})

watch(() => route.params.id, (id) => {
  if (typeof id === 'string') load(id)
})

// ---------- 随堂测验结果记录 ----------
const QUIZ_RESULT_KEY = (lessonId: string) => `ql:quizResults:${lessonId}`
const quizResults = ref<Record<string, number>>({})

function loadQuizResults(lessonId: string) {
  try {
    const raw = localStorage.getItem(QUIZ_RESULT_KEY(lessonId))
    const saved = raw ? JSON.parse(raw) : {}
    if (saved && typeof saved === 'object') quizResults.value = saved
  } catch {
    quizResults.value = {}
  }
}
function saveQuizResults() {
  try {
    localStorage.setItem(QUIZ_RESULT_KEY(lesson.value?.id ?? ''), JSON.stringify(quizResults.value))
  } catch {
    // 存储不可用：忽略
  }
}

function onQuizSubmitted(score: number, question: string) {
  if (!lesson.value) return
  quizResults.value[question] = Math.max(quizResults.value[question] ?? 0, score)
  saveQuizResults()
  const passed = Object.values(quizResults.value).filter((s) => s === 100).length
  const total = Object.keys(quizResults.value).length
  recordQuizAttempt(lesson.value.id, passed, total)
}
</script>

<template>
  <!-- 阅读进度条（顶部细条，主色） -->
  <div class="reading-bar" :style="{ width: readingProgress * 100 + '%' }"></div>

  <div v-if="loading" class="status"><AppSpinner text="加载课程…" /></div>
  <div v-else-if="error" class="status"><AppError :message="error" @retry="load(String(route.params.id))" /></div>

  <template v-else-if="lesson">
    <button v-if="readingProgress > 0.04" class="back-top" title="回到顶部" @click="scrollMainTop"><ArrowUp :size="18" /></button>

    <div class="lesson2">
      <!-- HERO：eyebrow + 章标题 + 引言（镜像首页 hero 节奏） -->
      <header class="hero">
        <div class="hero-main">
          <button class="eyebrow" type="button" @click="router.push(`/phase/${lesson.phase}`)" @keydown.enter.prevent>
            {{ lesson.phase_title }} <span class="eyebrow-arrow">→</span>
          </button>
          <h1>{{ lesson.title }}</h1>
          <p class="lead">{{ lesson.summary }}</p>
          <div class="concepts">
            <span v-for="c in lesson.concepts" :key="c" class="chip">{{ c }}</span>
          </div>
        </div>
      </header>

      <!-- 文档卡片：正文流 -->
      <article ref="articleRef" class="book-page">
        <section class="doc-flow">
          <div v-for="(s, i) in sections" :key="s.id" :id="s.id" class="doc-section">
            <h2 v-if="s.title" class="doc-heading">
              <span class="doc-num">{{ String(i + 1).padStart(2, '0') }}</span>
              {{ s.title }}
            </h2>
            <MarkdownRenderer
              v-if="s.body"
              :content="s.body"
              :lesson-id="lesson.id"
              :section-index="i"
              @quiz-submitted="onQuizSubmitted"
            />
          </div>
        </section>

        <!-- 本节小结（AI 生成） -->
        <section class="lesson-summary">
          <button
            v-if="!summary"
            type="button"
            class="btn btn-ghost summary-trigger"
            :disabled="summaryBusy"
            @click="genSummary"
          >
            <Sparkles :size="14" />
            {{ summaryBusy ? '生成中…' : '生成「本节小结」' }}
          </button>
          <div v-if="summary" class="summary-card">
            <div class="summary-head">
              <span class="summary-title"><Sparkles :size="13" /> 本节小结</span>
              <button type="button" class="btn btn-ghost summary-regen" :disabled="summaryBusy" @click="genSummary">
                <RefreshCw :size="12" :class="{ spin: summaryBusy }" />
                {{ summaryBusy ? '生成中…' : '重新生成' }}
              </button>
            </div>
            <div v-if="summaryError" class="summary-error">{{ summaryError }}</div>
            <div v-else class="summary-body" v-html="renderAiBubble(summary)"></div>
          </div>
          <div v-if="summaryError && !summary" class="summary-error">{{ summaryError }}</div>
        </section>

        <!-- 翻页导航 -->
        <nav class="chapter-nav">
          <button class="btn nav-btn" :disabled="!lesson.prev" @click="lesson.prev && router.push(`/lesson/${lesson.prev.id}`)">
            <ChevronLeft :size="16" /> <span><em>上一课</em>{{ lesson.prev?.title || '无上一章' }}</span>
          </button>
          <button class="btn nav-btn next" :disabled="!lesson.next" @click="lesson.next && router.push(`/lesson/${lesson.next.id}`)">
            <span><em>下一课</em>{{ lesson.next?.title || '无下一章' }}</span> <ChevronRight :size="16" />
          </button>
        </nav>
      </article>

      <!-- AI 追问面板 -->
      <AiAskPanel
        ref="askPanelRef"
        :lesson-id="lesson.id"
        :section-index="currentSection.index"
        :section-title="currentSection.title"
      />

      <!-- 选中文字 → 问 AI -->
      <button
        v-if="selBox.show"
        class="ask-selection"
        :style="{ left: selBox.x + 'px', top: selBox.y + 'px' }"
        @mousedown.prevent
        @click="askSelected"
      >
        问 AI
      </button>
    </div>
  </template>
</template>

<style scoped>
/* 全量复用首页 home2 / 课程页设计 token */

.lesson2 { max-width: 900px; margin: 0 auto; }
.status { padding: 40px; text-align: center; }

/* ============ Hero ============ */
.hero { padding: clamp(24px, 4vw, 48px) 0 clamp(16px, 3vw, 28px); }
.eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-family: var(--font-mono);
  font-size: var(--fs-xs);
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--primary);
  background: none;
  border: none;
  padding: 0;
  cursor: pointer;
  font-weight: 600;
  margin-bottom: 16px;
  transition: opacity 0.15s;
}
.eyebrow:hover { opacity: 0.75; }
.eyebrow-arrow { display: inline-flex; transform: translateX(0); transition: transform 0.2s var(--ease-out); }
.eyebrow:hover .eyebrow-arrow { transform: translateX(3px); }
.hero h1 { font-size: var(--fs-2xl); letter-spacing: -0.02em; line-height: 1.15; margin-bottom: 14px; max-width: 22ch; }
.hero .lead { color: var(--text-2); font-size: var(--fs-md); line-height: 1.75; max-width: 60ch; margin-bottom: 20px; }
.concepts { display: flex; flex-wrap: wrap; gap: 8px; }
.chip {
  font-size: var(--fs-xs);
  color: var(--primary);
  background: var(--primary-soft);
  padding: 4px 12px;
  border-radius: var(--r-pill);
  font-weight: 600;
  white-space: nowrap;
}

/* ============ 文档卡片 ============ */
.book-page {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--r-xl);
  padding: clamp(20px, 4vw, 44px);
  box-shadow: var(--shadow-md);
}
.doc-flow { display: flex; flex-direction: column; gap: clamp(24px, 5vw, 40px); }
.doc-section { scroll-margin-top: 24px; }
.doc-heading {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: var(--fs-lg);
  margin: 0 0 16px;
  color: var(--text-1);
  letter-spacing: -0.01em;
}
.doc-num {
  flex: none;
  font-family: var(--font-mono);
  font-size: var(--fs-xs);
  font-weight: 600;
  color: var(--primary);
  background: var(--primary-soft);
  padding: 4px 10px;
  border-radius: var(--r-sm);
  letter-spacing: 0.04em;
}

/* ============ 本节小结 ============ */
.lesson-summary { margin-top: clamp(28px, 5vw, 44px); padding-top: 8px; }
.summary-trigger {
  display: inline-flex; align-items: center; gap: 6px;
  color: var(--primary); border-color: var(--primary);
}
.summary-card {
  border: 1px solid var(--border);
  border-left: 4px solid var(--primary);
  border-radius: var(--r-lg);
  background: var(--bg-card);
  padding: 16px 20px;
}
.summary-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 10px; }
.summary-title { display: inline-flex; align-items: center; gap: 6px; font-size: var(--fs-sm); font-weight: 600; color: var(--primary); }
.summary-regen { display: inline-flex; align-items: center; gap: 5px; }
.summary-body { font-size: var(--fs-sm); line-height: 1.9; color: var(--text-2); }
.summary-body :deep(ul) { margin: 0; padding-left: 1.4em; }
.summary-body :deep(li) { margin-bottom: 4px; }
.summary-body :deep(.katex) { font-size: 1em; }
.summary-error {
  margin-top: 10px;
  font-size: var(--fs-xs);
  color: var(--danger, #dc2626);
  background: color-mix(in srgb, var(--danger, #dc2626) 8%, transparent);
  border-radius: var(--r-sm);
  padding: 8px 12px;
  line-height: 1.6;
}
.spin { animation: spin-rotate 0.8s linear infinite; }
@keyframes spin-rotate { to { transform: rotate(360deg); } }

/* ============ 翻页导航（卡片化） ============ */
.chapter-nav {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  margin-top: clamp(28px, 5vw, 44px);
}
.nav-btn {
  align-items: center;
  padding: 16px 18px;
  border-radius: var(--r-lg);
  background: var(--bg-card);
  border-color: var(--border);
  box-shadow: var(--shadow-xs);
}
.nav-btn:hover { border-color: color-mix(in srgb, var(--primary) 45%, var(--border)); color: var(--primary); transform: translateY(-2px); }
.nav-btn:disabled { opacity: 0.4; pointer-events: none; }
.nav-btn.next { flex-direction: row-reverse; }
.nav-btn span { display: flex; flex-direction: column; gap: 2px; align-items: flex-start; line-height: 1.4; text-align: left; font-weight: 600; font-size: var(--fs-sm); }
.nav-btn.next span { align-items: flex-end; text-align: right; }
.nav-btn em { font-style: normal; font-size: var(--fs-xs); color: var(--text-3); font-weight: 500; }

/* ============ 悬浮控件 ============ */
.ask-selection {
  position: fixed;
  transform: translateX(-100%);
  z-index: 90;
  font-size: var(--fs-xs);
  padding: 5px 14px;
  border: none;
  border-radius: var(--r-pill);
  background: var(--primary);
  color: #fff;
  cursor: pointer;
  box-shadow: 0 6px 18px rgba(47, 106, 232, 0.32);
}
.ask-selection:hover { filter: brightness(1.08); }

.reading-bar {
  position: fixed;
  top: 0; left: 0;
  height: 3px;
  background: var(--primary);
  z-index: 50;
  transition: width 0.1s linear;
}

.back-top {
  position: fixed;
  left: calc(var(--sidebar-w) + 18px);
  bottom: 20px;
  width: 40px; height: 40px;
  border: 1px solid var(--border-strong);
  border-radius: 50%;
  background: var(--bg-card);
  color: var(--text-2);
  font-size: 17px;
  cursor: pointer;
  box-shadow: var(--shadow-md);
  z-index: 40;
  display: flex; align-items: center; justify-content: center;
}
.back-top:hover { color: var(--primary); border-color: var(--primary); }

/* ============ 响应式 ============ */
@media (max-width: 900px) {
  .back-top { left: 18px; }
  .hero h1 { font-size: var(--fs-xl); }
  .chapter-nav { grid-template-columns: 1fr; }
  .ask-selection { font-size: var(--fs-base); padding: 7px 14px; }
}
</style>