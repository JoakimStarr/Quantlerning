<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C, withAlpha } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { fetchStockFinancials, type StockFinancials } from '@/api'

use([CanvasRenderer, BarChart, LineChart, GridComponent, TooltipComponent, LegendComponent])

// 财务比率趋势（真实 quantlab 财务指标）：营收/净利柱状 + 可切换比率指标折线
const props = defineProps<{
  params?: Record<string, unknown>
}>()

const code = computed(() => (typeof props.params?.code === 'string' ? props.params.code : 'sh600519'))
const limit = computed(() => {
  const v = props.params?.limit
  if (typeof v === 'number') return v
  if (typeof v === 'string' && /^\d+$/.test(v.trim())) return parseInt(v.trim(), 10)
  return 24
})

const fin = ref<StockFinancials | null>(null)
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    fin.value = await fetchStockFinancials(code.value, limit.value)
  } catch {
    error.value = '数据不可用'
  } finally {
    loading.value = false
  }
})

// 指标选择：比率指标页签下的分组下拉
const tab = ref<'rev' | 'ratio'>('rev')
const metric = ref('roe')
const METRIC_GROUPS: { label: string; items: [string, string][] }[] = [
  { label: '盈利能力', items: [['roe', 'ROE'], ['roa', 'ROA'], ['gross_margin', '毛利率'], ['net_margin', '净利率']] },
  { label: '成长性', items: [['revenue_yoy', '营收同比'], ['netprofit_yoy', '净利同比']] },
  { label: '现金流质量', items: [['ocf_to_np', '净现比']] },
  { label: '偿债与杠杆', items: [['debt_ratio', '资产负债率'], ['current_ratio', '流动比率'], ['quick_ratio', '速动比率'], ['equity_multiplier', '权益乘数']] },
]
const metricLabel = computed(() => {
  for (const g of METRIC_GROUPS) {
    const it = g.items.find(([k]) => k === metric.value)
    if (it) return it[1]
  }
  return metric.value
})
const metricUnit = computed(() => (fin.value?.units ? fin.value.units[metric.value] ?? '' : ''))

// 按时间升序（接口返回倒序，最新在前）
const periods = computed(() => (fin.value ? [...fin.value.periods].reverse() : []))
const latest = computed(() => fin.value?.periods[0] ?? null)

// 最新报告期统计卡片
const fmtYi = (v: unknown) => (typeof v === 'number' ? `${(v / 1e8).toFixed(1)} 亿` : '—')
const fmtPct = (v: unknown) => (typeof v === 'number' ? `${v.toFixed(1)}%` : '—')
const latestCards = computed(() => {
  const l = latest.value
  if (!l) return []
  return [
    { label: '报告期', value: l.report_date, sub: `披露 ${l.available_date}` },
    { label: '营收', value: fmtYi(l.revenue), sub: 'TTM 前 12 月' },
    { label: '净利', value: fmtYi(l.netprofit), sub: '归母' },
    { label: 'ROE', value: fmtPct(l.roe), sub: '净资产收益率' },
    { label: '毛利率', value: fmtPct(l.gross_margin), sub: '盈利能力' },
    { label: '资产负债率', value: fmtPct(l.debt_ratio), sub: '杠杆水平' },
  ]
})

// 营收/净利柱状（单位 亿元）
const revOption = computed(() => {
  const ps = periods.value
  const x = ps.map((p) => p.report_date)
  const fmt = (f: string) => ps.map((p) => (typeof p[f] === 'number' ? +((p[f] as number) / 1e8).toFixed(1) : null))
  return {
    animation: true,
    tooltip: {
      trigger: 'axis',
      formatter: (params: any[]) => {
        const date = params[0]?.name ?? ''
        return `${date}<br/>` + params
          .filter((q: any) => q.value !== null)
          .map((q: any) => `　${q.seriesName} ${q.value} 亿`)
          .join('<br/>')
      },
    },
    legend: { top: 0, textStyle: { fontSize: 12 }, data: ['营收', '净利'] },
    grid: { left: 56, right: 20, top: 34, bottom: 44 },
    xAxis: {
      type: 'category',
      data: x,
      axisLabel: { fontSize: 10, hideOverlap: true, formatter: (v: string) => v.slice(0, 4) },
    },
    yAxis: { type: 'value', name: '亿元', nameTextStyle: { fontSize: 10 }, axisLabel: { fontSize: 10 }, splitLine: { lineStyle: { color: C.value.grid } } },
    series: [
      { name: '营收', type: 'bar', data: fmt('revenue'), itemStyle: { color: C.value.primary }, barMaxWidth: 18 },
      { name: '净利', type: 'bar', data: fmt('netprofit'), itemStyle: { color: C.value.warning }, barMaxWidth: 18 },
    ],
  }
})

// 比率指标折线（按所选指标，单位取自 units）
const ratioOption = computed(() => {
  const ps = periods.value
  const x = ps.map((p) => p.report_date)
  const vals = ps.map((p) => (typeof p[metric.value] === 'number' ? +(p[metric.value] as number).toFixed(2) : null))
  const unit = metricUnit.value
  return {
    animation: true,
    tooltip: {
      trigger: 'axis',
      formatter: (params: any[]) => {
        const p = params[0]
        if (!p || p.value === null) return p?.name ?? ''
        return `${p.name}<br/>　${metricLabel.value} ${p.value}${unit}`
      },
    },
    grid: { left: 56, right: 20, top: 34, bottom: 44 },
    xAxis: {
      type: 'category',
      data: x,
      axisLabel: { fontSize: 10, hideOverlap: true, formatter: (v: string) => v.slice(0, 4) },
    },
    yAxis: {
      type: 'value',
      name: metricUnit.value,
      nameTextStyle: { fontSize: 10 },
      scale: true,
      axisLabel: { fontSize: 10 },
      splitLine: { lineStyle: { color: C.value.grid } },
    },
    series: [
      {
        name: metricLabel.value,
        type: 'line',
        data: vals,
        connectNulls: false,
        smooth: true,
        symbol: 'circle',
        symbolSize: 5,
        lineStyle: { width: 2, color: C.value.primary },
        itemStyle: { color: C.value.primary },
        areaStyle: { color: withAlpha(C.value.primary, 0.1) },
      },
    ],
  }
})

const option = computed(() => (tab.value === 'rev' ? revOption.value : ratioOption.value))
</script>

<template>
  <div class="ft">
    <div v-if="loading" class="status">数据加载中…</div>
    <div v-else-if="error" class="status">{{ error }}</div>
    <template v-else-if="fin">
      <div class="cards">
        <div v-for="c in latestCards" :key="c.label" class="card">
          <span class="card-label">{{ c.label }}</span>
          <strong class="card-value">{{ c.value }}</strong>
          <span class="card-sub">{{ c.sub }}</span>
        </div>
      </div>

      <div class="chart-head">
        <div class="tabs">
          <button :class="{ on: tab === 'rev' }" @click="tab = 'rev'">营收与净利</button>
          <button :class="{ on: tab === 'ratio' }" @click="tab = 'ratio'">比率指标</button>
        </div>
        <label v-if="tab === 'ratio'" class="metric-select">
          指标
          <select v-model="metric">
            <optgroup v-for="g in METRIC_GROUPS" :key="g.label" :label="g.label">
              <option v-for="[k, label] in g.items" :key="k" :value="k">{{ label }}</option>
            </optgroup>
          </select>
        </label>
      </div>

      <ThemedChart class="chart" :option="option" autoresize />

      <p class="hint">
        数据来自 quantlab 财务指标表（报告期口径，披露日已在数据中标注，避免前视）。
        营收与净利看绝对规模与增长，比率指标看质地——ROE 与毛利率反映赚钱能力，净现比反映利润含金量，负债率反映杠杆风险。
      </p>
    </template>
  </div>
</template>

<style scoped>
.ft { padding: 16px; }
.status { height: 380px; display: flex; align-items: center; justify-content: center; color: var(--text-3); font-size: 14px; }
.chart { height: 360px; }
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(110px, 1fr)); gap: 10px; margin-bottom: 14px; }
.card { display: flex; flex-direction: column; gap: 2px; padding: 10px 12px; background: var(--primary-soft); border-radius: var(--radius-sm); min-width: 0; }
.card-label { font-size: 11.5px; color: var(--text-3); }
.card-value { font-size: 16px; font-weight: 700; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.card-sub { font-size: 10.5px; color: var(--text-3); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.chart-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 8px; flex-wrap: wrap; }
.tabs { display: inline-flex; border: 1px solid var(--border); border-radius: 6px; overflow: hidden; }
.tabs button { padding: 4px 14px; font-size: 12.5px; background: transparent; color: var(--text-2); border: none; cursor: pointer; }
.tabs button.on { background: var(--primary); color: #fff; font-weight: 600; }
.metric-select { display: inline-flex; align-items: center; gap: 6px; font-size: 12.5px; color: var(--text-2); }
.metric-select select {
  border: 1px solid var(--border);
  background: var(--bg-card);
  color: var(--text-1);
  font-size: 12.5px;
  padding: 4px 8px;
  border-radius: var(--radius-sm);
  font-family: inherit;
}
.hint { margin-top: 12px; font-size: 12px; color: var(--text-3); line-height: 1.7; }
</style>
