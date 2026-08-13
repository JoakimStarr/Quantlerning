<script setup lang="ts">
import { computed } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { HeatmapChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, VisualMapComponent } from 'echarts/components'
import { useStockDaily } from '@/composables/useStockDaily'
import { maCrossSignal, shiftPosition, strategyNav, backtestArrays } from '@/utils/strategies'

use([CanvasRenderer, HeatmapChart, GridComponent, TooltipComponent, VisualMapComponent])

// 参数热力图（真实茅台 2020-2026，均线交叉）：快/慢周期 → 年化收益
const props = defineProps<{
  params?: Record<string, unknown>
}>()

const code = computed(() => (typeof props.params?.code === 'string' ? props.params.code : 'sh600519'))
const start = computed(() => (typeof props.params?.start === 'string' ? props.params.start : '2020-01-01'))
const end = computed(() => (typeof props.params?.end === 'string' ? props.params.end : '2026-08-10'))
const { data, loading, error } = useStockDaily(code, start.value, end.value)

const FASTS = [5, 10, 15, 20, 30, 40, 60]
const SLOWS = [20, 30, 40, 60, 90, 120, 180]

function annFromNav(last: number, n: number): number {
  return last ** (252 / n) - 1
}

const com = computed(() => {
  if (!data.value) return null
  const arr = backtestArrays(data.value)
  const n = arr.ret.length - 1
  const grid: number[][] = []
  let maxV = -Infinity
  let minV = Infinity
  for (let fi = 0; fi < FASTS.length; fi++) {
    for (let si = 0; si < SLOWS.length; si++) {
      const f = FASTS[fi]
      const s = SLOWS[si]
      if (f >= s) {
        grid.push([si, fi, null as unknown as number])
        continue
      }
      const pos = shiftPosition(maCrossSignal(arr.closes, f, s))
      const nav = strategyNav(arr.ret, pos)
      const ann = annFromNav(nav[nav.length - 1], n)
      grid.push([si, fi, +ann.toFixed(4)])
      if (ann > maxV) maxV = ann
      if (ann < minV) minV = ann
    }
  }
  // 标注最优参数
  let best: { f: number; s: number; v: number } | null = null
  for (const [si, fi, v] of grid) {
    if (v === null) continue
    if (!best || v > best.v) {
      best = { f: FASTS[fi], s: SLOWS[si], v }
    }
  }
  return { grid, maxV, minV, best, n }
})

const option = computed(() => {
  if (!com.value) return {}
  return {
    animation: true,
    tooltip: {
      formatter: (p: any) => {
        const f = FASTS[p.data[1]]
        const s = SLOWS[p.data[0]]
        const v = p.data[2]
        return v === null ? `MA${f}/${s}：无效` : `MA${f}/${s}：年化 ${(v * 100).toFixed(1)}%`
      },
    },
    grid: { left: 60, right: 80, top: 20, bottom: 40 },
    xAxis: { type: 'category', data: SLOWS.map((s) => `MA${s}`), axisLabel: { fontSize: 10 } },
    yAxis: { type: 'category', data: FASTS.map((f) => `MA${f}`), axisLabel: { fontSize: 10 } },
    visualMap: {
      min: com.value!.minV,
      max: com.value!.maxV,
      orient: 'vertical',
      right: 0,
      top: 'center',
      text: ['高', '低'],
      calculable: false,
      inRange: { color: [C.value.danger, C.value.warning, C.value.success] },
      textStyle: { fontSize: 10 },
    },
    series: [
      {
        type: 'heatmap',
        data: com.value!.grid.map((g) => g as unknown as [number, number, number]),
        label: {
          show: true,
          fontSize: 9,
          formatter: (p: any) => (p.data[2] === null ? '—' : `${(p.data[2] * 100).toFixed(1)}`),
        },
        itemStyle: { borderColor: '#fff', borderWidth: 1 },
        emphasis: { itemStyle: { shadowBlur: 8, shadowColor: 'rgba(0,0,0,0.4)' } },
      },
    ],
  }
})

const best = computed(() => com.value?.best)
</script>

<template>
  <div class="pl">
    <div v-if="loading" class="status">数据加载中…</div>
    <div v-else-if="error" class="status">数据不可用</div>
    <template v-else-if="com">
      <div class="result" v-if="best">
        本窗口最优 <strong>MA{{ best.f }}/{{ best.s }}</strong>，年化 {{ (best.v * 100).toFixed(1) }}% ——
        但它只是「这 6 年数据上的局部亮点」，换个窗口可能完全不成立（p2-l7 的过拟合）。
      </div>
      <ThemedChart class="chart" :option="option" autoresize />
    </template>
  </div>
</template>

<style scoped>
.pl { padding: 16px; }
.status { height: 360px; display: flex; align-items: center; justify-content: center; color: var(--text-3); font-size: 14px; }
.chart { height: 340px; }
.result { margin-bottom: 12px; padding: 10px 14px; background: var(--primary-soft); border-radius: var(--radius-sm); font-size: 13px; color: var(--text-2); line-height: 1.7; }
.result strong { color: var(--warning, #d97706); }
</style>