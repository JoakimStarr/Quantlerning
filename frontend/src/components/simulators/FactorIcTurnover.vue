<script setup lang="ts">
// 因子 IC vs 换手率散点（真实数据）：factor 表全部因子的 IC 与换手
// 教学点：高换手因子的 IC 未必更高——换手高 → 交易成本侵蚀大 → 净收益未必好
import { computed, onMounted, ref } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { ScatterChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, MarkLineComponent } from 'echarts/components'
import { fetchFactorIcTurnover } from '@/api'

use([CanvasRenderer, ScatterChart, GridComponent, TooltipComponent, MarkLineComponent])

const loading = ref(true)
const error = ref<string | null>(null)
const data = ref<Awaited<ReturnType<typeof fetchFactorIcTurnover>> | null>(null)

async function load() {
  loading.value = true
  error.value = null
  try {
    data.value = await fetchFactorIcTurnover('active', 200)
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
  const highTurnover = d.points.filter((p) => p.turnover >= 0.5)
  const lowTurnover = d.points.filter((p) => p.turnover < 0.5)
  return {
    animation: false,
    grid: { left: 52, right: 20, top: 30, bottom: 44 },
    tooltip: {
      trigger: 'item',
      formatter: (p: any) => {
        const pt = p.data.raw
        return `${pt.name}<br/>IC：${pt.ic.toFixed(4)}　换手率：${(pt.turnover * 100).toFixed(1)}%<br/>类别：${pt.category || '-'}`
      },
    },
    xAxis: {
      type: 'value',
      name: '换手率',
      nameLocation: 'middle',
      nameGap: 30,
      axisLabel: { fontSize: 10, formatter: (v: number) => `${Math.round(v * 100)}%` },
    },
    yAxis: {
      type: 'value',
      name: 'IC',
      nameLocation: 'middle',
      nameGap: 30,
      axisLabel: { fontSize: 10 },
    },
    series: [
      {
        name: '高换手（≥50%）',
        type: 'scatter',
        symbolSize: 10,
        data: highTurnover.map((p) => ({ value: [p.turnover, p.ic], raw: p })),
        itemStyle: { color: C.value.danger, opacity: 0.55 },
        markLine: {
          silent: true,
          symbol: 'none',
          data: [
            { xAxis: 0.5, label: { formatter: '换手 50%', position: 'insideEndTop' }, lineStyle: { color: C.value.text, type: 'dashed' } },
            { yAxis: 0, label: { formatter: 'IC=0', position: 'insideEndRight' }, lineStyle: { color: C.value.text, type: 'dotted' } },
          ],
        },
      },
      {
        name: '低换手（<50%）',
        type: 'scatter',
        symbolSize: 10,
        data: lowTurnover.map((p) => ({ value: [p.turnover, p.ic], raw: p })),
        itemStyle: { color: C.value.primary, opacity: 0.55 },
      },
    ],
  }
})
</script>

<template>
  <div class="factor-ic-turnover">
    <div v-if="loading" class="status">数据加载中…</div>
    <div v-else-if="error" class="status">数据不可用</div>
    <template v-else-if="data">
      <div class="stats">
        <span class="chip">因子数 <strong>{{ data.n }}</strong></span>
        <span class="chip">高换手（≥50%）<strong>{{ data.points.filter((p) => p.turnover >= 0.5).length }}</strong></span>
        <span class="chip">低换手（<50%）<strong>{{ data.points.filter((p) => p.turnover < 0.5).length }}</strong></span>
      </div>
      <ThemedChart class="chart" :option="option" autoresize />
    </template>
  </div>
</template>

<style scoped>
.factor-ic-turnover { padding: 16px; }
.status { height: 300px; display: flex; align-items: center; justify-content: center; color: var(--text-3); font-size: 14px; }
.chart { height: 340px; }
.stats { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
.chip {
  font-size: 12.5px; color: var(--text-3);
  padding: 4px 10px; border-radius: 999px; background: var(--bg-hover);
}
.chip strong { color: var(--primary); }
</style>
