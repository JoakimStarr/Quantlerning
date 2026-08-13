<script setup lang="ts">
import { computed, ref } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, MarkLineComponent } from 'echarts/components'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent])

// Black-Scholes 定价滑块：S/K/σ/T/r 实时计算期权价格
// 教学点：看涨期权价格随标的价格单调上升、随执行价单调下降、随波动率上升
function stdNormCdf(x: number): number {
  // Abramowitz-Stegun 近似
  const t = 1 / (1 + 0.2316419 * Math.abs(x))
  const d = 0.3989422804014327 * Math.exp((-x * x) / 2)
  let p = d * t * (0.31938153 + t * (-0.356563782 + t * (1.781477937 + t * (-1.821255978 + t * 1.330274429))))
  return x > 0 ? 1 - p : p
}

function bsPrice(S: number, K: number, sigma: number, T: number, r: number, type: 'call' | 'put'): number {
  if (T <= 0) return type === 'call' ? Math.max(S - K, 0) : Math.max(K - S, 0)
  const d1 = (Math.log(S / K) + (r + (sigma * sigma) / 2) * T) / (sigma * Math.sqrt(T))
  const d2 = d1 - sigma * Math.sqrt(T)
  if (type === 'call') return S * stdNormCdf(d1) - K * Math.exp(-r * T) * stdNormCdf(d2)
  return K * Math.exp(-r * T) * stdNormCdf(-d2) - S * stdNormCdf(-d1)
}

const S = ref(100)
const K = ref(100)
const sigma = ref(0.2755) // 默认锚定真实锚点：茅台 2024 年化波动 27.55%（quantlab 官方口径）
const T = ref(1)
const r = ref(0.03)

const call = computed(() => bsPrice(S.value, K.value, sigma.value, T.value, r.value, 'call'))
const put = computed(() => bsPrice(S.value, K.value, sigma.value, T.value, r.value, 'put'))

// 价格-标的价格曲线（固定其他参数）
const priceCurve = computed(() => {
  const xs = Array.from({ length: 41 }, (_, i) => 60 + i * 2)
  return {
    x: xs,
    call: xs.map((s) => bsPrice(s, K.value, sigma.value, T.value, r.value, 'call')),
    put: xs.map((s) => bsPrice(s, K.value, sigma.value, T.value, r.value, 'put')),
  }
})

const option = computed(() => {
  const c = priceCurve.value
  return {
    animation: false,
    grid: { left: 52, right: 24, top: 36, bottom: 44 },
    tooltip: { trigger: 'axis' },
    legend: { top: 0, textStyle: { fontSize: 11 } },
    xAxis: { type: 'value', name: '标的价格 S', nameLocation: 'middle', nameGap: 30, axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', name: '期权价格', nameLocation: 'middle', nameGap: 44, axisLabel: { fontSize: 10 } },
    series: [
      {
        name: '看涨 Call',
        type: 'line',
        data: c.x.map((x, i) => [x, +c.call[i].toFixed(2)]),
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 2, color: C.value.primary },
        markLine: {
          silent: true,
          symbol: 'none',
          data: [
            { xAxis: K.value, label: { formatter: 'K', position: 'insideEndTop' }, lineStyle: { color: C.value.slate, type: 'dashed' } },
            { xAxis: S.value, label: { formatter: `S=${S.value}`, position: 'end' }, lineStyle: { color: C.value.danger, type: 'dotted' } },
          ],
        },
      },
      {
        name: '看跌 Put',
        type: 'line',
        data: c.x.map((x, i) => [x, +c.put[i].toFixed(2)]),
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 2, color: C.value.danger },
      },
    ],
  }
})
</script>

<template>
  <div class="bs">
    <div class="controls">
      <label>S <input type="range" v-model.number="S" min="60" max="140" step="1" /> {{ S }}</label>
      <label>K <input type="range" v-model.number="K" min="60" max="140" step="1" /> {{ K }}</label>
      <label>σ <input type="range" v-model.number="sigma" min="0.05" max="0.8" step="0.01" /> {{ (sigma * 100).toFixed(0) }}%</label>
      <label>T <input type="range" v-model.number="T" min="0.1" max="3" step="0.1" /> {{ T.toFixed(1) }} 年</label>
      <label>r <input type="range" v-model.number="r" min="0" max="0.1" step="0.005" /> {{ (r * 100).toFixed(2) }}%</label>
    </div>
    <div class="stats">
      <span class="chip">看涨 Call = <strong>{{ call.toFixed(2) }}</strong></span>
      <span class="chip">看跌 Put = <strong>{{ put.toFixed(2) }}</strong></span>
      <span class="chip">内在价值 (S−K) = <strong>{{ (S - K).toFixed(2) }}</strong></span>
    </div>
    <ThemedChart class="chart" :option="option" autoresize />
    <p class="note">BS 公式（示意参数，非真实期权）：$C=S N(d_1)-K e^{-rT}N(d_2)$。拖动滑块观察：价格-标的价格曲线凸性、内在价值与时间价值的关系。真实锚点：无风险利率可参考 LPR 1Y 3.0%（2026-07 快照）。</p>
  </div>
</template>

<style scoped>
.bs { padding: 16px; }
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