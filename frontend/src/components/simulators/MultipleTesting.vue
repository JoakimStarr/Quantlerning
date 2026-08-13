<script setup lang="ts">
import { computed, ref } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, MarkLineComponent } from 'echarts/components'

use([CanvasRenderer, BarChart, LineChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent])

// 多重检验演示：一个「期望为零」的随机策略，试验 N 次，最优一次的表现
// 教学点：试的参数/策略越多，「最好结果」虚高越严重——这就是多重检验/数据窥探
// 纯模拟（示意）：随机收益 ~ N(0, 1)，每组独立，取最优的 t 统计量

const props = defineProps<{
  params?: Record<string, unknown>
}>()

const trials = ref(typeof props.params?.trials === 'number' ? props.params.trials : 50) // 试验组数

// 每次模拟：trials 组独立随机 |t| 值，取最大（重复 REP 次取中位数）
const REP = 20000
function simulate(nTrials: number): number {
  let best = 0
  for (let i = 0; i < nTrials; i++) {
    const u1 = Math.random()
    const u2 = Math.random()
    const t = Math.sqrt(-2 * Math.log(u1 || 1e-9)) * Math.cos(2 * Math.PI * u2)
    best = Math.max(best, Math.abs(t))
  }
  return best
}

// 多档试验数
const trialLevels = [1, 5, 10, 20, 50, 100, 200]
const histData = computed(() => {
  return trialLevels.map((n) => {
    const sims: number[] = []
    for (let r = 0; r < REP; r++) sims.push(simulate(n))
    sims.sort((a, b) => a - b)
    return { n, median: sims[Math.floor(REP / 2)] }
  })
})

// 理论曲线：E[max|Z|] ≈ sqrt(2 ln(2N))
const theory = computed<[number, number][]>(() => {
  const out: [number, number][] = []
  for (let n = 1; n <= 200; n += 1) out.push([n, +Math.sqrt(2 * Math.log(2 * n)).toFixed(3)])
  return out
})

const barOption = computed(() => ({
  animation: true,
  grid: { left: 48, right: 24, top: 36, bottom: 40 },
  tooltip: { trigger: 'axis' },
  legend: { top: 0, textStyle: { fontSize: 11 } },
  xAxis: { type: 'category', data: trialLevels.map((n) => `${n} 组`), axisLabel: { fontSize: 11 } },
  yAxis: { type: 'value', name: '最优 |t| 值', nameLocation: 'middle', nameGap: 38, axisLabel: { fontSize: 11 } },
  series: [
    {
      name: '模拟中位数',
      type: 'bar',
      data: histData.value.map((h) => +h.median.toFixed(2)),
      itemStyle: { color: C.value.primary },
      label: { show: true, position: 'top', fontSize: 11, formatter: (p: any) => p.value.toFixed(1) },
    },
    {
      name: '理论 E[max|Z|]',
      type: 'line',
      data: trialLevels.map((n) => +Math.sqrt(2 * Math.log(2 * n)).toFixed(2)),
      symbol: 'none',
      lineStyle: { width: 2, color: C.value.danger, type: 'dashed' },
      markLine: {
        silent: true,
        symbol: 'none',
        label: { fontSize: 11, formatter: '|t|=1.96（5% 显著）' },
        data: [{ yAxis: 1.96, lineStyle: { color: C.value.success, type: 'dotted' } }],
      },
    },
  ],
}))

const curveOption = computed(() => ({
  animation: true,
  grid: { left: 48, right: 24, top: 36, bottom: 40 },
  tooltip: { trigger: 'axis', formatter: (ps: any) => `试验 ${Number(ps[0].value[0]).toFixed(0)} 组<br/>最优|t| ≈ ${Number(ps[0].value[1]).toFixed(2)}` },
  legend: { top: 0, textStyle: { fontSize: 11 } },
  xAxis: { type: 'value', name: '试验组数 N', nameLocation: 'middle', nameGap: 28, min: 1, max: 200, axisLabel: { fontSize: 11 } },
  yAxis: { type: 'value', name: '最优 |t|', nameLocation: 'middle', nameGap: 36, axisLabel: { fontSize: 11 } },
  series: [
    {
      name: 'E[max|Z|]',
      type: 'line',
      smooth: true,
      symbol: 'none',
      data: theory.value,
      lineStyle: { width: 3, color: C.value.danger },
      markLine: {
        silent: true,
        symbol: 'none',
        lineStyle: { color: C.value.success, type: 'dotted' },
        label: { fontSize: 11, formatter: '|t|=1.96' },
        data: [{ yAxis: 1.96 }],
      },
    },
  ],
}))

// 当前滑块位置的解读（渐近近似，真实模拟中位数略低）
const curExp = computed(() => {
  const n = trials.value
  return +Math.sqrt(2 * Math.log(2 * n)).toFixed(2)
})
</script>

<template>
  <div class="mult-test">
    <div class="result-row">
      <div class="result-box">
        <span class="muted">试验组数 N</span>
        <strong class="res-main">{{ trials }}</strong>
      </div>
      <div class="result-box">
        <span class="muted">最优一组的期望 |t|</span>
        <strong class="res-main">{{ curExp }}</strong>
      </div>
      <div class="result-box">
        <span class="muted">5% 显著阈值</span>
        <strong class="res-sub">1.96</strong>
      </div>
      <div class="result-box">
        <span class="muted">N 组中「碰巧」|t|>1.96 的概率</span>
        <strong class="res-sub" :class="{ warn: curExp > 1.96 }">{{ (1 - Math.pow(0.95, trials) * 1).toFixed(1) }}%</strong>
      </div>
    </div>

    <ThemedChart class="chart" :option="barOption" autoresize />
    <ThemedChart class="chart" :option="curveOption" autoresize />

    <div class="controls">
      <div class="control-row">
        <span class="control-label">试验组数 N</span>
        <input v-model.number="trials" type="range" min="1" max="200" step="1" class="slider" />
        <span class="control-value">{{ trials }}</span>
      </div>
      <div class="tip">
        想象你在遍历 50 组均线参数、或回测 50 条不同的策略规则。每组都是「期望收益为零」的随机过程，但只要试得足够多，
        <b>最好那组</b>的 |t| 就会显著大于 1.96——这不是策略有效，而是多重检验的必然结果（蓝色柱为模拟，红线为理论）。
        应对：样本外验证、多重检验校正（Bonferroni）、以及对「调出来的最好参数」天然保持怀疑。
      </div>
    </div>
  </div>
</template>

<style scoped>
.mult-test { padding: 16px; }
.chart { height: 240px; }
.result-row { display: flex; gap: 10px; margin-bottom: 12px; }
.result-box {
  flex: 1; padding: 10px 12px; border-radius: var(--radius-sm);
  background: var(--primary-soft); text-align: center;
  display: flex; flex-direction: column; gap: 2px;
}
.muted { font-size: 12px; color: var(--text-3); }
.res-main { font-size: 18px; font-weight: 700; color: var(--primary); }
.res-sub { font-size: 15px; font-weight: 700; color: var(--text-2); }
.res-sub.warn { color: var(--danger, #dc2626); }
.controls { margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border); }
.control-row { display: flex; align-items: center; gap: 12px; }
.control-label { width: 88px; font-size: 13px; color: var(--text-2); flex-shrink: 0; }
.slider { flex: 1; accent-color: var(--primary); cursor: pointer; }
.control-value { width: 48px; font-size: 13px; font-weight: 600; color: var(--primary); text-align: right; flex-shrink: 0; }
.tip { margin-top: 10px; font-size: 12.5px; color: var(--text-3); line-height: 1.7; }
</style>
