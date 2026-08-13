<script setup lang="ts">
import { computed, ref } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, ScatterChart, BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, MarkLineComponent } from 'echarts/components'
import { usePortfolioDaily } from '@/composables/usePortfolioDaily'
import { cointegrationTest, pairTradingSignal, spreadNav } from '@/utils/portfolio'
import { mlxStats } from '@/utils/ml'

use([CanvasRenderer, LineChart, ScatterChart, BarChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent])

// 配对交易：真实 A 股对数价格回归 + 残差 ADF 协整检验 + 价差 z-score 均值回归信号
// 真实配对：招商银行-兴业银行（ADF -3.62）、贵州茅台-泸州老窖（ADF -3.14）
// 对照：贵州茅台-五粮液（不协整，教学点）
type PairKey = 'pa_cmb' | 'mt_lj' | 'mt_wly'

const PAIRS: Record<PairKey, { a: { code: string; name: string }; b: { code: string; name: string }; label: string }> = {
  pa_cmb: { a: { code: 'sh600036', name: '招商银行' }, b: { code: 'sh601166', name: '兴业银行' }, label: '银行股（协整，ADF≈-3.6）' },
  mt_lj: { a: { code: 'sh600519', name: '贵州茅台' }, b: { code: 'sz000568', name: '泸州老窖' }, label: '白酒（协整，ADF≈-3.1）' },
  mt_wly: { a: { code: 'sh600519', name: '贵州茅台' }, b: { code: 'sz000858', name: '五粮液' }, label: '白酒（不协整，对照）' },
}

const pair = ref<PairKey>('pa_cmb')
const universe = computed(() => {
  const p = PAIRS[pair.value]
  return [p.a, p.b]
})

const { dates, returns, closes, loading, error } = usePortfolioDaily(universe, '2023-01-01', '2024-12-31')

const entry = ref(1.5) // 开仓阈值（z-score）
const exit = ref(0.5) // 平仓阈值

const analysis = computed(() => {
  if (!closes.value.length) return null
  // 转成时间序列 [t][stock]
  const p1 = closes.value.map((row) => row[0]).filter((v) => !isNaN(v))
  const p2 = closes.value.map((row) => row[1]).filter((v) => !isNaN(v))
  const n = Math.min(p1.length, p2.length)
  const ci = cointegrationTest(p1.slice(0, n), p2.slice(0, n))
  const sig = pairTradingSignal(ci.zscore, entry.value, exit.value)
  const r1 = returns.value.slice(0, n).map((row) => row[0])
  const r2 = returns.value.slice(0, n).map((row) => row[1])
  const spreadRet = r1.map((v, i) => r2[i] - ci.beta * v)
  const nav = spreadNav(r1, r2, ci.beta, sig)
  const bhNav = spreadNav(r1, r2, ci.beta, new Array(n).fill(1))
  const stats = mlxStats(spreadRet, sig)
  return { ...ci, sig, nav, bhNav, stats, dates: dates.value.slice(0, n) }
})

const spreadOption = computed(() => {
  const a = analysis.value
  if (!a) return {}
  // 开仓/平仓标记
  const longOpen = a.zscore.map((z, i) => (i > 0 && a.sig[i] === 1 && a.sig[i - 1] !== 1 ? [i, z] : null)).filter(Boolean) as any
  const shortOpen = a.zscore.map((z, i) => (i > 0 && a.sig[i] === -1 && a.sig[i - 1] !== -1 ? [i, z] : null)).filter(Boolean) as any
  return {
    animation: false,
    grid: { left: 56, right: 24, top: 36, bottom: 44 },
    tooltip: { trigger: 'axis' },
    legend: { top: 0, textStyle: { fontSize: 11 } },
    xAxis: { type: 'category', data: a.dates.map((d) => d.slice(5)), axisLabel: { fontSize: 9, hideOverlap: true } },
    yAxis: { type: 'value', name: '价差 z-score', nameLocation: 'middle', nameGap: 40, axisLabel: { fontSize: 10 } },
    series: [
      {
        name: '标准化价差',
        type: 'line',
        data: a.zscore.map((z) => +z.toFixed(2)),
        symbol: 'none',
        lineStyle: { color: C.value.primary, width: 1.4 },
        markLine: {
          silent: true,
          symbol: 'none',
          data: [
            { yAxis: entry.value, label: { formatter: `+${entry.value}σ 开仓`, position: 'insideEndTop' }, lineStyle: { color: C.value.danger, type: 'dashed' } },
            { yAxis: -entry.value, label: { formatter: `-${entry.value}σ 开仓`, position: 'insideEndTop' }, lineStyle: { color: C.value.success, type: 'dashed' } },
            { yAxis: exit.value, lineStyle: { color: C.value.slate, type: 'dotted' } },
            { yAxis: -exit.value, lineStyle: { color: C.value.slate, type: 'dotted' } },
          ],
        },
      },
      { name: '做多价差开仓', type: 'scatter', data: longOpen, symbolSize: 10, itemStyle: { color: C.value.success } },
      { name: '做空价差开仓', type: 'scatter', data: shortOpen, symbolSize: 10, itemStyle: { color: C.value.danger } },
    ],
  }
})

const navOption = computed(() => {
  const a = analysis.value
  if (!a) return {}
  return {
    animation: false,
    grid: { left: 56, right: 24, top: 36, bottom: 44 },
    tooltip: { trigger: 'axis' },
    legend: { top: 0, textStyle: { fontSize: 11 } },
    xAxis: { type: 'category', data: a.dates.map((d) => d.slice(5)), axisLabel: { fontSize: 9, hideOverlap: true } },
    yAxis: { type: 'value', name: '净值', nameLocation: 'middle', nameGap: 40, scale: true, axisLabel: { fontSize: 10 } },
    series: [
      { name: '价差策略', type: 'line', data: a.nav, symbol: 'none', lineStyle: { color: C.value.primary, width: 2 } },
      { name: '价差买入持有', type: 'line', data: a.bhNav, symbol: 'none', lineStyle: { color: C.value.slate, width: 1.3, type: 'dashed' } },
    ],
  }
})
</script>

<template>
  <div class="pair">
    <div v-if="loading" class="status">数据加载中…</div>
    <div v-else-if="error" class="status">数据不可用</div>
    <template v-else-if="analysis">
      <div class="controls">
        <label>配对
          <select v-model="pair">
            <option v-for="(p, k) in PAIRS" :key="k" :value="k">{{ p.a.name }} - {{ p.b.name }}（{{ p.label }}）</option>
          </select>
        </label>
        <label>开仓阈值 <input type="range" v-model.number="entry" min="1" max="3" step="0.1" /> {{ entry.toFixed(1) }}σ</label>
        <label>平仓阈值 <input type="range" v-model.number="exit" min="0" max="1" step="0.1" /> {{ exit.toFixed(1) }}σ</label>
      </div>
      <div class="stats">
        <span class="chip">ADF t = <strong>{{ analysis.adf.toFixed(2) }}</strong>（5% 临界 {{ analysis.critical5 }}）</span>
        <span class="chip">{{ analysis.cointegrated ? '✅ 协整' : '❌ 不协整' }}</span>
        <span class="chip">β = <strong>{{ analysis.beta.toFixed(2) }}</strong></span>
        <span class="chip">策略年化 <strong>{{ (analysis.stats.ann * 100).toFixed(1) }}%</strong></span>
        <span class="chip">夏普 <strong>{{ analysis.stats.sharpe.toFixed(2) }}</strong></span>
      </div>
      <p class="sub">标准化价差（回归残差）+ 阈值开仓信号</p>
      <ThemedChart class="chart" :option="spreadOption" autoresize />
      <p class="sub">价差策略净值（做多/做空价差，信号次日生效）vs 买入持有价差</p>
      <ThemedChart class="chart" :option="navOption" autoresize />
      <p class="note">真实锚点：招商银行-兴业银行（协整）、贵州茅台-泸州老窖（协整）、贵州茅台-五粮液（不协整对照）2023-2024 日线。教学点：配对交易前提是协整（价差平稳，均值回归），不协整的配对会让价差漂移，策略失效。ADF 检验是第一步。</p>
    </template>
  </div>
</template>

<style scoped>
.pair { padding: 16px; }
.status { height: 300px; display: flex; align-items: center; justify-content: center; color: var(--text-3); font-size: 14px; }
.controls { display: flex; gap: 14px; flex-wrap: wrap; align-items: center; margin-bottom: 10px; font-size: 12.5px; color: var(--text-2); }
.controls label { display: flex; align-items: center; gap: 6px; }
.controls select { padding: 3px 6px; border: 1px solid var(--border); border-radius: 6px; background: var(--bg-card); color: var(--text-2); font-size: 12px; max-width: 320px; }
.controls input[type='range'] { width: 100px; }
.chart { height: 260px; margin-bottom: 6px; }
.stats { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
.chip {
  font-size: 12.5px; color: var(--text-3);
  padding: 4px 10px; border-radius: 999px; background: var(--bg-hover);
}
.chip strong { color: var(--primary); }
.sub { font-size: 12px; color: var(--text-3); margin: 6px 0 2px; }
.note { font-size: 12.5px; color: var(--text-3); margin-top: 10px; line-height: 1.6; }
</style>