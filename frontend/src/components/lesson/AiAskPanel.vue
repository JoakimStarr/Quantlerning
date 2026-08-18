<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  Brain,
  ChevronDown,
  Copy,
  Globe,
  HelpCircle,
  Link2,
  Maximize2,
  Minimize2,
  Search,
  Send,
  Sparkles,
  Square,
  X,
} from 'lucide-vue-next'
import { createMarkdown } from '@/utils/markdownIt'
import { unwrapOuterFence } from '@/utils/aiOutput'
import 'katex/dist/katex.min.css'
import { fetchAIModels, fetchAISettings, streamChat, type ChatTurn } from '@/api'
import { useChatHistory } from '@/composables/useChatHistory'
import { aiPanelLayout } from '@/stores/aiPanel'

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

// 提取链接域名（去掉 www. 前缀），用于参考文献的灰色域名标注
function hostOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return ''
  }
}

// 给 AI 回答里的每个代码块加「复制代码」按钮（v-html 无法绑事件，运行时注入 DOM）
function enhanceCodeBlocks() {  const list = listRef.value
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

// 分栏模式：放大 + 屏幕够宽（≥1024px）时，正文与面板分割剩余空间（可拖拽分隔条）。
// 窄屏/手机保持浮层，避免图表被挤压。
const splitMedia = window.matchMedia('(min-width: 1024px)')
const SIDEBAR_W = 230 // 与 App.vue --sidebar-w 一致，用于计算默认分栏宽度
const WIDTH_MIN = 360
const WIDTH_MAX = 720

// 用户拖拽过则持久化宽度；否则按「剩余空间 40%」给默认值（两者共同分割剩余空间）
const savedSplitWidth = (() => {
  const v = Number(localStorage.getItem('ql:aiAskSplitWidth'))
  return Number.isFinite(v) && v >= WIDTH_MIN && v <= WIDTH_MAX ? v : null
})()
let splitWidth = savedSplitWidth // 可变：拖拽后更新，供再次展开分栏时恢复

function clampWidth(w: number) {
  const remaining = window.innerWidth - SIDEBAR_W
  // 上限留出至少 420px 给正文，避免图表被压太窄
  return Math.min(Math.max(Math.round(w), WIDTH_MIN), Math.max(WIDTH_MIN, remaining - 420))
}

function defaultSplitWidth() {
  return clampWidth((window.innerWidth - SIDEBAR_W) * 0.45)
}

function updateSplit() {
  const on = open.value && expanded.value && splitMedia.matches
  if (on) aiPanelLayout.width = splitWidth ?? defaultSplitWidth()
  aiPanelLayout.split = on
}
watch([open, expanded], updateSplit)
splitMedia.addEventListener('change', updateSplit)

// 面板宽度由状态驱动（分栏时），分隔条拖拽实时调整
const panelStyle = computed(() =>
  aiPanelLayout.split ? { width: `${aiPanelLayout.width}px` } : undefined,
)

function startDrag(e: MouseEvent) {
  if (!aiPanelLayout.split) return
  e.preventDefault()
  aiPanelLayout.dragging = true
  document.body.style.userSelect = 'none' // 拖拽期间防正文被选中
  document.addEventListener('mousemove', onDrag)
  document.addEventListener('mouseup', endDrag)
}
function onDrag(e: MouseEvent) {
  // 面板右边距固定 24px，宽度 = 右缘 - 光标 x
  aiPanelLayout.width = clampWidth(window.innerWidth - 24 - e.clientX)
}
function endDrag() {
  aiPanelLayout.dragging = false
  document.body.style.userSelect = ''
  splitWidth = aiPanelLayout.width
  try {
    localStorage.setItem('ql:aiAskSplitWidth', String(aiPanelLayout.width))
  } catch {
    // 存储不可用：忽略
  }
  document.removeEventListener('mousemove', onDrag)
  document.removeEventListener('mouseup', endDrag)
}
function resetSplitWidth() {
  splitWidth = null
  try {
    localStorage.removeItem('ql:aiAskSplitWidth')
  } catch {
    // 存储不可用：忽略
  }
  aiPanelLayout.width = defaultSplitWidth()
}

// 对话消息：assistant 消息的 content 在流式期间持续追加
const messages = ref<ChatTurn[]>([])
const listRef = ref<HTMLElement | null>(null)
const inputRef = ref<HTMLTextAreaElement | null>(null)

const maxLen = 2000

// 空状态「建议问题」：点击即发送，降低提问门槛
const suggestions = ['用一句话概括本节核心', '结合真实数据举个例子', '讲解文中的公式', '和前面的内容有什么关系']
function askSuggestion(q: string) {
  input.value = q
  void send()
}

// ---------- 深度思考 & 引导式 & 模型选择 & 联网搜索（全局偏好，localStorage 持久化）----------
const deep = ref(localStorage.getItem('ql:aiAskDeep') === '1')
const guided = ref(localStorage.getItem('ql:aiAskGuide') === '1')
const model = ref(localStorage.getItem('ql:aiAskModel') || '') // '' = 默认（当前配置）
const models = ref<string[]>([])
const currentModel = ref('')
const web = ref(localStorage.getItem('ql:aiAskWeb') === '1')
const webSearchConfigured = ref(true) // 默认乐观；挂载后按设置页实际值修正
// 附加上下文（如代码沙箱代码与运行结果）：仅注入下一次发送，不进聊天历史
const pendingContext = ref('')

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
  try {
    const cfg = await fetchAISettings()
    webSearchConfigured.value = cfg.web_search_configured
  } catch {
    // 拉不到设置不阻塞
  }
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocClick)
  splitMedia.removeEventListener('change', updateSplit)
  document.removeEventListener('mousemove', onDrag)
  document.removeEventListener('mouseup', endDrag)
  document.body.style.userSelect = ''
  aiPanelLayout.split = false
  aiPanelLayout.dragging = false
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
function toggleGuide() {
  guided.value = !guided.value
  if (guided.value) localStorage.setItem('ql:aiAskGuide', '1')
  else localStorage.removeItem('ql:aiAskGuide')
}
function toggleWeb() {
  web.value = !web.value
  if (web.value) localStorage.setItem('ql:aiAskWeb', '1')
  else localStorage.removeItem('ql:aiAskWeb')
}

// 停止生成：中断当前流式请求（send 的 catch 会清理空气泡）
function stopGenerate() {
  abortCtrl.value?.abort()
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

/** 外部调用：打开面板并把选中文字作为问题预填（「选中问 AI」/「图表问 AI」/「代码问 AI」） */
function ask(prefill: string, context?: string) {
  open.value = true
  error.value = ''
  input.value = prefill
  pendingContext.value = context ?? '' // 附加上下文（如沙箱代码与运行结果），仅注入下一次发送
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

  // 联网搜索开启但未配置 Tavily key：本地拦截并提示，避免发了才报错
  if (web.value && !webSearchConfigured.value) {
    error.value = '联网搜索未配置：请先在「设置」页填写 Tavily API Key。'
    return
  }

  error.value = ''
  input.value = ''
  const question: ChatTurn = { role: 'user', content: text.slice(0, maxLen) }
  messages.value.push(question)
  messages.value.push({ role: 'assistant', content: '', guided: guided.value })

  thinking.value = true
  const ctrl = new AbortController()
  abortCtrl.value = ctrl
  await scrollToBottom()

  const history: ChatTurn[] = messages.value.slice(0, -1)
  // 附加上下文只在本次请求注入（沙箱代码问 AI），用完即清，避免后续轮次重复携带
  const ctx = pendingContext.value
  pendingContext.value = ''
  try {
    const result = await streamChat(
      {
        lesson_id: props.lessonId,
        section_index: props.sectionIndex,
        // 只传 role/content，sources 是 UI 数据不进模型上下文
        messages: history.map((m) => ({ role: m.role, content: m.content })),
        model: model.value || undefined,
        deep: deep.value,
        web_search: web.value,
        guided: guided.value,
        context: ctx || undefined,
      },
      (delta) => {
        const last = messages.value[messages.value.length - 1]
        if (last?.role === 'assistant') {
          last.content += delta
          void scrollToBottom()
        }
      },
      ctrl.signal,
      (sources) => {
        // 来源清单挂到最后一条 assistant 消息：渲染为回答下方「参考文献」
        const last = messages.value[messages.value.length - 1]
        if (last?.role === 'assistant') last.sources = sources
      },
    )
    if (result.error) {
      error.value = result.error
      // 保留空 assistant 消息前，先移除空条，避免留一个空气泡
      const last = messages.value[messages.value.length - 1]
      if (last?.role === 'assistant' && !last.content) messages.value.pop()
    }
  } catch (e) {
    // 用户主动停止/关闭面板（AbortError）静默；其余异常也提示，避免「没回复也没提示」
    const last = messages.value[messages.value.length - 1]
    if (last?.role === 'assistant' && !last.content) messages.value.pop()
    const aborted = e instanceof DOMException && e.name === 'AbortError'
    if (!aborted) {
      error.value = `请求异常：${e instanceof Error ? e.message : String(e)}`
    }
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
    <div
      v-if="open"
      class="ask-panel"
      :class="{ expanded, split: aiPanelLayout.split, dragging: aiPanelLayout.dragging }"
      :style="panelStyle"
    >
      <!-- 分栏分隔条：拖拽调整正文/面板比例，双击恢复默认 -->
      <div
        v-if="aiPanelLayout.split"
        class="split-drag"
        title="拖拽调整分栏 · 双击恢复默认"
        @mousedown="startDrag"
        @dblclick="resetSplitWidth"
      ></div>
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
          <p class="empty-sub">针对这个知识点提问，AI 导师会结合本节内容回答。<br />可开启「深度思考」深入分析，「引导式」启发思考，或「联网」检索外部实时信息。</p>
          <div class="sugg">
            <button v-for="q in suggestions" :key="q" class="sugg-chip" @click="askSuggestion(q)">{{ q }}</button>
          </div>
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
          <div v-else class="msg-ai-body">
            <div class="msg-meta">
              <span class="msg-role">AI 导师</span>
              <span v-if="m.guided" class="msg-badge guide">引导</span>
            </div>
            <div class="bubble bubble-md">
              <span v-if="m.content" v-html="renderBubble(m.content)"></span>
              <span v-else-if="thinking && i === messages.length - 1" class="typing">▍</span>
              <!-- 联网搜索来源：正文用 [1][2] 编号引用，这里列出可点击的参考文献 -->
              <div v-if="m.sources?.length" class="refs">
                <div class="refs-title"><Link2 :size="12" /> 参考文献</div>
                <ul class="refs-list">
                  <li v-for="(s, si) in m.sources" :key="si" class="refs-item">
                    <span class="refs-num">[{{ si + 1 }}]</span>
                    <a :href="s.url" target="_blank" rel="noreferrer" class="refs-link" :title="s.title">{{ s.title }}</a>
                    <span class="refs-host">{{ hostOf(s.url) }}</span>
                  </li>
                </ul>
              </div>
              <button v-if="m.content" class="copy-btn" title="复制回答" @click="copyMessage(m.content)"><Copy :size="13" /></button>
            </div>
          </div>
        </div>
      </div>

      <div v-if="error" class="msg-error">{{ error }}</div>

      <footer class="panel-input">
        <div class="input-row">
          <textarea
            ref="inputRef"
            v-model="input"
            class="input-box"
            :placeholder="thinking ? 'AI 思考中…' : '输入你的问题…'"
            :disabled="thinking"
            rows="2"
            @keydown.enter.exact.prevent="send"
          />
          <button
            v-if="thinking"
            class="send-btn stop"
            title="停止生成"
            @click="stopGenerate"
          >
            <Square :size="12" />
          </button>
          <button v-else class="send-btn" :disabled="!input.trim()" title="发送" @click="send">
            <Send :size="15" />
          </button>
        </div>
        <div class="toolbar">
          <button
            class="tb-btn"
            :class="{ on: deep }"
            :title="'深度思考：回答前先深入分析、分步推理'"
            @click="toggleDeep"
          >
            <Brain :size="13" />
            深度
          </button>
          <button
            class="tb-btn"
            :class="{ on: guided }"
            :title="'引导式：不直接给答案，先用提问引导你思考（苏格拉底式）'"
            @click="toggleGuide"
          >
            <HelpCircle :size="13" />
            引导
          </button>
          <button
            class="tb-btn"
            :class="{ on: web }"
            :title="webSearchConfigured ? '联网搜索：回答时检索外部实时信息并标注来源' : '未配置 Tavily Key（设置页填写）'"
            @click="toggleWeb"
          >
            <Globe :size="13" />
            联网
          </button>
          <span class="tb-spacer"></span>
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
  height: min(82vh, 680px);
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: width 0.2s ease, height 0.2s ease, top 0.2s ease;
}

/* 放大模式：四周对称留白（24px），避免上下不对称显得奇怪 */
.ask-panel.expanded {
  top: 24px;
  right: 24px;
  bottom: 24px;
  height: calc(100vh - 48px);
}

/* 放大但未进入分栏（屏幕 <1024px）：浮层适当加宽，避免 460px 长条 */
.ask-panel.expanded:not(.split) {
  width: min(540px, calc(100vw - 32px));
}

/* 分栏模式（放大 + 屏幕≥1024px）：面板与正文分割剩余空间，宽度由拖拽/状态驱动 */
.ask-panel.split {
  width: 480px; /* 兜底；实际宽度由 inline style（aiPanelLayout.width）覆盖 */
  top: 24px;
  height: calc(100vh - 48px);
  right: 24px;
  bottom: 24px;
}
/* 拖拽分隔条期间：宽度跟随光标实时更新，禁用过渡避免拖影 */
.ask-panel.dragging {
  transition: none;
}

/* 分隔条：位于面板左缘，拖拽调整分栏比例 */
.split-drag {
  position: absolute;
  left: 0; top: 0; bottom: 0;
  width: 8px;
  cursor: col-resize;
  z-index: 6;
}
.split-drag::before {
  content: '';
  position: absolute;
  left: 3px; top: 0; bottom: 0;
  width: 2px;
  background: var(--border);
  transition: background 0.15s;
}
.split-drag:hover::before { background: var(--primary); }

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
.sugg { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; margin-top: 12px; }
.sugg-chip {
  border: 1px solid var(--border);
  background: var(--bg-card);
  color: var(--text-2);
  font-size: 12px;
  padding: 5px 13px;
  border-radius: 999px;
  cursor: pointer;
  transition: all 0.15s;
}
.sugg-chip:hover { border-color: var(--primary); color: var(--primary); background: var(--primary-soft); }

.msg { display: flex; align-items: flex-start; gap: 8px; }
.msg-user { justify-content: flex-end; }
.msg-ai { justify-content: flex-start; }
.msg-ai-body {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
  max-width: 86%;
}
.msg-meta { display: flex; align-items: center; gap: 6px; padding-left: 2px; }
.msg-role { font-size: 11px; font-weight: 600; color: var(--text-3); }
.msg-badge {
  font-size: 10px;
  line-height: 1;
  padding: 2px 7px;
  border-radius: 999px;
  font-weight: 600;
}
.msg-badge.guide {
  color: #b45309;
  background: color-mix(in srgb, #f59e0b 16%, transparent);
  border: 1px solid color-mix(in srgb, #f59e0b 35%, transparent);
}
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
/* AI 气泡宽度由 msg-ai-body 上限控制，不再自身限宽 */
.msg-ai-body .bubble { max-width: 100%; }

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

/* 参考文献：正文 [n] 编号引用的来源清单，主流学术样式 */
.refs {
  margin-top: 10px;
  padding-top: 9px;
  border-top: 1px dashed var(--border);
}
.refs-title {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 11.5px;
  font-weight: 600;
  color: var(--text-3);
  margin-bottom: 6px;
}
.refs-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 5px; }
.refs-item {
  display: flex;
  align-items: baseline;
  gap: 6px;
  font-size: 12.5px;
  line-height: 1.5;
  min-width: 0;
}
.refs-num {
  flex-shrink: 0;
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-3);
}
.refs-link {
  color: var(--primary);
  text-decoration: none;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  min-width: 0;
}
.refs-link:hover { text-decoration: underline; }
.refs-host {
  flex-shrink: 0;
  font-size: 11px;
  color: var(--text-3);
  font-family: var(--font-mono);
}
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
  position: relative; /* 模型下拉弹层的定位上下文：锚定面板右下，避免小窗换行时被裁 */
  padding: 10px 14px 12px;
  border-top: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  gap: 8px;
}
/* 输入行：输入框 + 右侧独立发送按钮（按钮固定尺寸垂直居中，不随输入框高度拉伸） */
.input-row { display: flex; align-items: center; gap: 8px; }
.input-box {
  flex: 1;
  min-width: 0;
  resize: none;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-card);
  color: var(--text-1);
  padding: 9px 12px;
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
  flex-shrink: 0;
  width: 40px;
  height: 40px;
  border: none;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--primary), var(--primary-hover));
  color: #fff;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: opacity 0.15s, filter 0.15s, transform 0.15s;
}
.send-btn:hover:not(:disabled) { filter: brightness(1.08); }
.send-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.send-btn.stop { background: var(--danger, #dc2626); }
.send-btn.stop:hover:not(:disabled) { background: var(--danger, #dc2626); }

.toolbar { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; min-height: 26px; }
.tb-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: 1px solid var(--border);
  background: var(--bg-card);
  color: var(--text-2);
  font-size: 12px;
  padding: 3px 9px;
  border-radius: 999px;
  cursor: pointer;
  transition: all 0.15s;
  flex-shrink: 0;
}
.tb-btn:hover { border-color: var(--primary); color: var(--primary); }
.tb-btn.on {
  background: linear-gradient(135deg, var(--primary), var(--primary-hover));
  border-color: transparent;
  color: #fff;
}
.tb-spacer { flex: 1; }

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
  right: 14px; /* 锚定 footer 右缘（与输入框对齐），而不是按钮——小窗工具条换行时不被裁切 */
  bottom: calc(100% + 8px);
  width: 300px;
  max-width: 70vw;
  z-index: 10;
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
    height: min(82dvh, 680px);
  }
}
</style>
