<script setup lang="ts">
import { computed, ref } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C, withAlpha } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { ScatterChart, LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, MarkLineComponent } from 'echarts/components'

use([CanvasRenderer, ScatterChart, LineChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent])

// 资产风险-收益地图（教学示意）：横轴年化波动率（风险），纵轴年化收益率。
// 单一股票点用第一章主线真实锚点（茅台 2024：年化波动 27.55%、年化收益 -6.51%），
// 其余资产为长期经验的典型区间（正文 caption 已注明教学示意）。
// 股债组合线：σp = √(w²σs²+(1-w)²σb²+2w(1-w)ρσsσb)，ρ 固定 0.2（第七章会放宽）。

const STOCK = { sigma: 22, mu: 7 }   // 宽基股票基金（沪深300 长期经验区间）
const BOND = { sigma: 3, mu: 3 }     // 债券（国债/高等级信用债）
const RHO = 0.2

const w = ref(40) // 股票比例 %

const assets = computed(() => [
  { name: '现金/货基', sigma: 0.5, mu: 2, color: C.value.slate, symbol: 'circle' },
  { name: '债券', sigma: BOND.sigma, mu: BOND.mu, color: C.value.teal, symbol: 'circle' },
  { name: '股票基金(宽基)', sigma: STOCK.sigma, mu: STOCK.mu, color: C.value.primary, symbol: 'circle' },
  { name: '单一股票(茅台24)', sigma: 27.55, mu: -6.51, color: C.value.danger, symbol: 'diamond' },
  { name: '衍生品(示意)', sigma: 60, mu: 10, color: C.value.violet, symbol: 'triangle' },
])

const port = computed(() => {
  const ws = w.value / 100
  const mu = ws * STOCK.mu + (1 - ws) * BOND.mu
  const varP = ws * ws * STOCK.sigma ** 2 + (1 - ws) ** 2 * BOND.sigma ** 2
    + 2 * ws * (1 - ws) * RHO * STOCK.sigma * BOND.sigma
  const sigma = Math.sqrt(varP)
  // 不分散的 naive 波动：两资产波动的加权平均（对比出分散化红利）
  const naiveSigma = ws * STOCK.sigma + (1 - ws) * BOND.sigma
  return { mu, sigma, naiveSigma, bonus: naiveSigma - sigma }
})

// 组合线：股票比例 0→100% 扫描
const frontier = computed(() => {
  const pts: [number, number][] = []
  for (let i = 0; i <= 100; i += 5) {
    const ws = i / 100
    const mu = ws * STOCK.mu + (1 - ws) * BOND.mu
    const sigma = Math.sqrt(
      ws * ws * STOCK.sigma ** 2 + (1 - ws) ** 2 * BOND.sigma ** 2
      + 2 * ws * (1 - ws) * RHO * STOCK.sigma * BOND.sigma,
    )
    pts.push([Number(sigma.toFixed(2)), Number(mu.toFixed(2))])
  }
  return pts
})

const option = computed(() => ({
  animation: true,
  grid: { left: 56, right: 30, top: 40, bottom: 48 },
  tooltip: {
    trigger: 'item',
    formatter: (p: any) => {
      const v = Array.isArray(p.value) ? p.value : [p.value, 0]
      return `${p.seriesName === '资产' ? p.data.name : p.seriesName}<br/>波动率 ${Number(v[0]).toFixed(1)}%　收益 ${Number(v[1]).toFixed(1)}%`
    },
  },
  legend: {
    top: 4,
    textStyle: { fontSize: 12 },
    data: ['股债组合线(ρ=0.2)', '当前组合'],
  },
  xAxis: {
    type: 'value',
    name: '年化波动率（风险）%',
    nameLocation: 'middle',
    nameGap: 32,
    min: 0,
    max: 70,
    axisLabel: { fontSize: 10 },
    splitLine: { show: true },
  },
  yAxis: {
    type: 'value',
    name: '年化收益率 %',
    nameLocation: 'middle',
    nameGap: 40,
    min: -10,
    max: 12,
    axisLabel: { fontSize: 10 },
  },
  series: [
    {
      name: '股债组合线(ρ=0.2)',
      type: 'line',
      data: frontier.value,
      smooth: true,
      symbol: 'none',
      lineStyle: { width: 1.6, color: C.value.cyan, type: 'dashed' },
      tooltip: { show: false },
    },
    {
      name: '资产',
      type: 'scatter',
      data: assets.value.map((a) => ({
        name: a.name,
        value: [a.sigma, a.mu],
        symbol: a.symbol,
        symbolSize: 14,
        itemStyle: { color: withAlpha(a.color, 0.9), borderColor: a.color },
        label: {
          show: true,
          position: 'right',
          fontSize: 11,
          color: C.value.text,
          formatter: a.name,
        },
      })),
      tooltip: { show: true },
    },
    {
      name: '当前组合',
      type: 'scatter',
      data: [{ name: `股票 ${w.value}%`, value: [Number(port.value.sigma.toFixed(2)), Number(port.value.mu.toFixed(2))] }],
      symbol: 'circle',
      symbolSize: 18,
      itemStyle: {
        color: withAlpha(C.value.warning, 0.35),
        borderColor: C.value.warning,
        borderWidth: 2.5,
      },
      label: {
        show: true,
        position: 'left',
        fontSize: 11,
        fontWeight: 600,
        color: C.value.warning,
        formatter: `股票${w.value}%`,
      },
      z: 10,
    },
  ],
}))
</script>

<template>
  <div class="am">
    <div class="result">
      <div class="result-item">
        <span class="result-label">组合年化收益</span>
        <strong class="result-value">{{ port.mu.toFixed(1) }}%</strong>
      </div>
      <div class="result-item">
        <span class="result-label">组合波动率</span>
        <strong class="result-value">{{ port.sigma.toFixed(1) }}%</strong>
      </div>
      <div class="result-item">
        <span class="result-label">不分散的加权波动</span>
        <strong class="result-value" style="color: var(--text-2)">{{ port.naiveSigma.toFixed(1) }}%</strong>
      </div>
      <div class="result-item">
        <span class="result-label">分散化红利</span>
        <strong class="result-value" style="color: var(--success, #16a34a)">−{{ port.bonus.toFixed(1) }}%</strong>
      </div>
    </div>
    <ThemedChart class="chart" :option="option" autoresize />
    <div class="controls">
      <div class="control-row">
        <span class="control-label">股票比例</span>
        <input v-model.number="w" type="range" min="0" max="100" step="5" class="slider" />
        <span class="control-value">{{ w }}%</span>
      </div>
      <p class="hint">
        资产点为长期经验典型区间（教学示意）；单一股票点是第一章主线真实锚点——茅台 2024 年化波动 27.55%、年化收益
        -6.51%。拖动股票比例，橙色组合点沿股债组合线移动：50/50 时组合波动明显低于「两资产波动的加权平均」——这就是分散化的免费午餐（第七章展开）。
      </p>
    </div>
  </div>
</template>

<style scoped>
.am { padding: 16px; }
.chart { height: 360px; }
.result { display: flex; gap: 22px; margin-bottom: 12px; padding: 12px 16px; background: var(--primary-soft); border-radius: var(--radius-sm); flex-wrap: wrap; }
.result-item { display: flex; flex-direction: column; gap: 2px; }
.result-label { font-size: 12px; color: var(--text-3); }
.result-value { font-size: 18px; font-weight: 700; }
.controls { margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--border); display: flex; flex-direction: column; gap: 10px; }
.control-row { display: flex; align-items: center; gap: 12px; }
.control-label { width: 76px; font-size: 13px; color: var(--text-2); flex-shrink: 0; }
.slider { flex: 1; accent-color: var(--primary); cursor: pointer; }
.control-value { width: 56px; font-size: 13px; font-weight: 600; color: var(--primary); text-align: right; flex-shrink: 0; }
.hint { margin-top: 6px; font-size: 12px; color: var(--text-3); line-height: 1.7; }
</style>
