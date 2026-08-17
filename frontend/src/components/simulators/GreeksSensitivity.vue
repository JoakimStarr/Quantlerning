<script setup lang="ts">
// Greeks 敏感度曲线（BS 解析式）：Delta/Gamma/Vega/Theta/Rho 随标的价格 S 变化
// 教学点：Delta 呈 S 形（平值≈0.5）、Gamma 在山峰（平值最大）、Vega 也峰值在平值、
// Theta 平值最负（时间价值消耗最快）——五个 Greeks 的「形状」比数值更重要
import { computed, ref } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, MarkLineComponent } from 'echarts/components'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent])

function stdNormCdf(x: number): number {
  const t = 1 / (1 + 0.2316419 * Math.abs(x))
  const d = 0.3989422804014327 * Math.exp((-x * x) / 2)
  let p = d * t * (0.31938153 + t * (-0.356563782 + t * (1.781477937 + t * (-1.821255978 + t * 1.330274429))))
  return x > 0 ? 1 - p : p
}

function stdNormPdf(x: number): number {
  return Math.exp((-x * x) / 2) / Math.sqrt(2 * Math.PI)
}

const K = ref(100)
const sigma = ref(0.2755) // 锚定真实锚点：茅台 2024 年化波动 27.55%
const T = ref(1)
const r = ref(0.03)

// 5 个 Greeks（看涨，解析式）
function greeks(S: number) {
  const tv = T.value
  if (tv <= 0) return { delta: 0, gamma: 0, vega: 0, theta: 0, rho: 0 }
  const d1 = (Math.log(S / K.value) + (r.value + (sigma.value * sigma.value) / 2) * tv) / (sigma.value * Math.sqrt(tv))
  const d2 = d1 - sigma.value * Math.sqrt(tv)
  const delta = stdNormCdf(d1)
  const gamma = stdNormPdf(d1) / (S * sigma.value * Math.sqrt(tv))
  const vega = S * stdNormPdf(d1) * Math.sqrt(tv)
  const theta = (-S * stdNormPdf(d1) * sigma.value) / (2 * Math.sqrt(tv)) - r.value * K.value * Math.exp(-r.value * tv) * stdNormCdf(d2)
  const rho = K.value * tv * Math.exp(-r.value * tv) * stdNormCdf(d2)
  return { delta, gamma, vega, theta, rho }
}

const S = ref(100)

const current = computed(() => greeks(S.value))

const curve = computed(() => {
  const xs = Array.from({ length: 41 }, (_, i) => 60 + i * 2)
  return {
    x: xs,
    delta: xs.map((s) => greeks(s).delta),
    gamma: xs.map((s) => greeks(s).gamma),
    vega: xs.map((s) => greeks(s).vega),
    theta: xs.map((s) => greeks(s).theta),
    rho: xs.map((s) => greeks(s).rho),
  }
})

// 切换显示的 Greeks
const active = ref<'delta' | 'gamma' | 'vega' | 'theta' | 'rho'>('gamma')

const seriesConfig: Record<string, { name: string; color: string }> = {
  delta: { name: 'Delta', color: C.value.primary },
  gamma: { name: 'Gamma', color: C.value.danger },
  vega: { name: 'Vega', color: C.value.warning },
  theta: { name: 'Theta', color: C.value.violet },
  rho: { name: 'Rho', color: C.value.cyan },
}

const option = computed(() => {
  const c = curve.value
  const cfg = seriesConfig[active.value]
  return {
    animation: false,
    grid: { left: 52, right: 24, top: 36, bottom: 44 },
    tooltip: { trigger: 'axis', formatter: (ps: any[]) => `${ps[0].axisValue}<br/>${ps[0].seriesName} = ${ps[0].data[1].toFixed(4)}` },
    legend: { top: 0, textStyle: { fontSize: 11 } },
    xAxis: { type: 'value', name: '标的价格 S', nameLocation: 'middle', nameGap: 30, axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', name: cfg.name, nameLocation: 'middle', nameGap: 30, axisLabel: { fontSize: 10 } },
    series: [
      {
        name: cfg.name,
        type: 'line',
        data: c.x.map((x, i) => [x, +c[active.value][i].toFixed(4)]),
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 2.5, color: cfg.color },
        markLine: {
          silent: true,
          symbol: 'none',
          data: [
            { xAxis: K.value, label: { formatter: 'K（平值）', position: 'insideEndTop' }, lineStyle: { color: C.value.slate, type: 'dashed' } },
            { xAxis: S.value, label: { formatter: `S=${S.value}`, position: 'end' }, lineStyle: { color: C.value.slate, type: 'dotted' } },
          ],
        },
      },
    ],
  }
})
</script>

<template>
  <div class="greeks">
    <div class="controls">
      <label>S <input type="range" v-model.number="S" min="60" max="140" step="1" /> {{ S }}</label>
      <label>K <input type="range" v-model.number="K" min="60" max="140" step="1" /> {{ K }}</label>
      <label>σ <input type="range" v-model.number="sigma" min="0.05" max="0.8" step="0.01" /> {{ (sigma * 100).toFixed(0) }}%</label>
      <label>T <input type="range" v-model.number="T" min="0.1" max="3" step="0.1" /> {{ T.toFixed(1) }} 年</label>
      <label>r <input type="range" v-model.number="r" min="0" max="0.1" step="0.005" /> {{ (r * 100).toFixed(2) }}%</label>
    </div>
    <div class="switch">
      <button v-for="k in Object.values(seriesConfig)" :key="k.name" :class="['gbtn', { on: active === k.name }]" @click="active = k.name as any">
        {{ k.name }}
      </button>
    </div>
    <div class="stats">
      <span class="chip">Delta <strong>{{ current.delta.toFixed(3) }}</strong></span>
      <span class="chip">Gamma <strong>{{ current.gamma.toFixed(4) }}</strong></span>
      <span class="chip">Vega <strong>{{ current.vega.toFixed(3) }}</strong></span>
      <span class="chip">Theta <strong>{{ current.theta.toFixed(4) }}</strong></span>
      <span class="chip">Rho <strong>{{ current.rho.toFixed(3) }}</strong></span>
    </div>
    <ThemedChart class="chart" :option="option" autoresize />
    <p class="note">Greeks 解析式（看涨，示意参数）：$\Delta=N(d_1)$、$\Gamma=\frac{\phi(d_1)}{S\sigma\sqrt{T}}$、$\text{Vega}=S\phi(d_1)\sqrt{T}$、$\Theta=-\frac{S\phi(d_1)\sigma}{2\sqrt{T}}-rKe^{-rT}N(d_2)$。切换按钮看每个 Greeks 的「形状」：Gamma 在平值（S=K）处最高，Theta 在平值处最负（时间消耗最快）。真实锚点：σ 默认 27.55%（茅台 2024 年化波动），r 默认 LPR 1Y 3.0%。</p>
  </div>
</template>

<style scoped>
.greeks { padding: 16px; }
.chart { height: 320px; }
.controls { display: flex; gap: 14px; flex-wrap: wrap; align-items: center; margin-bottom: 10px; font-size: 12.5px; color: var(--text-2); }
.controls label { display: flex; align-items: center; gap: 6px; }
.controls input[type='range'] { width: 80px; }
.switch { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 10px; }
.gbtn {
  font-size: 12.5px; padding: 4px 14px; border-radius: 999px; cursor: pointer;
  border: 1px solid var(--border, rgba(128,128,128,0.3)); background: transparent; color: var(--text-2);
}
.gbtn.on { background: var(--primary); color: #fff; border-color: var(--primary); }
.stats { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
.chip {
  font-size: 12.5px; color: var(--text-3);
  padding: 4px 10px; border-radius: 999px; background: var(--bg-hover);
}
.chip strong { color: var(--primary); }
.note { font-size: 12.5px; color: var(--text-3); margin-top: 10px; line-height: 1.6; }
</style>
