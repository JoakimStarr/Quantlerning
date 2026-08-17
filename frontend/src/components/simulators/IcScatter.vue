<script setup lang="ts">
// PE 因子 IC 散点（真实数据）：月末全市场各股票 PE 百分位 vs 下月收益
// 教学点：把 IC=相关系数 从公式变可见——散点整体趋势的斜率即 PE 因子方向
import { computed, onMounted, ref } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { ScatterChart, LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, MarkLineComponent } from 'echarts/components'
import { fetchIcScatter } from '@/api'

use([CanvasRenderer, ScatterChart, LineChart, GridComponent, TooltipComponent, MarkLineComponent])

const loading = ref(true)
const error = ref<string | null>(null)
const data = ref<Awaited<ReturnType<typeof fetchIcScatter>> | null>(null)

async function load() {
  loading.value = true
  error.value = null
  try {
    data.value = await fetchIcScatter('2018-01-01', '2026-08-10', 8000)
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

onMounted(load)

// 简单线性回归 y = a + bx，供趋势线（教学够用）
function fitLine(pts: { x: number; y: number }[]) {
  const n = pts.length
  const mx = pts.reduce((s, p) => s + p.x, 0) / n
  const my = pts.reduce((s, p) => s + p.y, 0) / n
  let num = 0
  let den = 0
  for (const p of pts) {
    num += (p.x - mx) * (p.y - my)
    den += (p.x - mx) ** 2
  }
  const b = den === 0 ? 0 : num / den
  const a = my - b * mx
  return { a, b }
}

const option = computed(() => {
  if (!data.value) return {}
  const d = data.value
  const { a, b } = fitLine(d.points)
  const x0 = 0
  const x1 = 1
  return {
    animation: false,
    grid: { left: 58, right: 20, top: 30, bottom: 44 },
    tooltip: {
      trigger: 'item',
      formatter: (p: any) =>
        `${p.data.date}<br/>PE 百分位：${(p.data.x * 100).toFixed(1)}%<br/>下月收益：${p.data.y.toFixed(2)}%`,
    },
    xAxis: {
      type: 'value',
      name: 'PE 百分位（低→高）',
      nameLocation: 'middle',
      nameGap: 30,
      min: 0,
      max: 1,
      axisLabel: { fontSize: 10, formatter: (v: number) => `${Math.round(v * 100)}%` },
    },
    yAxis: {
      type: 'value',
      name: '下月收益（%）',
      nameLocation: 'middle',
      nameGap: 38,
      axisLabel: { fontSize: 10 },
    },
    series: [
      {
        name: '股票（月度）',
        type: 'scatter',
        symbolSize: 3.5,
        data: d.points.map((p) => ({ value: [p.x, p.y], date: p.date })),
        itemStyle: { color: C.value.primary, opacity: 0.35 },
      },
      {
        name: '趋势线',
        type: 'line',
        data: [
          [x0, a + b * x0],
          [x1, a + b * x1],
        ],
        symbol: 'none',
        lineStyle: { color: C.value.danger, width: 2, type: 'dashed' },
        markLine: {
          silent: true,
          symbol: 'none',
          data: [{ xAxis: 0, label: { formatter: 'PE 最低', position: 'insideEndBottom' }, lineStyle: { color: C.value.text, type: 'dotted' } }],
        },
      },
    ],
  }
})
</script>

<template>
  <div class="ic-scatter">
    <div v-if="loading" class="status">数据加载中…</div>
    <div v-else-if="error" class="status">数据不可用</div>
    <template v-else-if="data">
      <div class="stats">
        <span class="chip">样本 <strong>{{ data.n }}</strong> 点</span>
        <span class="chip">月份 <strong>{{ data.n_months }}</strong></span>
        <span class="chip">2018-2026 全市场</span>
      </div>
      <ThemedChart class="chart" :option="option" autoresize />
    </template>
  </div>
</template>

<style scoped>
.ic-scatter { padding: 16px; }
.status { height: 300px; display: flex; align-items: center; justify-content: center; color: var(--text-3); font-size: 14px; }
.chart { height: 320px; }
.stats { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
.chip {
  font-size: 12.5px; color: var(--text-3);
  padding: 4px 10px; border-radius: 999px; background: var(--bg-hover);
}
.chip strong { color: var(--primary); }
</style>
