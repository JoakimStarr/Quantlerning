<script setup lang="ts">
// 组合 VaR：相关性如何决定分散化收益（真实 5 股 2024 日收益）
// 教学点：① 组合参数法 VaR 中交叉项 ρ 是分散化的唯一来源（ρ<1 才低于加权平均）；
//        ② 历史法直接取组合逐日收益分位，无需公式；两法结果依然不同（尾部假设）；
//        ③ 权重越均衡、相关性越低，组合 VaR 相对单资产下降越多。
import { computed, ref } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { usePortfolioDaily } from '@/composables/usePortfolioDaily'
import { correlationMatrix, covarianceMatrix } from '@/utils/portfolio'

use([CanvasRenderer, BarChart, GridComponent, TooltipComponent, LegendComponent])

const universe = computed(() => [
  { code: 'sh600519', name: '贵州茅台' },
  { code: 'sz000858', name: '五粮液' },
  { code: 'sz300750', name: '宁德时代' },
  { code: 'sh600036', name: '招商银行' },
  { code: 'sh601318', name: '中国平安' },
])

const { returns, names, loading, error } = usePortfolioDaily(universe)

const Z = 1.645 // 95% 左尾分位数
const conf = 0.95

// 与茅台配对的资产 B（索引 1..4，默认宁德时代——跨行业相关性低，分散化效果明显）
const bIdx = ref(2)
const pairButtons = computed(() => names.value.slice(1).map((n, i) => ({ name: n, idx: i + 1 })))
const wA = ref(0.5) // 茅台权重

// 取百分数收益序列（与 VarSimulator 口径一致：去掉首日）
// w=茅台权重；B=配对资产列索引
function weightedSeries(B: number, w: number): number[] {
  const rows = returns.value
  if (!rows.length) return []
  return rows.slice(1).map((r) => (w * r[0] + (1 - w) * r[B]) * 100)
}

function muSd(vals: number[]): { mu: number; sd: number } {
  const n = vals.length
  const mu = vals.reduce((s, v) => s + v, 0) / n
  const sd = Math.sqrt(vals.reduce((s, v) => s + (v - mu) ** 2, 0) / (n - 1))
  return { mu, sd }
}

/** 历史法 VaR（与 p5-l6 锚点同口径） */
function histVaR(vals: number[]): number {
  const sorted = [...vals].sort((a, b) => a - b)
  const q = Math.max(0, Math.floor((1 - conf) * sorted.length) - 1)
  return sorted[q]
}

const analysis = computed(() => {
  if (!returns.value.length) return null
  const B = bIdx.value
  const rA = weightedSeries(B, 1) // w=1 → 茅台自身
  const rB = weightedSeries(B, 0) // w=0 → B 自身
  const rP = weightedSeries(B, wA.value)
  const A = muSd(rA)
  const Bm = muSd(rB)
  const P = muSd(rP)
  // 真实相关系数（茅台 vs B）
  const cov = covarianceMatrix(returns.value)
  const corr = correlationMatrix(cov)
  const rho = corr[0][B]

  // 输出损失幅度（正值）
  const mag = (v: number) => Math.max(0, -v)
  const histA = histVaR(rA)
  const histB = histVaR(rB)
  const histP = histVaR(rP)
  const paramA = A.mu - Z * A.sd
  const paramB = Bm.mu - Z * Bm.sd
  const paramP = P.mu - Z * P.sd
  const naiveHist = wA.value * mag(histA) + (1 - wA.value) * mag(histB)
  const benefit = naiveHist - mag(histP)

  return {
    nameA: names.value[0],
    nameB: names.value[B],
    rho,
    histA,
    histB,
    histP,
    paramA,
    paramB,
    paramP,
    magHistA: mag(histA),
    magHistB: mag(histB),
    magHistP: mag(histP),
    magParamA: mag(paramA),
    magParamB: mag(paramB),
    magParamP: mag(paramP),
    naiveHist,
    benefit,
  }
})

const option = computed(() => {
  const a = analysis.value
  if (!a) return {}
  const wPct = Math.round(wA.value * 100)
  const categories = [a.nameA, a.nameB, `组合（${wPct}/${100 - wPct}）`]
  const histVals = [a.magHistA, a.magHistB, a.magHistP]
  const paramVals = [a.magParamA, a.magParamB, a.magParamP]
  return {
    animation: false,
    grid: { left: 56, right: 24, top: 40, bottom: 36 },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { top: 0, textStyle: { fontSize: 11 } },
    xAxis: { type: 'category', data: categories, axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', name: '95% VaR 损失 %', nameLocation: 'middle', nameGap: 44, axisLabel: { fontSize: 10 } },
    series: [
      {
        name: '历史法（真实分位）',
        type: 'bar',
        barGap: '20%',
        data: histVals.map((v) => +v.toFixed(2)),
        itemStyle: { color: C.value.primary, opacity: 0.85 },
      },
      {
        name: '参数法（正态）',
        type: 'bar',
        data: paramVals.map((v) => +v.toFixed(2)),
        itemStyle: { color: C.value.cyan, opacity: 0.7 },
      },
    ],
  }
})
</script>

<template>
  <div class="portfolio-var">
    <div v-if="loading" class="status">数据加载中…</div>
    <div v-else-if="error" class="status">数据不可用</div>
    <template v-else-if="analysis">
      <div class="controls">
        <div class="group">
          <button
            v-for="b in pairButtons"
            :key="b.idx"
            :class="['gbtn', { on: bIdx === b.idx }]"
            @click="bIdx = b.idx"
          >
            {{ b.name }}
          </button>
        </div>
        <label>茅台权重 <input type="range" v-model.number="wA" min="0" max="1" step="0.05" /> {{ Math.round(wA * 100) }}%</label>
      </div>
      <div class="stats">
        <span class="chip">真实相关 ρ = <strong>{{ analysis.rho.toFixed(2) }}</strong></span>
        <span class="chip">组合 VaR（历史）<strong>{{ analysis.magHistP.toFixed(2) }}%</strong></span>
        <span class="chip">加权平均（历史）<strong>{{ analysis.naiveHist.toFixed(2) }}%</strong></span>
        <span class="chip">分散化收益 <strong>{{ analysis.benefit.toFixed(2) }}pp</strong></span>
      </div>
      <ThemedChart class="chart" :option="option" autoresize />
      <p class="note">真实数据：茅台/五粮液/宁德时代/招商银行/中国平安 2024 日收益（242 交易日，复权口径）。历史法柱子矮于对应参数法柱子（茅台与 p5-l6 锚点一致：-2.42% vs -2.87%）。切换 B 或拖权重看组合柱高变化——分散化收益 = 加权平均 − 组合 VaR，主要来自 ρ&lt;1。</p>
    </template>
  </div>
</template>

<style scoped>
.portfolio-var { padding: 16px; }
.status { height: 300px; display: flex; align-items: center; justify-content: center; color: var(--text-3); font-size: 14px; }
.chart { height: 320px; }
.controls { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; margin-bottom: 10px; font-size: 12.5px; color: var(--text-2); }
.controls .group { display: flex; gap: 4px; flex-wrap: wrap; }
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
