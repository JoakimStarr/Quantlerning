<script setup lang="ts">
import { computed, ref } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C, withAlpha } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, MarkLineComponent, MarkPointComponent } from 'echarts/components'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent, MarkPointComponent])

// 折现曲线滑块：PV = FV / (1+r)ⁿ
// 拖动利率 r 看曲线变化；拖动期数 n 标注当前现值

const props = defineProps<{
  params?: Record<string, unknown>
}>()

const FV = 100 // 终值固定 100 元

const rDefault = typeof props.params?.r === 'number' ? props.params.r : 0.05
const rMin = 0.01
const rMax = 0.20

const r = ref(rDefault)
const n = ref(10)

// 三条固定对比利率
const compareRates = [0.03, 0.08, 0.15]

// 折现曲线：n → PV
function curve(rr: number, maxN = 30) {
  const points: [number, number][] = []
  for (let i = 0; i <= maxN; i++) {
    points.push([i, Number((FV / Math.pow(1 + rr, i)).toFixed(2))])
  }
  return points
}

const mainCurve = computed(() => curve(r.value))

const compareSeries = computed(() =>
  compareRates
    .filter((rr) => Math.abs(rr - r.value) > 0.005)
    .map((rr) => ({
      name: `r = ${(rr * 100).toFixed(0)}%`,
      type: 'line' as const,
      smooth: true,
      symbol: 'none',
      data: curve(rr),
      lineStyle: { width: 1, type: 'dashed' as const, opacity: 0.6 },
      itemStyle: { opacity: 0.6 },
    })),
)

const currentPV = computed(() => Number((FV / Math.pow(1 + r.value, n.value)).toFixed(2)))

const option = computed(() => ({
  animation: true,
  grid: { left: 50, right: 20, top: 36, bottom: 40 },
  tooltip: {
    trigger: 'axis',
    valueFormatter: (v: number) => `${v} 元`,
  },
  legend: {
    top: 0,
    textStyle: { fontSize: 12 },
    data: [`r = ${(r.value * 100).toFixed(0)}%`, ...compareSeries.value.map((s) => s.name)],
  },
  xAxis: {
    type: 'value',
    name: '期数 n（年）',
    nameLocation: 'middle',
    nameGap: 28,
    min: 0,
    max: 30,
    axisLabel: { fontSize: 11 },
  },
  yAxis: {
    type: 'value',
    name: '现值 PV（元）',
    nameLocation: 'middle',
    nameGap: 38,
    min: 0,
    max: 100,
    axisLabel: { fontSize: 11, formatter: '{value}' },
  },
  series: [
    {
      name: `r = ${(r.value * 100).toFixed(0)}%`,
      type: 'line',
      smooth: true,
      symbol: 'none',
      data: mainCurve.value,
      lineStyle: { width: 3, color: C.value.primary },
      itemStyle: { color: C.value.primary },
      areaStyle: { color: withAlpha(C.value.primary, 0.08) },
      // 标记当前期数的现值点（value 必须显式给定，否则 ECharts 在 formatter 里拿到 undefined 会抛错）
      markPoint: {
        symbolSize: 46,
        label: { fontSize: 11, formatter: (p: any) => Number(p.value).toFixed(1) },
        data: [{ coord: [n.value, currentPV.value], value: currentPV.value }],
      },
      markLine: {
        silent: true,
        symbol: 'none',
        label: { fontSize: 11, formatter: `n=${n.value}` },
        data: [{ xAxis: n.value }],
      },
    },
    ...compareSeries.value,
  ],
}))
</script>

<template>
  <div class="discount-curve">
    <!-- 图表 -->
    <ThemedChart class="chart" :option="option" autoresize />

    <!-- 控制面板 -->
    <div class="controls">
      <div class="control-row">
        <span class="control-label">利率 r</span>
        <input v-model.number="r" type="range" :min="rMin" :max="rMax" step="0.01" class="slider" />
        <span class="control-value">{{ (r * 100).toFixed(0) }}%</span>
      </div>
      <div class="control-row">
        <span class="control-label">期数 n</span>
        <input v-model.number="n" type="range" min="0" max="30" step="1" class="slider" />
        <span class="control-value">{{ n }} 年</span>
      </div>
      <div class="pv-box">
        现值 <strong>PV = {{ currentPV }} 元</strong>
        <span class="pv-formula">FV={{ FV }} ÷ (1+{{ (r * 100).toFixed(0) }}%)<sup>{{ n }}</sup></span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.discount-curve { padding: 16px; }
.chart { height: 320px; }
.controls {
  margin-top: 14px; padding-top: 14px;
  border-top: 1px solid var(--border);
  display: flex; flex-direction: column; gap: 10px;
}
.control-row { display: flex; align-items: center; gap: 12px; }
.control-label { width: 64px; font-size: 13px; color: var(--text-2); flex-shrink: 0; }
.slider { flex: 1; accent-color: var(--primary); cursor: pointer; }
.control-value { width: 48px; font-size: 13px; font-weight: 600; color: var(--primary); text-align: right; flex-shrink: 0; }
.pv-box {
  margin-top: 6px; padding: 10px 14px;
  background: var(--primary-soft); border-radius: var(--radius-sm);
  font-size: 14px; display: flex; align-items: baseline; gap: 12px;
}
.pv-box strong { color: var(--primary); font-size: 17px; }
.pv-formula { font-size: 12px; color: var(--text-3); }
</style>
