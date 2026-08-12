<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from 'vue'
import MarkdownIt from 'markdown-it'
import mathPlugin from '@/utils/markdownMath'
import 'katex/dist/katex.min.css'
import { streamChat, type ChatTurn } from '@/api'
import { useChatHistory } from '@/composables/useChatHistory'
// AI 回答渲染器：与课程正文同一套 markdown-it + katex，支持公式/代码
const bubbleMd = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: false,
}).use(mathPlugin, {
  throwOnError: false,
  errorColor: '#dc2626',
})

// AI 输出的公式分隔符不统一（$$...$$、\(...\)、\[...\] 都可能出现），
// 统一归一化为行内 $...$，避免块级 $$ 不在行首时无法渲染；
// trim 掉公式首尾空白，防止 $ 与空白相邻而被识别为普通文本
function renderBubble(content: string): string {
  const normalized = content
    .replace(/\$\$([\s\S]+?)\$\$/g, (_, m: string) => `$${m.trim()}$`)
    .replace(/\\\[([\s\S]+?)\\\]/g, (_, m: string) => `$${m.trim()}$`)
    .replace(/\\\(([\s\S]+?)\\\)/g, (_, m: string) => `$${m.trim()}$`)
  return bubbleMd.render(normalized)
}

// 给 AI 回答里的每个代码块加「复制代码」按钮（v-html 无法绑事件，运行时注入 DOM）
function enhanceCodeBlocks() {
  const list = listRef.value
  if (!list) return
  list.querySelectorAll<HTMLElement>('pre:not([data-copied])').forEach((pre) => {
    pre.setAttribute('data-copied', '1')
    const btn = document.createElement('button')
    btn.className = 'copy-code-btn'
    btn.title = '复制代码'
    btn.textContent = '⧉'
    btn.setAttribute('aria-label', '复制代码')
    btn.addEventListener('click', () => {
      navigator.clipboard?.writeText(pre.innerText)?.catch(() => {})
    })
    pre.appendChild(btn)
  })
}

// 课程页「AI 追问」悬浮面板：围绕当前小节多轮对话，SSE 流式渲染
// 对话按「课程+小节」持久化到 localStorage：关闭面板/刷新/切课后再回来可继续聊

const props = defineProps<{
  lessonId: string
  sectionIndex: number
  sectionTitle: string
}>()

const open = ref(false)
const expanded = ref(false) // 放大模式：面板变宽填充右侧内容区
const input = ref('')
const thinking = ref(false)
const error = ref('')
const abortCtrl = ref<AbortController | null>(null)

// 对话消息：assistant 消息的 content 在流式期间持续追加
const messages = ref<ChatTurn[]>([])
const listRef = ref<HTMLElement | null>(null)
const inputRef = ref<HTMLTextAreaElement | null>(null)

const maxLen = 2000

// 历史持久化（按「课程+小节」存 localStorage）
const history = useChatHistory(() => props.lessonId, () => props.sectionIndex, messages)

onMounted(() => history.restore())

// 消息变化（含流式追加）→ DOM 更新后给代码块补复制按钮
watch(
  messages,
  async () => {
    await nextTick()
    enhanceCodeBlocks()
  },
  { deep: true },
)

/** 外部调用：打开面板并把选中文字作为问题预填（「选中问 AI」） */
function ask(prefill: string) {
  open.value = true
  error.value = ''
  input.value = prefill
  void nextTick(() => inputRef.value?.focus())
}

defineExpose({ ask })

function toggle() {
  if (open.value) {
    close()
  } else {
    open.value = true
    error.value = ''
  }
}

function close() {
  abortCtrl.value?.abort()
  abortCtrl.value = null
  thinking.value = false
  history.flushSave()
  open.value = false
}

function clearHistory() {
  abortCtrl.value?.abort()
  abortCtrl.value = null
  thinking.value = false
  history.clear()
  error.value = ''
}

// 复制 AI 回答全文（含 LaTeX 源码）
function copyMessage(text: string) {
  // 非安全上下文（http）下 navigator.clipboard 为 undefined，需整链可选
  navigator.clipboard?.writeText(text)?.catch(() => {})
}

async function send() {
  const text = input.value.trim()
  if (!text || thinking.value) return

  error.value = ''
  input.value = ''
  const question: ChatTurn = { role: 'user', content: text.slice(0, maxLen) }
  messages.value.push(question)
  messages.value.push({ role: 'assistant', content: '' })

  thinking.value = true
  const ctrl = new AbortController()
  abortCtrl.value = ctrl
  await scrollToBottom()

  const history: ChatTurn[] = messages.value.slice(0, -1)
  try {
    const result = await streamChat(
      {
        lesson_id: props.lessonId,
        section_index: props.sectionIndex,
        messages: history,
      },
      (delta) => {
        const last = messages.value[messages.value.length - 1]
        if (last?.role === 'assistant') {
          last.content += delta
          void scrollToBottom()
        }
      },
      ctrl.signal,
    )
    if (result.error) {
      error.value = result.error
      // 保留空 assistant 消息前，先移除空条，避免留一个空气泡
      const last = messages.value[messages.value.length - 1]
      if (last?.role === 'assistant' && !last.content) messages.value.pop()
    }
  } catch {
    // 用户中止（关闭面板/切课）等：移除空气泡，不显示错误
    const last = messages.value[messages.value.length - 1]
    if (last?.role === 'assistant' && !last.content) messages.value.pop()
  } finally {
    thinking.value = false
    abortCtrl.value = null
    await scrollToBottom()
  }
}

async function scrollToBottom() {
  await nextTick()
  if (listRef.value) listRef.value.scrollTop = listRef.value.scrollHeight
}

// 课程或小节变化：保存当前历史，载入新课程/小节历史（对话按「课程+小节」相互独立）
watch(
  () => [props.lessonId, props.sectionIndex],
  () => {
    abortCtrl.value?.abort()
    abortCtrl.value = null
    thinking.value = false
    history.flushSave()
    history.restore()
    error.value = ''
    void scrollToBottom()
  },
)
</script>

<template>
  <!-- 悬浮按钮 -->
  <button class="ask-fab" :class="{ active: open }" title="AI 追问" @click="toggle">
    <span class="fab-ai">AI</span>
  </button>

  <!-- 抽屉面板 -->
  <Transition name="panel">
    <div v-if="open" class="ask-panel" :class="{ expanded }">
      <header class="panel-head">
        <div class="panel-title">
          <span class="panel-ai">AI 追问</span>
          <span class="panel-section" :title="sectionTitle">{{ sectionTitle || '当前小节' }}</span>
        </div>
        <div class="panel-actions">
          <button v-if="messages.length" class="panel-clear" title="清空本小节对话" @click="clearHistory">
            清空
          </button>
          <button class="panel-expand" :title="expanded ? '缩小窗口' : '放大窗口'" @click="expanded = !expanded">
            {{ expanded ? '⤡' : '⤢' }}
          </button>
          <button class="panel-close" title="关闭" @click="close">×</button>
        </div>
      </header>

      <div ref="listRef" class="msg-list">
        <div v-if="messages.length === 0" class="msg-empty">
          正在学习「{{ sectionTitle }}」？
          <br />针对这个知识点提问，AI 导师会结合本节内容回答。
        </div>
        <div
          v-for="(m, i) in messages"
          :key="i"
          class="msg"
          :class="m.role === 'user' ? 'msg-user' : 'msg-ai'"
        >
          <!-- user 保持纯文本；assistant 渲染 Markdown/LaTeX -->
          <div v-if="m.role === 'user'" class="bubble">{{ m.content }}</div>
          <div v-else class="bubble bubble-md">
            <span v-if="m.content" v-html="renderBubble(m.content)"></span>
            <span v-else-if="thinking && i === messages.length - 1" class="typing">▍</span>
            <button v-if="m.content" class="copy-btn" title="复制回答" @click="copyMessage(m.content)">⧉</button>
          </div>
        </div>
      </div>

      <div v-if="error" class="msg-error">{{ error }}</div>

      <footer class="panel-input">
        <textarea
          ref="inputRef"
          v-model="input"
          class="input-box"
          :placeholder="thinking ? 'AI 思考中…' : '输入你的问题…'"
          :disabled="thinking"
          rows="2"
          @keydown.enter.exact.prevent="send"
        />
        <button class="send-btn" :disabled="thinking || !input.trim()" @click="send">
          {{ thinking ? '…' : '发送' }}
        </button>
      </footer>
    </div>
  </Transition>
</template>

<style scoped>
.ask-fab {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 100;
  width: 52px;
  height: 52px;
  border-radius: 50%;
  border: none;
  cursor: pointer;
  background: var(--primary);
  color: #fff;
  box-shadow: 0 6px 20px rgba(37, 99, 235, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: transform 0.15s, background 0.15s;
}
.ask-fab:hover { transform: scale(1.06); }
.ask-fab.active { background: var(--text-3); }
.fab-ai {
  font-weight: 700;
  font-size: 15px;
  letter-spacing: 0.5px;
}

.ask-panel {
  position: fixed;
  right: 24px;
  bottom: 88px;
  z-index: 100;
  width: 400px;
  max-width: calc(100vw - 32px);
  height: min(70vh, 560px);
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-md, 0 10px 40px rgba(0, 0, 0, 0.18));
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: width 0.2s ease, height 0.2s ease;
}

/* 放大模式：高度接近全高，宽度保持小窗不变 */
.ask-panel.expanded {
  height: calc(100vh - 32px);
  right: 24px;
  bottom: 24px;
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 12px 14px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-hover);
}
.panel-title { display: flex; align-items: center; gap: 8px; min-width: 0; }
.panel-ai { font-weight: 600; font-size: 14px; flex-shrink: 0; }
.panel-section {
  font-size: 12px;
  color: var(--text-3);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  border-left: 1px solid var(--border);
  padding-left: 8px;
}
.panel-actions { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }
.panel-clear {
  border: none;
  background: none;
  font-size: 12px;
  color: var(--text-3);
  cursor: pointer;
  padding: 3px 8px;
  border-radius: var(--radius-sm);
}
.panel-clear:hover {
  color: var(--danger, #dc2626);
  background: color-mix(in srgb, var(--danger, #dc2626) 8%, transparent);
}
.panel-close {
  border: none;
  background: none;
  font-size: 20px;
  color: var(--text-3);
  cursor: pointer;
  line-height: 1;
}
.panel-close:hover { color: var(--text-1); }

.panel-expand {
  border: none;
  background: none;
  font-size: 16px;
  color: var(--text-3);
  cursor: pointer;
  line-height: 1;
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  transition: color 0.12s, background 0.12s;
}
.panel-expand:hover { color: var(--primary); background: var(--bg-hover); }

.msg-list {
  flex: 1;
  overflow-y: auto;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.msg-empty {
  margin: auto;
  text-align: center;
  font-size: 13px;
  color: var(--text-3);
  line-height: 1.8;
}
.msg { display: flex; }
.msg-user { justify-content: flex-end; }
.msg-ai { justify-content: flex-start; }
.bubble {
  max-width: 86%;
  padding: 8px 12px;
  border-radius: var(--radius-sm);
  font-size: 14px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}
.msg-user .bubble {
  background: var(--primary);
  color: #fff;
  border-bottom-right-radius: 2px;
}
.msg-ai .bubble {
  background: var(--bg-hover);
  color: var(--text-1);
  border-bottom-left-radius: 2px;
}

/* AI 回答的 Markdown 渲染：段落/代码/列表/公式 */
.bubble-md {
  position: relative;
  white-space: normal;
}
.copy-btn {
  position: absolute;
  top: 4px; right: 4px;
  border: none; background: none; cursor: pointer;
  color: var(--text-3); font-size: 13px; line-height: 1;
  padding: 3px 6px; border-radius: 4px;
  opacity: 0;
  transition: opacity 0.15s;
}
.bubble-md:hover .copy-btn { opacity: 1; }
.copy-btn:hover { color: var(--primary); background: var(--bg-card); }
.bubble-md :deep(p) { margin: 0 0 8px; }
.bubble-md :deep(p:last-child) { margin-bottom: 0; }
.bubble-md :deep(strong) { font-weight: 600; }
.bubble-md :deep(ul),
.bubble-md :deep(ol) { margin: 0 0 8px; padding-left: 1.4em; }
.bubble-md :deep(li) { margin-bottom: 2px; }
.bubble-md :deep(code) {
  font-family: var(--font-mono);
  font-size: 0.88em;
  background: color-mix(in srgb, currentColor 12%, transparent);
  padding: 1px 5px;
  border-radius: 4px;
}
.bubble-md :deep(pre) {
  position: relative;
  background: #0f1420;
  color: #e6e9ef;
  border-radius: var(--radius-sm);
  padding: 10px 12px;
  overflow-x: auto;
  margin: 0 0 8px;
}
.bubble-md :deep(.copy-code-btn) {
  position: absolute;
  top: 6px; right: 6px;
  border: none; background: rgba(255, 255, 255, 0.08);
  color: #9aa3af;
  font-size: 12px; line-height: 1;
  padding: 4px 7px; border-radius: 4px;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.15s;
}
.bubble-md :deep(pre:hover .copy-code-btn) { opacity: 1; }
.bubble-md :deep(.copy-code-btn:hover) { color: #fff; background: rgba(255, 255, 255, 0.16); }
.bubble-md :deep(pre code) {
  background: none;
  padding: 0;
  font-size: 12.5px;
  line-height: 1.5;
}
.bubble-md :deep(blockquote) {
  margin: 0 0 8px;
  padding: 6px 10px;
  border-left: 3px solid var(--primary);
  background: color-mix(in srgb, var(--primary) 8%, transparent);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
}
.bubble-md :deep(.katex) { font-size: 1em; }
.typing {
  display: inline-block;
  animation: blink 1s steps(2) infinite;
}
@keyframes blink { 50% { opacity: 0; } }

.msg-error {
  margin: 0 14px 6px;
  padding: 8px 12px;
  font-size: 12.5px;
  color: var(--danger, #dc2626);
  background: color-mix(in srgb, var(--danger, #dc2626) 8%, transparent);
  border-radius: var(--radius-sm);
  line-height: 1.6;
}

.panel-input {
  display: flex;
  gap: 8px;
  padding: 12px 14px;
  border-top: 1px solid var(--border);
}
.input-box {
  flex: 1;
  resize: none;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-card);
  color: var(--text-1);
  padding: 8px 10px;
  font-size: 13.5px;
  line-height: 1.5;
  font-family: inherit;
}
.input-box:focus { outline: none; border-color: var(--primary); }
.input-box:disabled { opacity: 0.6; }
.send-btn {
  padding: 0 16px;
  border: none;
  border-radius: var(--radius-sm);
  background: var(--primary);
  color: #fff;
  font-size: 13px;
  cursor: pointer;
  flex-shrink: 0;
}
.send-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.panel-enter-active, .panel-leave-active { transition: opacity 0.15s, transform 0.15s; }
.panel-enter-from, .panel-leave-to { opacity: 0; transform: translateY(8px); }

/* 移动端适配 */
@media (max-width: 900px) {
  .ask-fab { right: 14px; bottom: 14px; }
  .ask-panel {
    right: 8px;
    bottom: 78px;
    width: calc(100vw - 16px);
    max-width: calc(100vw - 16px);
    height: min(78dvh, 560px);
  }
}
</style>
