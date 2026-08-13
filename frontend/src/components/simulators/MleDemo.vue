<script setup lang="ts">
import { computed, ref } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C, withAlpha } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, MarkLineComponent, MarkPointComponent } from 'echarts/components'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, MarkLineComponent, MarkPointComponent])

// 极大似然估计（MLE）：伯努利试验 p 的似然函数 L(p) = p^k (1-p)^(n-k)
// 拖动 n 与成功次数 k，观察使 L(p) 最大的点 = 样本比例 k/n（模拟演示，非真实数据）

const props = defineProps<{
  params?: Record<string, unknown>
}>()

const n = ref(typeof props.params?.n === 'number' ? props.params.n : 20)
const k = ref(typeof props.params?.k === 'number' ? props.params.k : 8)

function logL(p: number) {
  if (p <= 0 || p >= 1) return 0
  return k.value * Math.log(p) + (n.value - k.value) * Math.log(1 - p)
}

// 似然曲线（用 log-likelihood 更平滑；MLE 位置不变）
const curve = computed<[number, number][]>(() => {
  const pts: [number, number][] = []
  for (let i = 0; i <= 200; i++) {
    const p = i / 200
    pts.push([Number(p.toFixed(3)), Number(logL(p).toFixed(4))])
  }
  return pts
})

const mle = computed(() => (n.value === 0 ? 0 : k.value / n.value))
const maxL = computed(() => (mle.value > 0 && mle.value < 1 ? logL(mle.value) : 0))

const option = computed(() => ({
  animation: true,
  grid: { left: 55, right: 25, top: 40, bottom: 45 },
  tooltip: {
    trigger: 'axis',
    formatter: (ps: any) => {
      const p = Array.isArray(ps) ? ps[0] : ps
      if (!p) return ''
      const v = p.value as number[]
      return `p = ${Number(v[0]).toFixed(2)}<br/>ln L(p) = ${Number(v[1]).toFixed(3)}`
    },
  },
  xAxis: {
    type: 'value',
    name: 'p',
    nameLocation: 'middle',
    nameGap: 30,
    min: 0,
    max: 1,
    axisLabel: { fontSize: 11 },
  },
  yAxis: {
    type: 'value',
    name: 'ln L(p)',
    nameLocation: 'middle',
    nameGap: 46,
    axisLabel: { fontSize: 11 },
  },
  series: [
    {
      name: '对数似然函数 ln L(p)',
      type: 'line',
      smooth: true,
      symbol: 'none',
      data: curve.value,
      lineStyle: { width: 3, color: C.value.primary },
      areaStyle: { color: withAlpha(C.value.primary, 0.10) },
      markPoint: {
        symbol: 'pin',
        symbolSize: 50,
        label: { fontSize: 11, color: '#fff', formatter: 'MLE' },
        data: [{ coord: [mle.value, maxL.value] }],
        itemStyle: { color: C.value.danger },
      },
      markLine: {
        silent: true,
        symbol: 'none',
        label: { fontSize: 11, color: C.value.danger, formatter: `p̂ = k/n = ${mle.value.toFixed(2)}` },
        lineStyle: { color: C.value.danger, type: 'dashed', width: 1.5 },
        data: [{ xAxis: mle.value }],
      },
    },
  ],
}))
</script>

<template>
  <div class="mle">
    <ThemedChart class="chart" :option="option" autoresize />

    <div class="controls">
      <div class="control-row">
        <span class="control-label">试验次数 n</span>
        <input v-model.number="n" type="range" min="2" max="100" step="1" class="slider" />
        <span class="control-value">{{ n }}</span>
      </div>
      <div class="control-row">
        <span class="control-label">成功次数 k</span>
        <input v-model.number="k" type="range" :min="0" :max="n" step="1" class="slider" />
        <span class="control-value">{{ k }}</span>
      </div>
      <div class="result-row">
        <div class="result-box">
          <span class="muted">似然函数的最高点（MLE）</span>
          <strong>p̂ = {{ mle.toFixed(3) }}</strong>
        </div>
        <div class="result-box">
          <span class="muted">等价写法</span>
          <strong>p̂ = k / n</strong>
        </div>
      </div>
      <p class="hint">
        似然函数衡量「假设 p 是这个值时，看到手中数据有多合理」。MLE 就是找到让似然函数取
        最大值的 p——伯努利试验中恰好是样本比例 k/n。曲线越陡，说明数据对 p 的约束越强。
      </p>
    </div>
  </div>
</template>

<style scoped>
.mle { padding: 16px; }
.chart { height: 320px; }
.controls { margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border); display: flex; flex-direction: column; gap: 10px; }
.control-row { display: flex; align-items: center; gap: 12px; }
.control-label { width: 88px; font-size: 13px; color: var(--text-2); flex-shrink: 0; }
.slider { flex: 1; accent-color: var(--primary); cursor: pointer; }
.control-value { width: 40px; font-size: 13px; font-weight: 600; color: var(--primary); text-align: right; flex-shrink: 0; }
.result-row { display: flex; align-items: center; gap: 10px; margin-top: 4px; }
.result-box { flex: 1; padding: 8px 10px; border-radius: var(--radius-sm); background: var(--bg-hover); text-align: center; display: flex; flex-direction: column; gap: 2px; }
.result-box strong { font-size: 15px; color: var(--primary); }
.muted { font-size: 12px; color: var(--text-3); }
.hint { margin-top: 8px; font-size: 12px; color: var(--text-3); line-height: 1.7; }
</style>
