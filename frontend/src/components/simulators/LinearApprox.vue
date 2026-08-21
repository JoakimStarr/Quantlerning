<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import katex from 'katex'
import { parseFunction, exprToLatex } from '@/utils/mathExpr'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent])

// 微分：线性近似。f(x0+dx) ≈ f(x0) + f'(x0)·dx
// 显示真实变化 Δy 与线性近似 dy 两条竖线段，dx 越小误差越小
// 教学演示（函数为示意，非真实数据）

const props = defineProps<{
  params?: Record<string, unknown>
}>()

const DEFAULT_SRC = 'x^2'
const PRESETS = [DEFAULT_SRC, 'x^3/3 - x^2 - x + 3', 'sin(x)', 'exp(x)']

const src = ref(typeof props.params?.fn === 'string' ? (props.params.fn as string) : DEFAULT_SRC)
const compiled = ref<(x: number) => number>(parseFunction(src.value) ?? parseFunction(DEFAULT_SRC)!)
const latex = ref(exprToLatex(src.value) ?? '')
const error = ref('')

const x0 = ref(typeof props.params?.x0 === 'number' ? props.params.x0 : 1)
const dx = ref(1.5)

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
const formulaHtml = computed(() => (latex.value ? renderTex(`f(x) = ${latex.value}`) : ''))

const SLIDER_MIN = -3.2
const SLIDER_MAX = 3.2
const N = 240
const h = 1e-4

const y0 = computed(() => compiled.value(x0.value))
const m = computed(() => (compiled.value(x0.value + h) - compiled.value(x0.value - h)) / (2 * h))
const x1 = computed(() => x0.value + dx.value)
const dyVal = computed(() => m.value * dx.value)
const dyTrue = computed(() => compiled.value(x1.value) - y0.value)
const err = computed(() => Math.abs(dyTrue.value - dyVal.value))

const hasTangent = computed(() => Number.isFinite(y0.value) && Number.isFinite(m.value) && Number.isFinite(dyTrue.value))

// 图表 x 范围动态扩展：保证 x1（竖线段位置）始终在可视区内
const xMin = computed(() => Math.min(SLIDER_MIN, x1.value - 0.8))
const xMax = computed(() => Math.max(SLIDER_MAX, x1.value + 0.8))

const curve = computed<[number, number | null][]>(() => {
  const out: [number, number | null][] = []
  for (let i = 0; i <= N; i++) {
    const x = xMin.value + ((xMax.value - xMin.value) * i) / N
    const y = compiled.value(x)
    out.push([Number(x.toFixed(3)), Number.isFinite(y) ? Number(y.toFixed(4)) : null])
  }
  return out
})

// 切线（裁剪到曲线可见 y 范围）
const curveYRange = computed(() => {
  let mn = Infinity
  let mx = -Infinity
  for (const [, y] of curve.value) {
    if (typeof y === 'number' && Number.isFinite(y)) {
      if (y < mn) mn = y
      if (y > mx) mx = y
    }
  }
  if (!Number.isFinite(mn) || mn === mx) return null
  return { min: mn, max: mx }
})
const tangent = computed<[number, number][] | null>(() => {
  if (!hasTangent.value) return null
  const b = y0.value - m.value * x0.value
  const range = curveYRange.value
  if (!range) return null
  const xFor = (y: number) => (y - b) / m.value
  let lo: number
  let hi: number
  if (m.value === 0) {
    lo = xMin.value
    hi = xMax.value
  } else {
    const xs = [xFor(range.min), xFor(range.max)].filter(Number.isFinite).sort((a, b2) => a - b2)
    if (xs.length < 2) return null
    lo = Math.max(xMin.value, xs[0])
    hi = Math.min(xMax.value, xs[1])
  }
  if (hi <= lo) return null
  return [
    [Number(lo.toFixed(3)), Number((m.value * lo + b).toFixed(4))],
    [Number(hi.toFixed(3)), Number((m.value * hi + b).toFixed(4))],
  ]
})

// 竖线段端点裁剪到曲线可见范围，避免撑开 y 轴
function clipY(seg: [number, number][], range: { min: number; max: number }): [number, number][] {
  const yA = Math.max(range.min, Math.min(range.max, seg[0][1]))
  const yB = Math.max(range.min, Math.min(range.max, seg[1][1]))
  return [
    [seg[0][0], yA],
    [seg[1][0], yB],
  ]
}

// 基准点 (x1, f(x0))，及从 x0 到 x1 的水平引导线（dx）
const baseY = computed(() => (hasTangent.value ? y0.value : NaN))
const baseHoriz = computed<[number, number][] | null>(() =>
  hasTangent.value ? [[x0.value, y0.value], [x1.value, y0.value]] : null,
)
const dySeg = computed<[number, number][] | null>(() =>
  hasTangent.value && curveYRange.value
    ? clipY([[x1.value, baseY.value], [x1.value, baseY.value + dyVal.value]], curveYRange.value)
    : null,
)
const dyTrueSeg = computed<[number, number][] | null>(() =>
  hasTangent.value && curveYRange.value
    ? clipY([[x1.value, baseY.value], [x1.value, baseY.value + dyTrue.value]], curveYRange.value)
    : null,
)

const option = computed(() => {
  const series: any[] = [
    {
      name: 'f(x)',
      type: 'line',
      data: curve.value,
      smooth: true,
      symbol: 'none',
      lineStyle: { width: 2.5, color: C.value.primary },
      itemStyle: { color: C.value.primary },
      z: 2,
    },
  ]
  if (tangent.value) {
    series.push({
      name: `切线（dy 所在直线）`,
      type: 'line',
      data: tangent.value,
      symbol: 'none',
      lineStyle: { width: 1.8, color: C.value.warning, type: 'dashed' },
      itemStyle: { color: C.value.warning },
      z: 3,
    })
  }
  if (baseHoriz.value) {
    series.push({
      name: 'dx（水平基线）',
      type: 'line',
      data: baseHoriz.value,
      symbol: 'none',
      lineStyle: { width: 1.5, color: C.value.slate, type: 'dotted' },
      itemStyle: { color: C.value.slate },
      z: 2,
    })
  }
  if (dyTrueSeg.value) {
    series.push({
      name: 'Δy（真实变化）',
      type: 'line',
      data: dyTrueSeg.value,
      symbol: 'none',
      lineStyle: { width: 3, color: dyTrue.value >= 0 ? C.value.success : C.value.danger },
      itemStyle: { color: dyTrue.value >= 0 ? C.value.success : C.value.danger },
      z: 5,
    })
  }
  if (dySeg.value) {
    series.push({
      name: 'dy（线性近似）',
      type: 'line',
      data: dySeg.value,
      symbol: 'none',
      lineStyle: { width: 3, color: C.value.primary },
      itemStyle: { color: C.value.primary },
      z: 4,
    })
  }
  return {
    animation: false,
    grid: { left: 55, right: 20, top: 36, bottom: 42 },
    tooltip: {
      trigger: 'axis',
      formatter: (ps: any[]) => {
        const p = ps[0]
        if (!p || !Array.isArray(p.value)) return ''
        const y = p.value[1]
        if (y == null) return ''
        return `x = ${Number(p.value[0]).toFixed(2)}<br/>${p.seriesName} = ${Number(y).toFixed(4)}`
      },
    },
    legend: { top: 0, textStyle: { fontSize: 10.5 } },
    xAxis: { type: 'value', name: 'x', nameLocation: 'middle', nameGap: 28, min: xMin.value, max: xMax.value, axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', name: 'f(x)', nameLocation: 'middle', nameGap: 40, scale: true, axisLabel: { fontSize: 10 } },
    series,
  }
})

const fmt2 = (v: number) => (Number.isFinite(v) ? v.toFixed(3) : '—')
</script>

<template>
  <div class="linear-approx">
    <div class="formula-box">
      <div class="formula-row">
        <span class="f-label">f(x) =</span>
        <input v-model="src" class="f-input" spellcheck="false" placeholder="如 x^2、sin(x)、x^3/3 - x^2 - x + 3" />
      </div>
      <div class="presets">
        <button v-for="p in PRESETS" :key="p" class="preset" :class="{ active: src === p }" @click="src = p">
          <span v-html="presetLatex(p)"></span>
        </button>
      </div>
      <p v-if="error" class="f-error">{{ error }}</p>
    </div>

    <div class="formula-bar" v-html="formulaHtml"></div>

    <ThemedChart class="chart" :option="option" autoresize />

    <div class="controls">
      <div class="control-row">
        <span class="control-label">x₀</span>
        <input v-model.number="x0" type="range" :min="SLIDER_MIN" :max="SLIDER_MAX" step="0.1" class="slider" />
        <span class="control-value">{{ x0.toFixed(1) }}</span>
      </div>
      <div class="control-row">
        <span class="control-label">dx</span>
        <input v-model.number="dx" type="range" min="0.05" max="3" step="0.05" class="slider" />
        <span class="control-value">{{ dx.toFixed(2) }}</span>
      </div>
      <div class="result-row">
        <div class="result-box">
          <span class="muted">Δy 真实变化</span>
          <strong>{{ fmt2(dyTrue) }}</strong>
        </div>
        <div class="result-box">
          <span class="muted">dy = f′(x₀)·dx</span>
          <strong>{{ fmt2(dyVal) }}</strong>
        </div>
        <div class="result-box">
          <span class="muted">误差 |Δy − dy|</span>
          <strong>{{ fmt2(err) }}</strong>
        </div>
      </div>
      <p class="hint">
        灰色水平虚线是 dx，绿色竖线段是真实变化 Δy = f(x₀+dx) − f(x₀)，蓝色是线性近似 dy = f′(x₀)·dx。
        <strong>dx 越小，蓝色越贴近绿色</strong>——这就是「用切线代替曲线」的线性近似：小步长下误差可以忽略。
      </p>
    </div>
  </div>
</template>

<style scoped>
.linear-approx { padding: 16px; }
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
.control-label { width: 40px; font-size: 12.5px; color: var(--text-2); flex-shrink: 0; }
.slider { flex: 1; accent-color: var(--primary); cursor: pointer; }
.control-value { width: 46px; font-size: 12.5px; font-weight: 600; color: var(--primary); text-align: right; flex-shrink: 0; }
.result-row { display: flex; gap: 8px; margin-top: 8px; }
.result-box { flex: 1; padding: 8px 6px; border-radius: var(--radius-sm); background: var(--bg-hover); text-align: center; display: flex; flex-direction: column; gap: 2px; }
.result-box strong { font-size: 14px; }
.muted { font-size: 12px; color: var(--text-3); }
.hint { margin-top: 8px; font-size: 12px; color: var(--text-3); line-height: 1.7; }
</style>
