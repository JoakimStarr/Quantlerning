<script setup lang="ts">
// PE 分层累计净值（真实数据）：每月末按 PE 分 Q1~Q5，各组月度调仓累乘净值
// 教学点：把分层热力图的单调性用净值曲线呈现——U 形（Q1 与 Q5 高、中间低）
import { computed, onMounted, ref } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { fetchLayerNav } from '@/api'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent])

const loading = ref(true)
const error = ref<string | null>(null)
const data = ref<Awaited<ReturnType<typeof fetchLayerNav>> | null>(null)

async function load() {
  loading.value = true
  error.value = null
  try {
    data.value = await fetchLayerNav('2018-01-01', '2026-08-10', 5)
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

onMounted(load)

const colors = [
  C.value.primary,
  C.value.cyan,
  C.value.slate,
  C.value.warning,
  C.value.danger,
]

const option = computed(() => {
  if (!data.value) return {}
  const d = data.value
  return {
    animation: false,
    grid: { left: 52, right: 20, top: 40, bottom: 40 },
    legend: { top: 6, textStyle: { fontSize: 11 } },
    tooltip: {
      trigger: 'axis',
      formatter: (ps: any[]) => {
        const p = ps[0]
        return `${p.axisValue}<br/>` + ps.map((s) => `${s.seriesName}：${s.data.toFixed(2)}`).join('<br/>')
      },
    },
    xAxis: {
      type: 'category',
      data: d.dates,
      axisLabel: { fontSize: 10, formatter: (v: string) => v.slice(0, 7) },
    },
    yAxis: { type: 'value', name: '累计净值（起点 1.0）', nameLocation: 'middle', nameGap: 44, axisLabel: { fontSize: 10 } },
    series: d.groups.map((g, i) => ({
      name: g,
      type: 'line',
      smooth: false,
      showSymbol: false,
      data: d.nav[i],
      lineStyle: { width: 2, color: colors[i] },
      itemStyle: { color: colors[i] },
    })),
  }
})
</script>

<template>
  <div class="layer-nav">
    <div v-if="loading" class="status">数据加载中…</div>
    <div v-else-if="error" class="status">数据不可用</div>
    <template v-else-if="data">
      <div class="stats">
        <span class="chip">Q1 末净值 <strong>{{ data.nav[0][data.nav[0].length - 1].toFixed(2) }}</strong></span>
        <span class="chip">Q5 末净值 <strong>{{ data.nav[data.nav.length - 1][data.nav[data.nav.length - 1].length - 1].toFixed(2) }}</strong></span>
        <span class="chip">2018-2026 月度调仓</span>
      </div>
      <ThemedChart class="chart" :option="option" autoresize />
    </template>
  </div>
</template>

<style scoped>
.layer-nav { padding: 16px; }
.status { height: 300px; display: flex; align-items: center; justify-content: center; color: var(--text-3); font-size: 14px; }
.chart { height: 320px; }
.stats { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
.chip {
  font-size: 12.5px; color: var(--text-3);
  padding: 4px 10px; border-radius: 999px; background: var(--bg-hover);
}
.chip strong { color: var(--primary); }
</style>
