<script setup lang="ts">
import { computed, ref } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, MarkLineComponent, MarkPointComponent } from 'echarts/components'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent, MarkPointComponent])

// 凸性演示：价格-收益率曲线（真实） vs 久期一阶近似（切线） vs 凸性二阶修正
// ΔP/P ≈ -D*·Δy + ½·C·(Δy)²
// 教学示意模型（纯数学演示）

const props = defineProps<{
  params?: Record<string, unknown>
}>()

const face = 100
const coupon = 5 // 票息率 %
const years = 10 // 期限
const y0 = 5 // 当前 YTM %
const dy = ref(typeof props.params?.dy === 'number' ? props.params.dy : 1) // 利率变动 %

function price(yPct: number): number {
  const y = yPct / 100
  let p = 0
  for (let t = 1; t <= years; t++) p += (coupon / 100) * face / (1 + y) ** t
  p += face / (1 + y) ** years
  return p
}

// 一阶导：dP/dy
function dPrice(yPct: number): number {
  const y = yPct / 100
  let s = 0
  for (let t = 1; t <= years; t++) s += -t * (coupon / 100) * face / (1 + y) ** (t + 1)
  s += -years * face / (1 + y) ** (years + 1)
  return s
}

// 二阶导：d²P/dy²
function d2Price(yPct: number): number {
  const y = yPct / 100
  let s = 0
  for (let t = 1; t <= years; t++) s += t * (t + 1) * (coupon / 100) * face / (1 + y) ** (t + 2)
  s += years * (years + 1) * face / (1 + y) ** (years + 2)
  return s
}

const P0 = price(y0)
const dP0 = dPrice(y0)
const d2P0 = d2Price(y0)
const modDur = -dP0 / P0 // 修正久期 D*
const convexity = d2P0 / P0 // 凸性 C

// 曲线：实际价格、一阶切线、二阶近似（覆盖整个收益率区间）
const curve = computed<[number, number][]>(() => {
  const out: [number, number][] = []
  for (let y = 50; y <= 1500; y += 5) out.push([y / 100, +price(y / 100).toFixed(3)])
  return out
})
const lineApprox = computed<[number, number][]>(() => {
  const out: [number, number][] = []
  for (let y = 50; y <= 1500; y += 5) out.push([y / 100, +(P0 + dP0 * (y / 100 - y0 / 100)).toFixed(3)])
  return out
})
const quadApprox = computed<[number, number][]>(() => {
  const out: [number, number][] = []
  for (let y = 50; y <= 1500; y += 5) {
    const d = y / 100 - y0 / 100
    out.push([y / 100, +(P0 + dP0 * d + 0.5 * d2P0 * d * d).toFixed(3)])
  }
  return out
})

// Δy 处的价格变化 %
const target = computed(() => y0 + dy.value)
const actual = computed(() => (price(target.value) - P0) / P0 * 100)
const firstOrder = computed(() => -modDur * (dy.value / 100) * 100)
const secondOrder = computed(() => (-modDur * (dy.value / 100) + 0.5 * convexity * (dy.value / 100) ** 2) * 100)

const option = computed(() => ({
  animation: true,
  grid: { left: 52, right: 24, top: 40, bottom: 44 },
  tooltip: {
    trigger: 'axis',
    formatter: (ps: any[]) => {
      const p = Array.isArray(ps) ? ps[0] : ps
      return `收益率 ${Number(p.value[0]).toFixed(1)}%<br/>价格 ${Number(p.value[1]).toFixed(2)} 元`
    },
  },
  legend: { top: 0, textStyle: { fontSize: 12 } },
  xAxis: {
    type: 'value', name: '到期收益率 YTM %', nameLocation: 'middle', nameGap: 28,
    min: 0.5, max: 15, axisLabel: { fontSize: 10 },
  },
  yAxis: { type: 'value', name: '价格', nameLocation: 'middle', nameGap: 40, axisLabel: { fontSize: 10 }, scale: true },
  series: [
    {
      name: '真实价格曲线',
      type: 'line', symbol: 'none',
      data: curve.value,
      lineStyle: { width: 3, color: '#2563eb' },
      markPoint: {
        symbolSize: 44,
        label: { fontSize: 10, formatter: (p: any) => `${Number(p.value).toFixed(1)}` },
        data: [{ coord: [y0, +P0.toFixed(2)], value: +P0.toFixed(2) }],
      },
      markLine: {
        silent: true,
        symbol: 'none',
        lineStyle: { color: '#94a3b8', type: 'dotted' },
        label: { fontSize: 11, formatter: `Δy=${dy.value > 0 ? '+' : ''}${dy.value.toFixed(1)}%` },
        data: [{ xAxis: target.value }],
      },
    },
    {
      name: '久期近似（一阶）',
      type: 'line', symbol: 'none',
      data: lineApprox.value,
      lineStyle: { width: 2, color: '#dc2626', type: 'dashed' },
    },
    {
      name: '凸性修正（二阶）',
      type: 'line', symbol: 'none',
      data: quadApprox.value,
      lineStyle: { width: 2, color: '#16a34a', type: 'dashed' },
    },
  ],
}))
</script>

<template>
  <div class="convexity-demo">
    <div class="result-row">
      <div class="result-box">
        <span class="muted">真实价格变化</span>
        <strong class="res-actual">{{ actual.toFixed(2) }}%</strong>
      </div>
      <div class="result-box">
        <span class="muted">久期近似</span>
        <strong class="res-first">{{ firstOrder.toFixed(2) }}%</strong>
        <span class="err">误差 {{ (firstOrder - actual).toFixed(2) }}pp</span>
      </div>
      <div class="result-box">
        <span class="muted">凸性修正</span>
        <strong class="res-second">{{ secondOrder.toFixed(2) }}%</strong>
        <span class="err">误差 {{ (secondOrder - actual).toFixed(2) }}pp</span>
      </div>
    </div>

    <VChart class="chart" :option="option" autoresize />

    <div class="controls">
      <div class="control-row">
        <span class="control-label">利率变动 Δy</span>
        <input v-model.number="dy" type="range" min="-3" max="3" step="0.1" class="slider" />
        <span class="control-value">{{ dy > 0 ? '+' : '' }}{{ dy.toFixed(1) }}%</span>
      </div>
      <div class="params">
        债券参数：票息 {{ coupon }}% · 期限 {{ years }} 年 · 面值 {{ face }} · 当前 YTM {{ y0 }}%
        （修正久期 {{ modDur.toFixed(2) }} · 凸性 {{ convexity.toFixed(1) }}）
      </div>
      <div class="tip">
        拖动 Δy 观察：红线（久期切线）与蓝线（真实曲线）的差距随 |Δy| 增大而拉大——线性近似高估利率上升的跌幅。绿线（二阶凸性修正）始终紧贴真实曲线：凸性项 $+\tfrac{1}{2}C(\Delta y)^2$ 恒为正，抵消久期近似误差。利率波动越大，凸性越值钱。
      </div>
    </div>
  </div>
</template>

<style scoped>
.convexity-demo { padding: 16px; }
.chart { height: 320px; }
.result-row { display: flex; gap: 10px; margin-bottom: 12px; }
.result-box {
  flex: 1; padding: 10px 12px; border-radius: var(--radius-sm);
  background: var(--bg-hover); text-align: center;
  display: flex; flex-direction: column; gap: 2px;
}
.muted { font-size: 12px; color: var(--text-3); }
.result-box strong { font-size: 17px; }
.res-actual { color: #2563eb; }
.res-first { color: #dc2626; }
.res-second { color: #16a34a; }
.err { font-size: 11px; color: var(--text-3); }
.controls { margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border); }
.control-row { display: flex; align-items: center; gap: 12px; }
.control-label { width: 88px; font-size: 13px; color: var(--text-2); flex-shrink: 0; }
.slider { flex: 1; accent-color: var(--primary); cursor: pointer; }
.control-value { width: 64px; font-size: 13px; font-weight: 600; color: var(--primary); text-align: right; flex-shrink: 0; }
.params { margin-top: 10px; font-size: 12.5px; color: var(--text-2); }
.tip { margin-top: 8px; font-size: 12.5px; color: var(--text-3); line-height: 1.7; }
</style>
