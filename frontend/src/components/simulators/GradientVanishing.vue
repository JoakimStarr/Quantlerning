<script setup lang="ts">
// 梯度消失演示（纯数学可视化）：RNN 反向传播沿时间步的梯度 = 每步 tanh' 连乘
// 教学点：tanh'(z) ≤ 1，L 步连乘 → 梯度指数衰减 → 远时间步学不到
import { computed, ref } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, MarkLineComponent } from 'echarts/components'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent])

function tanh(z: number): number {
  return Math.tanh(z)
}

// 梯度传播：g_t = g_{t-1} * tanh'(h_{t-1})，g_0 = 1
function gradTrajectory(hs: number[]): number[] {
  const out: number[] = []
  let g = 1
  out.push(g)
  for (let i = 1; i < hs.length; i++) {
    const dh = 1 - hs[i - 1] * hs[i - 1] // tanh' = 1 - tanh²
    g *= dh
    out.push(g)
  }
  return out
}

const steps = ref(10)
const h0 = ref(0.8)

const data = computed(() => {
  const n = steps.value
  // 用当前 h0 重算轨迹
  const hs: number[] = []
  let h = h0.value
  hs.push(h)
  for (let i = 1; i < n; i++) {
    h = tanh(h)
    hs.push(h)
  }
  return { hs, grads: gradTrajectory(hs) }
})

const option = computed(() => {
  const d = data.value
  const xs = d.hs.map((_, i) => i + 1)
  return {
    animation: false,
    grid: { left: 52, right: 24, top: 36, bottom: 44 },
    tooltip: { trigger: 'axis' },
    legend: { top: 0, textStyle: { fontSize: 11 } },
    xAxis: { type: 'category', name: '时间步 t', nameLocation: 'middle', nameGap: 30, data: xs, axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', name: '数值', nameLocation: 'middle', nameGap: 36, axisLabel: { fontSize: 10 } },
    series: [
      {
        name: '隐藏状态 h_t',
        type: 'line',
        data: d.hs.map((v, i) => [xs[i], +v.toFixed(4)]),
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 2, color: C.value.primary },
      },
      {
        name: '梯度（连乘）',
        type: 'line',
        data: d.grads.map((v, i) => [xs[i], +v.toFixed(4)]),
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 2, color: C.value.danger },
        areaStyle: { color: C.value.danger, opacity: 0.08 },
        markLine: {
          silent: true,
          symbol: 'none',
          data: [{ yAxis: 0, label: { formatter: '0', position: 'insideEndRight' }, lineStyle: { color: C.value.text, type: 'dotted' } }],
        },
      },
    ],
  }
})
</script>

<template>
  <div class="grad-vanish">
    <div class="controls">
      <label>时间步 L <input type="range" v-model.number="steps" min="3" max="20" step="1" /> {{ steps }}</label>
      <label>初始 h₀ <input type="range" v-model.number="h0" min="0.1" max="1.5" step="0.05" /> {{ h0.toFixed(2) }}</label>
    </div>
    <div class="stats">
      <span class="chip">最后一步梯度 <strong>{{ data.grads[data.grads.length - 1].toExponential(1) }}</strong></span>
      <span class="chip">衰减量级 <strong>~{{ Math.abs(Math.log10(Math.max(data.grads[data.grads.length - 1], 1e-15))).toFixed(0) }} 个数量级</strong></span>
    </div>
    <ThemedChart class="chart" :option="option" autoresize />
    <p class="note">沿时间反向传播：$\frac{\partial h_t}{\partial h_{t-1}}=\tanh'(h_{t-1})=1-\tanh^2(h_{t-1})\le 1$。$L$ 步的梯度是这些导数的**连乘**——红色曲线随步数指数衰减，这正是「普通 RNN 记不住长期信息」的数学来源。$\tanh'$ 恒 ≤ 1，连乘必缩；LSTM 用门控让这条「乘法链」变成可调节的加法路径，从而缓解消失。</p>
  </div>
</template>

<style scoped>
.grad-vanish { padding: 16px; }
.chart { height: 320px; }
.controls { display: flex; gap: 14px; flex-wrap: wrap; align-items: center; margin-bottom: 10px; font-size: 12.5px; color: var(--text-2); }
.controls label { display: flex; align-items: center; gap: 6px; }
.controls input[type='range'] { width: 90px; }
.stats { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
.chip {
  font-size: 12.5px; color: var(--text-3);
  padding: 4px 10px; border-radius: 999px; background: var(--bg-hover);
}
.chip strong { color: var(--primary); }
.note { font-size: 12.5px; color: var(--text-3); margin-top: 10px; line-height: 1.6; }
</style>
