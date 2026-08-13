<script setup lang="ts">
import { computed, ref } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C, withAlpha } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { useStockDaily } from '@/composables/useStockDaily'
import { maCrossSignal, shiftPosition, strategyNav, backtestArrays } from '@/utils/strategies'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent])

// 朴素回测逐日重放（真实茅台 2020-2026）：上价格+持仓，下净值
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
  const pos = shiftPosition(maCrossSignal(arr.closes, effFast.value, slow.value))
  const nav = strategyNav(arr.ret, pos)
  const buyNav = strategyNav(arr.ret, arr.closes.map(() => 1))
  return { arr, pos, nav, buyNav }
})

const option = computed(() => {
  if (!com.value) return {}
  const c = com.value
  return {
    animation: true,
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    tooltip: {
      trigger: 'axis',
      formatter: (ps: any[]) => {
        const price = ps.find((p: any) => p.seriesName === '收盘价')
        const nav = ps.find((p: any) => p.seriesName === '策略净值')
        const bh = ps.find((p: any) => p.seriesName === '买入持有')
        const pos = ps.find((p: any) => p.seriesName === '持仓')
        const parts = [price ? `${price.name}<br/>收盘 ${price.value[1]}` : (nav?.name ?? '')]
        if (pos) parts.push(`持仓 ${pos.value[1] === 1 ? '满仓' : '空仓'}`)
        if (nav) parts.push(`策略净值 ${Number(nav.value[1]).toFixed(1)}`)
        if (bh) parts.push(`买入持有 ${Number(bh.value[1]).toFixed(1)}`)
        return parts.join('<br/>')
      },
    },
    legend: { top: 0, textStyle: { fontSize: 12 }, data: ['收盘价', '持仓', '策略净值', '买入持有'] },
    grid: [
      { left: 52, right: 24, top: 40, height: '42%' },
      { left: 52, right: 24, top: '52%', height: '10%' },
      { left: 52, right: 24, top: '70%', height: '20%' },
    ],
    xAxis: [
      { type: 'category', data: c.arr.dates, gridIndex: 0, axisLabel: { show: false }, axisPointer: { label: { show: false } } },
      { type: 'category', data: c.arr.dates, gridIndex: 1, axisLabel: { show: false }, axisPointer: { label: { show: false } } },
      { type: 'category', data: c.arr.dates, gridIndex: 2, axisLabel: { fontSize: 10, hideOverlap: true } },
    ],
    yAxis: [
      { type: 'value', gridIndex: 0, scale: true, axisLabel: { fontSize: 11 } },
      { type: 'value', gridIndex: 1, min: 0, max: 1, splitNumber: 1, axisLabel: { fontSize: 10, formatter: (v: number) => (v === 1 ? '满' : v === 0 ? '空' : '') } },
      { type: 'value', gridIndex: 2, scale: true, axisLabel: { fontSize: 10 } },
    ],
    series: [
      {
        name: '收盘价',
        type: 'line',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: c.arr.closes.map((v, i) => [c.arr.dates[i], v]),
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 1.3, color: C.value.primary },
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
        areaStyle: { color: withAlpha(C.value.cyan, 0.12) },
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
      },
    ],
  }
})
</script>

<template>
  <div class="be">
    <div v-if="loading" class="status">数据加载中…</div>
    <div v-else-if="error" class="status">数据不可用</div>
    <template v-else-if="com">
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
          逐日重放：t 日收盘看均线关系 → t+1 日按持仓在盘初成交 → 当日收盘计净值。持仓绿区与净值一一对应。
        </p>
      </div>
    </template>
  </div>
</template>

<style scoped>
.be { padding: 16px; }
.status { height: 420px; display: flex; align-items: center; justify-content: center; color: var(--text-3); font-size: 14px; }
.chart { height: 440px; }
.controls { margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--border); display: flex; flex-direction: column; gap: 10px; }
.control-row { display: flex; align-items: center; gap: 12px; }
.control-label { width: 72px; font-size: 13px; color: var(--text-2); flex-shrink: 0; }
.slider { flex: 1; accent-color: var(--primary); cursor: pointer; }
.control-value { width: 44px; font-size: 13px; font-weight: 600; color: var(--primary); text-align: right; flex-shrink: 0; }
.hint { margin-top: 10px; font-size: 12px; color: var(--text-3); line-height: 1.7; }
</style>