<script setup lang="ts">
import { computed } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C, withAlpha } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, MarkLineComponent, MarkAreaComponent, MarkPointComponent, DataZoomComponent } from 'echarts/components'
import { useStockDaily } from '@/composables/useStockDaily'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, MarkLineComponent, MarkAreaComponent, MarkPointComponent, DataZoomComponent])

// PE 历史分位带（真实 quantlab 日线 pe_ttm）：看当前估值处于历史什么位置
const props = defineProps<{
  params?: Record<string, unknown>
}>()

const code = computed(() => (typeof props.params?.code === 'string' ? props.params.code : 'sh600519'))
const { data, loading, error } = useStockDaily(code, '2020-01-01', '2026-08-10')

// 有效 PE 序列（剔除 <=0 的异常值）
const peSeries = computed(() => {
  const out: [string, number][] = []
  for (const d of data.value ?? []) {
    if (typeof d.pe_ttm === 'number' && d.pe_ttm > 0) out.push([d.date, +d.pe_ttm.toFixed(1)])
  }
  return out
})

const stats = computed(() => {
  const s = peSeries.value
  if (s.length < 30) return null
  const vals = s.map(([, v]) => v)
  const mean = vals.reduce((a, b) => a + b, 0) / vals.length
  const sd = Math.sqrt(vals.reduce((a, v) => a + (v - mean) ** 2, 0) / vals.length)
  const cur = vals[vals.length - 1]
  const pct = (vals.filter((v) => v <= cur).length / vals.length) * 100
  return { mean, sd, cur, pct, min: Math.min(...vals), max: Math.max(...vals) }
})

const option = computed(() => {
  const s = peSeries.value
  const st = stats.value
  if (!s.length || !st) return {}
  const dates = s.map(([d]) => d)
  const vals = s.map(([, v]) => v)
  const curDate = dates[dates.length - 1]
  return {
    animation: true,
    tooltip: {
      trigger: 'axis',
      formatter: (ps: any[]) => {
        const p = ps[0]
        if (!p) return ''
        return `${p.name}<br/>　PE(TTM) ${p.value}`
      },
    },
    grid: { left: 52, right: 20, top: 34, bottom: 44 },
    dataZoom: [
      { type: 'inside', xAxisIndex: [0], start: 0, end: 100, zoomOnMouseWheel: true },
      { type: 'slider', xAxisIndex: [0], start: 0, end: 100, bottom: 2, height: 16 },
    ],
    xAxis: { type: 'category', data: dates, axisLabel: { fontSize: 10, hideOverlap: true } },
    yAxis: { type: 'value', name: 'PE(TTM)', nameTextStyle: { fontSize: 10 }, axisLabel: { fontSize: 10 }, splitLine: { lineStyle: { color: C.value.grid } } },
    series: [
      {
        name: 'PE(TTM)',
        type: 'line',
        data: vals,
        symbol: 'none',
        lineStyle: { width: 1.5, color: C.value.primary },
        areaStyle: { color: withAlpha(C.value.primary, 0.08) },
        markLine: {
          silent: true,
          symbol: 'none',
          data: [
            { yAxis: st.mean, name: '均值', lineStyle: { color: C.value.slateStrong, type: 'dashed' }, label: { formatter: `均值 ${st.mean.toFixed(1)}`, fontSize: 10, color: C.value.slateStrong } },
            { yAxis: st.cur, name: '当前', lineStyle: { color: C.value.danger, type: 'solid' }, label: { formatter: `当前 ${st.cur}`, fontSize: 10, color: C.value.danger } },
          ],
        },
        markArea: {
          silent: true,
          itemStyle: { color: withAlpha(C.value.slate, 0.12) },
          data: [[{ yAxis: st.mean - st.sd }, { yAxis: st.mean + st.sd }]],
        },
        markPoint: {
          symbol: 'pin',
          symbolSize: 38,
          label: { fontSize: 9, color: '#fff', formatter: `分位 ${st.pct.toFixed(0)}%` },
          itemStyle: { color: C.value.danger },
          data: [{ coord: [curDate, st.cur], value: '' }],
        },
      },
    ],
  }
})
</script>

<template>
  <div class="pb">
    <div v-if="loading" class="status">数据加载中…</div>
    <div v-else-if="error" class="status">数据不可用</div>
    <template v-else-if="stats">
      <div class="cards">
        <div class="card"><span>当前 PE</span><strong>{{ stats.cur }}</strong></div>
        <div class="card"><span>历史均值</span><strong>{{ stats.mean.toFixed(1) }}</strong></div>
        <div class="card"><span>历史区间</span><strong>{{ stats.min }} ~ {{ stats.max }}</strong></div>
        <div class="card"><span>当前分位</span><strong>{{ stats.pct.toFixed(0) }}%</strong></div>
      </div>
      <ThemedChart class="chart" :option="option" autoresize />
      <p class="hint">
        灰虚线是历史均值，浅色带是均值±1 倍标准差区间，红色水平线是当前 PE。「分位」= 历史上有多少比例的日子 PE 低于当前值：分位低说明当前估值处于历史偏低位，分位高说明偏高位。注意 PE 分位是「市场给这家公司的定价位置」，不等于「便宜」——便宜与否还要结合基本面（p2-l2 质量）与增长预期（p2-l5 PEG）。
      </p>
    </template>
  </div>
</template>

<style scoped>
.pb { padding: 16px; }
.status { height: 380px; display: flex; align-items: center; justify-content: center; color: var(--text-3); font-size: 14px; }
.chart { height: 340px; }
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(100px, 1fr)); gap: 10px; margin-bottom: 12px; }
.card { display: flex; flex-direction: column; gap: 2px; padding: 9px 12px; background: var(--primary-soft); border-radius: var(--radius-sm); font-size: 11.5px; color: var(--text-3); }
.card strong { font-size: 16px; font-weight: 700; color: var(--text-1); }
.hint { margin-top: 12px; font-size: 12px; color: var(--text-3); line-height: 1.7; }
</style>
