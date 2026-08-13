<script setup lang="ts">
import { computed, ref } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C, withAlpha } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, MarkLineComponent, MarkPointComponent } from 'echarts/components'
import { useStockDaily } from '@/composables/useStockDaily'
import { sma, shiftPosition } from '@/utils/strategies'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent, MarkPointComponent])

// 策略解剖：真实行情 + 双均线信号 → 持仓映射（p2-l1）

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

const dates = computed(() => data.value?.map((d) => d.date) ?? [])
const closes = computed(() => data.value?.map((d) => d.close) ?? [])

const com = computed(() => {
  if (!data.value) return null
  const cl = closes.value
  const f = sma(cl, effFast.value)
  const s = sma(cl, slow.value)
  // 信号：金叉/死叉次日生效的持仓
  const rawSig = cl.map((_, i) => {
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
  return { f, s, pos, buyIdx, sellIdx }
})

const option = computed(() => {
  if (!com.value) return {}
  const f = com.value.f.map((v, i) => [dates.value[i], v === null ? '-' : +v.toFixed(1)])
  const s = com.value.s.map((v, i) => [dates.value[i], v === null ? '-' : +v.toFixed(1)])
  return {
    animation: true,
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    tooltip: {
      trigger: 'axis',
      formatter: (ps: any[]) => {
        const hp = ps.find((p: any) => p.seriesName === '收盘价')
        const hh = ps.find((p: any) => p.seriesName === '持仓')
        const head = hp ? `${hp.name}<br/>收盘 ${hp.value[1]}` : hp
        const parts = [head]
        if (hh) parts.push(`持仓 ${hh.value[1] === 1 ? '全仓' : '空仓'}`)
        return parts.join('<br/>')
      },
    },
    legend: { top: 0, textStyle: { fontSize: 12 }, data: ['收盘价', `MA${effFast.value}`, `MA${slow.value}`, '持仓'] },
    grid: [
      { left: 56, right: 24, top: 40, height: '62%' },
      { left: 56, right: 24, top: '76%', height: '14%' },
    ],
    xAxis: [
      {
        type: 'category',
        data: dates.value,
        gridIndex: 0,
        axisLabel: { show: false },
        axisPointer: { label: { show: false } },
      },
      {
        type: 'category',
        data: dates.value,
        gridIndex: 1,
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
    ],
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
        markPoint: {
          symbolSize: 46,
          label: { fontSize: 11, color: '#fff' },
          data: com.value.buyIdx.map((i) => ({ coord: [dates.value[i], closes.value[i]], value: '买', itemStyle: { color: C.value.success } })),
        },
      },
      {
        name: `MA${effFast.value}`,
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
        name: `MA${slow.value}`,
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
        data: com.value.pos.map((v, i) => [dates.value[i], v]),
        symbol: 'none',
        step: 'end',
        lineStyle: { width: 2, color: C.value.cyan },
        itemStyle: { color: C.value.cyan },
        areaStyle: { color: withAlpha(C.value.cyan, 0.15) },
      },
    ],
  }
})

const buyCount = computed(() => com.value?.buyIdx.length ?? 0)
const sellCount = computed(() => com.value?.sellIdx.length ?? 0)
const posPct = computed(() => {
  if (!com.value) return 0
  return Math.round((com.value.pos.reduce((a, b) => a + b, 0) / com.value.pos.length) * 100)
})
</script>

<template>
  <div class="ss">
    <div v-if="loading" class="status">数据加载中…</div>
    <div v-else-if="error" class="status">数据不可用</div>
    <template v-else-if="com">
      <div class="result">
        <div class="result-item">
          <span class="result-label">买点（金叉次日起）</span>
          <strong class="result-value" style="color: var(--success, #16a34a)">{{ buyCount }}</strong>
        </div>
        <div class="result-item">
          <span class="result-label">卖点（死叉次日起）</span>
          <strong class="result-value" style="color: var(--danger, #dc2626)">{{ sellCount }}</strong>
        </div>
        <div class="result-item">
          <span class="result-label">持仓占比</span>
          <strong class="result-value">{{ posPct }}%</strong>
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
          信号（金叉/死叉）→ 持仓（次日生效）→ 成交（次日开盘）：三段式缺一不可。拖动参数看信号与持仓如何联动变化。
        </p>
      </div>
    </template>
  </div>
</template>

<style scoped>
.ss { padding: 16px; }
.status { height: 460px; display: flex; align-items: center; justify-content: center; color: var(--text-3); font-size: 14px; }
.chart { height: 460px; }
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