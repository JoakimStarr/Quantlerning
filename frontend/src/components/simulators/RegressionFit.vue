<script setup lang="ts">
import { computed, ref } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, ScatterChart, LinesChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'

use([CanvasRenderer, LineChart, ScatterChart, LinesChart, GridComponent, TooltipComponent, LegendComponent])

// 线性回归演示：散点数据 + OLS 拟合线 + 残差
// 教学演示（随机生成数据，非真实数据）

const props = defineProps<{
  params?: Record<string, unknown>
}>()

const n = ref(typeof props.params?.n === 'number' ? props.params.n : 40)
const beta0 = ref(typeof props.params?.beta0 === 'number' ? props.params.beta0 : 1.0)
const beta1 = ref(typeof props.params?.beta1 === 'number' ? props.params.beta1 : 0.8)
const noise = ref(typeof props.params?.noise === 'number' ? props.params.noise : 0.5)

let seed = 7
function rng() {
  seed = (seed * 1103515245 + 12345) % 2147483648
  return seed / 2147483648
}
function randn() {
  const u1 = Math.max(rng(), 1e-9)
  const u2 = rng()
  return Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2)
}

const points = ref<Array<{ x: number; y: number }>>([])

function regenerate() {
  const out: Array<{ x: number; y: number }> = []
  for (let i = 0; i < n.value; i++) {
    const x = (i / Math.max(n.value - 1, 1)) * 10 - 5 // x ∈ [-5, 5]
    const y = beta0.value + beta1.value * x + noise.value * randn()
    out.push({ x, y })
  }
  points.value = out
}

regenerate()

// 重新生成（保持样本量，但重新抽噪声）
function resample() {
  seed = (seed + 1000) % 2147483648
  regenerate()
}

// OLS 拟合
const fit = computed(() => {
  const xs = points.value.map((p) => p.x)
  const ys = points.value.map((p) => p.y)
  const xbar = xs.reduce((s, v) => s + v, 0) / xs.length
  const ybar = ys.reduce((s, v) => s + v, 0) / ys.length
  let sxy = 0
  let sxx = 0
  for (let i = 0; i < xs.length; i++) {
    sxy += (xs[i] - xbar) * (ys[i] - ybar)
    sxx += (xs[i] - xbar) * (xs[i] - xbar)
  }
  const b1 = sxx > 0 ? sxy / sxx : 0
  const b0 = ybar - b1 * xbar
  // R²
  let sst = 0
  let sse = 0
  for (let i = 0; i < ys.length; i++) {
    sst += (ys[i] - ybar) * (ys[i] - ybar)
    sse += (ys[i] - (b0 + b1 * xs[i])) * (ys[i] - (b0 + b1 * xs[i]))
  }
  const r2 = sst > 0 ? 1 - sse / sst : 0
  return { b0, b1, r2 }
})

// 拟合线 + 残差线段
const fittedLine = computed<[number, number][]>(() => {
  const xs = points.value.map((p) => p.x)
  const minX = Math.min(...xs)
  const maxX = Math.max(...xs)
  return [
    [minX, fit.value.b0 + fit.value.b1 * minX],
    [maxX, fit.value.b0 + fit.value.b1 * maxX],
  ]
})

// 残差线段：每段 [拟合点, 观测点]（lines 系列按线段绘制，line 系列画不出竖线段）
const residuals = computed<[[number, number], [number, number]][]>(() =>
  points.value.map((p) => {
    const yhat = fit.value.b0 + fit.value.b1 * p.x
    return [
      [p.x, yhat],
      [p.x, p.y],
    ]
  }),
)

const option = computed(() => ({
  animation: true,
  grid: { left: 55, right: 24, top: 36, bottom: 40 },
  tooltip: {
    trigger: 'item',
    formatter: (p: any) => `x = ${Number(p.value[0]).toFixed(2)}<br/>y = ${Number(p.value[1]).toFixed(2)}`,
  },
  legend: { top: 0, textStyle: { fontSize: 12 } },
  xAxis: { type: 'value', name: 'x', nameLocation: 'middle', nameGap: 26, axisLabel: { fontSize: 11 } },
  yAxis: { type: 'value', name: 'y', nameLocation: 'middle', nameGap: 36, axisLabel: { fontSize: 11 } },
  series: [
    {
      name: '观测点',
      type: 'scatter',
      data: points.value.map((p) => [p.x, p.y]),
      symbolSize: 6,
      itemStyle: { color: '#94a3b8' },
    },
    {
      name: '残差',
      type: 'lines',
      coordinateSystem: 'cartesian2d',
      data: residuals.value,
      symbol: ['none', 'none'],
      lineStyle: { width: 1, color: '#dc2626', opacity: 0.4 },
      tooltip: { show: false },
      zlevel: 1,
    },
    {
      name: `OLS：y = ${fit.value.b1.toFixed(2)}x + ${fit.value.b0.toFixed(2)}`,
      type: 'line',
      data: fittedLine.value,
      symbol: 'none',
      lineStyle: { width: 2.5, color: '#2563eb' },
      itemStyle: { color: '#2563eb' },
    },
  ],
}))
</script>

<template>
  <div class="reg-sim">
    <VChart class="chart" :option="option" autoresize />

    <div class="controls">
      <div class="control-row">
        <span class="control-label">截距 β₀</span>
        <input v-model.number="beta0" type="range" min="-3" max="3" step="0.1" class="slider" />
        <span class="control-value">{{ beta0.toFixed(1) }}</span>
      </div>
      <div class="control-row">
        <span class="control-label">斜率 β₁</span>
        <input v-model.number="beta1" type="range" min="-2" max="2" step="0.1" class="slider" />
        <span class="control-value">{{ beta1.toFixed(1) }}</span>
      </div>
      <div class="control-row">
        <span class="control-label">噪声 σ</span>
        <input v-model.number="noise" type="range" min="0" max="3" step="0.1" class="slider" />
        <span class="control-value">{{ noise.toFixed(1) }}</span>
      </div>
      <div class="result-row">
        <div class="result-box">
          <span class="muted">拟合斜率 b₁</span>
          <strong>{{ fit.b1.toFixed(3) }}</strong>
        </div>
        <div class="result-box">
          <span class="muted">拟合截距 b₀</span>
          <strong>{{ fit.b0.toFixed(3) }}</strong>
        </div>
        <div class="result-box">
          <span class="muted">R²</span>
          <strong>{{ (fit.r2 * 100).toFixed(1) }}%</strong>
        </div>
        <button class="btn" @click="resample">重新抽样</button>
      </div>
      <p class="hint">
        OLS 找使「残差平方和最小」的直线。噪声越大，估计的 b₁ 越不稳定、R² 越低。
        回到真值 β₁ 后，对比拟合 b₁ —— 样本量越小估计越易偏离。
      </p>
    </div>
  </div>
</template>

<style scoped>
.reg-sim { padding: 16px; }
.chart { height: 340px; }
.controls { margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border); display: flex; flex-direction: column; gap: 10px; }
.control-row { display: flex; align-items: center; gap: 12px; }
.control-label { width: 88px; font-size: 13px; color: var(--text-2); flex-shrink: 0; }
.slider { flex: 1; accent-color: var(--primary); cursor: pointer; }
.control-value { width: 56px; font-size: 13px; font-weight: 600; color: var(--primary); text-align: right; flex-shrink: 0; }
.result-row { display: flex; align-items: center; gap: 10px; margin-top: 8px; flex-wrap: wrap; }
.result-box { flex: 1; padding: 8px 10px; border-radius: var(--radius-sm); background: var(--bg-hover); text-align: center; display: flex; flex-direction: column; gap: 2px; }
.result-box strong { font-size: 16px; color: var(--primary); }
.btn {
  padding: 5px 14px; border: 1px solid var(--border); border-radius: var(--radius-sm);
  background: var(--bg-card); color: var(--text-1); font-size: 13px; cursor: pointer;
  transition: all 0.15s;
}
.btn:hover { border-color: var(--primary); color: var(--primary); }
.muted { font-size: 12px; color: var(--text-3); }
.hint { margin-top: 8px; font-size: 12px; color: var(--text-3); line-height: 1.7; }
</style>