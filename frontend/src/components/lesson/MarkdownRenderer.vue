<script setup lang="ts">
import { computed } from 'vue'
import MarkdownIt from 'markdown-it'
import mathPlugin from '../../utils/markdownMath'
import 'katex/dist/katex.min.css'
import VizBlock from './VizBlock.vue'
import QuizBlock from './QuizBlock.vue'
import ExerciseBlock from './ExerciseBlock.vue'
import type { VizKey } from './vizRegistry'

// Markdown 渲染器，支持：
// - 标准 Markdown（标题/列表/代码/表格）
// - LaTeX 公式：$...$ 行内，$$...$$ 块级
// - :::viz 组件名 参数 自定义块（嵌入可视化）
// - :::quiz 自定义块（知识点测验）
// - :::exercise 自定义块（应用题，调 AI 批改）

interface VizNode {
  component: VizKey
  params: Record<string, unknown>
  caption?: string
}

export interface QuizQuestion {
  q: string
  options: string[]
  answer: number[]   // 正确选项下标（0-based）
  explain?: string
}

export interface ExerciseQuestion {
  title: string
  hint?: string
}

interface Part {
  kind: 'md' | 'viz' | 'quiz' | 'exercise'
  html?: string
  viz?: VizNode
  quiz?: QuizQuestion
  quizIndex?: number
  exercise?: ExerciseQuestion
}

const props = defineProps<{
  content: string
  lessonId?: string
  sectionIndex?: number
}>()

const emit = defineEmits<{
  (e: 'quiz-submitted', score: number, question: string): void
}>()

const md = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: false,
}).use(mathPlugin, {
  throwOnError: false,
  errorColor: '#dc2626',
})

// 渲染 Markdown；把表格包进横向滚动容器（移动端宽表可滑动，不撑破页面）
function renderMd(text: string): string {
  return md
    .render(text)
    .replace(/<table>/g, '<div class="md-table-wrap"><table>')
    .replace(/<\/table>/g, '</table></div>')
}

// 将内容切分为「Markdown 片段」「viz 块」与「quiz 块」
// 语法：
//   :::viz 组件名 caption=图注内容 参数=值
//   :::quiz
//     Q: 题目
//     - 选项一
//     - 选项二
//     - 选项三
//     A: 2          （正确选项编号，1 起；可逗号分隔支持多选）
//     E: 解析
//   :::
const parts = computed<Part[]>(() => {
  const out: Part[] = []
  // 块分割：:::tag [参数] \n 正文 \n:::
  // 注意不能写成 [^\n]*\n?，否则 \n? 会吃掉正文前/后的换行，导致正文与闭合线粘连、
  // 懒匹配跳过紧跟的 ::: 吞掉后续整节内容。参数与正文之间靠 [^\n]* 自身不跨行保证。
  const re = /:::([\w-]+)([^\n]*)([\s\S]*?)\n:::/g
  let last = 0
  let m: RegExpExecArray | null
  while ((m = re.exec(props.content)) !== null) {
    if (m.index > last) {
      out.push({ kind: 'md', html: renderMd(props.content.slice(last, m.index)) })
    }
    const tag = m[1]
    const argStr = m[2].trim()
    if (tag === 'viz') {
      // 组件名来自 Markdown 文本，需收窄为注册表键（未注册名由 vizRegistry 兜底为占位图）
      const viz: VizNode = { component: argStr.split(/\s/)[0] as VizKey, params: {} }
      const rest = argStr.slice(argStr.indexOf(' ')) || ''
      // 提取 caption=xxx（允许空格）
      const capMatch = rest.match(/caption=(.+)/)
      if (capMatch) {
        viz.caption = capMatch[1].trim()
      }
      // 提取参数（排除 caption=）
      viz.params = parseParams(rest.replace(/caption=.+$/, ''))
      out.push({ kind: 'viz', viz })
    } else if (tag === 'quiz') {
      const quiz = parseQuiz(m[3])
      if (quiz) out.push({ kind: 'quiz', quiz, quizIndex: out.filter((p) => p.kind === 'quiz').length })
    } else if (tag === 'exercise') {
      const exercise = parseExercise(m[3])
      if (exercise) out.push({ kind: 'exercise', exercise })
    }
    last = m.index + m[0].length
  }
  if (last < props.content.length) {
    out.push({ kind: 'md', html: renderMd(props.content.slice(last)) })
  }
  if (out.length === 0) {
    out.push({ kind: 'md', html: renderMd(props.content) })
  }
  return out
})

// 解析 :::quiz 块正文 → QuizQuestion；格式不合法时返回 null（渲染方静默跳过）
function parseQuiz(raw: string): QuizQuestion | null {
  const lines = raw
    .split('\n')
    .map((l) => l.trim())
    .filter((l) => l.length > 0)
  let q = ''
  const options: string[] = []
  let answer: number[] = []
  let explain = ''
  for (const line of lines) {
    if (line.startsWith('Q:')) {
      q = line.slice(2).trim()
    } else if (line.startsWith('A:')) {
      answer = line
        .slice(2)
        .split(/[,，、\s]+/)
        .map((s) => parseInt(s, 10) - 1)
        .filter((n) => !Number.isNaN(n))
    } else if (line.startsWith('E:')) {
      explain = line.slice(2).trim()
    } else if (line.startsWith('- ')) {
      options.push(line.slice(2).trim())
    }
  }
  if (!q || options.length < 2) return null
  const ok = answer.every((a) => a >= 0 && a < options.length)
  if (!ok || answer.length === 0) return null
  return { q, options, answer, explain: explain || undefined }
}

// 解析 :::exercise 块正文 → ExerciseQuestion；缺标题时返回 null
// 语法：
//   :::exercise
//   T: 题目（应用题）
//   H: 提示（可选）
//   :::
function parseExercise(raw: string): ExerciseQuestion | null {
  const lines = raw
    .split('\n')
    .map((l) => l.trim())
    .filter((l) => l.length > 0)
  let title = ''
  const hints: string[] = []
  for (const line of lines) {
    if (line.startsWith('T:')) title = line.slice(2).trim()
    else if (line.startsWith('H:')) hints.push(line.slice(2).trim())
  }
  if (!title) return null
  return { title, hint: hints.length ? hints.join('\n\n') : undefined }
}

function parseParams(raw: string): Record<string, unknown> {
  const params: Record<string, unknown> = {}
  const re = /(\w+)=([^\s]+)/g
  let m: RegExpExecArray | null
  while ((m = re.exec(raw)) !== null) {
    const v = m[2]
    params[m[1]] = Number.isNaN(Number(v)) ? v : Number(v)
  }
  return params
}
</script>

<template>
  <div class="markdown-body">
    <template v-for="(part, i) in parts" :key="i">
      <VizBlock
        v-if="part.kind === 'viz' && part.viz"
        :component="part.viz.component"
        :params="part.viz.params"
        :caption="part.viz.caption"
      />
      <QuizBlock
        v-else-if="part.kind === 'quiz' && part.quiz"
        :quiz="part.quiz"
        :lesson-id="lessonId ?? ''"
        :section-index="sectionIndex ?? 0"
        :quiz-index="part.quizIndex ?? 0"
        @submitted="(s, q) => emit('quiz-submitted', s, q)"
      />
      <ExerciseBlock
        v-else-if="part.kind === 'exercise' && part.exercise"
        :exercise="part.exercise"
        :lesson-id="lessonId ?? ''"
        :section-index="sectionIndex ?? 0"
      />
      <div v-else-if="part.html" v-html="part.html" class="md-fragment"></div>
    </template>
  </div>
</template>

<style scoped>
.markdown-body { line-height: 1.8; font-size: 15px; }

/* Markdown 内容样式（作用于 v-html 注入的 HTML） */
.md-fragment :deep(h1),
.md-fragment :deep(h2),
.md-fragment :deep(h3),
.md-fragment :deep(h4) {
  margin: 1.6em 0 0.6em;
  line-height: 1.4;
}
.md-fragment :deep(h1) { font-size: 1.7em; }
.md-fragment :deep(h2) { font-size: 1.45em; }
.md-fragment :deep(h3) { font-size: 1.25em; }
.md-fragment :deep(h4) { font-size: 1.1em; }

.md-fragment :deep(p) { margin: 0 0 12px; }
.md-fragment :deep(p:last-child) { margin-bottom: 0; }

.md-fragment :deep(strong) { font-weight: 600; }

.md-fragment :deep(ul),
.md-fragment :deep(ol) { padding-left: 1.6em; margin: 0 0 12px; }
.md-fragment :deep(li) { margin-bottom: 4px; }

.md-fragment :deep(code) {
  font-family: var(--font-mono);
  font-size: 0.88em;
  background: var(--bg-hover);
  padding: 2px 6px;
  border-radius: 4px;
}

.md-fragment :deep(pre) {
  background: #0f1420;
  color: #e6e9ef;
  border-radius: var(--radius-md);
  padding: 14px 16px;
  overflow-x: auto;
  margin: 0 0 16px;
}
.md-fragment :deep(pre code) {
  background: none;
  color: inherit;
  padding: 0;
  font-size: 13px;
  line-height: 1.6;
}

.md-fragment :deep(table) {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
  margin: 0 0 16px;
}
/* 表格横向滚动容器（renderMd 注入，移动端宽表可滑动） */
.md-fragment :deep(.md-table-wrap) {
  overflow-x: auto;
  margin: 0 0 16px;
}
.md-fragment :deep(.md-table-wrap table) {
  width: max-content;
  min-width: 100%;
  margin: 0;
}
.md-fragment :deep(th),
.md-fragment :deep(td) {
  padding: 8px 12px;
  border: 1px solid var(--border);
  text-align: left;
}
.md-fragment :deep(th) { background: var(--bg-hover); font-weight: 600; }

.md-fragment :deep(blockquote) {
  margin: 0 0 12px;
  padding: 10px 16px;
  border-left: 3px solid var(--primary);
  background: var(--bg-hover);
  color: var(--text-2);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
}

.md-fragment :deep(hr) {
  border: none;
  border-top: 1px solid var(--border);
  margin: 20px 0;
}

/* 代码块滚动条 */
.md-fragment :deep(pre::-webkit-scrollbar) { height: 6px; }
.md-fragment :deep(pre::-webkit-scrollbar-thumb) { background: #3a4a6b; border-radius: 3px; }
</style>
