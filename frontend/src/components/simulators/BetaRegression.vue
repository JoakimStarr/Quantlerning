<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { ScatterChart, LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, MarkLineComponent, DataZoomComponent } from 'echarts/components'
import { fetchStockDaily, fetchMacro } from '@/api'

use([CanvasRenderer, ScatterChart, LineChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent, DataZoomComponent])

// 真实 β 回归：贵州茅台 vs 上证指数（2020-2026 日收益 OLS）
// 市场基准用 quantlab 宏数据 SH_INDEX 的日收盘点序列（sh_idx_close）算日收益
// 教学点：β = 个股对市场系统性风险的敏感度；散点越聚拢、R² 越高，市场因子解释力越强

const props = defineProps<{
  params?: Record<string, unknown>
}>()

const start = computed(() => (typeof props.params?.start === 'string' ? props.params.start : '2020-01-02'))
const end = computed(() => (typeof props.params?.end === 'string' ? props.params.end : '2026-08-10'))
const stockCode = computed(() => (typeof props.params?.code === 'string' ? props.params.code : 'sh600519'))

const loading = ref(true)
const error = ref<string | null>(null)

// 对齐后的 (市场收益, 个股收益) 点
const points = ref<[number, number][]>([])

// 简单 OLS：y = α + β·x（x=市场收益%，y=个股收益%）
function ols(xs: number[], ys: number[]) {
  const n = xs.length
  const mx = xs.reduce((a, b) => a + b, 0) / n
  const my = ys.reduce((a, b) => a + b, 0) / n
  let num = 0
  let den = 0
  for (let i = 0; i < n; i++) {
    num += (xs[i] - mx) * (ys[i] - my)
    den += (xs[i] - mx) ** 2
  }
  const beta = num / den
  const alpha = my - beta * mx
  // R²
  let ssTot = 0
  let ssRes = 0
  for (let i = 0; i < n; i++) {
    ssTot += (ys[i] - my) ** 2
    ssRes += (ys[i] - (alpha + beta * xs[i])) ** 2
  }
  const r2 = 1 - ssRes / ssTot
  return { alpha, beta, r2, n }
}

const stats = computed(() => {
  const xs = points.value.map((p) => p[0])
  const ys = points.value.map((p) => p[1])
  if (xs.length < 2) return null
  return ols(xs, ys)
})

// 回归线端点（覆盖 x 轴范围）
const lineData = computed<[number, number][]>(() => {
  if (!stats.value || !points.value.length) return []
  const xs = points.value.map((p) => p[0])
  const xMin = Math.min(...xs)
  const xMax = Math.max(...xs)
  const s = stats.value
  return [
    [+xMin.toFixed(2), +(s.alpha + s.beta * xMin).toFixed(2)],
    [+xMax.toFixed(2), +(s.alpha + s.beta * xMax).toFixed(2)],
  ]
})

async function load() {
  loading.value = true
  error.value = null
  try {
    const [stock, idxRows] = await Promise.all([
      fetchStockDaily(stockCode.value, start.value, end.value),
      fetchMacro('SH_INDEX', start.value, end.value) as Promise<{ date: string; field: string; value: number }[]>,
    ])
    // 市场日收益：SH_INDEX 收盘点序列 → 相邻日算 pct_chg
    const idxSorted = idxRows
      .filter((r) => r.field === 'sh_idx_close')
      .sort((a, b) => (a.date < b.date ? -1 : 1))
    const mMap = new Map<string, number>()
    for (let i = 1; i < idxSorted.length; i++) {
      const prev = idxSorted[i - 1].value
      mMap.set(idxSorted[i].date, (idxSorted[i].value / prev - 1) * 100)
    }
    const out: [number, number][] = []
    for (const r of stock) {
      const mp = mMap.get(r.date)
      if (mp != null && r.pct_chg != null) out.push([mp, r.pct_chg])
    }
    points.value = out
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

onMounted(load)

const option = computed(() => ({
  animation: false,
  grid: { left: 52, right: 24, top: 40, bottom: 60 },
  tooltip: {
    trigger: 'item',
    formatter: (p: any) =>
      `市场 ${Number(p.value[0]).toFixed(2)}%<br/>个股 ${Number(p.value[1]).toFixed(2)}%`,
  },
  legend: { top: 0, textStyle: { fontSize: 12 } },
  xAxis: {
    type: 'value',
    name: '上证指数日收益 %',
    nameLocation: 'middle',
    nameGap: 30,
    axisLabel: { fontSize: 11 },
  },
  yAxis: {
    type: 'value',
    name: '茅台日收益 %',
    nameLocation: 'middle',
    nameGap: 40,
    axisLabel: { fontSize: 11 },
  },
  dataZoom: [
    { type: 'inside', xAxisIndex: 0 },
    { type: 'slider', xAxisIndex: 0, height: 18, bottom: 8 },
  ],
  series: [
    {
      name: '日收益散点',
      type: 'scatter',
      data: points.value.map((p) => [+p[0].toFixed(3), +p[1].toFixed(3)]),
      symbolSize: 4,
      itemStyle: { color: 'rgba(37, 99, 235, 0.5)' },
    },
    {
      name: stats.value ? `回归线 β=${stats.value.beta.toFixed(2)}` : '回归线',
      type: 'line',
      data: lineData.value,
      symbol: 'none',
      lineStyle: { width: 3, color: '#dc2626' },
      markLine: {
        silent: true,
        symbol: 'none',
        lineStyle: { color: '#94a3b8', type: 'dashed' },
        data: [
          { xAxis: 0, label: { formatter: '市场 0%' } },
          { yAxis: 0, label: { formatter: '个股 0%' } },
        ],
      },
    },
  ],
}))
</script>

<template>
  <div class="beta-reg">
    <div v-if="loading" class="status">数据加载中…</div>
    <div v-else-if="error" class="status">数据不可用</div>
    <template v-else-if="points.length">
      <div class="stats">
        <span class="chip" v-if="stats">样本 <strong>{{ stats.n }}</strong> 个交易日</span>
        <span class="chip" v-if="stats">β <strong>{{ stats.beta.toFixed(2) }}</strong></span>
        <span class="chip" v-if="stats">α（年化前）<strong>{{ stats.alpha.toFixed(3) }}%</strong></span>
        <span class="chip" v-if="stats">R² <strong>{{ stats.r2.toFixed(3) }}</strong></span>
      </div>
      <VChart class="chart" :option="option" autoresize />
      <div class="tip">
        茅台对上证指数（2020-2026 日收益 OLS）的 β 约 {{ stats?.beta.toFixed(2) }}：市场每涨跌 1%，茅台平均同向变动约
        {{ (stats?.beta ?? 0).toFixed(2) }}%（回归线斜率）。R²={{ stats?.r2.toFixed(2) }} 表示市场因子能解释茅台约
        {{ ((stats?.r2 ?? 0) * 100).toFixed(0) }}% 的日收益方差，其余来自个股自身。
      </div>
    </template>
  </div>
</template>

<style scoped>
.beta-reg { padding: 16px; }
.status { height: 300px; display: flex; align-items: center; justify-content: center; color: var(--text-3); font-size: 14px; }
.chart { height: 360px; }
.stats { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
.chip {
  font-size: 12.5px; color: var(--text-3);
  padding: 4px 10px; border-radius: 999px; background: var(--bg-hover);
}
.chip strong { color: var(--primary); }
.tip { margin-top: 10px; font-size: 12.5px; color: var(--text-3); line-height: 1.7; }
</style>
