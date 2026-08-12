<script setup lang="ts">
import { computed, ref } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'

use([CanvasRenderer, BarChart, LineChart, GridComponent, TooltipComponent, LegendComponent])

// 二项分布 B(n,p)：n/p 滑块 → 概率柱状图 + 可选正态逼近
// 教学模拟（非真实数据）

const props = defineProps<{
  params?: Record<string, unknown>
}>()

const n = ref(typeof props.params?.n === 'number' ? props.params.n : 20)
const p = ref(typeof props.params?.p === 'number' ? props.params.p : 0.5)
const showNormal = ref(false) // 默认关闭，勾选后叠加正态逼近（呼应 caption）

// log-gamma（Lanczos 近似），用于稳定计算组合数 C(n,k)
function lgamma(x: number): number {
  const g = 7
  const c = [
    0.99999999999980993, 676.5203681218851, -1259.1392167224028,
    771.32342877765313, -176.61502916214059, 12.507343278686905,
    -0.13857109526572012, 9.9843695780195716e-6, 1.5056327351493116e-7,
  ]
  if (x < 0.5) {
    return Math.log(Math.PI / Math.sin(Math.PI * x)) - lgamma(1 - x)
  }
  x -= 1
  let a = c[0]
  const t = x + g + 0.5
  for (let i = 1; i < g + 2; i++) a += c[i] / (x + i)
  return 0.5 * Math.log(2 * Math.PI) + (x + 0.5) * Math.log(t) - t + Math.log(a)
}

function logComb(nn: number, k: number) {
  return lgamma(nn + 1) - lgamma(k + 1) - lgamma(nn - k + 1)
}

// 概率质量 P(X=k)
const pmf = computed<[number, number][]>(() => {
  const out: [number, number][] = []
  for (let k = 0; k <= n.value; k++) {
    out.push([k, Number(Math.exp(logComb(n.value, k) + k * Math.log(p.value) + (n.value - k) * Math.log(1 - p.value)).toFixed(5))])
  }
  return out
})

// 正态逼近 N(np, np(1-p)) 的密度（连续曲线，叠加在柱状图上）
const normalCurve = computed<[number, number][]>(() => {
  const mean = n.value * p.value
  const sd = Math.sqrt(n.value * p.value * (1 - p.value))
  if (sd === 0) return []
  const pts: [number, number][] = []
  const lo = Math.max(0, mean - 3.5 * sd)
  const hi = Math.min(n.value, mean + 3.5 * sd)
  for (let i = 0; i <= 100; i++) {
    const x = lo + ((hi - lo) * i) / 100
    const y = (1 / (sd * Math.sqrt(2 * Math.PI))) * Math.exp(-((x - mean) ** 2) / (2 * sd * sd))
    pts.push([Number(x.toFixed(3)), Number(y.toFixed(5))])
  }
  return pts
})

const stats = computed(() => ({
  mean: Number((n.value * p.value).toFixed(2)),
  variance: Number((n.value * p.value * (1 - p.value)).toFixed(2)),
}))

const option = computed(() => ({
  animation: true,
  grid: { left: 55, right: 20, top: 40, bottom: 40 },
  tooltip: {
    trigger: 'axis',
    axisPointer: { type: 'shadow' },
    formatter: (params: any) => {
      const arr = Array.isArray(params) ? params : [params]
      return arr
        .map((pa: any) => {
          // 数据项是 [k, y] 数组时 value 为数组，需取分量
          const isArr = Array.isArray(pa.value)
          const x = isArr ? pa.value[0] : pa.axisValue
          const y = isArr ? pa.value[1] : pa.value
          const label = pa.seriesName.includes('正态')
            ? `x≈${Number(x).toFixed(1)}`
            : `k=${x}`
          return `${label}｜${pa.seriesName}: ${Number(y).toFixed(4)}`
        })
        .join('<br/>')
    },
  },
  legend: { top: 0, textStyle: { fontSize: 12 } },
  xAxis: {
    type: 'value',
    name: 'k（成功次数）',
    nameLocation: 'middle',
    nameGap: 28,
    min: 0,
    max: n.value,
    interval: Math.max(1, Math.floor(n.value / 10)),
    axisLabel: { fontSize: 11 },
  },
  yAxis: {
    type: 'value',
    name: 'P(X=k)',
    nameLocation: 'middle',
    nameGap: 40,
    axisLabel: { fontSize: 11 },
  },
  series: [
    {
      name: 'B(n,p)',
      type: 'bar',
      data: pmf.value,
      barWidth: '60%',
      itemStyle: { color: 'rgba(37, 99, 235, 0.55)', borderRadius: [2, 2, 0, 0] },
    },
    ...(showNormal.value && normalCurve.value.length
      ? [
          {
            name: '正态逼近 N(np, np(1-p))',
            type: 'line' as const,
            smooth: true,
            symbol: 'none',
            data: normalCurve.value,
            lineStyle: { width: 2.5, color: '#d97706' },
            itemStyle: { color: '#d97706' },
          },
        ]
      : []),
  ],
}))
</script>

<template>
  <div class="binomial-dist">
    <VChart class="chart" :option="option" autoresize />

    <div class="controls">
      <div class="control-row">
        <span class="control-label">试验次数 n</span>
        <input v-model.number="n" type="range" min="1" max="50" step="1" class="slider" />
        <span class="control-value">{{ n }}</span>
      </div>
      <div class="control-row">
        <span class="control-label">成功概率 p</span>
        <input v-model.number="p" type="range" min="0.05" max="0.95" step="0.05" class="slider" />
        <span class="control-value">{{ (p * 100).toFixed(0) }}%</span>
      </div>
      <div class="bottom-row">
        <label class="toggle">
          <input v-model="showNormal" type="checkbox" class="checkbox" />
          正态逼近
        </label>
        <div class="stats">
          <span class="stat-chip">期望 np = <strong>{{ stats.mean }}</strong></span>
          <span class="stat-chip">方差 np(1−p) = <strong>{{ stats.variance }}</strong></span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.binomial-dist { padding: 16px; }
.chart { height: 320px; }
.controls { margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border); display: flex; flex-direction: column; gap: 10px; }
.control-row { display: flex; align-items: center; gap: 12px; }
.control-label { width: 80px; font-size: 13px; color: var(--text-2); flex-shrink: 0; }
.slider { flex: 1; accent-color: var(--primary); cursor: pointer; }
.control-value { width: 48px; font-size: 13px; font-weight: 600; color: var(--primary); text-align: right; flex-shrink: 0; }
.bottom-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-top: 4px; }
.toggle { display: flex; align-items: center; gap: 6px; font-size: 13px; color: var(--text-2); cursor: pointer; }
.checkbox { accent-color: var(--primary); cursor: pointer; }
.stats { display: flex; gap: 10px; }
.stat-chip {
  font-size: 12.5px; color: var(--text-3);
  padding: 4px 10px; border-radius: 999px; background: var(--bg-hover);
}
.stat-chip strong { color: var(--primary); }
</style>
