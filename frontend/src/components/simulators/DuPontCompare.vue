<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { fetchStockFinancials, type StockFinancials } from '@/api'

use([CanvasRenderer, BarChart, GridComponent, TooltipComponent, LegendComponent])

// 三公司杜邦分解对比（真实 quantlab 财务数据）：净利率/周转/乘数/ROE 四件套
const props = defineProps<{
  params?: Record<string, unknown>
}>()

const DEFAULT_CODES: [string, string][] = [
  ['sh600519', '贵州茅台'],
  ['sz000858', '五粮液'],
  ['sh600036', '招商银行'],
]

const codes = computed<[string, string][]>(() => {
  const p = props.params
  const list: [string, string][] = []
  for (const k of ['code1', 'code2', 'code3']) {
    const v = p?.[k]
    if (typeof v === 'string' && v.trim()) list.push([v.trim(), v.trim()])
  }
  return list.length >= 2 ? list : DEFAULT_CODES
})

const year = ref(2024) // 默认取 2024 年报（与全书主线一致）
const data = ref<Record<string, StockFinancials>>({})
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    const results = await Promise.all(codes.value.map(async ([c]) => [c, await fetchStockFinancials(c, 120)] as const))
    data.value = Object.fromEntries(results)
  } catch {
    error.value = '数据不可用'
  } finally {
    loading.value = false
  }
})

interface Row {
  name: string
  nm: number | null // 净利率 %
  turn: number | null // 总资产周转率
  em: number | null // 权益乘数
  roe: number | null // ROE %
}

const rows = computed<Row[]>(() => {
  return codes.value.map(([c, name]) => {
    const fin = data.value[c]
    if (!fin) return { name, nm: null, turn: null, em: null, roe: null }
    const p = fin.periods.find((x) => x.report_date === `${year.value}-12-31`) ?? fin.periods[0]
    if (!p) return { name, nm: null, turn: null, em: null, roe: null }
    const nm = typeof p.net_margin === 'number' ? p.net_margin : null
    const em = typeof p.equity_multiplier === 'number' ? p.equity_multiplier : null
    const roe = typeof p.roe === 'number' ? p.roe : null
    const turn = nm && em && roe ? roe / (nm * em) : null
    return { name, nm, turn, em, roe }
  })
})

// 分组柱状：净利率 vs ROE（同为 %，量纲一致）；周转与乘数差异大，放表格里展示
const chartOption = computed(() => {
  const rs = rows.value
  return {
    animation: true,
    tooltip: {
      trigger: 'axis',
      formatter: (ps: any[]) => {
        const name = ps[0]?.name ?? ''
        return `${name}<br/>` + ps
          .filter((q: any) => q.value !== null)
          .map((q: any) => `　${q.seriesName} ${q.value}%`)
          .join('<br/>')
      },
    },
    legend: { top: 0, textStyle: { fontSize: 12 }, data: ['净利率', 'ROE'] },
    grid: { left: 56, right: 20, top: 34, bottom: 40 },
    xAxis: { type: 'category', data: rs.map((r) => r.name), axisLabel: { fontSize: 11 } },
    yAxis: { type: 'value', name: '%', nameTextStyle: { fontSize: 10 }, axisLabel: { fontSize: 10 }, splitLine: { lineStyle: { color: C.value.grid } } },
    series: [
      { name: '净利率', type: 'bar', data: rs.map((r) => (r.nm !== null ? +r.nm.toFixed(1) : null)), itemStyle: { color: C.value.slateStrong }, barMaxWidth: 26 },
      { name: 'ROE', type: 'bar', data: rs.map((r) => (r.roe !== null ? +r.roe.toFixed(1) : null)), itemStyle: { color: C.value.primary }, barMaxWidth: 26 },
    ],
  }
})
</script>

<template>
  <div class="dc">
    <div v-if="loading" class="status">数据加载中…</div>
    <div v-else-if="error" class="status">{{ error }}</div>
    <template v-else>
      <div class="year-row">
        <label>
          年报年份
          <select v-model.number="year">
            <option v-for="y in [2019, 2020, 2021, 2022, 2023, 2024, 2025]" :key="y" :value="y">{{ y }}</option>
          </select>
        </label>
        <span class="year-note">ROE = 净利率 × 周转率 × 权益乘数（周转率由三者反推）</span>
      </div>
      <table class="tbl">
        <thead>
          <tr><th>公司</th><th>净利率</th><th>周转率</th><th>权益乘数</th><th>ROE</th></tr>
        </thead>
        <tbody>
          <tr v-for="r in rows" :key="r.name">
            <td class="c-name">{{ r.name }}</td>
            <td>{{ r.nm !== null ? r.nm.toFixed(1) + '%' : '—' }}</td>
            <td>{{ r.turn !== null ? r.turn.toFixed(2) : '—' }}</td>
            <td>{{ r.em !== null ? r.em.toFixed(2) : '—' }}</td>
            <td class="c-roe">{{ r.roe !== null ? r.roe.toFixed(1) + '%' : '—' }}</td>
          </tr>
        </tbody>
      </table>
      <ThemedChart class="chart" :option="chartOption" autoresize />
      <p class="hint">
        读表要点：茅台净利率 52% + 杠杆 1.27 → ROE 36%（质量型）；五粮液三项都略逊（第二梯队）；招行净利率 44% 不低，但周转仅 0.03、靠 11.76 倍杠杆拉到 ROE 14.5%——跨行业看模式，不能直接比高低。图中「净利率 vs ROE」的差距直观展示周转与杠杆对 ROE 的放大/稀释。
      </p>
    </template>
  </div>
</template>

<style scoped>
.dc { padding: 16px; }
.status { height: 380px; display: flex; align-items: center; justify-content: center; color: var(--text-3); font-size: 14px; }
.chart { height: 320px; }
.year-row { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; flex-wrap: wrap; }
.year-row label { display: inline-flex; align-items: center; gap: 6px; font-size: 12.5px; color: var(--text-2); }
.year-row select {
  border: 1px solid var(--border);
  background: var(--bg-card);
  color: var(--text-1);
  font-size: 12.5px;
  padding: 3px 8px;
  border-radius: var(--radius-sm);
  font-family: inherit;
}
.year-note { font-size: 11.5px; color: var(--text-3); }
.tbl { width: 100%; border-collapse: collapse; margin-bottom: 12px; font-size: 12.5px; }
.tbl th, .tbl td { border: 1px solid var(--border); padding: 6px 10px; text-align: right; }
.tbl th { background: var(--primary-soft); color: var(--text-2); font-weight: 600; font-size: 12px; }
.tbl .c-name { text-align: left; font-weight: 600; }
.tbl .c-roe { font-weight: 700; color: var(--primary); }
.hint { margin-top: 10px; font-size: 12px; color: var(--text-3); line-height: 1.7; }
</style>
