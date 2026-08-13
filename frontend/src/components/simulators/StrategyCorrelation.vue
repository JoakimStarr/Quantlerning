<script setup lang="ts">
import { computed } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, HeatmapChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, VisualMapComponent } from 'echarts/components'
import { useStockDaily } from '@/composables/useStockDaily'
import {
  maCrossSignal,
  bollingerZSignal,
  momentumSignal,
  shiftPosition,
  strategyNav,
  stats,
  backtestArrays,
} from '@/utils/strategies'

use([CanvasRenderer, LineChart, HeatmapChart, GridComponent, TooltipComponent, LegendComponent, VisualMapComponent])

// 三策略相关性矩阵 + 等权组合（真实茅台 2020-2026）
// 教学点：策略收益相关性低 → 组合后波动下降、夏普提升——分散化在策略层的体现

const props = defineProps<{
  params?: Record<string, unknown>
}>()

const code = computed(() => (typeof props.params?.code === 'string' ? props.params.code : 'sh600519'))
const start = computed(() => (typeof props.params?.start === 'string' ? props.params.start : '2020-01-01'))
const end = computed(() => (typeof props.params?.end === 'string' ? props.params.end : '2026-08-10'))
const { data, loading, error } = useStockDaily(code, start.value, end.value)

interface Strat {
  name: string
  color: string
  ret: number[] // 策略日收益
  nav: number[]
  st: ReturnType<typeof stats>
}

const strats = computed<Strat[] | null>(() => {
  if (!data.value) return null
  const arr = backtestArrays(data.value)
  const specs: { name: string; color: string; sig: number[] }[] = [
    { name: '均线 MA20/60', color: C.value.warning, sig: maCrossSignal(arr.closes, 20, 60) },
    { name: 'z-score 回归', color: C.value.success, sig: bollingerZSignal(arr.closes, 20, 2) },
    { name: '时序动量', color: C.value.violet, sig: momentumSignal(arr.closes, 20) },
  ]
  return specs.map((s) => {
    const pos = shiftPosition(s.sig)
    const nav = strategyNav(arr.ret, pos)
    // 策略日收益：净值差分
    const ret = nav.map((_, i) => (i === 0 ? 0 : nav[i] / nav[i - 1] - 1))
    return { name: s.name, color: s.color, ret, nav, st: stats(arr.ret, pos) }
  })
})

// 相关性矩阵
const corrData = computed<{ matrix: number[][]; names: string[] }>(() => {
  const s = strats.value
  if (!s || s.length === 0) return { matrix: [], names: [] }
  const n = s.length
  const names = s.map((x) => x.name)
  const matrix: number[][] = Array.from({ length: n }, () => Array(n).fill(0))
  for (let i = 0; i < n; i++) {
    for (let j = 0; j < n; j++) {
      if (i === j) {
        matrix[i][j] = 1
        continue
      }
      const a = s[i].ret
      const b = s[j].ret
      const ma = a.reduce((x, y) => x + y, 0) / a.length
      const mb = b.reduce((x, y) => x + y, 0) / b.length
      let cov = 0
      let va = 0
      let vb = 0
      for (let k = 0; k < a.length; k++) {
        cov += (a[k] - ma) * (b[k] - mb)
        va += (a[k] - ma) ** 2
        vb += (b[k] - mb) ** 2
      }
      matrix[i][j] = cov / Math.sqrt(va * vb)
    }
  }
  return { matrix, names }
})

// 等权组合净值与统计
const combo = computed<{ nav: number[]; st: ReturnType<typeof stats> } | null>(() => {
  const s = strats.value
  if (!s || s.length === 0) return null
  const n = s.length
  const nav = s[0].nav.map((_, i) => {
    let v = 0
    for (const st of s) v += st.nav[i]
    return v / n
  })
  // 组合日收益
  const ret = nav.map((_, i) => (i === 0 ? 0 : nav[i] / nav[i - 1] - 1))
  const cum = nav[nav.length - 1] / 100 - 1
  const ann = (1 + cum) ** (252 / ret.length) - 1
  const vol = Math.sqrt(252) * std(ret.filter((_, i) => i > 0))
  const sharpe = (ann - 0.02) / vol
  let peak = 0
  let mdd = 0
  for (const v of nav) {
    peak = Math.max(peak, v)
    mdd = Math.min(mdd, v / peak - 1)
  }
  const st = { cum, ann, vol, mdd, sharpe, switches: 0 } as ReturnType<typeof stats>
  return { nav, st }
})

function std(xs: number[]) {
  const m = xs.reduce((a, b) => a + b, 0) / xs.length
  return Math.sqrt(xs.reduce((a, b) => a + (b - m) ** 2, 0) / (xs.length - 1))
}

const heatmapOption = computed(() => {
  const { matrix, names } = corrData.value
  if (!matrix.length) return {}
  const cells: [number, number, number][] = []
  matrix.forEach((row, i) => row.forEach((v, j) => cells.push([j, i, +v.toFixed(2)])))
  return {
    animation: false,
    grid: { left: 90, right: 40, top: 30, bottom: 60 },
    tooltip: {
      position: 'top',
      formatter: (p: any) => {
        const v = matrix[p.value[1]][p.value[0]]
        return `${names[p.value[1]]} × ${names[p.value[0]]}<br/>相关系数 ${v.toFixed(2)}`
      },
    },
    xAxis: { type: 'category', data: names, axisLabel: { fontSize: 10, rotate: 18 } },
    yAxis: { type: 'category', data: names, axisLabel: { fontSize: 10 } },
    visualMap: {
      min: -1,
      max: 1,
      calculable: false,
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
      inRange: { color: [C.value.danger, '#f8fafc', C.value.primary] },
      textStyle: { fontSize: 10 },
    },
    series: [
      {
        type: 'heatmap',
        data: cells,
        label: { show: true, fontSize: 11, formatter: (p: any) => matrix[p.value[1]][p.value[0]].toFixed(2) },
        itemStyle: { borderColor: '#fff', borderWidth: 2 },
      },
    ],
  }
})

const navOption = computed(() => {
  if (!strats.value || !combo.value) return {}
  const dates = data.value!.map((d) => d.date)
  const series = [
    ...strats.value.map((s) => ({
      name: s.name,
      type: 'line',
      data: s.nav.map((v) => +v.toFixed(1)),
      smooth: true,
      symbol: 'none',
      lineStyle: { width: 1.2, color: s.color },
    })),
    {
      name: '等权组合',
      type: 'line',
      data: combo.value.nav.map((v) => +v.toFixed(1)),
      smooth: true,
      symbol: 'none',
      lineStyle: { width: 3, color: C.value.primary },
    },
  ]
  return {
    animation: true,
    grid: { left: 52, right: 24, top: 36, bottom: 44 },
    tooltip: { trigger: 'axis' },
    legend: { top: 0, textStyle: { fontSize: 11 } },
    xAxis: { type: 'category', data: dates, axisLabel: { fontSize: 10, hideOverlap: true } },
    yAxis: { type: 'value', name: '净值（起点=100）', nameLocation: 'middle', nameGap: 44, scale: true, axisLabel: { fontSize: 10 } },
    series,
  }
})
</script>

<template>
  <div class="sc-corr">
    <div v-if="loading" class="status">数据加载中…</div>
    <div v-else-if="error" class="status">数据不可用</div>
    <template v-else-if="strats">
      <div class="stats">
        <span class="chip" v-for="s in strats" :key="s.name">
          <span class="dot" :style="{ background: s.color }"></span>{{ s.name }} Sharpe <strong>{{ s.st.sharpe.toFixed(2) }}</strong>
        </span>
        <span class="chip chip-main" v-if="combo">等权组合 Sharpe <strong>{{ combo.st.sharpe.toFixed(2) }}</strong></span>
      </div>

      <ThemedChart class="chart heat" :option="heatmapOption" autoresize />
      <ThemedChart class="chart nav" :option="navOption" autoresize />

      <div class="tip">
        左图：三策略日收益的相关矩阵（红=负相关、蓝=正相关）。均线与动量同属顺势、相关性偏高；z-score 回归逆势，
        与前两者相关性明显更低。右图：等权组合（蓝粗线）在同样收益水平下，波动与回撤都比单一策略更小——相关性低是「策略层分散化」的数学基础（Phase 6 会系统讲组合）。
      </div>
    </template>
  </div>
</template>

<style scoped>
.sc-corr { padding: 16px; }
.status { height: 300px; display: flex; align-items: center; justify-content: center; color: var(--text-3); font-size: 14px; }
.chart { width: 100%; }
.heat { height: 240px; margin-bottom: 10px; }
.nav { height: 260px; }
.stats { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
.chip {
  font-size: 12px; color: var(--text-3);
  padding: 4px 10px; border-radius: 999px; background: var(--bg-hover);
}
.chip strong { color: var(--primary); }
.chip-main { background: var(--primary-soft); }
.dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 5px; }
.tip { margin-top: 10px; font-size: 12.5px; color: var(--text-3); line-height: 1.7; }
</style>
