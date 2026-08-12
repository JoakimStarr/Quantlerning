<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, MarkPointComponent } from 'echarts/components'
import katex from 'katex'
import 'katex/dist/katex.min.css'
import { parseFunction, exprToLatex, taylorCoefficients } from '@/utils/mathExpr'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent, MarkPointComponent])

// 泰勒展开逼近：用符号微分算 f 在 a 处的泰勒多项式，逐阶看它在展开点附近越贴越紧
// 教学点：低阶近似在展开点附近好、离得远差；阶数越高吻合范围越宽
// 教学演示（函数为示意，非真实数据）

const props = defineProps<{
  params?: Record<string, unknown>
}>()

const DEFAULT_SRC = 'sin(x)'
const PRESETS = [DEFAULT_SRC, 'exp(x)', 'cos(x)', 'x^3/3 - x^2 - x + 3']

const src = ref(typeof props.params?.fn === 'string' ? (props.params.fn as string) : DEFAULT_SRC)
const compiled = ref<(x: number) => number>(parseFunction(src.value) ?? parseFunction(DEFAULT_SRC)!)
const latex = ref(exprToLatex(src.value) ?? '')
const error = ref('')

const a = ref(typeof props.params?.a === 'number' ? props.params.a : 0) // 展开点
const order = ref(3) // 泰勒阶数

watch(src, (s) => {
  if (!s.trim()) return
  const f = parseFunction(s)
  if (f) {
    compiled.value = f
    latex.value = exprToLatex(s) ?? latex.value
    error.value = ''
  } else {
    error.value = '表达式无法解析（支持 x、|x|、+ - * / ^、括号，以及 sin/cos/tan/sqrt/log/ln/exp/abs）'
  }
})

const renderTex = (s: string) => katex.renderToString(s, { throwOnError: false, strict: false })
const presetLatex = (p: string) => renderTex(exprToLatex(p) ?? p)

const N = 240
const xMin = computed(() => a.value - 3.5)
const xMax = computed(() => a.value + 3.5)

// 泰勒系数 c_k = f⁽ᵏ⁾(a)/k!
const coeffs = computed(() => taylorCoefficients(src.value, a.value, 6).coeffs)

// 泰勒多项式 P_n(x) = Σ c_k (x-a)^k
const poly = computed<(x: number) => number>(() => {
  const c = coeffs.value
  const n = order.value
  const aa = a.value
  return (x: number) => {
    let s = 0
    let dx = 1
    for (let k = 0; k <= n; k++) {
      s += c[k] * dx
      dx *= x - aa
    }
    return s
  }
})

const fCurve = computed<[number, number | null][]>(() => {
  const out: [number, number | null][] = []
  for (let i = 0; i <= N; i++) {
    const x = xMin.value + ((xMax.value - xMin.value) * i) / N
    const y = compiled.value(x)
    out.push([Number(x.toFixed(3)), Number.isFinite(y) ? Number(y.toFixed(4)) : null])
  }
  return out
})

const polyCurve = computed<[number, number][]>(() => {
  const p = poly.value
  const out: [number, number][] = []
  for (let i = 0; i <= N; i++) {
    const x = xMin.value + ((xMax.value - xMin.value) * i) / N
    const y = p(x)
    out.push([Number(x.toFixed(3)), Number.isFinite(y) ? Number(y.toFixed(4)) : NaN])
  }
  return out
})

// 多项式公式 LaTeX
const polyLatex = computed(() => {
  const c = coeffs.value
  const n = order.value
  const aa = a.value
  const terms: string[] = []
  const fmt = (v: number) => {
    if (v === 0) return '0'
    const r = Math.abs(v) < 1e-4 ? 0 : Number(v.toFixed(4))
    return r === 0 ? '0' : String(r)
  }
  for (let k = 0; k <= n; k++) {
    const ck = fmt(c[k])
    if (ck === '0') continue
    let term: string
    if (k === 0) term = ck
    else if (k === 1) term = `${ck}(x ${aa >= 0 ? '-' : '+'} ${Math.abs(aa)})`
    else term = `${ck}(x ${aa >= 0 ? '-' : '+'} ${Math.abs(aa)})^{${k}}`
    terms.push(term)
  }
  const rhs = terms.length ? terms.join(' + ') : '0'
  return `P_{${n}}(x) = ${rhs}`.replace(/\+ -/g, '- ')
})

const polyHtml = computed(() => (polyLatex.value ? renderTex(polyLatex.value) : ''))

const option = computed(() => ({
  animation: false,
  grid: { left: 55, right: 20, top: 36, bottom: 42 },
  tooltip: {
    trigger: 'axis',
    formatter: (ps: any[]) => {
      const p = ps[0]
      if (!p || !Array.isArray(p.value)) return ''
      const x = p.value[0]
      const y = p.value[1]
      if (y == null || Number.isNaN(y)) return ''
      return `x = ${Number(x).toFixed(2)}<br/>${p.seriesName} = ${Number(y).toFixed(4)}`
    },
  },
  legend: { top: 0, textStyle: { fontSize: 11 } },
  xAxis: { type: 'value', name: 'x', nameLocation: 'middle', nameGap: 28, min: xMin.value, max: xMax.value, axisLabel: { fontSize: 10 } },
  yAxis: { type: 'value', name: 'f(x)', nameLocation: 'middle', nameGap: 40, scale: true, axisLabel: { fontSize: 10 } },
  series: [
    {
      name: 'f(x)',
      type: 'line',
      data: fCurve.value,
      smooth: true,
      symbol: 'none',
      lineStyle: { width: 2.5, color: '#2563eb' },
      itemStyle: { color: '#2563eb' },
      markPoint: {
        symbol: 'pin',
        symbolSize: 26,
        label: { fontSize: 9, formatter: '展开点' },
        data: [{ coord: [a.value, compiled.value(a.value)], itemStyle: { color: '#d97706' } }],
      },
    },
    {
      name: `泰勒多项式 P₍${order.value}₎`,
      type: 'line',
      data: polyCurve.value,
      smooth: true,
      symbol: 'none',
      lineStyle: { width: 2, color: '#d97706', type: 'dashed' },
      itemStyle: { color: '#d97706' },
    },
  ],
}))
</script>

<template>
  <div class="taylor-series">
    <div class="formula-box">
      <div class="formula-row">
        <span class="f-label">f(x) =</span>
        <input v-model="src" class="f-input" spellcheck="false" placeholder="如 sin(x)、exp(x)、x^3/3 - x^2 - x + 3" />
      </div>
      <div class="presets">
        <button v-for="p in PRESETS" :key="p" class="preset" :class="{ active: src === p }" @click="src = p">
          <span v-html="presetLatex(p)"></span>
        </button>
      </div>
      <p v-if="error" class="f-error">{{ error }}</p>
    </div>

    <div class="formula-bar" v-html="polyHtml"></div>

    <VChart class="chart" :option="option" autoresize />

    <div class="controls">
      <div class="control-row">
        <span class="control-label">展开点 a</span>
        <input v-model.number="a" type="range" min="-3" max="3" step="0.1" class="slider" />
        <span class="control-value">{{ a.toFixed(1) }}</span>
      </div>
      <div class="control-row">
        <span class="control-label">阶数 n</span>
        <input v-model.number="order" type="range" min="0" max="6" step="1" class="slider" />
        <span class="control-value">{{ order }}</span>
      </div>
      <p class="hint">
        阶数越高，多项式在展开点附近与 f(x) 吻合越好（曲线几乎重合）；离展开点越远误差越大。
        注意观察 n=0 是常数、n=1 是切线（对应微分），n=2 起捕捉弯曲。
      </p>
    </div>
  </div>
</template>

<style scoped>
.taylor-series { padding: 16px; }
.formula-box { margin-bottom: 8px; }
.formula-row { display: flex; align-items: center; gap: 8px; }
.f-label { font-size: 13px; font-weight: 600; color: var(--text-2); flex-shrink: 0; font-family: var(--font-mono); }
.f-input {
  flex: 1; font-family: var(--font-mono); font-size: 13px; color: var(--text-1);
  background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 7px 10px;
}
.f-input:focus { outline: none; border-color: var(--primary); }
.presets { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.preset {
  border: 1px solid var(--border); background: var(--bg-card); color: var(--text-2);
  font-size: 11.5px; font-family: var(--font-mono); padding: 2px 8px; border-radius: 999px; cursor: pointer;
}
.preset:hover { border-color: var(--primary); color: var(--primary); }
.preset.active { background: var(--primary-soft); border-color: var(--primary); color: var(--primary); }
.f-error { margin: 8px 0 0; font-size: 12px; color: var(--danger, #dc2626); }
.formula-bar {
  text-align: center; font-size: 13.5px; padding: 6px 10px; margin-bottom: 6px;
  background: var(--bg-hover); border-radius: var(--radius-sm); overflow-x: auto;
}
.chart { height: 330px; }
.controls { margin-top: 10px; padding-top: 10px; border-top: 1px solid var(--border); display: flex; flex-direction: column; gap: 8px; }
.control-row { display: flex; align-items: center; gap: 12px; }
.control-label { width: 76px; font-size: 12.5px; color: var(--text-2); flex-shrink: 0; }
.slider { flex: 1; accent-color: var(--primary); cursor: pointer; }
.control-value { width: 40px; font-size: 12.5px; font-weight: 600; color: var(--primary); text-align: right; flex-shrink: 0; }
.hint { margin-top: 8px; font-size: 12px; color: var(--text-3); line-height: 1.7; }
</style>
