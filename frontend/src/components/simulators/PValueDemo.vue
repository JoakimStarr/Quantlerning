<script setup lang="ts">
import { computed, ref } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C, withAlpha } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, MarkLineComponent } from 'echarts/components'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, MarkLineComponent])

// 假设检验可视化：H0 下的检验统计量 ~ N(0,1)，拒绝域为 |z| > z_{α/2}
// 拖动观测到的检验统计量 z，阴影面积即 p 值；与显著性水平 α 比较判断拒绝与否
// （示意演示，非真实数据）

const props = defineProps<{
  params?: Record<string, unknown>
}>()

const zObs = ref(typeof props.params?.z === 'number' ? props.params.z : 2.2)
const alpha = ref(typeof props.params?.alpha === 'number' ? props.params.alpha : 0.05)

// 标准正态密度
function normDensity(x: number) {
  return (1 / Math.sqrt(2 * Math.PI)) * Math.exp(-(x * x) / 2)
}

const N = 300
const xMin = -4.5
const xMax = 4.5

// 双侧临界值
const zCrit = computed(() => {
  // 用 1.96 / 1.645 / 2.576 近似 α = 0.05 / 0.10 / 0.01；其余按线性插值
  const map: Record<string, number> = {
    '0.01': 2.576,
    '0.02': 2.326,
    '0.03': 2.17,
    '0.04': 2.054,
    '0.05': 1.96,
    '0.06': 1.881,
    '0.07': 1.812,
    '0.08': 1.751,
    '0.09': 1.695,
    '0.10': 1.645,
    '0.15': 1.44,
    '0.20': 1.282,
  }
  return map[alpha.value.toFixed(2)] ?? 1.96
})

// p 值 = 2 * P(Z > |z_obs|)
const pValue = computed(() => {
  const az = Math.abs(zObs.value)
  // 用对称正态概率近似（数值积分）
  let prob = 0
  const step = 0.001
  for (let x = az; x < 8; x += step) {
    prob += normDensity(x) * step
  }
  return Math.min(1, 2 * prob)
})

const reject = computed(() => pValue.value < alpha.value)

const density = computed<[number, number][]>(() => {
  const pts: [number, number][] = []
  for (let i = 0; i <= N; i++) {
    const x = xMin + ((xMax - xMin) * i) / N
    pts.push([Number(x.toFixed(3)), Number(normDensity(x).toFixed(5))])
  }
  return pts
})

// 阴影区域：|z| 以上的双侧尾部
const shadeSeries = computed(() => {
  const az = Math.abs(zObs.value)
  const data: [number, number | null][] = []
  for (let i = 0; i <= N; i++) {
    const x = xMin + ((xMax - xMin) * i) / N
    const inShade = Math.abs(x) >= az
    data.push([Number(x.toFixed(3)), inShade ? Number(normDensity(x).toFixed(5)) : null])
  }
  return { data }
})

const option = computed(() => ({
  animation: true,
  grid: { left: 55, right: 20, top: 40, bottom: 45 },
  tooltip: {
    trigger: 'axis',
    formatter: (ps: any) => {
      const p = Array.isArray(ps) ? ps[0] : ps
      if (!p) return ''
      const v = p.value as number[]
      return `z = ${Number(v[0]).toFixed(2)}<br/>φ(z) = ${Number(v[1]).toFixed(4)}`
    },
  },
  xAxis: {
    type: 'value',
    name: '检验统计量 z',
    nameLocation: 'middle',
    nameGap: 30,
    min: xMin,
    max: xMax,
    axisLabel: { fontSize: 11 },
  },
  yAxis: {
    type: 'value',
    name: 'φ(z)',
    nameLocation: 'middle',
    nameGap: 40,
    min: 0,
    axisLabel: { fontSize: 11 },
  },
  series: [
    {
      name: 'H0 下 N(0,1)',
      type: 'line',
      smooth: true,
      symbol: 'none',
      data: density.value,
      lineStyle: { width: 3, color: C.value.primary },
      z: 3,
    },
    {
      name: 'p 值（阴影）',
      type: 'line',
      smooth: true,
      symbol: 'none',
      data: shadeSeries.value.data,
      lineStyle: { width: 0, color: 'transparent' },
      areaStyle: { color: withAlpha(C.value.danger, 0.55) },
      silent: true,
      z: 1,
    },
    {
      name: '观测值 z',
      type: 'line',
      symbol: 'none',
      data: [],
      markLine: {
        silent: true,
        symbol: 'none',
        label: { fontSize: 11, color: C.value.danger, formatter: `z = ${zObs.value.toFixed(2)}` },
        lineStyle: { color: C.value.danger, width: 2.5 },
        data: [{ xAxis: zObs.value }],
      },
    },
    {
      name: '临界值',
      type: 'line',
      symbol: 'none',
      data: [],
      markLine: {
        silent: true,
        symbol: 'none',
        label: { fontSize: 11, color: C.value.warning, formatter: `±z${(alpha.value * 100).toFixed(0)}% = ±${zCrit.value.toFixed(2)}` },
        lineStyle: { color: C.value.warning, type: 'dashed', width: 1.5 },
        data: [{ xAxis: -zCrit.value }, { xAxis: zCrit.value }],
      },
    },
  ],
}))
</script>

<template>
  <div class="pvalue">
    <ThemedChart class="chart" :option="option" autoresize />

    <div class="controls">
      <div class="control-row">
        <span class="control-label">观测统计量 z</span>
        <input v-model.number="zObs" type="range" min="-4" max="4" step="0.05" class="slider" />
        <span class="control-value">{{ zObs.toFixed(2) }}</span>
      </div>
      <div class="control-row">
        <span class="control-label">显著性水平 α</span>
        <input v-model.number="alpha" type="range" min="0.01" max="0.20" step="0.01" class="slider" />
        <span class="control-value">{{ (alpha * 100).toFixed(0) }}%</span>
      </div>
      <div class="result-row">
        <div class="result-box">
          <span class="muted">p 值（双侧）</span>
          <strong>{{ pValue.toFixed(4) }}</strong>
        </div>
        <div class="result-box">
          <span class="muted">临界值 ±z</span>
          <strong>±{{ zCrit.toFixed(2) }}</strong>
        </div>
        <div class="result-box" :class="reject ? 'red' : 'green'">
          <span class="muted">结论</span>
          <strong>{{ reject ? '拒绝 H0' : '不拒绝 H0' }}</strong>
        </div>
      </div>
      <p class="hint">
        阴影面积就是 p 值——在 H0 为真的前提下，出现「比当前观测更极端」的数据的概率。
        p 值小于 α（或 |z| 越过临界值）时拒绝 H0；z 滑向 0，p 值变大，证据变弱。
      </p>
    </div>
  </div>
</template>

<style scoped>
.pvalue { padding: 16px; }
.chart { height: 320px; }
.controls { margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border); display: flex; flex-direction: column; gap: 10px; }
.control-row { display: flex; align-items: center; gap: 12px; }
.control-label { width: 100px; font-size: 13px; color: var(--text-2); flex-shrink: 0; }
.slider { flex: 1; accent-color: var(--primary); cursor: pointer; }
.control-value { width: 40px; font-size: 13px; font-weight: 600; color: var(--primary); text-align: right; flex-shrink: 0; }
.result-row { display: flex; align-items: center; gap: 10px; margin-top: 4px; flex-wrap: wrap; }
.result-box { flex: 1; padding: 8px 10px; border-radius: var(--radius-sm); background: var(--bg-hover); text-align: center; display: flex; flex-direction: column; gap: 2px; }
.result-box strong { font-size: 15px; }
.result-box.green strong { color: var(--success, #16a34a); }
.result-box.red strong { color: var(--danger, #dc2626); }
.muted { font-size: 12px; color: var(--text-3); }
.hint { margin-top: 8px; font-size: 12px; color: var(--text-3); line-height: 1.7; }
</style>
