<script setup lang="ts">
import { computed, ref } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C, withAlpha } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, ScatterChart, CandlestickChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
  TitleComponent,
} from 'echarts/components'
import { useStockDaily } from '@/composables/useStockDaily'
import { donchianSignal, shiftPosition, strategyNav, stats, backtestArrays } from '@/utils/strategies'

use([
  CanvasRenderer,
  LineChart,
  ScatterChart,
  CandlestickChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
  TitleComponent,
])

// 唐奇安通道（真实茅台 2020-2026）：通道带 + 通道宽度 + 净值对比
const props = defineProps<{
  params?: Record<string, unknown>
}>()

const code = computed(() => (typeof props.params?.code === 'string' ? props.params.code : 'sh600519'))
const start = computed(() => (typeof props.params?.start === 'string' ? props.params.start : '2020-01-01'))
const end = computed(() => (typeof props.params?.end === 'string' ? props.params.end : '2026-08-10'))
const { data, loading, error } = useStockDaily(code, start.value, end.value)

const donN = ref(20) // 突破：过去 N 日最高
const donM = ref(10) // 离场：过去 M 日最低

const com = computed(() => {
  if (!data.value) return null
  const arr = backtestArrays(data.value)
  const n = donN.value
  const m = donM.value
  const len = arr.highs.length
  // 通道：t 日上轨 = max(high[t-n..t-1])、下轨 = min(low[t-m..t-1])（预热期 null，不含当日杜绝前视）
  const upper: (number | null)[] = []
  const lower: (number | null)[] = []
  for (let i = 0; i < len; i++) {
    if (i < n) {
      upper.push(null)
    } else {
      let hi = -Infinity
      for (let j = i - n; j < i; j++) hi = Math.max(hi, arr.highs[j])
      upper.push(hi)
    }
    if (i < m) {
      lower.push(null)
    } else {
      let lo = Infinity
      for (let j = i - m; j < i; j++) lo = Math.min(lo, arr.lows[j])
      lower.push(lo)
    }
  }
  // 通道宽度 = 上轨 − 下轨（波动率的直观代理）
  const width = upper.map((u, i) => (u !== null && lower[i] !== null ? +(u - lower[i]!).toFixed(1) : null))
  // 策略：信号次日生效（杜绝前视）
  const sig = donchianSignal(arr.highs, arr.lows, n, m)
  const pos = shiftPosition(sig)
  const buyNav = strategyNav(arr.ret, arr.closes.map(() => 1))
  const nav = strategyNav(arr.ret, pos)
  const st = stats(arr.ret, pos)
  const bh = stats(arr.ret, arr.closes.map(() => 1))
  // 买卖点：标记在突破日（信号日）
  const buyIdx: number[] = []
  const sellIdx: number[] = []
  for (let i = 1; i < sig.length; i++) {
    if (sig[i] > sig[i - 1]) buyIdx.push(i)
    else if (sig[i] < sig[i - 1]) sellIdx.push(i)
  }
  return { arr, upper, lower, width, pos, nav, buyNav, st, bh, buyIdx, sellIdx }
})

const option = computed(() => {
  if (!com.value) return {}
  const c = com.value
  const dates = c.arr.dates
  const band = (v: (number | null)[]) => v.map((x, i) => [dates[i], x === null ? '-' : +x.toFixed(1)])
  // 通道填充：下轨系列用「下轨−上轨」堆叠在「上轨」之上，填出 [上轨, 下轨] 区间
  const fill = c.lower.map((v, i) => (v === null || c.upper[i] === null ? '-' : +(v - c.upper[i]!).toFixed(1)))
  return {
    animation: true,
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    tooltip: {
      trigger: 'axis',
      formatter: (ps: any[]) => {
        const priceS = ps.find((p: any) => p.seriesName === '收盘价')
        const up = ps.find((p: any) => p.seriesName === '上轨')
        const lo = ps.find((p: any) => p.seriesName === '下轨')
        const w = ps.find((p: any) => p.seriesName === '通道宽度')
        const nav = ps.find((p: any) => p.seriesName === '策略净值')
        const bh = ps.find((p: any) => p.seriesName === '买入持有')
        const name = priceS?.name ?? nav?.name ?? ''
        const parts: string[] = []
        if (name) parts.push(`<b>${name}</b>`)
        if (priceS) parts.push('K线与通道带：')
        if (priceS) parts.push(`　收盘 ${priceS.value[1]} 元`)
        if (up && up.value[1] !== '-') parts.push(`　上轨 ${up.value[1]} 元（突破买入）`)
        if (lo && lo.value[1] !== '-') parts.push(`　下轨 ${lo.value[1]} 元（跌破离场）`)
        if (w) parts.push(`通道宽度：${w.value[1]} 元（上轨 − 下轨，收窄=蓄势）`)
        if (nav || bh) parts.push('净值对比（起点 100）：')
        if (nav) parts.push(`　策略净值 ${nav.value[1]}`)
        if (bh) parts.push(`　买入持有 ${bh.value[1]}`)
        return parts.join('<br/>')
      },
    },
    legend: { top: 0, textStyle: { fontSize: 12 }, data: ['收盘价', '上轨', '下轨', '买入', '卖出', '通道宽度', '策略净值', '买入持有'] },
    grid: [
      { left: 56, right: 24, top: 48, height: '30%' },
      { left: 56, right: 24, top: '50%', height: '14%' },
      { left: 56, right: 24, top: '71%', height: '14%' },
    ],
    title: [
      {
        text: '① K线与通道带（元）',
        left: 56,
        top: 8,
        textStyle: { fontSize: 12, fontWeight: 600, color: C.value.text },
      },
      {
        text: '② 通道宽度 = 上轨 − 下轨（元）',
        left: 56,
        top: '46%',
        textStyle: { fontSize: 12, fontWeight: 600, color: C.value.text },
      },
      {
        text: '③ 策略净值 vs 买入持有（起点 100）',
        left: 56,
        top: '67%',
        textStyle: { fontSize: 12, fontWeight: 600, color: C.value.text },
      },
    ],
    dataZoom: [
      {
        type: 'inside',
        xAxisIndex: [0, 1, 2],
        start: 69.8,
        end: 100,
        zoomOnMouseWheel: true,
        moveOnMouseMove: true,
      },
      {
        type: 'slider',
        xAxisIndex: [0, 1, 2],
        start: 69.8,
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
    xAxis: [
      { type: 'category', data: dates, gridIndex: 0, axisLabel: { show: false }, axisPointer: { label: { show: false } } },
      { type: 'category', data: dates, gridIndex: 1, axisLabel: { show: false }, axisPointer: { label: { show: false } } },
      { type: 'category', data: dates, gridIndex: 2, axisLabel: { fontSize: 10, hideOverlap: true } },
    ],
    yAxis: [
      { type: 'value', gridIndex: 0, scale: true, axisLabel: { fontSize: 11 } },
      { type: 'value', gridIndex: 1, scale: true, axisLabel: { fontSize: 10 } },
      { type: 'value', gridIndex: 2, scale: true, axisLabel: { fontSize: 10 } },
    ],
    series: [
      {
        name: '收盘价',
        type: 'candlestick',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: c.arr.opens.map((o, i) => [o, c.arr.closes[i], c.arr.lows[i], c.arr.highs[i]]),
        itemStyle: {
          color: C.value.danger,
          color0: C.value.success,
          borderColor: C.value.danger,
          borderColor0: C.value.success,
          borderWidth: 1,
        },
      },
      {
        name: '买入',
        type: 'scatter',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: c.buyIdx.map((i) => [dates[i], c.arr.lows[i]]),
        symbol: 'triangle',
        symbolSize: 9,
        itemStyle: { color: C.value.success },
        z: 3,
      },
      {
        name: '卖出',
        type: 'scatter',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: c.sellIdx.map((i) => [dates[i], c.arr.highs[i]]),
        symbol: 'triangle',
        symbolRotate: 180,
        symbolSize: 9,
        itemStyle: { color: C.value.danger },
        z: 3,
      },
      {
        name: '上轨',
        type: 'line',
        xAxisIndex: 0,
        yAxisIndex: 0,
        stack: 'chan',
        data: band(c.upper),
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 1, color: C.value.danger, type: 'dashed', opacity: 0.75 },
        itemStyle: { color: C.value.danger },
        areaStyle: { color: 'transparent' },
      },
      {
        name: '下轨',
        type: 'line',
        xAxisIndex: 0,
        yAxisIndex: 0,
        stack: 'chan',
        data: fill.map((v, i) => [dates[i], v]),
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 1, color: C.value.success, type: 'dashed', opacity: 0.75 },
        itemStyle: { color: C.value.success },
        areaStyle: { color: withAlpha(C.value.primary, 0.07) },
        tooltip: { show: false },
        silent: true,
      },
      {
        name: '通道宽度',
        type: 'line',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: c.width.map((v, i) => [dates[i], v === null ? '-' : v]),
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 1.5, color: C.value.cyan },
        itemStyle: { color: C.value.cyan },
        areaStyle: { color: withAlpha(C.value.cyan, 0.12) },
      },
      {
        name: '策略净值',
        type: 'line',
        xAxisIndex: 2,
        yAxisIndex: 2,
        data: c.nav.map((v, i) => [dates[i], +v.toFixed(1)]),
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 2, color: C.value.warning },
        itemStyle: { color: C.value.warning },
      },
      {
        name: '买入持有',
        type: 'line',
        xAxisIndex: 2,
        yAxisIndex: 2,
        data: c.buyNav.map((v, i) => [dates[i], +v.toFixed(1)]),
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 1.5, color: C.value.slateStrong, type: 'dashed' },
        itemStyle: { color: C.value.slateStrong },
      },
    ],
  }
})
</script>

<template>
  <div class="dc">
    <div v-if="loading" class="status">数据加载中…</div>
    <div v-else-if="error" class="status">数据不可用</div>
    <template v-else-if="com">
      <div class="result">
        <div class="result-item">
          <span class="result-label">累计收益</span>
          <strong class="result-value" :style="{ color: com.st.cum >= 0 ? 'var(--success, #16a34a)' : 'var(--danger, #dc2626)' }">{{ (com.st.cum * 100).toFixed(1) }}%</strong>
        </div>
        <div class="result-item">
          <span class="result-label">最大回撤</span>
          <strong class="result-value" style="color: var(--danger, #dc2626)">{{ (com.st.mdd * 100).toFixed(1) }}%</strong>
        </div>
        <div class="result-item">
          <span class="result-label">持仓占比</span>
          <strong class="result-value">{{ (com.st.posMean * 100).toFixed(1) }}%</strong>
        </div>
        <div class="result-item">
          <span class="result-label">交易次数</span>
          <strong class="result-value">{{ com.st.trades }}</strong>
        </div>
      </div>
      <ThemedChart class="chart" :option="option" autoresize />
      <div class="controls">
        <div class="control-row">
          <span class="control-label">突破 N</span>
          <input v-model.number="donN" type="range" min="10" max="80" step="1" class="slider" />
          <span class="control-value">{{ donN }}</span>
        </div>
        <div class="control-row">
          <span class="control-label">离场 M</span>
          <input v-model.number="donM" type="range" min="5" max="40" step="1" class="slider" />
          <span class="control-value">{{ donM }}</span>
        </div>
        <p class="hint">
          三个面板时间轴联动，可用鼠标滚轮缩放、拖动底部时间轴选择区间放大看细节。
          ① K线与通道带（绿虚线上轨/红虚线下轨）：价格走出通道触发「买入/卖出」；② 通道宽度 = 上轨 − 下轨，收窄意味着波动压缩、蓄势待发；
          ③ 策略净值（橙）对比买入持有（灰虚线），净值起点均为 100。N/M 越大通道越宽、交易越少也越「迟钝」。
        </p>
      </div>
    </template>
  </div>
</template>

<style scoped>
.dc { padding: 16px; }
.status { height: 470px; display: flex; align-items: center; justify-content: center; color: var(--text-3); font-size: 14px; }
.chart { height: 490px; }
.result { display: flex; gap: 22px; margin-bottom: 12px; padding: 12px 16px; background: var(--primary-soft); border-radius: var(--radius-sm); flex-wrap: wrap; }
.result-item { display: flex; flex-direction: column; gap: 2px; }
.result-label { font-size: 12px; color: var(--text-3); }
.result-value { font-size: 18px; font-weight: 700; }
.controls { margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border); display: flex; flex-direction: column; gap: 10px; }
.control-row { display: flex; align-items: center; gap: 12px; }
.control-label { width: 72px; font-size: 13px; color: var(--text-2); flex-shrink: 0; }
.slider { flex: 1; accent-color: var(--primary); cursor: pointer; }
.control-value { width: 44px; font-size: 13px; font-weight: 600; color: var(--primary); text-align: right; flex-shrink: 0; }
.hint { margin-top: 10px; font-size: 12px; color: var(--text-3); line-height: 1.7; }
</style>
