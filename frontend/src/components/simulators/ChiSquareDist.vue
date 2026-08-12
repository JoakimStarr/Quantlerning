<script setup lang="ts">
import { computed, ref } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, MarkLineComponent } from 'echarts/components'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, MarkLineComponent])

// 卡方分布 χ²(k)：自由度为 k 时，k 个独立标准正态的平方和
// 拖动自由度，观察形状变化：均值 = k、众数 = k-2（k>2 时），右偏且随 k 增大趋近对称
// （示意演示，非真实数据）

const props = defineProps<{
  params?: Record<string, unknown>
}>()

const df = ref(typeof props.params?.df === 'number' ? props.params.df : 5)

// 伽马分布密度（用 ln 求值避免溢出）：χ²(k) = Gamma(shape=k/2, rate=1/2)
function gammaLn(z: number): number {
  // Stirling + Lanczos 近似（对整数半值足够）
  if (z < 0.5) return 0
  const g = 7
  const C = [
    0.99999999999980993, 676.5203681218851, -1259.1392167224028,
    771.32342877765313, -176.61502916214059, 12.507343278686905,
    -0.13857109526572012, 9.9843695780195716e-6, 1.5056327351493116e-7,
  ]
  if (z < 0.5) return Math.log(Math.PI / Math.sin(Math.PI * z)) - gammaLn(1 - z)
  z -= 1
  let x = C[0]
  for (let i = 1; i < g + 2; i++) x += C[i] / (z + i)
  const t = z + g + 0.5
  return 0.5 * Math.log(2 * Math.PI) + (z + 0.5) * Math.log(t) - t + Math.log(x)
}

function chi2Density(x: number, k: number) {
  if (x <= 0) return 0
  const shape = k / 2
  const rate = 0.5
  const ln = (shape - 1) * Math.log(x) + shape * Math.log(rate) - rate * x - gammaLn(shape)
  return Math.exp(ln)
}

const N = 300
const xMax = computed(() => Math.min(60, df.value + 6 * Math.sqrt(2 * df.value) + 6))

const density = computed<[number, number][]>(() => {
  const pts: [number, number][] = []
  for (let i = 0; i <= N; i++) {
    const x = (xMax.value * i) / N
    pts.push([Number(x.toFixed(3)), Number(chi2Density(x, df.value).toFixed(6))])
  }
  return pts
})

// α=0.05 的右侧临界值（近似：用正态修正 (z + sqrt(2k-1))²/2）
const z005 = 1.645
const chiCrit = computed(() => {
  const approx = (z005 + Math.sqrt(2 * df.value - 1)) ** 2 / 2
  return Number(approx.toFixed(2))
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
      return `x = ${Number(v[0]).toFixed(2)}<br/>f(x) = ${Number(v[1]).toFixed(4)}`
    },
  },
  xAxis: {
    type: 'value',
    name: 'x',
    nameLocation: 'middle',
    nameGap: 30,
    min: 0,
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
      name: `χ²(${df})`,
      type: 'line',
      smooth: true,
      symbol: 'none',
      data: density.value,
      lineStyle: { width: 3, color: '#2563eb' },
      areaStyle: { color: 'rgba(37, 99, 235, 0.10)' },
      z: 3,
    },
    {
      name: 'α=5% 临界值',
      type: 'line',
      symbol: 'none',
      data: [],
      markLine: {
        silent: true,
        symbol: 'none',
        label: { fontSize: 11, color: '#dc2626', formatter: `χ²₀.₀₅≈${chiCrit.value}` },
        lineStyle: { color: '#dc2626', type: 'dashed', width: 1.5 },
        data: [{ xAxis: chiCrit.value }],
      },
    },
  ],
}))

const mode = computed(() => Math.max(0, df.value - 2))
</script>

<template>
  <div class="chi">
    <VChart class="chart" :option="option" autoresize />

    <div class="controls">
      <div class="control-row">
        <span class="control-label">自由度 k</span>
        <input v-model.number="df" type="range" min="1" max="30" step="1" class="slider" />
        <span class="control-value">{{ df }}</span>
      </div>
      <div class="result-row">
        <div class="result-box">
          <span class="muted">均值</span>
          <strong>{{ df }}</strong>
        </div>
        <div class="result-box">
          <span class="muted">众数（k>2 时）</span>
          <strong>{{ mode }}</strong>
        </div>
        <div class="result-box">
          <span class="muted">方差</span>
          <strong>{{ 2 * df }}</strong>
        </div>
      </div>
      <p class="hint">
        卡方分布是右偏的，自由度越大越接近对称（并趋于正态）。它是拟合优度检验与
        独立性检验的检验统计量分布：统计量 χ² 越大，越说明观测与期望不符。
      </p>
    </div>
  </div>
</template>

<style scoped>
.chi { padding: 16px; }
.chart { height: 320px; }
.controls { margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border); display: flex; flex-direction: column; gap: 10px; }
.control-row { display: flex; align-items: center; gap: 12px; }
.control-label { width: 76px; font-size: 13px; color: var(--text-2); flex-shrink: 0; }
.slider { flex: 1; accent-color: var(--primary); cursor: pointer; }
.control-value { width: 40px; font-size: 13px; font-weight: 600; color: var(--primary); text-align: right; flex-shrink: 0; }
.result-row { display: flex; align-items: center; gap: 10px; margin-top: 4px; }
.result-box { flex: 1; padding: 8px 10px; border-radius: var(--radius-sm); background: var(--bg-hover); text-align: center; display: flex; flex-direction: column; gap: 2px; }
.result-box strong { font-size: 15px; color: var(--primary); }
.muted { font-size: 12px; color: var(--text-3); }
.hint { margin-top: 8px; font-size: 12px; color: var(--text-3); line-height: 1.7; }
</style>
