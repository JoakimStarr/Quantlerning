<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, MarkLineComponent, MarkPointComponent } from 'echarts/components'
import katex from 'katex'
import { parseFunction, exprToLatex } from '@/utils/mathExpr'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent, MarkPointComponent])

// 数值积分演示：没有原函数时的办法
// 关键教学点不是「逼近」本身（那是定积分演示的内容），而是【方法间的精度对比】：
//   中点矩形 ≈ 梯形法（误差 O(h²)），辛普森法（误差 O(h⁴)）快两个数量级
// 因此本组件主打：
//   1) 同一 n 下三种方法的形状并排对比（谁贴曲线更紧）
//   2) 误差随 n 增大的收敛曲线（对数坐标 → 斜率就是收敛阶）
// 教学演示（函数为示意，非真实数据）

const props = defineProps<{
  params?: Record<string, unknown>
}>()

const DEFAULT_SRC = 'sin(x)'
const PRESETS = [DEFAULT_SRC, '1/(1+x^2)', 'x^2', 'x^3 - 3*x', 'exp(x)'] // sin/1/(1+x²) 无初等原函数 → 必须数值

const src = ref(typeof props.params?.fn === 'string' ? (props.params.fn as string) : DEFAULT_SRC)
const compiled = ref<(x: number) => number>(parseFunction(src.value) ?? parseFunction(DEFAULT_SRC)!)
const latex = ref(exprToLatex(src.value) ?? exprToLatex(DEFAULT_SRC) ?? '')
const error = ref('')

watch(src, (s) => {
  if (!s.trim()) return
  const f = parseFunction(s)
  if (f) {
    compiled.value = f
    latex.value = exprToLatex(s) ?? latex.value
    error.value = ''
  } else {
    error.value = '表达式无法解析，请检查（支持 x、|x|、+ - * / ^、括号，以及 sin/cos/tan/sqrt/log/ln/exp/abs）'
  }
})

const renderTex = (s: string) => katex.renderToString(s, { throwOnError: false, strict: false })
const presetLatex = (p: string) => renderTex(exprToLatex(p) ?? p)
const formulaHtml = computed(() => (latex.value ? renderTex(`f(x) = ${latex.value}`) : ''))

// 区间与分割数
const a = ref(typeof props.params?.a === 'number' ? (props.params.a as number) : 0)
const b = ref(typeof props.params?.b === 'number' ? (props.params.b as number) : 2)
const n = ref(typeof props.params?.n === 'number' ? (props.params.n as number) : 8)
const SLIDER_MIN = -3.2
const SLIDER_MAX = 3.2
const MAXN = 80

const viewMin = computed(() => Math.min(a.value, b.value) - (Math.abs(b.value - a.value) * 0.25 + 0.5))
const viewMax = computed(() => Math.max(a.value, b.value) + (Math.abs(b.value - a.value) * 0.25 + 0.5))

const k = computed(() => Math.max(1, Math.round(n.value)))
const lo = computed(() => Math.min(a.value, b.value))
const hi = computed(() => Math.max(a.value, b.value))
const sign = computed(() => (a.value <= b.value ? 1 : -1))

// 三种方法：中点矩形 / 梯形 / 辛普森
type Method = 'mid' | 'trap' | 'simp'
const METHOD_LABELS: Record<Method, string> = { mid: '中点矩形', trap: '梯形法', simp: '辛普森法' }
const METHOD_COLORS = computed<Record<Method, string>>(() => ({ mid: C.value.cyan, trap: C.value.warning, simp: C.value.violet }))
const METHODS: Method[] = ['mid', 'trap', 'simp']

// 当前高亮的方法（主图显示它的形状）
const focus = ref<Method>('trap')

const curve = computed<[number, number | null][]>(() => {
  const out: [number, number | null][] = []
  const N = 240
  for (let i = 0; i <= N; i++) {
    const x = viewMin.value + ((viewMax.value - viewMin.value) * i) / N
    const y = compiled.value(x)
    out.push([Number(x.toFixed(3)), Number.isFinite(y) ? Number(y.toFixed(4)) : null])
  }
  return out
})

const yRange = computed(() => {
  let min = 0
  let max = 0
  for (const [, y] of curve.value) {
    if (typeof y === 'number' && Number.isFinite(y)) {
      if (y < min) min = y
      if (y > max) max = y
    }
  }
  const pad = Math.max(0.5, (max - min) * 0.12)
  return { min: min - pad, max: max + pad }
})

// 真值：高精度梯形积分
function exactIntegral(f: (x: number) => number, x0: number, x1: number): number | null {
  const M = 20000
  const h = (x1 - x0) / M
  let s = 0
  for (let i = 0; i < M; i++) {
    const y1 = f(x0 + h * i)
    const y2 = f(x0 + h * (i + 1))
    if (!Number.isFinite(y1) || !Number.isFinite(y2)) return null
    s += ((y1 + y2) / 2) * h
  }
  return s
}
const exactSigned = computed<number | null>(() => {
  const e = exactIntegral(compiled.value, lo.value, hi.value)
  return e == null ? null : sign.value * e
})

// 指定方法、指定分割数下的近似和
function sumMethod(m: Method, nSplit: number): number | null {
  const h = (hi.value - lo.value) / nSplit
  let s = 0
  for (let i = 0; i < nSplit; i++) {
    const xl = lo.value + h * i
    const xr = xl + h
    const xm = (xl + xr) / 2
    let y: number
    if (m === 'mid') y = compiled.value(xm)
    else if (m === 'trap') y = (compiled.value(xl) + compiled.value(xr)) / 2
    else y = (compiled.value(xl) + 4 * compiled.value(xm) + compiled.value(xr)) / 6
    if (!Number.isFinite(y)) return null
    s += y * h
  }
  return sign.value * s
}

// 各方法当前结果（显示用）
const perMethod = computed(() =>
  METHODS.map((m) => {
    const s = sumMethod(m, k.value)
    const exact = exactSigned.value
    return {
      m,
      sum: s,
      err: s != null && exact != null ? Math.abs(s - exact) : null,
      rel: s != null && exact != null ? Math.abs(s - exact) / Math.abs(exact || 1) : null,
    }
  }),
)
const bestRel = computed(() => {
  const vals = perMethod.value.filter((p) => p.rel != null).map((p) => p.rel as number)
  return vals.length ? Math.min(...vals) : null
})

// 过三点抛物线采样（辛普森形状用）
function sampleParabola(x0: number, y0: number, x1: number, y1: number, x2: number, y2: number, nS = 12): [number, number][] {
  const denom = (x0 - x1) * (x0 - x2) * (x1 - x2)
  const A = (x2 * (y1 - y0) + x1 * (y0 - y2) + x0 * (y2 - y1)) / denom
  const B = (x2 * x2 * (y0 - y1) + x1 * x1 * (y2 - y0) + x0 * x0 * (y1 - y2)) / denom
  const C = (x1 * x2 * (x1 - x2) * y0 + x2 * x0 * (x2 - x0) * y1 + x0 * x1 * (x0 - x1) * y2) / denom
  const pts: [number, number][] = []
  for (let i = 0; i <= nS; i++) {
    const t = i / nS
    const x = x0 + (x2 - x0) * t
    pts.push([x, A * x * x + B * x + C])
  }
  return pts
}

function hexToRgba(hex: string, alpha: number): string {
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

// 某一方法的上边界折线
function boundaryFor(m: Method): [number, number | null][] {
  const out: [number, number | null][] = []
  const h = (hi.value - lo.value) / k.value
  const push = (x: number, y: number) => out.push([Number(x.toFixed(3)), Number(y.toFixed(4))])
  if (m === 'trap') {
    for (let i = 0; i <= k.value; i++) {
      const y = compiled.value(lo.value + h * i)
      if (!Number.isFinite(y)) {
        out.push([NaN, NaN])
        continue
      }
      push(lo.value + h * i, y)
    }
  } else if (m === 'simp') {
    for (let i = 0; i < k.value; i++) {
      const xl = lo.value + h * i
      const xr = xl + h
      const xm = (xl + xr) / 2
      const yl = compiled.value(xl)
      const ym = compiled.value(xm)
      const yr = compiled.value(xr)
      if (!Number.isFinite(yl) || !Number.isFinite(ym) || !Number.isFinite(yr)) {
        out.push([NaN, NaN])
        continue
      }
      for (const [x, y] of sampleParabola(xl, yl, xm, ym, xr, yr)) push(x, y)
    }
  } else {
    for (let i = 0; i < k.value; i++) {
      const y = compiled.value(lo.value + h * (i + 0.5))
      if (!Number.isFinite(y)) {
        out.push([NaN, NaN])
        continue
      }
      push(lo.value + h * i, y)
      push(lo.value + h * (i + 1), y)
    }
  }
  return out
}

const mainOption = computed(() => {
  const color = METHOD_COLORS.value[focus.value]
  return {
    animation: false,
    grid: { left: 52, right: 20, top: 30, bottom: 36 },
    tooltip: {
      trigger: 'axis',
      formatter: (ps: any[]) => {
        const p = ps[0]
        if (!p || !Array.isArray(p.value)) return ''
        const y = p.value[1]
        if (y == null) return ''
        return `x = ${Number(p.value[0]).toFixed(2)}<br/>f(x) = ${Number(y).toFixed(4)}`
      },
    },
    legend: { top: 0, textStyle: { fontSize: 11 }, data: ['f(x)', '近似形状'] },
    xAxis: { type: 'value', name: 'x', nameLocation: 'middle', nameGap: 26, min: viewMin.value, max: viewMax.value, axisLabel: { fontSize: 11 } },
    yAxis: { type: 'value', name: 'f(x)', nameLocation: 'middle', nameGap: 40, min: yRange.value.min, max: yRange.value.max, axisLabel: { fontSize: 11 } },
    series: [
      {
        type: 'line',
        name: '近似形状',
        data: boundaryFor(focus.value),
        smooth: false,
        symbol: 'none',
        lineStyle: { width: 1.8, color },
        itemStyle: { color },
        areaStyle: { color: hexToRgba(color, 0.3), origin: 0 },
        z: 2,
      },
      {
        type: 'line',
        name: 'f(x)',
        data: curve.value,
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 2.5, color: C.value.primary },
        itemStyle: { color: C.value.primary },
        markLine: {
          silent: true,
          symbol: 'none',
          data: [
            { xAxis: a.value, name: 'a', lineStyle: { color: C.value.danger, type: 'dashed', width: 1.2 }, label: { formatter: 'a', position: 'insideEndTop', fontSize: 10, color: C.value.danger } },
            { xAxis: b.value, name: 'b', lineStyle: { color: C.value.danger, type: 'dashed', width: 1.2 }, label: { formatter: 'b', position: 'insideEndTop', fontSize: 10, color: C.value.danger } },
          ],
        },
        z: 3,
      },
    ],
  }
})

// 收敛曲线（对数坐标）：三种方法的 |误差| 随 n 增大，斜率即收敛阶
const convergeSeries = computed(() => {
  const ns: number[] = []
  for (let m = 2; m <= MAXN; m += Math.max(1, Math.round(m / 8))) ns.push(m)
  return METHODS.map((m) => {
    const pts: [number, number | null][] = []
    for (const nn of ns) {
      const s = sumMethod(m, nn)
      const e = exactSigned.value
      if (s == null || e == null) {
        pts.push([nn, null])
        continue
      }
      const err = Math.abs(s - e)
      pts.push([nn, err > 0 ? Number(err.toExponential(6)) : null])
    }
    return { m, data: pts }
  })
})

const convergeOption = computed(() => ({
  animation: false,
  grid: { left: 58, right: 24, top: 26, bottom: 36 },
  tooltip: {
    trigger: 'axis',
    formatter: (ps: any[]) => {
      const lines = ps.map((p: any) => {
        const v = p.value
        if (!Array.isArray(v) || v[1] == null) return ''
        return `${METHOD_LABELS[p.seriesName as Method]}：|误差| = ${Number(v[1]).toExponential(3)}`
      })
      if (!lines.length) return ''
      const n = ps[0]?.value?.[0]
      return `n = ${n}<br/>${lines.filter(Boolean).join('<br/>')}`
    },
  },
  legend: { top: 0, textStyle: { fontSize: 11 } },
  xAxis: {
    type: 'log',
    name: 'n',
    nameLocation: 'middle',
    nameGap: 26,
    min: 2,
    max: MAXN,
    logBase: 2,
    axisLabel: { fontSize: 10, formatter: (v: number) => `${v}` },
  },
  yAxis: {
    type: 'log',
    name: '|误差|',
    nameLocation: 'middle',
    nameGap: 44,
    axisLabel: { fontSize: 10, formatter: (v: number) => (v >= 10 ? `${v}` : v.toExponential(0)) },
  },
  series: convergeSeries.value.map(({ m, data }) => ({
    type: 'line',
    name: METHOD_LABELS[m],
    data,
    symbol: 'circle',
    symbolSize: 4,
    lineStyle: { width: 2, color: METHOD_COLORS.value[m] },
    itemStyle: { color: METHOD_COLORS.value[m] },
    z: 3,
  })),
}))

// 收敛阶说明（LaTeX）
const orderHtml = computed(() =>
  renderTex('\\text{中点/梯形: }O(h^2)\\quad\\text{辛普森: }O(h^4),\\quad h=(b-a)/n'),
)
</script>

<template>
  <div class="numint-sim">
    <!-- 函数输入 -->
    <div class="formula-box">
      <div class="formula-row">
        <span class="f-label">f(x) =</span>
        <input v-model="src" class="f-input" spellcheck="false" placeholder="如 sin(x)、1/(1+x^2)、x^2" />
      </div>
      <div class="presets">
        <button v-for="p in PRESETS" :key="p" class="preset" :class="{ active: src === p }" @click="src = p">
          <span v-html="presetLatex(p)"></span>
        </button>
      </div>
      <p v-if="error" class="f-error">{{ error }}</p>
    </div>

    <div v-if="formulaHtml" class="formula-bar" v-html="formulaHtml"></div>

    <!-- 方法选择（主图高亮显示该方法的形状） -->
    <div class="method-row">
      <button v-for="m in METHODS" :key="m" class="method-btn" :class="{ active: focus === m }" @click="focus = m">
        <span class="dot" :style="{ background: METHOD_COLORS[m] }"></span>{{ METHOD_LABELS[m] }}
      </button>
    </div>

    <!-- 主图：当前方法的形状贴曲线多紧 -->
    <ThemedChart class="chart main-chart" :option="mainOption" autoresize />

    <!-- 同一 n 下三种方法对比 -->
    <div class="compare-row">
      <div v-for="p in perMethod" :key="p.m" class="compare-box" :class="{ best: p.rel != null && bestRel != null && p.rel === bestRel, focus: focus === p.m }">
        <span class="compare-label" :style="{ color: METHOD_COLORS[p.m] }">{{ METHOD_LABELS[p.m] }}</span>
        <strong class="compare-sum">{{ p.sum == null ? '—' : p.sum.toFixed(5) }}</strong>
        <span class="compare-err">误差 {{ p.err == null ? '—' : p.err.toExponential(2) }}</span>
        <span class="compare-rel">相对 {{ p.rel == null ? '—' : (p.rel * 100).toFixed(3) }}%</span>
      </div>
    </div>

    <!-- 收敛曲线：误差随 n 增大（对数坐标，斜率=收敛阶） -->
    <div class="converge-head">
      <span class="converge-title">误差随 n 增大如何下降（对数坐标）</span>
      <span class="order-html" v-html="orderHtml"></span>
    </div>
    <ThemedChart class="chart converge-chart" :option="convergeOption" autoresize />

    <div class="controls">
      <div class="control-row">
        <span class="control-label">下限 a</span>
        <input v-model.number="a" type="range" :min="SLIDER_MIN" :max="SLIDER_MAX" step="0.1" class="slider" />
        <span class="control-value">{{ a.toFixed(1) }}</span>
      </div>
      <div class="control-row">
        <span class="control-label">上限 b</span>
        <input v-model.number="b" type="range" :min="SLIDER_MIN" :max="SLIDER_MAX" step="0.1" class="slider" />
        <span class="control-value">{{ b.toFixed(1) }}</span>
      </div>
      <div class="control-row">
        <span class="control-label">分割数 n</span>
        <input v-model.number="n" type="range" min="1" :max="MAXN" step="1" class="slider" />
        <span class="control-value">{{ k }}</span>
      </div>
      <p class="hint">
        没有原函数时只能「以直代曲」求和。三种方法的精度差很远：<strong>中点矩形和梯形法</strong>误差 ~ O(h²)（n 翻倍误差约 /4），
        <strong>辛普森法</strong>用抛物线拟合，误差 ~ O(h⁴)（n 翻倍误差约 /16）——所以在对数坐标下辛普森的线更陡。
        上图中绿色虚线是真值，对比框里标出了各方法在<strong>同一个 n</strong> 下的误差，误差最小的方法会高亮。
      </p>
    </div>
  </div>
</template>

<style scoped>
.numint-sim { padding: 16px; }
.formula-box { margin-bottom: 8px; }
.formula-row { display: flex; align-items: center; gap: 8px; }
.f-label { font-size: 13px; font-weight: 600; color: var(--text-2); flex-shrink: 0; font-family: var(--font-mono); }
.f-input {
  flex: 1; font-family: var(--font-mono); font-size: 13.5px; color: var(--text-1);
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
  text-align: center; font-size: 14px; padding: 6px 10px; margin-bottom: 6px;
  background: var(--bg-hover); border-radius: var(--radius-sm); overflow-x: auto;
}
.method-row { display: flex; gap: 8px; margin: 8px 0; }
.method-btn {
  flex: 1; display: flex; align-items: center; justify-content: center; gap: 6px;
  font-size: 12.5px; padding: 6px 8px; border-radius: var(--radius-sm);
  border: 1px solid var(--border); background: var(--bg-card); color: var(--text-2); cursor: pointer;
}
.method-btn .dot { width: 9px; height: 9px; border-radius: 50%; display: inline-block; }
.method-btn.active { border-color: var(--primary); color: var(--primary); background: var(--primary-soft); font-weight: 600; }
.chart { width: 100%; }
.main-chart { height: 270px; }
.converge-chart { height: 190px; }
.compare-row { display: flex; gap: 8px; margin: 8px 0; }
.compare-box {
  flex: 1; padding: 8px 6px; border-radius: var(--radius-sm); background: var(--bg-hover);
  text-align: center; display: flex; flex-direction: column; gap: 2px; border: 1px solid transparent;
}
.compare-box.focus { border-color: var(--primary); }
.compare-box.best { box-shadow: 0 0 0 1px var(--success, #16a34a) inset; }
.compare-label { font-size: 12px; font-weight: 600; }
.compare-sum { font-size: 14px; color: var(--text-1); }
.compare-err { font-size: 11px; color: var(--danger, #dc2626); }
.compare-rel { font-size: 11px; color: var(--text-3); }
.converge-head { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; margin: 4px 0; flex-wrap: wrap; }
.converge-title { font-size: 12.5px; font-weight: 600; color: var(--text-2); }
.order-html { font-size: 12px; color: var(--text-3); }
.controls { margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border); display: flex; flex-direction: column; gap: 10px; }
.control-row { display: flex; align-items: center; gap: 12px; }
.control-label { width: 80px; font-size: 13px; color: var(--text-2); flex-shrink: 0; }
.slider { flex: 1; accent-color: var(--primary); cursor: pointer; }
.control-value { width: 48px; font-size: 13px; font-weight: 600; color: var(--primary); text-align: right; flex-shrink: 0; }
.hint { margin-top: 8px; font-size: 12px; color: var(--text-3); line-height: 1.7; }
</style>
