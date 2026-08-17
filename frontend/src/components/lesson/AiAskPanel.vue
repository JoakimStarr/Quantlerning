<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  Brain,
  ChevronDown,
  Copy,
  Maximize2,
  Minimize2,
  Search,
  Send,
  Sparkles,
  X,
} from 'lucide-vue-next'
import { createMarkdown } from '@/utils/markdownIt'
import { unwrapOuterFence } from '@/utils/aiOutput'
import 'katex/dist/katex.min.css'
import { fetchAIModels, streamChat, type ChatTurn } from '@/api'
import { useChatHistory } from '@/composables/useChatHistory'

// 运行时注入代码块的复制按钮图标（DOM 操作无法用 Vue 组件，内联 lucide Copy 的 SVG）
const COPY_SVG =
  '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>'

// AI 回答渲染器：与课程正文同一套 markdown-it + katex，支持公式/代码
const bubbleMd = createMarkdown({ breaks: false })

// AI 输出的公式分隔符不统一（$$...$$、\(...\)、\[...\] 都可能出现），
// 统一归一化为行内 $...$，避免块级 $$ 不在行首时无法渲染；
// trim 掉公式首尾空白，防止 $ 与空白相邻而被识别为普通文本
// 先剥掉外层代码围栏：模型把整段 Markdown 包在 ```…``` 里时会整块显示为代码框
function renderBubble(content: string): string {
  const normalized = unwrapOuterFence(content)
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
    btn.innerHTML = COPY_SVG
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

// ---------- 深度思考 & 模型选择（全局偏好，localStorage 持久化）----------
const deep = ref(localStorage.getItem('ql:aiAskDeep') === '1')
const model = ref(localStorage.getItem('ql:aiAskModel') || '') // '' = 默认（当前配置）
const models = ref<string[]>([])
const currentModel = ref('')

// 模型下拉（自定义搜索弹层）
const modelOpen = ref(false)
const modelQuery = ref('')
const modelRef = ref<HTMLElement | null>(null)

const filteredModels = computed(() => {
  const q = modelQuery.value.trim().toLowerCase()
  if (!q) return models.value
  return models.value.filter((m) => m.toLowerCase().includes(q))
})

const modelLabel = computed(() => {
  if (model.value) return model.value
  return currentModel.value ? `默认 · ${currentModel.value}` : '默认模型'
})

const deepLabel = computed(() => (deep.value ? '深度思考·开' : '深度思考'))

// 历史持久化（按「课程+小节」存 localStorage）
const history = useChatHistory(() => props.lessonId, () => props.sectionIndex, messages)

onMounted(async () => {
  history.restore()
  try {
    const { models: list, current } = await fetchAIModels()
    models.value = list
    currentModel.value = current
    // 之前保存的模型若已不在列表（配置变更），回退默认
    if (model.value && !list.includes(model.value)) model.value = ''
  } catch {
    // 拉不到模型列表不阻塞：仍可用默认模型对话
  }
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocClick)
  history.flushSave()
})

// 模型下拉：展开/收起、点击外部关闭
function toggleModel() {
  if (modelOpen.value) closeModel()
  else {
    modelOpen.value = true
    modelQuery.value = ''
  }
}
function closeModel() {
  modelOpen.value = false
}
function onDocClick(e: MouseEvent) {
  if (modelRef.value && !modelRef.value.contains(e.target as Node)) closeModel()
}
watch(modelOpen, (v) => {
  if (v) document.addEventListener('click', onDocClick)
  else document.removeEventListener('click', onDocClick)
})
function pickModel(m: string) {
  model.value = m
  if (m) localStorage.setItem('ql:aiAskModel', m)
  else localStorage.removeItem('ql:aiAskModel')
  closeModel()
}
function toggleDeep() {
  deep.value = !deep.value
  if (deep.value) localStorage.setItem('ql:aiAskDeep', '1')
  else localStorage.removeItem('ql:aiAskDeep')
}

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
        model: model.value || undefined,
        deep: deep.value,
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
    <Sparkles :size="22" />
  </button>

  <!-- 抽屉面板 -->
  <Transition name="panel">
    <div v-if="open" class="ask-panel" :class="{ expanded }">
      <header class="panel-head">
        <div class="panel-brand">
          <span class="avatar"><Sparkles :size="15" /></span>
          <div class="panel-title-box">
            <span class="panel-ai">AI 追问</span>
            <span class="panel-section" :title="sectionTitle">{{ sectionTitle || '当前小节' }}</span>
          </div>
        </div>
        <div class="panel-actions">
          <button v-if="messages.length" class="panel-clear" title="清空本小节对话" @click="clearHistory">
            清空
          </button>
          <button class="panel-expand" :title="expanded ? '缩小窗口' : '放大窗口'" @click="expanded = !expanded">
            <Maximize2 v-if="!expanded" :size="14" />
            <Minimize2 v-else :size="14" />
          </button>
          <button class="panel-close" title="关闭" @click="close"><X :size="16" /></button>
        </div>
      </header>

      <div ref="listRef" class="msg-list">
        <div v-if="messages.length === 0" class="msg-empty">
          <span class="empty-icon"><Sparkles :size="20" /></span>
          <p class="empty-title">正在学习「{{ sectionTitle }}」？</p>
          <p class="empty-sub">针对这个知识点提问，AI 导师会结合本节内容回答。<br />可开启「深度思考」获得更深入的分析。</p>
        </div>
        <div
          v-for="(m, i) in messages"
          :key="i"
          class="msg"
          :class="m.role === 'user' ? 'msg-user' : 'msg-ai'"
        >
          <span v-if="m.role === 'assistant'" class="msg-avatar"><Sparkles :size="12" /></span>
          <!-- user 保持纯文本；assistant 渲染 Markdown/LaTeX -->
          <div v-if="m.role === 'user'" class="bubble bubble-user">{{ m.content }}</div>
          <div v-else class="bubble bubble-md">
            <span v-if="m.content" v-html="renderBubble(m.content)"></span>
            <span v-else-if="thinking && i === messages.length - 1" class="typing">▍</span>
            <button v-if="m.content" class="copy-btn" title="复制回答" @click="copyMessage(m.content)"><Copy :size="13" /></button>
          </div>
        </div>
      </div>

      <div v-if="error" class="msg-error">{{ error }}</div>

      <footer class="panel-input">
        <div class="input-wrap">
          <textarea
            ref="inputRef"
            v-model="input"
            class="input-box"
            :placeholder="thinking ? 'AI 思考中…' : '输入你的问题…'"
            :disabled="thinking"
            rows="2"
            @keydown.enter.exact.prevent="send"
          />
          <button class="send-btn" :disabled="thinking || !input.trim()" title="发送" @click="send">
            <Send :size="15" />
          </button>
        </div>
        <div class="toolbar">
          <button class="deep-btn" :class="{ on: deep }" :title="'深度思考：回答前先深入分析、分步推理'" @click="toggleDeep">
            <Brain :size="13" />
            {{ deepLabel }}
          </button>
          <div ref="modelRef" class="model-select">
            <button class="model-btn" :title="modelLabel" @click.stop="toggleModel">
              <span class="model-label">{{ modelLabel }}</span>
              <ChevronDown :size="13" class="chev" :class="{ open: modelOpen }" />
            </button>
            <Transition name="drop">
              <div v-if="modelOpen" class="model-pop">
                <div class="model-search">
                  <Search :size="13" />
                  <input v-model="modelQuery" placeholder="搜索模型…" @click.stop />
                </div>
                <div class="model-list">
                  <button class="model-item" :class="{ cur: model === '' }" @click="pickModel('')">
                    <span class="model-name">{{ currentModel ? `默认 · ${currentModel}` : '默认模型' }}</span>
                    <span class="model-tag">主配置</span>
                  </button>
                  <button
                    v-for="m in filteredModels"
                    :key="m"
                    class="model-item"
                    :class="{ cur: model === m }"
                    @click="pickModel(m)"
                  >
                    <span class="model-name">{{ m }}</span>
                  </button>
                  <div v-if="filteredModels.length === 0" class="model-empty">无匹配模型</div>
                </div>
              </div>
            </Transition>
          </div>
          <span v-if="deep" class="toolbar-hint">回答将更详细深入</span>
        </div>
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
  background: linear-gradient(135deg, var(--primary), var(--primary-hover));
  color: #fff;
  box-shadow: 0 6px 20px color-mix(in srgb, var(--primary) 35%, transparent);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: transform 0.15s, background 0.15s, opacity 0.15s;
}
.ask-fab:hover { transform: scale(1.06); }
.ask-fab.active { background: var(--text-3); transform: scale(0.94); }

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
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
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
  padding: 11px 14px;
  border-bottom: 1px solid var(--border);
  background: linear-gradient(
    180deg,
    color-mix(in srgb, var(--primary-soft) 55%, transparent),
    transparent
  );
}
.panel-brand { display: flex; align-items: center; gap: 9px; min-width: 0; }
.avatar {
  flex-shrink: 0;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--violet), var(--primary));
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 8px color-mix(in srgb, var(--primary) 35%, transparent);
}
.panel-title-box { display: flex; flex-direction: column; min-width: 0; gap: 1px; }
.panel-ai { font-weight: 700; font-size: 14px; line-height: 1.2; }
.panel-section {
  font-size: 11.5px;
  color: var(--text-3);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.panel-actions { display: flex; align-items: center; gap: 2px; flex-shrink: 0; }
.panel-clear {
  border: none;
  background: none;
  font-size: 12px;
  color: var(--text-3);
  cursor: pointer;
  padding: 4px 8px;
  border-radius: var(--radius-sm);
}
.panel-clear:hover {
  color: var(--danger, #dc2626);
  background: color-mix(in srgb, var(--danger, #dc2626) 8%, transparent);
}
.panel-expand,
.panel-close {
  border: none;
  background: none;
  color: var(--text-3);
  cursor: pointer;
  line-height: 1;
  padding: 5px 6px;
  border-radius: var(--radius-sm);
  transition: color 0.12s, background 0.12s;
}
.panel-expand:hover,
.panel-close:hover { color: var(--text-1); background: var(--bg-hover); }

.msg-list {
  flex: 1;
  overflow-y: auto;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.msg-empty {
  margin: auto;
  text-align: center;
  font-size: 13px;
  color: var(--text-3);
  line-height: 1.8;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}
.empty-icon {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--violet), var(--primary));
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 4px;
  box-shadow: 0 4px 14px color-mix(in srgb, var(--primary) 30%, transparent);
}
.empty-title { margin: 0; font-size: 13.5px; color: var(--text-2); font-weight: 600; }
.empty-sub { margin: 0; font-size: 12.5px; }

.msg { display: flex; align-items: flex-start; gap: 8px; }
.msg-user { justify-content: flex-end; }
.msg-ai { justify-content: flex-start; }
.msg-avatar {
  flex-shrink: 0;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--violet), var(--primary));
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 2px;
}
.bubble {
  max-width: 86%;
  padding: 9px 13px;
  border-radius: var(--radius-md);
  font-size: 14px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}
.msg-user .bubble-user {
  background: linear-gradient(135deg, var(--primary), var(--primary-hover));
  color: #fff;
  border-bottom-right-radius: 3px;
  box-shadow: 0 2px 8px color-mix(in srgb, var(--primary) 25%, transparent);
}
.msg-ai .bubble-md {
  background: var(--bg-hover);
  color: var(--text-1);
  border-bottom-left-radius: 3px;
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
.bubble-md :deep(pre) {
  position: relative;
  background: #0f1420;
  color: #e6e9ef;
  border-radius: var(--radius-sm);
  padding: 10px 12px;
  overflow-x: auto;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  word-break: break-word;
  margin: 0 0 8px;
  font-size: 13px;
  line-height: 1.6;
}
.bubble-md :deep(pre code) {
  background: none;
  color: inherit;
  padding: 0;
  font-size: 13px;
  line-height: 1.6;
}
.bubble-md :deep(code) {
  font-family: var(--font-mono);
  font-size: 0.88em;
  background: color-mix(in srgb, currentColor 12%, transparent);
  padding: 1px 5px;
  border-radius: 4px;
}
.bubble-md :deep(.copy-code-btn) {
  position: absolute;
  top: 6px; right: 6px;
  border: none; background: rgba(255, 255, 255, 0.08);
  color: var(--textWeak, #9aa3af);
  font-size: 12px; line-height: 1;
  padding: 4px 7px; border-radius: 4px;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.15s;
}
.bubble-md :deep(pre:hover .copy-code-btn) { opacity: 1; }
.bubble-md :deep(.copy-code-btn:hover) { color: #fff; background: rgba(255, 255, 255, 0.16); }
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
  padding: 10px 14px 12px;
  border-top: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.input-wrap { position: relative; }
.input-box {
  width: 100%;
  resize: none;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-card);
  color: var(--text-1);
  padding: 9px 44px 9px 11px;
  font-size: 13.5px;
  line-height: 1.5;
  font-family: inherit;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.input-box:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--primary) 14%, transparent);
}
.input-box:disabled { opacity: 0.6; }
.send-btn {
  position: absolute;
  right: 7px;
  bottom: 7px;
  width: 30px;
  height: 30px;
  border: none;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--primary), var(--primary-hover));
  color: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: opacity 0.15s, transform 0.15s;
}
.send-btn:hover:not(:disabled) { transform: scale(1.05); }
.send-btn:disabled { opacity: 0.4; cursor: not-allowed; }

.toolbar { display: flex; align-items: center; gap: 8px; min-height: 26px; }
.deep-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border: 1px solid var(--border);
  background: var(--bg-card);
  color: var(--text-2);
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 999px;
  cursor: pointer;
  transition: all 0.15s;
  flex-shrink: 0;
}
.deep-btn:hover { border-color: var(--primary); color: var(--primary); }
.deep-btn.on {
  background: linear-gradient(135deg, var(--primary), var(--primary-hover));
  border-color: transparent;
  color: #fff;
}
.toolbar-hint {
  font-size: 11px;
  color: var(--text-3);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 模型选择下拉 */
.model-select { position: relative; flex-shrink: 0; min-width: 0; }
.model-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  max-width: 220px;
  border: 1px solid var(--border);
  background: var(--bg-card);
  color: var(--text-2);
  font-size: 12px;
  padding: 4px 9px;
  border-radius: 999px;
  cursor: pointer;
  transition: all 0.15s;
}
.model-btn:hover { border-color: var(--primary); color: var(--primary); }
.model-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.model-btn .chev { flex-shrink: 0; transition: transform 0.15s; }
.model-btn .chev.open { transform: rotate(180deg); }

.model-pop {
  position: absolute;
  right: 0;
  bottom: calc(100% + 8px);
  width: 300px;
  max-width: 70vw;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.model-search {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 10px;
  border-bottom: 1px solid var(--border);
  color: var(--text-3);
}
.model-search input {
  flex: 1;
  border: none;
  background: none;
  outline: none;
  font-size: 12.5px;
  color: var(--text-1);
  font-family: inherit;
}
.model-list { max-height: 240px; overflow-y: auto; padding: 4px; }
.model-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
  border: none;
  background: none;
  text-align: left;
  padding: 7px 9px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 12.5px;
  color: var(--text-1);
}
.model-item:hover { background: var(--bg-hover); }
.model-item.cur { background: var(--primary-soft); color: var(--primary); }
.model-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: var(--font-mono);
  font-size: 12px;
}
.model-tag {
  flex-shrink: 0;
  font-size: 10.5px;
  color: var(--text-3);
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 1px 7px;
}
.model-item.cur .model-tag { border-color: transparent; color: inherit; }
.model-empty { padding: 14px; text-align: center; font-size: 12px; color: var(--text-3); }

.panel-enter-active, .panel-leave-active { transition: opacity 0.15s, transform 0.15s; }
.panel-enter-from, .panel-leave-to { opacity: 0; transform: translateY(8px); }
.drop-enter-active, .drop-leave-active { transition: opacity 0.12s, transform 0.12s; }
.drop-enter-from, .drop-leave-to { opacity: 0; transform: translateY(6px); }

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
