<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { runCode, type ExecResult } from '@/api'
import { recordSandboxRun } from '@/stores/progress'

// 代码练习沙箱：提交 Python 代码到后端受限环境执行
// 可用：白名单库（numpy/pandas/matplotlib/math/statistics/random 等）
//     + get_daily(code, start, end) 个股日线 / get_index(indicator, start, end) 指数日收盘（只读真实行情）
//     + plt 画图 → 图形以 base64 PNG 内联显示在输出区
// 教学点：学习即动手——在真实数据上验证公式（官方口径与课程主线一致）
const props = defineProps<{
  params?: Record<string, unknown>
}>()

const DEFAULT_CODE = `# 茅台 2024 真实日线：官方口径计算核心指标（rf=2%）
import numpy as np
df = get_daily('sh600519', '2024-01-01', '2024-12-31')
ret = df['pct_chg'] / 100
cum = (1 + ret[1:]).prod() - 1                 # 复利连乘，不含首日
ann = (1 + cum) ** (252 / (len(ret) - 1)) - 1  # 几何年化
vol = ret[1:].std(ddof=1) * np.sqrt(252)       # 年化波动
nav = (1 + ret[1:]).cumprod() * 100
mdd = (nav / nav.cummax() - 1).min()           # 最大回撤
sharpe = (ann - 0.02) / vol
print(f'累计 {cum*100:.2f}% | 年化 {ann*100:.2f}% | 波动 {vol*100:.2f}%')
print(f'最大回撤 {mdd*100:.2f}% | 夏普 {sharpe:.2f}')
print('交易日数', len(df))`

const starter =
  typeof props.params?.code === 'string' && props.params.code
    ? (props.params.code as string)
    : DEFAULT_CODE

const expected =
  typeof props.params?.expected === 'string' && props.params.expected
    ? (props.params.expected as string)
    : ''

const lessonId =
  typeof props.params?.lesson_id === 'string' ? props.params.lesson_id : ''
const DRAFT_KEY = lessonId
  ? `quantlerning_sandbox_draft_${lessonId}`
  : 'quantlerning_sandbox_draft'

// 草稿：上次编辑的代码（刷新/切课不丢）；「重置」按钮清空
function loadDraft(): string | null {
  try {
    const raw = localStorage.getItem(DRAFT_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    return typeof parsed === 'string' && parsed.trim() ? parsed : null
  } catch {
    return null
  }
}

const code = ref(loadDraft() ?? starter)
const running = ref(false)
const errorLine = ref<number | null>(null)
const showExpected = ref(false)
const copied = ref(false)

// 草稿自动保存（防抖）
let saveTimer: ReturnType<typeof setTimeout> | undefined
watch(code, (v) => {
  clearTimeout(saveTimer)
  saveTimer = setTimeout(() => {
    try {
      localStorage.setItem(DRAFT_KEY, JSON.stringify(v))
    } catch {
      // 存储不可用：仅影响持久化
    }
  }, 400)
})

// 行号 gutter + 高亮层：与 textarea 同步滚动
const taRef = ref<HTMLTextAreaElement | null>(null)
const hlRef = ref<HTMLPreElement | null>(null)
const gutterRef = ref<HTMLDivElement | null>(null)
const lineCount = computed(() => code.value.replace(/\n$/, '').split('\n').length)

function syncScroll() {
  if (gutterRef.value && taRef.value) {
    gutterRef.value.scrollTop = taRef.value.scrollTop
  }
  if (hlRef.value && taRef.value) {
    hlRef.value.scrollTop = taRef.value.scrollTop
    hlRef.value.scrollLeft = taRef.value.scrollLeft
  }
}

const result = ref<ExecResult | null>(null)

async function run() {
  if (!code.value.trim() || running.value) return
  running.value = true
  result.value = null
  errorLine.value = null
  copied.value = false
  try {
    const res = await runCode(code.value)
    result.value = res
    const m = res.stderr.match(/第 (\d+) 行/)
    if (m) {
      errorLine.value = Number(m[1])
      nextTick(() => {
        const ta = taRef.value
        if (ta && errorLine.value) {
          ta.scrollTop = Math.max(0, errorLine.value - 4) * 20
          syncScroll()
        }
      })
    }
    recordSandboxRun(res.ok)
  } catch (e) {
    result.value = {
      ok: false,
      stdout: '',
      stderr: `请求失败：${e instanceof Error ? e.message : String(e)}`,
      duration_ms: 0,
      blocked: [],
      images: [],
    }
    recordSandboxRun(false)
  } finally {
    running.value = false
  }
}

function resetCode() {
  try {
    localStorage.removeItem(DRAFT_KEY)
  } catch {
    // 忽略
  }
  code.value = starter
  result.value = null
  errorLine.value = null
  copied.value = false
}

async function copyOutput() {
  if (!result.value?.stdout) return
  try {
    await navigator.clipboard.writeText(result.value.stdout)
    copied.value = true
    setTimeout(() => (copied.value = false), 1500)
  } catch {
    // 剪贴板不可用：静默
  }
}

function onKeydown(e: KeyboardEvent) {
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
    e.preventDefault()
    run()
  }
}

// ---------- 轻量 Python 语法高亮（pre 覆盖层，textarea 文字透明） ----------
const PY_KEYWORDS = new Set([
  'and', 'as', 'assert', 'async', 'await', 'break', 'class', 'continue',
  'def', 'del', 'elif', 'else', 'except', 'finally', 'for', 'from', 'global',
  'if', 'import', 'in', 'is', 'lambda', 'nonlocal', 'not', 'or', 'pass',
  'raise', 'return', 'try', 'while', 'with', 'yield',
])
const PY_BUILTINS = new Set([
  'True', 'False', 'None', 'print', 'len', 'range', 'abs', 'min', 'max',
  'sum', 'round', 'int', 'float', 'str', 'list', 'dict', 'set', 'tuple',
  'enumerate', 'zip', 'sorted', 'map', 'filter', 'type', 'isinstance', 'repr',
  'input', 'open', 'bool', 'pow', 'divmod',
])

function escHtml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function highlightPython(src: string): string {
  const re =
    /('''[\s\S]*?'''|"""[\s\S]*?"""|'[^'\n]*'|"[^"\n]*")|(#.*$)|\s+|(@\w+)|\b([A-Za-z_]\w*)\b|(\d+(?:\.\d+)?)/gm
  let out = ''
  let last = 0
  let m: RegExpExecArray | null
  while ((m = re.exec(src)) !== null) {
    out += escHtml(src.slice(last, m.index))
    const [, str, comment, ws, dec, word, num] = m
    if (str) out += `<span class="tok-s">${escHtml(str)}</span>`
    else if (comment) out += `<span class="tok-c">${escHtml(comment)}</span>`
    else if (ws) out += escHtml(ws)
    else if (dec) out += `<span class="tok-d">${escHtml(dec)}</span>`
    else if (word) {
      if (PY_KEYWORDS.has(word)) out += `<span class="tok-k">${escHtml(word)}</span>`
      else if (PY_BUILTINS.has(word)) out += `<span class="tok-b">${escHtml(word)}</span>`
      else out += escHtml(word)
    } else if (num) out += `<span class="tok-n">${escHtml(num)}</span>`
    last = m.index + m[0].length
  }
  out += escHtml(src.slice(last))
  return out
}

const highlightedHtml = computed(() => highlightPython(code.value))
</script>

<template>
  <div class="code-sandbox">
    <div class="sb-card">
      <!-- 头部：仿编辑器标签页 -->
      <div class="sb-header">
        <span class="sb-dots" aria-hidden="true">
          <i class="dot dot-red"></i>
          <i class="dot dot-yellow"></i>
          <i class="dot dot-green"></i>
        </span>
        <span class="sb-title">代码沙箱</span>
        <span class="sb-badge">Python · 白名单 · 真实行情</span>
      </div>

      <!-- 编辑区：行号 + 高亮层 + 输入框 -->
      <div class="editor">
        <div ref="gutterRef" class="gutter" aria-hidden="true">
          <div
            v-for="n in lineCount"
            :key="n"
            class="gutter-line"
            :class="{ err: n === errorLine }"
          >{{ n }}</div>
        </div>
        <div class="code-area">
          <pre ref="hlRef" class="code-hl" v-html="highlightedHtml" aria-hidden="true"></pre>
          <textarea
            ref="taRef"
            v-model="code"
            class="code-input"
            spellcheck="false"
            rows="9"
            wrap="off"
            placeholder="# 在这里写 Python 代码…"
            @scroll="syncScroll"
            @keydown="onKeydown"
          ></textarea>
        </div>
      </div>

      <!-- 工具栏 -->
      <div class="sb-toolbar">
        <button class="run-btn" :disabled="running || !code.trim()" @click="run">
          <span class="run-icon" aria-hidden="true">{{ running ? '◌' : '▶' }}</span>
          {{ running ? '运行中…' : '运行' }}
          <span class="run-shortcut">Ctrl+↵</span>
        </button>
        <button class="ghost-btn" :disabled="code === starter" @click="resetCode" title="回到起始代码">
          ↺ 重置
        </button>
        <button v-if="expected" class="ghost-btn" @click="showExpected = !showExpected">
          预期输出 {{ showExpected ? '▴' : '▾' }}
        </button>
        <span class="hint">
          可用 <code>get_daily(个股, 开始, 结束)</code> / <code>get_index(指数, 开始, 结束)</code>
          读取真实行情 · <code>plt</code> 可画图
        </span>
      </div>

      <!-- 预期输出（可折叠自检） -->
      <div v-if="showExpected && expected" class="expected">
        <div class="exp-head">预期输出（真实数据）</div>
        <pre class="exp-body">{{ expected }}</pre>
      </div>

      <!-- 输出面板 -->
      <div v-if="result" class="output">
        <div class="out-head">
          <span>输出</span>
          <span class="out-right">
            <button v-if="result.stdout" class="copy-btn" @click="copyOutput">
              {{ copied ? '已复制' : '复制' }}
            </button>
            <span class="out-ms">{{ result.duration_ms }} ms</span>
          </span>
        </div>
        <template v-if="result.blocked.length">
          <p class="out-blocked">⛔ 代码被安全过滤拦截：</p>
          <ul class="blocked-list">
            <li v-for="b in result.blocked" :key="b">{{ b }}</li>
          </ul>
        </template>
        <template v-else>
          <pre v-if="result.stdout" class="out-stdout">{{ result.stdout }}</pre>
          <pre v-if="result.stderr" class="out-stderr">{{ result.stderr }}</pre>
          <div v-if="result.images.length" class="out-images">
            <img
              v-for="(img, i) in result.images"
              :key="i"
              :src="`data:image/png;base64,${img}`"
              :alt="`输出图形 ${i + 1}`"
            />
          </div>
          <p v-if="!result.stdout && !result.stderr && !result.images.length" class="out-empty">
            （无输出）
          </p>
          <p class="out-meta" :class="{ ok: result.ok }">
            {{ result.ok ? '✓ 执行完成' : '✗ 执行失败' }}
          </p>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.code-sandbox {
  padding: 16px;
  /* 语法高亮配色：浅色/深色两套（跟随主题） */
  --tok-k: #7c3aed;
  --tok-s: #15803d;
  --tok-c: #94a3b8;
  --tok-n: #b45309;
  --tok-b: #1d4ed8;
  --tok-d: #9d174d;
}
[data-theme="dark"] .code-sandbox {
  --tok-k: #c792ea;
  --tok-s: #98c379;
  --tok-c: #6d7688;
  --tok-n: #d19a66;
  --tok-b: #61afef;
  --tok-d: #e5c07b;
}

/* 卡片 */
.sb-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

/* 头部 */
.sb-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 14px;
  background: var(--bg-hover);
  border-bottom: 1px solid var(--border);
}
.sb-dots { display: flex; gap: 5px; }
.dot { width: 10px; height: 10px; border-radius: 50%; display: block; }
.dot-red { background: #f87171; }
.dot-yellow { background: #fbbf24; }
.dot-green { background: #4ade80; }
.sb-title { font-size: 13px; font-weight: 600; color: var(--text-1); }
.sb-badge {
  margin-left: auto;
  font-size: 11px;
  color: var(--text-3);
  background: var(--bg-active);
  border: 1px solid var(--border);
  padding: 2px 9px;
  border-radius: 999px;
  white-space: nowrap;
}

/* 编辑区 */
.editor {
  display: flex;
  align-items: stretch;
  background: var(--bg-code);
}
.gutter {
  flex-shrink: 0;
  min-width: 42px;
  padding: 10px 8px;
  text-align: right;
  overflow: hidden;
  color: var(--text-3);
  user-select: none;
  font-family: var(--font-mono);
  font-size: 12.5px;
  line-height: 1.6;
  border-right: 1px solid var(--border);
}
.gutter-line { white-space: pre; }
.gutter-line.err {
  color: var(--danger);
  font-weight: 700;
  background: var(--danger-soft);
  border-radius: 3px;
}
.code-area {
  position: relative;
  flex: 1;
  min-width: 0;
}
.code-hl {
  position: absolute;
  inset: 0;
  margin: 0;
  padding: 10px 12px;
  overflow: hidden;
  color: var(--text-1);
  font-family: var(--font-mono);
  font-size: 12.5px;
  line-height: 1.6;
  white-space: pre;
  pointer-events: none;
  tab-size: 2;
}
.code-input {
  position: relative;
  width: 100%;
  min-height: 200px;
  font-family: var(--font-mono);
  font-size: 12.5px;
  line-height: 1.6;
  color: transparent;
  caret-color: var(--primary);
  background: transparent;
  border: none;
  padding: 10px 12px;
  resize: vertical;
  tab-size: 2;
  white-space: pre;
}
.code-input::placeholder { color: var(--text-3); }
.code-input:focus { outline: none; }
.code-input::selection { background: var(--primary-soft); }

/* 语法高亮 token */
.tok-k { color: var(--tok-k); font-weight: 600; }
.tok-s { color: var(--tok-s); }
.tok-c { color: var(--tok-c); font-style: italic; }
.tok-n { color: var(--tok-n); }
.tok-b { color: var(--tok-b); }
.tok-d { color: var(--tok-d); }

/* 工具栏 */
.sb-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-top: 1px solid var(--border);
  flex-wrap: wrap;
}
.run-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 16px;
  border: none;
  border-radius: var(--radius-sm);
  background: var(--primary);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  flex-shrink: 0;
  transition: background 0.15s;
}
.run-btn:hover:not(:disabled) { background: var(--primary-hover); }
.run-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.run-icon { font-size: 11px; }
.run-shortcut {
  font-size: 10.5px;
  opacity: 0.75;
  font-weight: 400;
  border: 1px solid rgba(255, 255, 255, 0.45);
  border-radius: 4px;
  padding: 1px 5px;
}
.ghost-btn {
  padding: 6px 12px;
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-sm);
  background: var(--bg-card);
  color: var(--text-2);
  font-size: 12.5px;
  cursor: pointer;
  flex-shrink: 0;
  transition: all 0.15s;
}
.ghost-btn:hover:not(:disabled) { color: var(--primary); border-color: var(--primary); }
.ghost-btn:disabled { opacity: 0.45; cursor: not-allowed; }
.hint { font-size: 11.5px; color: var(--text-3); line-height: 1.5; }
.hint code { font-family: var(--font-mono); font-size: 11px; }

/* 预期输出 */
.expected {
  border-top: 1px solid var(--border);
  background: var(--bg-hover);
}
.exp-head {
  padding: 6px 14px;
  font-size: 11.5px;
  color: var(--text-3);
  border-bottom: 1px solid var(--border);
}
.exp-body {
  margin: 0;
  padding: 10px 14px;
  white-space: pre-wrap;
  word-break: break-all;
  font-family: var(--font-mono);
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--text-2);
}

/* 输出面板 */
.output { border-top: 1px solid var(--border); }
.out-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 14px;
  font-size: 11.5px;
  color: var(--text-3);
  background: var(--bg-hover);
  border-bottom: 1px solid var(--border);
}
.out-right { display: inline-flex; align-items: center; gap: 10px; }
.copy-btn {
  border: none;
  background: transparent;
  color: var(--primary);
  font-size: 11.5px;
  cursor: pointer;
  padding: 0;
}
.copy-btn:hover { text-decoration: underline; }
.out-ms { font-variant-numeric: tabular-nums; }
.out-stdout,
.out-stderr {
  white-space: pre-wrap;
  word-break: break-all;
  font-family: var(--font-mono);
  font-size: 12.5px;
  line-height: 1.6;
  padding: 10px 14px;
  margin: 0;
  max-height: 260px;
  overflow: auto;
}
.out-stdout { color: var(--text-1); }
.out-stderr { color: var(--danger); background: var(--danger-soft); }
.out-images {
  padding: 10px 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  align-items: flex-start;
}
.out-images img {
  max-width: 100%;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: #fff;
}
.out-empty { padding: 10px 14px; color: var(--text-3); font-size: 12.5px; }
.out-blocked {
  color: var(--danger);
  font-size: 13px;
  padding: 10px 14px 0;
  margin: 0;
}
.blocked-list {
  margin: 0;
  padding: 4px 14px 10px 2.2em;
  color: var(--danger);
  font-size: 12.5px;
}
.out-meta {
  font-size: 12px;
  color: var(--text-3);
  padding: 0 14px 10px;
  margin: 8px 0 0;
}
.out-meta.ok { color: var(--success); }
</style>