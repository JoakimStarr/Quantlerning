<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, MarkLineComponent } from 'echarts/components'
import { fetchIcDistribution } from '@/api'

use([CanvasRenderer, BarChart, GridComponent, TooltipComponent, MarkLineComponent])

// 161 个真实因子的 IC 分布：IC 值聚集在 0 附近，极少数偏离 >3%
// 教学点：横截面因子 IC 的绝对值普遍很小，好因子是「稳定的小正向 IC」
const loading = ref(true)
const error = ref<string | null>(null)
const data = ref<Awaited<ReturnType<typeof fetchIcDistribution>> | null>(null)

async function load() {
  loading.value = true
  error.value = null
  try {
    data.value = await fetchIcDistribution(30)
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
    grid: { left: 52, right: 20, top: 36, bottom: 40 },
    tooltip: {
      trigger: 'axis',
      formatter: (ps: any[]) => {
        const p = Array.isArray(ps) ? ps[0] : ps
        const bw = (d.hi - d.lo) / d.bins.length // 桶宽按实际分箱数计算
        return `IC ∈ [${(p.axisValue - bw).toFixed(4)}, ${(p.axisValue + bw).toFixed(4)}]<br/>因子数：${p.value[1]}`
      },
    },
    xAxis: {
      type: 'value',
      name: 'IC',
      nameLocation: 'middle',
      nameGap: 30,
      axisLabel: { fontSize: 10 },
    },
    yAxis: { type: 'value', name: '因子数', nameLocation: 'middle', nameGap: 36, axisLabel: { fontSize: 10 } },
    series: [
      {
        name: '因子数',
        type: 'bar',
        barWidth: '80%',
        data: d.bins.map((b) => [b.center, b.count]),
        itemStyle: { color: '#2563eb', opacity: 0.6 },
        markLine: {
          silent: true,
          symbol: 'none',
          data: [
            { xAxis: 0, label: { formatter: '0（无关）', position: 'insideEndTop' }, lineStyle: { color: '#dc2626', type: 'dashed' } },
            { xAxis: d.mean, label: { formatter: `均值 ${d.mean.toFixed(4)}`, position: 'insideEndBottom' }, lineStyle: { color: '#d97706', type: 'dotted' } },
          ],
        },
      },
    ],
  }
})
</script>

<template>
  <div class="ic-dist">
    <div v-if="loading" class="status">数据加载中…</div>
    <div v-else-if="error" class="status">数据不可用</div>
    <template v-else-if="data">
      <div class="stats">
        <span class="chip">因子数 <strong>{{ data.count }}</strong></span>
        <span class="chip">IC 中位数 <strong>{{ data.median.toFixed(4) }}</strong></span>
        <span class="chip">IC 均值 <strong>{{ data.mean.toFixed(4) }}</strong></span>
        <span class="chip">IC 90 分位 <strong>{{ data.p90.toFixed(4) }}</strong></span>
      </div>
      <VChart class="chart" :option="option" autoresize />
    </template>
  </div>
</template>

<style scoped>
.ic-dist { padding: 16px; }
.status { height: 300px; display: flex; align-items: center; justify-content: center; color: var(--text-3); font-size: 14px; }
.chart { height: 300px; }
.stats { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
.chip {
  font-size: 12.5px; color: var(--text-3);
  padding: 4px 10px; border-radius: 999px; background: var(--bg-hover);
}
.chip strong { color: var(--primary); }
</style>
