<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { MessageCircle, RefreshCw } from 'lucide-vue-next'
import { createMarkdown } from '../../utils/markdownIt'
import { unwrapOuterFence } from '../../utils/aiOutput'
import 'katex/dist/katex.min.css'
import { judgeAnswer, streamGenExercise, streamJudgeFollowup } from '@/api'
import type { ChatTurn } from '@/api'
import { recordExercise } from '@/stores/progress'

// 应用题（:::exercise 块）：展示题目 + 用户输入答案 + 调 AI 批改（SSE 流式）
// 题目/提示为 Markdown 文本（支持 LaTeX），AI 批改结果渲染 Markdown/LaTeX
// 答案与批改反馈按「课程+小节+题号」自动保存到 localStorage，刷新/重开后恢复

export interface ExerciseQuestion {
  title: string
  hint?: string
}

const props = defineProps<{
  exercise: ExerciseQuestion
  lessonId: string
  sectionIndex: number
  exerciseIndex?: number
}>()

const md = createMarkdown()

const render = (text: string) => md.render(text)

// AI 输出的公式分隔符统一归一化（与 AiAskPanel 一致）；先剥掉外层代码围栏，
// 否则模型把整段 Markdown 包在 ```…``` 里时会整块显示为代码框、语法原样可见
function renderBubble(content: string): string {
  const normalized = unwrapOuterFence(content)
    .replace(/\$\$([\s\S]+?)\$\$/g, (_, m: string) => `$${m.trim()}$`)
    .replace(/\\\[([\s\S]+?)\\\]/g, (_, m: string) => `$${m.trim()}$`)
    .replace(/\\\(([\s\S]+?)\\\)/g, (_, m: string) => `$${m.trim()}$`)
  return md.render(normalized)
}

const answer = ref('')
const judging = ref(false)
const error = ref('')
const feedback = ref('')
const resultOpen = ref(true)
const abortCtrl = ref<AbortController | null>(null)

const maxLen = 4000

// 草稿持久化：按「课程+小节+题号」存答案与反馈，重开/刷新自动恢复
const STORAGE_KEY = `ql:exercise:${props.lessonId ?? ''}:${props.sectionIndex ?? 0}:${props.exerciseIndex ?? 0}`

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return
    const state = JSON.parse(raw)
    if (state && typeof state.answer === 'string') answer.value = state.answer
    if (state && typeof state.feedback === 'string') feedback.value = state.feedback
  } catch {
    // 存储不可用或数据损坏：忽略
  }
}
function saveState() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ answer: answer.value, feedback: feedback.value }))
  } catch {
    // 存储不可用：忽略
  }
}
// 输入与批改反馈变化即自动保存（轻量写入，无需防抖）
watch([answer, feedback], saveState)

loadState()

async function judge() {
  if (judging.value) return
  if (!answer.value.trim()) {
    error.value = '请先写下你的答案，再请 AI 批改。'
    return
  }
  error.value = ''
  feedback.value = ''
  resultOpen.value = true
  judging.value = true
  const ctrl = new AbortController()
  abortCtrl.value = ctrl
  try {
    const result = await judgeAnswer(
      {
        lesson_id: props.lessonId,
        section_index: props.sectionIndex,
        question: props.exercise.title,
        answer: answer.value.slice(0, maxLen),
      },
      (delta) => {
        feedback.value += delta
      },
      ctrl.signal,
    )
    if (result.error) error.value = result.error
    else recordExercise(props.lessonId) // 成功批改记一次练习提交
  } catch {
    // 用户中止（retry/离开）等：不记提交
  } finally {
    judging.value = false
    abortCtrl.value = null
  }
}

function retry() {
  abortCtrl.value?.abort()
  abortCtrl.value = null
  judging.value = false
  error.value = ''
  feedback.value = ''
}

// ---------- 批改后追问（会话内，不持久化）----------
const fuOpen = ref(false)
const fuText = ref('')
const fuBusy = ref(false)
const fuThread = ref<ChatTurn[]>([])
const fuError = ref('')

async function askFollowup() {
  const text = fuText.value.trim()
  if (!text || fuBusy.value) return
  fuThread.value.push({ role: 'user', content: text })
  fuThread.value.push({ role: 'assistant', content: '' })
  fuText.value = ''
  fuError.value = ''
  fuBusy.value = true
  const last = fuThread.value[fuThread.value.length - 1]
  try {
    const result = await streamJudgeFollowup(
      {
        lesson_id: props.lessonId,
        section_index: props.sectionIndex,
        question: props.exercise.title,
        answer: answer.value.slice(0, maxLen),
        feedback: feedback.value,
        messages: fuThread.value.slice(0, -2), // 历史（不含刚追加的 user 与空 assistant）
      },
      (delta) => {
        last.content += delta
      },
    )
    if (result.error) {
      fuError.value = result.error
      fuThread.value.pop() // 移除空 assistant 气泡
    }
  } catch {
    fuThread.value.pop()
  } finally {
    fuBusy.value = false
  }
}

// ---------- 生成变式练习题 ----------
const variant = ref('')
const generating = ref(false)
const variantError = ref('')

async function genVariant() {
  if (generating.value) return
  variant.value = ''
  variantError.value = ''
  generating.value = true
  try {
    const result = await streamGenExercise(
      {
        lesson_id: props.lessonId,
        section_index: props.sectionIndex,
        question: props.exercise.title,
        answer: answer.value.slice(0, maxLen),
        feedback: feedback.value,
      },
      (delta) => {
        variant.value += delta
      },
    )
    if (result.error) variantError.value = result.error
  } catch {
    // 中止等：忽略
  } finally {
    generating.value = false
  }
}

// 题目与参考答案以「---」分隔
const variantParts = computed(() => {
  const m = variant.value.match(/\n---\s*\n/)
  if (!m || m.index === undefined) return { q: variant.value, a: '' }
  return { q: variant.value.slice(0, m.index), a: variant.value.slice(m.index + m[0].length) }
})
</script>

<template>
  <div class="exercise-card">
    <div class="exercise-head">
      <span class="exercise-badge">应用题</span>
      <span class="exercise-tip">写清过程，提交后由 AI 批改</span>
    </div>

    <div class="exercise-question" v-html="render(exercise.title)"></div>

    <div v-if="exercise.hint" class="exercise-hint">
      <span class="hint-label">提示：</span>
      <span v-html="render(exercise.hint)"></span>
    </div>

    <textarea
      v-model="answer"
      class="answer-box"
      rows="4"
      :placeholder="'在下方输入你的解答…（支持 LaTeX 公式，如 $\\int_a^b f(x)\\,dx$）'"
      :disabled="judging"
    ></textarea>

    <div class="exercise-actions">
      <button
        v-if="!feedback && !judging"
        class="btn btn-primary"
        :disabled="!answer.trim()"
        @click="judge"
      >
        请 AI 批改
      </button>
      <template v-else>
        <button class="btn btn-ghost" :disabled="judging" @click="retry">重新批改</button>
      </template>
    </div>

    <div v-if="judging" class="judge-status">AI 正在批改…<span class="typing">▍</span></div>
    <div v-if="error" class="judge-error">{{ error }}</div>

    <div v-if="feedback" class="judge-result">
      <div class="judge-result-head">
        <span class="judge-result-label">AI 批改结果</span>
        <button class="collapse-toggle" @click="resultOpen = !resultOpen">
          {{ resultOpen ? '收起' : '展开' }}
        </button>
      </div>
      <div v-show="resultOpen" class="judge-result-body" v-html="renderBubble(feedback)"></div>
    </div>

    <div v-if="feedback" class="exercise-ai-tools">
      <button class="btn btn-ghost" :disabled="fuBusy" @click="fuOpen = !fuOpen">
        {{ fuOpen ? '收起追问' : '对批改有疑问？' }}<MessageCircle v-if="!fuOpen" :size="14" />
      </button>
      <button class="btn btn-ghost" :disabled="generating" @click="genVariant">
        {{ generating ? '生成中…' : '生成同类练习题' }}<RefreshCw v-if="!generating" :size="14" />
      </button>
    </div>

    <!-- 批改后追问 -->
    <div v-if="fuOpen" class="fu-panel">
      <div v-if="fuThread.length" class="fu-list">
        <div v-for="(t, i) in fuThread" :key="i" class="fu-item" :class="t.role">
          <div class="fu-role">{{ t.role === 'user' ? '我' : 'AI' }}</div>
          <div v-if="t.role === 'user'" class="fu-bubble user">{{ t.content }}</div>
          <div v-else class="fu-bubble" v-html="renderBubble(t.content)"></div>
        </div>
      </div>
      <div v-if="fuError" class="judge-error">{{ fuError }}</div>
      <div class="fu-input">
        <input
          v-model="fuText"
          :disabled="fuBusy"
          placeholder="针对批改结果提问，如：为什么这里要取对数？"
          @keydown.enter="askFollowup"
        />
        <button class="btn btn-primary" :disabled="fuBusy || !fuText.trim()" @click="askFollowup">
          追问
        </button>
      </div>
    </div>

    <!-- 变式练习 -->
    <div v-if="variant || variantError" class="variant-panel">
      <div class="variant-head">变式练习</div>
      <div v-if="variantError" class="judge-error">{{ variantError }}</div>
      <template v-if="variant">
        <div class="variant-question" v-html="renderBubble(variantParts.q)"></div>
        <details v-if="variantParts.a" class="variant-answer">
          <summary>参考答案</summary>
          <div v-html="renderBubble(variantParts.a)"></div>
        </details>
      </template>
    </div>
  </div>
</template>

<style scoped>
.exercise-card {
  margin: 20px 0 8px;
  padding: 16px 18px;
  border: 1px solid var(--border);
  border-left: 4px solid var(--violet, #7c3aed);
  border-radius: var(--radius-md);
  background: var(--bg-card);
}

.exercise-head { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
.exercise-badge {
  font-size: 12px; font-weight: 600; color: #fff;
  background: var(--violet, #7c3aed); padding: 2px 10px; border-radius: 999px;
}
.exercise-tip { font-size: 12px; color: var(--text-3); }

.exercise-question { font-weight: 600; font-size: 15px; line-height: 1.7; margin-bottom: 10px; }
.exercise-question :deep(.katex) { font-size: 1em; }

.exercise-hint {
  font-size: 13px; line-height: 1.7; color: var(--text-2);
  background: var(--bg-hover); border-radius: var(--radius-sm);
  padding: 8px 12px; margin-bottom: 12px;
}
.exercise-hint .hint-label { font-weight: 600; color: var(--violet, #7c3aed); }
.exercise-hint :deep(.katex) { font-size: 1em; }

.answer-box {
  width: 100%;
  resize: vertical;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-card);
  color: var(--text-1);
  padding: 10px 12px;
  font-size: 14px;
  line-height: 1.7;
  font-family: inherit;
  box-sizing: border-box;
}
.answer-box:focus { outline: none; border-color: var(--violet, #7c3aed); }
.answer-box:disabled { opacity: 0.6; }

.exercise-actions { margin-top: 10px; display: flex; align-items: center; gap: 12px; }

.btn { font-size: 13px; padding: 6px 16px; border-radius: var(--radius-sm); cursor: pointer; border: none; }
.btn-primary { background: var(--violet, #7c3aed); color: #fff; }
.btn-primary:disabled { opacity: .5; cursor: not-allowed; }
.btn-ghost { background: none; border: 1px solid var(--border); color: var(--text-2); }

.judge-status { margin-top: 12px; font-size: 13px; color: var(--text-3); }
.judge-error {
  margin-top: 12px; font-size: 13px; color: var(--danger, #dc2626);
  background: color-mix(in srgb, var(--danger, #dc2626) 8%, transparent);
  border-radius: var(--radius-sm); padding: 8px 12px; line-height: 1.6;
}
.judge-result {
  margin-top: 14px;
  border-radius: var(--radius-sm);
  background: var(--bg-hover);
  overflow: hidden;
}
.judge-result-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 14px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-2);
  border-bottom: 1px solid var(--border);
  cursor: pointer;
  user-select: none;
}
.judge-result-head:hover { background: var(--bg-active); }
.judge-result-label { color: var(--violet, #7c3aed); }
.collapse-toggle {
  background: none;
  border: none;
  color: var(--text-3);
  font-size: 12px;
  cursor: pointer;
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
}
.collapse-toggle:hover { color: var(--violet, #7c3aed); border-color: var(--violet, #7c3aed); }
.judge-result-body {
  padding: 14px;
  font-size: 14px;
  line-height: 1.75;
  color: var(--text-1);
}
.judge-result-body :deep(p) { margin: 0 0 8px; }
.judge-result-body :deep(p:last-child) { margin-bottom: 0; }
.judge-result-body :deep(strong) { font-weight: 600; }
.judge-result-body :deep(em) { font-style: italic; }
.judge-result-body :deep(ul),
.judge-result-body :deep(ol) { margin: 0 0 8px; padding-left: 1.4em; }
.judge-result-body :deep(li) { margin-bottom: 2px; }
.judge-result-body :deep(h1),
.judge-result-body :deep(h2),
.judge-result-body :deep(h3),
.judge-result-body :deep(h4) { margin: 12px 0 6px; font-weight: 600; line-height: 1.4; }
.judge-result-body :deep(h1) { font-size: 1.25em; }
.judge-result-body :deep(h2) { font-size: 1.15em; }
.judge-result-body :deep(h3) { font-size: 1.05em; }
.judge-result-body :deep(h4) { font-size: 1em; }
.judge-result-body :deep(a) { color: var(--primary); }
.judge-result-body :deep(table) {
  border-collapse: collapse; margin: 0 0 8px; font-size: 13px;
}
.judge-result-body :deep(th),
.judge-result-body :deep(td) {
  border: 1px solid var(--border); padding: 5px 9px; text-align: left;
}
.judge-result-body :deep(th) { background: var(--bg-active); font-weight: 600; }
.judge-result-body :deep(code) {
  font-family: var(--font-mono);
  font-size: 0.88em;
  background: color-mix(in srgb, currentColor 12%, transparent);
  padding: 1px 5px;
  border-radius: 4px;
}
.judge-result-body :deep(pre) {
  background: #0f1420;
  color: #e6e9ef;
  border-radius: var(--radius-sm);
  padding: 10px 12px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  word-break: break-word;
  margin: 0 0 8px;
}
.judge-result-body :deep(pre code) {
  background: none;
  padding: 0;
  font-size: 12.5px;
  line-height: 1.5;
}
.judge-result-body :deep(blockquote) {
  margin: 0 0 8px;
  padding: 6px 10px;
  border-left: 3px solid var(--violet, #7c3aed);
  background: color-mix(in srgb, var(--violet, #7c3aed) 8%, transparent);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
}
.judge-result-body :deep(.katex) { font-size: 1em; }
.typing { display: inline-block; animation: blink 1s steps(2) infinite; }
@keyframes blink { 50% { opacity: 0; } }

.exercise-ai-tools { margin-top: 12px; display: flex; gap: 10px; flex-wrap: wrap; }

/* 批改后追问 */
.fu-panel {
  margin-top: 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 12px;
  background: var(--bg-card);
}
.fu-list { display: flex; flex-direction: column; gap: 10px; margin-bottom: 10px; max-height: 320px; overflow-y: auto; }
.fu-item { display: flex; flex-direction: column; gap: 3px; }
.fu-role { font-size: 11px; color: var(--text-3); font-weight: 600; }
.fu-item.user .fu-role { color: var(--violet, #7c3aed); }
.fu-bubble {
  font-size: 13.5px; line-height: 1.7; color: var(--text-1);
  background: var(--bg-hover); border-radius: var(--radius-sm);
  padding: 8px 12px;
}
.fu-bubble.user { background: color-mix(in srgb, var(--violet, #7c3aed) 10%, transparent); white-space: pre-wrap; }
.fu-bubble :deep(p) { margin: 0 0 8px; }
.fu-bubble :deep(p:last-child) { margin-bottom: 0; }
.fu-bubble :deep(strong) { font-weight: 600; }
.fu-bubble :deep(em) { font-style: italic; }
.fu-bubble :deep(ul),
.fu-bubble :deep(ol) { margin: 0 0 8px; padding-left: 1.4em; }
.fu-bubble :deep(li) { margin-bottom: 2px; }
.fu-bubble :deep(code) {
  font-family: var(--font-mono);
  font-size: 0.88em;
  background: color-mix(in srgb, currentColor 12%, transparent);
  padding: 1px 5px;
  border-radius: 4px;
}
.fu-bubble :deep(pre) {
  background: #0f1420;
  color: #e6e9ef;
  border-radius: var(--radius-sm);
  padding: 10px 12px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  word-break: break-word;
  margin: 0 0 8px;
}
.fu-bubble :deep(pre code) {
  background: none;
  padding: 0;
  font-size: 12.5px;
  line-height: 1.5;
}
.fu-bubble :deep(blockquote) {
  margin: 0 0 8px;
  padding: 6px 10px;
  border-left: 3px solid var(--violet, #7c3aed);
  background: color-mix(in srgb, var(--violet, #7c3aed) 8%, transparent);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
}
.fu-bubble :deep(.katex) { font-size: 1em; }
.fu-input { display: flex; gap: 8px; }
.fu-input input {
  flex: 1;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-card);
  color: var(--text-1);
  padding: 8px 12px;
  font-size: 13px;
  font-family: inherit;
}
.fu-input input:focus { outline: none; border-color: var(--violet, #7c3aed); }
.fu-input input:disabled { opacity: 0.6; }

/* 变式练习 */
.variant-panel {
  margin-top: 12px;
  border: 1px dashed var(--border-strong, var(--border));
  border-radius: var(--radius-sm);
  padding: 14px;
  background: var(--bg-card);
}
.variant-head { font-size: 13px; font-weight: 600; color: var(--violet, #7c3aed); margin-bottom: 10px; }
.variant-question { font-size: 14px; line-height: 1.75; color: var(--text-1); }
.variant-question :deep(.katex) { font-size: 1em; }
.variant-question :deep(p) { margin: 0 0 8px; }
.variant-question :deep(p:last-child) { margin-bottom: 0; }
.variant-question :deep(strong) { font-weight: 600; }
.variant-question :deep(em) { font-style: italic; }
.variant-question :deep(ul),
.variant-question :deep(ol) { margin: 0 0 8px; padding-left: 1.4em; }
.variant-question :deep(li) { margin-bottom: 2px; }
.variant-question :deep(code) {
  font-family: var(--font-mono);
  font-size: 0.88em;
  background: color-mix(in srgb, currentColor 12%, transparent);
  padding: 1px 5px;
  border-radius: 4px;
}
.variant-question :deep(pre) {
  background: #0f1420;
  color: #e6e9ef;
  border-radius: var(--radius-sm);
  padding: 10px 12px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  word-break: break-word;
  margin: 0 0 8px;
}
.variant-question :deep(pre code) {
  background: none;
  padding: 0;
  font-size: 12.5px;
  line-height: 1.5;
}
.variant-question :deep(blockquote) {
  margin: 0 0 8px;
  padding: 6px 10px;
  border-left: 3px solid var(--violet, #7c3aed);
  background: color-mix(in srgb, var(--violet, #7c3aed) 8%, transparent);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
}
.variant-answer { margin-top: 12px; font-size: 13.5px; }
.variant-answer summary { cursor: pointer; color: var(--violet, #7c3aed); font-weight: 600; margin-bottom: 6px; }
.variant-answer :deep(p) { margin: 0 0 8px; line-height: 1.7; }
.variant-answer :deep(p:last-child) { margin-bottom: 0; }
.variant-answer :deep(strong) { font-weight: 600; }
.variant-answer :deep(em) { font-style: italic; }
.variant-answer :deep(ul),
.variant-answer :deep(ol) { margin: 0 0 8px; padding-left: 1.4em; }
.variant-answer :deep(li) { margin-bottom: 2px; }
.variant-answer :deep(code) {
  font-family: var(--font-mono);
  font-size: 0.88em;
  background: color-mix(in srgb, currentColor 12%, transparent);
  padding: 1px 5px;
  border-radius: 4px;
}
.variant-answer :deep(pre) {
  background: #0f1420;
  color: #e6e9ef;
  border-radius: var(--radius-sm);
  padding: 10px 12px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  word-break: break-word;
  margin: 0 0 8px;
}
.variant-answer :deep(pre code) {
  background: none;
  padding: 0;
  font-size: 12.5px;
  line-height: 1.5;
}
.variant-answer :deep(blockquote) {
  margin: 0 0 8px;
  padding: 6px 10px;
  border-left: 3px solid var(--violet, #7c3aed);
  background: color-mix(in srgb, var(--violet, #7c3aed) 8%, transparent);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
}
.variant-answer :deep(.katex) { font-size: 1em; }
</style>
