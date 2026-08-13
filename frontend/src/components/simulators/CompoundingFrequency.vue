<script setup lang="ts">
import { computed, ref } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C, withAlpha } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent])

// 复利频率：相同名义利率，按年/按月/按日/连续复利的终值增长对比
// FV = PV × (1 + r/m)^(m·n)，连续复利 FV = PV × e^(r·n)
// 教学示意模型（纯数学演示）

const props = defineProps<{
  params?: Record<string, unknown>
}>()

const PV = 100
const YEARS = 20
const r = ref(typeof props.params?.r === 'number' ? props.params.r : 0.06) // 名义年利率

// 各频率的复利终值曲线：n → FV
function curve(pv: number, nominal: number, perYear: number, n: number) {
  // perYear=0 表示连续复利
  return perYear > 0 ? pv * Math.pow(1 + nominal / perYear, perYear * n) : pv * Math.exp(nominal * n)
}

const seriesData = computed(() => {
  const freqs = [
    { key: 'yearly', label: '按年复利', perYear: 1 },
    { key: 'monthly', label: '按月复利', perYear: 12 },
    { key: 'daily', label: '按日复利', perYear: 365 },
    { key: 'continuous', label: '连续复利', perYear: 0 },
  ]
  const series = freqs.map((f) => {
    const points: [number, number][] = []
    for (let n = 0; n <= YEARS; n++) points.push([n, Number(curve(PV, r.value, f.perYear, n).toFixed(2))])
    return { key: f.key, label: f.label, perYear: f.perYear, data: points }
  })
  return series
})

// 有效年利率与终值汇总
const summary = computed(() => {
  const m = [1, 12, 365, 0] // 0 = 连续
  const names = ['按年复利', '按月复利', '按日复利', '连续复利']
  return m.map((perYear, i) => {
    const ear = perYear > 0 ? Math.pow(1 + r.value / perYear, perYear) - 1 : Math.exp(r.value) - 1
    return {
      name: names[i],
      ear,
      fv: Number(curve(PV, r.value, perYear, YEARS).toFixed(2)),
    }
  })
})

const option = computed(() => ({
  animation: true,
  grid: { left: 50, right: 24, top: 36, bottom: 40 },
  tooltip: { trigger: 'axis', valueFormatter: (v: number) => `${v} 元` },
  legend: { top: 0, textStyle: { fontSize: 12 } },
  xAxis: {
    type: 'value', name: '年数 n', nameLocation: 'middle', nameGap: 28,
    min: 0, max: YEARS, axisLabel: { fontSize: 11 },
  },
  yAxis: {
    type: 'value', name: '终值 FV（元）', nameLocation: 'middle', nameGap: 42,
    axisLabel: { fontSize: 11 },
  },
  series: [
    {
      name: '按年复利',
      type: 'line', smooth: true, symbol: 'none',
      data: seriesData.value.find((s) => s.key === 'yearly')!.data,
      lineStyle: { width: 2, color: C.value.slateStrong, type: 'dashed' },
    },
    {
      name: '按月复利',
      type: 'line', smooth: true, symbol: 'none',
      data: seriesData.value.find((s) => s.key === 'monthly')!.data,
      lineStyle: { width: 2, color: C.value.warning },
    },
    {
      name: '按日复利',
      type: 'line', smooth: true, symbol: 'none',
      data: seriesData.value.find((s) => s.key === 'daily')!.data,
      lineStyle: { width: 2, color: C.value.cyan },
    },
    {
      name: '连续复利',
      type: 'line', smooth: true, symbol: 'none',
      data: seriesData.value.find((s) => s.key === 'continuous')!.data,
      lineStyle: { width: 3, color: C.value.primary },
      areaStyle: { color: withAlpha(C.value.primary, 0.05) },
    },
  ],
}))
</script>

<template>
  <div class="compounding-frequency">
    <ThemedChart class="chart" :option="option" autoresize />

    <div class="controls">
      <div class="control-row">
        <span class="control-label">名义利率 r</span>
        <input v-model.number="r" type="range" min="0.01" max="0.20" step="0.005" class="slider" />
        <span class="control-value">{{ (r * 100).toFixed(1) }}%</span>
      </div>
      <div class="result-row">
        <div v-for="s in summary" :key="s.name" class="result-box">
          <span class="muted">{{ s.name }}</span>
          <strong class="result-ear">EAR {{ (s.ear * 100).toFixed(2) }}%</strong>
          <span class="result-fv">{{ s.fv }} 元</span>
        </div>
      </div>
      <div class="tip">
        名义利率相同时，计息频率越高实际收益越高，但差距是收敛的——连续复利是上限。例如名义 6%，按年复利 EAR 恰为 6%，按月复利约 6.17%，连续复利约 6.18%。多出的部分来自「利息的利息」更早产生。
      </div>
    </div>
  </div>
</template>

<style scoped>
.compounding-frequency { padding: 16px; }
.chart { height: 300px; }
.controls { margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border); }
.control-row { display: flex; align-items: center; gap: 12px; }
.control-label { width: 88px; font-size: 13px; color: var(--text-2); flex-shrink: 0; }
.slider { flex: 1; accent-color: var(--primary); cursor: pointer; }
.control-value { width: 56px; font-size: 13px; font-weight: 600; color: var(--primary); text-align: right; flex-shrink: 0; }
.result-row { display: flex; gap: 8px; margin-top: 12px; flex-wrap: wrap; }
.result-box {
  flex: 1; min-width: 130px; padding: 8px 10px; border-radius: var(--radius-sm);
  background: var(--bg-hover); text-align: center;
  display: flex; flex-direction: column; gap: 2px;
}
.muted { font-size: 12px; color: var(--text-3); }
.result-ear { font-size: 14px; color: var(--primary); }
.result-fv { font-size: 12px; color: var(--text-2); }
.tip { margin-top: 10px; font-size: 12.5px; color: var(--text-3); line-height: 1.7; }
</style>
