<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, MarkLineComponent, MarkPointComponent } from 'echarts/components'
import { fetchMacro } from '@/api'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent, MarkPointComponent])

// CPI / PPI 真实月度序列（macro_indicator）
// 教学点：CPI 低通胀 + PPI 通缩 → 宽松预期 → 利率下行 → 资产重估

const props = defineProps<{
  params?: Record<string, unknown>
}>()

const start = computed(() => (typeof props.params?.start === 'string' ? props.params.start : '2020-01-01'))
const end = computed(() => (typeof props.params?.end === 'string' ? props.params.end : '2026-08-10'))

type MacroRow = { date: string; field: string; value: number }
const loading = ref(true)
const error = ref<string | null>(null)

// 按日期对齐的 CPI/PPI
const dates = ref<string[]>([])
const cpi = ref<number[]>([])
const ppi = ref<number[]>([])

async function load() {
  loading.value = true
  error.value = null
  try {
    const raw = (await fetchMacro('CPI', start.value, end.value)) as MacroRow[]
    const ppiRaw = (await fetchMacro('PPI', start.value, end.value)) as MacroRow[]
    const cpiMap = new Map(raw.map((r) => [r.date.slice(0, 7), r.value]))
    const ppiMap = new Map(ppiRaw.map((r) => [r.date.slice(0, 7), r.value]))
    const months = Array.from(new Set([...cpiMap.keys(), ...ppiMap.keys()])).sort()
    dates.value = months
    cpi.value = months.map((m) => cpiMap.get(m) ?? NaN)
    ppi.value = months.map((m) => ppiMap.get(m) ?? NaN)
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

onMounted(load)

// 最新值与全年范围
const latest = computed(() => {
  if (!dates.value.length) return null
  const i = dates.value.length - 1
  return { month: dates.value[i], cpi: cpi.value[i], ppi: ppi.value[i] }
})
const range = computed(() => {
  const valid = cpi.value.filter((v) => !Number.isNaN(v))
  const pValid = ppi.value.filter((v) => !Number.isNaN(v))
  if (!valid.length || !pValid.length) return null
  return { cpiMin: Math.min(...valid), cpiMax: Math.max(...valid), ppiMin: Math.min(...pValid), ppiMax: Math.max(...pValid) }
})

const option = computed(() => {
  if (!dates.value.length) return {}
  return {
    animation: false,
    grid: { left: 48, right: 24, top: 40, bottom: 40 },
    tooltip: {
      trigger: 'axis',
      formatter: (ps: any[]) => {
        const month = dates.value[ps[0].dataIndex]
        return ps.map((p) => `${p.marker}${p.seriesName}：${Number(p.value).toFixed(1)}%`).join('<br/>') + `<br/>${month}`
      },
    },
    legend: { top: 0, textStyle: { fontSize: 12 } },
    xAxis: {
      type: 'category',
      data: dates.value,
      axisLabel: { fontSize: 9, hideOverlap: true },
    },
    yAxis: {
      type: 'value',
      name: '同比 %',
      nameLocation: 'middle',
      nameGap: 34,
      axisLabel: { fontSize: 11, formatter: '{value}%' },
    },
    series: [
      {
        name: 'CPI',
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 5,
        connectNulls: true,
        data: cpi.value.map((v) => (Number.isNaN(v) ? null : +v.toFixed(1))),
        lineStyle: { width: 2.5, color: C.value.primary },
        itemStyle: { color: C.value.primary },
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: { color: C.value.slate, type: 'dashed' },
          data: [{ yAxis: 0 }],
        },
        markPoint: {
          symbolSize: 42,
          label: { fontSize: 10 },
          data: latest.value && !Number.isNaN(latest.value.cpi) ? [{ coord: [dates.value.length - 1, latest.value.cpi], value: `${latest.value.cpi.toFixed(1)}` }] : [],
        },
      },
      {
        name: 'PPI',
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 5,
        connectNulls: true,
        data: ppi.value.map((v) => (Number.isNaN(v) ? null : +v.toFixed(1))),
        lineStyle: { width: 2.5, color: C.value.danger },
        itemStyle: { color: C.value.danger },
      },
    ],
  }
})
</script>

<template>
  <div class="macro-series">
    <div v-if="loading" class="status">数据加载中…</div>
    <div v-else-if="error" class="status">数据不可用</div>
    <template v-else-if="dates.length">
      <div class="stats">
        <span class="chip" v-if="latest && !Number.isNaN(latest.cpi)">最新（{{ latest.month }}）CPI <strong>{{ latest.cpi.toFixed(1) }}%</strong></span>
        <span class="chip" v-if="latest && !Number.isNaN(latest.ppi)">PPI <strong>{{ latest.ppi.toFixed(1) }}%</strong></span>
        <span class="chip" v-if="range">区间 CPI <strong>{{ range.cpiMin.toFixed(1) }}% ~ {{ range.cpiMax.toFixed(1) }}%</strong></span>
        <span class="chip" v-if="range">PPI <strong>{{ range.ppiMin.toFixed(1) }}% ~ {{ range.ppiMax.toFixed(1) }}%</strong></span>
      </div>
      <ThemedChart class="chart" :option="option" autoresize />
      <div class="tip" v-if="latest && !Number.isNaN(latest.cpi) && !Number.isNaN(latest.ppi)">
        {{ latest.month }} CPI {{ latest.cpi.toFixed(1) }}%（{{ latest.cpi > 0 ? '温和正通胀' : '负通胀/通缩' }}）、PPI
        {{ latest.ppi.toFixed(1) }}%（{{ latest.ppi < 0 ? '工业品通缩' : '工业品扩张' }}）——
        这种「生产端偏弱、需求端温和」的组合对应宽松预期，推动利率下行、支撑资产估值（p1-l8 主线逻辑）。
      </div>
    </template>
  </div>
</template>

<style scoped>
.macro-series { padding: 16px; }
.status { height: 300px; display: flex; align-items: center; justify-content: center; color: var(--text-3); font-size: 14px; }
.chart { height: 300px; }
.stats { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
.chip {
  font-size: 12.5px; color: var(--text-3);
  padding: 4px 10px; border-radius: 999px; background: var(--bg-hover);
}
.chip strong { color: var(--primary); }
.tip { margin-top: 10px; font-size: 12.5px; color: var(--text-3); line-height: 1.7; }
</style>
