<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, MarkLineComponent } from 'echarts/components'
import { fetchPeIc } from '@/api'

use([CanvasRenderer, LineChart, BarChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent])

// PE 因子月度 Rank IC 序列（真实数据）：IC 围绕均值波动，ICIR 衡量稳定性
const props = defineProps<{
  params?: Record<string, unknown>
}>()

const start = computed(() => (typeof props.params?.start === 'string' ? props.params.start : '2018-01-01'))
const end = computed(() => (typeof props.params?.end === 'string' ? props.params.end : '2026-08-10'))
const loading = ref(true)
const error = ref<string | null>(null)
const data = ref<Awaited<ReturnType<typeof fetchPeIc>> | null>(null)

async function load() {
  loading.value = true
  error.value = null
  try {
    data.value = await fetchPeIc(start.value, end.value)
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
  return {
    animation: false,
    grid: { left: 52, right: 24, top: 36, bottom: 44 },
    tooltip: {
      trigger: 'axis',
      formatter: (ps: any[]) => {
        const p = Array.isArray(ps) ? ps[0] : ps
        return `${d.dates[p.dataIndex]}<br/>Rank IC：${Number(p.value[1]).toFixed(4)}`
      },
    },
    legend: { top: 0, textStyle: { fontSize: 11 } },
    xAxis: { type: 'category', data: d.dates.map((m) => m.slice(0, 7)), axisLabel: { fontSize: 9, hideOverlap: true } },
    yAxis: { type: 'value', name: 'Rank IC', nameLocation: 'middle', nameGap: 42, axisLabel: { fontSize: 10 } },
    series: [
      {
        name: '月度 Rank IC',
        type: 'bar',
        data: d.ic.map((v) => +v.toFixed(4)),
        itemStyle: {
          color: (p: any) => (p.value >= 0 ? C.value.success : C.value.danger),
          opacity: 0.65,
        },
        barWidth: '60%',
      },
      {
        name: `均值 ${d.mean?.toFixed(3)}`,
        type: 'line',
        data: d.ic.map(() => d.mean),
        symbol: 'none',
        lineStyle: { width: 1.5, color: C.value.primary },
        markLine: {
          silent: true,
          symbol: 'none',
          data: [{ yAxis: 0, lineStyle: { color: C.value.slate }, label: { formatter: '0' } }],
        },
      },
    ],
  }
})
</script>

<template>
  <div class="pe-ic">
    <div v-if="loading" class="status">数据加载中…</div>
    <div v-else-if="error" class="status">数据不可用</div>
    <template v-else-if="data">
      <div class="stats">
        <span class="chip">样本 <strong>{{ data.n_obs }}</strong> 个月</span>
        <span class="chip">IC 均值 <strong>{{ data.mean?.toFixed(3) }}</strong></span>
        <span class="chip">IC 标准差 <strong>{{ data.std?.toFixed(3) }}</strong></span>
        <span class="chip">ICIR <strong>{{ data.icir?.toFixed(2) }}</strong></span>
      </div>
      <ThemedChart class="chart" :option="option" autoresize />
    </template>
  </div>
</template>

<style scoped>
.pe-ic { padding: 16px; }
.status { height: 300px; display: flex; align-items: center; justify-content: center; color: var(--text-3); font-size: 14px; }
.chart { height: 300px; }
.stats { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
.chip {
  font-size: 12.5px; color: var(--text-3);
  padding: 4px 10px; border-radius: 999px; background: var(--bg-hover);
}
.chip strong { color: var(--primary); }
</style>
