<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { HeatmapChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, VisualMapComponent } from 'echarts/components'
import { fetchPeLayers } from '@/api'

use([CanvasRenderer, HeatmapChart, GridComponent, TooltipComponent, VisualMapComponent])

// 全市场 PE 分层收益热力图（真实数据）：
// 每月末按 PE 从低到高分成 5 组，格子颜色 = 该组下月平均收益
// 教学点：真实结果呈 U 形（Q1 与 Q5 都高、中间低）而非单调，且 IC 微弱不稳定——
// 因子方向与强度依赖研究区间，严谨做法是分样本、分市场检验
const props = defineProps<{
  params?: Record<string, unknown>
}>()

const start = computed(() => (typeof props.params?.start === 'string' ? props.params.start : '2018-01-01'))
const end = computed(() => (typeof props.params?.end === 'string' ? props.params.end : '2026-08-10'))
const nGroups = computed(() => {
  const v = Number(props.params?.n_groups ?? 5)
  return Number.isFinite(v) && v >= 2 && v <= 10 ? v : 5
})

const loading = ref(true)
const error = ref<string | null>(null)
const data = ref<Awaited<ReturnType<typeof fetchPeLayers>> | null>(null)

async function load() {
  loading.value = true
  error.value = null
  try {
    data.value = await fetchPeLayers(start.value, end.value, nGroups.value)
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

onMounted(load)

const option = computed(() => {
  if (!data.value) return {}
  const d = data.value
  const cells: [number, number, number][] = []
  d.dates.forEach((_, mi) => {
    d.matrix[mi].forEach((v, gi) => {
      if (v != null) cells.push([gi, mi, v])
    })
  })
  return {
    animation: false,
    grid: { left: 90, right: 16, top: 16, bottom: 56 },
    tooltip: {
      formatter: (p: any) => {
        const { value } = p
        if (value[2] == null) return ''
        return `${d.groups[value[0]]} · ${d.dates[value[1]]}<br/>下月平均收益：${(value[2] * 100).toFixed(2)}%`
      },
    },
    visualMap: {
      min: -0.06,
      max: 0.06,
      calculable: true,
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
      textStyle: { fontSize: 10 },
      inRange: { color: ['#b91c1c', '#fca5a5', '#ffffff', '#86efac', '#15803d'] },
    },
    xAxis: {
      type: 'category',
      data: d.groups,
      axisLabel: { fontSize: 10, interval: 0 },
      splitArea: { show: true },
    },
    yAxis: {
      type: 'category',
      data: d.dates.map((m) => m.slice(0, 7)),
      axisLabel: { fontSize: 9, interval: 3 },
      splitArea: { show: true },
    },
    series: [
      {
        name: '月收益',
        type: 'heatmap',
        data: cells,
        label: { show: false },
        emphasis: { itemStyle: { shadowBlur: 6, shadowColor: 'rgba(0,0,0,0.4)' } },
      },
    ],
  }
})

// 组平均（全部月份）——展示价值溢价
const groupMean = computed(() => {
  if (!data.value) return []
  const d = data.value
  return d.groups.map((g, gi) => {
    const vals = d.matrix.map((row) => row[gi]).filter((v): v is number => v != null)
    return {
      name: g,
      mean: vals.reduce((s, v) => s + v, 0) / vals.length,
      win: vals.filter((v) => v > 0).length / vals.length,
      // 真实复利连乘：∏(1+r_t) − 1（不能用 (1+平均)^N−1，会高估）
      cum: vals.reduce((s, v) => s * (1 + v), 1) - 1,
    }
  })
})
</script>

<template>
  <div class="pe-layers">
    <div v-if="loading" class="status">数据加载中…</div>
    <div v-else-if="error" class="status">数据不可用</div>
    <template v-else-if="data">
      <ThemedChart class="chart" :option="option" autoresize />
      <div class="table-wrap">
        <table class="tbl">
          <thead>
            <tr>
              <th>PE 分组</th>
              <th>平均月收益</th>
              <th>月胜率</th>
              <th>累计（复利）</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="g in groupMean" :key="g.name">
              <td>{{ g.name }}</td>
              <td :class="{ pos: g.mean > 0 }">{{ (g.mean * 100).toFixed(2) }}%</td>
              <td>{{ (g.win * 100).toFixed(0) }}%</td>
              <td :class="{ pos: g.cum > 0 }">
                {{ (g.cum * 100).toFixed(0) }}%
              </td>
            </tr>
          </tbody>
        </table>
        <p class="note">真实数据：全市场 {{ data.dates.length }} 个月末快照，按 PE 从低到高分组，取各组下月平均收益。</p>
      </div>
    </template>
  </div>
</template>

<style scoped>
.pe-layers { padding: 16px; }
.status { height: 300px; display: flex; align-items: center; justify-content: center; color: var(--text-3); font-size: 14px; }
.chart { height: 420px; }
.table-wrap { margin-top: 14px; }
.tbl { width: 100%; border-collapse: collapse; font-size: 12.5px; }
.tbl th, .tbl td { padding: 6px 8px; border: 1px solid var(--border); text-align: right; }
.tbl th:first-child, .tbl td:first-child { text-align: left; }
.tbl th { background: var(--bg-hover); color: var(--text-2); font-weight: 600; }
.pos { color: var(--success); font-weight: 600; }
.note { font-size: 12px; color: var(--text-3); margin-top: 10px; }
</style>
