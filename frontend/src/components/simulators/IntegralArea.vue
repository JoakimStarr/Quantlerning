<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, MarkLineComponent, MarkPointComponent } from 'echarts/components'
import katex from 'katex'
import 'katex/dist/katex.min.css'
import { parseFunction, exprToLatex } from '@/utils/mathExpr'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent, MarkPointComponent])

// 定积分演示：分割 → 求和 → 取极限
// 主图：曲线 + 近似形状（左/右/中点矩形、梯形、辛普森抛物线）+ 分割线（只在面积范围内）
// 下方收敛曲线展示 S_n 随 n 逼近真值
// 教学演示（函数为示意，非真实数据）

const props = defineProps<{
  params?: Record<string, unknown>
}>()

const DEFAULT_SRC = 'x^2'
const PRESETS = [DEFAULT_SRC, 'x^3 - 3*x', 'sin(x)', 'sqrt(x)']

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
const MAXN = 60 // 收敛曲线的最大分割数

// 近似方法
type Method = 'left' | 'right' | 'mid' | 'trap' | 'simp'
const method = ref<Method>(typeof props.params?.method === 'string' ? (props.params.method as Method) : 'left')

const METHOD_LABELS: Record<Method, string> = {
  left: '左端点',
  right: '右端点',
  mid: '中点',
  trap: '梯形法',
  simp: '辛普森法',
}
const METHOD_COLORS: Record<Method, string> = {
  left: '#2563eb',
  right: '#0ea5e9',
  mid: '#0891b2',
  trap: '#d97706',
  simp: '#7c3aed',
}

// 主图视口：围绕区间 [a,b]，留一点曲线弯曲的上下文
const viewMin = computed(() => Math.min(a.value, b.value) - (Math.abs(b.value - a.value) * 0.25 + 0.5))
const viewMax = computed(() => Math.max(a.value, b.value) + (Math.abs(b.value - a.value) * 0.25 + 0.5))

const k = computed(() => Math.max(1, Math.round(n.value)))
const lo = computed(() => Math.min(a.value, b.value))
const hi = computed(() => Math.max(a.value, b.value))
const sign = computed(() => (a.value <= b.value ? 1 : -1))

// 播放：n 从 1 增到 MAXN（演示「取极限」）
const playing = ref(false)
let playTimer: number | undefined
function togglePlay() {
  if (playing.value) {
    stopPlay()
    return
  }
  playing.value = true
  n.value = 1
  playTimer = window.setInterval(() => {
    if (n.value >= MAXN) stopPlay()
    else n.value += 1
  }, 90)
}
function stopPlay() {
  playing.value = false
  if (playTimer) {
    window.clearInterval(playTimer)
    playTimer = undefined
  }
}
onBeforeUnmount(stopPlay)

// 曲线采样
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

// 主图 y 范围：包含曲线、0（形状底部）与形状顶部，留白
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

// 第 m 个分割下的近似和（m 个等宽子区间）
function sumN(m: number): number | null {
  const h = (hi.value - lo.value) / m
  let s = 0
  for (let i = 0; i < m; i++) {
    const xl = lo.value + h * i
    const xr = xl + h
    const xm = (xl + xr) / 2
    let y: number
    switch (method.value) {
      case 'left':
        y = compiled.value(xl)
        break
      case 'right':
        y = compiled.value(xr)
        break
      case 'mid':
        y = compiled.value(xm)
        break
      case 'trap':
        y = (compiled.value(xl) + compiled.value(xr)) / 2
        break
      case 'simp':
        y = (compiled.value(xl) + 4 * compiled.value(xm) + compiled.value(xr)) / 6
        break
    }
    if (!Number.isFinite(y)) return null
    s += y * h
  }
  return sign.value * s
}

const riemann = computed<number | null>(() => sumN(k.value))

// 真值：高精度梯形积分（当作「取极限」的极限）
function trapExact(f: (x: number) => number, x0: number, x1: number): number | null {
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
  const e = trapExact(compiled.value, lo.value, hi.value)
  return e == null ? null : sign.value * e
})

const errText = computed(() => {
  if (riemann.value == null || exactSigned.value == null) return '—'
  return (Math.abs(riemann.value - exactSigned.value) / Math.abs(exactSigned.value || 1)).toFixed(4)
})

// 过三点 (x0,y0),(x1,y1),(x2,y2) 的抛物线采样点（辛普森近似形状用）
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

// 近似形状的上边界（折线/阶梯/抛物线），配合 areaStyle 从 0 填充成闭合形状
const boundaryData = computed<[number, number | null][]>(() => {
  const out: [number, number | null][] = []
  const h = (hi.value - lo.value) / k.value
  const push = (x: number, y: number) => {
    out.push([Number(x.toFixed(3)), Number(y.toFixed(4))])
  }
  if (method.value === 'trap') {
    for (let i = 0; i <= k.value; i++) {
      const y = compiled.value(lo.value + h * i)
      if (!Number.isFinite(y)) {
        out.push([NaN, NaN])
        continue
      }
      push(lo.value + h * i, y)
    }
  } else if (method.value === 'simp') {
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
    // 阶梯：左/右/中点矩形
    const sample = (i: number) => {
      const xl = lo.value + h * i
      const xr = xl + h
      if (method.value === 'left') return compiled.value(xl)
      if (method.value === 'right') return compiled.value(xr)
      return compiled.value((xl + xr) / 2)
    }
    for (let i = 0; i < k.value; i++) {
      const y = sample(i)
      if (!Number.isFinite(y)) {
        out.push([NaN, NaN])
        continue
      }
      push(lo.value + h * i, y)
      push(lo.value + h * (i + 1), y)
    }
  }
  return out
})

// 分割线：只在面积范围内（从 y=0 到曲线上端），不延伸整幅图
const partitionSegs = computed<[number, number | null][]>(() => {
  const out: [number, number | null][] = []
  const h = (hi.value - lo.value) / k.value
  for (let i = 0; i <= k.value; i++) {
    const x = lo.value + h * i
    const y = compiled.value(x)
    if (!Number.isFinite(y)) {
      out.push([NaN, NaN])
      continue
    }
    out.push([Number(x.toFixed(3)), 0])
    out.push([Number(x.toFixed(3)), Number(y.toFixed(4))])
    out.push([NaN, NaN]) // 断开，只画竖线
  }
  return out
})

const mainOption = computed(() => {
  const color = METHOD_COLORS[method.value]
  // [lo, hi] 内的真实曲线（淡色填充，提示真值区域）
  const areaData: [number, number | null][] = []
  const N = 120
  for (let i = 0; i <= N; i++) {
    const x = lo.value + ((hi.value - lo.value) * i) / N
    const y = compiled.value(x)
    areaData.push([Number(x.toFixed(3)), Number.isFinite(y) ? Number(y.toFixed(4)) : null])
  }
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
        name: '曲线下真值区域',
        data: areaData,
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 0, opacity: 0 },
        areaStyle: { color: hexToRgba(color, 0.07), origin: 0 },
        silent: true,
        z: 1,
      },
      {
        type: 'line',
        name: '近似形状',
        data: boundaryData.value,
        smooth: false,
        symbol: 'none',
        lineStyle: { width: 1.6, color },
        itemStyle: { color },
        areaStyle: { color: hexToRgba(color, 0.3), origin: 0 },
        z: 2,
      },
      {
        type: 'line',
        name: '分割线',
        data: partitionSegs.value,
        symbol: 'none',
        lineStyle: { width: 1, color: '#94a3b8', type: 'dashed', opacity: 0.6 },
        silent: true,
        z: 1,
      },
      {
        type: 'line',
        name: 'f(x)',
        data: curve.value,
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 2.5, color: '#2563eb' },
        itemStyle: { color: '#2563eb' },
        markLine: {
          silent: true,
          symbol: 'none',
          data: [
            { xAxis: a.value, name: 'a', lineStyle: { color: '#dc2626', type: 'dashed', width: 1.2 }, label: { formatter: 'a', position: 'insideEndTop', fontSize: 10, color: '#dc2626' } },
            { xAxis: b.value, name: 'b', lineStyle: { color: '#dc2626', type: 'dashed', width: 1.2 }, label: { formatter: 'b', position: 'insideEndTop', fontSize: 10, color: '#dc2626' } },
          ],
        },
        z: 3,
      },
    ],
  }
})

// 收敛曲线：S_n 随 n 从 1 到 MAXN 的变化（取极限）
const convergeData = computed<[number, number | null][]>(() => {
  const out: [number, number | null][] = []
  for (let m = 1; m <= MAXN; m++) {
    const s = sumN(m)
    out.push([m, s == null ? null : Number(s.toFixed(6))])
  }
  return out
})

const convergeOption = computed(() => {
  const exact = exactSigned.value
  const methodColor = METHOD_COLORS[method.value]
  return {
    animation: false,
    grid: { left: 52, right: 20, top: 28, bottom: 34 },
    tooltip: {
      trigger: 'axis',
      formatter: (ps: any[]) => {
        const p = ps[0]
        if (!p || !Array.isArray(p.value)) return ''
        const v = p.value[1]
        if (v == null) return ''
        return `n = ${Number(p.value[0])}<br/>S_n = ${Number(v).toFixed(5)}`
      },
    },
    legend: { top: 0, textStyle: { fontSize: 11 }, data: ['S_n'] },
    xAxis: { type: 'value', name: 'n', nameLocation: 'middle', nameGap: 24, min: 1, max: MAXN, axisLabel: { fontSize: 11 } },
    yAxis: { type: 'value', scale: true, axisLabel: { fontSize: 11 } },
    series: [
      {
        type: 'line',
        name: 'S_n',
        data: convergeData.value,
        symbol: 'none',
        lineStyle: { width: 2, color: methodColor },
        itemStyle: { color: methodColor },
        markLine:
          exact == null
            ? undefined
            : {
                silent: true,
                symbol: 'none',
                lineStyle: { color: '#16a34a', type: 'dashed', width: 1.2 },
                label: { formatter: '∫ₐᵇ f(x)dx', position: 'insideEndTop', fontSize: 10, color: '#16a34a' },
                data: [{ yAxis: exact }],
              },
        markPoint:
          riemann.value == null
            ? undefined
            : {
                symbol: 'pin',
                symbolSize: 28,
                label: { fontSize: 9 },
                data: [{ name: '当前', coord: [k.value, riemann.value], itemStyle: { color: methodColor } }],
              },
        z: 3,
      },
    ],
  }
})

// 当前方法的求和公式（LaTeX 展示）
const methodFormulaHtml = computed(() => {
  const dx = '\\Delta x = \\frac{b-a}{n}'
  let sum: string
  switch (method.value) {
    case 'left':
      sum = '\\sum_{i=0}^{n-1} f(x_i)\\,\\Delta x'
      break
    case 'right':
      sum = '\\sum_{i=1}^{n} f(x_i)\\,\\Delta x'
      break
    case 'mid':
      sum = '\\sum_{i=0}^{n-1} f\\!\\left(\\bar{x}_i\\right)\\Delta x'
      break
    case 'trap':
      sum = '\\sum_{i=0}^{n-1} \\frac{f(x_i)+f(x_{i+1})}{2}\\,\\Delta x'
      break
    case 'simp':
      sum = '\\sum_{i=0}^{n-1} \\frac{f(x_i)+4f\\!\\left(x_{i+\\frac12}\\right)+f(x_{i+1})}{6}\\,\\Delta x'
      break
  }
  return renderTex(`S_n = ${sum}, \\quad ${dx}`)
})
</script>

<template>
  <div class="integral-sim">
    <!-- 函数输入 -->
    <div class="formula-box">
      <div class="formula-row">
        <span class="f-label">f(x) =</span>
        <input v-model="src" class="f-input" spellcheck="false" placeholder="如 x^2、sin(x)、x^3 - 3*x" />
      </div>
      <div class="presets">
        <button v-for="p in PRESETS" :key="p" class="preset" :class="{ active: src === p }" @click="src = p">
          <span v-html="presetLatex(p)"></span>
        </button>
      </div>
      <p v-if="error" class="f-error">{{ error }}</p>
    </div>

    <div v-if="formulaHtml" class="formula-bar" v-html="formulaHtml"></div>
    <div v-if="methodFormulaHtml" class="formula-bar method-formula" v-html="methodFormulaHtml"></div>

    <!-- 主图：分割 + 求和 -->
    <VChart class="chart main-chart" :option="mainOption" autoresize />

    <!-- 收敛曲线：取极限 -->
    <div class="converge-head">
      <span class="converge-title">取极限：S<sub>n</sub> 随 n 增大 → ∫</span>
      <button class="play-btn" :class="{ on: playing }" @click="togglePlay">
        {{ playing ? '⏸ 暂停' : '▶ 播放 n 增大' }}
      </button>
    </div>
    <VChart class="chart converge-chart" :option="convergeOption" autoresize />

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
      <div class="control-row">
        <span class="control-label">近似方法</span>
        <div class="method-btns">
          <button v-for="(label, m) in METHOD_LABELS" :key="m" :class="{ active: method === m }" @click="method = m as Method">
            {{ label }}
          </button>
        </div>
      </div>
      <div class="result-row">
        <div class="result-box">
          <span class="muted">S<sub>n</sub>（近似和）</span>
          <strong class="num-primary">{{ riemann == null ? '—' : riemann.toFixed(4) }}</strong>
        </div>
        <div class="result-box">
          <span class="muted">定积分（真值）</span>
          <strong class="num-green">{{ exactSigned == null ? '—' : exactSigned.toFixed(4) }}</strong>
        </div>
        <div class="result-box">
          <span class="muted">相对误差</span>
          <strong class="num-red">{{ errText }}</strong>
        </div>
      </div>
      <p class="hint">
        三步：<strong>分割</strong>（把 [a,b] 切成 n 份，灰色虚线只在面积内）、<strong>求和</strong>（每份用{{ METHOD_LABELS[method] }}近似，彩色形状）、
        <strong>取极限</strong>（下方曲线展示 S_n 随 n 增大的变化——n 越大越逼近绿色虚线真值）。
        矩形法收敛慢（锯齿形逼近），梯形法快一些，辛普森法最快（用抛物线拟合，n 很小就很准）。
      </p>
    </div>
  </div>
</template>

<style scoped>
.integral-sim { padding: 16px; }
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
.method-formula { font-size: 13px; color: var(--text-2); }
.chart { width: 100%; }
.main-chart { height: 300px; }
.converge-chart { height: 170px; }
.converge-head {
  display: flex; align-items: center; justify-content: space-between; gap: 8px;
  margin: 2px 0 4px;
}
.converge-title { font-size: 12.5px; font-weight: 600; color: var(--text-2); }
.play-btn {
  flex-shrink: 0; font-size: 12px; padding: 4px 12px;
  border: 1px solid var(--border); border-radius: 999px;
  background: var(--bg-card); color: var(--primary); cursor: pointer;
}
.play-btn:hover { border-color: var(--primary); }
.play-btn.on { background: var(--primary); color: #fff; }
.controls { margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border); display: flex; flex-direction: column; gap: 10px; }
.control-row { display: flex; align-items: center; gap: 12px; }
.control-label { width: 80px; font-size: 13px; color: var(--text-2); flex-shrink: 0; }
.slider { flex: 1; accent-color: var(--primary); cursor: pointer; }
.control-value { width: 48px; font-size: 13px; font-weight: 600; color: var(--primary); text-align: right; flex-shrink: 0; }
.method-btns { display: flex; flex-wrap: wrap; gap: 6px; }
.method-btns button {
  font-size: 12px; padding: 3px 10px; border-radius: 999px; border: 1px solid var(--border);
  background: var(--bg-card); color: var(--text-2); cursor: pointer;
}
.method-btns button.active { background: var(--primary-soft); border-color: var(--primary); color: var(--primary); }
.result-row { display: flex; gap: 10px; margin-top: 8px; }
.result-box { flex: 1; padding: 8px 10px; border-radius: var(--radius-sm); background: var(--bg-hover); text-align: center; display: flex; flex-direction: column; gap: 2px; }
.result-box strong { font-size: 15px; }
.num-primary { color: var(--primary); }
.num-green { color: #16a34a; }
.num-red { color: #dc2626; }
.muted { font-size: 12px; color: var(--text-3); }
.hint { margin-top: 8px; font-size: 12px; color: var(--text-3); line-height: 1.7; }
</style>
