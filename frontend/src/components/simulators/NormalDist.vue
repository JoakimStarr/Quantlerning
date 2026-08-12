<script setup lang="ts">
import { computed, ref } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent])

// 正态分布探索：拖动 μ/σ，观察密度曲线与 ±1/2/3σ 区间
// 演示 68-95-99.7 经验法则（教学模拟，非真实数据）

const props = defineProps<{
  params?: Record<string, unknown>
}>()

const mu = ref(typeof props.params?.mu === 'number' ? props.params.mu : 0)
const sigma = ref(typeof props.params?.sigma === 'number' ? props.params.sigma : 1)

const N = 200

function normalDensity(x: number, m: number, s: number) {
  return (1 / (s * Math.sqrt(2 * Math.PI))) * Math.exp(-((x - m) ** 2) / (2 * s * s))
}

// 分段区域：每个 σ 区间一组 (多个 [lo,hi] 段 + 填充色)，用不同色相区分
const sigmaZones: Array<{ label: string; ranges: [number, number][]; color: string; fill: string }> = [
  { label: '±1σ', ranges: [[-1, 1]], color: '#2563eb', fill: 'rgba(37, 99, 235, 0.32)' },
  { label: '±2σ', ranges: [[-2, -1], [1, 2]], color: '#0d9488', fill: 'rgba(13, 148, 136, 0.24)' },
  { label: '±3σ', ranges: [[-3, -2], [2, 3]], color: '#d97706', fill: 'rgba(217, 119, 6, 0.18)' },
]

const xMin = computed(() => mu.value - 4 * sigma.value)
const xMax = computed(() => mu.value + 4 * sigma.value)

// 完整密度曲线
const density = computed<[number, number][]>(() => {
  const pts: [number, number][] = []
  for (let i = 0; i <= N; i++) {
    const x = xMin.value + ((xMax.value - xMin.value) * i) / N
    pts.push([Number(x.toFixed(3)), Number(normalDensity(x, mu.value, sigma.value).toFixed(5))])
  }
  return pts
})

// 每个 σ 区间生成一条分段 area 数据（区间内填值，区间外 null）
const zoneSeries = computed(() =>
  sigmaZones.map((z) => {
    const data: [number, number | null][] = []
    for (let i = 0; i <= N; i++) {
      const x = xMin.value + ((xMax.value - xMin.value) * i) / N
      const k = (x - mu.value) / sigma.value
      const inZone = z.ranges.some(([lo, hi]) => k >= lo && k <= hi)
      data.push([Number(x.toFixed(3)), inZone ? Number(normalDensity(x, mu.value, sigma.value).toFixed(5)) : null])
    }
    return { label: z.label, data, fill: z.fill }
  }),
)

// 经验法则常数（正态分布的数学性质），颜色与图上区间一致
const rule = [
  { label: '±1σ', pct: '68.3%', color: '#2563eb' },
  { label: '±2σ', pct: '95.4%', color: '#0d9488' },
  { label: '±3σ', pct: '99.7%', color: '#d97706' },
]

const option = computed(() => ({
  animation: true,
  grid: { left: 55, right: 20, top: 40, bottom: 45 },
  tooltip: {
    trigger: 'axis',
    formatter: (params: any) => {
      const p = Array.isArray(params) ? params[0] : params
      if (p == null) return ''
      return `x = ${Number((p.value as number[])[0]).toFixed(2)}<br/>f(x) = ${Number((p.value as number[])[1]).toFixed(4)}`
    },
  },
  legend: { top: 0, textStyle: { fontSize: 12 } },
  xAxis: {
    type: 'value',
    name: 'x',
    nameLocation: 'middle',
    nameGap: 30,
    min: xMin.value,
    max: xMax.value,
    axisLabel: { fontSize: 11 },
  },
  yAxis: {
    type: 'value',
    name: 'f(x)',
    nameLocation: 'middle',
    nameGap: 42,
    min: 0,
    axisLabel: { fontSize: 11 },
  },
  series: [
    {
      name: `N(${mu.value.toFixed(1)}, ${sigma.value.toFixed(1)}²)`,
      type: 'line',
      smooth: true,
      symbol: 'none',
      data: density.value,
      lineStyle: { width: 3, color: '#2563eb' },
      itemStyle: { color: '#2563eb' },
      z: 5,
    },
    ...zoneSeries.value.map((zs) => ({
      name: zs.label,
      type: 'line' as const,
      smooth: true,
      symbol: 'none',
      data: zs.data,
      lineStyle: { width: 0, color: 'transparent' },
      areaStyle: { color: zs.fill },
      silent: true,
      z: 1,
    })),
  ],
}))
</script>

<template>
  <div class="normal-dist">
    <VChart class="chart" :option="option" autoresize />

    <div class="controls">
      <div class="control-row">
        <span class="control-label">均值 μ</span>
        <input v-model.number="mu" type="range" min="-3" max="3" step="0.1" class="slider" />
        <span class="control-value">{{ mu.toFixed(1) }}</span>
      </div>
      <div class="control-row">
        <span class="control-label">标准差 σ</span>
        <input v-model.number="sigma" type="range" min="0.3" max="2" step="0.1" class="slider" />
        <span class="control-value">{{ sigma.toFixed(1) }}</span>
      </div>
      <div class="rule-row">
        <div
          v-for="r in rule"
          :key="r.label"
          class="rule-box"
          :style="{ borderTopColor: r.color }"
        >
          <span class="muted">{{ r.label }} 区间</span>
          <strong :style="{ color: r.color }">{{ r.pct }}</strong>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.normal-dist { padding: 16px; }
.chart { height: 320px; }
.controls { margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border); display: flex; flex-direction: column; gap: 10px; }
.control-row { display: flex; align-items: center; gap: 12px; }
.control-label { width: 72px; font-size: 13px; color: var(--text-2); flex-shrink: 0; }
.slider { flex: 1; accent-color: var(--primary); cursor: pointer; }
.control-value { width: 48px; font-size: 13px; font-weight: 600; color: var(--primary); text-align: right; flex-shrink: 0; }
.rule-row { display: flex; gap: 10px; margin-top: 8px; }
.rule-box {
  flex: 1; padding: 8px 10px; border-radius: var(--radius-sm);
  background: var(--bg-hover); text-align: center;
  display: flex; flex-direction: column; gap: 2px;
  border-top: 3px solid transparent;
}
.rule-box strong { font-size: 16px; color: var(--primary); }
.muted { font-size: 12px; color: var(--text-3); }
</style>
