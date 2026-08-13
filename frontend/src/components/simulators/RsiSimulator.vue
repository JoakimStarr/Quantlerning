<script setup lang="ts">
import { computed, ref } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C, withAlpha } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, MarkLineComponent, MarkAreaComponent } from 'echarts/components'
import { useStockDaily } from '@/composables/useStockDaily'
import { rsi } from '@/utils/indicators'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, MarkLineComponent, MarkAreaComponent])

// RSI 模拟器：真实行情 + 周期可调
// RSI = 100 − 100/(1+RS)，RS = 平均涨幅/平均跌幅（Wilder 平滑）

const props = defineProps<{
  params?: Record<string, unknown>
}>()

const code = computed(() => (typeof props.params?.code === 'string' ? props.params.code : 'sh600519'))
const { data, loading, error } = useStockDaily(code)

const period = ref(14)

const dates = computed(() => data.value?.map((d) => d.date) ?? [])
const closes = computed(() => data.value?.map((d) => d.close) ?? [])

const rsiVals = computed(() => {
  if (closes.value.length === 0) return []
  return rsi(closes.value, period.value).map((v) => (v === null ? '-' : +v.toFixed(1)))
})

// 区间内最低收盘价日期（虚线标记），避免硬编码 2024-09-19 在换 code/区间时失效
const lowDate = computed(() => {
  if (!dates.value.length || !closes.value.length) return ''
  let idx = 0
  for (let i = 1; i < closes.value.length; i++) if (closes.value[i] < closes.value[idx]) idx = i
  return dates.value[idx]
})

const option = computed(() => {
  if (dates.value.length === 0) return {}
  return {
    animation: true,
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    tooltip: {
      trigger: 'axis',
      formatter: (ps: any[]) => {
        const first = ps[0]
        const parts = [`<b>${first.name}</b>`]
        for (const p of ps) {
          if (p.value === '-' || p.value === undefined) continue
          parts.push(`${p.marker}${p.seriesName}: ${typeof p.value === 'number' ? p.value : p.value}`)
        }
        return parts.join('<br/>')
      },
    },
    legend: { top: 0, textStyle: { fontSize: 12 }, data: ['收盘价', `RSI(${period})`] },
    grid: [
      { left: 56, right: 24, top: 40, height: '48%' },
      { left: 56, right: 24, top: '68%', height: '22%' },
    ],
    xAxis: [
      { type: 'category', data: dates.value, gridIndex: 0, axisLabel: { show: false }, axisPointer: { label: { show: false } } },
      { type: 'category', data: dates.value, gridIndex: 1, axisLabel: { fontSize: 10, hideOverlap: true } },
    ],
    yAxis: [
      { type: 'value', gridIndex: 0, scale: true, axisLabel: { fontSize: 11 } },
      { type: 'value', gridIndex: 1, min: 0, max: 100, axisLabel: { fontSize: 10 } },
    ],
    dataZoom: [{ type: 'inside', xAxisIndex: [0, 1], start: 0, end: 100 }],
    series: [
      {
        name: '收盘价',
        type: 'line',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: closes.value.map((v, i) => [dates.value[i], v]),
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 1.5, color: C.value.primary },
        itemStyle: { color: C.value.primary },
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: { color: C.value.slateStrong, type: 'dotted', width: 1 },
          label: { show: false },
          data: lowDate.value ? [{ xAxis: lowDate.value }] : [],
        },
      },
      {
        name: `RSI(${period})`,
        type: 'line',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: rsiVals.value.map((v, i) => [dates.value[i], v]),
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 1.8, color: C.value.violet },
        itemStyle: { color: C.value.violet },
        markLine: {
          silent: true,
          symbol: 'none',
          label: { fontSize: 10, color: C.value.slate },
          data: [
            { yAxis: 70, lineStyle: { color: C.value.danger, type: 'dashed', width: 1 }, label: { formatter: '超买 70' } },
            { yAxis: 50, lineStyle: { color: C.value.slate, type: 'dotted', width: 1 } },
            { yAxis: 30, lineStyle: { color: C.value.success, type: 'dashed', width: 1 }, label: { formatter: '超卖 30' } },
          ],
        },
        markArea: {
          silent: true,
          data: [
            [{ yAxis: 100, itemStyle: { color: withAlpha(C.value.danger, 0.06) } }, { yAxis: 70 }],
            [{ yAxis: 30, itemStyle: { color: withAlpha(C.value.success, 0.08) } }, { yAxis: 0 }],
          ],
        },
      },
    ],
  }
})
</script>

<template>
  <div class="rsi-sim">
    <div v-if="loading" class="status">数据加载中…</div>
    <div v-else-if="error" class="status">数据不可用</div>
    <template v-else>
      <ThemedChart class="chart" :option="option" autoresize />

      <div class="controls">
        <div class="control-row">
          <span class="control-label">RSI 周期</span>
          <input v-model.number="period" type="range" min="2" max="40" step="1" class="slider" />
          <span class="control-value">{{ period }}</span>
        </div>
        <p class="hint">
          周期越短越敏感（更易触发超买超卖），越长越平滑。绿色阴影 = 超卖区（&lt;30），红色 = 超买区（&gt;70）。虚线标记区间最低收盘价。
        </p>
      </div>
    </template>
  </div>
</template>

<style scoped>
.rsi-sim { padding: 16px; }
.status { height: 400px; display: flex; align-items: center; justify-content: center; color: var(--text-3); font-size: 14px; }
.chart { height: 400px; }
.controls { margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--border); display: flex; flex-direction: column; gap: 10px; }
.control-row { display: flex; align-items: center; gap: 12px; }
.control-label { width: 72px; font-size: 13px; color: var(--text-2); flex-shrink: 0; }
.slider { flex: 1; accent-color: var(--primary); cursor: pointer; }
.control-value { width: 40px; font-size: 13px; font-weight: 600; color: var(--primary); text-align: right; flex-shrink: 0; }
.hint { margin-top: 10px; font-size: 12px; color: var(--text-3); line-height: 1.7; }
</style>
