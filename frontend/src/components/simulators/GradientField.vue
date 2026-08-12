<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { ScatterChart, LinesChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, VisualMapComponent } from 'echarts/components'
import katex from 'katex'
import 'katex/dist/katex.min.css'
import { parseBinaryFunction, exprToLatex } from '@/utils/mathExpr'

use([CanvasRenderer, ScatterChart, LinesChart, GridComponent, TooltipComponent, VisualMapComponent])

// 梯度场演示：f(x,y) 的高度图（颜色）+ 各点梯度箭头 + 可拖动/点击的当前点
// 教学点：梯度 ∇f 指向「上升最快」的方向，与等高线垂直；沿负梯度走即梯度下降
// 教学演示（函数为示意，非真实数据）

const props = defineProps<{
  params?: Record<string, unknown>
}>()

const DEFAULT_SRC = 'x^2 + y^2'
const PRESETS = [DEFAULT_SRC, '(x-1)^2 + (y+1)^2', 'x^2 - y^2', 'sin(x)*cos(y)']

const src = ref(typeof props.params?.fn === 'string' ? (props.params.fn as string) : DEFAULT_SRC)
const compiled = ref<(x: number, y: number) => number>(
  parseBinaryFunction(src.value) ?? parseBinaryFunction(DEFAULT_SRC)!,
)
const latex = ref(exprToLatex(src.value) ?? exprToLatex(DEFAULT_SRC) ?? '')
const error = ref('')

// 当前考察点
const px = ref(typeof props.params?.x0 === 'number' ? props.params.x0 : 1)
const py = ref(typeof props.params?.y0 === 'number' ? props.params.y0 : 1)

const renderTex = (s: string) => katex.renderToString(s, { throwOnError: false, strict: false })
const presetLatex = (p: string) => renderTex(exprToLatex(p) ?? p)
const formulaHtml = computed(() => (latex.value ? renderTex(`f(x, y) = ${latex.value}`) : ''))

watch(src, (s) => {
  if (!s.trim()) return
  const f = parseBinaryFunction(s)
  if (f) {
    compiled.value = f
    latex.value = exprToLatex(s) ?? latex.value
    error.value = ''
  } else {
    error.value = '表达式无法解析（支持 x、y、|x| 绝对值、+ - * / ^、括号，以及 sin/cos/tan/sqrt/log/ln/exp/abs）'
  }
})

const DOMAIN = 3.2
const clamp = (v: number) => Math.max(-DOMAIN, Math.min(DOMAIN, v))

// 中心差商求偏导
function gradFn(fn: (x: number, y: number) => number, x: number, y: number): [number, number] {
  const h = 1e-4
  const gx = (fn(x + h, y) - fn(x - h, y)) / (2 * h)
  const gy = (fn(x, y + h) - fn(x, y - h)) / (2 * h)
  if (!Number.isFinite(gx) || !Number.isFinite(gy)) return [NaN, NaN]
  return [gx, gy]
}

// 背景高度图（散点着色）
const bg = computed<[number, number, number][]>(() => {
  const pts: [number, number, number][] = []
  for (let x = -DOMAIN; x <= DOMAIN + 0.001; x += 0.25) {
    for (let y = -DOMAIN; y <= DOMAIN + 0.001; y += 0.25) {
      const v = compiled.value(x, y)
      if (Number.isFinite(v)) pts.push([Number(x.toFixed(2)), Number(y.toFixed(2)), Number(v.toFixed(3))])
    }
  }
  return pts
})
const bgRange = computed(() => {
  let min = Infinity
  let max = -Infinity
  for (const [, , v] of bg.value) {
    if (v < min) min = v
    if (v > max) max = v
  }
  if (!Number.isFinite(min)) return { min: 0, max: 1 }
  return min === max ? { min: min - 1, max: max + 1 } : { min, max }
})

// 梯度箭头（网格采样）
const arrows = computed(() => {
  const step = 0.75
  const list: { x: number; y: number; mag: number; rotate: number; size: number }[] = []
  let maxMag = 1e-9
  const raw: { x: number; y: number; gx: number; gy: number; mag: number }[] = []
  for (let x = -DOMAIN; x <= DOMAIN + 0.001; x += step) {
    for (let y = -DOMAIN; y <= DOMAIN + 0.001; y += step) {
      const [gx, gy] = gradFn(compiled.value, x, y)
      if (Number.isNaN(gx)) continue
      const mag = Math.hypot(gx, gy)
      raw.push({ x, y, gx, gy, mag })
      if (mag > maxMag) maxMag = mag
    }
  }
  for (const a of raw) {
    list.push({
      x: a.x,
      y: a.y,
      mag: a.mag,
      rotate: (Math.atan2(-a.gy, a.gx) * 180) / Math.PI + 90,
      size: 7 + 16 * (a.mag / maxMag),
    })
  }
  return { list, maxMag }
})

// 当前点
const curGrad = computed<[number, number]>(() => gradFn(compiled.value, px.value, py.value))
const curValue = computed(() => compiled.value(px.value, py.value))
const curRotate = computed(() => (Math.atan2(-curGrad.value[1], curGrad.value[0]) * 180) / Math.PI + 90)

// ---------- 等高线（marching squares，教学用近似） ----------
const GRID_N = 40
function isoSegments(
  fn: (x: number, y: number) => number,
  x0: number, x1: number, y0: number, y1: number,
  nx: number, ny: number, level: number,
): [number, number][][] {
  const segs: [number, number][][] = []
  const dx = (x1 - x0) / nx
  const dy = (y1 - y0) / ny
  for (let i = 0; i < nx; i++) {
    for (let j = 0; j < ny; j++) {
      const xl = x0 + i * dx
      const xr = xl + dx
      const yb = y0 + j * dy
      const yt = yb + dy
      const v00 = fn(xl, yb)
      const v10 = fn(xr, yb)
      const v11 = fn(xr, yt)
      const v01 = fn(xl, yt)
      if (![v00, v10, v11, v01].every(Number.isFinite)) continue
      const c00 = v00 > level
      const c10 = v10 > level
      const c11 = v11 > level
      const c01 = v01 > level
      const lerp = (a: number, b: number, va: number, vb: number) => (va === vb ? a : a + ((b - a) * (level - va)) / (vb - va))
      // 四条边的穿越点：下 右 上 左
      const edges: ([number, number] | null)[] = [
        c00 !== c10 ? [lerp(xl, xr, v00, v10), yb] : null,
        c10 !== c11 ? [xr, lerp(yb, yt, v10, v11)] : null,
        c11 !== c01 ? [lerp(xr, xl, v11, v01), yt] : null,
        c01 !== c00 ? [xl, lerp(yt, yb, v01, v00)] : null,
      ]
      const pts = edges.filter(Boolean) as [number, number][]
      if (pts.length === 2) segs.push([pts[0], pts[1]])
      else if (pts.length === 4) {
        // 鞍点：连对边
        segs.push([pts[0], pts[2]])
        segs.push([pts[1], pts[3]])
      }
    }
  }
  return segs
}

const contours = computed<[number, number][][]>(() => {
  const range = bgRange.value
  if (range.min === range.max) return []
  const all: [number, number][][] = []
  const NLEVEL = 7
  for (let k = 1; k <= NLEVEL; k++) {
    const level = range.min + ((range.max - range.min) * k) / (NLEVEL + 1)
    all.push(...isoSegments(compiled.value, -DOMAIN, DOMAIN, -DOMAIN, DOMAIN, GRID_N, GRID_N, level))
  }
  return all
})

// ---------- 梯度下降演示 ----------
const descentPath = ref<[number, number][]>([])
function runDescent() {
  const lr = 0.12
  const steps = 40
  let x = px.value
  let y = py.value
  const path: [number, number][] = [[Number(x.toFixed(3)), Number(y.toFixed(3))]]
  for (let i = 0; i < steps; i++) {
    const [gx, gy] = gradFn(compiled.value, x, y)
    if (!Number.isFinite(gx) || Math.hypot(gx, gy) < 1e-6) break
    x -= lr * gx
    y -= lr * gy
    path.push([Number(x.toFixed(3)), Number(y.toFixed(3))])
  }
  descentPath.value = path
}

function onChartClick(params: any) {
  if (params?.value && Array.isArray(params.value)) {
    px.value = clamp(params.value[0])
    py.value = clamp(params.value[1])
  }
}

const fmt2 = (v: number) => (Number.isFinite(v) ? v.toFixed(2) : '—')
const gradMagText = computed(() => (Number.isFinite(curGrad.value[0]) ? Math.hypot(...curGrad.value).toFixed(2) : '—'))

const option = computed(() => ({
  animation: false,
  grid: { left: 46, right: 24, top: 20, bottom: 42 },
  tooltip: {
    trigger: 'item',
    formatter: (p: any) => {
      const v = p.value
      if (!Array.isArray(v)) return ''
      return `x = ${Number(v[0]).toFixed(2)}, y = ${Number(v[1]).toFixed(2)}<br/>f = ${Number(v[2]).toFixed(3)}`
    },
  },
  xAxis: { type: 'value', name: 'x', nameLocation: 'middle', nameGap: 26, min: -DOMAIN, max: DOMAIN, axisLabel: { fontSize: 10 } },
  yAxis: { type: 'value', name: 'y', nameLocation: 'middle', nameGap: 34, min: -DOMAIN, max: DOMAIN, axisLabel: { fontSize: 10 } },
  visualMap: {
    min: bgRange.value.min,
    max: bgRange.value.max,
    dimension: 2,
    inRange: { color: ['#1e3a8a', '#3b82f6', '#f59e0b', '#ef4444'] },
    right: 6,
    top: 'middle',
    text: ['高', '低'],
    textStyle: { fontSize: 10 },
    calculable: false,
    itemHeight: 120,
  },
  series: [
    {
      type: 'scatter',
      name: 'f(x,y)',
      data: bg.value,
      symbolSize: 8,
      itemStyle: { opacity: 0.95 },
      z: 1,
    },
    {
      type: 'lines',
      name: '等高线',
      data: contours.value.map((c) => ({ coords: c })),
      coordinateSystem: 'cartesian2d',
      lineStyle: { color: 'rgba(15, 23, 42, 0.45)', width: 1 },
      silent: true,
      z: 2,
    },
    {
      type: 'scatter',
      name: '梯度 ∇f',
      data: arrows.value.list.map((a) => ({
        value: [a.x, a.y],
        symbolRotate: a.rotate,
        symbolSize: a.size,
      })),
      symbol: 'arrow',
      itemStyle: { color: 'rgba(15, 23, 42, 0.6)' },
      z: 3,
      silent: true,
    },
    {
      type: 'line',
      name: '梯度下降路径',
      data: descentPath.value,
      symbol: 'circle',
      symbolSize: 4,
      lineStyle: { color: '#dc2626', width: 2 },
      itemStyle: { color: '#dc2626' },
      z: 6,
    },
    {
      type: 'scatter',
      name: '当前点',
      data: [[px.value, py.value, Number.isFinite(curValue.value) ? Number(curValue.value.toFixed(3)) : null]],
      symbolSize: 10,
      itemStyle: { color: '#dc2626', borderColor: '#fff', borderWidth: 1.5 },
      z: 5,
    },
    {
      type: 'scatter',
      name: '当前梯度',
      data: [{ value: [px.value, py.value], symbolRotate: curRotate.value, symbolSize: 13 }],
      symbol: 'arrow',
      itemStyle: { color: '#dc2626' },
      z: 4,
      silent: true,
    },
  ],
}))
</script>

<template>
  <div class="gradient-field">
    <!-- 函数输入 -->
    <div class="formula-box">
      <div class="formula-row">
        <span class="f-label">f(x, y) =</span>
        <input
          v-model="src"
          class="f-input"
          spellcheck="false"
          placeholder="如 x^2 + y^2、|x| + |y|、sin(x)*cos(y)"
        />
      </div>
      <div class="presets">
        <button v-for="p in PRESETS" :key="p" class="preset" :class="{ active: src === p }" @click="src = p">
          <span v-html="presetLatex(p)"></span>
        </button>
      </div>
      <p v-if="error" class="f-error">{{ error }}</p>
    </div>

    <!-- 当前二元函数公式（katex 渲染） -->
    <div v-if="formulaHtml" class="formula-bar" v-html="formulaHtml"></div>

    <VChart class="chart" :option="option" autoresize @click="onChartClick" />

    <div class="controls">
      <div class="control-row">
        <span class="control-label">x₀</span>
        <input v-model.number="px" type="range" :min="-DOMAIN" :max="DOMAIN" step="0.1" class="slider" />
        <span class="control-value">{{ fmt2(px) }}</span>
      </div>
      <div class="control-row">
        <span class="control-label">y₀</span>
        <input v-model.number="py" type="range" :min="-DOMAIN" :max="DOMAIN" step="0.1" class="slider" />
        <span class="control-value">{{ fmt2(py) }}</span>
      </div>
      <div class="control-row">
        <span class="control-label">演示</span>
        <button class="descent-btn" @click="runDescent">▶ 梯度下降（沿 −∇f 走 40 步）</button>
      </div>
      <div class="result-row">
        <div class="result-box">
          <span class="muted">∂f/∂x</span>
          <strong>{{ fmt2(curGrad[0]) }}</strong>
        </div>
        <div class="result-box">
          <span class="muted">∂f/∂y</span>
          <strong>{{ fmt2(curGrad[1]) }}</strong>
        </div>
        <div class="result-box">
          <span class="muted">|∇f|</span>
          <strong>{{ gradMagText }}</strong>
        </div>
        <div class="result-box">
          <span class="muted">f(x₀,y₀)</span>
          <strong>{{ fmt2(curValue) }}</strong>
        </div>
      </div>
      <p class="hint">
        颜色 = f(x,y) 高低（深蓝低、红色高），<strong>黑色细线是等高线</strong>，灰色箭头是各点梯度 ∇f——
        它总指向「往上爬最快」的方向，因此<strong>与等高线垂直</strong>。红色箭头是当前点的梯度；
        拖动滑块或点击图面移动当前点，点「梯度下降」按钮看沿 −∇f 一步步行下山（路径变红），直到到达谷底。
      </p>
    </div>
  </div>
</template>

<style scoped>
.gradient-field { padding: 16px; }
.formula-box { margin-bottom: 8px; }
.formula-row { display: flex; align-items: center; gap: 8px; }
.f-label { font-size: 13px; font-weight: 600; color: var(--text-2); flex-shrink: 0; font-family: var(--font-mono); }
.f-input {
  flex: 1;
  font-family: var(--font-mono);
  font-size: 13px;
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

.chart { height: 360px; }
.controls { margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border); display: flex; flex-direction: column; gap: 8px; }
.control-row { display: flex; align-items: center; gap: 12px; }
.control-label { width: 42px; font-size: 13px; color: var(--text-2); flex-shrink: 0; }
.slider { flex: 1; accent-color: var(--primary); cursor: pointer; }
.control-value { width: 48px; font-size: 13px; font-weight: 600; color: var(--primary); text-align: right; flex-shrink: 0; }
.descent-btn {
  flex: 1;
  font-size: 12.5px;
  padding: 6px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-card);
  color: var(--primary);
  cursor: pointer;
}
.descent-btn:hover { border-color: var(--primary); background: var(--primary-soft); }
.result-row { display: flex; gap: 8px; margin-top: 6px; }
.result-box { flex: 1; padding: 8px 6px; border-radius: var(--radius-sm); background: var(--bg-hover); text-align: center; display: flex; flex-direction: column; gap: 2px; }
.result-box strong { font-size: 14px; }
.muted { font-size: 12px; color: var(--text-3); }
.hint { margin-top: 8px; font-size: 12px; color: var(--text-3); line-height: 1.7; }
</style>
