<script setup lang="ts">
import { computed, ref } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, MarkPointComponent, MarkLineComponent } from 'echarts/components'
import { useStockDaily } from '@/composables/useStockDaily'
import {
  sma,
  donchianSignal,
  maCrossSignal,
  shiftPosition,
  strategyNav,
  stats,
  backtestArrays,
} from '@/utils/strategies'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent, MarkPointComponent, MarkLineComponent])

// 趋势跟踪模拟器：均线交叉 / 唐奇安通道，真实茅台 2020-2026

const props = defineProps<{
  params?: Record<string, unknown>
}>()

const code = computed(() => (typeof props.params?.code === 'string' ? props.params.code : 'sh600519'))
const start = computed(() => (typeof props.params?.start === 'string' ? props.params.start : '2020-01-01'))
const end = computed(() => (typeof props.params?.end === 'string' ? props.params.end : '2026-08-10'))
const strategy = computed(() => (typeof props.params?.strategy === 'string' ? props.params.strategy : 'ma'))
const { data, loading, error } = useStockDaily(code, start.value, end.value)

const fast = ref(20)
const slow = ref(60)
const donN = ref(20)
const donM = ref(10)
const effFast = computed(() => Math.min(fast.value, slow.value - 1))

const com = computed(() => {
  if (!data.value) return null
  const arr = backtestArrays(data.value)
  const pos = shiftPosition(
    strategy.value === 'donchian'
      ? donchianSignal(arr.highs, arr.lows, donN.value, donM.value)
      : maCrossSignal(arr.closes, effFast.value, slow.value),
  )
  const buyNav = strategyNav(arr.ret, arr.closes.map(() => 1))
  const nav = strategyNav(arr.ret, pos)
  const st = stats(arr.ret, pos)
  const bh = stats(arr.ret, arr.closes.map(() => 1))
  // 交易点
  const buyIdx: number[] = []
  const sellIdx: number[] = []
  for (let i = 1; i < pos.length; i++) {
    if (pos[i] > pos[i - 1]) buyIdx.push(i)
    else if (pos[i] < pos[i - 1]) sellIdx.push(i)
  }
  const f = strategy.value === 'donchian' ? null : sma(arr.closes, effFast.value).map((v) => (v === null ? '-' : +v.toFixed(1)))
  const s = strategy.value === 'donchian' ? null : sma(arr.closes, slow.value).map((v, i) => [arr.dates[i], v === null ? '-' : +v.toFixed(1)])
  return { arr, pos, nav, buyNav, st, bh, buyIdx, sellIdx, f, s, dates: arr.dates, closes: arr.closes }
})

const option = computed(() => {
  if (!com.value) return {}
  const c = com.value
  const buyp = c.buyIdx.map((i) => ({ coord: [c.dates[i], c.closes[i]], value: '买', itemStyle: { color: '#16a34a' } }))
  const sellp = c.sellIdx.map((i) => ({ coord: [c.dates[i], c.closes[i]], value: '卖', itemStyle: { color: '#dc2626' } }))
  return {
    animation: true,
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    tooltip: {
      trigger: 'axis',
      formatter: (ps: any[]) => {
        const nav = ps.find((p: any) => p.seriesName === '策略净值')
        const bh = ps.find((p: any) => p.seriesName === '买入持有')
        const price = ps.find((p: any) => p.seriesName === '收盘价')
        const parts = [price ? `${price.name}<br/>收盘 ${price.value[1]}` : nav?.name ?? '']
        if (nav) parts.push(`策略净值 ${Number(nav.value[1]).toFixed(1)}`)
        if (bh) parts.push(`买入持有 ${Number(bh.value[1]).toFixed(1)}`)
        return parts.join('<br/>')
      },
    },
    legend: {
      top: 0,
      textStyle: { fontSize: 12 },
      data: strategy.value === 'donchian' ? ['收盘价', '策略净值', '买入持有'] : ['收盘价', `MA${effFast.value}`, `MA${slow.value}`, '策略净值', '买入持有'],
    },
    grid: [
      { left: 52, right: 24, top: 40, height: '46%' },
      { left: 52, right: 24, top: '58%', height: '30%' },
    ],
    xAxis: [
      { type: 'category', data: c.dates, gridIndex: 0, axisLabel: { show: false }, axisPointer: { label: { show: false } } },
      { type: 'category', data: c.dates, gridIndex: 1, axisLabel: { fontSize: 10, hideOverlap: true } },
    ],
    yAxis: [
      { type: 'value', gridIndex: 0, scale: true, axisLabel: { fontSize: 11 } },
      { type: 'value', gridIndex: 1, scale: true, axisLabel: { fontSize: 10 } },
    ],
    series: [
      {
        name: '收盘价',
        type: 'line',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: c.closes.map((v, i) => [c.dates[i], v]),
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 1.5, color: '#2563eb' },
        itemStyle: { color: '#2563eb' },
        markPoint: { symbolSize: 42, label: { fontSize: 10, color: '#fff' }, data: [...buyp, ...sellp] },
      },
...(strategy.value === 'donchian'
        ? []
        : [
            {
              name: `MA${effFast.value}`,
              type: 'line',
              xAxisIndex: 0,
              yAxisIndex: 0,
              data: c.f!.map((v, i) => [c.dates[i], v]),
              smooth: true,
              symbol: 'none',
              lineStyle: { width: 1, color: '#d97706', opacity: 0.9 },
              itemStyle: { color: '#d97706' },
            },
            {
              name: `MA${slow.value}`,
              type: 'line',
              xAxisIndex: 0,
              yAxisIndex: 0,
              data: c.s!.map((v, i) => [c.dates[i], v]),
              smooth: true,
              symbol: 'none',
              lineStyle: { width: 1, color: '#dc2626', opacity: 0.9 },
              itemStyle: { color: '#dc2626' },
            },
          ]),
      {
        name: '策略净值',
        type: 'line',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: c.nav.map((v, i) => [c.dates[i], +v.toFixed(1)]),
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 2, color: '#d97706' },
        itemStyle: { color: '#d97706' },
      },
      {
        name: '买入持有',
        type: 'line',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: c.buyNav.map((v, i) => [c.dates[i], +v.toFixed(1)]),
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 1.5, color: '#64748b', type: 'dashed' },
        itemStyle: { color: '#64748b' },
      },
    ],
  }
})
</script>

<template>
  <div class="tf">
    <div v-if="loading" class="status">数据加载中…</div>
    <div v-else-if="error" class="status">数据不可用</div>
    <template v-else-if="com">
      <div class="controls top">
        <div class="mode-row">
          策略类型：
          <button :class="{ on: strategy !== 'donchian' }" disabled>均线交叉</button>
          <span v-if="strategy === 'donchian'" class="mode-active">唐奇安通道</span>
          <span v-else class="mode-active">均线交叉</span>
        </div>
      </div>
      <div class="result">
        <div class="result-item">
          <span class="result-label">累计收益</span>
          <strong class="result-value" :style="{ color: com.st.cum >= 0 ? '#16a34a' : '#dc2626' }">{{ (com.st.cum * 100).toFixed(1) }}%</strong>
        </div>
        <div class="result-item">
          <span class="result-label">年化收益</span>
          <strong class="result-value">{{ (com.st.ann * 100).toFixed(1) }}%</strong>
        </div>
        <div class="result-item">
          <span class="result-label">最大回撤</span>
          <strong class="result-value" style="color: #dc2626">{{ (com.st.mdd * 100).toFixed(1) }}%</strong>
        </div>
        <div class="result-item">
          <span class="result-label">Sharpe(rf 2%)</span>
          <strong class="result-value">{{ com.st.sharpe.toFixed(2) }}</strong>
        </div>
        <div class="result-item">
          <span class="result-label">持仓占比</span>
          <strong class="result-value">{{ (com.st.posMean * 100).toFixed(1) }}%</strong>
        </div>
      </div>
      <VChart class="chart" :option="option" autoresize />
      <div class="controls">
        <template v-if="strategy === 'donchian'">
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
          <p class="hint">突破过去 N 日最高买入，跌破过去 M 日最低离场。参数越大越「迟钝」，交易越少。</p>
        </template>
        <template v-else>
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
          <p class="hint">买入持有（灰虚线）波动大；策略（橙）靠「少在场」控制回撤。参数越短越灵敏。</p>
        </template>
      </div>
    </template>
  </div>
</template>

<style scoped>
.tf { padding: 16px; }
.status { height: 420px; display: flex; align-items: center; justify-content: center; color: var(--text-3); font-size: 14px; }
.chart { height: 430px; }
.result { display: flex; gap: 22px; margin-bottom: 12px; padding: 12px 16px; background: var(--primary-soft); border-radius: var(--radius-sm); flex-wrap: wrap; }
.result-item { display: flex; flex-direction: column; gap: 2px; }
.result-label { font-size: 12px; color: var(--text-3); }
.result-value { font-size: 18px; font-weight: 700; }
.controls { margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border); display: flex; flex-direction: column; gap: 10px; }
.controls.top { border-top: none; padding-top: 0; margin-top: 0; }
.mode-row { display: flex; align-items: center; gap: 10px; font-size: 13px; color: var(--text-2); }
.mode-row button { display: none; }
.mode-active { font-size: 13px; font-weight: 600; color: var(--primary); padding: 3px 10px; border-radius: var(--radius-sm); background: var(--primary-soft); }
.control-row { display: flex; align-items: center; gap: 12px; }
.control-label { width: 72px; font-size: 13px; color: var(--text-2); flex-shrink: 0; }
.slider { flex: 1; accent-color: var(--primary); cursor: pointer; }
.control-value { width: 44px; font-size: 13px; font-weight: 600; color: var(--primary); text-align: right; flex-shrink: 0; }
.hint { margin-top: 10px; font-size: 12px; color: var(--text-3); line-height: 1.7; }
</style>