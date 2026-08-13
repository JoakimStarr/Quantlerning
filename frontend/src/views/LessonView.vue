<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowUp, ChevronLeft, ChevronRight } from 'lucide-vue-next'
import { fetchLesson } from '@/api'
import MarkdownRenderer from '@/components/lesson/MarkdownRenderer.vue'
import AiAskPanel from '@/components/lesson/AiAskPanel.vue'
import AppSpinner from '@/components/common/AppSpinner.vue'
import AppError from '@/components/common/AppError.vue'
import { getSelectionMarkdown } from '@/utils/selectionToMarkdown'
import { recordLessonRead, recordQuizAttempt } from '@/stores/progress'

const route = useRoute()
const router = useRouter()

const lesson = ref<any>(null)
const loading = ref(true)
const error = ref('')

// 课程内容：sections，每节 body 为 Markdown（可含 :::viz 块，图文交融）
const sections = ref<any[]>([])

// 当前正在阅读的小节（供 AI 追问定位上下文）
const currentSection = ref<{ index: number; title: string }>({ index: 0, title: '' })
// 阅读进度 0~1（body 为滚动容器，浏览器原生恢复滚动位置，这里只算进度条）
const readingProgress = ref(0)

function scrollMainTop() {
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

// ---------- 选中文字 → 问 AI ----------
const askPanelRef = ref<{ ask: (text: string) => void } | null>(null)
const articleRef = ref<HTMLElement | null>(null)
const selBox = reactive({ show: false, x: 0, y: 0, text: '' })

function onSelectionChange() {
  const sel = window.getSelection()
  const range = sel && !sel.isCollapsed && sel.rangeCount ? sel.getRangeAt(0) : null
  if (!range) {
    selBox.show = false
    return
  }
  // 只对课程正文内的选区弹出「问 AI」按钮
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
    // 首次显示时缓存选区 Markdown（含公式源码）；点击时不再依赖实时选区，
    // 避免「点击瞬间选区被浏览器折叠」导致取不到文本的竞态
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
  // ←/→ 上一课/下一课（输入框/文本域内不触发）
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
  // 优先用缓存文本（按钮出现时已抓取），兜底实时读取
  const text = selBox.text || getSelectionMarkdown()
  selBox.show = false
  selBox.text = ''
  window.getSelection()?.removeAllRanges()
  if (!text) return
  // 选中段落（含 LaTeX 公式）作为问题预填，AI 会结合当前小节回答
  askPanelRef.value?.ask(`请解释我选中的这段话，讲清楚每个符号和概念的含义（公式用 LaTeX 保留）：\n${text}`)
}

async function load(id: string) {
  loading.value = true
  error.value = ''
  loadQuizResults(id)
  try {
    lesson.value = await fetchLesson(id)
    recordLessonRead(id) // 阅读行为 → 学习天数/阅读次数
    sections.value = lesson.value.sections?.length
      ? lesson.value.sections.map((s: any, i: number) => ({
          id: `sec-${i}`, title: s.title, body: s.body,
        }))
      : [{ id: 'sec-0', title: '概念讲解', body: lesson.value.content }]
    // 支持从 URL 参数跳转到指定区块（左侧目录点击）
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

// 滚动跟踪当前小节：取视口上方 80px 以下、最后进入视野的小节
let scrollRaf = 0

function onScroll() {
  if (scrollRaf) return
  scrollRaf = requestAnimationFrame(() => {
    scrollRaf = 0
    // 阅读进度：body 为滚动容器（浏览器原生恢复滚动位置，这里只算进度条）
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

// 滚动跟踪：document 捕获阶段监听，body 滚动时触发
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
})

watch(() => route.params.id, (id) => {
  if (typeof id === 'string') load(id)
})

// ---------- 随堂测验结果记录 ----------
// 记录本课每道测验的最佳得分，全部答对后计为「测验通过」
// 持久化到 localStorage（按课程），刷新/重开后恢复，后端不参与
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
  // passed = 答对数（score===100 才算通过），completed 仅全部答对时置位
  const passed = Object.values(quizResults.value).filter((s) => s === 100).length
  const total = Object.keys(quizResults.value).length
  recordQuizAttempt(lesson.value.id, passed, total)
}
</script>

<template>
  <!-- 阅读进度条（顶部细条） -->
  <div class="reading-bar" :style="{ width: readingProgress * 100 + '%' }"></div>

  <div v-if="loading" class="status"><AppSpinner text="加载课程…" /></div>
  <div v-else-if="error" class="status"><AppError :message="error" @retry="load(String(route.params.id))" /></div>

  <template v-else-if="lesson">
    <!-- 回到顶部（放在课程块内，避免 v-if 打断 loading/error/lesson 的 v-else-if 链） -->
    <button v-if="readingProgress > 0.04" class="back-top" title="回到顶部" @click="scrollMainTop"><ArrowUp :size="18" /></button>

    <!-- 面包屑 -->
    <div class="breadcrumb">
      <button class="link-btn" @click="router.push(`/phase/${lesson.phase}`)">{{ lesson.phase_title }}</button>
      <span class="sep">/</span>
      <span>{{ lesson.title }}</span>
    </div>

    <!-- 文档式课程页 -->
    <article ref="articleRef" class="book-page">
      <!-- 章标题 -->
      <header class="chapter-header">
        <h1 class="chapter-title">{{ lesson.title }}</h1>
        <div class="concepts">
          <span v-for="c in lesson.concepts" :key="c" class="badge badge-primary">{{ c }}</span>
        </div>
        <p v-if="lesson.summary" class="chapter-summary">{{ lesson.summary }}</p>
      </header>

      <!-- 正文：Markdown 文档流，可视化嵌入正文（图文交融） -->
      <section class="doc-flow">
        <div v-for="(s, i) in sections" :key="s.id" :id="s.id" class="doc-section">
          <h2 v-if="s.title" class="doc-heading">
            <span class="doc-num">{{ i + 1 }}</span>
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

      <!-- 翻页导航：上一章 / 下一章 -->
      <nav class="chapter-nav">
        <button class="btn nav-btn" :disabled="!lesson.prev" @click="lesson.prev && router.push(`/lesson/${lesson.prev.id}`)">
          <ChevronLeft :size="16" /> {{ lesson.prev?.title || '无上一章' }}
        </button>
        <button class="btn nav-btn next" :disabled="!lesson.next" @click="lesson.next && router.push(`/lesson/${lesson.next.id}`)">
          {{ lesson.next?.title || '无下一章' }} <ChevronRight :size="16" />
        </button>
      </nav>
    </article>

    <!-- AI 追问：围绕当前小节对话 -->
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
  </template>
</template>

<style scoped>
.status { padding: 40px; text-align: center; }

.breadcrumb { display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--text-3); margin-bottom: 16px; }
.link-btn { background: none; border: none; color: var(--primary); cursor: pointer; font-size: 13px; padding: 0; }
.link-btn:hover { text-decoration: underline; }
.sep { color: var(--text-3); }

.book-page {
  max-width: 800px; margin: 0 auto;
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: var(--radius-md); padding: 36px 44px; box-shadow: var(--shadow-sm);
}

.chapter-header { margin-bottom: 32px; }
.chapter-title { font-size: 28px; margin-bottom: 12px; }
.concepts { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 14px; }
.chapter-summary {
  font-size: 15px; color: var(--text-2); line-height: 1.8;
  border-left: 3px solid var(--primary); padding-left: 14px; margin: 0;
}

.doc-section { margin-bottom: 32px; scroll-margin-top: 24px; }
.doc-heading { display: flex; align-items: center; gap: 10px; font-size: 20px; margin: 0 0 14px; padding-bottom: 8px; border-bottom: 1px solid var(--border); }
.doc-num {
  width: 26px; height: 26px; border-radius: 8px; flex-shrink: 0;
  background: var(--primary-soft); color: var(--primary);
  display: flex; align-items: center; justify-content: center; font-size: 13px; font-weight: 600;
}

.chapter-nav { display: flex; justify-content: space-between; gap: 12px; margin-top: 40px; padding-top: 20px; border-top: 1px solid var(--border); }
.nav-btn { flex: 1; justify-content: space-between; }
.nav-btn.next { flex-direction: row-reverse; }

/* 选中文字后的「问 AI」悬浮按钮 */
.ask-selection {
  position: fixed;
  transform: translateX(-100%);
  z-index: 90;
  font-size: 12px;
  padding: 4px 12px;
  border: none;
  border-radius: 999px;
  background: var(--primary);
  color: #fff;
  cursor: pointer;
  box-shadow: 0 4px 14px rgba(37, 99, 235, 0.35);
}
.ask-selection:hover { filter: brightness(1.08); }

/* 阅读进度条（顶部细条） */
.reading-bar {
  position: fixed;
  top: 0; left: 0;
  height: 3px;
  background: var(--primary);
  z-index: 50;
  transition: width 0.1s linear;
}

/* 回到顶部 */
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

/* 移动端适配 */
@media (max-width: 900px) {
  .back-top { left: 18px; }
  .chapter-title { font-size: 23px; }
  .doc-heading { font-size: 18px; }
  .chapter-nav { flex-direction: column; }
  .ask-selection { font-size: 13px; padding: 8px 14px; }
}
</style>
