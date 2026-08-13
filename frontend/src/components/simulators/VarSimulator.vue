<script setup lang="ts">
import { computed, ref } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, MarkLineComponent } from 'echarts/components'
import { useStockDaily } from '@/composables/useStockDaily'

use([CanvasRenderer, BarChart, LineChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent])

// VaR 三种算法（真实茅台 2024 日收益）：
// 参数法（正态假设） / 历史法（真实分布分位） / MC 法（模拟路径）
// 教学点：三种方法答案不同——尾部假设决定 VaR
const props = defineProps<{
  params?: Record<string, unknown>
}>()

const code = computed(() => (typeof props.params?.code === 'string' ? props.params.code : 'sh600519'))
const { data } = useStockDaily(code, '2024-01-01', '2024-12-31')

const horizon = ref(1) // 持有期（天）
const confidence = ref(0.95)
const amount = ref(100) // 组合金额（万）

// 真实日收益（复权口径，不含首日）
const rets = computed<number[]>(() => (data.value ? data.value.map((d) => d.pct_chg).slice(1) : []))

function gauss(): number {
  let u = 0
  let v = 0
  while (u === 0) u = Math.random()
  while (v === 0) v = Math.random()
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v)
}

/** 标准正态分位数 Φ⁻¹(p)（Acklam 近似，任意置信度），替代只覆盖 0.90/0.95/0.99 的三档查表 */
function invNormal(p: number): number {
  const a = [-39.69683028665376, 220.9460984245205, -275.9285104469687, 138.357751867269, -30.66479806614716, 2.506628277459239]
  const b = [-54.47609879822406, 161.5858368580409, -155.6989798598866, 66.80131188771972, -13.28068155288572]
  const c = [-0.007784894002430293, -0.3223964580411365, -2.400758277161838, -2.549732539343734, 4.374664141464968, 2.938163982698783]
  const d = [0.007784695709041462, 0.3224671290700398, 2.445134137142996, 3.754408661907416]
  const plow = 0.02425
  const phigh = 1 - plow
  if (p < plow) {
    const q = Math.sqrt(-2 * Math.log(p))
    return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
  }
  if (p <= phigh) {
    const q = p - 0.5
    const r = q * q
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)
  }
  const q = Math.sqrt(-2 * Math.log(1 - p))
  return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
}

const analysis = computed(() => {
  const r = rets.value
  if (!r.length) return null
  const n = r.length
  const mu = r.reduce((s, v) => s + v, 0) / n
  const sd = Math.sqrt(r.reduce((s, v) => s + (v - mu) ** 2, 0) / (n - 1))
  const z = invNormal(confidence.value) // 标准正态分位数（左尾 Φ⁻¹(1−c) 的绝对值）
  const paramDaily = mu - z * sd // 日 VaR（收益率）
  const paramH = paramDaily * Math.sqrt(horizon.value)

  // 历史法：真实分布分位
  const sorted = [...r].sort((a, b) => a - b)
  const q = Math.max(0, Math.floor((1 - confidence.value) * n) - 1)
  const histDaily = sorted[q]
  const histH = histDaily * Math.sqrt(horizon.value)

  // MC：模拟 T 日累计收益，取分位
  const t = horizon.value
  const mcRet: number[] = []
  for (let i = 0; i < 5000; i++) {
    let cum = 0
    for (let d = 0; d < t; d++) cum += mu + sd * gauss()
    mcRet.push(cum)
  }
  const mcSorted = [...mcRet].sort((a, b) => a - b)
  const mcDaily = mcSorted[Math.max(0, Math.floor((1 - confidence.value) * 5000) - 1)]
  const mcH = mcDaily

  return {
    mu,
    sd,
    paramDaily,
    paramH,
    histDaily,
    histH,
    mcDaily,
    mcH,
    hist: { vals: r, sorted },
    pct: (1 - confidence.value) * 100,
    conf: confidence.value,
    t,
  }
})

const histOption = computed(() => {
  const a = analysis.value
  if (!a) return {}
  const vals = a.hist.vals
  const lo = -8
  const hi = 8
  const bins = 32
  const w = (hi - lo) / bins
  const counts = new Array(bins).fill(0)
  for (const v of vals) {
    const b = Math.min(bins - 1, Math.max(0, Math.floor((v - lo) / w)))
    counts[b]++
  }
  const centers = counts.map((_, i) => Number((lo + w * (i + 0.5)).toFixed(2)))
  const markData: any[] = [
    { xAxis: a.paramDaily, label: { formatter: `参数法 ${a.paramDaily.toFixed(1)}%`, position: 'insideEndTop' }, lineStyle: { color: C.value.danger, type: 'dashed' } },
    { xAxis: a.histDaily, label: { formatter: `历史法 ${a.histDaily.toFixed(1)}%`, position: 'insideEndBottom' }, lineStyle: { color: C.value.warning, type: 'dashed' } },
    { xAxis: a.mcDaily, label: { formatter: `MC ${a.mcDaily.toFixed(1)}%`, position: 'insideEndTop' }, lineStyle: { color: C.value.violet, type: 'dashed' } },
  ]
  return {
    animation: false,
    grid: { left: 52, right: 24, top: 36, bottom: 40 },
    tooltip: { trigger: 'axis' },
    legend: { top: 0, textStyle: { fontSize: 11 } },
    xAxis: { type: 'value', name: '日收益 %', nameLocation: 'middle', nameGap: 28, axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', name: '天数', nameLocation: 'middle', nameGap: 36, axisLabel: { fontSize: 10 } },
    series: [
      {
        name: '真实收益分布',
        type: 'bar',
        barWidth: '90%',
        data: centers.map((c, i) => [c, counts[i]]),
        itemStyle: { color: C.value.primary, opacity: 0.55 },
        markLine: { silent: true, symbol: 'none', data: markData },
      },
    ],
  }
})

function fmt(x: number | null): string {
  return x == null ? '-' : x.toFixed(2)
}
</script>

<template>
  <div class="var">
    <div v-if="!analysis" class="status">数据加载中…</div>
    <template v-else-if="analysis">
      <div class="controls">
        <label>持有期 <input type="range" v-model.number="horizon" min="1" max="10" step="1" /> {{ horizon }} 天</label>
        <label>置信度 <input type="range" v-model.number="confidence" min="0.9" max="0.99" step="0.01" /> {{ (confidence * 100).toFixed(0) }}%</label>
        <label>组合金额 <input type="range" v-model.number="amount" min="10" max="500" step="10" /> {{ amount }} 万</label>
      </div>
      <p class="note">真实数据：茅台 2024 全年 {{ analysis.hist.vals.length }} 个日收益（quantlab 库，复权口径）。三种 VaR 算法在同一置信度下给出不同结果——尾部分布假设不同。</p>
      <ThemedChart class="chart" :option="histOption" autoresize />
      <div class="table-wrap">
        <table class="tbl">
          <thead>
            <tr>
              <th>方法</th>
              <th>日 VaR（收益率）</th>
              <th>{{ horizon }} 日 VaR（收益率）</th>
              <th>金额损失（{{ amount }} 万）</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>参数法（正态）</td>
              <td>{{ fmt(analysis.paramDaily) }}%</td>
              <td>{{ fmt(analysis.paramH) }}%</td>
              <td>{{ (Math.abs(analysis.paramH / 100) * amount).toFixed(1) }} 万</td>
            </tr>
            <tr>
              <td>历史法（真实分位）</td>
              <td>{{ fmt(analysis.histDaily) }}%</td>
              <td>{{ fmt(analysis.histH) }}%</td>
              <td>{{ (Math.abs(analysis.histH / 100) * amount).toFixed(1) }} 万</td>
            </tr>
            <tr>
              <td>MC 模拟</td>
              <td>{{ fmt(analysis.mcDaily) }}%</td>
              <td>{{ fmt(analysis.mcH) }}%</td>
              <td>{{ (Math.abs(analysis.mcH / 100) * amount).toFixed(1) }} 万</td>
            </tr>
          </tbody>
        </table>
        <p class="note">解读：{{ (confidence * 100).toFixed(0) }}% 置信度、{{ horizon }} 天持有期下，组合最大预期损失。参数法假设正态尾部（低估肥尾风险），历史法直接取真实分位（更贴合 A 股），MC 依赖模拟模型。</p>
      </div>
    </template>
  </div>
</template>

<style scoped>
.var { padding: 16px; }
.status { height: 300px; display: flex; align-items: center; justify-content: center; color: var(--text-3); font-size: 14px; }
.chart { height: 320px; }
.controls { display: flex; gap: 14px; flex-wrap: wrap; align-items: center; margin-bottom: 10px; font-size: 12.5px; color: var(--text-2); }
.controls label { display: flex; align-items: center; gap: 6px; }
.controls input[type='range'] { width: 90px; }
.note { font-size: 12.5px; color: var(--text-3); margin-bottom: 10px; line-height: 1.6; }
.table-wrap { margin-top: 14px; }
.tbl { width: 100%; border-collapse: collapse; font-size: 12.5px; }
.tbl th, .tbl td { padding: 7px 10px; border: 1px solid var(--border); text-align: right; }
.tbl th:first-child, .tbl td:first-child { text-align: left; }
.tbl th { background: var(--bg-hover); color: var(--text-2); font-weight: 600; }
</style>