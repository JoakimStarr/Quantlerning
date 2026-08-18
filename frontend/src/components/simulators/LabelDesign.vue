<script setup lang="ts">
import { computed, ref } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C, withAlpha } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart, ScatterChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, MarkLineComponent, DataZoomComponent, TitleComponent } from 'echarts/components'
import { useStockDaily } from '@/composables/useStockDaily'
import { mean, std } from '@/utils/ml'

use([CanvasRenderer, BarChart, LineChart, ScatterChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent, DataZoomComponent, TitleComponent])

// 标签设计：把真实茅台 2024 日收益转成「前瞻 N 日收益」标签
// 教学点：分类标签 = 前瞻收益 > 阈值；阈值/周期决定正负样本比例（类别不平衡）
const props = defineProps<{
  params?: Record<string, unknown>
}>()

const code = computed(() => (typeof props.params?.code === 'string' ? props.params.code : 'sh600519'))
const { data, loading, error } = useStockDaily(code)

const horizon = ref(5) // 前瞻交易日数
const threshold = ref(0) // 标签阈值（%）

const rets = computed<number[]>(() => (data.value ? data.value.map((d) => d.pct_chg / 100).slice(1) : []))

// 前瞻 N 日累计收益（不含首日）
const fwdReturns = computed<number[]>(() => {
  const r = rets.value
  const out: number[] = []
  for (let i = 0; i < r.length; i++) {
    const h = Math.min(horizon.value, r.length - 1 - i)
    if (h <= 0) {
      out.push(0)
      continue
    }
    let prod = 1
    for (let k = 1; k <= h; k++) prod *= 1 + r[i + k]
    out.push(prod - 1)
  }
  return out
})

// 标签：前瞻收益 > 阈值 → 上涨(1)，否则下跌(0)
const labels = computed<number[]>(() => {
  const t = threshold.value / 100
  return fwdReturns.value.map((v) => (v > t ? 1 : 0))
})

const dist = computed(() => {
  const f = fwdReturns.value
  const n = f.length
  const up = f.filter((v) => v > threshold.value / 100).length
  const dn = n - up
  const pUp = n ? up / n : 0
  const hitRate = mean(f) // 平均前瞻收益
  return { n, up, dn, pUp, meanFwd: hitRate, stdFwd: std(f) }
})

function hist(vals: number[], bins = 30) {
  let min = Math.min(...vals)
  let max = Math.max(...vals)
  if (min === max) {
    min -= 0.01
    max += 0.01
  }
  const w = (max - min) / bins
  const counts = new Array(bins).fill(0)
  for (const v of vals) {
    let b = Math.floor((v - min) / w)
    if (b >= bins) b = bins - 1
    counts[b]++
  }
  const centers = counts.map((_, i) => Number((min + w * (i + 0.5)).toFixed(4)))
  return { centers, counts, min, max }
}

const histOption = computed(() => {
  const h = hist(fwdReturns.value)
  const t = threshold.value / 100
  return {
    animation: false,
    grid: { left: 56, right: 24, top: 36, bottom: 44 },
    tooltip: {
      trigger: 'axis',
      formatter: (ps: any[]) => {
        const p = Array.isArray(ps) ? ps[0] : ps
        return `前瞻 ${horizon.value} 日收益：${(p.value[0] * 100).toFixed(2)}%<br/>样本：${p.value[1]}`
      },
    },
    xAxis: { type: 'value', name: '前瞻收益 %', nameLocation: 'middle', nameGap: 30, axisLabel: { fontSize: 10, formatter: (v: number) => (v * 100).toFixed(0) } },
    yAxis: { type: 'value', name: '频数', nameLocation: 'middle', nameGap: 34, axisLabel: { fontSize: 11 } },
    series: [
      {
        name: '前瞻收益分布',
        type: 'bar',
        barWidth: '90%',
        data: h.centers.map((c, i) => [+(c * 100).toFixed(2), h.counts[i]]),
        itemStyle: {
          color: (p: any) => (p.value[0] > threshold.value ? C.value.success : C.value.slate),
          opacity: 0.6,
        },
        markLine: {
          silent: true,
          symbol: 'none',
          data: [
            {
              xAxis: t * 100,
              label: { formatter: `阈值 ${threshold.value}%`, position: 'insideEndTop' },
              lineStyle: { color: C.value.danger, type: 'dashed' },
            },
          ],
        },
      },
    ],
  }
})

// 时间序列：净值 + 标签着色（绿=看多标签）
const dates = computed<string[]>(() => (data.value ? data.value.map((d) => d.date).slice(1) : []))
const nav = computed<number[]>(() => {
  const r = rets.value
  const out: number[] = []
  let v = 100
  out.push(v)
  for (let i = 1; i < r.length; i++) {
    v *= 1 + r[i]
    out.push(v)
  }
  return out
})

const seriesOption = computed(() => {
  const lbl = labels.value
  return {
    animation: false,
    grid: { left: 56, right: 24, top: 40, bottom: 44 },
    title: [
      {
        text: '茅台净值 + 多空标签（起点 100）',
        left: 56,
        top: 8,
        textStyle: { fontSize: 12, fontWeight: 600, color: C.value.text },
      },
    ],
    dataZoom: [
      {
        type: 'inside',
        xAxisIndex: [0],
        start: 0,
        end: 100,
        zoomOnMouseWheel: true,
        moveOnMouseMove: true,
      },
      {
        type: 'slider',
        xAxisIndex: [0],
        start: 0,
        end: 100,
        bottom: 2,
        height: 16,
        borderColor: C.value.grid,
        backgroundColor: 'transparent',
        fillerColor: withAlpha(C.value.primary, 0.15),
        handleStyle: { color: C.value.primary },
        textStyle: { color: C.value.text, fontSize: 10 },
        dataBackground: {
          lineStyle: { color: C.value.slate, opacity: 0.5 },
          areaStyle: { color: withAlpha(C.value.slate, 0.1) },
        },
        selectedDataBackground: {
          lineStyle: { color: C.value.primary, opacity: 0.6 },
          areaStyle: { color: withAlpha(C.value.primary, 0.12) },
        },
      },
    ],
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: dates.value.map((d) => d.slice(5)), axisLabel: { fontSize: 9, hideOverlap: true } },
    yAxis: [
      { type: 'value', name: '净值', nameLocation: 'middle', nameGap: 40, axisLabel: { fontSize: 10 } },
    ],
    series: [
      {
        name: '茅台净值',
        type: 'line',
        data: nav.value.map((v) => +v.toFixed(2)),
        symbol: 'none',
        lineStyle: { color: C.value.primary, width: 1.6 },
      },
      {
        name: '看多标签',
        type: 'scatter',
        symbolSize: 5,
        data: lbl.map((v, i) => (v ? [i, nav.value[i]] : null)).filter(Boolean) as any,
        itemStyle: { color: C.value.success, opacity: 0.5 },
      },
      {
        name: '看空标签',
        type: 'scatter',
        symbolSize: 4,
        data: lbl.map((v, i) => (!v ? [i, nav.value[i]] : null)).filter(Boolean) as any,
        itemStyle: { color: C.value.danger, opacity: 0.35 },
      },
    ],
  }
})

const pUp = computed(() => (dist.value.n ? (dist.value.pUp * 100).toFixed(1) : '—'))
</script>

<template>
  <div class="label-design">
    <div v-if="loading" class="status">数据加载中…</div>
    <div v-else-if="error" class="status">数据不可用</div>
    <template v-else-if="rets.length">
      <div class="controls">
        <label>前瞻周期 N <input type="range" v-model.number="horizon" min="1" max="20" step="1" /> {{ horizon }} 日</label>
        <label>阈值 <input type="range" v-model.number="threshold" min="-2" max="2" step="0.1" /> {{ threshold }}%</label>
      </div>
      <div class="stats">
        <span class="chip">样本 n = <strong>{{ dist.n }}</strong></span>
        <span class="chip">上涨标签 <strong style="color: var(--success, #16a34a)">{{ dist.up }}</strong>（{{ pUp }}%）</span>
        <span class="chip">下跌标签 <strong style="color: var(--danger, #dc2626)">{{ dist.dn }}</strong>（{{ (100 - +pUp).toFixed(1) }}%）</span>
        <span class="chip">平均前瞻收益 <strong>{{ (dist.meanFwd * 100).toFixed(2) }}%</strong></span>
      </div>
      <p class="sub">前瞻 N 日收益分布（绿=>阈值，红/灰=<阈值）</p>
      <ThemedChart class="chart" :option="histOption" autoresize />
      <p class="sub">标签叠加在真实净曲线上（绿点=看多标签，红点=看空标签）</p>
      <ThemedChart class="chart" :option="seriesOption" autoresize />
      <p class="note">真实锚点：贵州茅台 SH600519 2024 全年复权日收益。教学点：阈值/周期改变正负样本比例（类别不平衡），也改变标签「可用性」——超前 20 日标签波动更大，噪音更多。</p>
    </template>
  </div>
</template>

<style scoped>
.label-design { padding: 16px; }
.status { height: 300px; display: flex; align-items: center; justify-content: center; color: var(--text-3); font-size: 14px; }
.controls { display: flex; gap: 16px; flex-wrap: wrap; align-items: center; margin-bottom: 10px; font-size: 12.5px; color: var(--text-2); }
.controls label { display: flex; align-items: center; gap: 6px; }
.controls input[type='range'] { width: 110px; }
.chart { height: 280px; margin-bottom: 6px; }
.stats { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
.chip {
  font-size: 12.5px; color: var(--text-3);
  padding: 4px 10px; border-radius: 999px; background: var(--bg-hover);
}
.chip strong { color: var(--primary); }
.sub { font-size: 12px; color: var(--text-3); margin: 6px 0 2px; }
.note { font-size: 12.5px; color: var(--text-3); margin-top: 10px; line-height: 1.6; }
</style>
