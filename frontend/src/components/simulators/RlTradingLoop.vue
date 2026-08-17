<script setup lang="ts">
// RL 交易循环演示（真实茅台 2024 日线）：状态→动作→环境→奖励 的循环
// 教学点：把 RL 三要素套到交易上——状态=行情特征、动作=仓位、奖励=收益；
// 交互：调动作策略（涨则买/跌则买/随机）看净值曲线差异，体会「奖励设计决定行为」
import { computed, ref } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, MarkLineComponent } from 'echarts/components'
import { useStockDaily } from '@/composables/useStockDaily'
import { mean, std, navFromReturns } from '@/utils/ml'

use([CanvasRenderer, LineChart, BarChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent])

const props = defineProps<{
  params?: Record<string, unknown>
}>()

const code = computed(() => (typeof props.params?.code === 'string' ? props.params.code : 'sh600519'))
const { data, loading, error } = useStockDaily(code)

const rets = computed<number[]>(() => (data.value ? data.value.map((d) => d.pct_chg / 100).slice(1) : []))

// 三种「动作策略」：把状态映射成仓位（0/1）
// 涨则买：昨日收益>0 → 今日满仓（动量类）；跌则买：昨日收益<0 → 今日满仓（反转类）；随机：掷硬币
type Policy = 'momentum' | 'contrarian' | 'random'
const policy = ref<Policy>('momentum')
const lookback = ref(5) // 状态 = 过去 N 日平均收益

function positionsFromPolicy(rets: number[]): number[] {
  const n = rets.length
  const pos: number[] = []
  for (let i = 0; i < n; i++) {
    if (policy.value === 'random') {
      pos.push(Math.random() > 0.5 ? 1 : 0)
      continue
    }
    const lb = Math.max(1, Math.min(lookback.value, i))
    const window = rets.slice(i - lb, i)
    const avg = mean(window)
    if (policy.value === 'momentum') pos.push(avg > 0 ? 1 : 0)
    else pos.push(avg < 0 ? 1 : 0)
  }
  return pos
}

const pos = computed<number[]>(() => positionsFromPolicy(rets.value))
const nav = computed<number[]>(() => navFromReturns(rets.value, pos.value))
const bhNav = computed<number[]>(() => {
  const out = [1]
  for (let i = 1; i < rets.value.length; i++) out.push(out[i - 1] * (1 + rets.value[i]))
  return out
})

const dates = computed<string[]>(() => (data.value ? data.value.map((d) => d.date).slice(1) : []))

const option = computed(() => {
  const xs = dates.value
  return {
    animation: false,
    grid: [
      { left: 52, right: 20, top: 30, height: '52%' },
      { left: 52, right: 20, top: '68%', height: '22%' },
    ],
    tooltip: { trigger: 'axis' },
    legend: { top: 0, textStyle: { fontSize: 11 } },
    xAxis: [
      { type: 'category', data: xs, axisLabel: { fontSize: 10, formatter: (v: string) => v.slice(5) } },
      { type: 'category', data: xs, axisLabel: { show: false } },
    ],
    yAxis: [
      { type: 'value', name: '净值', nameLocation: 'middle', nameGap: 36, axisLabel: { fontSize: 10 } },
      { type: 'value', name: '仓位', min: 0, max: 1, nameLocation: 'middle', nameGap: 30, axisLabel: { fontSize: 10, formatter: (v: number) => (v === 1 ? '满仓' : '空仓') } },
    ],
    series: [
      {
        name: '策略净值',
        type: 'line',
        xAxisIndex: 0,
        data: xs.map((d, i) => [d, +nav.value[i].toFixed(3)]),
        symbol: 'none',
        lineStyle: { width: 2, color: C.value.primary },
      },
      {
        name: '买入持有',
        type: 'line',
        xAxisIndex: 0,
        data: xs.map((d, i) => [d, +bhNav.value[i].toFixed(3)]),
        symbol: 'none',
        lineStyle: { width: 1.5, color: C.value.slate, type: 'dashed' },
      },
      {
        name: '仓位（动作）',
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: xs.map((d, i) => [d, pos.value[i]]),
        barWidth: '90%',
        itemStyle: { color: C.value.cyan, opacity: 0.4 },
      },
    ],
  }
})

// 奖励统计
const stats = computed(() => {
  const r = rets.value
  const p = pos.value
  const strat = r.map((v, i) => v * p[i])
  return {
    cum: nav.value[nav.value.length - 1] - 1,
    annVol: std(strat.slice(1)) * Math.sqrt(252),
    meanReward: mean(strat),
  }
})
</script>

<template>
  <div class="rl-loop">
    <div v-if="loading" class="status">数据加载中…</div>
    <div v-else-if="error" class="status">数据不可用</div>
    <template v-else>
      <div class="switch">
        <button :class="['gbtn', { on: policy === 'momentum' }]" @click="policy = 'momentum'">动量（涨则买）</button>
        <button :class="['gbtn', { on: policy === 'contrarian' }]" @click="policy = 'contrarian'">反转（跌则买）</button>
        <button :class="['gbtn', { on: policy === 'random' }]" @click="policy = 'random'">随机</button>
      </div>
      <label class="lb">状态 = 过去 <input type="range" v-model.number="lookback" min="1" max="20" step="1" /> {{ lookback }} 日均收益（Lookback 越大「状态」越迟钝）</label>
      <div class="stats">
        <span class="chip">累计收益 <strong>{{ (stats.cum * 100).toFixed(1) }}%</strong></span>
        <span class="chip">策略波动 <strong>{{ (stats.annVol * 100).toFixed(1) }}%</strong></span>
        <span class="chip">日均奖励 <strong>{{ (stats.meanReward * 100).toFixed(2) }}%</strong></span>
      </div>
      <ThemedChart class="chart" :option="option" autoresize />
      <p class="note">RL 三要素演示（真实茅台 2024 日线，示意动作策略，非真实 RL 训练）：**状态**=过去 N 日均收益，**动作**=仓位（满仓/空仓），**奖励**=当日策略收益（仓位 × 当日涨跌）。切换动作策略看「不同策略 = 不同行为」如何导致不同净值；Lookback 滑块改变「状态」的敏感度。真实 RL 会用策略梯度在大量回合中学习 $\pi(a|s)$，本图只是把三要素的**循环**演示出来——理解这个循环，是理解 RL 在交易中一切应用的前提。</p>
    </template>
  </div>
</template>

<style scoped>
.rl-loop { padding: 16px; }
.status { height: 320px; display: flex; align-items: center; justify-content: center; color: var(--text-3); font-size: 14px; }
.chart { height: 380px; }
.switch { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 8px; }
.gbtn {
  font-size: 12.5px; padding: 4px 14px; border-radius: 999px; cursor: pointer;
  border: 1px solid var(--border, rgba(128,128,128,0.3)); background: transparent; color: var(--text-2);
}
.gbtn.on { background: var(--primary); color: #fff; border-color: var(--primary); }
.lb { display: flex; align-items: center; gap: 6px; font-size: 12.5px; color: var(--text-2); margin-bottom: 10px; }
.lb input[type='range'] { width: 80px; }
.stats { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
.chip {
  font-size: 12.5px; color: var(--text-3);
  padding: 4px 10px; border-radius: 999px; background: var(--bg-hover);
}
.chip strong { color: var(--primary); }
.note { font-size: 12.5px; color: var(--text-3); margin-top: 10px; line-height: 1.6; }
</style>
