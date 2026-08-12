<script setup lang="ts">
import { computed, ref } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, MarkLineComponent, MarkPointComponent, MarkAreaComponent } from 'echarts/components'
import { useStockDaily } from '@/composables/useStockDaily'
import { maxDrawdown, recoveryNeeded } from '@/utils/indicators'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent, MarkPointComponent, MarkAreaComponent])

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
    tooltip: {
      trigger: 'axis',
      formatter: (ps: any[]) => {
        const a = ps[0]
        const ddVal = ps[1] ? ps[1].data[1] : '—'
        return `${a.name}<br/>净值 ${a.data[1].toFixed(2)}　回撤 ${ddVal}%`
      },
    },
    legend: { top: 0, textStyle: { fontSize: 12 }, data: ['复权净值', '回撤'] },
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
        lineStyle: { width: 2, color: '#2563eb' },
        itemStyle: { color: '#2563eb' },
        markArea: {
          silent: true,
          itemStyle: { color: 'rgba(220, 38, 38, 0.12)' },
          label: { show: true, position: 'insideTop', fontSize: 11, color: '#dc2626', formatter: `最大回撤区间` },
          data: [[{ xAxis: peakDate }, { xAxis: troughDate }]],
        },
        markPoint: {
          symbolSize: 44,
          label: { fontSize: 10 },
          data: [
            { coord: [peakDate, nav.value[dd.value.peakIdx]], value: '峰值', itemStyle: { color: '#d97706' } },
            { coord: [troughDate, nav.value[dd.value.troughIdx]], value: '谷底', itemStyle: { color: '#dc2626' } },
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
        lineStyle: { width: 1, color: '#dc2626', opacity: 0.7 },
        areaStyle: { color: 'rgba(220, 38, 38, 0.18)' },
        itemStyle: { color: '#dc2626' },
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

      <VChart class="chart" :option="option" autoresize />

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
.result-value.red { color: #dc2626; }
.result-value.sm { font-size: 15px; color: var(--text-2); font-family: var(--font-mono); }
.controls { margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--border); display: flex; flex-direction: column; gap: 10px; }
.control-row { display: flex; align-items: center; gap: 12px; }
.control-label { width: 72px; font-size: 13px; color: var(--text-2); flex-shrink: 0; }
.slider { flex: 1; accent-color: var(--primary); cursor: pointer; }
.control-value { width: 64px; font-size: 13px; font-weight: 600; color: var(--primary); text-align: right; flex-shrink: 0; }
.align-btn { font-size: 12px; padding: 4px 10px; border-radius: var(--radius-sm); background: var(--primary); color: #fff; border: none; cursor: pointer; flex-shrink: 0; }
.rec-box { margin-top: 6px; padding: 10px 14px; background: var(--bg-hover); border-radius: var(--radius-sm); font-size: 14px; display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; }
.rec-need { color: #dc2626; font-size: 18px; }
.rec-formula { font-size: 12px; color: var(--text-3); font-family: var(--font-mono); }
</style>
