<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, ScatterChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, MarkLineComponent } from 'echarts/components'

use([CanvasRenderer, LineChart, ScatterChart, GridComponent, TooltipComponent, MarkLineComponent])

// 置信区间模拟：从 N(μ, σ²) 重复抽样，每次构造 95% 置信区间
// 观察「约 95% 的区间覆盖真值」（模拟演示，非真实数据）

const props = defineProps<{
  params?: Record<string, unknown>
}>()

const mu = ref(typeof props.params?.mu === 'number' ? props.params.mu : 0)
const sigma = ref(typeof props.params?.sigma === 'number' ? props.params.sigma : 1)
const n = ref(typeof props.params?.n === 'number' ? props.params.n : 30)
const numIntervals = ref(20)

// 抽样种子（固定初值，保证每次重抽结果不同）
let seed = 42

function rng() {
  seed = (seed * 1103515245 + 12345) % 2147483648
  return seed / 2147483648
}

function randn() {
  // Box-Muller
  const u1 = Math.max(rng(), 1e-9)
  const u2 = rng()
  return Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2)
}

const samples = ref<Array<{ lo: number; hi: number; covers: boolean }>>([])

function regenerate() {
  const out: Array<{ lo: number; hi: number; covers: boolean }> = []
  for (let i = 0; i < numIntervals.value; i++) {
    let sum = 0
    for (let j = 0; j < n.value; j++) sum += mu.value + sigma.value * randn()
    const xbar = sum / n.value
    const se = sigma.value / Math.sqrt(n.value)
    const lo = xbar - 1.96 * se
    const hi = xbar + 1.96 * se
    out.push({ lo, hi, covers: lo <= mu.value && mu.value <= hi })
  }
  samples.value = out
}

regenerate()

watch([mu, sigma, n, numIntervals], () => regenerate())

const coverCount = computed(() => samples.value.filter((s) => s.covers).length)
const coverRate = computed(() =>
  samples.value.length ? Math.round((coverCount.value / samples.value.length) * 100) : 0,
)

// 区间集合：每个区间一条横线（离散 y 轴 = 抽样序号）
const intervalSeries = computed(() =>
  samples.value.map((s, i) => ({
    name: `区间 ${i + 1}`,
    type: 'line' as const,
    xAxisIndex: 0,
    yAxisIndex: 0,
    symbol: 'none',
    data: [
      [s.lo, i + 1],
      [s.hi, i + 1],
    ],
    lineStyle: { width: 3, color: s.covers ? C.value.success : C.value.danger },
  })),
)

const meanSeries = computed(() => ({
  name: '样本均值',
  type: 'scatter' as const,
  xAxisIndex: 0,
  yAxisIndex: 0,
  symbolSize: 5,
  data: samples.value.map((s, i) => [s.lo + (s.hi - s.lo) / 2, i + 1]),
  itemStyle: { color: C.value.primary },
}))

const option = computed(() => {
  const xMax = mu.value + 4 * sigma.value
  const xMin = mu.value - 4 * sigma.value
  return {
    animation: true,
    grid: { left: 55, right: 24, top: 40, bottom: 45 },
    tooltip: {
      trigger: 'axis',
      formatter: (ps: any[]) => {
        const p = ps[0]
        if (!p) return ''
        return `区间 ${p.value[1]}：${p.value[0].toFixed(2)}`
      },
    },
    xAxis: {
      type: 'value',
      name: '样本均值与区间',
      nameLocation: 'middle',
      nameGap: 30,
      min: xMin,
      max: xMax,
      axisLabel: { fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      name: '抽样批次',
      nameLocation: 'middle',
      nameGap: 34,
      min: 0,
      max: numIntervals.value + 1,
      splitLine: { show: false },
      axisLabel: { fontSize: 10 },
    },
    series: [
      ...intervalSeries.value,
      meanSeries.value,
      {
        name: '真值 μ',
        type: 'line',
        xAxisIndex: 0,
        yAxisIndex: 0,
        symbol: 'none',
        data: [],
        markLine: {
          silent: true,
          symbol: 'none',
          label: { show: true, fontSize: 11, color: C.value.warning, formatter: `μ = ${mu.value.toFixed(2)}` },
          lineStyle: { color: C.value.warning, type: 'dashed', width: 1.5 },
          data: [{ xAxis: mu.value }],
        },
      },
    ],
  }
})
</script>

<template>
  <div class="ci-sim">
    <ThemedChart class="chart" :option="option" autoresize />

    <div class="controls">
      <div class="control-row">
        <span class="control-label">总体均值 μ</span>
        <input v-model.number="mu" type="range" min="-2" max="2" step="0.1" class="slider" />
        <span class="control-value">{{ mu.toFixed(1) }}</span>
      </div>
      <div class="control-row">
        <span class="control-label">总体标准差 σ</span>
        <input v-model.number="sigma" type="range" min="0.5" max="3" step="0.1" class="slider" />
        <span class="control-value">{{ sigma.toFixed(1) }}</span>
      </div>
      <div class="control-row">
        <span class="control-label">样本量 n</span>
        <input v-model.number="n" type="range" min="5" max="200" step="5" class="slider" />
        <span class="control-value">{{ n }}</span>
      </div>
      <div class="control-row">
        <span class="control-label">抽样批次</span>
        <input v-model.number="numIntervals" type="range" min="5" max="50" step="5" class="slider" />
        <span class="control-value">{{ numIntervals }}</span>
      </div>
      <div class="result-row">
        <div class="result-box">
          <span class="muted">覆盖区间数</span>
          <strong :class="{ green: coverRate >= 95, red: coverRate < 95 }">{{ coverCount }}/{{ samples.length }}</strong>
        </div>
        <div class="result-box">
          <span class="muted">覆盖率</span>
          <strong :class="{ green: coverRate >= 95, red: coverRate < 95 }">{{ coverRate }}%</strong>
        </div>
        <button class="btn" @click="regenerate">重新抽样</button>
      </div>
      <p class="hint">
        绿色 = 区间覆盖真值 μ，红色 = 未覆盖。重复抽样次数越多，覆盖率越接近 95%——
        这就是频率学派对置信区间的定义：约 95% 的区间会覆盖真值。
      </p>
    </div>
  </div>
</template>

<style scoped>
.ci-sim { padding: 16px; }
.chart { height: 360px; }
.controls { margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border); display: flex; flex-direction: column; gap: 10px; }
.control-row { display: flex; align-items: center; gap: 12px; }
.control-label { width: 88px; font-size: 13px; color: var(--text-2); flex-shrink: 0; }
.slider { flex: 1; accent-color: var(--primary); cursor: pointer; }
.control-value { width: 56px; font-size: 13px; font-weight: 600; color: var(--primary); text-align: right; flex-shrink: 0; }
.result-row { display: flex; align-items: center; gap: 10px; margin-top: 8px; flex-wrap: wrap; }
.result-box { flex: 1; padding: 8px 10px; border-radius: var(--radius-sm); background: var(--bg-hover); text-align: center; display: flex; flex-direction: column; gap: 2px; }
.result-box strong { font-size: 16px; }
.result-box strong.green { color: var(--success, #16a34a); }
.result-box strong.red { color: var(--danger, #dc2626); }
.btn {
  padding: 5px 14px; border: 1px solid var(--border); border-radius: var(--radius-sm);
  background: var(--bg-card); color: var(--text-1); font-size: 13px; cursor: pointer;
  transition: all 0.15s;
}
.btn:hover { border-color: var(--primary); color: var(--primary); }
.muted { font-size: 12px; color: var(--text-3); }
.hint { margin-top: 8px; font-size: 12px; color: var(--text-3); line-height: 1.7; }
</style>
