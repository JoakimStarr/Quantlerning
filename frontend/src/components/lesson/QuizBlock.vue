<script setup lang="ts">
import { ref, computed, onBeforeUnmount } from 'vue'
import { Check, Sparkles, X } from 'lucide-vue-next'
import { createMarkdown } from '../../utils/markdownIt'
import { renderAiBubble } from '../../utils/aiBubble'
import { streamQuizExplain } from '@/api'
import type { QuizQuestion } from './MarkdownRenderer.vue'

const props = defineProps<{
  quiz: QuizQuestion
  lessonId?: string
  sectionIndex?: number
  quizIndex?: number
}>()

const emit = defineEmits<{
  (e: 'submitted', score: number, question: string): void
}>()

const md = createMarkdown()

const selected = ref<number[]>([])
const submitted = ref(false)

// AI 展开解析：流式输出正确项/错误项讲解
const explaining = ref(false)
const explainText = ref('')
const explainError = ref('')
const abortCtrl = ref<AbortController | null>(null)

async function explainWithAi() {
  if (explaining.value || !props.lessonId) return
  explainError.value = ''
  explainText.value = ''
  explaining.value = true
  const ctrl = new AbortController()
  abortCtrl.value = ctrl
  try {
    const result = await streamQuizExplain(
      {
        lesson_id: props.lessonId,
        section_index: props.sectionIndex ?? 0,
        question: props.quiz.q,
        options: props.quiz.options,
        correct_indexes: props.quiz.answer,
        user_indexes: selected.value,
      },
      (d) => {
        explainText.value += d
      },
      ctrl.signal,
    )
    if (result.error) explainError.value = result.error
  } catch {
    // 用户中止/切课：忽略
  } finally {
    explaining.value = false
    abortCtrl.value = null
  }
}

onBeforeUnmount(() => {
  abortCtrl.value?.abort()
})

// 每道测验的作答状态按「课程+小节+题号」存入 localStorage，刷新/重开后仍保留
const STORAGE_KEY = `ql:quiz:${props.lessonId ?? ''}:${props.sectionIndex ?? 0}:${props.quizIndex ?? 0}`

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return
    const state = JSON.parse(raw)
    if (state && typeof state.submitted === 'boolean') {
      submitted.value = state.submitted
      if (Array.isArray(state.selected)) selected.value = state.selected
    }
  } catch {
    // 存储不可用或数据损坏：忽略
  }
}
function saveState() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ submitted: submitted.value, selected: selected.value }))
  } catch {
    // 存储不可用：忽略
  }
}

loadState()

const multi = computed(() => props.quiz.answer.length > 1)

const render = (text: string) => md.render(text)

function toggle(i: number) {
  if (submitted.value) return
  if (multi.value) {
    const idx = selected.value.indexOf(i)
    if (idx >= 0) selected.value.splice(idx, 1)
    else selected.value.push(i)
  } else {
    selected.value = [i]
  }
}

const score = computed(() => {
  const correct = props.quiz.answer
  if (!multi.value) return selected.value.length === 1 && correct.includes(selected.value[0]) ? 100 : 0
  const okAll = correct.every((a) => selected.value.includes(a))
  const noExtra = selected.value.every((s) => correct.includes(s))
  return okAll && noExtra ? 100 : 0
})

function submit() {
  if (submitted.value || selected.value.length === 0) return
  submitted.value = true
  saveState()
  emit('submitted', score.value, props.quiz.q)
}

function reset() {
  submitted.value = false
  selected.value = []
  saveState()
}

function stateClass(i: number): string {
  if (!submitted.value) return selected.value.includes(i) ? 'opt selected' : 'opt'
  if (props.quiz.answer.includes(i)) return 'opt correct'
  if (selected.value.includes(i)) return 'opt wrong'
  return 'opt'
}
</script>

<template>
  <div class="quiz-card">
    <div class="quiz-head">
      <span class="quiz-badge">随堂测验</span>
      <span class="quiz-tip">{{ multi ? '多选题' : '单选题' }}</span>
    </div>

    <div class="quiz-question" v-html="render(quiz.q)"></div>

    <div class="quiz-options">
      <button
        v-for="(opt, i) in quiz.options"
        :key="i"
        type="button"
        class="quiz-opt"
        :class="stateClass(i)"
        @click="toggle(i)"
      >
        <span class="opt-idx">{{ String.fromCharCode(65 + i) }}</span>
        <span class="opt-text" v-html="render(opt)"></span>
        <span class="opt-mark">
          <Check v-if="stateClass(i).includes('correct')" :size="13" />
          <X v-else-if="stateClass(i).includes('wrong')" :size="13" />
        </span>
      </button>
    </div>

    <div class="quiz-actions">
      <button v-if="!submitted" type="button" class="btn btn-primary" :disabled="selected.length === 0" @click="submit">
        提交答案
      </button>
      <template v-else>
        <span class="quiz-score" :class="score === 100 ? 'pass' : 'fail'">{{ score === 100 ? '回答正确' : '回答错误' }}</span>
        <button v-if="lessonId" type="button" class="btn btn-ghost" :disabled="explaining" @click="explainWithAi">
          <Sparkles :size="13" />
          {{ explaining ? '解析中…' : 'AI 展开解析' }}
        </button>
        <button type="button" class="btn btn-ghost" @click="reset">重新作答</button>
      </template>
    </div>

    <div v-if="submitted && quiz.explain" class="quiz-explain">
      <div class="explain-title">解析</div>
      <div class="explain-body" v-html="render(quiz.explain)"></div>
    </div>

    <div v-if="explainText || explaining" class="quiz-explain quiz-ai">
      <div class="explain-title"><Sparkles :size="12" /> AI 解析</div>
      <div v-if="explainError" class="explain-error">{{ explainError }}</div>
      <div v-else-if="explainText" class="explain-body" v-html="renderAiBubble(explainText)"></div>
      <span v-else class="typing">▍</span>
    </div>
  </div>
</template>

<style scoped>
.quiz-card {
  margin: 20px 0 8px;
  padding: 16px 18px;
  border: 1px solid var(--border);
  border-left: 4px solid var(--primary);
  border-radius: var(--radius-md);
  background: var(--bg-card);
}

.quiz-head { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
.quiz-badge {
  font-size: 12px; font-weight: 600; color: #fff;
  background: var(--primary); padding: 2px 10px; border-radius: 999px;
}
.quiz-tip { font-size: 12px; color: var(--text-3); }

.quiz-question { font-weight: 600; font-size: 15px; line-height: 1.7; margin-bottom: 12px; }
.quiz-question :deep(.katex) { font-size: 1em; }

.quiz-options { display: flex; flex-direction: column; gap: 8px; margin-bottom: 14px; }

.quiz-opt {
  display: flex; align-items: center; gap: 10px;
  padding: 9px 12px; border: 1px solid var(--border); border-radius: var(--radius-sm);
  background: var(--bg-card); color: var(--text-1); cursor: pointer; text-align: left;
  font-size: 14px; line-height: 1.6; transition: border-color .15s, background .15s;
}
.quiz-opt:hover:not(.submitted) { border-color: var(--primary); }
.quiz-opt.selected { border-color: var(--primary); background: var(--primary-soft); }
.quiz-opt.correct { border-color: var(--success, #16a34a); background: color-mix(in srgb, var(--success) 8%, transparent); }
.quiz-opt.wrong { border-color: var(--danger, #dc2626); background: color-mix(in srgb, var(--danger) 8%, transparent); }

.opt-idx {
  width: 22px; height: 22px; border-radius: 6px; flex-shrink: 0;
  background: var(--bg-hover); color: var(--text-2);
  display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 600;
}
.quiz-opt.selected .opt-idx { background: var(--primary); color: #fff; }
.quiz-opt.correct .opt-idx { background: var(--success, #16a34a); color: #fff; }
.quiz-opt.wrong .opt-idx { background: var(--danger, #dc2626); color: #fff; }

.opt-text { flex: 1; }
.opt-mark { font-weight: 700; }
.quiz-opt.correct .opt-mark { color: var(--success, #16a34a); }
.quiz-opt.wrong .opt-mark { color: var(--danger, #dc2626); }

.quiz-actions { display: flex; align-items: center; gap: 14px; }
.quiz-score { font-size: 14px; font-weight: 600; }
.quiz-score.pass { color: var(--success, #16a34a); }
.quiz-score.fail { color: var(--danger, #dc2626); }

.btn { font-size: 13px; padding: 6px 16px; border-radius: var(--radius-sm); cursor: pointer; border: none; }
.btn-primary { background: var(--primary); color: #fff; }
.btn-primary:disabled { opacity: .5; cursor: not-allowed; }
.btn-ghost {
  background: none; border: 1px solid var(--border); color: var(--text-2);
  display: inline-flex; align-items: center; gap: 5px;
}
.btn-ghost:disabled { opacity: .5; cursor: not-allowed; }

.quiz-explain {
  margin-top: 14px; padding: 12px 14px; border-radius: var(--radius-sm);
  background: var(--bg-hover);
}
.explain-title { font-size: 12px; font-weight: 600; color: var(--primary); margin-bottom: 6px; display: flex; align-items: center; gap: 4px; }
.explain-body { font-size: 14px; line-height: 1.7; color: var(--text-2); }
.explain-body :deep(.katex) { font-size: 1em; }

/* AI 展开解析：流式输出区 */
.quiz-ai { border: 1px solid color-mix(in srgb, var(--primary) 35%, transparent); }
.explain-error { font-size: 13px; color: var(--danger, #dc2626); line-height: 1.6; }
.typing { display: inline-block; animation: blink 1s steps(2) infinite; color: var(--primary); }
@keyframes blink { 50% { opacity: 0; } }
</style>
