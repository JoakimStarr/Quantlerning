<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { fetchStockFinancials, type StockFinancials } from '@/api'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent])

// 护城河宽窄对比（茅台 vs 五粮液，真实财务数据）：ROE/毛利率十年双线
const props = defineProps<{
  params?: Record<string, unknown>
}>()

const STOCKS: [string, string][] = [
  ['sh600519', '贵州茅台'],
  ['sz000858', '五粮液'],
]
const stocks = computed<[string, string][]>(() => {
  const p = props.params
  const a = typeof p?.code_a === 'string' && p.code_a ? p.code_a : STOCKS[0][0]
  const b = typeof p?.code_b === 'string' && p.code_b ? p.code_b : STOCKS[1][0]
  const nameA = typeof p?.name_a === 'string' && p.name_a ? p.name_a : '公司 A'
  const nameB = typeof p?.name_b === 'string' && p.name_b ? p.name_b : '公司 B'
  return [[a, nameA], [b, nameB]] as [string, string][]
})

const metric = ref('roe') // roe | gross_margin | net_margin
const METRICS: [string, string][] = [['roe', 'ROE'], ['gross_margin', '毛利率'], ['net_margin', '净利率']]

const fin = ref<Record<string, StockFinancials>>({})
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    const results = await Promise.all(stocks.value.map(async ([c]) => [c, await fetchStockFinancials(c, 60)] as const))
    fin.value = Object.fromEntries(results)
  } catch {
    error.value = '数据不可用'
  } finally {
    loading.value = false
  }
})

// 年报序列：对齐两家都有的年份，取值（%）
const series = computed(() => {
  const key = metric.value
  return stocks.value.map(([c, name]) => {
    const f = fin.value[c]
    const rows = (f?.periods ?? []).filter((p) => p.report_date.endsWith('12-31')).reverse()
    return {
      name,
      points: rows.map((p) => ({
        date: p.report_date.slice(0, 4),
        v: typeof p[key] === 'number' ? +(p[key] as number).toFixed(1) : null,
      })),
    }
  })
})

const option = computed(() => {
  const s = series.value
  if (!s.length || !s[0].points.length) return {}
  // 用第一家的年份作 x（两家年报期基本对齐）
  const dates = s[0].points.map((x) => x.date)
  return {
    animation: true,
    tooltip: {
      trigger: 'axis',
      formatter: (ps: any[]) => {
        const date = ps[0]?.name ?? ''
        return `${date}<br/>` + ps
          .filter((q: any) => q.value !== null)
          .map((q: any) => `　${q.seriesName} ${q.value}%`)
          .join('<br/>')
      },
    },
    legend: { top: 0, textStyle: { fontSize: 12 }, data: s.map((x) => x.name) },
    grid: { left: 52, right: 20, top: 34, bottom: 40 },
    xAxis: { type: 'category', data: dates, axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', name: '%', nameTextStyle: { fontSize: 10 }, scale: true, axisLabel: { fontSize: 10 }, splitLine: { lineStyle: { color: C.value.grid } } },
    series: s.map((x, i) => ({
      name: x.name,
      type: 'line',
      data: x.points.map((p) => p.v),
      connectNulls: false,
      smooth: true,
      symbol: 'circle',
      symbolSize: 5,
      lineStyle: { width: 2, color: i === 0 ? C.value.primary : C.value.warning },
      itemStyle: { color: i === 0 ? C.value.primary : C.value.warning },
    })),
  }
})
</script>

<template>
  <div class="mc">
    <div v-if="loading" class="status">数据加载中…</div>
    <div v-else-if="error" class="status">{{ error }}</div>
    <template v-else-if="series.length">
      <div class="metric-row">
        <span class="metric-label">对比指标</span>
        <div class="tabs">
          <button v-for="[k, label] in METRICS" :key="k" :class="{ on: metric === k }" @click="metric = k">{{ label }}</button>
        </div>
      </div>
      <ThemedChart class="chart" :option="option" autoresize />
      <p class="hint">
        两条线的相对位置与波动幅度，就是「护城河宽窄」的数字投影：ROE 页签下，茅台（蓝）十年稳定在 30% 上方、五粮液（橙）在 23-25% 区间——茅台更高且更稳，护城河更宽；切到毛利率，差距更明显（茅台 91% vs 五粮液 77%，各自几乎走成直线）。指标越稳、差距越恒定，越说明定价权是被「可防守的优势」锁住的，而非行业景气偶得。
      </p>
    </template>
  </div>
</template>

<style scoped>
.mc { padding: 16px; }
.status { height: 380px; display: flex; align-items: center; justify-content: center; color: var(--text-3); font-size: 14px; }
.chart { height: 340px; }
.metric-row { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; flex-wrap: wrap; }
.metric-label { font-size: 12.5px; color: var(--text-2); }
.tabs { display: inline-flex; border: 1px solid var(--border); border-radius: 6px; overflow: hidden; }
.tabs button { padding: 3px 12px; font-size: 12.5px; background: transparent; color: var(--text-2); border: none; cursor: pointer; }
.tabs button.on { background: var(--primary); color: #fff; font-weight: 600; }
.hint { margin-top: 12px; font-size: 12px; color: var(--text-3); line-height: 1.7; }
</style>
