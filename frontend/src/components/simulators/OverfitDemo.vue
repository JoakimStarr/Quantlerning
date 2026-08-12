<script setup lang="ts">
import { computed, ref } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, ScatterChart, BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, MarkLineComponent } from 'echarts/components'
import { useStockDaily } from '@/composables/useStockDaily'
import { polyFit, mse } from '@/utils/ml'

use([CanvasRenderer, LineChart, ScatterChart, BarChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent])

// 过拟合演示：用真实茅台 2024 净值拟合多项式
// 教学点：阶数越高，训练集误差越小（记忆噪声），验证集误差先降后升（偏差-方差权衡）
const props = defineProps<{
  params?: Record<string, unknown>
}>()

const code = computed(() => (typeof props.params?.code === 'string' ? props.params.code : 'sh600519'))
const { data, loading, error } = useStockDaily(code)

// 用净值（起点 100）作为拟合目标 y
const raw = computed<number[]>(() => {
  if (!data.value) return []
  const out: number[] = []
  let v = 100
  out.push(v)
  for (let i = 1; i < data.value.length; i++) {
    v *= 1 + data.value[i].pct_chg / 100
    out.push(v)
  }
  return out
})

const degree = ref(3)
const trainRatio = ref(0.6)

// x 归一化到 [0,1]，避免多项式数值溢出
const x = computed<number[]>(() => raw.value.map((_, i) => (raw.value.length > 1 ? i / (raw.value.length - 1) : 0)))

const split = computed(() => {
  const n = x.value.length
  const cut = Math.max(2, Math.floor(n * trainRatio.value))
  const xi = x.value.slice(0, cut)
  const yi = raw.value.slice(0, cut)
  const xv = x.value.slice(cut)
  const yv = raw.value.slice(cut)
  return { xi, yi, xv, yv, cut }
})

const fit = computed(() => {
  const { xi, yi } = split.value
  return polyFit(xi, yi, degree.value)
})

// 训练/验证误差随阶数变化（供误差曲线图）
const errorCurve = computed(() => {
  const { xi, yi, xv, yv } = split.value
  const degrees: number[] = []
  const trainErr: number[] = []
  const valErr: number[] = []
  for (let d = 1; d <= 12; d++) {
    const f = polyFit(xi, yi, d)
    degrees.push(d)
    trainErr.push(+mse(xi.map((v) => f.predict(v)), yi).toFixed(2))
    valErr.push(+mse(xv.map((v) => f.predict(v)), yv).toFixed(2))
  }
  return { degrees, trainErr, valErr }
})

const trainMse = computed(() => {
  const { xi, yi } = split.value
  return mse(xi.map((v) => fit.value.predict(v)), yi)
})
const valMse = computed(() => {
  const { xv, yv } = split.value
  return mse(xv.map((v) => fit.value.predict(v)), yv)
})

// 拟合曲线采样点
const curvePts = computed(() => {
  const pts: number[] = []
  const n = 120
  for (let i = 0; i <= n; i++) pts.push(i / n)
  return pts.map((t) => +fit.value.predict(t).toFixed(2))
})

const fitOption = computed(() => {
  const { xi, yi, xv, yv, cut } = split.value
  const dates = raw.value.length ? (data.value ? data.value.map((d) => d.date) : []) : []
  return {
    animation: false,
    grid: { left: 56, right: 24, top: 36, bottom: 44 },
    tooltip: { trigger: 'item' },
    legend: { top: 0, textStyle: { fontSize: 11 } },
    xAxis: { type: 'category', data: dates.map((d, i) => i === cut ? `${d}\n（验证起点）` : d), axisLabel: { fontSize: 9, hideOverlap: true, interval: 40 } },
    yAxis: { type: 'value', name: '净值', nameLocation: 'middle', nameGap: 40, axisLabel: { fontSize: 10 } },
    series: [
      {
        name: '训练样本',
        type: 'scatter',
        data: xi.map((_, i) => [i, +yi[i].toFixed(2)]),
        symbolSize: 4,
        itemStyle: { color: '#2563eb', opacity: 0.7 },
      },
      {
        name: '验证样本',
        type: 'scatter',
        data: xv.map((_, i) => [i + cut, +yv[i].toFixed(2)]),
        symbolSize: 4,
        itemStyle: { color: '#d97706', opacity: 0.7 },
      },
      {
        name: `${degree.value} 阶拟合`,
        type: 'line',
        data: curvePts.value.map((v, i) => [i / 120 * (raw.value.length - 1), v]),
        symbol: 'none',
        lineStyle: { color: '#dc2626', width: 2 },
        markLine: {
          silent: true,
          symbol: 'none',
          data: [{ xAxis: cut, label: { formatter: '训练 | 验证', position: 'insideEndTop' }, lineStyle: { color: '#64748b', type: 'dashed' } }],
        },
      },
    ],
  }
})

const errOption = computed(() => {
  const ec = errorCurve.value
  return {
    animation: false,
    grid: { left: 56, right: 24, top: 36, bottom: 44 },
    tooltip: { trigger: 'axis' },
    legend: { top: 0, textStyle: { fontSize: 11 } },
    xAxis: { type: 'category', data: ec.degrees, name: '阶数', nameLocation: 'middle', nameGap: 30, axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', name: 'MSE', nameLocation: 'middle', nameGap: 40, axisLabel: { fontSize: 10 }, min: 0 },
    series: [
      {
        name: '训练误差',
        type: 'line',
        data: ec.trainErr,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: { color: '#2563eb', width: 2 },
        itemStyle: { color: '#2563eb' },
        markLine: {
          silent: true,
          symbol: 'none',
          data: [{ xAxis: degree.value, lineStyle: { color: '#dc2626', type: 'dashed' }, label: { formatter: `当前 ${degree.value} 阶`, position: 'end' } }],
        },
      },
      {
        name: '验证误差',
        type: 'line',
        data: ec.valErr,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: { color: '#d97706', width: 2 },
        itemStyle: { color: '#d97706' },
      },
    ],
  }
})

const gap = computed(() => (valMse.value - trainMse.value) / (valMse.value || 1))
</script>

<template>
  <div class="overfit">
    <div v-if="loading" class="status">数据加载中…</div>
    <div v-else-if="error" class="status">数据不可用</div>
    <template v-else-if="raw.length">
      <div class="controls">
        <label>阶数 <input type="range" v-model.number="degree" min="1" max="12" step="1" /> {{ degree }}</label>
        <label>训练集占比 <input type="range" v-model.number="trainRatio" min="0.4" max="0.9" step="0.05" /> {{ (trainRatio * 100).toFixed(0) }}%</label>
      </div>
      <div class="stats">
        <span class="chip">训练 MSE = <strong>{{ trainMse.toFixed(1) }}</strong></span>
        <span class="chip">验证 MSE = <strong>{{ valMse.toFixed(1) }}</strong></span>
        <span class="chip">差距 <strong>{{ gap.toFixed(1) }}×</strong></span>
        <span class="chip note">{{ degree >= 8 ? '⚠ 高方差（过拟合）' : degree <= 3 ? '高偏差（欠拟合）' : '偏差-方差平衡' }}</span>
      </div>
      <p class="sub">拟合曲线（真实茅台净值，蓝=训练样本，橙=验证样本，红=多项式拟合）</p>
      <VChart class="chart" :option="fitOption" autoresize />
      <p class="sub">训练/验证误差 vs 阶数（虚线=当前阶数；曲线交汇最低点即最优复杂度）</p>
      <VChart class="chart" :option="errOption" autoresize />
      <p class="note">真实锚点：贵州茅台 SH600519 2024 复权净值（起点 100）。教学点：阶数低→欠拟合（验证误差高），阶数高→完美记忆训练集但验证误差回升——这就是过拟合的经典信号，交叉验证正是为此而生。</p>
    </template>
  </div>
</template>

<style scoped>
.overfit { padding: 16px; }
.status { height: 300px; display: flex; align-items: center; justify-content: center; color: var(--text-3); font-size: 14px; }
.controls { display: flex; gap: 16px; flex-wrap: wrap; align-items: center; margin-bottom: 10px; font-size: 12.5px; color: var(--text-2); }
.controls label { display: flex; align-items: center; gap: 6px; }
.controls input[type='range'] { width: 110px; }
.chart { height: 280px; margin-bottom: 6px; }
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
