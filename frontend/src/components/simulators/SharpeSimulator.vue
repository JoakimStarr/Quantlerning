<script setup lang="ts">
import { computed, ref } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, ScatterChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, MarkLineComponent } from 'echarts/components'
import { useStockDaily } from '@/composables/useStockDaily'

use([CanvasRenderer, LineChart, ScatterChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent])

// 夏普比率模拟器：Sharpe = (μ − Rf) / σ
// 拖动收益/波动/无风险利率，实时看夏普；风险收益平面上标出等夏普线
// 茅台点为后端实时计算（复权口径，不含首日，ddof=1），与课程主线一致

const props = defineProps<{
  params?: Record<string, unknown>
}>()

const num = (v: unknown, def: number) => (typeof v === 'number' ? v : def)

const mu = ref(num(props.params?.mu, 0.15)) // 年化收益（小数）
const sigma = ref(num(props.params?.sigma, 0.25)) // 年化波动（小数）
const rf = ref(num(props.params?.rf, 0.02)) // 无风险利率（小数）

// 茅台 2024 真实数据（复权 pct_chg，不含首日 241 收益，ddof=1）
const { data, loading, error } = useStockDaily(
  computed(() => (typeof props.params?.code === 'string' ? props.params.code : 'sh600519')),
)

function std(a: number[]): number {
  const m = a.reduce((s, v) => s + v, 0) / a.length
  return Math.sqrt(a.reduce((s, v) => s + (v - m) ** 2, 0) / (a.length - 1))
}

// 茅台点：年化收益 = 复利几何年化，年化波动 = 日波动×√252
// rets 单位已是「%」，年化波动结果同样是「%」数值；年化收益以小数计算再转「%」
const maotaiPoint = computed<[number, number] | null>(() => {
  if (!data.value || data.value.length < 2) return null
  const rets = data.value.map((d) => d.pct_chg).slice(1) // 不含首日
  const n = rets.length
  const cum = rets.reduce((acc, r) => acc * (1 + r / 100), 1) - 1
  const annRet = Math.pow(1 + cum, 252 / n) - 1
  const annVol = std(rets) * Math.sqrt(252)
  return [Number(annVol.toFixed(2)), Number((annRet * 100).toFixed(2))]
})

// 滑块用百分比表示
const muPct = computed(() => mu.value * 100)
const sigmaPct = computed(() => sigma.value * 100)
const rfPct = computed(() => rf.value * 100)

const sharpe = computed(() => {
  if (sigma.value <= 0) return null
  return (mu.value - rf.value) / sigma.value
})

function sharpeColor(s: number | null) {
  if (s === null) return '#94a3b8'
  if (s < 0) return '#dc2626'
  if (s < 1) return '#d97706'
  return '#16a34a'
}

// 等夏普参考线：μ = rf + s·σ
function isoSharpeLine(s: number) {
  const points: [number, number][] = []
  for (let x = 0; x <= 50; x += 5) {
    points.push([x, rf.value * 100 + s * x])
  }
  return points
}

const maotaiSharpe = computed(() =>
  maotaiPoint.value ? (maotaiPoint.value[1] / 100 - rf.value) / (maotaiPoint.value[0] / 100) : null,
)

const option = computed(() => {
  const s = sharpe.value
  return {
    animation: true,
    grid: { left: 46, right: 20, top: 36, bottom: 40 },
    tooltip: {
      trigger: 'axis',
      formatter: (ps: any[]) => {
        const p = ps[0]
        return `σ=${p.value[0].toFixed(1)}%　μ=${p.value[1].toFixed(1)}%`
      },
    },
    legend: { top: 0, textStyle: { fontSize: 12 }, data: ['等夏普 0.5', '等夏普 1.0', '等夏普 2.0', '当前组合', '茅台 2024'] },
    xAxis: {
      type: 'value',
      name: '风险 σ（年化波动）',
      nameLocation: 'middle',
      nameGap: 28,
      min: 0,
      max: 50,
      axisLabel: { fontSize: 11, formatter: '{value}%' },
    },
    yAxis: {
      type: 'value',
      name: '收益 μ（年化）',
      nameLocation: 'middle',
      nameGap: 38,
      min: -20,
      max: 40,
      axisLabel: { fontSize: 11, formatter: '{value}%' },
    },
    series: [
      {
        name: '等夏普 0.5',
        type: 'line',
        data: isoSharpeLine(0.5),
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 1, type: 'dashed', color: '#94a3b8', opacity: 0.7 },
      },
      {
        name: '等夏普 1.0',
        type: 'line',
        data: isoSharpeLine(1),
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 1, type: 'dashed', color: '#94a3b8', opacity: 0.7 },
      },
      {
        name: '等夏普 2.0',
        type: 'line',
        data: isoSharpeLine(2),
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 1, type: 'dashed', color: '#94a3b8', opacity: 0.7 },
      },
      {
        name: '当前组合',
        type: 'scatter',
        data: [[sigmaPct.value, muPct.value]],
        symbolSize: 14,
        itemStyle: { color: sharpeColor(s) },
        markLine: {
          silent: true,
          symbol: 'none',
          label: { fontSize: 11, color: '#94a3b8', formatter: 'μ = Rf + S·σ' },
          lineStyle: { type: 'dotted', color: sharpeColor(s), width: 1.5 },
          data: [{ xAxis: sigmaPct.value }],
        },
      },
      {
        name: '茅台 2024',
        type: 'scatter',
        data: maotaiPoint.value ? [maotaiPoint.value] : [],
        symbolSize: 10,
        itemStyle: { color: '#7c3aed' },
        label: {
          show: !!maotaiSharpe.value,
          position: 'top',
          fontSize: 10,
          color: '#7c3aed',
          formatter: `夏普 ${maotaiSharpe.value?.toFixed(2)}`,
        },
      },
    ],
  }
})
</script>

<template>
  <div class="sharpe-sim">
    <div class="result">
      <span class="result-label">夏普比率</span>
      <strong class="result-value" :style="{ color: sharpeColor(sharpe) }">{{ sharpe === null ? '—' : sharpe.toFixed(2) }}</strong>
      <span class="result-tag" :style="{ background: sharpeColor(sharpe) }">
        {{ sharpe === null ? '' : sharpe < 0 ? '负夏普' : sharpe < 1 ? '合格' : sharpe < 2 ? '良好' : '优秀' }}
      </span>
    </div>

    <VChart class="chart" :option="option" autoresize />

    <div class="controls">
      <div class="control-row">
        <span class="control-label">收益 μ</span>
        <input v-model.number="mu" type="range" min="-0.20" max="0.40" step="0.005" class="slider" />
        <span class="control-value">{{ muPct.toFixed(1) }}%</span>
      </div>
      <div class="control-row">
        <span class="control-label">波动 σ</span>
        <input v-model.number="sigma" type="range" min="0.02" max="0.50" step="0.005" class="slider" />
        <span class="control-value">{{ sigmaPct.toFixed(1) }}%</span>
      </div>
      <div class="control-row">
        <span class="control-label">无风险 Rf</span>
        <input v-model.number="rf" type="range" min="0" max="0.10" step="0.005" class="slider" />
        <span class="control-value">{{ rfPct.toFixed(1) }}%</span>
      </div>
    </div>
    <p class="hint" v-if="loading">茅台点加载中…</p>
    <p class="hint" v-else-if="error">茅台点：数据不可用</p>
    <p class="hint" v-else-if="maotaiPoint">紫点为茅台 2024 实际位置：年化 {{ maotaiPoint[1] }}%、波动 {{ maotaiPoint[0] }}%（真实行情实时计算）。</p>
  </div>
</template>

<style scoped>
.sharpe-sim { padding: 16px; }
.chart { height: 320px; }
.result {
  display: flex; align-items: baseline; gap: 12px;
  margin-bottom: 12px; padding: 12px 16px;
  background: var(--primary-soft); border-radius: var(--radius-sm);
}
.result-label { font-size: 14px; color: var(--text-2); }
.result-value { font-size: 30px; font-weight: 700; line-height: 1; }
.result-tag {
  font-size: 12px; padding: 2px 10px; border-radius: 999px; color: #fff;
}
.controls {
  margin-top: 14px; padding-top: 14px;
  border-top: 1px solid var(--border);
  display: flex; flex-direction: column; gap: 10px;
}
.control-row { display: flex; align-items: center; gap: 12px; }
.control-label { width: 72px; font-size: 13px; color: var(--text-2); flex-shrink: 0; }
.slider { flex: 1; accent-color: var(--primary); cursor: pointer; }
.control-value { width: 56px; font-size: 13px; font-weight: 600; color: var(--primary); text-align: right; flex-shrink: 0; }
.hint { margin-top: 10px; font-size: 12px; color: var(--text-3); }
</style>
