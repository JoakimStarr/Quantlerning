<script setup lang="ts">
import { ref } from 'vue'
import MarkdownIt from 'markdown-it'
import mathPlugin from '../../utils/markdownMath'
import 'katex/dist/katex.min.css'
import { judgeAnswer } from '@/api'
import { recordExercise } from '@/stores/progress'

// 应用题（:::exercise 块）：展示题目 + 用户输入答案 + 调 AI 批改（SSE 流式）
// 题目/提示为 Markdown 文本（支持 LaTeX），AI 批改结果渲染 Markdown/LaTeX

export interface ExerciseQuestion {
  title: string
  hint?: string
}

const props = defineProps<{
  exercise: ExerciseQuestion
  lessonId: string
  sectionIndex: number
}>()

const md = new MarkdownIt({ html: false, linkify: true }).use(mathPlugin, {
  throwOnError: false,
  errorColor: '#dc2626',
})

const render = (text: string) => md.render(text)

// AI 输出的公式分隔符统一归一化（与 AiAskPanel 一致）
function renderBubble(content: string): string {
  const normalized = content
    .replace(/\$\$([\s\S]+?)\$\$/g, (_, m: string) => `$${m.trim()}$`)
    .replace(/\\\[([\s\S]+?)\\\]/g, (_, m: string) => `$${m.trim()}$`)
    .replace(/\\\(([\s\S]+?)\\\)/g, (_, m: string) => `$${m.trim()}$`)
  return md.render(normalized)
}

const answer = ref('')
const judging = ref(false)
const error = ref('')
const feedback = ref('')
const abortCtrl = ref<AbortController | null>(null)

const maxLen = 4000

async function judge() {
  if (judging.value) return
  if (!answer.value.trim()) {
    error.value = '请先写下你的答案，再请 AI 批改。'
    return
  }
  error.value = ''
  feedback.value = ''
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
    <div v-if="feedback" class="judge-result" v-html="renderBubble(feedback)"></div>
  </div>
</template>

<style scoped>
.exercise-card {
  margin: 20px 0 8px;
  padding: 16px 18px;
  border: 1px solid var(--border);
  border-left: 4px solid #7c3aed;
  border-radius: var(--radius-md);
  background: var(--bg-card);
}

.exercise-head { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
.exercise-badge {
  font-size: 12px; font-weight: 600; color: #fff;
  background: #7c3aed; padding: 2px 10px; border-radius: 999px;
}
.exercise-tip { font-size: 12px; color: var(--text-3); }

.exercise-question { font-weight: 600; font-size: 15px; line-height: 1.7; margin-bottom: 10px; }
.exercise-question :deep(.katex) { font-size: 1em; }

.exercise-hint {
  font-size: 13px; line-height: 1.7; color: var(--text-2);
  background: var(--bg-hover); border-radius: var(--radius-sm);
  padding: 8px 12px; margin-bottom: 12px;
}
.exercise-hint .hint-label { font-weight: 600; color: #7c3aed; }
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
.answer-box:focus { outline: none; border-color: #7c3aed; }
.answer-box:disabled { opacity: 0.6; }

.exercise-actions { margin-top: 10px; display: flex; align-items: center; gap: 12px; }

.btn { font-size: 13px; padding: 6px 16px; border-radius: var(--radius-sm); cursor: pointer; border: none; }
.btn-primary { background: #7c3aed; color: #fff; }
.btn-primary:disabled { opacity: .5; cursor: not-allowed; }
.btn-ghost { background: none; border: 1px solid var(--border); color: var(--text-2); }

.judge-status { margin-top: 12px; font-size: 13px; color: var(--text-3); }
.judge-error {
  margin-top: 12px; font-size: 13px; color: var(--danger, #dc2626);
  background: color-mix(in srgb, var(--danger, #dc2626) 8%, transparent);
  border-radius: var(--radius-sm); padding: 8px 12px; line-height: 1.6;
}
.judge-result {
  margin-top: 14px; padding: 14px;
  border-radius: var(--radius-sm);
  background: var(--bg-hover);
  border-left: 3px solid #7c3aed;
  font-size: 14px;
  line-height: 1.75;
  color: var(--text-1);
}
.judge-result :deep(p) { margin: 0 0 8px; }
.judge-result :deep(p:last-child) { margin-bottom: 0; }
.judge-result :deep(strong) { font-weight: 600; }
.judge-result :deep(ul),
.judge-result :deep(ol) { margin: 0 0 8px; padding-left: 1.4em; }
.judge-result :deep(li) { margin-bottom: 2px; }
.judge-result :deep(code) {
  font-family: var(--font-mono);
  font-size: 0.88em;
  background: color-mix(in srgb, currentColor 12%, transparent);
  padding: 1px 5px;
  border-radius: 4px;
}
.judge-result :deep(pre) {
  background: #0f1420;
  color: #e6e9ef;
  border-radius: var(--radius-sm);
  padding: 10px 12px;
  overflow-x: auto;
  margin: 0 0 8px;
}
.judge-result :deep(pre code) {
  background: none;
  padding: 0;
  font-size: 12.5px;
  line-height: 1.5;
}
.judge-result :deep(blockquote) {
  margin: 0 0 8px;
  padding: 6px 10px;
  border-left: 3px solid #7c3aed;
  background: color-mix(in srgb, #7c3aed 8%, transparent);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
}
.judge-result :deep(.katex) { font-size: 1em; }
.typing { display: inline-block; animation: blink 1s steps(2) infinite; }
@keyframes blink { 50% { opacity: 0; } }
</style>
