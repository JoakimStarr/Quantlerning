<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, MarkLineComponent } from 'echarts/components'
import { fetchMarketPeDistribution } from '@/api'

use([CanvasRenderer, BarChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent])

// 全市场 PE 分布（真实 quantlab 数据快照）
// 看估值分布是「右偏 + 负值桶（亏损股）」——所以要用分位而非孤立数字

const props = defineProps<{
  params?: Record<string, unknown>
}>()

const tradeDate = ref(typeof props.params?.date === 'string' ? props.params.date : '2026-08-10')

const dist = ref<{ date: string; count: number; median: number | null; p90: number | null; bins: { lo: number | null; hi: number; count: number }[] } | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)

async function load() {
  loading.value = true
  error.value = null
  try {
    dist.value = await fetchMarketPeDistribution(tradeDate.value, 40)
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

onMounted(load)

// 只画 PE > 0 的桶，且截断到 99 分位以内以便观察主体；负值桶单独标注
const truncated = computed(() => {
  if (!dist.value) return null
  const pos = dist.value.bins.filter((b): b is { lo: number; hi: number; count: number } => b.lo !== null)
  const maxHi = dist.value.p90 ? Math.min(Math.max(pos[pos.length - 1].hi, 50), 200) : 200
  const visible = pos.filter((b) => b.lo < maxHi)
  return { negCount: dist.value.bins[0].count, visible }
})

const option = computed(() => {
  if (!dist.value || !truncated.value) return {}
  const { visible } = truncated.value
  const marks: any[] = []
  if (dist.value.median !== null)
    marks.push({ xAxis: dist.value.median, label: { formatter: `中位数 ${dist.value.median}`, position: 'insideEndTop' }, lineStyle: { color: C.value.primary, type: 'dashed' } })
  if (dist.value.p90 !== null)
    marks.push({ xAxis: dist.value.p90, label: { formatter: `90分位 ${dist.value.p90}`, position: 'insideEndTop' }, lineStyle: { color: C.value.danger, type: 'dashed' } })
  return {
    animation: true,
    grid: { left: 52, right: 24, top: 36, bottom: 56 },
    tooltip: { trigger: 'axis' },
    legend: { top: 0, textStyle: { fontSize: 12 } },
    xAxis: { type: 'value', name: 'PE', nameLocation: 'middle', nameGap: 28, min: 0, axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', name: '股票数', nameLocation: 'middle', nameGap: 34, axisLabel: { fontSize: 10 } },
    series: [
      {
        name: 'PE 分布',
        type: 'bar',
        data: visible.map((b) => [b.lo, b.count]),
        barWidth: '90%',
        itemStyle: { color: C.value.primary, opacity: 0.7 },
        markLine: marks.length ? { silent: true, symbol: 'none', data: marks } : undefined,
      },
    ],
  }
})
</script>

<template>
  <div class="ped">
    <div v-if="loading" class="status">数据加载中…</div>
    <div v-else-if="error" class="status">数据不可用</div>
    <template v-else-if="dist && truncated">
      <div class="result">
        <div class="result-item">
          <span class="result-label">快照日期</span>
          <strong class="result-value sm">{{ dist.date }}</strong>
        </div>
        <div class="result-item">
          <span class="result-label">样本数</span>
          <strong class="result-value">{{ dist.count }}</strong>
        </div>
        <div class="result-item">
          <span class="result-label">中位数</span>
          <strong class="result-value primary">{{ dist.median }}</strong>
        </div>
        <div class="result-item">
          <span class="result-label">90 分位</span>
          <strong class="result-value red">{{ dist.p90 }}</strong>
        </div>
        <div class="result-item">
          <span class="result-label">亏损股（PE≤0）</span>
          <strong class="result-value warn">{{ truncated.negCount }} 只</strong>
        </div>
      </div>
      <ThemedChart class="chart" :option="option" autoresize />
      <div class="tip">
        分布严重右偏：一半股票 PE 低于中位数，但尾部拖到 100+；另有 {{ truncated.negCount }} 只亏损股（PE 为负或缺失）。所以判断个股贵贱要用「分位」，不能孤立看 PE=30。
      </div>
    </template>
  </div>
</template>

<style scoped>
.ped { padding: 16px; }
.status { height: 300px; display: flex; align-items: center; justify-content: center; color: var(--text-3); font-size: 14px; }
.chart { height: 320px; }
.result { display: flex; gap: 20px; margin-bottom: 12px; padding: 12px 16px; background: var(--primary-soft); border-radius: var(--radius-sm); flex-wrap: wrap; }
.result-item { display: flex; flex-direction: column; gap: 2px; }
.result-label { font-size: 12px; color: var(--text-3); }
.result-value { font-size: 18px; font-weight: 700; }
.result-value.primary { color: var(--primary); }
.result-value.red { color: var(--danger, #dc2626); }
.result-value.warn { color: var(--warning, #d97706); }
.result-value.sm { font-size: 15px; color: var(--text-2); font-family: var(--font-mono); }
.tip { margin-top: 10px; font-size: 12.5px; color: var(--text-3); line-height: 1.7; }
</style>
