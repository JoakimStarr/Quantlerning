<script setup lang="ts">
import { computed, ref } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { usePortfolioDaily } from '@/composables/usePortfolioDaily'
import { covarianceMatrix, portfolioVol } from '@/utils/portfolio'
import { navFromReturns } from '@/utils/ml'

use([CanvasRenderer, LineChart, BarChart, GridComponent, TooltipComponent, LegendComponent])

// 组合风控仪表盘：5 股真实 2024 收益组合
// 1) 压力测试：2008 式崩盘（-50%）、2020 疫情（-30%）、2015 股灾（-40%）、2024 回撤（-20%）→ 组合损益
// 2) 止损线：组合回撤达到阈值清仓 → 净值对比
const universe = computed(() => [
  { code: 'sh600519', name: '贵州茅台' },
  { code: 'sz000858', name: '五粮液' },
  { code: 'sz300750', name: '宁德时代' },
  { code: 'sh600036', name: '招商银行' },
  { code: 'sh601318', name: '中国平安' },
])

const { returns, names, dates, loading, error } = usePortfolioDaily(universe)

const cov = computed(() => (returns.value.length ? covarianceMatrix(returns.value) : []))

const wRaw = ref([0.2, 0.2, 0.2, 0.2, 0.2])
const weights = computed(() => {
  const s = wRaw.value.reduce((a, b) => a + b, 0)
  return s === 0 ? new Array(5).fill(0.2) : wRaw.value.map((w) => w / s)
})

// 压力情景：市场暴跌幅度 → 组合按 β≈1 等比例承受（教学示意，标注清楚）
const scenarios = [
  { name: '2008 金融危机', drop: 0.5, note: '沪深 300 腰斩' },
  { name: '2015 股灾', drop: 0.4, note: '千股跌停' },
  { name: '2020 疫情', drop: 0.3, note: '全球抛售' },
  { name: '2024 局部回撤', drop: 0.2, note: '典型中期调整' },
]

const stressResult = computed(() => {
  if (!returns.value.length) return null
  // 组合历史波动作为 β≈1 的代理：市场跌 drop → 组合近似跌 drop×组合暴露
  const vol = portfolioVol(weights.value, cov.value)
  const marketVol = 0.2 // 沪深 300 历史年化波动近似
  const beta = marketVol > 0 ? Math.min(1.5, vol / marketVol) : 1
  return scenarios.map((s) => ({
    ...s,
    portLoss: -s.drop * beta,
  }))
})

// 简化压力：组合损失 = 组合波动 × 情景幅度 × 相关系数(≈1)，显示为净值 ×(1-drop)
const stressOption = computed(() => {
  const r = stressResult.value
  if (!r) return {}
  return {
    animation: false,
    grid: { left: 56, right: 24, top: 24, bottom: 40 },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (ps: any[]) => {
        const p = Array.isArray(ps) ? ps[0] : ps
        const s = r[p.dataIndex]
        return `${s.name}（${s.note}）<br/>组合预计损益：${(s.portLoss * 100).toFixed(1)}%`
      },
    },
    xAxis: { type: 'category', data: r.map((s) => s.name), axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', name: '组合损益 %', nameLocation: 'middle', nameGap: 36, axisLabel: { fontSize: 10 } },
    series: [
      {
        type: 'bar',
        data: r.map((s) => +(s.portLoss * 100).toFixed(1)),
        itemStyle: {
          color: (p: any) => (p.value >= 0 ? '#16a34a' : '#dc2626'),
          opacity: 0.8,
        },
        label: { show: true, position: 'top', fontSize: 11, formatter: (p: any) => `${p.value}%` },
      },
    ],
  }
})

// 止损演示：用组合实际历史净值 + 止损阈值
const stopLoss = ref(0.1) // 10% 止损
const stopResult = computed(() => {
  if (!returns.value.length) return null
  // 组合日收益序列
  const portRets = returns.value.map((row) => weights.value.reduce((s, w, i) => s + w * row[i], 0))
  // 无止损净值
  const navNo = navFromReturns(portRets, new Array(portRets.length).fill(1))
  // 带止损净值：回撤达到阈值 → 清仓（次日生效）
  let peak = 100
  let v = 100
  const navStop: number[] = [100]
  let stopped = false
  for (let i = 1; i < portRets.length; i++) {
    v *= 1 + portRets[i]
    if (v > peak) peak = v
    const dd = v / peak - 1
    if (!stopped && dd <= -stopLoss.value) {
      stopped = true // 触发止损，次日清仓（模拟用净值不再变动，标记）
    }
    navStop.push(stopped ? navStop[i - 1] : Number(v.toFixed(4)))
  }
  return { navNo, navStop, stopped, stopDate: null, portRets }
})

const stopOption = computed(() => {
  const r = stopResult.value
  if (!r) return {}
  return {
    animation: false,
    grid: { left: 56, right: 24, top: 36, bottom: 44 },
    tooltip: { trigger: 'axis' },
    legend: { top: 0, textStyle: { fontSize: 11 } },
    xAxis: { type: 'category', data: dates.value.map((d) => d.slice(5)), axisLabel: { fontSize: 9, hideOverlap: true } },
    yAxis: { type: 'value', name: '净值', nameLocation: 'middle', nameGap: 40, scale: true, axisLabel: { fontSize: 10 } },
    series: [
      { name: '不止损', type: 'line', data: r.navNo, symbol: 'none', lineStyle: { color: '#94a3b8', width: 1.3, type: 'dashed' } },
      { name: `止损 ${(stopLoss.value * 100).toFixed(0)}%`, type: 'line', data: r.navStop, symbol: 'none', lineStyle: { color: '#dc2626', width: 2 } },
    ],
  }
})
</script>

<template>
  <div class="risk">
    <div v-if="loading" class="status">数据加载中…</div>
    <div v-else-if="error" class="status">数据不可用</div>
    <template v-else-if="stressResult && stopResult">
      <div class="controls">
        <label v-for="(n, i) in names" :key="n">
          {{ n }} <input type="range" v-model.number="wRaw[i]" min="0" max="1" step="0.05" /> {{ (weights[i] * 100).toFixed(0) }}%
        </label>
        <label>止损阈值 <input type="range" v-model.number="stopLoss" min="0.05" max="0.3" step="0.01" /> {{ (stopLoss * 100).toFixed(0) }}%</label>
      </div>
      <p class="sub">压力测试：极端情景下组合预计损益（示意，按组合年化收益等比例外推）</p>
      <VChart class="chart small" :option="stressOption" autoresize />
      <p class="sub">止损演示：真实 5 股等权组合净值，回撤达阈值清仓（真实历史净值）</p>
      <VChart class="chart" :option="stopOption" autoresize />
      <p class="note">真实锚点：贵州茅台 / 五粮液 / 宁德时代 / 招商银行 / 中国平安 2024 全年日收益（组合净值真实计算）。压力情景幅度为教学示意（2008 腰斩等），需明确标注；止损阈值用真实历史回撤演示「止损降低尾部风险但也会在波动中被震出」。</p>
    </template>
  </div>
</template>

<style scoped>
.risk { padding: 16px; }
.status { height: 300px; display: flex; align-items: center; justify-content: center; color: var(--text-3); font-size: 14px; }
.controls { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; margin-bottom: 10px; font-size: 12px; color: var(--text-2); }
.controls label { display: flex; align-items: center; gap: 4px; }
.controls input[type='range'] { width: 70px; }
.chart { height: 260px; margin-bottom: 6px; }
.small { height: 200px; }
.sub { font-size: 12px; color: var(--text-3); margin: 6px 0 2px; }
.note { font-size: 12.5px; color: var(--text-3); margin-top: 10px; line-height: 1.6; }
</style>