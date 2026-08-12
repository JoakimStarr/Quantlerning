<script setup lang="ts">
import { ref } from 'vue'
import { runCode } from '@/api'
import { recordSandboxRun } from '@/stores/progress'

// 代码练习沙箱：提交 Python 代码到后端受限环境执行
// 可用：白名单库（numpy/pandas/math/statistics/random 等）+ get_daily(code, start, end) 只读真实行情
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

const code = ref(starter)
const running = ref(false)
const result = ref<{
  ok: boolean
  stdout: string
  stderr: string
  duration_ms: number
  blocked: string[]
} | null>(null)

async function run() {
  if (!code.value.trim() || running.value) return
  running.value = true
  result.value = null
  try {
    result.value = await runCode(code.value)
    recordSandboxRun() // 记一次代码运行（驱动学习统计）
  } catch (e) {
    result.value = {
      ok: false,
      stdout: '',
      stderr: `请求失败：${e instanceof Error ? e.message : String(e)}`,
      duration_ms: 0,
      blocked: [],
    }
  } finally {
    running.value = false
  }
}
</script>

<template>
  <div class="code-sandbox">
    <textarea
      v-model="code"
      class="code-input"
      spellcheck="false"
      rows="9"
      placeholder="# 在这里写 Python 代码…"
    ></textarea>
    <div class="toolbar">
      <button class="run-btn" :disabled="running || !code.trim()" @click="run">
        {{ running ? '运行中…' : '▶ 运行' }}
      </button>
      <span class="hint">Python 沙箱 · 白名单库（numpy/pandas/math/statistics/random…）+ <code>get_daily(代码, 开始, 结束)</code> 只读真实行情</span>
    </div>

    <div v-if="result" class="output">
      <template v-if="result.blocked.length">
        <p class="out-blocked">⛔ 代码被安全过滤拦截：</p>
        <ul class="blocked-list">
          <li v-for="b in result.blocked" :key="b">{{ b }}</li>
        </ul>
      </template>
      <template v-else>
        <pre v-if="result.stdout" class="out-stdout">{{ result.stdout }}</pre>
        <pre v-if="result.stderr" class="out-stderr">{{ result.stderr }}</pre>
        <p class="out-meta" :class="{ ok: result.ok }">
          {{ result.ok ? '✓ 执行完成' : '✗ 执行失败' }} · {{ result.duration_ms }} ms
        </p>
      </template>
    </div>
  </div>
</template>

<style scoped>
.code-sandbox { padding: 14px; }
.code-input {
  width: 100%;
  min-height: 200px;
  font-family: var(--font-mono);
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--text-1);
  background: #0f1420;
  color: #e6e9ef;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 10px 12px;
  resize: vertical;
  tab-size: 2;
}
.code-input:focus { outline: none; border-color: var(--primary); }
.toolbar { display: flex; align-items: center; gap: 12px; margin: 10px 0 6px; flex-wrap: wrap; }
.run-btn {
  padding: 6px 18px;
  border: none;
  border-radius: var(--radius-sm);
  background: var(--primary);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  flex-shrink: 0;
}
.run-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.hint { font-size: 12px; color: var(--text-3); line-height: 1.6; }
.hint code { font-family: var(--font-mono); font-size: 11.5px; }
.output { margin-top: 8px; }
.out-stdout, .out-stderr {
  white-space: pre-wrap;
  word-break: break-all;
  font-family: var(--font-mono);
  font-size: 12.5px;
  line-height: 1.6;
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  background: var(--bg-hover);
  margin: 4px 0;
  max-height: 260px;
  overflow: auto;
}
.out-stdout { color: var(--text-1); }
.out-stderr { color: var(--danger, #dc2626); }
.out-blocked { color: var(--danger, #dc2626); font-size: 13px; margin: 4px 0; }
.blocked-list { margin: 0 0 4px; padding-left: 1.3em; color: var(--danger, #dc2626); font-size: 12.5px; }
.blocked-list li { margin-bottom: 2px; }
.out-meta { font-size: 12px; color: var(--text-3); margin: 6px 0 0; }
.out-meta.ok { color: var(--success); }
</style>
