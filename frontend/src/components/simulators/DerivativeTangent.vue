<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, MarkPointComponent } from 'echarts/components'
import katex from 'katex'
import 'katex/dist/katex.min.css'
import { parseFunction, exprToLatex } from '@/utils/mathExpr'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent, MarkPointComponent])

// 导数切线演示：可输入任意一元函数 f(x)，显示曲线 + 在 x0 处的切线
// 导数用数值差商计算（即正文的极限定义），因此任意输入函数都能演示
// 教学演示（函数为示意，非真实数据）

const props = defineProps<{
  params?: Record<string, unknown>
}>()

const DEFAULT_SRC = 'x^3/3 - x^2 - x + 3'
const PRESETS = [DEFAULT_SRC, 'x^2', 'sin(x)', 'exp(-x^2)', '1/(1+exp(-x))']

// 公式输入：非法时保留上一次可用的函数，仅提示错误
const src = ref(typeof props.params?.fn === 'string' ? (props.params.fn as string) : DEFAULT_SRC)
const compiled = ref<(x: number) => number>(parseFunction(src.value) ?? parseFunction(DEFAULT_SRC)!)
const latex = ref(exprToLatex(src.value) ?? exprToLatex(DEFAULT_SRC) ?? '') // 当前函数的 LaTeX（供公式展示）
const error = ref('')

watch(src, (s) => {
  if (!s.trim()) return // 清空输入时保留上一次函数
  const f = parseFunction(s)
  if (f) {
    compiled.value = f
    latex.value = exprToLatex(s) ?? latex.value
    error.value = ''
  } else {
    error.value = '表达式无法解析，请检查（支持 x、|x| 绝对值、+ - * / ^、括号，以及 sin/cos/tan/sqrt/log/ln/exp/abs）'
  }
})

const renderTex = (s: string) => katex.renderToString(s, { throwOnError: false, strict: false })
// 预设按钮以 LaTeX 展示
const presetLatex = (p: string) => renderTex(exprToLatex(p) ?? p)
// 当前函数 f(x) 公式
const formulaHtml = computed(() => (latex.value ? renderTex(`f(x) = ${latex.value}`) : ''))

const x0 = ref(typeof props.params?.x0 === 'number' ? props.params.x0 : -1)
const xMin = -3.2
const xMax = 3.2
const N = 240

// 曲线采样；非有限值（如 sqrt(x) 的负半轴）挖成空档
const curve = computed<[number, number | null][]>(() => {
  const out: [number, number | null][] = []
  for (let i = 0; i <= N; i++) {
    const x = xMin + ((xMax - xMin) * i) / N
    const y = compiled.value(x)
    out.push([Number(x.toFixed(3)), Number.isFinite(y) ? Number(y.toFixed(4)) : null])
  }
  return out
})

const h = 1e-4
const y0 = computed(() => compiled.value(x0.value))

type TangentState = 'ok' | 'undefined' | 'cusp'
// 判断该点是否有切线：函数是否定义、左右导数是否一致（尖点不可导）
const tangentState = computed<TangentState>(() => {
  const y0v = y0.value
  if (!Number.isFinite(y0v)) return 'undefined'
  const y1 = compiled.value(x0.value + h)
  const y2 = compiled.value(x0.value - h)
  if (!Number.isFinite(y1) || !Number.isFinite(y2)) return 'undefined'
  const fwd = (y1 - y0v) / h // 右导数
  const bwd = (y0v - y2) / h // 左导数
  if (Math.abs(fwd - bwd) > 1e-3 * Math.max(1, Math.abs(fwd), Math.abs(bwd))) return 'cusp'
  return 'ok'
})

// 中心差商（比前向差商更准）；尖点/无定义时无导数
const slope = computed(() => {
  if (tangentState.value !== 'ok') return NaN
  return (compiled.value(x0.value + h) - compiled.value(x0.value - h)) / (2 * h)
})

// 曲线的可见 y 范围（用于裁剪切线，避免陡峭函数的切线把 y 轴撑开）
const curveYRange = computed(() => {
  let min = Infinity
  let max = -Infinity
  for (const [, y] of curve.value) {
    if (typeof y === 'number' && Number.isFinite(y)) {
      if (y < min) min = y
      if (y > max) max = y
    }
  }
  if (!Number.isFinite(min) || min === max) return null
  return { min, max }
})

// 过 (x0, f(x0)) 的切线 y = m·x + b，其中截距 b = y0 − m·x0；裁剪到曲线可见范围
const tangent = computed<[number, number][] | null>(() => {
  const m = slope.value
  const range = curveYRange.value
  if (!Number.isFinite(m) || !Number.isFinite(y0.value) || !range) return null
  const b = y0.value - m * x0.value // 切线截距（此前误用 y0 导致切线不经过切点）

  const xFor = (y: number) => (y - b) / m
  let lo: number
  let hi: number
  if (m === 0) {
    lo = xMin
    hi = xMax
  } else {
    const xs = [xFor(range.min), xFor(range.max)]
      .filter((x) => Number.isFinite(x))
      .sort((a, b2) => a - b2)
    if (xs.length < 2) return null
    lo = Math.max(xMin, xs[0])
    hi = Math.min(xMax, xs[1])
  }
  if (hi <= lo) return null
  return [
    [Number(lo.toFixed(3)), Number((m * lo + b).toFixed(4))],
    [Number(hi.toFixed(3)), Number((m * hi + b).toFixed(4))],
  ]
})

const option = computed(() => {
  const m = slope.value
  const rising = m >= 0
  const series: any[] = [
    {
      name: 'f(x)',
      type: 'line',
      data: curve.value,
      smooth: true,
      symbol: 'none',
      lineStyle: { width: 2.5, color: '#2563eb' },
      itemStyle: { color: '#2563eb' },
      ...(Number.isFinite(y0.value)
        ? {
            markPoint: {
              symbol: 'pin',
              symbolSize: 30,
              label: { fontSize: 9 },
              data: [{ name: '切点', coord: [x0.value, y0.value], itemStyle: { color: '#d97706' } }],
            },
          }
        : {}),
    },
  ]
  if (tangent.value) {
    series.push({
      name: '切线',
      type: 'line',
      data: tangent.value,
      symbol: 'none',
      lineStyle: { width: 1.8, color: rising ? '#16a34a' : '#dc2626', type: 'dashed' },
      itemStyle: { color: rising ? '#16a34a' : '#dc2626' },
    })
  }
  return {
    animation: true,
    grid: { left: 55, right: 20, top: 36, bottom: 40 },
    tooltip: {
      trigger: 'axis',
      formatter: (ps: any[]) => {
        const p = ps[0]
        if (!p || !Array.isArray(p.value)) return ''
        const x = p.value[0]
        const y = p.value[1]
        if (y == null) return ''
        return `x = ${Number(x).toFixed(2)}<br/>f(x) = ${Number(y).toFixed(3)}`
      },
    },
    legend: { top: 0, textStyle: { fontSize: 11 } },
    xAxis: { type: 'value', name: 'x', nameLocation: 'middle', nameGap: 28, min: xMin, max: xMax, axisLabel: { fontSize: 11 } },
    yAxis: { type: 'value', name: 'f(x)', nameLocation: 'middle', nameGap: 40, axisLabel: { fontSize: 11 } },
    series,
  }
})

const slopeText = computed(() => (Number.isFinite(slope.value) ? slope.value.toFixed(2) : '—'))
const y0Text = computed(() => (Number.isFinite(y0.value) ? y0.value.toFixed(2) : '—'))

// 切线方程以 LaTeX 完整展示（截距式 y = mx + b）
const tangentLatex = computed(() => {
  const m = slope.value
  const b = y0.value
  if (!Number.isFinite(m) || !Number.isFinite(b)) return ''
  const intercept = b - m * x0.value
  const sign = intercept >= 0 ? '+' : '-'
  return `y = ${m.toFixed(2)}x ${sign} ${Math.abs(intercept).toFixed(2)}`
})
const tangentHtml = computed(() => (tangentLatex.value ? renderTex(tangentLatex.value) : ''))
</script>

<template>
  <div class="derivative-sim">
    <!-- 函数输入 -->
    <div class="formula-box">
      <div class="formula-row">
        <span class="f-label">f(x) =</span>
        <input
          v-model="src"
          class="f-input"
          spellcheck="false"
          placeholder="如 x^2、sin(x)、|x|、x^3/3 - x^2 - x + 3"
        />
      </div>
      <div class="presets">
        <button
          v-for="p in PRESETS"
          :key="p"
          class="preset"
          :class="{ active: src === p }"
          @click="src = p"
        >
          <span v-html="presetLatex(p)"></span>
        </button>
      </div>
      <p v-if="error" class="f-error">{{ error }}</p>
    </div>

    <!-- 当前函数公式（katex 渲染） -->
    <div v-if="formulaHtml" class="formula-bar" v-html="formulaHtml"></div>

    <VChart class="chart" :option="option" autoresize />

    <div class="controls">
      <div class="control-row">
        <span class="control-label">切点 x₀</span>
        <input v-model.number="x0" type="range" :min="xMin" :max="xMax" step="0.1" class="slider" />
        <span class="control-value">{{ x0.toFixed(1) }}</span>
      </div>
      <div class="result-row">
        <div class="result-box">
          <span class="muted">斜率 f′(x₀)（差商）</span>
          <strong :class="slope >= 0 ? 'num-green' : 'num-red'">{{ slopeText }}</strong>
        </div>
        <div class="result-box">
          <span class="muted">f(x₀)</span>
          <strong>{{ y0Text }}</strong>
        </div>
      </div>
      <div v-if="tangentHtml" class="tangent-line">
        <span class="muted">切线：</span><span v-html="tangentHtml"></span>
      </div>
      <div v-if="tangentState !== 'ok'" class="tangent-notice">
        <template v-if="tangentState === 'undefined'">
          f(x₀) 无定义（该点不在函数定义域内，如 sqrt(x) 的负数处、1/x 的 0 处），此处没有切线。
        </template>
        <template v-else>
          该点是尖点/折点——左导数与右导数不一致（如 |x| 在 0 处），导数不存在，因此没有切线。
        </template>
      </div>
      <p class="hint">
        拖动切点，观察切线斜率随 x₀ 变化。斜率 &gt; 0 时曲线在此处上升（绿色切线），
        &lt; 0 时下降（红色切线）。导数用差商 (f(x+h)−f(x−h))/2h 数值计算，因此任意输入函数都能演示；
        在局部极值点附近斜率变号——这是「一阶条件」的几何含义。
      </p>
    </div>
  </div>
</template>

<style scoped>
.derivative-sim { padding: 16px; }

.formula-box { margin-bottom: 8px; }
.formula-row { display: flex; align-items: center; gap: 8px; }
.f-label { font-size: 13px; font-weight: 600; color: var(--text-2); flex-shrink: 0; font-family: var(--font-mono); }
.f-input {
  flex: 1;
  font-family: var(--font-mono);
  font-size: 13.5px;
  color: var(--text-1);
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 7px 10px;
}
.f-input:focus { outline: none; border-color: var(--primary); }
.presets { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.preset {
  border: 1px solid var(--border);
  background: var(--bg-card);
  color: var(--text-2);
  font-size: 11.5px;
  font-family: var(--font-mono);
  padding: 2px 8px;
  border-radius: 999px;
  cursor: pointer;
}
.preset:hover { border-color: var(--primary); color: var(--primary); }
.preset.active { background: var(--primary-soft); border-color: var(--primary); color: var(--primary); }
.f-error { margin: 8px 0 0; font-size: 12px; color: var(--danger, #dc2626); }
.formula-bar {
  text-align: center;
  font-size: 14px;
  padding: 6px 10px;
  margin-bottom: 6px;
  background: var(--bg-hover);
  border-radius: var(--radius-sm);
  overflow-x: auto;
}
.tangent-line {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  font-size: 13px;
  padding: 4px 10px;
  background: var(--bg-hover);
  border-radius: var(--radius-sm);
}
.tangent-line .katex { font-size: 1.05em; }
.tangent-notice {
  font-size: 12.5px;
  line-height: 1.7;
  color: var(--danger, #dc2626);
  background: color-mix(in srgb, var(--danger, #dc2626) 8%, transparent);
  border-radius: var(--radius-sm);
  padding: 8px 12px;
}

.chart { height: 340px; }
.controls { margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border); display: flex; flex-direction: column; gap: 10px; }
.control-row { display: flex; align-items: center; gap: 12px; }
.control-label { width: 88px; font-size: 13px; color: var(--text-2); flex-shrink: 0; }
.slider { flex: 1; accent-color: var(--primary); cursor: pointer; }
.control-value { width: 56px; font-size: 13px; font-weight: 600; color: var(--primary); text-align: right; flex-shrink: 0; }
.result-row { display: flex; gap: 10px; margin-top: 8px; }
.result-box { flex: 1; padding: 8px 10px; border-radius: var(--radius-sm); background: var(--bg-hover); text-align: center; display: flex; flex-direction: column; gap: 2px; }
.result-box strong { font-size: 16px; }
.num-green { color: #16a34a; }
.num-red { color: #dc2626; }
.muted { font-size: 12px; color: var(--text-3); }
.hint { margin-top: 8px; font-size: 12px; color: var(--text-3); line-height: 1.7; }
</style>
