<script setup lang="ts">
import { computed, ref } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, MarkPointComponent, MarkLineComponent, TitleComponent } from 'echarts/components'
import { useStockDaily } from '@/composables/useStockDaily'
import { maCrossSignal, shiftPosition, strategyNav, backtestArrays } from '@/utils/strategies'

use([CanvasRenderer, BarChart, GridComponent, TooltipComponent, LegendComponent, MarkPointComponent, MarkLineComponent, TitleComponent])

// 锯齿现象演示（真实茅台 2020-2026，均线交叉）：
// 主图 = 样本内（2020~2023）快线参数扫描年化柱状图，展示锯齿形态 + 全局最优 + ±20% 邻域
// 副图 = 样本外（2024~2026）同参数年化，展示「样本内冠军」换窗口塌陷 → 参数过拟合的证据
const props = defineProps<{
  params?: Record<string, unknown>
}>()

const code = computed(() => (typeof props.params?.code === 'string' ? props.params.code : 'sh600519'))
const start = computed(() => (typeof props.params?.start === 'string' ? props.params.start : '2020-01-01'))
const end = computed(() => (typeof props.params?.end === 'string' ? props.params.end : '2026-08-10'))
const { data, loading, error } = useStockDaily(code, start.value, end.value)

const SLOWS = [20, 40, 60, 90, 120]
const slowIdx = ref(2) // 默认 MA60
const slow = computed(() => SLOWS[slowIdx.value])
// 样本外起点（与课程「2020-2026 全窗口、2024 起为样本外」口径一致）
const SPLIT_DATE = '2024-01-01'

/** 几何年化：净值 100 起点，(last/100)^(252/n) − 1，n 为收益日数 */
function annFromNav(last: number, n: number): number {
  if (!(n > 0) || !isFinite(last) || last <= 0) return 0
  return (last / 100) ** (252 / n) - 1
}

/** 对一段行数据做均线交叉，返回各快线参数的年化 */
function scanAnn(closes: number[], ret: number[], fmax: number, slowP: number): number[] {
  const n = ret.length - 1
  const out: number[] = []
  for (let f = 5; f <= fmax; f++) {
    const pos = shiftPosition(maCrossSignal(closes, f, slowP))
    const nav = strategyNav(ret, pos)
    out.push(annFromNav(nav[nav.length - 1], n))
  }
  return out
}

const com = computed(() => {
  if (!data.value) return null
  const arr = backtestArrays(data.value)
  const cut = arr.dates.findIndex((d) => d >= SPLIT_DATE)
  if (cut <= 60) return null // 数据过短时无法切分
  const innerCloses = arr.closes.slice(0, cut)
  const innerRet = arr.ret.slice(0, cut)
  const outerCloses = arr.closes.slice(cut)
  const outerRet = arr.ret.slice(cut)
  const fmax = Math.min(slow.value - 1, 50)
  const fasts: number[] = []
  for (let f = 5; f <= fmax; f++) fasts.push(f)
  const annsIn = scanAnn(innerCloses, innerRet, fmax, slow.value)
  const annsOut = scanAnn(outerCloses, outerRet, fmax, slow.value)

  // 样本内全局最优及其 ±20% 邻域
  let bestF = fasts[0]
  let bestV = -Infinity
  fasts.forEach((f, i) => {
    if (annsIn[i] > bestV) {
      bestV = annsIn[i]
      bestF = f
    }
  })
  let neighMin = Infinity
  let neighMax = -Infinity
  fasts.forEach((f, i) => {
    if (Math.abs(f - bestF) / bestF <= 0.2) {
      if (annsIn[i] < neighMin) neighMin = annsIn[i]
      if (annsIn[i] > neighMax) neighMax = annsIn[i]
    }
  })
  const outerOfBest = annsOut[fasts.indexOf(bestF)]
  return {
    fasts,
    annsIn,
    annsOut,
    bestF,
    bestV,
    neighMin: neighMin === Infinity ? 0 : neighMin,
    neighMax: neighMax === -Infinity ? 0 : neighMax,
    outerOfBest,
    splitLabel: SPLIT_DATE,
  }
})

// 主图：样本内参数扫描柱状图（锯齿 + 最优 + 邻域高亮）
const mainOption = computed(() => {
  const c = com.value
  if (!c) return {}
  const isNeigh = (f: number) => Math.abs(f - c.bestF) / c.bestF <= 0.2
  const data = c.fasts.map((f, i) => ({
    value: +(c.annsIn[i] * 100).toFixed(2),
    itemStyle: { color: f === c.bestF ? C.value.success : isNeigh(f) ? C.value.warning : C.value.slate },
  }))
  return {
    animation: true,
    grid: { left: 56, right: 24, top: 40, bottom: 44 },
    title: [
      {
        text: `① 样本内（2020~2023）快线扫描年化：锯齿形态（慢线 MA${slow.value}）`,
        left: 52,
        top: 8,
        textStyle: { fontSize: 12, fontWeight: 600, color: C.value.text },
      },
    ],
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (ps: any[]) => {
        const p = ps[0]
        const f = c.fasts[p.dataIndex]
        const v = (p.value as number).toFixed(1)
        const tag = f === c.bestF ? '（全局最优）' : isNeigh(f) ? '（±20% 邻域）' : ''
        return `MA${f}：年化 ${v}%${tag}`
      },
    },
    xAxis: { type: 'category', data: c.fasts.map((f) => `MA${f}`), axisLabel: { fontSize: 10, interval: 4, hideOverlap: true } },
    yAxis: {
      type: 'value',
      name: '年化 %',
      nameLocation: 'middle',
      nameGap: 44,
      scale: true,
      axisLabel: { fontSize: 10, formatter: (v: number) => `${v.toFixed(0)}%` },
    },
    series: [
      {
        name: '样本内年化',
        type: 'bar',
        barMaxWidth: 22,
        data,
        markPoint: {
          symbol: 'pin',
          symbolSize: 40,
          label: { show: true, fontSize: 10, color: '#fff', formatter: '最优' },
          data: [
            {
              coord: [c.fasts.indexOf(c.bestF), Number((c.bestV * 100).toFixed(1))],
              value: '最优',
              itemStyle: { color: C.value.primary },
            },
          ],
        },
      },
    ],
  }
})

// 副图：样本外同参数年化（样本内冠军标红，展示塌陷/反超）
const outerOption = computed(() => {
  const c = com.value
  if (!c) return {}
  const data = c.fasts.map((f, i) => ({
    value: +(c.annsOut[i] * 100).toFixed(2),
    itemStyle: { color: f === c.bestF ? C.value.danger : C.value.slate },
  }))
  return {
    animation: true,
    grid: { left: 56, right: 24, top: 40, bottom: 44 },
    title: [
      {
        text: '② 样本外（2024~2026）同一批参数：冠军位置是否失效？',
        left: 52,
        top: 8,
        textStyle: { fontSize: 12, fontWeight: 600, color: C.value.text },
      },
    ],
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (ps: any[]) => {
        const p = ps[0]
        const f = c.fasts[p.dataIndex]
        const v = (p.value as number).toFixed(1)
        const tag = f === c.bestF ? '（样本内冠军 → 此处看它是否塌陷）' : ''
        return `MA${f}：样本外年化 ${v}%${tag}`
      },
    },
    xAxis: { type: 'category', data: c.fasts.map((f) => `MA${f}`), axisLabel: { fontSize: 10, interval: 4, hideOverlap: true } },
    yAxis: {
      type: 'value',
      name: '年化 %',
      nameLocation: 'middle',
      nameGap: 44,
      scale: true,
      axisLabel: { fontSize: 10, formatter: (v: number) => `${v.toFixed(0)}%` },
    },
    series: [
      {
        name: '样本外年化',
        type: 'bar',
        barMaxWidth: 22,
        data,
        markLine: {
          silent: true,
          symbol: 'none',
          data: [
            {
              xAxis: c.fasts.indexOf(c.bestF),
              lineStyle: { color: C.value.danger, type: 'dashed' },
              label: { formatter: `样本内冠军 MA${c.bestF}`, position: 'insideEndTop', fontSize: 10 },
            },
          ],
        },
      },
    ],
  }
})
</script>

<template>
  <div class="sw">
    <div v-if="loading" class="status">数据加载中…</div>
    <div v-else-if="error" class="status">数据不可用</div>
    <template v-else-if="com">
      <div class="result">
        <div class="result-item">
          <span class="result-label">样本内最优</span>
          <strong class="result-value" style="color: var(--success, #16a34a)">MA{{ com.bestF }} · {{ (com.bestV * 100).toFixed(1) }}%</strong>
        </div>
        <div class="result-item">
          <span class="result-label">同参数样本外</span>
          <strong class="result-value" style="color: var(--danger, #dc2626)">{{ (com.outerOfBest * 100).toFixed(1) }}%（Δ {{ ((com.outerOfBest - com.bestV) * 100).toFixed(1) }}）</strong>
        </div>
        <div class="result-item">
          <span class="result-label">邻域年化区间（±20%）</span>
          <strong class="result-value" style="color: var(--warning, #d97706)">{{ (com.neighMin * 100).toFixed(1) }}% ~ {{ (com.neighMax * 100).toFixed(1) }}%</strong>
        </div>
      </div>
      <ThemedChart class="chart main" :option="mainOption" autoresize />
      <ThemedChart class="chart" :option="outerOption" autoresize />
      <div class="controls">
        <div class="control-row">
          <span class="control-label">慢线 MA</span>
          <input v-model.number="slowIdx" type="range" min="0" max="4" step="1" class="slider" />
          <span class="control-value">{{ slow }}</span>
        </div>
        <p class="hint">先看①：样本内各快线年化剧烈跳动成「锯齿」——绿色是最优参数，黄色是它 ±20% 的邻域。再看②：同一批参数换到样本外，绿色那根（红虚线标出）大多塌陷甚至垫底。样本内越亮的冠军，样本外越不可信——这就是「用噪声调出来的参数」。</p>
      </div>
    </template>
  </div>
</template>

<style scoped>
.sw { padding: 16px; }
.status { height: 360px; display: flex; align-items: center; justify-content: center; color: var(--text-3); font-size: 14px; }
.chart { height: 300px; }
.chart.main { height: 300px; }
.result { display: flex; gap: 22px; margin-bottom: 12px; padding: 12px 16px; background: var(--primary-soft); border-radius: var(--radius-sm); flex-wrap: wrap; }
.result-item { display: flex; flex-direction: column; gap: 2px; }
.result-label { font-size: 12px; color: var(--text-3); }
.result-value { font-size: 15px; font-weight: 700; }
.controls { margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--border); display: flex; flex-direction: column; gap: 10px; }
.control-row { display: flex; align-items: center; gap: 12px; }
.control-label { width: 72px; font-size: 13px; color: var(--text-2); flex-shrink: 0; }
.slider { flex: 1; accent-color: var(--primary); cursor: pointer; }
.control-value { width: 44px; font-size: 13px; font-weight: 600; color: var(--primary); text-align: right; flex-shrink: 0; }
.hint { margin-top: 10px; font-size: 12px; color: var(--text-3); line-height: 1.7; }
</style>
