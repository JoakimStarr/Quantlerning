<script setup lang="ts">
import { computed, ref } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, MarkLineComponent, MarkPointComponent } from 'echarts/components'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent, MarkPointComponent])

// 债券定价：价格-收益率曲线（凸的），拖动收益率 y 看价格与久期变化
// 教学示意模型（非真实数据）

const props = defineProps<{
  params?: Record<string, unknown>
}>()

const coupon = ref(typeof props.params?.coupon === 'number' ? props.params.coupon : 5) // 票息率 %
const years = ref(typeof props.params?.years === 'number' ? props.params.years : 10) // 期限
const face = 100
const yieldRate = ref(5) // 当前 YTM %

function price(yPct: number): number {
  const y = yPct / 100
  let p = 0
  for (let t = 1; t <= years.value; t++) p += (coupon.value / 100) * face / (1 + y) ** t
  p += face / (1 + y) ** years.value
  return p
}

// 麦考利久期（加权回款时间）
function macaulay(yPct: number): number {
  const y = yPct / 100
  let num = 0
  let den = 0
  for (let t = 1; t <= years.value; t++) {
    const cf = (coupon.value / 100) * face
    num += t * cf / (1 + y) ** t
    den += cf / (1 + y) ** t
  }
  num += years.value * face / (1 + y) ** years.value
  den += face / (1 + y) ** years.value
  return num / den
}

// 价格-收益率曲线：y 从 0.5% 到 15%
const curve = computed<[number, number][]>(() => {
  const out: [number, number][] = []
  for (let y = 50; y <= 1500; y += 5) out.push([y / 100, +price(y / 100).toFixed(2)])
  return out
})

const curPrice = computed(() => price(yieldRate.value))
const duration = computed(() => macaulay(yieldRate.value))
// 修正久期 ≈ D/(1+y)
const modDuration = computed(() => duration.value / (1 + yieldRate.value / 100))
// 利率 ±1% 的价格变化估算
const dp1 = computed(() => (price(yieldRate.value - 1) - curPrice.value) / curPrice.value * 100)
const dm1 = computed(() => (price(yieldRate.value + 1) - curPrice.value) / curPrice.value * 100)

const option = computed(() => ({
  animation: true,
  grid: { left: 52, right: 24, top: 36, bottom: 44 },
  tooltip: {
    trigger: 'axis',
    formatter: (ps: any) => {
      const a = Array.isArray(ps) ? ps[0] : ps
      return `收益率 ${Number(a.value[0]).toFixed(1)}%<br/>债券价格 ${Number(a.value[1]).toFixed(2)} 元`
    },
  },
  legend: { top: 0, textStyle: { fontSize: 12 } },
  xAxis: {
    type: 'value',
    name: '到期收益率 YTM %',
    nameLocation: 'middle',
    nameGap: 28,
    min: 0.5,
    max: 15,
    axisLabel: { fontSize: 10 },
  },
  yAxis: { type: 'value', name: '价格', nameLocation: 'middle', nameGap: 40, axisLabel: { fontSize: 10 } },
  series: [
    {
      name: '价格-收益率曲线',
      type: 'line',
      data: curve.value,
      symbol: 'none',
      lineStyle: { width: 2.5, color: '#2563eb' },
      markPoint: {
        symbolSize: 48,
        label: { fontSize: 10 },
        data: [
          {
            coord: [yieldRate.value, +curPrice.value.toFixed(2)],
            value: `y=${yieldRate.value}%`,
            itemStyle: { color: '#d97706' },
          },
        ],
      },
    },
  ],
}))
</script>

<template>
  <div class="bond-dur">
    <div class="result">
      <div class="result-item">
        <span class="result-label">债券价格</span>
        <strong class="result-value primary">{{ curPrice.toFixed(2) }}</strong>
      </div>
      <div class="result-item">
        <span class="result-label">麦考利久期</span>
        <strong class="result-value">{{ duration.toFixed(2) }} 年</strong>
      </div>
      <div class="result-item">
        <span class="result-label">修正久期</span>
        <strong class="result-value">{{ modDuration.toFixed(2) }}</strong>
      </div>
      <div class="result-item">
        <span class="result-label">利率±1% 价格变动</span>
        <strong class="result-value red">+{{ dm1.toFixed(1) }}% / {{ dp1.toFixed(1) }}%</strong>
      </div>
    </div>

    <VChart class="chart" :option="option" autoresize />

    <div class="controls">
      <div class="control-row">
        <span class="control-label">到期收益率</span>
        <input v-model.number="yieldRate" type="range" min="0.5" max="15" step="0.1" class="slider" />
        <span class="control-value">{{ yieldRate.toFixed(1) }}%</span>
      </div>
      <div class="control-row">
        <span class="control-label">票息率</span>
        <input v-model.number="coupon" type="range" min="1" max="10" step="0.5" class="slider" />
        <span class="control-value">{{ coupon.toFixed(1) }}%</span>
      </div>
      <div class="control-row">
        <span class="control-label">期限</span>
        <input v-model.number="years" type="range" min="1" max="30" step="1" class="slider" />
        <span class="control-value">{{ years }} 年</span>
      </div>
      <div class="tip">
        拖动滑块：曲线总是向右下倾斜（利率↑价格↓），且**凸**——收益率降时价格涨幅大于同等幅度上升时的跌幅。久期越大，曲线在该点越陡（利率敏感度越高）。
      </div>
    </div>
  </div>
</template>

<style scoped>
.bond-dur { padding: 16px; }
.chart { height: 300px; }
.result { display: flex; gap: 20px; margin-bottom: 12px; padding: 12px 16px; background: var(--primary-soft); border-radius: var(--radius-sm); flex-wrap: wrap; }
.result-item { display: flex; flex-direction: column; gap: 2px; }
.result-label { font-size: 12px; color: var(--text-3); }
.result-value { font-size: 18px; font-weight: 700; }
.result-value.primary { color: var(--primary); }
.result-value.red { font-size: 14px; color: #dc2626; }
.controls { margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border); display: flex; flex-direction: column; gap: 10px; }
.control-row { display: flex; align-items: center; gap: 12px; }
.control-label { width: 72px; font-size: 13px; color: var(--text-2); flex-shrink: 0; }
.slider { flex: 1; accent-color: var(--primary); cursor: pointer; }
.control-value { width: 64px; font-size: 13px; font-weight: 600; color: var(--primary); text-align: right; flex-shrink: 0; }
.tip { margin-top: 4px; font-size: 12.5px; color: var(--text-3); line-height: 1.7; }
</style>
