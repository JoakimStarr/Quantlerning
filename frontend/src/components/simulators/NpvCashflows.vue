<script setup lang="ts">
import { computed, ref } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C, withAlpha } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, MarkLineComponent, MarkPointComponent } from 'echarts/components'

use([CanvasRenderer, LineChart, BarChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent, MarkPointComponent])

// 多期现金流净现值：NPV = Σ CF_t/(1+r)^t
// 上：NPV 随折现率 r 的曲线（穿过零点的位置即 IRR）
// 下：各期现金流的现值分布（t0 为投资支出）
// 教学示意模型（纯数学演示）

const props = defineProps<{
  params?: Record<string, unknown>
}>()

// t0 投入 100，后 5 年每年回收 25
const cashflows = [ -100, 25, 25, 25, 25, 25 ]
const r = ref(typeof props.params?.r === 'number' ? props.params.r : 0.08) // 折现率

function npv(rr: number) {
  return cashflows.reduce((acc, cf, t) => acc + cf / Math.pow(1 + rr, t), 0)
}

// 各期现金流现值
const pvSeries = computed(() =>
  cashflows.map((cf, t) => Number((cf / Math.pow(1 + r.value, t)).toFixed(2))),
)

// IRR：二分法在 [0, 0.5] 内求 NPV(r)=0 的根
const internalRate = computed(() => {
  const lo = 0
  const hi = 0.5
  if (npv(lo) * npv(hi) > 0) return null
  let a = lo
  let b = hi
  for (let i = 0; i < 200; i++) {
    const mid = (a + b) / 2
    if (npv(mid) > 0) a = mid
    else b = mid
  }
  return (a + b) / 2
})

const currentNpv = computed(() => npv(r.value))

// NPV 曲线：r → NPV
const curveData = computed<[number, number][]>(() => {
  const out: [number, number][] = []
  for (let p = 0; p <= 200; p++) {
    const rr = p / 1000
    out.push([Number((rr * 100).toFixed(1)), Number(npv(rr).toFixed(2))])
  }
  return out
})

const curveOption = computed(() => ({
  animation: true,
  grid: { left: 52, right: 24, top: 30, bottom: 36 },
  tooltip: {
    trigger: 'axis',
    formatter: (ps: any) => {
      const a = Array.isArray(ps) ? ps[0] : ps
      return `r = ${Number(a.value[0]).toFixed(1)}%<br/>NPV = ${Number(a.value[1]).toFixed(2)} 元`
    },
  },
  xAxis: { type: 'value', name: '折现率 r %', nameLocation: 'middle', nameGap: 26, min: 0, max: 20, axisLabel: { fontSize: 11 } },
  yAxis: { type: 'value', name: 'NPV（元）', nameLocation: 'middle', nameGap: 40, axisLabel: { fontSize: 11 }, scale: true },
  series: [
    {
      name: 'NPV',
      type: 'line',
      smooth: true,
      symbol: 'none',
      data: curveData.value,
      lineStyle: { width: 2.5, color: C.value.primary },
      areaStyle: { color: withAlpha(C.value.primary, 0.06) },
      markLine: {
        silent: true,
        symbol: 'none',
        label: { fontSize: 11, color: C.value.danger, formatter: 'IRR = {c}%' },
        data: internalRate.value != null ? [{ xAxis: +(internalRate.value * 100).toFixed(2) }] : [],
        lineStyle: { color: C.value.danger, type: 'dashed' },
      },
      markPoint: {
        symbolSize: 44,
        label: { fontSize: 10, formatter: (p: any) => Number(p.value).toFixed(1) },
        data: [{ coord: [+(r.value * 100).toFixed(1), +currentNpv.value.toFixed(2)], value: +currentNpv.value.toFixed(2) }],
      },
    },
  ],
}))

const barOption = computed(() => ({
  animation: true,
  grid: { left: 52, right: 24, top: 30, bottom: 36 },
  tooltip: {
    trigger: 'axis',
    formatter: (ps: any) => {
      const a = Array.isArray(ps) ? ps[0] : ps
      return `第 ${a.dataIndex} 年<br/>现值 ${Number(a.value).toFixed(2)} 元`
    },
  },
  xAxis: { type: 'category', name: '期数 t', nameLocation: 'middle', nameGap: 26, data: ['t0', 't1', 't2', 't3', 't4', 't5'], axisLabel: { fontSize: 11 } },
  yAxis: { type: 'value', name: '现金流现值（元）', nameLocation: 'middle', nameGap: 42, axisLabel: { fontSize: 11 } },
  series: [
    {
      name: '现金流现值',
      type: 'bar',
      data: pvSeries.value.map((v, i) => ({ value: v, itemStyle: { color: i === 0 ? C.value.danger : C.value.primary } })),
      barMaxWidth: 44,
      label: { show: true, position: 'top', fontSize: 11, formatter: (p: any) => p.value.toFixed(1) },
    },
  ],
}))
</script>

<template>
  <div class="npv-cashflows">
    <div class="result-row">
      <div class="result-box">
        <span class="muted">折现率 r</span>
        <strong class="result-primary">{{ (r * 100).toFixed(1) }}%</strong>
      </div>
      <div class="result-box">
        <span class="muted">净现值 NPV</span>
        <strong class="result-primary" :class="{ neg: currentNpv < 0 }">{{ currentNpv.toFixed(2) }} 元</strong>
      </div>
      <div class="result-box">
        <span class="muted">内部收益率 IRR</span>
        <strong class="result-primary" v-if="internalRate != null">{{ (internalRate * 100).toFixed(2) }}%</strong>
        <strong class="result-primary" v-else>无定义</strong>
      </div>
    </div>

    <ThemedChart class="chart" :option="curveOption" autoresize />
    <ThemedChart class="chart" :option="barOption" autoresize />

    <div class="controls">
      <div class="control-row">
        <span class="control-label">折现率 r</span>
        <input v-model.number="r" type="range" min="0" max="0.20" step="0.005" class="slider" />
        <span class="control-value">{{ (r * 100).toFixed(1) }}%</span>
      </div>
      <div class="tip">
        现金流为 t0 投入 100，后 5 年每年回收 25。折现率低于 IRR 时 NPV &gt; 0——项目回报超过资金成本，值得投资；高于 IRR 时 NPV &lt; 0，应放弃。IRR 正是 NPV 曲线穿过零点的位置。
      </div>
    </div>
  </div>
</template>

<style scoped>
.npv-cashflows { padding: 16px; }
.chart { height: 240px; }
.result-row { display: flex; gap: 10px; margin-bottom: 12px; }
.result-box {
  flex: 1; padding: 10px 12px; border-radius: var(--radius-sm);
  background: var(--primary-soft); text-align: center;
  display: flex; flex-direction: column; gap: 2px;
}
.muted { font-size: 12px; color: var(--text-3); }
.result-primary { font-size: 18px; font-weight: 700; color: var(--primary); }
.result-primary.neg { color: var(--danger, #dc2626); }
.controls { margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border); }
.control-row { display: flex; align-items: center; gap: 12px; }
.control-label { width: 88px; font-size: 13px; color: var(--text-2); flex-shrink: 0; }
.slider { flex: 1; accent-color: var(--primary); cursor: pointer; }
.control-value { width: 56px; font-size: 13px; font-weight: 600; color: var(--primary); text-align: right; flex-shrink: 0; }
.tip { margin-top: 10px; font-size: 12.5px; color: var(--text-3); line-height: 1.7; }
</style>
