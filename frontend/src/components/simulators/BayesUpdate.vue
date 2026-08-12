<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent])

// 贝叶斯更新：把「某信号明日上涨概率 θ」视为未知参数
// 先验 Beta(a,b) + 数据(k/n) → 后验 Beta(a+k, b+n-k)
// 教学模拟（非真实数据）

const props = defineProps<{
  params?: Record<string, unknown>
}>()

const a = ref(typeof props.params?.a === 'number' ? props.params.a : 2)
const b = ref(typeof props.params?.b === 'number' ? props.params.b : 2)
const n = ref(typeof props.params?.n === 'number' ? props.params.n : 10)
const k = ref(typeof props.params?.k === 'number' ? props.params.k : 6)

// k 不得超过 n
watch(n, (v) => {
  if (k.value > v) k.value = v
})
watch(k, (v) => {
  if (v > n.value) k.value = n.value
})

const M = 200 // [0,1] 上的采样点数

// Beta 密度核：x^(a-1)(1-x)^(b-1)，数值归一化（梯形法）
function betaDensity(x: number, alpha: number, beta: number) {
  if (x <= 0 || x >= 1) return 0
  return Math.exp((alpha - 1) * Math.log(x) + (beta - 1) * Math.log(1 - x))
}

function betaCurve(alpha: number, beta: number): [number, number][] {
  const pts: [number, number][] = []
  const raw: number[] = []
  const dx = 1 / M
  for (let i = 0; i <= M; i++) {
    const x = (i / M) * 1
    const v = betaDensity(x, alpha, beta)
    raw.push(v)
    pts.push([Number(x.toFixed(3)), v])
  }
  // 梯形法积分
  let area = 0
  for (let i = 0; i < M; i++) area += ((raw[i] + raw[i + 1]) / 2) * dx
  if (area > 0) {
    for (let i = 0; i <= M; i++) pts[i][1] = Number((raw[i] / area).toFixed(5))
  }
  return pts
}

const prior = computed(() => betaCurve(a.value, b.value))
const posterior = computed(() => betaCurve(a.value + k.value, b.value + n.value - k.value))

const postMean = computed(() => (a.value + k.value) / (a.value + b.value + n.value))

const priorMean = computed(() => a.value / (a.value + b.value))

const option = computed(() => ({
  animation: true,
  grid: { left: 55, right: 20, top: 40, bottom: 40 },
  tooltip: {
    trigger: 'axis',
    formatter: (params: any) => {
      const arr = Array.isArray(params) ? params : [params]
      return arr
        .map((pa: any) => {
          // 曲线数据为 [x,y] 数组，需取分量，否则 Number(数组)=NaN
          const isArr = Array.isArray(pa.value)
          const x = isArr ? pa.value[0] : pa.axisValue
          const y = isArr ? pa.value[1] : pa.value
          return `${pa.seriesName}: θ=${Number(x).toFixed(3)}，密度=${Number(y).toFixed(4)}`
        })
        .join('<br/>')
    },
  },
  legend: { top: 0, textStyle: { fontSize: 12 } },
  xAxis: {
    type: 'value',
    name: 'θ（上涨概率）',
    nameLocation: 'middle',
    nameGap: 28,
    min: 0,
    max: 1,
    axisLabel: { fontSize: 11, formatter: (v: number) => `${(v * 100).toFixed(0)}%` },
  },
  yAxis: {
    type: 'value',
    name: '密度',
    nameLocation: 'middle',
    nameGap: 40,
    axisLabel: { fontSize: 11 },
  },
  series: [
    {
      name: `先验 Beta(${a.value}, ${b.value})`,
      type: 'line',
      smooth: true,
      symbol: 'none',
      data: prior.value,
      lineStyle: { width: 2, color: '#64748b', type: 'dashed' },
      itemStyle: { color: '#64748b' },
      areaStyle: { color: 'rgba(100, 116, 139, 0.10)' },
    },
    {
      name: `后验 Beta(${a.value + k.value}, ${b.value + n.value - k.value})`,
      type: 'line',
      smooth: true,
      symbol: 'none',
      data: posterior.value,
      lineStyle: { width: 3, color: '#2563eb' },
      itemStyle: { color: '#2563eb' },
      areaStyle: { color: 'rgba(37, 99, 235, 0.12)' },
    },
  ],
}))
</script>

<template>
  <div class="bayes-update">
    <VChart class="chart" :option="option" autoresize />

    <div class="controls">
      <div class="control-row">
        <span class="control-label">先验 a</span>
        <input v-model.number="a" type="range" min="1" max="10" step="1" class="slider" />
        <span class="control-value">{{ a }}</span>
      </div>
      <div class="control-row">
        <span class="control-label">先验 b</span>
        <input v-model.number="b" type="range" min="1" max="10" step="1" class="slider" />
        <span class="control-value">{{ b }}</span>
      </div>
      <div class="control-row">
        <span class="control-label">观察次数 n</span>
        <input v-model.number="n" type="range" min="0" max="50" step="1" class="slider" />
        <span class="control-value">{{ n }}</span>
      </div>
      <div class="control-row">
        <span class="control-label">上涨次数 k</span>
        <input v-model.number="k" type="range" min="0" :max="n" step="1" class="slider" />
        <span class="control-value">{{ k }}</span>
      </div>
      <div class="result-row">
        <div class="result-box">
          <span class="muted">先验均值 a/(a+b)</span>
          <strong>{{ (priorMean * 100).toFixed(1) }}%</strong>
        </div>
        <div class="result-box">
          <span class="muted">样本频率 k/n</span>
          <strong>{{ n > 0 ? ((k / n) * 100).toFixed(1) + '%' : '—' }}</strong>
        </div>
        <div class="result-box post">
          <span class="muted">后验均值 (a+k)/(a+b+n)</span>
          <strong>{{ (postMean * 100).toFixed(1) }}%</strong>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.bayes-update { padding: 16px; }
.chart { height: 320px; }
.controls { margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border); display: flex; flex-direction: column; gap: 10px; }
.control-row { display: flex; align-items: center; gap: 12px; }
.control-label { width: 80px; font-size: 13px; color: var(--text-2); flex-shrink: 0; }
.slider { flex: 1; accent-color: var(--primary); cursor: pointer; }
.control-value { width: 48px; font-size: 13px; font-weight: 600; color: var(--primary); text-align: right; flex-shrink: 0; }
.result-row { display: flex; gap: 10px; margin-top: 8px; }
.result-box {
  flex: 1; padding: 8px 10px; border-radius: var(--radius-sm);
  background: var(--bg-hover); text-align: center;
  display: flex; flex-direction: column; gap: 2px;
}
.result-box strong { font-size: 16px; }
.result-box.post strong { color: var(--primary); }
.muted { font-size: 12px; color: var(--text-3); }
</style>
