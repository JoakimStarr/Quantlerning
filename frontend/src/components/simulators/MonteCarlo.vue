<script setup lang="ts">
import { computed, ref } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, BarChart, ScatterChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, MarkLineComponent } from 'echarts/components'
import { useStockDaily } from '@/composables/useStockDaily'

use([CanvasRenderer, LineChart, BarChart, ScatterChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent])

// 蒙特卡洛期权定价：模拟大量标的路径 → 末值取均值 → 折现
// 教学点：MC 价格随路径数增加收敛到 BS 价格（大数定律）；同时展示终止收益分布
const props = defineProps<{
  params?: Record<string, unknown>
}>()

const code = computed(() => (typeof props.params?.code === 'string' ? props.params.code : 'sh600519'))
const { data } = useStockDaily(code, '2024-01-01', '2024-12-31')

const S = ref(100)
const K = ref(100)
const sigma = ref(0.2)
const T = ref(1)
const r = ref(0.03)
const nPaths = ref(1000)

// 用真实茅台收益估计 σ
const realVol = computed(() => {
  if (!data.value || data.value.length < 2) return null
  const rets = data.value.map((d) => d.pct_chg).slice(1)
  const m = rets.reduce((s, v) => s + v, 0) / rets.length
  const sd = Math.sqrt(rets.reduce((s, v) => s + (v - m) ** 2, 0) / (rets.length - 1))
  return sd * Math.sqrt(252)
})

function stdNormCdf(x: number): number {
  const t = 1 / (1 + 0.2316419 * Math.abs(x))
  const d = 0.3989422804014327 * Math.exp((-x * x) / 2)
  let p = d * t * (0.31938153 + t * (-0.356563782 + t * (1.781477937 + t * (-1.821255978 + t * 1.330274429))))
  return x > 0 ? 1 - p : p
}

function bsCall(S: number, K: number, sigma: number, T: number, r: number): number {
  if (T <= 0) return Math.max(S - K, 0)
  const d1 = (Math.log(S / K) + (r + (sigma * sigma) / 2) * T) / (sigma * Math.sqrt(T))
  const d2 = d1 - sigma * Math.sqrt(T)
  return S * stdNormCdf(d1) - K * Math.exp(-r * T) * stdNormCdf(d2)
}

function gauss(): number {
  let u = 0
  let v = 0
  while (u === 0) u = Math.random()
  while (v === 0) v = Math.random()
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v)
}

function mcCall(S: number, K: number, sigma: number, T: number, r: number, n: number) {
  const dt = T
  const paths: number[][] = []
  const finals: number[] = []
  const drift = (r - (sigma * sigma) / 2) * dt
  const vol = sigma * Math.sqrt(dt)
  for (let i = 0; i < n; i++) {
    const path: number[] = [S]
    let price = S
    for (let s = 1; s <= 12; s++) {
      price = price * Math.exp(drift / 12 + (vol / Math.sqrt(12)) * gauss())
      path.push(price)
    }
    paths.push(path)
    finals.push(Math.max(price - K, 0))
  }
  const disc = Math.exp(-r * T)
  const price = disc * finals.reduce((a, b) => a + b, 0) / n
  return { paths: paths.slice(0, 8), finals, price }
}

const result = computed(() => mcCall(S.value, K.value, sigma.value, T.value, r.value, nPaths.value))
const bsRef = computed(() => bsCall(S.value, K.value, sigma.value, T.value, r.value))

const pathOption = computed(() => {
  const dates = Array.from({ length: 13 }, (_, i) => `m${i}`)
  return {
    animation: false,
    grid: { left: 52, right: 24, top: 36, bottom: 40 },
    tooltip: { trigger: 'axis' },
    legend: { top: 0, textStyle: { fontSize: 11 } },
    xAxis: { type: 'category', data: dates, axisLabel: { fontSize: 9 } },
    yAxis: { type: 'value', name: '价格', nameLocation: 'middle', nameGap: 40, scale: true, axisLabel: { fontSize: 10 } },
    series: result.value.paths.map((p, i) => ({
      name: `路径 ${i + 1}`,
      type: 'line',
      data: p.map((v) => +v.toFixed(1)),
      smooth: false,
      symbol: 'none',
      lineStyle: { width: 1, opacity: 0.6 },
    })),
  }
})

const distOption = computed(() => {
  const finals = result.value.finals
  const lo = 0
  const hi = 300
  const bins = 40
  const w = (hi - lo) / bins
  const counts = new Array(bins).fill(0)
  for (const v of finals) {
    const b = Math.min(bins - 1, Math.max(0, Math.floor((v - lo) / w)))
    counts[b]++
  }
  const centers = counts.map((_, i) => Number((lo + w * (i + 0.5)).toFixed(1)))
  return {
    animation: false,
    grid: { left: 52, right: 24, top: 36, bottom: 40 },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'value', name: '到期价格 S_T', nameLocation: 'middle', nameGap: 30, axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', name: '频数', nameLocation: 'middle', nameGap: 36, axisLabel: { fontSize: 10 } },
    series: [
      {
        name: '终止价分布',
        type: 'bar',
        barWidth: '90%',
        data: centers.map((c, i) => [c, counts[i]]),
        itemStyle: { color: '#2563eb', opacity: 0.6 },
      },
      {
        name: `K=${K.value}`,
        type: 'line',
        data: [[K.value, 0], [K.value, Math.max(...counts)]],
        symbol: 'none',
        lineStyle: { color: '#dc2626', type: 'dashed' },
        markLine: {
          silent: true,
          symbol: 'none',
          data: [{ xAxis: K.value, label: { formatter: 'K', position: 'insideEndTop' }, lineStyle: { color: '#dc2626', type: 'dashed' } }],
        },
      },
    ],
  }
})
</script>

<template>
  <div class="mc">
    <div class="controls">
      <label>S <input type="range" v-model.number="S" min="60" max="140" step="1" /> {{ S }}</label>
      <label>K <input type="range" v-model.number="K" min="60" max="140" step="1" /> {{ K }}</label>
      <label>σ <input type="range" v-model.number="sigma" min="0.05" max="0.8" step="0.01" /> {{ (sigma * 100).toFixed(0) }}%</label>
      <label>路径数 <input type="range" v-model.number="nPaths" min="100" max="5000" step="100" /> {{ nPaths }}</label>
    </div>
    <div class="stats">
      <span class="chip">MC 价格 = <strong>{{ result.price.toFixed(2) }}</strong></span>
      <span class="chip">BS 价格 = <strong>{{ bsRef.toFixed(2) }}</strong></span>
      <span class="chip">误差 = <strong>{{ Math.abs(result.price - bsRef).toFixed(2) }}</strong></span>
      <span v-if="realVol" class="chip">真实茅台年化波动 = <strong>{{ realVol.toFixed(1) }}%</strong></span>
    </div>
    <div class="two-col">
      <div>
        <p class="sub">8 条抽样路径</p>
        <VChart class="chart half" :option="pathOption" autoresize />
      </div>
      <div>
        <p class="sub">到期价格分布（{{ nPaths }} 条，红线 = 执行价 K）</p>
        <VChart class="chart half" :option="distOption" autoresize />
      </div>
    </div>
    <p class="note">教学点：路径数越多，MC 价格越接近 BS（大数定律）。真实锚点：σ 取茅台 2024 真实波动率时，MC 定价即模拟「茅台风格的期权」。示意数据。</p>
  </div>
</template>

<style scoped>
.mc { padding: 16px; }
.controls { display: flex; gap: 14px; flex-wrap: wrap; align-items: center; margin-bottom: 10px; font-size: 12.5px; color: var(--text-2); }
.controls label { display: flex; align-items: center; gap: 6px; }
.controls input[type='range'] { width: 90px; }
.stats { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
.chip {
  font-size: 12.5px; color: var(--text-3);
  padding: 4px 10px; border-radius: 999px; background: var(--bg-hover);
}
.chip strong { color: var(--primary); }
.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.chart { width: 100%; }
.half { height: 260px; }
.sub { font-size: 12px; color: var(--text-3); margin-bottom: 6px; }
.note { font-size: 12.5px; color: var(--text-3); margin-top: 10px; line-height: 1.6; }
</style>