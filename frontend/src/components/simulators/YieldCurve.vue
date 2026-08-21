<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { fetchMacro } from '@/api'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent])

// 中国国债收益率曲线（真实数据，macro_indicator）
// 期限：2Y / 5Y / 10Y / 30Y；滑块选日期，观察曲线形状与期限利差
const props = defineProps<{
  params?: Record<string, unknown>
}>()

const start = computed(() => (typeof props.params?.start === 'string' ? props.params.start : '2024-01-01'))
const end = computed(() => (typeof props.params?.end === 'string' ? props.params.end : '2024-12-31'))

type TreasuryRow = { date: string; field: string; value: number }
const loading = ref(true)
const error = ref<string | null>(null)
const rows = ref<TreasuryRow[]>([])

// 按日期对齐的各期限收益率（以 trsy10y 的交易日为准）
const dates = ref<string[]>([])
const curves = ref<Record<string, number[]>>({}) // field -> 与 dates 对齐的值数组
const spreads = ref<number[]>([]) // 10Y-2Y 期限利差
const idx = ref(0) // 当前选中日期下标

async function load() {
  loading.value = true
  error.value = null
  try {
    const raw = (await fetchMacro('TREASURY', start.value, end.value)) as TreasuryRow[]
    rows.value = raw
    // 按 field 分组
    const byField: Record<string, TreasuryRow[]> = {}
    for (const r of raw) (byField[r.field] ??= []).push(r)
    const tenorFields = ['trsy2y', 'trsy5y', 'trsy10y', 'trsy30y']
    // 以 trsy10y 日期为主轴
    const main = byField['trsy10y'] ?? []
    dates.value = main.map((r) => r.date)
    const tenor: Record<string, number[]> = {}
    for (const f of tenorFields) {
      const m = new Map(byField[f]?.map((r) => [r.date, r.value]) ?? [])
      // 缺失日期用最近的前值填充
      const arr: number[] = []
      let last: number | null = null
      for (const d of dates.value) {
        if (m.has(d)) last = m.get(d)!
        arr.push(last!)
      }
      tenor[f] = arr
    }
    curves.value = tenor
    const spread = new Map(byField['trsy_spread_10y2y']?.map((r) => [r.date, r.value]) ?? [])
    spreads.value = dates.value.map((d) => (spread.has(d) ? spread.get(d)! : NaN))
    idx.value = dates.value.length - 1 // 默认最新交易日
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

onMounted(load)

const terms = [2, 5, 10, 30] // 期限（年）

// 当前日期的收益率曲线点
const curvePoints = computed<[number, number][]>(() => {
  if (!dates.value.length) return []
  const i = idx.value
  const out: [number, number][] = []
  for (const t of terms) {
    const key = t === 2 ? 'trsy2y' : t === 5 ? 'trsy5y' : t === 10 ? 'trsy10y' : 'trsy30y'
    out.push([t, curves.value[key]?.[i] ?? NaN])
  }
  return out.filter((p) => !Number.isNaN(p[1]))
})

const currentDate = computed(() => dates.value[idx.value] ?? '')
const currentSpread = computed(() => {
  const v = spreads.value[idx.value]
  return Number.isNaN(v) ? null : v
})

// 全年期限利差范围（看曲线走平/走陡的幅度）
const spreadRange = computed(() => {
  const valid = spreads.value.filter((v) => !Number.isNaN(v))
  if (!valid.length) return null
  return { min: Math.min(...valid), max: Math.max(...valid) }
})

// 隐含远期利率 f(2→5)：由 2Y 与 5Y 即期利率推导
const impliedForward = computed(() => {
  const i = idx.value
  const s2 = curves.value['trsy2y']?.[i]
  const s5 = curves.value['trsy5y']?.[i]
  if (s2 == null || s5 == null || Number.isNaN(s2) || Number.isNaN(s5)) return null
  const f = Math.pow(Math.pow(1 + s5 / 100, 5) / Math.pow(1 + s2 / 100, 2), 1 / 3) - 1
  return f * 100
})

const option = computed(() => {
  if (!dates.value.length) return {}
  return {
    animation: false,
    grid: { left: 52, right: 28, top: 40, bottom: 40 },
    tooltip: {
      trigger: 'axis',
      formatter: (ps: any[]) => {
        const p = Array.isArray(ps) ? ps[0] : ps
        const t = p.value[0]
        return `期限 ${t}Y<br/>收益率 ${Number(p.value[1]).toFixed(2)}%`
      },
    },
    legend: { top: 0, textStyle: { fontSize: 12 }, data: [`国债收益率 ${currentDate.value}`] },
    xAxis: {
      type: 'value',
      name: '期限（年）',
      nameLocation: 'middle',
      nameGap: 28,
      min: 0,
      max: 32,
      interval: 5,
      axisLabel: { fontSize: 11, formatter: '{value}Y' },
    },
    yAxis: {
      type: 'value',
      name: '收益率（%）',
      nameLocation: 'middle',
      nameGap: 40,
      axisLabel: { fontSize: 11, formatter: '{value}%' },
    },
    series: [
      {
        name: `国债收益率 ${currentDate.value}`,
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 8,
        data: curvePoints.value,
        lineStyle: { width: 3, color: C.value.primary },
        itemStyle: { color: C.value.primary },
        label: { show: true, position: 'top', fontSize: 11, formatter: (p: any) => `${p.value[1].toFixed(2)}%` },
        connectNulls: true,
      },
    ],
  }
})
</script>

<template>
  <div class="yield-curve">
    <div v-if="loading" class="status">数据加载中…</div>
    <div v-else-if="error" class="status">数据不可用</div>
    <template v-else-if="dates.length">
      <div class="stats">
        <span class="chip">日期 <strong>{{ currentDate }}</strong></span>
        <span class="chip">10Y−2Y 利差 <strong>{{ currentSpread != null ? currentSpread.toFixed(2) + '%' : '—' }}</strong></span>
        <span class="chip">全年利差区间 <strong v-if="spreadRange">{{ spreadRange.min.toFixed(2) }}% ~ {{ spreadRange.max.toFixed(2) }}%</strong></span>
        <span class="chip">隐含远期 f(2→5) <strong v-if="impliedForward != null">{{ impliedForward.toFixed(2) }}%</strong></span>
      </div>

      <ThemedChart class="chart" :option="option" autoresize />

      <div class="controls">
        <div class="control-row">
          <span class="control-label">交易日</span>
          <input v-model.number="idx" type="range" min="0" :max="dates.length - 1" step="1" class="slider" />
          <span class="control-value">{{ currentDate }}</span>
        </div>
      </div>

      <div class="tip">
        <template v-if="currentSpread != null">
          {{ currentDate }} 10Y−2Y 期限利差 {{ currentSpread.toFixed(2) }}%：
          {{ currentSpread > 0 ? '曲线正常（短低长高），长端要求更高的时间补偿' : '曲线倒挂（短高长低），常被视为衰退信号' }}。
          2024 全年利差在 {{ spreadRange?.min.toFixed(2) }}% ~ {{ spreadRange?.max.toFixed(2) }}% 之间波动。
          隐含远期 f(2→5) 由 2Y 与 5Y 即期利率无套利推导——曲线本身就「定价」了市场对未来利率的预期。
        </template>
      </div>
    </template>
  </div>
</template>

<style scoped>
.yield-curve { padding: 16px; }
.status { height: 300px; display: flex; align-items: center; justify-content: center; color: var(--text-3); font-size: 14px; }
.chart { height: 300px; }
.stats { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
.chip {
  font-size: 12.5px; color: var(--text-3);
  padding: 4px 10px; border-radius: 999px; background: var(--bg-hover);
}
.chip strong { color: var(--primary); }
.controls { margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border); }
.control-row { display: flex; align-items: center; gap: 12px; }
.control-label { width: 64px; font-size: 13px; color: var(--text-2); flex-shrink: 0; }
.slider { flex: 1; accent-color: var(--primary); cursor: pointer; }
.control-value { width: 96px; font-size: 12.5px; font-weight: 600; color: var(--primary); text-align: right; flex-shrink: 0; }
.tip { margin-top: 10px; font-size: 12.5px; color: var(--text-3); line-height: 1.7; }
</style>
