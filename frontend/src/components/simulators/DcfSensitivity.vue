<script setup lang="ts">
import { computed, ref } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C, withAlpha } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, MarkLineComponent } from 'echarts/components'

use([CanvasRenderer, BarChart, LineChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent])

// DCF 两阶段模型：5 年显式预测 + 永续增长终值
// 企业价值 = Σ FCF_t/(1+WACC)^t + TV/(1+WACC)^T
// 其中 TV = FCF_{T+1}/(WACC - g∞)
// 拖动初始 FCF / 5 年增长 g / 折现率 WACC / 永续增长 g∞ 看估值敏感度
// 教学示意模型（非真实数据）

const props = defineProps<{
  params?: Record<string, unknown>
}>()

const fcf0 = ref(typeof props.params?.f0 === 'number' ? props.params.f0 : 100)  // 初始自由现金流
const g = ref(typeof props.params?.g === 'number' ? props.params.g : 12)      // 5 年显式增长率 %
const wacc = ref(typeof props.params?.w === 'number' ? props.params.w : 10)   // 折现率 %
const gInfVal = ref(typeof props.params?.gi === 'number' ? props.params.gi : 3) // 永续增长率 %

const T = 5 // 显式预测期

// 显式预测期 FCF_t = FCF0 · (1+g)^t，t=1..T
const forecast = computed<number[]>(() => {
  const arr: number[] = []
  for (let t = 1; t <= T; t++) arr.push(fcf0.value * Math.pow(1 + g.value / 100, t))
  return arr
})

// 终值（Gordon）= FCF_{T+1}/(WACC - g∞)
const tv = computed(() => {
  const fcfT1 = forecast.value[T - 1] * (1 + gInfVal.value / 100)
  const w = wacc.value / 100
  const gi = gInfVal.value / 100
  return w > gi ? fcfT1 / (w - gi) : NaN
})

// 显式期现值、终值现值、企业总价值
const explicitPv = computed(() =>
  forecast.value.reduce((acc, f, i) => acc + f / Math.pow(1 + wacc.value / 100, i + 1), 0),
)
const tvPv = computed(() => (Number.isFinite(tv.value) ? tv.value / Math.pow(1 + wacc.value / 100, T) : NaN))
const enterpriseValue = computed(() => explicitPv.value + (Number.isFinite(tvPv.value) ? tvPv.value : 0))

// 各期现金流现值（用于柱状图）
const pvBars = computed(() => forecast.value.map((f, i) => Number((f / Math.pow(1 + wacc.value / 100, i + 1)).toFixed(1))))

// 终值现值占企业价值比例（揭示「绝大部分价值来自终值」）
const tvShare = computed(() => {
  const ev = enterpriseValue.value
  return Number.isFinite(tvPv.value) && ev > 0 ? (tvPv.value / ev) * 100 : NaN
})

// EV vs WACC 曲线（固定 g/g∞/FCF0），标注当前位置
const evCurve = computed<[number, number][]>(() => {
  const out: [number, number][] = []
  for (let w = 5; w <= 20; w += 0.25) {
    if (w / 100 <= gInfVal.value / 100) {
      out.push([w, NaN])
      continue
    }
    const explicit = forecast.value.reduce((acc, f, i) => acc + f / Math.pow(1 + w / 100, i + 1), 0)
    const fcfT1 = forecast.value[T - 1] * (1 + gInfVal.value / 100)
    const t = fcfT1 / (w / 100 - gInfVal.value / 100)
    const tvpv = t / Math.pow(1 + w / 100, T)
    out.push([w, Number(((explicit + tvpv)).toFixed(1))])
  }
  return out
})

const option = computed(() => ({
  animation: true,
  grid: [
    { left: 56, right: 24, top: 40, height: '46%' },
    { left: 56, right: 24, top: '66%', height: '28%' },
  ],
  tooltip: {
    trigger: 'axis',
    axisPointer: { type: 'shadow' },
    formatter: (ps: any) => {
      const arr = Array.isArray(ps) ? ps : [ps]
      return arr
        .map((p: any) => {
          const x = p.axisValue
          if (p.seriesName === 'EV vs WACC') {
            const v = Array.isArray(p.value) ? p.value[1] : p.value
            return `${p.seriesName}<br/>WACC=${x}%<br/>EV=${Number(v).toFixed(1)}`
          }
          return `${p.seriesName}<br/>t=${x}<br/>现值=${Number(Array.isArray(p.value) ? p.value[1] : p.value).toFixed(1)}`
        })
        .join('<br/>')
    },
  },
  legend: { top: 0, textStyle: { fontSize: 12 } },
  xAxis: [
    { type: 'category', name: '期数 t', nameLocation: 'middle', nameGap: 24, gridIndex: 0, data: [1, 2, 3, 4, 5].map(String), axisLabel: { fontSize: 10 } },
    { type: 'value', name: 'WACC %', nameLocation: 'middle', nameGap: 24, gridIndex: 1, min: 5, max: 20, axisLabel: { fontSize: 10, formatter: '{value}%' } },
  ],
  yAxis: [
    { type: 'value', name: '现值', nameLocation: 'middle', nameGap: 40, gridIndex: 0, axisLabel: { fontSize: 10 } },
    { type: 'value', name: '企业价值', nameLocation: 'middle', nameGap: 42, gridIndex: 1, axisLabel: { fontSize: 10 } },
  ],
  series: [
    {
      name: '显式期现值',
      type: 'bar',
      xAxisIndex: 0,
      yAxisIndex: 0,
      data: pvBars.value,
      itemStyle: { color: withAlpha(C.value.primary, 0.7) },
      label: { show: true, position: 'top', fontSize: 10, formatter: (p: any) => Number(Array.isArray(p.value) ? p.value[1] : p.value).toFixed(0) },
    },
    {
      name: '终值现值',
      type: 'bar',
      xAxisIndex: 0,
      yAxisIndex: 0,
      data: Array(T).fill(Number.isFinite(tvPv.value) ? Number(tvPv.value.toFixed(1)) : 0),
      itemStyle: { color: withAlpha(C.value.warning, 0.7) },
      label: {
        show: true,
        position: 'top',
        fontSize: 10,
        formatter: () => (Number.isFinite(tvPv.value) ? `TV=${tvPv.value.toFixed(0)}` : '无定义'),
      },
    },
    {
      name: 'EV vs WACC',
      type: 'line',
      xAxisIndex: 1,
      yAxisIndex: 1,
      data: evCurve.value,
      smooth: true,
      symbol: 'none',
      lineStyle: { width: 2, color: C.value.primary },
      markLine: {
        silent: true,
        symbol: 'none',
        lineStyle: { type: 'dashed', color: C.value.danger },
        label: { fontSize: 10, color: C.value.danger, formatter: `WACC = ${wacc.value}%` },
        data: [{ xAxis: wacc.value }],
      },
    },
  ],
}))
</script>

<template>
  <div class="dcf">
    <div class="result">
      <div class="result-item">
        <span class="result-label">企业价值 EV</span>
        <strong class="result-value primary" v-if="Number.isFinite(enterpriseValue)">{{ enterpriseValue.toFixed(1) }}</strong>
        <strong class="result-value red" v-else>无定义（WACC ≤ g∞）</strong>
      </div>
      <div class="result-item">
        <span class="result-label">显式期 PV</span>
        <strong class="result-value">{{ explicitPv.toFixed(1) }}</strong>
      </div>
      <div class="result-item">
        <span class="result-label">终值 PV</span>
        <strong class="result-value" v-if="Number.isFinite(tvPv)">{{ tvPv.toFixed(1) }}</strong>
        <strong class="result-value red" v-else>无定义</strong>
      </div>
      <div class="result-item">
        <span class="result-label">终值占比</span>
        <strong class="result-value warn" v-if="Number.isFinite(tvShare)">{{ tvShare.toFixed(0) }}%</strong>
        <strong class="result-value red" v-else>—</strong>
      </div>
    </div>

    <ThemedChart class="chart" :option="option" autoresize />

    <div class="controls">
      <div class="control-row">
        <span class="control-label">初始 FCF₀</span>
        <input v-model.number="fcf0" type="range" min="20" max="300" step="5" class="slider" />
        <span class="control-value">{{ fcf0 }}</span>
      </div>
      <div class="control-row">
        <span class="control-label">5 年增长 g</span>
        <input v-model.number="g" type="range" min="-5" max="30" step="0.5" class="slider" />
        <span class="control-value">{{ g.toFixed(1) }}%</span>
      </div>
      <div class="control-row">
        <span class="control-label">折现率 WACC</span>
        <input v-model.number="wacc" type="range" min="6" max="18" step="0.25" class="slider" />
        <span class="control-value">{{ wacc.toFixed(1) }}%</span>
      </div>
      <div class="control-row">
        <span class="control-label">永续增长 g∞</span>
        <input v-model.number="gInfVal" type="range" min="0" max="5" step="0.25" class="slider" />
        <span class="control-value">{{ gInfVal.toFixed(2) }}%</span>
      </div>
      <div class="tip">
        DCF 是「精确的错误」：EV 对 WACC 和 g∞ 极敏感——WACC 从 10% 升到 11%（+10% 相对值）EV 往往腰斩，g∞ 从 3% 降到 2.5% EV 也腰斩。注意橙柱（终值现值）通常远大于蓝柱（显式期现值之和），说明企业「绝大部分价值来自终值」，假设的小变动即放大成估值巨震。
      </div>
    </div>
  </div>
</template>

<style scoped>
.dcf { padding: 16px; }
.chart { height: 380px; }
.result { display: flex; gap: 20px; margin-bottom: 12px; padding: 12px 16px; background: var(--primary-soft); border-radius: var(--radius-sm); flex-wrap: wrap; }
.result-item { display: flex; flex-direction: column; gap: 2px; }
.result-label { font-size: 12px; color: var(--text-3); }
.result-value { font-size: 18px; font-weight: 700; }
.result-value.primary { color: var(--primary); }
.result-value.warn { color: var(--warning, #d97706); }
.result-value.red { font-size: 14px; color: var(--danger, #dc2626); }
.controls { margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border); display: flex; flex-direction: column; gap: 10px; }
.control-row { display: flex; align-items: center; gap: 12px; }
.control-label { width: 100px; font-size: 13px; color: var(--text-2); flex-shrink: 0; }
.slider { flex: 1; accent-color: var(--primary); cursor: pointer; }
.control-value { width: 64px; font-size: 13px; font-weight: 600; color: var(--primary); text-align: right; flex-shrink: 0; }
.tip { margin-top: 4px; font-size: 12.5px; color: var(--text-3); line-height: 1.7; }
</style>