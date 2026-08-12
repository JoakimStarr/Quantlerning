<script setup lang="ts">
import { computed, ref } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { ScatterChart, LineChart, BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, MarkLineComponent } from 'echarts/components'
import { usePortfolioDaily } from '@/composables/usePortfolioDaily'
import { covarianceMatrix, annualReturns, annualVols, efficientFrontier, portfolioReturn, portfolioVol, portfolioSharpe, minVariancePortfolio, maxSharpePortfolio } from '@/utils/portfolio'

use([CanvasRenderer, ScatterChart, LineChart, BarChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent])

// 马科维茨有效前沿：5 只真实 A 股 2024 收益 → 风险-收益平面
// 教学点：分散化「免费午餐」——前沿左上沿优于单个资产；权重滑块看组合在平面上的位置
const universe = computed(() => [
  { code: 'sh600519', name: '贵州茅台' },
  { code: 'sz000858', name: '五粮液' },
  { code: 'sz300750', name: '宁德时代' },
  { code: 'sh600036', name: '招商银行' },
  { code: 'sh601318', name: '中国平安' },
])

const { returns, names, loading, error } = usePortfolioDaily(universe)

const annRets = computed(() => (returns.value.length ? annualReturns(returns.value) : []))
const cov = computed(() => (returns.value.length ? covarianceMatrix(returns.value) : []))
const vols = computed(() => (cov.value.length ? annualVols(cov.value) : []))
const frontier = computed(() => (annRets.value.length ? efficientFrontier(annRets.value, cov.value) : []))
const minVar = computed(() => (cov.value.length ? minVariancePortfolio(cov.value) : []))
const maxS = computed(() => (annRets.value.length ? maxSharpePortfolio(annRets.value, cov.value) : []))

// 用户权重滑块（归一化）
const wRaw = ref([0.2, 0.2, 0.2, 0.2, 0.2])
const weights = computed(() => {
  const s = wRaw.value.reduce((a, b) => a + b, 0)
  return s === 0 ? new Array(5).fill(0.2) : wRaw.value.map((w) => w / s)
})

const curPort = computed(() => {
  if (!annRets.value.length) return null
  return {
    ret: portfolioReturn(weights.value, annRets.value),
    vol: portfolioVol(weights.value, cov.value),
    sharpe: portfolioSharpe(weights.value, annRets.value, cov.value),
  }
})

const scatterOption = computed(() => {
  if (!annRets.value.length) return {}
  const single = names.value.map((_, i) => [vols.value[i] * 100, annRets.value[i] * 100])
  const frontierPts = frontier.value.map((p) => [+(p.vol * 100).toFixed(2), +(p.ret * 100).toFixed(2)])
  const mv = minVar.value
  const ms = maxS.value
  const mvPt = [portfolioVol(mv, cov.value) * 100, portfolioReturn(mv, annRets.value) * 100]
  const msPt = [portfolioVol(ms, cov.value) * 100, portfolioReturn(ms, annRets.value) * 100]
  return {
    animation: false,
    grid: { left: 56, right: 24, top: 36, bottom: 44 },
    tooltip: {
      trigger: 'item',
      formatter: (p: any) => {
        if (p.seriesType === 'scatter') return `${p.name}<br/>波动：${p.value[0].toFixed(1)}%<br/>年化：${p.value[1].toFixed(1)}%`
        return `${p.name}<br/>波动：${p.value[0].toFixed(1)}%<br/>年化：${p.value[1].toFixed(1)}%`
      },
    },
    legend: { top: 0, textStyle: { fontSize: 11 } },
    xAxis: { type: 'value', name: '年化波动 %', nameLocation: 'middle', nameGap: 28, axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', name: '年化收益 %', nameLocation: 'middle', nameGap: 34, axisLabel: { fontSize: 10 } },
    series: [
      {
        name: '有效前沿',
        type: 'line',
        data: frontierPts,
        symbol: 'none',
        lineStyle: { color: '#2563eb', width: 2 },
        areaStyle: { color: 'rgba(37,99,235,0.06)' },
      },
      {
        name: '个股',
        type: 'scatter',
        data: single,
        symbolSize: 10,
        itemStyle: { color: '#64748b' },
        label: { show: true, position: 'top', fontSize: 10, formatter: (p: any) => names.value[p.dataIndex] },
      },
      {
        name: '最小方差',
        type: 'scatter',
        data: [mvPt.map((v) => +v.toFixed(2))],
        symbolSize: 12,
        itemStyle: { color: '#16a34a' },
      },
      {
        name: '最大夏普',
        type: 'scatter',
        data: [msPt.map((v) => +v.toFixed(2))],
        symbolSize: 12,
        itemStyle: { color: '#d97706' },
      },
      {
        name: '当前组合',
        type: 'scatter',
        data: curPort.value ? [[+(curPort.value.vol * 100).toFixed(2), +(curPort.value.ret * 100).toFixed(2)]] : [],
        symbolSize: 14,
        itemStyle: { color: '#dc2626', borderColor: '#fff', borderWidth: 2 },
      },
    ],
  }
})

const weightOption = computed(() => ({
  animation: false,
  grid: { left: 56, right: 24, top: 24, bottom: 40 },
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
  xAxis: { type: 'category', data: names.value, axisLabel: { fontSize: 10 } },
  yAxis: { type: 'value', name: '权重', nameLocation: 'middle', nameGap: 34, max: 1, axisLabel: { fontSize: 10 } },
  series: [
    {
      type: 'bar',
      data: weights.value.map((w) => +w.toFixed(3)),
      itemStyle: { color: '#2563eb', opacity: 0.75 },
      label: { show: true, position: 'top', fontSize: 10, formatter: (p: any) => `${(p.value * 100).toFixed(0)}%` },
    },
  ],
}))
</script>

<template>
  <div class="frontier">
    <div v-if="loading" class="status">数据加载中…</div>
    <div v-else-if="error" class="status">数据不可用</div>
    <template v-else-if="annRets.length && curPort">
      <div class="controls">
        <label v-for="(n, i) in names" :key="n">
          {{ n }} <input type="range" v-model.number="wRaw[i]" min="0" max="1" step="0.05" /> {{ (weights[i] * 100).toFixed(0) }}%
        </label>
      </div>
      <div class="stats">
        <span class="chip">年化 <strong>{{ (curPort.ret * 100).toFixed(1) }}%</strong></span>
        <span class="chip">波动 <strong>{{ (curPort.vol * 100).toFixed(1) }}%</strong></span>
        <span class="chip">夏普 <strong>{{ curPort.sharpe.toFixed(2) }}</strong></span>
      </div>
      <p class="sub">有效前沿（真实 5 股 2024 收益）：蓝线 = 前沿，红点 = 当前组合，绿 = 最小方差，橙 = 最大夏普</p>
      <VChart class="chart" :option="scatterOption" autoresize />
      <p class="sub">当前权重</p>
      <VChart class="chart small" :option="weightOption" autoresize />
      <p class="note">真实锚点：贵州茅台 / 五粮液 / 宁德时代 / 招商银行 / 中国平安 2024 全年日收益（242 交易日）。教学点：前沿左上沿优于所有个股——分散化是「免费午餐」；拖动权重看组合沿前沿移动。</p>
    </template>
  </div>
</template>

<style scoped>
.frontier { padding: 16px; }
.status { height: 300px; display: flex; align-items: center; justify-content: center; color: var(--text-3); font-size: 14px; }
.controls { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; margin-bottom: 10px; font-size: 12px; color: var(--text-2); }
.controls label { display: flex; align-items: center; gap: 4px; }
.controls input[type='range'] { width: 70px; }
.chart { height: 320px; margin-bottom: 6px; }
.small { height: 160px; }
.stats { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
.chip {
  font-size: 12.5px; color: var(--text-3);
  padding: 4px 10px; border-radius: 999px; background: var(--bg-hover);
}
.chip strong { color: var(--primary); }
.sub { font-size: 12px; color: var(--text-3); margin: 6px 0 2px; }
.note { font-size: 12.5px; color: var(--text-3); margin-top: 10px; line-height: 1.6; }
</style>