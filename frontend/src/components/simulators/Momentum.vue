<script setup lang="ts">
import { computed, ref } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C, withAlpha } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, CandlestickChart, ScatterChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, DataZoomComponent } from 'echarts/components'
import { useStockDaily } from '@/composables/useStockDaily'
import { momentumSignal, shiftPosition, strategyNav, stats, backtestArrays } from '@/utils/strategies'

use([CanvasRenderer, LineChart, CandlestickChart, ScatterChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent])

// 时序动量（真实茅台 2020-2026）：过去 N 日涨则持有
const props = defineProps<{
  params?: Record<string, unknown>
}>()

const code = computed(() => (typeof props.params?.code === 'string' ? props.params.code : 'sh600519'))
const start = computed(() => (typeof props.params?.start === 'string' ? props.params.start : '2020-01-01'))
const end = computed(() => (typeof props.params?.end === 'string' ? props.params.end : '2026-08-10'))
const { data, loading, error } = useStockDaily(code, start.value, end.value)

const lookback = ref(20)

// 当前缩放窗口（百分比），用于 y 轴按可见 K 线高低价自适应
const zoom = ref({ start: 69.8, end: 100 })

function onDataZoom(params: any) {
  const p = params?.batch?.[0] ?? params
  if (p && typeof p.start === 'number' && typeof p.end === 'number') {
    zoom.value = { start: p.start, end: p.end }
  }
}

const com = computed(() => {
  if (!data.value) return null
  const arr = backtestArrays(data.value)
  const pos = shiftPosition(momentumSignal(arr.closes, lookback.value))
  const nav = strategyNav(arr.ret, pos)
  const buyNav = strategyNav(arr.ret, arr.closes.map(() => 1))
  const st = stats(arr.ret, pos)
  const bh = stats(arr.ret, arr.closes.map(() => 1))
  // 过去 lookback 日收益
  const pastRet = arr.closes.map((_, i) => (i < lookback.value ? null : +((arr.closes[i] / arr.closes[i - lookback.value] - 1) * 100).toFixed(1)))
  // 交易时点：0→1 买入、1→0 卖出（shiftPosition 已含次日生效，用 pos 变化定位）
  const buyIdx: number[] = []
  const sellIdx: number[] = []
  for (let i = 1; i < pos.length; i++) {
    if (pos[i] === 1 && pos[i - 1] === 0) buyIdx.push(i)
    if (pos[i] === 0 && pos[i - 1] === 1) sellIdx.push(i)
  }
  const ohlc = data.value.map((d) => [d.open, d.close, d.low, d.high])
  return { arr, pos, nav, buyNav, st, bh, pastRet, buyIdx, sellIdx, ohlc }
})

const option = computed(() => {
  if (!com.value) return {}
  const c = com.value
  // 当前可见窗口内 K 线的最高/最低价（随 dataZoom 缩放自适应）
  const n = c.arr.lows.length
  const s = Math.max(0, Math.min(n - 1, Math.floor((zoom.value.start / 100) * n)))
  const e = Math.max(s + 1, Math.min(n, Math.ceil((zoom.value.end / 100) * n)))
  let vMin = Infinity
  let vMax = -Infinity
  for (let i = s; i < e; i++) {
    if (c.arr.lows[i] < vMin) vMin = c.arr.lows[i]
    if (c.arr.highs[i] > vMax) vMax = c.arr.highs[i]
  }
  // 主图：价格 + 持仓色区
  return {
    animation: true,
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    tooltip: {
      trigger: 'axis',
      formatter: (ps: any[]) => {
        const pr = ps.find((p: any) => p.seriesName === '股价')
        const mom = ps.find((p: any) => p.seriesName === '过去收益')
        const nav = ps.find((p: any) => p.seriesName === '策略净值')
        const bh = ps.find((p: any) => p.seriesName === '买入持有')
        const name = pr?.name ?? nav?.name ?? ''
        const parts: string[] = []
        if (name) parts.push(`<b>${name}</b>`)
        if (pr) {
          const [o, c, l, h] = pr.value as number[]
          parts.push(`开 ${o} / 收 ${c}<br/>高 ${h} / 低 ${l}`)
        }
        if (mom && mom.value[1] !== '-') parts.push(`　过去${lookback.value}日收益 ${mom.value[1]}%`)
        if (nav || bh) parts.push('净值对比（起点 100）：')
        if (nav) parts.push(`　策略净值 ${Number(nav.value[1]).toFixed(1)}`)
        if (bh) parts.push(`　买入持有 ${Number(bh.value[1]).toFixed(1)}`)
        return parts.join('<br/>')
      },
    },
    legend: { top: 0, textStyle: { fontSize: 12 }, data: ['股价', '买入', '卖出', '策略净值', '买入持有', '过去收益'] },
    grid: [
      { left: 52, right: 24, top: 30, height: '58%' },
      { left: 52, right: 24, top: '72%', height: '16%' },
    ],
    dataZoom: [
      {
        type: 'inside',
        xAxisIndex: [0, 1],
        start: 69.8,
        end: 100,
        zoomOnMouseWheel: true,
        moveOnMouseMove: true,
      },
      {
        type: 'slider',
        xAxisIndex: [0, 1],
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
      { type: 'category', data: c.arr.dates, gridIndex: 0, axisLabel: { show: false }, axisPointer: { label: { show: false } } },
      { type: 'category', data: c.arr.dates, gridIndex: 1, axisLabel: { fontSize: 10, hideOverlap: true } },
    ],
    yAxis: [
      { type: 'value', gridIndex: 0, scale: true, axisLabel: { fontSize: 11 }, min: vMin === Infinity ? undefined : vMin, max: vMax === -Infinity ? undefined : vMax },
      { type: 'value', gridIndex: 1, scale: true, axisLabel: { fontSize: 10 } },
    ],
    series: [
      {
        name: '股价',
        type: 'candlestick',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: c.ohlc,
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
        data: c.buyIdx.map((i) => [c.arr.dates[i], c.arr.lows[i]]),
        symbol: 'triangle',
        symbolRotate: 180,
        symbolSize: 9,
        itemStyle: { color: C.value.success },
        z: 3,
      },
      {
        name: '卖出',
        type: 'scatter',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: c.sellIdx.map((i) => [c.arr.dates[i], c.arr.highs[i]]),
        symbol: 'triangle',
        symbolSize: 9,
        itemStyle: { color: C.value.danger },
        z: 3,
      },
      {
        name: '策略净值',
        type: 'line',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: c.nav.map((v, i) => [c.arr.dates[i], +v.toFixed(1)]),
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 2, color: C.value.warning },
        itemStyle: { color: C.value.warning },
      },
      {
        name: '买入持有',
        type: 'line',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: c.buyNav.map((v, i) => [c.arr.dates[i], +v.toFixed(1)]),
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 1.2, color: C.value.slateStrong, type: 'dashed' },
        itemStyle: { color: C.value.slateStrong },
      },
      {
        name: '过去收益',
        type: 'line',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: c.pastRet.map((v, i) => [c.arr.dates[i], v === null ? '-' : v]),
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 1, color: C.value.violet, opacity: 0.7 },
        itemStyle: { color: C.value.violet },
      },
    ],
  }
})

const st = computed(() => com.value?.st)

</script>

<template>
  <div class="mm">
    <div v-if="loading" class="status">数据加载中…</div>
    <div v-else-if="error" class="status">数据不可用</div>
    <template v-else-if="com && st">
      <div class="result">
        <div class="result-item">
          <span class="result-label">累计收益</span>
          <strong class="result-value" :style="{ color: st.cum >= 0 ? 'var(--success, #16a34a)' : 'var(--danger, #dc2626)' }">{{ (st.cum * 100).toFixed(1) }}%</strong>
        </div>
        <div class="result-item">
          <span class="result-label">最大回撤</span>
          <strong class="result-value" style="color: var(--danger, #dc2626)">{{ (st.mdd * 100).toFixed(1) }}%</strong>
        </div>
        <div class="result-item">
          <span class="result-label">持仓占比</span>
          <strong class="result-value">{{ (st.posMean * 100).toFixed(1) }}%</strong>
        </div>
        <div class="result-item">
          <span class="result-label">信号次数</span>
          <strong class="result-value">{{ st.switches }}</strong>
        </div>
      </div>
      <ThemedChart class="chart" :option="option" autoresize @datazoom="onDataZoom" />
      <div class="controls">
        <div class="control-row">
          <span class="control-label">回看 N</span>
          <input v-model.number="lookback" type="range" min="5" max="120" step="1" class="slider" />
          <span class="control-value">{{ lookback }}</span>
        </div>
        <p class="hint">
          K 线为真实价格；▼ 买入、▲ 卖出标在交易日的低价下方/高价上方，不遮挡蜡烛。「过去收益」> 0 时持有。N 越大越「慢」——参数即世界观。
        </p>
      </div>
    </template>
  </div>
</template>

<style scoped>
.mm { padding: 16px; }
.status { height: 380px; display: flex; align-items: center; justify-content: center; color: var(--text-3); font-size: 14px; }
.chart { height: 360px; }
.result { display: flex; gap: 22px; margin-bottom: 12px; padding: 12px 16px; background: var(--primary-soft); border-radius: var(--radius-sm); flex-wrap: wrap; }
.result-item { display: flex; flex-direction: column; gap: 2px; }
.result-label { font-size: 12px; color: var(--text-3); }
.result-value { font-size: 18px; font-weight: 700; }
.controls { margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--border); display: flex; flex-direction: column; gap: 10px; }
.control-row { display: flex; align-items: center; gap: 12px; }
.control-label { width: 72px; font-size: 13px; color: var(--text-2); flex-shrink: 0; }
.slider { flex: 1; accent-color: var(--primary); cursor: pointer; }
.control-value { width: 56px; font-size: 13px; font-weight: 600; color: var(--primary); text-align: right; flex-shrink: 0; }
.hint { margin-top: 10px; font-size: 12px; color: var(--text-3); line-height: 1.7; }
</style>