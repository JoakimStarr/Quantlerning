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
} from 'echarts/components'
import { useStockDaily } from '@/composables/useStockDaily'
import { sma, rollingStd } from '@/utils/strategies'

use([CanvasRenderer, LineChart, ScatterChart, CandlestickChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent])

// 布林带（真实茅台 2020-2026）：中轨 + ±kσ，z-score 触轨提示
const props = defineProps<{
  params?: Record<string, unknown>
}>()

const code = computed(() => (typeof props.params?.code === 'string' ? props.params.code : 'sh600519'))
const start = computed(() => (typeof props.params?.start === 'string' ? props.params.start : '2020-01-01'))
const end = computed(() => (typeof props.params?.end === 'string' ? props.params.end : '2026-08-10'))
const { data, loading, error } = useStockDaily(code, start.value, end.value)

const period = ref(20)
const k = ref(2)
const priceStyle = ref<'line' | 'candle'>('line')

const dates = computed(() => data.value?.map((d) => d.date) ?? [])
const closes = computed(() => data.value?.map((d) => d.close) ?? [])
const lows = computed(() => data.value?.map((d) => d.low) ?? [])
const highs = computed(() => data.value?.map((d) => d.high) ?? [])
const ohlc = computed(() => data.value?.map((d) => [d.open, d.close, d.low, d.high]) ?? [])

const com = computed(() => {
  if (!data.value) return null
  const mid = sma(closes.value, period.value)
  const sd = rollingStd(closes.value, period.value)
  const upper = mid.map((v, i) => (v === null || sd[i] === null ? null : v + k.value * sd[i]!))
  const lower = mid.map((v, i) => (v === null || sd[i] === null ? null : v - k.value * sd[i]!))
  // 触轨点：收盘跌破下轨 / 升破上轨
  const touchLow: number[] = []
  const touchHigh: number[] = []
  for (let i = period.value; i < closes.value.length; i++) {
    if (lower[i] !== null && closes.value[i] < lower[i]!) touchLow.push(i)
    if (upper[i] !== null && closes.value[i] > upper[i]!) touchHigh.push(i)
  }
  return { mid, upper, lower, touchLow, touchHigh }
})

const option = computed(() => {
  if (!com.value) return {}
  const dates0 = dates.value
  const band = (v: (number | null)[]) => v.map((x, i) => [dates0[i], x === null ? '-' : +x.toFixed(1)])
  const price = closes.value.map((v, i) => [dates0[i], v])
  const priceSeries =
    priceStyle.value === 'candle'
      ? {
          name: '股价',
          type: 'candlestick' as const,
          data: ohlc.value,
          itemStyle: {
            color: C.value.danger,
            color0: C.value.success,
            borderColor: C.value.danger,
            borderColor0: C.value.success,
            borderWidth: 1,
          },
        }
      : {
          name: '股价',
          type: 'line' as const,
          data: price,
          smooth: true,
          symbol: 'none',
          lineStyle: { width: 1.5, color: C.value.primary },
        }
  return {
    animation: true,
    tooltip: {
      trigger: 'axis',
      formatter: (ps: any[]) => {
        const p = ps.find((q: any) => q.seriesName === '股价')
        const touch = ps.find((q: any) => q.seriesName === '触下轨' || q.seriesName === '触上轨')
        if (!p && !touch) return ''
        if (!p) return `${touch.name}<br/>${touch.seriesName}`
        let html: string
        if (p.seriesType === 'candlestick') {
          const [o, c, l, h] = p.value as number[]
          html = `${p.name}<br/>开 ${o} / 收 ${c}<br/>高 ${h} / 低 ${l}`
        } else {
          html = `${p.name}<br/>收盘 ${p.value[1]}`
        }
        if (touch) html += `<br/>${touch.seriesName}`
        return html
      },
    },
    legend: { top: 0, textStyle: { fontSize: 12 }, data: ['股价', '中轨', '上轨', '下轨', '触下轨', '触上轨'] },
    grid: { left: 52, right: 24, top: 32, bottom: 44 },
    dataZoom: [
      {
        type: 'inside',
        xAxisIndex: [0],
        start: 69.8,
        end: 100,
        zoomOnMouseWheel: true,
        moveOnMouseMove: true,
      },
      {
        type: 'slider',
        xAxisIndex: [0],
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
    xAxis: { type: 'category', data: dates0, axisLabel: { fontSize: 10, hideOverlap: true } },
    yAxis: { type: 'value', scale: true, axisLabel: { fontSize: 11 } },
    series: [
      priceSeries,
      { name: '中轨', type: 'line', data: band(com.value.mid), symbol: 'none', lineStyle: { width: 1, color: C.value.slateStrong, type: 'dashed' } },
      { name: '上轨', type: 'line', data: band(com.value.upper), symbol: 'none', lineStyle: { width: 1, color: C.value.danger, opacity: 0.7 } },
      { name: '下轨', type: 'line', data: band(com.value.lower), symbol: 'none', lineStyle: { width: 1, color: C.value.success, opacity: 0.7 } },
      {
        name: '触上轨',
        type: 'scatter',
        data: com.value.touchHigh.map((i) => [dates0[i], lows.value[i]]),
        symbol: 'triangle',
        symbolSize: 9,
        itemStyle: { color: C.value.danger },
        z: 3,
      },
      {
        name: '触下轨',
        type: 'scatter',
        data: com.value.touchLow.map((i) => [dates0[i], highs.value[i]]),
        symbol: 'triangle',
        symbolRotate: 180,
        symbolSize: 9,
        itemStyle: { color: C.value.success },
        z: 3,
      },
    ],
  }
})

const touchLowCount = computed(() => com.value?.touchLow.length ?? 0)
const touchHighCount = computed(() => com.value?.touchHigh.length ?? 0)
</script>

<template>
  <div class="bb">
    <div v-if="loading" class="status">数据加载中…</div>
    <div v-else-if="error" class="status">数据不可用</div>
    <template v-else-if="com">
      <div class="result">
        <div class="result-item">
          <span class="result-label">价格通道</span>
          <strong class="result-value">MA{{ period }} ± {{ k }}σ</strong>
        </div>
        <div class="result-item">
          <span class="result-label">跌破下轨次数</span>
          <strong class="result-value" style="color: var(--success, #16a34a)">{{ touchLowCount }}</strong>
        </div>
        <div class="result-item">
          <span class="result-label">升破上轨次数</span>
          <strong class="result-value" style="color: var(--danger, #dc2626)">{{ touchHighCount }}</strong>
        </div>
      </div>
      <ThemedChart class="chart" :option="option" autoresize />
      <div class="controls">
        <div class="control-row">
          <span class="control-label">价格样式</span>
          <div class="seg">
            <button :class="{ active: priceStyle === 'line' }" @click="priceStyle = 'line'">折线</button>
            <button :class="{ active: priceStyle === 'candle' }" @click="priceStyle = 'candle'">K线</button>
          </div>
        </div>
        <div class="control-row">
          <span class="control-label">周期 N</span>
          <input v-model.number="period" type="range" min="5" max="60" step="1" class="slider" />
          <span class="control-value">{{ period }}</span>
        </div>
        <div class="control-row">
          <span class="control-label">带宽 k</span>
          <input v-model.number="k" type="range" min="1" max="3" step="0.1" class="slider" />
          <span class="control-value">{{ k.toFixed(1) }}σ</span>
        </div>
        <p class="hint">
          价格反复穿越轨道 → 回归信号。▲ 标在触上轨日的 K 线最低价下方、▼ 标在触下轨日的最高价上方，不遮挡蜡烛；周期越短、k 越小，触轨越频繁。
        </p>
      </div>
    </template>
  </div>
</template>

<style scoped>
.bb { padding: 16px; }
.status { height: 380px; display: flex; align-items: center; justify-content: center; color: var(--text-3); font-size: 14px; }
.chart { height: 360px; }
.result { display: flex; gap: 22px; margin-bottom: 12px; padding: 12px 16px; background: var(--primary-soft); border-radius: var(--radius-sm); }
.result-item { display: flex; flex-direction: column; gap: 2px; }
.result-label { font-size: 12px; color: var(--text-3); }
.result-value { font-size: 18px; font-weight: 700; }
.controls { margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--border); display: flex; flex-direction: column; gap: 10px; }
.control-row { display: flex; align-items: center; gap: 12px; }
.control-label { width: 72px; font-size: 13px; color: var(--text-2); flex-shrink: 0; }
.slider { flex: 1; accent-color: var(--primary); cursor: pointer; }
.control-value { width: 56px; font-size: 13px; font-weight: 600; color: var(--primary); text-align: right; flex-shrink: 0; }
.seg { display: inline-flex; border: 1px solid var(--border); border-radius: 6px; overflow: hidden; }
.seg button { padding: 4px 14px; font-size: 13px; background: transparent; color: var(--text-2); border: none; cursor: pointer; }
.seg button.active { background: var(--primary); color: #fff; font-weight: 600; }
.hint { margin-top: 10px; font-size: 12px; color: var(--text-3); line-height: 1.7; }
</style>