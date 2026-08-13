<script setup lang="ts">
import { computed, ref } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { usePortfolioDaily } from '@/composables/usePortfolioDaily'
import { covarianceMatrix, annualReturns, annualVols, portfolioReturn, portfolioVol, riskParityWeights, riskContributions } from '@/utils/portfolio'

use([CanvasRenderer, BarChart, LineChart, GridComponent, TooltipComponent, LegendComponent])

// 风险平价：波动率平价配置 vs 等权 vs 最小方差
// 教学点：风险平价让每个资产对组合风险贡献相等；对比等权看「风险集中在高波动资产」的隐患
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

const eqW = computed(() => new Array(names.value.length).fill(1 / names.value.length))
const rpW = computed(() => (cov.value.length ? riskParityWeights(cov.value) : []))
const invW = computed(() => {
  // 波动率倒数加权（接近风险平价，教学对照）
  if (!vols.value.length) return []
  const inv = vols.value.map((v) => (v > 0 ? 1 / v : 0))
  const s = inv.reduce((a, b) => a + b, 0)
  return inv.map((x) => x / s)
})

type Method = 'equal' | 'parity' | 'inverse'
const method = ref<Method>('parity')

const current = computed(() => {
  if (!annRets.value.length) return null
  const w = method.value === 'equal' ? eqW.value : method.value === 'parity' ? rpW.value : invW.value
  return {
    w,
    ret: portfolioReturn(w, annRets.value),
    vol: portfolioVol(w, cov.value),
    rc: riskContributions(w, cov.value),
  }
})

const weightOption = computed(() => {
  if (!current.value) return {}
  return {
    animation: false,
    grid: { left: 56, right: 24, top: 24, bottom: 40 },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    xAxis: { type: 'category', data: names.value, axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', name: '权重', nameLocation: 'middle', nameGap: 34, max: 1, axisLabel: { fontSize: 10 } },
    series: [
      {
        type: 'bar',
        data: current.value.w.map((w) => +w.toFixed(3)),
        itemStyle: { color: C.value.primary, opacity: 0.75 },
        label: { show: true, position: 'top', fontSize: 10, formatter: (p: any) => `${(p.value * 100).toFixed(0)}%` },
      },
    ],
  }
})

const rcOption = computed(() => {
  if (!current.value) return {}
  return {
    animation: false,
    grid: { left: 56, right: 24, top: 24, bottom: 40 },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    xAxis: { type: 'category', data: names.value, axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', name: '风险贡献', nameLocation: 'middle', nameGap: 34, axisLabel: { fontSize: 10 } },
    series: [
      {
        type: 'bar',
        data: current.value.rc.map((v) => +v.toFixed(3)),
        itemStyle: { color: C.value.warning, opacity: 0.8 },
        label: { show: true, position: 'top', fontSize: 10, formatter: (p: any) => `${(p.value * 100).toFixed(0)}%` },
      },
    ],
  }
})

const compareOption = computed(() => {
  if (!annRets.value.length) return {}
  const labels = ['等权', '风险平价', '倒数波动加权']
  const wList = [eqW.value, rpW.value, invW.value]
  return {
    animation: false,
    grid: { left: 56, right: 24, top: 24, bottom: 40 },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { top: 0, textStyle: { fontSize: 11 } },
    xAxis: { type: 'category', data: labels, axisLabel: { fontSize: 11 } },
    yAxis: { type: 'value', name: '年化波动 %', nameLocation: 'middle', nameGap: 36, axisLabel: { fontSize: 10 } },
    series: [
      {
        name: '组合波动',
        type: 'bar',
        data: wList.map((w) => +(portfolioVol(w, cov.value) * 100).toFixed(1)),
        itemStyle: { color: C.value.danger, opacity: 0.8 },
        label: { show: true, position: 'top', fontSize: 10, formatter: (p: any) => `${p.value}%` },
      },
    ],
  }
})
</script>

<template>
  <div class="risk-parity">
    <div v-if="loading" class="status">数据加载中…</div>
    <div v-else-if="error" class="status">数据不可用</div>
    <template v-else-if="current">
      <div class="controls">
        <span class="mode-label">配置方法</span>
        <select v-model="method">
          <option value="parity">风险平价</option>
          <option value="equal">等权</option>
          <option value="inverse">倒数波动加权</option>
        </select>
      </div>
      <div class="stats">
        <span class="chip">组合年化 <strong>{{ (current.ret * 100).toFixed(1) }}%</strong></span>
        <span class="chip">组合波动 <strong>{{ (current.vol * 100).toFixed(1) }}%</strong></span>
        <span class="chip note">夏普(rf=2%) <strong>{{ ((current.ret - 0.02) / current.vol).toFixed(2) }}</strong></span>
      </div>
      <p class="sub">当前权重</p>
      <ThemedChart class="chart small" :option="weightOption" autoresize />
      <p class="sub">各资产对组合的风险贡献（风险平价 → 各柱接近等高）</p>
      <ThemedChart class="chart small" :option="rcOption" autoresize />
      <p class="sub">三种方法组合波动对比</p>
      <ThemedChart class="chart small" :option="compareOption" autoresize />
      <p class="note">真实锚点：贵州茅台 / 五粮液 / 宁德时代 / 招商银行 / 中国平安 2024 全年日收益。教学点：宁德时代波动高（46%），等权时它贡献了大部分风险；风险平价降低它的权重，让每个资产风险贡献均衡——不预测收益，只看波动与相关性。</p>
    </template>
  </div>
</template>

<style scoped>
.risk-parity { padding: 16px; }
.status { height: 300px; display: flex; align-items: center; justify-content: center; color: var(--text-3); font-size: 14px; }
.controls { display: flex; gap: 10px; align-items: center; margin-bottom: 10px; font-size: 12.5px; color: var(--text-2); }
.controls select { padding: 3px 6px; border: 1px solid var(--border); border-radius: 6px; background: var(--bg-card); color: var(--text-2); font-size: 12px; }
.mode-label { color: var(--text-3); }
.chart { height: 200px; margin-bottom: 6px; }
.small { height: 180px; }
.stats { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
.chip {
  font-size: 12.5px; color: var(--text-3);
  padding: 4px 10px; border-radius: 999px; background: var(--bg-hover);
}
.chip strong { color: var(--primary); }
.chip.note { background: var(--primary-soft); color: var(--text-2); }
.sub { font-size: 12px; color: var(--text-3); margin: 6px 0 2px; }
.note { font-size: 12.5px; color: var(--text-3); margin-top: 10px; line-height: 1.6; }
</style>