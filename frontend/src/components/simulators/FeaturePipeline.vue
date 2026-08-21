<script setup lang="ts">
import { computed, ref } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, MarkLineComponent } from 'echarts/components'
import { useStockDaily } from '@/composables/useStockDaily'

use([CanvasRenderer, BarChart, LineChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent])

// 特征工程流水线：真实茅台 2024 日收益 → MAD 去极值 → z-score 标准化
// 每个阶段看收益分布直方图 + 正态参考曲线，直观看到清洗/变换的效果

const props = defineProps<{
  params?: Record<string, unknown>
}>()

const code = computed(() => (typeof props.params?.code === 'string' ? props.params.code : 'sh600519'))
const { data, loading, error } = useStockDaily(code)

// 原始收益：pct_chg 复权口径，不含首日（与课程主线一致）
const rets = computed<number[]>(() => (data.value ? data.value.map((d) => d.pct_chg).slice(1) : []))

const stage = ref<'raw' | 'winsor' | 'z'>('raw')

function median(vals: number[]): number {
  const s = [...vals].sort((a, b) => a - b)
  const m = Math.floor(s.length / 2)
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2
}

function mean(vals: number[]): number {
  return vals.reduce((s, v) => s + v, 0) / vals.length
}

function std(vals: number[]): number {
  const m = mean(vals)
  return Math.sqrt(vals.reduce((s, v) => s + (v - m) ** 2, 0) / (vals.length - 1))
}

/** MAD 去极值：阈值 = 中位数 ± n × 1.4826 × MAD（1.4826 把 MAD 归一化到 σ 尺度） */
function winsorizeMAD(vals: number[], n = 3) {
  const med = median(vals)
  const mad = median(vals.map((v) => Math.abs(v - med)))
  const scale = n * 1.4826 * mad
  const lo = med - scale
  const hi = med + scale
  const clipped = vals.map((v) => Math.max(lo, Math.min(hi, v)))
  const nClipped = vals.filter((v) => v < lo || v > hi).length
  return { clipped, nClipped, lo, hi }
}

function zscore(vals: number[]): number[] {
  const m = mean(vals)
  const s = std(vals)
  return vals.map((v) => (v - m) / s)
}

const winsor = computed(() => (rets.value.length ? winsorizeMAD(rets.value) : null))
const zscores = computed(() => (rets.value.length ? zscore(rets.value) : []))

const current = computed<{
  vals: number[]
  label: string
  mu: number
  sd: number
  lo?: number
  hi?: number
  note: string
} | null>(() => {
  if (!rets.value.length) return null
  if (stage.value === 'winsor' && winsor.value) {
    const w = winsor.value
    return {
      vals: w.clipped,
      label: 'MAD 去极值后',
      mu: mean(w.clipped),
      sd: std(w.clipped),
      lo: w.lo,
      hi: w.hi,
      note: `裁掉 ${w.nClipped} 个极端点`,
    }
  }
  if (stage.value === 'z') {
    const z = zscores.value
    return { vals: z, label: 'z-score 标准化后', mu: 0, sd: 1, note: '均值≈0，标准差≈1' }
  }
  return {
    vals: rets.value,
    label: '原始日收益',
    mu: mean(rets.value),
    sd: std(rets.value),
    note: '含离群点（左尾暴跌 / 右尾暴涨）',
  }
})

function hist(vals: number[], bins = 36) {
  let min = Math.min(...vals)
  let max = Math.max(...vals)
  if (min === max) {
    min -= 1
    max += 1
  }
  const w = (max - min) / bins
  const counts = new Array(bins).fill(0)
  for (const v of vals) {
    let b = Math.floor((v - min) / w)
    if (b >= bins) b = bins - 1
    counts[b]++
  }
  const centers = counts.map((_, i) => Number((min + w * (i + 0.5)).toFixed(4)))
  return { centers, counts, width: w, n: vals.length, min, max }
}

function normPdf(x: number, mu: number, sd: number) {
  return (1 / (sd * Math.sqrt(2 * Math.PI))) * Math.exp(-((x - mu) ** 2) / (2 * sd * sd))
}

const option = computed(() => {
  if (!current.value) return {}
  const { vals, mu, sd, lo, hi } = current.value
  const h = hist(vals)
  const isZ = stage.value === 'z'
  const unit = (v: number) => (isZ ? `${v.toFixed(1)}` : `${v.toFixed(2)}%`)
  const pdf = h.centers.map((c) => Number((normPdf(c, mu, sd) * h.n * h.width).toFixed(4)))
  const marks: any[] = []
  if (lo !== undefined && hi !== undefined) {
    marks.push(
      { xAxis: lo, label: { formatter: '下界', position: 'insideEndTop' }, lineStyle: { color: C.value.danger, type: 'dashed' } },
      { xAxis: hi, label: { formatter: '上界', position: 'insideEndTop' }, lineStyle: { color: C.value.danger, type: 'dashed' } },
    )
  }
  if (isZ) {
    ;[-3, -2, -1, 1, 2, 3].forEach((v) =>
      marks.push({ xAxis: v, label: { formatter: `${v}σ`, position: 'insideEndTop' }, lineStyle: { color: C.value.slate, type: 'dotted' } }),
    )
  }
  return {
    animation: false,
    grid: { left: 52, right: 24, top: 36, bottom: 44 },
    tooltip: {
      trigger: 'axis',
      formatter: (ps: any[]) => {
        const arr = Array.isArray(ps) ? ps : [ps]
        return arr
          .map((p: any) => {
            const c = Array.isArray(p.value) ? p.value[0] : p.axisValue
            return `${p.seriesName}：${Number(p.value[1]).toFixed(2)}（x=${unit(c)}）`
          })
          .join('<br/>')
      },
    },
    legend: { top: 0, textStyle: { fontSize: 12 } },
    xAxis: {
      type: 'value',
      name: isZ ? 'z 值' : '日收益 %',
      nameLocation: 'middle',
      nameGap: 28,
      min: h.min - 0.2 * (h.max - h.min),
      max: h.max + 0.2 * (h.max - h.min),
      axisLabel: { fontSize: 10, formatter: (v: number) => unit(v) },
    },
    yAxis: { type: 'value', name: '频数', nameLocation: 'middle', nameGap: 34, axisLabel: { fontSize: 11 } },
    series: [
      {
        name: current.value.label,
        type: 'bar',
        barWidth: '90%',
        data: h.centers.map((c, i) => [c, h.counts[i]]),
        itemStyle: { color: C.value.primary, opacity: 0.55 },
      },
      {
        name: '正态参考',
        type: 'line',
        data: h.centers.map((c, i) => [c, pdf[i]]),
        symbol: 'none',
        lineStyle: { width: 2, color: C.value.warning },
        markLine: marks.length
          ? { silent: true, symbol: 'none', data: marks }
          : undefined,
      },
    ],
  }
})
</script>

<template>
  <div class="feat-pipe">
    <div v-if="loading" class="status">数据加载中…</div>
    <div v-else-if="error" class="status">数据不可用</div>
    <template v-else-if="current">
      <div class="stage-tabs">
        <button class="stage-btn" :class="{ active: stage === 'raw' }" @click="stage = 'raw'">原始收益</button>
        <span class="stage-arrow">→</span>
        <button class="stage-btn" :class="{ active: stage === 'winsor' }" @click="stage = 'winsor'">MAD 去极值</button>
        <span class="stage-arrow">→</span>
        <button class="stage-btn" :class="{ active: stage === 'z' }" @click="stage = 'z'">z-score 标准化</button>
      </div>

      <div class="stats">
        <span class="chip">样本 n = <strong>{{ current.vals.length }}</strong></span>
        <span class="chip">均值 = <strong>{{ current.mu.toFixed(3) }}{{ stage === 'z' ? '' : '%' }}</strong></span>
        <span class="chip">标准差 = <strong>{{ current.sd.toFixed(3) }}</strong></span>
        <span class="chip note">{{ current.note }}</span>
      </div>

      <ThemedChart class="chart" :option="option" autoresize />

      <p class="tip">
        注意：z-score 标准化是<b>线性变换</b>——减去均值、除以标准差，只改横轴尺度和单位，<b>不改变分布形状</b>。
        所以「标准化」与「原始收益」直方图形状一致是正常的；真正改变形状的是上一步「MAD 去极值」（把尾部极端值裁到阈值内）。
      </p>
    </template>
  </div>
</template>

<style scoped>
.feat-pipe { padding: 16px; }
.status { height: 300px; display: flex; align-items: center; justify-content: center; color: var(--text-3); font-size: 14px; }
.chart { height: 300px; }
.stage-tabs { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; flex-wrap: wrap; }
.stage-btn {
  padding: 5px 14px; border: 1px solid var(--border); border-radius: 999px;
  background: var(--bg-card); color: var(--text-2); font-size: 13px; cursor: pointer; transition: all 0.15s;
}
.stage-btn:hover { border-color: var(--primary); color: var(--primary); }
.stage-btn.active { background: var(--primary); border-color: var(--primary); color: #fff; }
.stage-arrow { color: var(--text-3); font-size: 13px; }
.stats { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
.chip {
  font-size: 12.5px; color: var(--text-3);
  padding: 4px 10px; border-radius: 999px; background: var(--bg-hover);
}
.chip strong { color: var(--primary); }
.chip.note { background: var(--primary-soft); color: var(--text-2); }
.tip {
  margin-top: 10px; font-size: 12.5px; color: var(--text-3); line-height: 1.7;
  background: var(--primary-soft); border-radius: var(--radius-sm); padding: 8px 12px;
}
.tip b { color: var(--text-2); }
</style>
