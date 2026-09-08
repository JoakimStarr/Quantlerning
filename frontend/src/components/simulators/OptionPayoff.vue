<script setup lang="ts">
// 期权/期货到期损益图（教学示意，函数关系）：四类基本头寸的到期损益 + 含权利金的净盈亏
// 教学点：① 期货是线性损益（多空对称），期权是折线（损益不对称 = 权利与义务不对等）；
//        ② 期权价格 = 内在价值 + 时间价值，买入方的最大亏损 = 权利金，盈亏平衡点 = K ± 权利金；
//        ③ 卖方收益封顶（权利金）、风险不封顶——「卖出期权」是真正意义上的风险敞口。
import { computed, ref } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, MarkLineComponent } from 'echarts/components'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent])

type Kind = 'futures' | 'call' | 'put'
type Side = 'long' | 'short'

const kind = ref<Kind>('call')
const side = ref<Side>('long')
const K = ref(100) // 执行价 K（期货为开仓价 F）
const premium = ref(8) // 权利金（示意，仅期权适用）

const isOption = computed(() => kind.value !== 'futures')

// 到期损益（不计权利金）
function payoffAt(S: number): number {
  if (kind.value === 'futures') return side.value === 'long' ? S - K.value : K.value - S
  const k = K.value
  const inner = kind.value === 'call' ? Math.max(S - k, 0) : Math.max(k - S, 0)
  return side.value === 'long' ? inner : -inner
}

// 净盈亏（计入权利金：买方付出、卖方收取）
function profitAt(S: number): number {
  const p = isOption.value ? premium.value : 0
  return side.value === 'long' ? payoffAt(S) - p : payoffAt(S) + p
}

const xs = Array.from({ length: 101 }, (_, i) => 50 + i)

const curve = computed(() => ({
  x: xs,
  payoff: xs.map(payoffAt),
  profit: xs.map(profitAt),
}))

// 盈亏平衡点（净盈亏=0 处）；期货的平衡点就是开仓价 F（由 K/F 线标出），不再重复标注
const breakevens = computed<number[]>(() => {
  if (!isOption.value) return []
  if (kind.value === 'call') return [K.value + premium.value]
  return [K.value - premium.value]
})

// 上下限（封顶端用于顶部 chips 展示；null = 不封顶）
const stats = computed<{ maxGain: number | null; maxLoss: number | null }>(() => {
  if (!isOption.value) return { maxGain: null, maxLoss: null }
  const p = premium.value
  if (kind.value === 'call')
    return side.value === 'long'
      ? { maxGain: null, maxLoss: -p }
      : { maxGain: p, maxLoss: null }
  const k = K.value
  return side.value === 'long'
    ? { maxGain: k - p, maxLoss: -p }
    : { maxGain: p, maxLoss: -(k - p) }
})

const posName = computed(() => {
  const d = side.value === 'long' ? '买入' : '卖出'
  const t = { futures: '期货', call: '看涨期权', put: '看跌期权' }[kind.value]
  return `${d}${t}`
})

const option = computed(() => {
  const c = curve.value
  const be = breakevens.value
  const markLines: Record<string, unknown>[] = [
    {
      xAxis: K.value,
      label: { formatter: kind.value === 'futures' ? '开仓价 F' : '执行价 K', position: 'insideEndTop' },
      lineStyle: { color: C.value.slate, type: 'dashed' },
    },
    { yAxis: 0, label: { formatter: '盈亏 0', position: 'insideEndLeft' }, lineStyle: { color: C.value.slate, type: 'dotted' } },
  ]
  for (const b of be) {
    markLines.push({
      xAxis: b,
      label: { formatter: `盈亏平衡 ${b}`, position: 'end' },
      lineStyle: { color: C.value.warning, type: 'solid' },
    })
  }
  const series: Record<string, unknown>[] = []
  if (isOption.value) {
    series.push({
      name: '到期损益（不计权利金）',
      type: 'line',
      data: c.x.map((x, i) => [x, +c.payoff[i].toFixed(2)]),
      smooth: false,
      symbol: 'none',
      lineStyle: { width: 1.5, color: C.value.slateStrong, type: 'dashed' },
    })
  }
  series.push({
    name: isOption.value ? '净盈亏（含权利金）' : '到期损益',
    type: 'line',
    data: c.x.map((x, i) => [x, +c.profit[i].toFixed(2)]),
    smooth: false,
    symbol: 'none',
    lineStyle: { width: 2.5, color: C.value.primary },
    markLine: {
      silent: true,
      symbol: 'none',
      data: markLines,
    },
  })
  return {
    animation: false,
    grid: { left: 52, right: 24, top: 40, bottom: 44 },
    tooltip: {
      trigger: 'axis',
      formatter: (ps: any[]) => {
        const p = ps[0]
        const s = p.data[0]
        const prof = profitAt(s)
        const pay = isOption.value ? payoffAt(s) : prof
        const lines = [`标的价格 S<sub>T</sub> = ${s}`]
        if (isOption.value) lines.push(`到期损益（不计权利金）= ${pay >= 0 ? '+' : ''}${pay.toFixed(1)}`)
        lines.push(`净盈亏（含权利金）= ${prof >= 0 ? '+' : ''}${prof.toFixed(1)}`)
        return lines.join('<br/>')
      },
    },
    legend: { top: 0, textStyle: { fontSize: 11 } },
    xAxis: { type: 'value', name: '到期标的价格 S_T', min: 50, max: 150, nameLocation: 'middle', nameGap: 30, axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', name: '损益', min: -100, max: 100, nameLocation: 'middle', nameGap: 40, axisLabel: { fontSize: 10 } },
    series,
  }
})
</script>

<template>
  <div class="option-payoff">
    <div class="controls">
      <div class="group">
        <button :class="['gbtn', { on: kind === 'futures' }]" @click="kind = 'futures'">期货</button>
        <button :class="['gbtn', { on: kind === 'call' }]" @click="kind = 'call'">看涨期权</button>
        <button :class="['gbtn', { on: kind === 'put' }]" @click="kind = 'put'">看跌期权</button>
      </div>
      <div class="group">
        <button :class="['gbtn', { on: side === 'long' }]" @click="side = 'long'">买入</button>
        <button :class="['gbtn', { on: side === 'short' }]" @click="side = 'short'">卖出</button>
      </div>
      <label>K/F <input type="range" v-model.number="K" min="60" max="140" step="1" /> {{ K }}</label>
      <label v-if="isOption">权利金 <input type="range" v-model.number="premium" min="0" max="25" step="1" /> {{ premium }}</label>
    </div>
    <div class="stats">
      <span class="chip"><strong>{{ posName }}</strong></span>
      <span class="chip" v-if="stats.maxGain != null">最大收益 = <strong>+{{ stats.maxGain }}</strong></span>
      <span class="chip" v-else>收益理论上不封顶</span>
      <span class="chip" v-if="stats.maxLoss != null">最大亏损 = <strong>{{ stats.maxLoss }}</strong></span>
      <span class="chip" v-else>亏损理论上不封顶</span>
    </div>
    <ThemedChart class="chart" :option="option" autoresize />
    <p class="note">到期损益图（教学示意，函数关系）：蓝线是当前头寸的净盈亏。切换「期货 → 看涨/看跌」对比关键差异——期货是穿过开仓价的直线（多空对称），期权在行权价处折断（多空不对称）；再切「买入 → 卖出」，看买入方最大亏损=权利金、卖方收益=权利金但亏损不封顶。</p>
  </div>
</template>

<style scoped>
.option-payoff { padding: 16px; }
.chart { height: 340px; }
.controls { display: flex; gap: 14px; flex-wrap: wrap; align-items: center; margin-bottom: 10px; font-size: 12.5px; color: var(--text-2); }
.controls .group { display: flex; gap: 4px; }
.controls label { display: flex; align-items: center; gap: 6px; }
.controls input[type='range'] { width: 90px; }
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
