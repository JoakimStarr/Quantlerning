<script setup lang="ts">
import { computed } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C, withAlpha } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, TitleComponent } from 'echarts/components'
import { useStockDaily } from '@/composables/useStockDaily'
import {
  maCrossSignal,
  bollingerZSignal,
  momentumSignal,
  donchianSignal,
  shiftPosition,
  strategyNav,
  stats,
  backtestArrays,
} from '@/utils/strategies'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, TitleComponent])

// 五策略净值对比（真实茅台 2020-2026）：买入持有 / 均线 / 回归 / 动量 / 唐奇安
const props = defineProps<{
  params?: Record<string, unknown>
}>()

const code = computed(() => (typeof props.params?.code === 'string' ? props.params.code : 'sh600519'))
const start = computed(() => (typeof props.params?.start === 'string' ? props.params.start : '2020-01-01'))
const end = computed(() => (typeof props.params?.end === 'string' ? props.params.end : '2026-08-10'))
const { data, loading, error } = useStockDaily(code, start.value, end.value)

interface Row {
  name: string
  color: string
  width: number
  dash?: boolean
  pos: number[]
  nav: number[]
  st: ReturnType<typeof stats>
}

const rows = computed<Row[] | null>(() => {
  if (!data.value) return null
  const arr = backtestArrays(data.value)
  const ones = arr.closes.map(() => 1)
  const specs: { name: string; color: string; width: number; dash?: boolean; sig: number[] }[] = [
    { name: '买入持有', color: C.value.slate, width: 1.2, dash: true, sig: ones },
    { name: '均线 MA20/60', color: C.value.warning, width: 1.6, sig: maCrossSignal(arr.closes, 20, 60) },
    { name: 'z-score 回归', color: C.value.success, width: 1.6, sig: bollingerZSignal(arr.closes, 20, 2) },
    { name: '时序动量', color: C.value.violet, width: 1.6, sig: momentumSignal(arr.closes, 20) },
    { name: '唐奇安 20/10', color: C.value.cyan, width: 1.8, sig: donchianSignal(arr.highs, arr.lows, 20, 10) },
  ]
  return specs.map((s) => {
    const pos = shiftPosition(s.sig)
    return {
      name: s.name,
      color: s.color,
      width: s.width,
      dash: s.dash,
      pos,
      nav: strategyNav(arr.ret, pos),
      st: stats(arr.ret, pos),
    }
  })
})

const option = computed(() => {
  if (!rows.value) return {}
  const dates = data.value!.map((d) => d.date)
  return {
    animation: true,
    grid: { left: 52, right: 24, top: 24, bottom: 44 },
    tooltip: {
      trigger: 'axis',
      formatter: (ps: any[]) => {
        const head = ps[0].name
        const lines = ps.map((p: any) => `<span style="color:${p.color}">●</span> ${p.seriesName}: ${Number(Array.isArray(p.value) ? p.value[1] : p.value).toFixed(1)}`).join('<br/>')
        return `<b>${head}</b><br/>${lines}`
      },
    },
    legend: { top: 0, textStyle: { fontSize: 11 } },
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
    xAxis: { type: 'category', data: dates, axisLabel: { fontSize: 10, hideOverlap: true } },
    yAxis: { type: 'value', name: '净值（起点=100）', nameLocation: 'middle', nameGap: 44, scale: true, axisLabel: { fontSize: 10 } },
    series: rows.value.map((r) => ({
      name: r.name,
      type: 'line',
      data: r.nav.map((v) => +v.toFixed(1)),
      smooth: true,
      symbol: 'none',
      lineStyle: { width: r.width, color: r.color, type: r.dash ? 'dashed' : 'solid' },
    })),
  }
})

const table = computed(() => {
  if (!rows.value) return []
  return rows.value.map((r) => ({
    name: r.name,
    color: r.color,
    cum: (r.st.cum * 100).toFixed(1),
    ann: (r.st.ann * 100).toFixed(1),
    vol: (r.st.vol * 100).toFixed(1),
    mdd: (r.st.mdd * 100).toFixed(1),
    sharpe: r.st.sharpe.toFixed(2),
    switches: r.st.switches,
  }))
})
</script>

<template>
  <div class="sc">
    <div v-if="loading" class="status">数据加载中…</div>
    <div v-else-if="error" class="status">数据不可用</div>
    <template v-else-if="rows">
      <div class="chart-wrap">
        <ThemedChart class="chart" :option="option" autoresize />
      </div>
      <table class="tbl">
        <thead>
          <tr>
            <th>策略</th>
            <th>累计</th>
            <th>年化</th>
            <th>波动</th>
            <th>最大回撤</th>
            <th>Sharpe</th>
            <th>信号次数</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in table" :key="r.name">
            <td><span class="dot" :style="{ background: r.color }"></span>{{ r.name }}</td>
            <td>{{ r.cum }}%</td>
            <td>{{ r.ann }}%</td>
            <td>{{ r.vol }}%</td>
            <td>{{ r.mdd }}%</td>
            <td>{{ r.sharpe }}</td>
            <td>{{ r.switches }}</td>
          </tr>
        </tbody>
      </table>
    </template>
  </div>
</template>

<style scoped>
.sc { padding: 16px; }
.status { height: 320px; display: flex; align-items: center; justify-content: center; color: var(--text-3); font-size: 14px; }
.chart { height: 300px; }
.chart-wrap { margin-bottom: 14px; }
.tbl { width: 100%; border-collapse: collapse; font-size: 12.5px; }
.tbl th, .tbl td { padding: 6px 8px; border: 1px solid var(--border); text-align: right; }
.tbl th:first-child, .tbl td:first-child { text-align: left; }
.tbl th { background: var(--bg-hover); color: var(--text-2); font-weight: 600; }
.tbl td { font-variant-numeric: tabular-nums; }
.dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 8px; }
</style>