<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { fetchStockFinancials, type StockFinancials } from '@/api'

use([CanvasRenderer, BarChart, LineChart, GridComponent, TooltipComponent, LegendComponent])

// 净利润 vs 经营现金流（真实财务数据）：利润含金量的直观对比
const props = defineProps<{
  params?: Record<string, unknown>
}>()

const code = computed(() => (typeof props.params?.code === 'string' ? props.params.code : 'sh600519'))
const fin = ref<StockFinancials | null>(null)
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    fin.value = await fetchStockFinancials(code.value, 60)
  } catch {
    error.value = '数据不可用'
  } finally {
    loading.value = false
  }
})

// 年报序列（时间升序），只保留净利与 OCF 都有值的年份
const annual = computed(() => {
  const ps = (fin.value?.periods ?? []).filter((p) => p.report_date.endsWith('12-31')).reverse()
  return ps
    .filter((p) => typeof p.netprofit === 'number' && typeof p.ocf === 'number')
    .map((p) => ({
      date: p.report_date.slice(0, 4),
      np: (p.netprofit as number) / 1e8,
      ocf: (p.ocf as number) / 1e8,
      ratio: typeof p.ocf_to_np === 'number' ? +(p.ocf_to_np as number).toFixed(2) : null,
    }))
})

const option = computed(() => {
  const a = annual.value
  if (!a.length) return {}
  return {
    animation: true,
    tooltip: {
      trigger: 'axis',
      formatter: (ps: any[]) => {
        const date = ps[0]?.name ?? ''
        let html = `${date} 年<br/>`
        for (const q of ps) {
          if (q.seriesName === '净现比') {
            if (q.value !== null) html += `　净现比 ${q.value}`
          } else if (q.value !== null) {
            html += `　${q.seriesName} ${q.value} 亿`
          }
        }
        return html
      },
    },
    legend: { top: 0, textStyle: { fontSize: 12 }, data: ['净利润', '经营现金流', '净现比'] },
    grid: { left: 56, right: 48, top: 34, bottom: 40 },
    xAxis: { type: 'category', data: a.map((x) => x.date), axisLabel: { fontSize: 10 } },
    yAxis: [
      { type: 'value', name: '亿元', nameTextStyle: { fontSize: 10 }, axisLabel: { fontSize: 10 }, splitLine: { lineStyle: { color: C.value.grid } } },
      { type: 'value', name: '净现比', nameTextStyle: { fontSize: 10 }, min: 0, axisLabel: { fontSize: 10 }, splitLine: { show: false } },
    ],
    series: [
      { name: '净利润', type: 'bar', yAxisIndex: 0, data: a.map((x) => +x.np.toFixed(0)), itemStyle: { color: C.value.primary }, barMaxWidth: 22 },
      { name: '经营现金流', type: 'bar', yAxisIndex: 0, data: a.map((x) => +x.ocf.toFixed(0)), itemStyle: { color: C.value.slateStrong, opacity: 0.85 }, barMaxWidth: 22 },
      { name: '净现比', type: 'line', yAxisIndex: 1, data: a.map((x) => x.ratio), symbol: 'circle', symbolSize: 5, lineStyle: { width: 2, color: C.value.warning }, itemStyle: { color: C.value.warning } },
    ],
  }
})

// 最新年报的净现比用于结果卡
const latestRatio = computed(() => {
  const r = annual.value[annual.value.length - 1]?.ratio
  return r !== null && r !== undefined ? r : null
})
</script>

<template>
  <div class="pcc">
    <div v-if="loading" class="status">数据加载中…</div>
    <div v-else-if="error" class="status">{{ error }}</div>
    <template v-else-if="annual.length">
      <div class="cards">
        <div class="card"><span>数据范围</span><strong>{{ annual[0].date }} ~ {{ annual[annual.length - 1].date }}</strong></div>
        <div class="card"><span>最新净现比</span><strong>{{ latestRatio !== null ? latestRatio : '—' }}</strong></div>
        <div class="card"><span>净现比 ≈ 1</span><strong>利润含金量正常</strong></div>
      </div>
      <ThemedChart class="chart" :option="option" autoresize />
      <p class="hint">
        蓝色柱是净利润、灰色柱是经营现金流（OCF），橙线是净现比。两排柱子高度越接近，利润含金量越高；灰色明显低于蓝色时，说明当年利润没等额变成现金——茅台 2022 年（净现比 0.59）就是典型：现金流滞后于利润，但后一年（0.89）回补。若一家公司常年「蓝高灰矮」，就要警惕账面富贵（p2-l3 排雷表）。
      </p>
    </template>
  </div>
</template>

<style scoped>
.pcc { padding: 16px; }
.status { height: 380px; display: flex; align-items: center; justify-content: center; color: var(--text-3); font-size: 14px; }
.chart { height: 340px; }
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 10px; margin-bottom: 12px; }
.card { display: flex; flex-direction: column; gap: 2px; padding: 9px 12px; background: var(--primary-soft); border-radius: var(--radius-sm); font-size: 11.5px; color: var(--text-3); }
.card strong { font-size: 15px; font-weight: 700; color: var(--text-1); }
.hint { margin-top: 12px; font-size: 12px; color: var(--text-3); line-height: 1.7; }
</style>
