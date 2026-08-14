<script setup lang="ts">
import { computed } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C, withAlpha } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, DataZoomComponent } from 'echarts/components'
import { useStockDaily } from '@/composables/useStockDaily'

use([CanvasRenderer, BarChart, LineChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent])

// 真实茅台 2024：日收益柱状 + 20/60 日滚动年化波动曲线
// 直观看到「波动聚集」——大波动扎堆，平静后接平静

const props = defineProps<{
  params?: Record<string, unknown>
}>()

const code = computed(() => (typeof props.params?.code === 'string' ? props.params.code : 'sh600519'))
const { data, loading, error } = useStockDaily(code)

const series = computed(() => {
  if (!data.value || data.value.length === 0) return null
  const dates = data.value.map((d) => d.date)
  const rets = data.value.map((d) => d.pct_chg).slice(1) // 复权收益，不含首日
  const dDates = dates.slice(1)
  const vol20: (number | null)[] = []
  const vol60: (number | null)[] = []
  for (let i = 0; i < rets.length; i++) {
    vol20.push(i >= 19 ? Number((std(rets.slice(i - 19, i + 1)) * Math.sqrt(252)).toFixed(2)) : null)
    vol60.push(i >= 59 ? Number((std(rets.slice(i - 59, i + 1)) * Math.sqrt(252)).toFixed(2)) : null)
  }
  return { dDates, rets, vol20, vol60 }
})

function std(a: number[]): number {
  const m = a.reduce((s, v) => s + v, 0) / a.length
  return Math.sqrt(a.reduce((s, v) => s + (v - m) ** 2, 0) / (a.length - 1))
}

const option = computed(() => {
  if (!series.value) return {}
  const { dDates, rets, vol20, vol60 } = series.value
  return {
    animation: true,
    grid: [{ left: 52, right: 20, top: 40, height: '52%' }, { left: 52, right: 20, top: '70%', height: '22%' }],
    tooltip: {
      trigger: 'axis',
      formatter: (ps: any[]) => {
        const arr = Array.isArray(ps) ? ps : [ps]
        return arr.map((p: any) => {
          const v = Array.isArray(p.value) ? p.value[1] : p.value
          return `${p.seriesName}：${v == null || Number.isNaN(v) ? '—' : Number(v).toFixed(2)}`
        }).join('<br/>')
      },
    },
    legend: { top: 0, textStyle: { fontSize: 12 } },
    dataZoom: [{ type: 'inside', xAxisIndex: [0, 1] }],
    xAxis: [
      { type: 'category', data: dDates, gridIndex: 0, axisLabel: { fontSize: 10, hideOverlap: true } },
      { type: 'category', data: dDates, gridIndex: 1, axisLabel: { show: false } },
    ],
    yAxis: [
      { type: 'value', name: '日收益 %', nameLocation: 'middle', nameGap: 36, gridIndex: 0, axisLabel: { fontSize: 10 } },
      { type: 'value', name: '年化波动 %', nameLocation: 'middle', nameGap: 42, gridIndex: 1, scale: true, axisLabel: { fontSize: 10 } },
    ],
    series: [
      {
        name: '日收益',
        type: 'bar',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: rets.map((v) => +v.toFixed(2)),
        itemStyle: { color: (p: any) => (p.value >= 0 ? withAlpha(C.value.primary, 0.6) : withAlpha(C.value.danger, 0.6)) },
      },
      { name: '20日滚动波动', type: 'line', xAxisIndex: 1, yAxisIndex: 1, data: vol20, symbol: 'none', lineStyle: { width: 2, color: C.value.primary } },
      { name: '60日滚动波动', type: 'line', xAxisIndex: 1, yAxisIndex: 1, data: vol60, symbol: 'none', lineStyle: { width: 1.5, color: C.value.warning } },
    ],
  }
})
</script>

<template>
  <div class="vc">
    <div v-if="loading" class="status">数据加载中…</div>
    <div v-else-if="error" class="status">数据不可用</div>
    <template v-else-if="series">
      <ThemedChart class="chart" :option="option" autoresize />
      <div class="tip">
        注意日收益柱状：剧烈波动（2024-09 下跌、09-26 大涨、10-09 大跌）总是扎堆出现，而 6-8 月相对平静——这就是波动聚集。20 日滚动波动曲线清晰呈现「波动有记忆」。
      </div>
    </template>
  </div>
</template>

<style scoped>
.vc { padding: 16px; }
.status { height: 300px; display: flex; align-items: center; justify-content: center; color: var(--text-3); font-size: 14px; }
.chart { height: 380px; }
.tip { margin-top: 10px; font-size: 12.5px; color: var(--text-3); line-height: 1.7; }
</style>
