<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C, withAlpha } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, MarkLineComponent } from 'echarts/components'

use([CanvasRenderer, BarChart, LineChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent])

// 中心极限定理 / 抽样分布：总体是右偏的指数分布（均值 1、标准差 1），
// 反复抽取样本、计算样本均值，直方图随样本量 n 增大趋近正态，且宽度按 σ/√n 收窄
// （随机模拟，非真实数据）

const props = defineProps<{
  params?: Record<string, unknown>
}>()

const n = ref(typeof props.params?.n === 'number' ? props.params.n : 10)
const k = ref(3000)

const POP_MEAN = 1
const POP_SD = 1

let seed = 20240812
function rng() {
  seed = (seed * 1103515245 + 12345) % 2147483648
  return seed / 2147483648
}

// 指数分布抽样（逆变换法）
function randExp() {
  return -Math.log(1 - rng() + 1e-9)
}

const means = ref<number[]>([])

function regenerate() {
  const out: number[] = []
  for (let i = 0; i < k.value; i++) {
    let sum = 0
    for (let j = 0; j < n.value; j++) sum += randExp()
    out.push(sum / n.value)
  }
  means.value = out
}

regenerate()

watch([n, k], () => regenerate())

const BINS = 32
const observedSd = computed(() => {
  const m = means.value.reduce((s, v) => s + v, 0) / means.value.length
  const v = means.value.reduce((s, x) => s + (x - m) ** 2, 0) / means.value.length
  return Math.sqrt(v)
})

// 直方图分箱
const hist = computed(() => {
  const lo = POP_MEAN - 4 * (POP_SD / Math.sqrt(n.value))
  const hi = POP_MEAN + 4 * (POP_SD / Math.sqrt(n.value))
  const width = (hi - lo) / BINS
  const counts = new Array(BINS).fill(0) as number[]
  for (const m of means.value) {
    const idx = Math.floor((m - lo) / width)
    if (idx >= 0 && idx < BINS) counts[idx]++
  }
  const freq = counts.map((c) => c / means.value.length / width)
  return { lo, hi, width, freq }
})

// 理论正态密度 N(μ, σ²/n)（叠在直方图上，尺度对齐到频率）
const normalCurve = computed<[number, number][]>(() => {
  const { lo, hi } = hist.value
  const se = POP_SD / Math.sqrt(n.value)
  const pts: [number, number][] = []
  for (let i = 0; i <= 120; i++) {
    const x = lo + ((hi - lo) * i) / 120
    const y = (1 / (se * Math.sqrt(2 * Math.PI))) * Math.exp(-((x - POP_MEAN) ** 2) / (2 * se * se))
    pts.push([Number(x.toFixed(4)), Number(y.toFixed(5))])
  }
  return pts
})

const option = computed(() => {
  const { lo, hi, width, freq } = hist.value
  const barData = freq.map((f, i) => [Number((lo + width * (i + 0.5)).toFixed(4)), Number(f.toFixed(5))])
  return {
    animation: true,
    grid: { left: 60, right: 20, top: 40, bottom: 45 },
    tooltip: {
      trigger: 'axis',
      formatter: (ps: any) => {
        const arr = Array.isArray(ps) ? ps : [ps]
        return arr
          .map((pa: any) => {
            const v = pa.value as number[]
            return `${pa.seriesName}: ${Number(v[1]).toFixed(4)}`
          })
          .join('<br/>')
      },
    },
    legend: { top: 0, textStyle: { fontSize: 12 } },
    xAxis: {
      type: 'value',
      name: '样本均值 x̄',
      nameLocation: 'middle',
      nameGap: 30,
      min: lo,
      max: hi,
      axisLabel: { fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      name: '频率',
      nameLocation: 'middle',
      nameGap: 48,
      axisLabel: { fontSize: 11 },
    },
    series: [
      {
        name: '样本均值直方图',
        type: 'bar',
        data: barData,
        barWidth: '98%',
        itemStyle: { color: withAlpha(C.value.primary, 0.35) },
        z: 1,
      },
      {
        name: `理论 N(${POP_MEAN}, (${POP_SD}/√${n.value})²)`,
        type: 'line',
        smooth: true,
        symbol: 'none',
        data: normalCurve.value,
        lineStyle: { width: 3, color: C.value.danger },
        z: 5,
      },
      {
        name: '总体均值 μ',
        type: 'line',
        symbol: 'none',
        data: [],
        markLine: {
          silent: true,
          symbol: 'none',
          label: { fontSize: 11, color: C.value.warning, formatter: `μ = ${POP_MEAN}` },
          lineStyle: { color: C.value.warning, type: 'dashed', width: 1.5 },
          data: [{ xAxis: POP_MEAN }],
        },
      },
    ],
  }
})
</script>

<template>
  <div class="sampling">
    <ThemedChart class="chart" :option="option" autoresize />

    <div class="controls">
      <div class="control-row">
        <span class="control-label">每个样本的 n</span>
        <input v-model.number="n" type="range" min="2" max="120" step="1" class="slider" />
        <span class="control-value">{{ n }}</span>
      </div>
      <div class="result-row">
        <div class="result-box">
          <span class="muted">样本均值标准差（实测）</span>
          <strong>{{ observedSd.toFixed(3) }}</strong>
        </div>
        <div class="result-box">
          <span class="muted">理论标准误 σ/√n</span>
          <strong>{{ (POP_SD / Math.sqrt(n)).toFixed(3) }}</strong>
        </div>
        <button class="btn" @click="regenerate">重新抽样</button>
      </div>
      <p class="hint">
        总体是右偏的指数分布（μ = 1，σ = 1）。无论总体多歪，样本均值的分布都随 n 增大趋近正态——
        这就是中心极限定理。同时直方图越收越窄，实测标准差逼近理论标准误 σ/√n。
      </p>
    </div>
  </div>
</template>

<style scoped>
.sampling { padding: 16px; }
.chart { height: 320px; }
.controls { margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border); display: flex; flex-direction: column; gap: 10px; }
.control-row { display: flex; align-items: center; gap: 12px; }
.control-label { width: 110px; font-size: 13px; color: var(--text-2); flex-shrink: 0; }
.slider { flex: 1; accent-color: var(--primary); cursor: pointer; }
.control-value { width: 40px; font-size: 13px; font-weight: 600; color: var(--primary); text-align: right; flex-shrink: 0; }
.result-row { display: flex; align-items: center; gap: 10px; margin-top: 4px; flex-wrap: wrap; }
.result-box { flex: 1; padding: 8px 10px; border-radius: var(--radius-sm); background: var(--bg-hover); text-align: center; display: flex; flex-direction: column; gap: 2px; }
.result-box strong { font-size: 15px; color: var(--primary); }
.btn {
  padding: 5px 14px; border: 1px solid var(--border); border-radius: var(--radius-sm);
  background: var(--bg-card); color: var(--text-1); font-size: 13px; cursor: pointer;
  transition: all 0.15s;
}
.btn:hover { border-color: var(--primary); color: var(--primary); }
.muted { font-size: 12px; color: var(--text-3); }
.hint { margin-top: 8px; font-size: 12px; color: var(--text-3); line-height: 1.7; }
</style>
