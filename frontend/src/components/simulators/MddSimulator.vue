<script setup lang="ts">
import { computed, ref } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C, withAlpha } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, MarkLineComponent, MarkPointComponent, MarkAreaComponent, DataZoomComponent, TitleComponent } from 'echarts/components'
import { useStockDaily } from '@/composables/useStockDaily'
import { maxDrawdown, recoveryNeeded } from '@/utils/indicators'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent, MarkPointComponent, MarkAreaComponent, DataZoomComponent, TitleComponent])

// 最大回撤模拟器：真实茅台 2024 复权净值 + 回撤阴影 + 回本滑块

const props = defineProps<{
  params?: Record<string, unknown>
}>()

const code = computed(() => (typeof props.params?.code === 'string' ? props.params.code : 'sh600519'))
const { data, nav, loading, error } = useStockDaily(code)

const dd = computed(() => (nav.value ? maxDrawdown(nav.value) : null))

// 回本滑块：拖回撤深度看需涨多少回本
const rec = ref(0.27) // 默认 27%
const recPct = computed(() => Math.round(rec.value * 100))
const recNeeded = computed(() => recoveryNeeded(-rec.value))

function alignMdd() {
  if (dd.value) rec.value = -dd.value.mdd
}

const option = computed(() => {
  if (!nav.value || !dd.value || !data.value) return {}
  const dates = data.value.map((d) => d.date)
  const peakDate = dates[dd.value.peakIdx]
  const troughDate = dates[dd.value.troughIdx]
  const drawPct = dd.value.drawdown.map((v) => +(v * 100).toFixed(2))
  return {
    animation: true,
    grid: { left: 52, right: 52, top: 40, bottom: 44 },
    title: [
      {
        text: '复权净值与回撤（起点 100）',
        left: 52,
        top: 8,
        textStyle: { fontSize: 12, fontWeight: 600, color: C.value.text },
      },
    ],
    tooltip: {
      trigger: 'axis',
      formatter: (ps: any[]) => {
        const a = ps[0]
        const ddVal = ps[1] ? ps[1].data[1] : '—'
        return `${a.name}<br/>净值 ${a.data[1].toFixed(2)}　回撤 ${ddVal}%`
      },
    },
    legend: { top: 0, textStyle: { fontSize: 12 }, data: ['复权净值', '回撤'] },
    dataZoom: [
      {
        type: 'inside',
        xAxisIndex: [0],
        start: 0,
        end: 100,
        zoomOnMouseWheel: true,
        moveOnMouseMove: true,
      },
      {
        type: 'slider',
        xAxisIndex: [0],
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
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: { fontSize: 10, hideOverlap: true },
    },
    yAxis: [
      {
        type: 'value',
        name: '净值',
        nameLocation: 'middle',
        nameGap: 30,
        scale: true,
        axisLabel: { fontSize: 11 },
      },
      {
        type: 'value',
        name: '回撤',
        nameLocation: 'middle',
        nameGap: 40,
        max: 0,
        axisLabel: { fontSize: 11, formatter: '{value}%' },
      },
    ],
    series: [
      {
        name: '复权净值',
        type: 'line',
        data: nav.value.map((v, i) => [dates[i], +v.toFixed(2)]),
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 2, color: C.value.primary },
        itemStyle: { color: C.value.primary },
        markArea: {
          silent: true,
          itemStyle: { color: withAlpha(C.value.danger, 0.12) },
          label: { show: true, position: 'insideTop', fontSize: 11, color: C.value.danger, formatter: `最大回撤区间` },
          data: [[{ xAxis: peakDate }, { xAxis: troughDate }]],
        },
        markPoint: {
          symbolSize: 44,
          label: { fontSize: 10 },
          data: [
            { coord: [peakDate, nav.value[dd.value.peakIdx]], value: '峰值', itemStyle: { color: C.value.warning } },
            { coord: [troughDate, nav.value[dd.value.troughIdx]], value: '谷底', itemStyle: { color: C.value.danger } },
          ],
        },
      },
      {
        name: '回撤',
        type: 'line',
        yAxisIndex: 1,
        data: nav.value.map((_, i) => [dates[i], drawPct[i]]),
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 1, color: C.value.danger, opacity: 0.7 },
        areaStyle: { color: withAlpha(C.value.danger, 0.18) },
        itemStyle: { color: C.value.danger },
      },
    ],
  }
})
</script>

<template>
  <div class="mdd-sim">
    <div v-if="loading" class="status">数据加载中…</div>
    <div v-else-if="error" class="status">数据不可用</div>
    <template v-else-if="nav && dd">
      <div class="result">
        <div class="result-item">
          <span class="result-label">最大回撤</span>
          <strong class="result-value red">{{ (dd.mdd * 100).toFixed(2) }}%</strong>
        </div>
        <div class="result-item">
          <span class="result-label">峰值</span>
          <strong class="result-value sm">{{ data![dd.peakIdx].date }}</strong>
        </div>
        <div class="result-item">
          <span class="result-label">谷底</span>
          <strong class="result-value sm">{{ data![dd.troughIdx].date }}</strong>
        </div>
      </div>

      <ThemedChart class="chart" :option="option" autoresize />

      <div class="controls">
        <div class="control-row">
          <span class="control-label">回撤深度</span>
          <input v-model.number="rec" type="range" min="0.05" max="0.90" step="0.01" class="slider" />
          <span class="control-value">−{{ recPct }}%</span>
          <button class="align-btn" @click="alignMdd">对齐主线回撤</button>
        </div>
        <div class="rec-box">
          回撤 −{{ recPct }}% 需要上涨
          <strong class="rec-need">{{ (recNeeded * 100).toFixed(1) }}%</strong> 才回本
          <span class="rec-formula">1/(1−{{ recPct / 100 }}) − 1</span>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.mdd-sim { padding: 16px; }
.status { height: 320px; display: flex; align-items: center; justify-content: center; color: var(--text-3); font-size: 14px; }
.chart { height: 320px; }
.result { display: flex; gap: 24px; margin-bottom: 12px; padding: 12px 16px; background: var(--primary-soft); border-radius: var(--radius-sm); flex-wrap: wrap; }
.result-item { display: flex; flex-direction: column; gap: 2px; }
.result-label { font-size: 12px; color: var(--text-3); }
.result-value { font-size: 20px; font-weight: 700; }
.result-value.red { color: var(--danger, #dc2626); }
.result-value.sm { font-size: 15px; color: var(--text-2); font-family: var(--font-mono); }
.controls { margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--border); display: flex; flex-direction: column; gap: 10px; }
.control-row { display: flex; align-items: center; gap: 12px; }
.control-label { width: 72px; font-size: 13px; color: var(--text-2); flex-shrink: 0; }
.slider { flex: 1; accent-color: var(--primary); cursor: pointer; }
.control-value { width: 64px; font-size: 13px; font-weight: 600; color: var(--primary); text-align: right; flex-shrink: 0; }
.align-btn { font-size: 12px; padding: 4px 10px; border-radius: var(--radius-sm); background: var(--primary); color: #fff; border: none; cursor: pointer; flex-shrink: 0; }
.rec-box { margin-top: 6px; padding: 10px 14px; background: var(--bg-hover); border-radius: var(--radius-sm); font-size: 14px; display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; }
.rec-need { color: var(--danger, #dc2626); font-size: 18px; }
.rec-formula { font-size: 12px; color: var(--text-3); font-family: var(--font-mono); }
</style>
