<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C, withAlpha } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, MarkAreaComponent, MarkPointComponent } from 'echarts/components'
import katex from 'katex'
import 'katex/dist/katex.min.css'
import { parseAst, exprToLatex, evaluateAst, differentiate } from '@/utils/mathExpr'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent, MarkAreaComponent, MarkPointComponent])

// 凹凸与拐点：符号微分得到 f' 与 f''，同图显示 f 与 f''（右轴）
// f''>0 区域绿色（凹向上）、f''<0 区域红色（凹向下）；f'=0 标极值、f''=0 标拐点
// 教学演示（函数为示意，非真实数据）

const props = defineProps<{
  params?: Record<string, unknown>
}>()

const DEFAULT_SRC = 'x^3/3 - x^2 - x + 3'
const PRESETS = [DEFAULT_SRC, 'x^2', 'x^3', 'sin(x)']

const src = ref(typeof props.params?.fn === 'string' ? (props.params.fn as string) : DEFAULT_SRC)
const latex = ref(exprToLatex(src.value) ?? '')
const error = ref('')

const x0 = ref(typeof props.params?.x0 === 'number' ? props.params.x0 : 1)

watch(src, (s) => {
  if (!s.trim()) return
  const ast = parseAst(s)
  if (ast) {
    latex.value = exprToLatex(s) ?? latex.value
    error.value = ''
  } else {
    error.value = '表达式无法解析（支持 x、|x|、+ - * / ^、括号，以及 sin/cos/tan/sqrt/log/ln/exp/abs）'
  }
})

const renderTex = (s: string) => katex.renderToString(s, { throwOnError: false, strict: false })
const presetLatex = (p: string) => renderTex(exprToLatex(p) ?? p)
const formulaHtml = computed(() => (latex.value ? renderTex(`f(x) = ${latex.value}`) : ''))

const xMin = -3.2
const xMax = 3.2
const N = 240

// 符号微分（精确）
const ast = computed(() => parseAst(src.value))
const f1Ast = computed(() => (ast.value ? differentiate(ast.value, 'x') : null))
const f2Ast = computed(() => (f1Ast.value ? differentiate(f1Ast.value, 'x') : null))
const f = (x: number) => (ast.value ? evaluateAst(ast.value, x, 0) : NaN)
const f1 = (x: number) => (f1Ast.value ? evaluateAst(f1Ast.value, x, 0) : NaN)
const f2 = (x: number) => (f2Ast.value ? evaluateAst(f2Ast.value, x, 0) : NaN)

const fCurve = computed<[number, number | null][]>(() => {
  const out: [number, number | null][] = []
  for (let i = 0; i <= N; i++) {
    const x = xMin + ((xMax - xMin) * i) / N
    const y = f(x)
    out.push([Number(x.toFixed(3)), Number.isFinite(y) ? Number(y.toFixed(4)) : null])
  }
  return out
})
const f2Curve = computed<[number, number | null][]>(() => {
  const out: [number, number | null][] = []
  for (let i = 0; i <= N; i++) {
    const x = xMin + ((xMax - xMin) * i) / N
    const y = f2(x)
    out.push([Number(x.toFixed(3)), Number.isFinite(y) ? Number(y.toFixed(5)) : null])
  }
  return out
})

// 扫描 f'' 符号区间（凹向区间）
function signIntervals(fn: (x: number) => number, lo: number, hi: number, wantPos: boolean, step = 0.05): [number, number][] {
  const out: [number, number][] = []
  let start: number | null = null
  for (let x = lo; x <= hi + 1e-9; x += step) {
    const v = fn(x)
    const pos = Number.isFinite(v) && v > 0
    if (pos === wantPos) {
      if (start === null) start = x
    } else if (start !== null) {
      out.push([start, x])
      start = null
    }
  }
  if (start !== null) out.push([start, hi])
  return out
}

const concavityAreas = computed<any[]>(() => {
  if (!f2Ast.value) return []
  const green = signIntervals(f2, xMin, xMax, true)
  const red = signIntervals(f2, xMin, xMax, false)
  return [
    ...green.map(([lo, hi]) => [{ xAxis: lo, itemStyle: { color: withAlpha(C.value.success, 0.14) } }, { xAxis: hi }]),
    ...red.map(([lo, hi]) => [{ xAxis: lo, itemStyle: { color: withAlpha(C.value.danger, 0.10) } }, { xAxis: hi }]),
  ]
})

// 找根（扫描符号变化 + 二分）
function findRoots(fn: (x: number) => number, lo: number, hi: number): number[] {
  const roots: number[] = []
  const step = 0.02
  let px = lo
  let pv = fn(lo)
  for (let x = lo + step; x <= hi + 1e-9; x += step) {
    const cv = fn(x)
    if (pv === 0) roots.push(px)
    else if (cv === 0) roots.push(x)
    else if ((pv < 0 && cv > 0) || (pv > 0 && cv < 0)) {
      let a = px
      let b = x
      let fa = pv
      for (let i = 0; i < 30; i++) {
        const mid = (a + b) / 2
        const fm = fn(mid)
        if (fm === 0) {
          a = b = mid
          break
        }
        if ((fa < 0 && fm > 0) || (fa > 0 && fm < 0)) b = mid
        else {
          a = mid
          fa = fm
        }
      }
      roots.push((a + b) / 2)
    }
    px = x
    pv = cv
  }
  return roots.filter((r, i) => i === 0 || r - roots[i - 1] > 0.05)
}

// 极值（f'=0）与拐点（f''=0）
const extrema = computed(() => (f1Ast.value ? findRoots(f1, xMin, xMax) : []))
const inflections = computed(() => (f2Ast.value ? findRoots(f2, xMin, xMax) : []))

const markPointData = computed(() => [
  ...extrema.value.map((x) => ({ coord: [Number(x.toFixed(3)), Number(f(x).toFixed(4))], itemStyle: { color: C.value.warning } })),
  ...inflections.value.map((x) => ({ coord: [Number(x.toFixed(3)), Number(f(x).toFixed(4))], itemStyle: { color: C.value.violet } })),
])

// 当前点读数与判定
const cur = computed(() => ({
  f: f(x0.value),
  f1: f1(x0.value),
  f2: f2(x0.value),
}))
const verdict = computed(() => {
  const { f1: f1v, f2: f2v } = cur.value
  if (!Number.isFinite(f2v)) return '该点 f″ 无定义'
  const nearStationary = Number.isFinite(f1v) && Math.abs(f1v) < 0.02
  if (nearStationary && Math.abs(f2v) > 1e-3) {
    return f2v > 0 ? '驻点 → 局部极小（f″>0）' : '驻点 → 局部极大（f″<0）'
  }
  if (Math.abs(f2v) < 1e-3) return 'f″≈0，拐点候选'
  return f2v > 0 ? '凹向上（f″>0）' : '凹向下（f″<0）'
})

const option = computed(() => ({
  animation: false,
  grid: { left: 55, right: 56, top: 36, bottom: 42 },
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
  legend: { top: 0, textStyle: { fontSize: 11 } },
  xAxis: { type: 'value', name: 'x', nameLocation: 'middle', nameGap: 28, min: xMin, max: xMax, axisLabel: { fontSize: 10 } },
  yAxis: [
    { type: 'value', name: 'f(x)', nameLocation: 'middle', nameGap: 40, scale: true, axisLabel: { fontSize: 10 } },
    { type: 'value', name: 'f″(x)', nameLocation: 'middle', nameGap: 46, splitLine: { show: false }, axisLabel: { fontSize: 10 } },
  ],
  series: [
    {
      name: 'f(x)',
      type: 'line',
      data: fCurve.value,
      smooth: true,
      symbol: 'none',
      lineStyle: { width: 2.5, color: C.value.primary },
      itemStyle: { color: C.value.primary },
      yAxisIndex: 0,
      z: 3,
      markArea: { data: concavityAreas.value, silent: true },
      markPoint: { symbolSize: 10, label: { show: false }, data: markPointData.value },
    },
    {
      name: 'f″(x)（右轴）',
      type: 'line',
      data: f2Curve.value,
      smooth: true,
      symbol: 'none',
      lineStyle: { width: 1.8, color: C.value.slate, type: 'dashed' },
      itemStyle: { color: C.value.slate },
      yAxisIndex: 1,
      z: 2,
    },
  ],
}))

const fmt2 = (v: number) => (Number.isFinite(v) ? v.toFixed(3) : '—')
</script>

<template>
  <div class="concavity-demo">
    <div class="formula-box">
      <div class="formula-row">
        <span class="f-label">f(x) =</span>
        <input v-model="src" class="f-input" spellcheck="false" placeholder="如 x^3/3 - x^2 - x + 3、sin(x)" />
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
        <input v-model.number="x0" type="range" :min="xMin" :max="xMax" step="0.1" class="slider" />
        <span class="control-value">{{ x0.toFixed(1) }}</span>
      </div>
      <div class="result-row">
        <div class="result-box"><span class="muted">f(x₀)</span><strong>{{ fmt2(cur.f) }}</strong></div>
        <div class="result-box"><span class="muted">f′(x₀)</span><strong>{{ fmt2(cur.f1) }}</strong></div>
        <div class="result-box"><span class="muted">f″(x₀)</span><strong>{{ fmt2(cur.f2) }}</strong></div>
        <div class="result-box"><span class="muted">判定</span><strong class="v">{{ verdict }}</strong></div>
      </div>
      <p class="hint">
        背景绿色 = f″&gt;0（凹向上），红色 = f″&lt;0（凹向下）。橙色点是 f′=0 的极值候选，紫色点是 f″=0
        变号的拐点。f′、f″ 由符号微分精确求得（非数值近似）。
      </p>
    </div>
  </div>
</template>

<style scoped>
.concavity-demo { padding: 16px; }
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
.result-box strong { font-size: 13px; }
.result-box strong.v { color: var(--text-1); font-size: 12px; }
.muted { font-size: 11.5px; color: var(--text-3); }
.hint { margin-top: 8px; font-size: 12px; color: var(--text-3); line-height: 1.7; }
</style>
