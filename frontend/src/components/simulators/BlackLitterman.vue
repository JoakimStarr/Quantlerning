<script setup lang="ts">
import { computed, ref } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { usePortfolioDaily } from '@/composables/usePortfolioDaily'
import { covarianceMatrix, annualReturns, blackLitterman, type BlView } from '@/utils/portfolio'

use([CanvasRenderer, BarChart, GridComponent, TooltipComponent, LegendComponent])

// Black-Litterman：观点融合
// 用户对某只股票给出「年化收益观点 + 置信度」→ 后验权重从均衡权重偏移
// 教学点：BL 把主观观点与市场均衡结合，置信度越高观点权重越大
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

// 观点设置：选中资产 + 目标年化 + 置信度
const viewAsset = ref(0)
const viewReturn = ref(0.3) // 年化收益观点
const viewConf = ref(0.5) // 置信度

const eqW = computed(() => new Array(names.value.length).fill(1 / names.value.length))

const result = computed(() => {
  if (!annRets.value.length) return null
  const views: BlView[] = [{ asset: viewAsset.value, return: viewReturn.value, confidence: viewConf.value }]
  const bl = blackLitterman(cov.value, views)
  return {
    bl,
    eqWeights: eqW.value,
    viewName: names.value[viewAsset.value],
  }
})

const weightOption = computed(() => {
  if (!result.value) return {}
  const r = result.value
  return {
    animation: false,
    grid: { left: 56, right: 24, top: 24, bottom: 40 },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { top: 0, textStyle: { fontSize: 11 } },
    xAxis: { type: 'category', data: names.value, axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', name: '权重', nameLocation: 'middle', nameGap: 34, max: 1, axisLabel: { fontSize: 10 } },
    series: [
      {
        name: '均衡权重',
        type: 'bar',
        data: r.eqWeights.map((w) => +w.toFixed(3)),
        itemStyle: { color: '#94a3b8', opacity: 0.5 },
      },
      {
        name: 'BL 后验',
        type: 'bar',
        data: r.bl.weights.map((w) => +w.toFixed(3)),
        itemStyle: { color: '#2563eb', opacity: 0.8 },
        label: { show: true, position: 'top', fontSize: 10, formatter: (p: any) => `${(p.value * 100).toFixed(0)}%` },
      },
    ],
  }
})

const muOption = computed(() => {
  if (!result.value) return {}
  const r = result.value
  return {
    animation: false,
    grid: { left: 56, right: 24, top: 24, bottom: 40 },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { top: 0, textStyle: { fontSize: 11 } },
    xAxis: { type: 'category', data: names.value, axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', name: '年化超额收益', nameLocation: 'middle', nameGap: 34, axisLabel: { fontSize: 10 } },
    series: [
      {
        name: '隐含均衡超额',
        type: 'bar',
        data: r.bl.implied.map((v) => +(v * 100).toFixed(1)),
        itemStyle: { color: '#94a3b8', opacity: 0.5 },
      },
      {
        name: 'BL 后验超额',
        type: 'bar',
        data: r.bl.mu.map((v) => +(v * 100).toFixed(1)),
        itemStyle: { color: '#d97706', opacity: 0.8 },
      },
    ],
  }
})
</script>

<template>
  <div class="bl">
    <div v-if="loading" class="status">数据加载中…</div>
    <div v-else-if="error" class="status">数据不可用</div>
    <template v-else-if="result">
      <div class="controls">
        <label>观点资产
          <select v-model.number="viewAsset">
            <option v-for="(n, i) in names" :key="n" :value="i">{{ n }}</option>
          </select>
        </label>
        <label>观点年化收益 <input type="range" v-model.number="viewReturn" min="-0.2" max="0.8" step="0.05" /> {{ (viewReturn * 100).toFixed(0) }}%</label>
        <label>置信度 <input type="range" v-model.number="viewConf" min="0.05" max="0.95" step="0.05" /> {{ (viewConf * 100).toFixed(0) }}%</label>
      </div>
      <div class="stats">
        <span class="chip">观点资产 <strong>{{ result.viewName }}</strong></span>
        <span class="chip">观点超额 <strong>{{ ((viewReturn - 0.02) * 100).toFixed(0) }}%</strong></span>
        <span class="chip note">置信度越高 → 后验权重越偏离均衡</span>
      </div>
      <p class="sub">权重：均衡 vs BL 后验（观点资产随置信度上移/下移）</p>
      <VChart class="chart" :option="weightOption" autoresize />
      <p class="sub">隐含均衡超额收益 vs BL 后验超额收益</p>
      <VChart class="chart small" :option="muOption" autoresize />
      <p class="note">真实锚点：贵州茅台 / 五粮液 / 宁德时代 / 招商银行 / 中国平安 2024 全年日收益（协方差矩阵来自真实数据）。教学点：BL = 市场均衡（隐含） + 主观观点加权；观点乐观且置信度高 → 权重上调，反之下调。示意性模型，用于理解观点融合机制。</p>
    </template>
  </div>
</template>

<style scoped>
.bl { padding: 16px; }
.status { height: 300px; display: flex; align-items: center; justify-content: center; color: var(--text-3); font-size: 14px; }
.controls { display: flex; gap: 14px; flex-wrap: wrap; align-items: center; margin-bottom: 10px; font-size: 12.5px; color: var(--text-2); }
.controls label { display: flex; align-items: center; gap: 6px; }
.controls select { padding: 3px 6px; border: 1px solid var(--border); border-radius: 6px; background: var(--bg-card); color: var(--text-2); font-size: 12px; }
.controls input[type='range'] { width: 100px; }
.chart { height: 280px; margin-bottom: 6px; }
.small { height: 200px; }
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