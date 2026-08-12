<script setup lang="ts">
import { computed, ref } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, MarkLineComponent } from 'echarts/components'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent])

// DDM 戈登增长模型：P = D1 / (r - g)
// 拖动 D1（下年股息）/ r（要求回报）/ g（永续增长）看估值变化
// 教学示意模型（非真实数据）

const props = defineProps<{
  params?: Record<string, unknown>
}>()

const d1 = ref(typeof props.params?.d === 'number' ? props.params.d : 2) // 下年股息
const r = ref(typeof props.params?.r === 'number' ? props.params.r : 10) // 要求回报 %
const g = ref(typeof props.params?.g === 'number' ? props.params.g : 4) // 永续增长 %

const price = computed(() => (r.value / 100 > g.value / 100 ? (d1.value / (r.value / 100 - g.value / 100)) : NaN))

// 价格 vs 增长率 g 曲线（固定 D1 与 r）
const curve = computed<[number, number][]>(() => {
  const out: [number, number][] = []
  for (let gg = 0; gg <= 9.9; gg += 0.1) {
    if (r.value / 100 > gg / 100) out.push([gg, +(d1.value / (r.value / 100 - gg / 100)).toFixed(1)])
  }
  return out
})

const option = computed(() => ({
  animation: true,
  grid: { left: 52, right: 24, top: 36, bottom: 44 },
  tooltip: {
    trigger: 'axis',
    formatter: (ps: any) => {
      const a = Array.isArray(ps) ? ps[0] : ps
      return `g = ${Number(a.value[0]).toFixed(1)}%<br/>股价 ${Number(a.value[1]).toFixed(1)} 元`
    },
  },
  legend: { top: 0, textStyle: { fontSize: 12 } },
  xAxis: { type: 'value', name: '永续增长 g %', nameLocation: 'middle', nameGap: 28, min: 0, max: 10, axisLabel: { fontSize: 10 } },
  yAxis: { type: 'value', name: '股价', nameLocation: 'middle', nameGap: 40, axisLabel: { fontSize: 10 }, scale: true },
  series: [
    {
      name: 'P = D₁/(r−g)',
      type: 'line',
      data: curve.value,
      symbol: 'none',
      lineStyle: { width: 2.5, color: '#2563eb' },
      markLine: {
        silent: true,
        symbol: 'none',
        lineStyle: { type: 'dashed', color: '#dc2626' },
        label: { fontSize: 11, color: '#dc2626', formatter: `g = r = ${r.value}%` },
        data: [{ xAxis: r.value }],
      },
    },
  ],
}))
</script>

<template>
  <div class="ddm">
    <div class="result">
      <div class="result-item">
        <span class="result-label">戈登模型估值</span>
        <strong class="result-value primary" v-if="!isNaN(price)">{{ price.toFixed(2) }} 元</strong>
        <strong class="result-value red" v-else>无定义（g ≥ r）</strong>
      </div>
      <div class="result-item">
        <span class="result-label">公式</span>
        <strong class="result-value formula">P = D₁/(r−g)</strong>
      </div>
    </div>

    <VChart class="chart" :option="option" autoresize />

    <div class="controls">
      <div class="control-row">
        <span class="control-label">下年股息 D₁</span>
        <input v-model.number="d1" type="range" min="0.5" max="6" step="0.1" class="slider" />
        <span class="control-value">{{ d1.toFixed(1) }} 元</span>
      </div>
      <div class="control-row">
        <span class="control-label">要求回报 r</span>
        <input v-model.number="r" type="range" min="5" max="15" step="0.5" class="slider" />
        <span class="control-value">{{ r.toFixed(1) }}%</span>
      </div>
      <div class="control-row">
        <span class="control-label">永续增长 g</span>
        <input v-model.number="g" type="range" min="0" max="9" step="0.5" class="slider" />
        <span class="control-value">{{ g.toFixed(1) }}%</span>
      </div>
      <div class="tip">
        g 逼近 r 时估值趋于无穷——分母 (r−g) 极小变化就引起估值巨大波动。这就是「低利率时代高估值」的数学根源：r 下降让分母变小，同样的 D₁ 和 g 估值成倍放大。红线是 g = r 的渐近线。
      </div>
    </div>
  </div>
</template>

<style scoped>
.ddm { padding: 16px; }
.chart { height: 300px; }
.result { display: flex; gap: 20px; margin-bottom: 12px; padding: 12px 16px; background: var(--primary-soft); border-radius: var(--radius-sm); flex-wrap: wrap; }
.result-item { display: flex; flex-direction: column; gap: 2px; }
.result-label { font-size: 12px; color: var(--text-3); }
.result-value { font-size: 20px; font-weight: 700; }
.result-value.primary { color: var(--primary); }
.result-value.red { font-size: 16px; color: #dc2626; }
.result-value.formula { font-size: 15px; color: var(--text-2); font-family: var(--font-mono); }
.controls { margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border); display: flex; flex-direction: column; gap: 10px; }
.control-row { display: flex; align-items: center; gap: 12px; }
.control-label { width: 88px; font-size: 13px; color: var(--text-2); flex-shrink: 0; }
.slider { flex: 1; accent-color: var(--primary); cursor: pointer; }
.control-value { width: 64px; font-size: 13px; font-weight: 600; color: var(--primary); text-align: right; flex-shrink: 0; }
.tip { margin-top: 4px; font-size: 12.5px; color: var(--text-3); line-height: 1.7; }
</style>
