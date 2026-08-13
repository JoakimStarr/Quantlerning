<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, MarkLineComponent } from 'echarts/components'
import { fetchIndustryPe } from '@/api'

use([CanvasRenderer, BarChart, LineChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent])

// 行业 PE 中位数（真实数据）：同一交易日，不同行业的估值中枢差异巨大
// 教学点：行业效应是横截面因子的最大噪声源——比较个股 PE 必须「同行业内比较」
const props = defineProps<{
  params?: Record<string, unknown>
}>()

const tradeDate = computed(() => (typeof props.params?.trade_date === 'string' ? props.params.trade_date : '2024-06-28'))
const loading = ref(true)
const error = ref<string | null>(null)
const data = ref<Awaited<ReturnType<typeof fetchIndustryPe>> | null>(null)

async function load() {
  loading.value = true
  error.value = null
  try {
    data.value = await fetchIndustryPe(tradeDate.value, 30)
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

onMounted(load)

// 横向条形图：按 PE 中位数排序
const option = computed(() => {
  if (!data.value) return {}
  const inds = data.value.industries
  const names = inds.map((i) => i.industry)
  return {
    animation: false,
    grid: { left: 210, right: 40, top: 16, bottom: 40 },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (ps: any[]) => {
        const p = Array.isArray(ps) ? ps[0] : ps
        const i = inds[p.dataIndex]
        return `${i.industry}<br/>公司数：${i.n}<br/>PE 中位数：${i.median?.toFixed(1)}<br/>区间 [${i.lo?.toFixed(1)}, ${i.hi?.toFixed(1)}]`
      },
    },
    xAxis: { type: 'value', name: 'PE(TTM) 中位数', nameLocation: 'middle', nameGap: 30, axisLabel: { fontSize: 10 } },
    yAxis: { type: 'category', data: names, axisLabel: { fontSize: 9 } },
    series: [
      {
        name: 'PE 中位数',
        type: 'bar',
        data: inds.map((i) => (i.median ?? null)),
        itemStyle: { color: C.value.primary, opacity: 0.75 },
        markLine: {
          silent: true,
          symbol: 'none',
          data: [
            {
              xAxis: 20,
              label: { formatter: 'PE 20（市场常识分界）', position: 'insideEndTop' },
              lineStyle: { color: C.value.danger, type: 'dashed' },
            },
          ],
        },
      },
    ],
  }
})
</script>

<template>
  <div class="industry-pe">
    <div v-if="loading" class="status">数据加载中…</div>
    <div v-else-if="error" class="status">数据不可用</div>
    <template v-else-if="data">
      <p class="note">真实数据：{{ data.date }} 全市场 {{ data.count }} 个申万一级行业的 PE(TTM) 中位数。货币金融 5.4、地产 9.3，而成长行业动辄 30+——跨行业直接比 PE 会得出「银行便宜」的错误结论。</p>
      <ThemedChart class="chart" :option="option" autoresize />
    </template>
  </div>
</template>

<style scoped>
.industry-pe { padding: 16px; }
.status { height: 300px; display: flex; align-items: center; justify-content: center; color: var(--text-3); font-size: 14px; }
.chart { height: 460px; }
.note { font-size: 12.5px; color: var(--text-3); margin-bottom: 10px; line-height: 1.6; }
</style>
