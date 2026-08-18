<script setup lang="ts">
import { computed, ref } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C, withAlpha } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, MarkLineComponent, TitleComponent } from 'echarts/components'
import { useStockDaily } from '@/composables/useStockDaily'
import { macd } from '@/utils/indicators'

use([CanvasRenderer, LineChart, BarChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, MarkLineComponent, TitleComponent])

// MACD 模拟器：真实行情 + 快/慢/信号线参数可调
// DIF = EMA(fast) − EMA(slow)，DEA = DIF 的 signal 日 EMA，柱 = (DIF−DEA)×2

const props = defineProps<{
  params?: Record<string, unknown>
}>()

const code = computed(() => (typeof props.params?.code === 'string' ? props.params.code : 'sh600519'))
const { data, loading, error } = useStockDaily(code)

const fast = ref(12)
const slow = ref(26)
const signal = ref(9)

// 钳制：快线必须小于慢线，避免退化/NaN
const effFast = computed(() => Math.min(fast.value, slow.value - 1))

const ind = computed(() => {
  if (!data.value || data.value.length === 0) return null
  const closes = data.value.map((d) => d.close)
  return macd(closes, effFast.value, slow.value, signal.value)
})

const dates = computed(() => data.value?.map((d) => d.date) ?? [])
const closes = computed(() => data.value?.map((d) => d.close) ?? [])

// 区间内最低收盘价日期（虚线标记），避免硬编码 2024-09-19 在换 code/区间时失效
const lowDate = computed(() => {
  if (!dates.value.length || !closes.value.length) return ''
  let idx = 0
  for (let i = 1; i < closes.value.length; i++) if (closes.value[i] < closes.value[idx]) idx = i
  return dates.value[idx]
})

// 修整 null 为 '—'（ECharts 不显示该点）
function pad(v: (number | null)[]): (number | string)[] {
  return v.map((x) => (x === null ? '-' : +x.toFixed(3)))
}

const option = computed(() => {
  if (!ind.value) return {}
  return {
    animation: true,
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    tooltip: {
      trigger: 'axis',
      formatter: (ps: any[]) => {
        const first = ps[0]
        const parts = [`<b>${first.name}</b>`]
        const num = (p: any) => (Array.isArray(p.value) ? p.value[1] : p.value)
        const main = ps.filter((p: any) => p.seriesName !== 'MACD' && num(p) !== '-' && num(p) !== undefined)
        const hist = ps.find((p: any) => p.seriesName === 'MACD')
        const hV = hist ? num(hist) : undefined
        if (main.length) {
          parts.push('价格与 MACD 线：')
          for (const p of main) parts.push(`　${p.marker}${p.seriesName}: ${num(p)}`)
        }
        if (hist && hV !== '-' && hV !== undefined) parts.push(`MACD 柱：　${hist.marker}${hV}`)
        return parts.join('<br/>')
      },
    },
    legend: { top: 0, textStyle: { fontSize: 12 }, data: ['收盘价', 'DIF', 'DEA', 'MACD'] },
    grid: [
      { left: 56, right: 24, top: 48, height: '48%' },
      { left: 56, right: 24, top: '68%', height: '22%' },
    ],
    title: [
      { text: '① 价格 + MACD 线（元）', left: 56, top: 8, textStyle: { fontSize: 12, fontWeight: 600, color: C.value.text } },
      { text: '② MACD 柱（DIF − DEA）', left: 56, top: '64%', textStyle: { fontSize: 12, fontWeight: 600, color: C.value.text } },
    ],
    xAxis: [
      { type: 'category', data: dates.value, gridIndex: 0, axisLabel: { show: false }, axisPointer: { label: { show: false } } },
      { type: 'category', data: dates.value, gridIndex: 1, axisLabel: { fontSize: 10, hideOverlap: true } },
    ],
    yAxis: [
      { type: 'value', gridIndex: 0, scale: true, axisLabel: { fontSize: 11 } },
      { type: 'value', gridIndex: 1, axisLabel: { fontSize: 10 } },
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1], start: 0, end: 100 },
      {
        type: 'slider',
        xAxisIndex: [0, 1],
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
        name: 'DIF',
        type: 'line',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: pad(ind.value.dif).map((v, i) => [dates.value[i], v]),
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 1.5, color: C.value.warning },
        itemStyle: { color: C.value.warning },
      },
      {
        name: 'DEA',
        type: 'line',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: pad(ind.value.dea).map((v, i) => [dates.value[i], v]),
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 1.5, color: C.value.cyan },
        itemStyle: { color: C.value.cyan },
      },
      {
        name: 'MACD',
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: ind.value.hist.map((v) => ({
          value: v === null ? null : +v.toFixed(3),
          itemStyle: { color: v !== null && v >= 0 ? C.value.danger : C.value.success },
        })),
        barWidth: '60%',
      },
    ],
  }
})
</script>

<template>
  <div class="macd-sim">
    <div v-if="loading" class="status">数据加载中…</div>
    <div v-else-if="error" class="status">数据不可用</div>
    <template v-else>
      <ThemedChart class="chart" :option="option" autoresize />

      <div class="controls">
        <div class="control-row">
          <span class="control-label">快线 EMA</span>
          <input v-model.number="fast" type="range" min="5" max="40" step="1" class="slider" />
          <span class="control-value">{{ effFast }}</span>
        </div>
        <div class="control-row">
          <span class="control-label">慢线 EMA</span>
          <input v-model.number="slow" type="range" min="6" max="60" step="1" class="slider" />
          <span class="control-value">{{ slow }}</span>
        </div>
        <div class="control-row">
          <span class="control-label">信号 DEA</span>
          <input v-model.number="signal" type="range" min="2" max="20" step="1" class="slider" />
          <span class="control-value">{{ signal }}</span>
        </div>
        <p class="hint">
          周期短 → 灵敏但假信号多；周期长 → 迟钝但抓大趋势。虚线标记区间最低收盘价。
          <span class="warn" v-if="fast >= slow">快线已自动钳制为慢线 − 1，快线必须小于慢线。</span>
        </p>
      </div>
    </template>
  </div>
</template>

<style scoped>
.macd-sim { padding: 16px; }
.status { height: 400px; display: flex; align-items: center; justify-content: center; color: var(--text-3); font-size: 14px; }
.chart { height: 400px; }
.controls { margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--border); display: flex; flex-direction: column; gap: 10px; }
.control-row { display: flex; align-items: center; gap: 12px; }
.control-label { width: 72px; font-size: 13px; color: var(--text-2); flex-shrink: 0; }
.slider { flex: 1; accent-color: var(--primary); cursor: pointer; }
.control-value { width: 40px; font-size: 13px; font-weight: 600; color: var(--primary); text-align: right; flex-shrink: 0; }
.hint { margin-top: 10px; font-size: 12px; color: var(--text-3); line-height: 1.7; }
.warn { color: var(--warning, #d97706); }
</style>
