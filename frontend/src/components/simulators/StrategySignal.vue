<script setup lang="ts">
import { computed, ref } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C, withAlpha } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, ScatterChart, CandlestickChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, DataZoomComponent } from 'echarts/components'
import { useStockDaily } from '@/composables/useStockDaily'
import { sma, shiftPosition, strategyNav, stats, backtestArrays } from '@/utils/strategies'

use([CanvasRenderer, LineChart, ScatterChart, CandlestickChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent])

// 策略解剖：真实行情 + 双均线信号 → 持仓映射 → 净值与回测指标（p2-l1）

const props = defineProps<{
  params?: Record<string, unknown>
}>()

const code = computed(() => (typeof props.params?.code === 'string' ? props.params.code : 'sh600519'))
const start = computed(() => (typeof props.params?.start === 'string' ? props.params.start : '2020-01-01'))
const end = computed(() => (typeof props.params?.end === 'string' ? props.params.end : '2026-08-10'))
const { data, loading, error } = useStockDaily(code, start.value, end.value)

const fast = ref(20)
const slow = ref(60)
const effFast = computed(() => Math.min(fast.value, slow.value - 1))

const com = computed(() => {
  if (!data.value) return null
  const arr = backtestArrays(data.value)
  const f = sma(arr.closes, effFast.value)
  const s = sma(arr.closes, slow.value)
  // 信号：金叉/死叉次日生效的持仓
  const rawSig = arr.closes.map((_, i) => {
    if (f[i] === null || s[i] === null) return 0
    return f[i]! > s[i]! ? 1 : 0
  })
  const pos = shiftPosition(rawSig)
  // 交易点：持仓变化处（金叉→次日做多，死叉→次日空仓）
  const buyIdx: number[] = []
  const sellIdx: number[] = []
  for (let i = 1; i < pos.length; i++) {
    if (pos[i] > pos[i - 1]) buyIdx.push(i)
    else if (pos[i] < pos[i - 1]) sellIdx.push(i)
  }
  const nav = strategyNav(arr.ret, pos)
  const buyNav = strategyNav(arr.ret, arr.closes.map(() => 1))
  const st = stats(arr.ret, pos)
  return { arr, f, s, pos, nav, buyNav, st, buyIdx, sellIdx }
})

const option = computed(() => {
  const c = com.value
  if (!c) return {}
  const f = c.f.map((v, i) => [c.arr.dates[i], v === null ? '-' : +v.toFixed(1)])
  const s = c.s.map((v, i) => [c.arr.dates[i], v === null ? '-' : +v.toFixed(1)])
  const maFast = `MA${effFast.value}`
  const maSlow = `MA${slow.value}`
  return {
    animation: true,
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    tooltip: {
      trigger: 'axis',
      formatter: (ps: any[]) => {
        const hp = ps.find((p: any) => p.seriesName === '收盘价')
        const fv = ps.find((p: any) => p.seriesName === maFast)
        const sv = ps.find((p: any) => p.seriesName === maSlow)
        const hh = ps.find((p: any) => p.seriesName === '持仓')
        const nv = ps.find((p: any) => p.seriesName === '策略净值')
        const bv = ps.find((p: any) => p.seriesName === '买入持有')
        const name = hp?.name ?? nv?.name ?? ''
        const parts: string[] = []
        if (name) parts.push(`<b>${name}</b>`)
        if (hp || fv || sv) parts.push('K线与买卖信号：')
        if (hp) parts.push(`　收盘 ${hp.value[1]} 元`)
        if (fv) parts.push(`　${maFast} ${fv.value[1]}`)
        if (sv) parts.push(`　${maSlow} ${sv.value[1]}`)
        if (hh) parts.push('持仓状态（0/1）：')
        if (hh) parts.push(`　${hh.value[1] === 1 ? '全仓' : '空仓'}`)
        if (nv || bv) parts.push('净值对比（起点 100）：')
        if (nv) parts.push(`　策略净值 ${Number(nv.value[1]).toFixed(1)}`)
        if (bv) parts.push(`　买入持有 ${Number(bv.value[1]).toFixed(1)}`)
        return parts.join('<br/>')
      },
    },
    legend: {
      top: 0,
      textStyle: { fontSize: 12 },
      data: ['收盘价', maFast, maSlow, '买入', '卖出', '持仓', '策略净值', '买入持有'],
    },
    grid: [
      { left: 56, right: 24, top: 32, height: '36%' },
      { left: 56, right: 24, top: '53%', height: '12%' },
      { left: 56, right: 24, top: '68%', height: '22%' },
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
      {
        type: 'category',
        data: c.arr.dates,
        gridIndex: 0,
        axisLabel: { show: false },
        axisPointer: { label: { show: false } },
      },
      {
        type: 'category',
        data: c.arr.dates,
        gridIndex: 1,
        axisLabel: { show: false },
        axisPointer: { label: { show: false } },
      },
      {
        type: 'category',
        data: c.arr.dates,
        gridIndex: 2,
        axisLabel: { fontSize: 10, hideOverlap: true },
      },
    ],
    yAxis: [
      { type: 'value', gridIndex: 0, scale: true, axisLabel: { fontSize: 11 } },
      {
        type: 'value',
        gridIndex: 1,
        min: 0,
        max: 1,
        splitNumber: 1,
        axisLabel: { fontSize: 10, formatter: (v: number) => (v === 1 ? '①全仓' : v === 0 ? '〇空仓' : '') },
      },
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
        data: c.buyIdx.map((i) => [c.arr.dates[i], c.arr.lows[i]]),
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
        data: c.sellIdx.map((i) => [c.arr.dates[i], c.arr.highs[i]]),
        symbol: 'triangle',
        symbolRotate: 180,
        symbolSize: 9,
        itemStyle: { color: C.value.danger },
        z: 3,
      },
      {
        name: maFast,
        type: 'line',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: f,
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 1, color: C.value.warning, opacity: 0.9 },
        itemStyle: { color: C.value.warning },
      },
      {
        name: maSlow,
        type: 'line',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: s,
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 1, color: C.value.danger, opacity: 0.9 },
        itemStyle: { color: C.value.danger },
      },
      {
        name: '持仓',
        type: 'line',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: c.pos.map((v, i) => [c.arr.dates[i], v]),
        symbol: 'none',
        step: 'end',
        lineStyle: { width: 2, color: C.value.cyan },
        itemStyle: { color: C.value.cyan },
        areaStyle: { color: withAlpha(C.value.cyan, 0.15) },
      },
      {
        name: '策略净值',
        type: 'line',
        xAxisIndex: 2,
        yAxisIndex: 2,
        data: c.nav.map((v, i) => [c.arr.dates[i], +v.toFixed(1)]),
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
        data: c.buyNav.map((v, i) => [c.arr.dates[i], +v.toFixed(1)]),
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 1.2, color: C.value.slateStrong, type: 'dashed' },
        itemStyle: { color: C.value.slateStrong },
      },
    ],
  }
})
</script>

<template>
  <div class="ss">
    <div v-if="loading" class="status">数据加载中…</div>
    <div v-else-if="error" class="status">数据不可用</div>
    <template v-else-if="com">
      <div class="result">
        <div class="result-item">
          <span class="result-label">累计收益</span>
          <strong class="result-value" :style="{ color: com.st.cum >= 0 ? 'var(--success, #16a34a)' : 'var(--danger, #dc2626)' }">{{ (com.st.cum * 100).toFixed(1) }}%</strong>
        </div>
        <div class="result-item">
          <span class="result-label">年化收益</span>
          <strong class="result-value">{{ (com.st.ann * 100).toFixed(1) }}%</strong>
        </div>
        <div class="result-item">
          <span class="result-label">最大回撤</span>
          <strong class="result-value" style="color: var(--danger, #dc2626)">{{ (com.st.mdd * 100).toFixed(1) }}%</strong>
        </div>
        <div class="result-item">
          <span class="result-label">Sharpe(rf 2%)</span>
          <strong class="result-value">{{ com.st.sharpe.toFixed(2) }}</strong>
        </div>
        <div class="result-item">
          <span class="result-label">胜率</span>
          <strong class="result-value">{{ (com.st.winRate * 100).toFixed(0) }}%</strong>
        </div>
        <div class="result-item">
          <span class="result-label">持仓占比</span>
          <strong class="result-value">{{ (com.st.posMean * 100).toFixed(1) }}%</strong>
        </div>
        <div class="result-item">
          <span class="result-label">信号次数</span>
          <strong class="result-value">{{ com.st.switches }}</strong>
        </div>
      </div>
      <ThemedChart class="chart" :option="option" autoresize />
      <div class="controls">
        <div class="control-row">
          <span class="control-label">快线 MA</span>
          <input v-model.number="fast" type="range" min="5" max="120" step="1" class="slider" />
          <span class="control-value">{{ effFast }}</span>
        </div>
        <div class="control-row">
          <span class="control-label">慢线 MA</span>
          <input v-model.number="slow" type="range" min="10" max="250" step="1" class="slider" />
          <span class="control-value">{{ slow }}</span>
        </div>
        <p class="hint">
          信号（金叉/死叉）→ 持仓（次日生效）→ 成交（次日开盘）：三段式缺一不可。上图 K 线与买卖点（▲ 买入标在最低价下方、▼ 卖出标在最高价上方）、中图持仓、下图净值（橙）对比买入持有（灰虚线），回测指标随参数实时更新。
        </p>
      </div>
    </template>
  </div>
</template>

<style scoped>
.ss { padding: 16px; }
.status { height: 520px; display: flex; align-items: center; justify-content: center; color: var(--text-3); font-size: 14px; }
.chart { height: 520px; }
.result { display: flex; gap: 28px; margin-bottom: 12px; padding: 12px 16px; background: var(--primary-soft); border-radius: var(--radius-sm); flex-wrap: wrap; }
.result-item { display: flex; flex-direction: column; gap: 2px; }
.result-label { font-size: 12px; color: var(--text-3); }
.result-value { font-size: 20px; font-weight: 700; }
.controls { margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--border); display: flex; flex-direction: column; gap: 10px; }
.control-row { display: flex; align-items: center; gap: 12px; }
.control-label { width: 72px; font-size: 13px; color: var(--text-2); flex-shrink: 0; }
.slider { flex: 1; accent-color: var(--primary); cursor: pointer; }
.control-value { width: 44px; font-size: 13px; font-weight: 600; color: var(--primary); text-align: right; flex-shrink: 0; }
.hint { margin-top: 10px; font-size: 12px; color: var(--text-3); line-height: 1.7; }
</style>
