<script setup lang="ts">
import { computed, ref } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { useStockDaily } from '@/composables/useStockDaily'
import {
  maCrossSignal,
  bollingerZSignal,
  momentumSignal,
  donchianSignal,
  shiftPosition,
  stats,
  backtestArrays,
  type StrategyStats,
} from '@/utils/strategies'

use([CanvasRenderer, BarChart, GridComponent, TooltipComponent, LegendComponent])

// 绩效仪表盘：四类指标（收益/风险/风险调整/交易）全表 + 指标对比条形图
const props = defineProps<{
  params?: Record<string, unknown>
}>()

const code = computed(() => (typeof props.params?.code === 'string' ? props.params.code : 'sh600519'))
const start = computed(() => (typeof props.params?.start === 'string' ? props.params.start : '2020-01-01'))
const end = computed(() => (typeof props.params?.end === 'string' ? props.params.end : '2026-08-10'))
const { data, loading, error } = useStockDaily(code, start.value, end.value)

interface StrategyRow {
  name: string
  color: string
  st: StrategyStats
}

const rows = computed<StrategyRow[] | null>(() => {
  if (!data.value) return null
  const arr = backtestArrays(data.value)
  const ones = arr.closes.map(() => 1)
  const specs: { name: string; color: string; sig: number[] }[] = [
    { name: '买入持有', color: C.value.slate, sig: ones },
    { name: '均线 MA20/60', color: C.value.warning, sig: maCrossSignal(arr.closes, 20, 60) },
    { name: 'z-score 回归', color: C.value.success, sig: bollingerZSignal(arr.closes, 20, 2) },
    { name: '时序动量', color: C.value.violet, sig: momentumSignal(arr.closes, 20) },
    { name: '唐奇安 20/10', color: C.value.cyan, sig: donchianSignal(arr.highs, arr.lows, 20, 10) },
  ]
  return specs.map((s) => ({
    name: s.name,
    color: s.color,
    st: stats(arr.ret, shiftPosition(s.sig)),
  }))
})

// 选择要对比的指标
type MetricKey =
  | 'cum'
  | 'ann'
  | 'vol'
  | 'mdd'
  | 'sharpe'
  | 'sortino'
  | 'calmar'
  | 'underwaterDays'
  | 'winRate'
  | 'profitLossRatio'
  | 'turnover'
  | 'trades'

const METRIC_DEFS: { key: MetricKey; label: string; cat: string; fmt: (v: number) => string; lowerBetter: boolean }[] = [
  { key: 'cum', label: '累计收益', cat: '收益', fmt: (v) => `${(v * 100).toFixed(1)}%`, lowerBetter: false },
  { key: 'ann', label: '年化收益', cat: '收益', fmt: (v) => `${(v * 100).toFixed(1)}%`, lowerBetter: false },
  { key: 'vol', label: '年化波动', cat: '风险', fmt: (v) => `${(v * 100).toFixed(1)}%`, lowerBetter: true },
  { key: 'mdd', label: '最大回撤', cat: '风险', fmt: (v) => `${(v * 100).toFixed(1)}%`, lowerBetter: true },
  { key: 'underwaterDays', label: '水下期间(天)', cat: '风险', fmt: (v) => `${v}`, lowerBetter: true },
  { key: 'sharpe', label: 'Sharpe', cat: '风险调整', fmt: (v) => v.toFixed(2), lowerBetter: false },
  { key: 'sortino', label: 'Sortino', cat: '风险调整', fmt: (v) => v.toFixed(2), lowerBetter: false },
  { key: 'calmar', label: 'Calmar', cat: '风险调整', fmt: (v) => v.toFixed(2), lowerBetter: false },
  { key: 'winRate', label: '胜率', cat: '交易', fmt: (v) => `${(v * 100).toFixed(0)}%`, lowerBetter: false },
  { key: 'profitLossRatio', label: '盈亏比', cat: '交易', fmt: (v) => (Number.isFinite(v) ? v.toFixed(2) : '∞'), lowerBetter: false },
  { key: 'turnover', label: '年化换手率', cat: '交易', fmt: (v) => `${(v * 100).toFixed(0)}%`, lowerBetter: true },
  { key: 'trades', label: '交易次数', cat: '交易', fmt: (v) => `${v}`, lowerBetter: true },
]

const activeKey = ref<MetricKey>('sharpe')
const activeDef = computed(() => METRIC_DEFS.find((m) => m.key === activeKey.value)!)

const barOption = computed(() => {
  if (!rows.value) return {}
  const def = activeDef.value
  const vals = rows.value.map((r) => {
    const v = r.st[def.key]
    return typeof v === 'number' ? +v.toFixed(4) : 0
  })
  const best = def.lowerBetter
    ? Math.min(...vals)
    : Math.max(...vals)
  return {
    animation: true,
    grid: { left: 56, right: 24, top: 30, bottom: 40 },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (ps: any[]) => {
        const p = ps[0]
        const r = rows.value![p.dataIndex]
        const isBest = +p.value === best
        return `<b>${r.name}</b><br/>${def.label}：${def.fmt(r.st[def.key])}${isBest ? '（最优）' : ''}`
      },
    },
    xAxis: {
      type: 'category',
      data: rows.value.map((r) => r.name.replace(' MA20/60', '').replace(' 20/10', '').replace('z-score ', 'z-')),
      axisLabel: { fontSize: 10, hideOverlap: true },
    },
    yAxis: { type: 'value', axisLabel: { fontSize: 10 } },
    series: [
      {
        name: def.label,
        type: 'bar',
        barMaxWidth: 42,
        data: rows.value.map((r, i) => ({
          value: vals[i],
          itemStyle: { color: r.color },
        })),
        label: {
          show: true,
          position: 'top',
          fontSize: 10,
          color: C.value.text,
          formatter: (p: any) => def.fmt(rows.value![p.dataIndex].st[def.key]),
        },
        markPoint: {
          symbol: 'pin',
          symbolSize: 44,
          data: [
            {
              coord: [vals.indexOf(best), best],
              value: '最优',
              itemStyle: { color: C.value.primary },
            },
          ],
        },
      },
    ],
  }
})

const CAT_ORDER = ['收益', '风险', '风险调整', '交易']

const tableGroups = computed(() => {
  if (!rows.value) return []
  const groups = new Map<string, typeof METRIC_DEFS>()
  for (const m of METRIC_DEFS) {
    const arr = groups.get(m.cat) ?? []
    arr.push(m)
    groups.set(m.cat, arr)
  }
  const out: { cat: string; defs: typeof METRIC_DEFS }[] = []
  for (const cat of CAT_ORDER) {
    const defs = groups.get(cat)
    if (defs) out.push({ cat, defs })
  }
  return out
})

// 计算某指标的最优策略名（用于高亮）
function bestOf(def: (typeof METRIC_DEFS)[number]): number {
  if (!rows.value) return -1
  const vals = rows.value.map((r) => r.st[def.key] as number)
  if (def.lowerBetter) return vals.indexOf(Math.min(...vals))
  return vals.indexOf(Math.max(...vals))
}
</script>

<template>
  <div class="pd">
    <div v-if="loading" class="status">数据加载中…</div>
    <div v-else-if="error" class="status">数据不可用</div>
    <template v-else-if="rows">
      <div class="ctrl">
        <span class="ctrl-label">对比指标</span>
        <div class="chips">
          <button
            v-for="m in METRIC_DEFS"
            :key="m.key"
            class="chip"
            :class="{ active: m.key === activeKey }"
            @click="activeKey = m.key"
          >
            {{ m.label }}
          </button>
        </div>
      </div>
      <ThemedChart class="chart" :option="barOption" autoresize />
      <div class="tbl-wrap">
        <table class="tbl">
          <thead>
            <tr>
              <th>指标</th>
              <th v-for="r in rows" :key="r.name">
                <span class="dot" :style="{ background: r.color }"></span>{{ r.name }}
              </th>
            </tr>
          </thead>
          <tbody>
            <template v-for="g in tableGroups" :key="g.cat">
              <tr class="cat-row">
                <td colspan="6">{{ g.cat }}类</td>
              </tr>
              <tr v-for="def in g.defs" :key="def.key">
                <td class="metric-name">{{ def.label }}</td>
                <td v-for="(r, i) in rows" :key="r.name" :class="{ best: i === bestOf(def) }">
                  {{ def.fmt(r.st[def.key]) }}
                </td>
              </tr>
            </template>
          </tbody>
        </table>
        <p class="hint">口径：真实茅台 {{ start }} ~ {{ end }}，复权 pct_chg 连乘、不含首日、ddof=1、几何年化、Sharpe/Sortino 用 rf=2%、信号次日生效。「最优」单元格为每行最有利值，由指标方向（越大越好/越小越好）判定。</p>
      </div>
    </template>
  </div>
</template>

<style scoped>
.pd { padding: 16px; }
.status { height: 340px; display: flex; align-items: center; justify-content: center; color: var(--text-3); font-size: 14px; }
.ctrl { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; flex-wrap: wrap; }
.ctrl-label { font-size: 13px; color: var(--text-2); flex-shrink: 0; }
.chips { display: flex; gap: 6px; flex-wrap: wrap; }
.chip { border: 1px solid var(--border); background: transparent; color: var(--text-2); font-size: 12px; padding: 4px 10px; border-radius: 999px; cursor: pointer; transition: all 0.15s; }
.chip:hover { border-color: var(--primary); color: var(--primary); }
.chip.active { background: var(--primary); border-color: var(--primary); color: #fff; }
.chart { height: 300px; }
.tbl-wrap { margin-top: 14px; }
.tbl { width: 100%; border-collapse: collapse; font-size: 12.5px; }
.tbl th, .tbl td { padding: 6px 8px; border: 1px solid var(--border); text-align: right; }
.tbl th:first-child, .tbl td:first-child { text-align: left; }
.tbl th { background: var(--bg-hover); color: var(--text-2); font-weight: 600; }
.tbl td { font-variant-numeric: tabular-nums; }
.tbl tr.cat-row td { background: var(--primary-soft); font-weight: 700; color: var(--primary); text-align: left; }
.tbl td.metric-name { color: var(--text-2); }
.tbl td.best { color: var(--primary); font-weight: 700; }
.dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; }
.hint { margin-top: 10px; font-size: 12px; color: var(--text-3); line-height: 1.7; }
</style>
