<script setup lang="ts">
import { computed, ref } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent])

// 单利 vs 复利：拖动年化收益，看 30 年增长差距

const props = defineProps<{
  params?: Record<string, unknown>
}>()

const PV = 100
const r = ref(typeof props.params?.r === 'number' ? props.params.r : 0.10)
const YEARS = 30

const growth = computed(() => {
  const simple: [number, number][] = []
  const compound: [number, number][] = []
  for (let n = 0; n <= YEARS; n++) {
    simple.push([n, Number((PV * (1 + r.value * n)).toFixed(0))])
    compound.push([n, Number((PV * Math.pow(1 + r.value, n)).toFixed(0))])
  }
  return { simple, compound }
})

const endValues = computed(() => ({
  simple: Number((PV * (1 + r.value * YEARS)).toFixed(0)),
  compound: Number((PV * Math.pow(1 + r.value, YEARS)).toFixed(0)),
  ratio: Number((Math.pow(1 + r.value, YEARS) / (1 + r.value * YEARS)).toFixed(2)),
}))

const option = computed(() => ({
  animation: true,
  grid: { left: 50, right: 30, top: 40, bottom: 40 },
  tooltip: { trigger: 'axis', valueFormatter: (v: number) => `${v} 元` },
  legend: { top: 0, textStyle: { fontSize: 12 } },
  xAxis: {
    type: 'value', name: '年数 n', nameLocation: 'middle', nameGap: 28,
    min: 0, max: YEARS, axisLabel: { fontSize: 11 },
  },
  yAxis: {
    type: 'value', name: '金额（元）', nameLocation: 'middle', nameGap: 40,
    axisLabel: { fontSize: 11 },
  },
  series: [
    {
      name: '单利',
      type: 'line', smooth: true, symbol: 'none',
      data: growth.value.simple,
      lineStyle: { width: 2, color: '#d97706', type: 'dashed' },
    },
    {
      name: '复利',
      type: 'line', smooth: true, symbol: 'none',
      data: growth.value.compound,
      lineStyle: { width: 3, color: '#2563eb' },
      areaStyle: { color: 'rgba(37, 99, 235, 0.06)' },
    },
  ],
}))
</script>

<template>
  <div class="compound-growth">
    <VChart class="chart" :option="option" autoresize />

    <div class="controls">
      <div class="control-row">
        <span class="control-label">年化收益 r</span>
        <input v-model.number="r" type="range" min="0.02" max="0.25" step="0.01" class="slider" />
        <span class="control-value">{{ (r * 100).toFixed(0) }}%</span>
      </div>
      <div class="result-row">
        <div class="result-box">
          <span class="muted">30 年后单利</span>
          <strong class="result-simple">{{ endValues.simple }} 元</strong>
        </div>
        <div class="result-box">
          <span class="muted">30 年后复利</span>
          <strong class="result-compound">{{ endValues.compound }} 元</strong>
        </div>
        <div class="result-box ratio">
          <span class="muted">复利/单利倍数</span>
          <strong>{{ endValues.ratio }}×</strong>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.compound-growth { padding: 16px; }
.chart { height: 300px; }
.controls { margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border); }
.control-row { display: flex; align-items: center; gap: 12px; }
.control-label { width: 80px; font-size: 13px; color: var(--text-2); flex-shrink: 0; }
.slider { flex: 1; accent-color: var(--primary); cursor: pointer; }
.control-value { width: 48px; font-size: 13px; font-weight: 600; color: var(--primary); text-align: right; flex-shrink: 0; }
.result-row { display: flex; gap: 10px; margin-top: 14px; }
.result-box {
  flex: 1; padding: 10px 12px; border-radius: var(--radius-sm);
  background: var(--bg-hover); text-align: center;
  display: flex; flex-direction: column; gap: 2px;
}
.result-box strong { font-size: 18px; }
.result-simple { color: var(--warning); }
.result-compound { color: var(--primary); }
.result-box.ratio strong { color: var(--success); }
</style>
