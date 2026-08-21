<script setup lang="ts">
import { computed } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C, withAlpha } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, TitleComponent } from 'echarts/components'
import { useStockDaily } from '@/composables/useStockDaily'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, TitleComponent])

// 真实茅台 2024：算术 vs 对数日收益的累计路径对比
// 复权口径（pct_chg 连乘）vs 未复权收盘价 pct_change

const props = defineProps<{
  params?: Record<string, unknown>
}>()

const code = computed(() => (typeof props.params?.code === 'string' ? props.params.code : 'sh600519'))
const { data, loading, error } = useStockDaily(code)

// 累计：从 100 起点
function cumFrom(pcts: number[]): number[] {
  const out: number[] = []
  let v = 100
  for (const p of pcts) {
    v *= 1 + p / 100
    out.push(Number(v.toFixed(3)))
  }
  return out
}

const series = computed(() => {
  if (!data.value || data.value.length === 0) return null
  const dates = data.value.map((d) => d.date)
  const pctAdj = data.value.map((d) => d.pct_chg).slice(1) // 复权涨跌幅（不含首日）
  const closeRaw = data.value.map((d) => d.close)
  // 未复权简单收益
  const pctRaw: number[] = []
  for (let i = 1; i < closeRaw.length; i++) pctRaw.push(((closeRaw[i] / closeRaw[i - 1] - 1) * 100))
  // 对数收益（复权近似：用 pct_chg 转对数）
  const logAdj = pctAdj.map((p) => Math.log(1 + p / 100) * 100)
  return {
    dates: dates.slice(1),
    adjCum: cumFrom(pctAdj),
    rawCum: cumFrom(pctRaw),
    logCum: cumFrom(logAdj),
  }
})

const sums = computed(() => {
  if (!series.value) return null
  const n = series.value.adjCum.length
  return {
    adj: series.value.adjCum[n - 1],
    raw: series.value.rawCum[n - 1],
    log: series.value.logCum[n - 1],
  }
})

const option = computed(() => {
  if (!series.value) return {}
  return {
    animation: true,
    grid: { left: 52, right: 24, top: 24, bottom: 44 },
    dataZoom: [
      {
        type: 'inside',
        xAxisIndex: [0],
        start: 0,
        end: 100,
        zoomOnMouseWheel: true,
        moveOnMouseMove: true,
      },
      {
        type: 'slider',
        xAxisIndex: [0],
        start: 0,
        end: 100,
        bottom: 2,
        height: 16,
        borderColor: C.value.grid,
        backgroundColor: 'transparent',
        fillerColor: withAlpha(C.value.primary, 0.15),
        handleStyle: { color: C.value.primary },
        textStyle: { color: C.value.text, fontSize: 10 },
        dataBackground: {
          lineStyle: { color: C.value.slate, opacity: 0.5 },
          areaStyle: { color: withAlpha(C.value.slate, 0.1) },
        },
        selectedDataBackground: {
          lineStyle: { color: C.value.primary, opacity: 0.6 },
          areaStyle: { color: withAlpha(C.value.primary, 0.12) },
        },
      },
    ],
    tooltip: {
      trigger: 'axis',
      formatter: (ps: any[]) => {
        const arr = Array.isArray(ps) ? ps : [ps]
        return arr.map((p: any) => `${p.seriesName}：${Number(Array.isArray(p.value) ? p.value[1] : p.value).toFixed(2)}（${p.name}）`).join('<br/>')
      },
    },
    legend: { top: 0, textStyle: { fontSize: 12 } },
    xAxis: { type: 'category', data: series.value.dates, axisLabel: { fontSize: 10, hideOverlap: true } },
    yAxis: { type: 'value', name: '累计净值（起=100）', nameLocation: 'middle', nameGap: 42, scale: true, axisLabel: { fontSize: 10 } },
    series: [
      { name: '复权累计（主线口径）', type: 'line', data: series.value.adjCum, symbol: 'none', lineStyle: { width: 2.5, color: C.value.primary } },
      { name: '未复权累计', type: 'line', data: series.value.rawCum, symbol: 'none', lineStyle: { width: 1.5, color: C.value.danger, opacity: 0.8 } },
      { name: '对数收益累计', type: 'line', data: series.value.logCum, symbol: 'none', lineStyle: { width: 1.5, color: C.value.warning, opacity: 0.8 } },
    ],
  }
})
</script>

<template>
  <div class="rl">
    <div v-if="loading" class="status">数据加载中…</div>
    <div v-else-if="error" class="status">数据不可用</div>
    <template v-else-if="series && sums">
      <div class="result">
        <div class="result-item">
          <span class="result-label">复权累计（主线）</span>
          <strong class="result-value primary">{{ ((sums.adj / 100 - 1) * 100).toFixed(2) }}%</strong>
        </div>
        <div class="result-item">
          <span class="result-label">未复权累计</span>
          <strong class="result-value red">{{ ((sums.raw / 100 - 1) * 100).toFixed(2) }}%</strong>
        </div>
        <div class="result-item">
          <span class="result-label">对数收益累计</span>
          <strong class="result-value warn">{{ ((sums.log / 100 - 1) * 100).toFixed(2) }}%</strong>
        </div>
      </div>
      <ThemedChart class="chart" :option="option" autoresize />
      <div class="tip">
        复权与未复权差异来自 6 月分红除权（未复权价在除权日「凭空下跌」）；算术与对数在日频几乎重合，但在更长周期或更大波动下会明显分离。
      </div>
    </template>
  </div>
</template>

<style scoped>
.rl { padding: 16px; }
.status { height: 300px; display: flex; align-items: center; justify-content: center; color: var(--text-3); font-size: 14px; }
.chart { height: 300px; }
.result { display: flex; gap: 20px; margin-bottom: 12px; padding: 12px 16px; background: var(--primary-soft); border-radius: var(--radius-sm); flex-wrap: wrap; }
.result-item { display: flex; flex-direction: column; gap: 2px; }
.result-label { font-size: 12px; color: var(--text-3); }
.result-value { font-size: 18px; font-weight: 700; }
.result-value.primary { color: var(--primary); }
.result-value.red { color: var(--danger, #dc2626); }
.result-value.warn { color: var(--warning, #d97706); }
.tip { margin-top: 12px; font-size: 12.5px; color: var(--text-3); line-height: 1.7; }
</style>
