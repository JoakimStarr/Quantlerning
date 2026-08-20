<script setup lang="ts">
import { computed, ref } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, ScatterChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, MarkLineComponent } from 'echarts/components'

use([CanvasRenderer, LineChart, ScatterChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent])

// 二项式（二叉树）定价：步数 N 越多，越收敛到 Black-Scholes 价格
// 教学点：二叉树是 BS 的离散近似——N→∞ 时收敛；「步数滑块」演示收敛速度
function stdNormCdf(x: number): number {
  const t = 1 / (1 + 0.2316419 * Math.abs(x))
  const d = 0.3989422804014327 * Math.exp((-x * x) / 2)
  let p = d * t * (0.31938153 + t * (-0.356563782 + t * (1.781477937 + t * (-1.821255978 + t * 1.330274429))))
  return x > 0 ? 1 - p : p
}

function bsCall(S: number, K: number, sigma: number, T: number, r: number): number {
  if (T <= 0) return Math.max(S - K, 0)
  const d1 = (Math.log(S / K) + (r + (sigma * sigma) / 2) * T) / (sigma * Math.sqrt(T))
  const d2 = d1 - sigma * Math.sqrt(T)
  return S * stdNormCdf(d1) - K * Math.exp(-r * T) * stdNormCdf(d2)
}

function binomialCall(S: number, K: number, sigma: number, T: number, r: number, N: number): number {
  const dt = T / N
  const u = Math.exp(sigma * Math.sqrt(dt))
  const d = 1 / u
  const p = (Math.exp(r * dt) - d) / (u - d)
  const disc = Math.exp(-r * dt)
  // 末节点
  const payoffs: number[] = []
  for (let j = 0; j <= N; j++) {
    const price = S * Math.pow(u, j) * Math.pow(d, N - j)
    payoffs.push(Math.max(price - K, 0))
  }
  // 反向递推
  for (let i = N - 1; i >= 0; i--) {
    for (let j = 0; j <= i; j++) {
      payoffs[j] = disc * (p * payoffs[j + 1] + (1 - p) * payoffs[j])
    }
  }
  return payoffs[0]
}

const S = ref(100)
const K = ref(100)
const sigma = ref(0.2755) // 默认锚定真实锚点：茅台 2024 年化波动 27.55%（quantlab 官方口径）
const T = ref(1)
const r = ref(0.03)
const N = ref(5)

const call = computed(() => binomialCall(S.value, K.value, sigma.value, T.value, r.value, N.value))
const bsRef = computed(() => bsCall(S.value, K.value, sigma.value, T.value, r.value))

// 收敛曲线：N=1..30 的二叉树价格 vs BS 价格
const convergence = computed(() => {
  const xs = Array.from({ length: 30 }, (_, i) => i + 1)
  return {
    x: xs,
    binom: xs.map((n) => binomialCall(S.value, K.value, sigma.value, T.value, r.value, n)),
    bs: bsRef.value,
  }
})

// 二叉树结构（当前 N 下的树节点路径）
const treeData = computed(() => {
  const dt = T.value / N.value
  const u = Math.exp(sigma.value * Math.sqrt(dt))
  const d = 1 / u
  const nodes: [number, number, number][] = []
  for (let i = 0; i <= N.value; i++) {
    for (let j = 0; j <= i; j++) {
      nodes.push([i, j - i / 2, Number((S.value * Math.pow(u, j) * Math.pow(d, i - j)).toFixed(2))])
    }
  }
  return nodes
})

const treeOption = computed(() => ({
  animation: false,
  grid: { left: 40, right: 20, top: 24, bottom: 40 },
  tooltip: { formatter: (p: any) => `步 ${p.value[0]} · 节点 ${p.value[1]}<br/>价格 ${p.value[2]}` },
  xAxis: { type: 'value', name: '步数', nameLocation: 'middle', nameGap: 26, axisLabel: { fontSize: 10 } },
  yAxis: { type: 'value', name: '价格', nameLocation: 'middle', nameGap: 40, axisLabel: { fontSize: 10 } },
  series: [
    {
      name: '树节点',
      type: 'scatter',
      data: treeData.value,
      symbolSize: 6,
      itemStyle: { color: C.value.primary, opacity: 0.7 },
    },
  ],
}))

const convOption = computed(() => {
  const c = convergence.value
  return {
    animation: false,
    grid: { left: 52, right: 24, top: 36, bottom: 40 },
    tooltip: { trigger: 'axis' },
    legend: { top: 0, textStyle: { fontSize: 11 } },
    xAxis: { type: 'category', data: c.x, name: '步数 N', nameLocation: 'middle', nameGap: 26, axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', name: '期权价格', nameLocation: 'middle', nameGap: 44, scale: true, axisLabel: { fontSize: 10 } },
    series: [
      {
        name: '二叉树',
        type: 'line',
        data: c.binom.map((v) => +v.toFixed(2)),
        smooth: true,
        symbol: 'circle',
        symbolSize: 4,
        lineStyle: { width: 1.6, color: C.value.primary },
      },
      {
        name: 'BS 收敛值',
        type: 'line',
        data: c.x.map(() => +c.bs.toFixed(2)),
        symbol: 'none',
        lineStyle: { width: 1.5, color: C.value.danger, type: 'dashed' },
      },
    ],
  }
})
</script>

<template>
  <div class="bt">
    <div class="controls">
      <label>S <input type="range" v-model.number="S" min="60" max="140" step="1" /> {{ S }}</label>
      <label>K <input type="range" v-model.number="K" min="60" max="140" step="1" /> {{ K }}</label>
      <label>σ <input type="range" v-model.number="sigma" min="0.05" max="0.8" step="0.01" /> {{ (sigma * 100).toFixed(0) }}%</label>
      <label>T <input type="range" v-model.number="T" min="0.1" max="3" step="0.1" /> {{ T.toFixed(1) }} 年</label>
      <label>步数 N <input type="range" v-model.number="N" min="1" max="20" step="1" /> {{ N }}</label>
    </div>
    <div class="stats">
      <span class="chip">二叉树价格（N={{ N }}）= <strong>{{ call.toFixed(2) }}</strong></span>
      <span class="chip">BS 价格 = <strong>{{ bsRef.toFixed(2) }}</strong></span>
      <span class="chip" :class="{ pos: Math.abs(call - bsRef) < 0.1 }">误差 <strong>{{ Math.abs(call - bsRef).toFixed(2) }}</strong></span>
    </div>
    <ThemedChart class="chart tree" :option="treeOption" autoresize />
    <p class="note">上图：N 步二叉树节点（步数滑块控制，节点随 N 变密）；下图：收敛曲线——N 从 1 到 30，二叉树价格（蓝）逐步收敛到 BS 价格（红虚线）。真实锚点：r 参考 LPR 1Y 3.0%（示意）。</p>
    <ThemedChart class="chart conv" :option="convOption" autoresize />
  </div>
</template>

<style scoped>
.bt { padding: 16px; }
.chart { width: 100%; }
.tree { height: 260px; margin-bottom: 12px; }
.conv { height: 260px; }
.controls { display: flex; gap: 14px; flex-wrap: wrap; align-items: center; margin-bottom: 10px; font-size: 12.5px; color: var(--text-2); }
.controls label { display: flex; align-items: center; gap: 6px; }
.controls input[type='range'] { width: 90px; }
.stats { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
.chip {
  font-size: 12.5px; color: var(--text-3);
  padding: 4px 10px; border-radius: 999px; background: var(--bg-hover);
}
.chip strong { color: var(--primary); }
.chip.pos strong { color: var(--success); }
.note { font-size: 12.5px; color: var(--text-3); margin: 10px 0; line-height: 1.6; }
</style>