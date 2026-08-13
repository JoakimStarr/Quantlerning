<script setup lang="ts">
import { computed, ref } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, MarkLineComponent, MarkPointComponent } from 'echarts/components'
import { createMarkdown } from '../../utils/markdownIt'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent, MarkPointComponent])

// CAPM 证券市场线 SML：E[R] = rf + β·(Rm − rf)
// 拖动 β 看期望收益在 SML 上的位置；rf / Rm 可调
// 教学示意模型（非真实数据）

// 公式渲染：katex（与正文同一套 markdown-it 数学插件）
const md = createMarkdown()
const formulaHtml = md.renderInline('$E[R] = r_f + \\beta \\cdot (R_m - r_f)$')

const props = defineProps<{
  params?: Record<string, unknown>
}>()

const rf = ref(typeof props.params?.rf === 'number' ? props.params.rf : 2) // 无风险利率 %
const rm = ref(typeof props.params?.rm === 'number' ? props.params.rm : 10) // 市场期望收益 %
const beta = ref(typeof props.params?.beta === 'number' ? props.params.beta : 1.0)

const sml = (b: number) => rf.value + b * (rm.value - rf.value)

const linePoints = computed<[number, number][]>(() => [
  [0, +rf.value.toFixed(2)],
  [2, +sml(2).toFixed(2)],
])

const expRet = computed(() => sml(beta.value))
// 超配/低配判断：SML 上方 = 低估（实际收益高于 CAPM 要求），下方 = 高估
const status = computed(() => {
  if (Math.abs(beta.value) < 0.001) return 'β=0：与市场无关'
  if (beta.value === 1) return 'β=1：与市场同涨跌'
  return beta.value > 1 ? `β=${beta.value.toFixed(1)}：进攻型（放大波动）` : `β=${beta.value.toFixed(1)}：防御型（波动小于市场）`
})

const option = computed(() => ({
  animation: true,
  grid: { left: 52, right: 24, top: 36, bottom: 44 },
  tooltip: {
    trigger: 'axis',
    formatter: (ps: any) => {
      const a = Array.isArray(ps) ? ps[0] : ps
      return `β = ${Number(a.value[0]).toFixed(1)}<br/>期望收益 ${Number(a.value[1]).toFixed(1)}%`
    },
  },
  legend: { top: 0, textStyle: { fontSize: 12 } },
  xAxis: { type: 'value', name: 'β', nameLocation: 'middle', nameGap: 26, min: 0, max: 2, axisLabel: { fontSize: 10 } },
  yAxis: { type: 'value', name: '期望收益 %', nameLocation: 'middle', nameGap: 40, min: 0, max: Math.max(20, rm.value + 8), axisLabel: { fontSize: 10 } },
  series: [
    {
      name: 'SML',
      type: 'line',
      data: linePoints.value,
      symbol: 'none',
      lineStyle: { width: 2.5, color: '#2563eb' },
      markLine: {
        silent: true,
        symbol: 'none',
        lineStyle: { type: 'dashed', color: '#9ca3af' },
        label: { fontSize: 10, color: '#6b7280', formatter: 'β = 1' },
        data: [{ xAxis: 1 }],
      },
      markPoint: {
        symbolSize: 52,
        label: { fontSize: 10 },
        data: [
          {
            coord: [+beta.value.toFixed(2), +expRet.value.toFixed(2)],
            value: '本资产',
            itemStyle: { color: '#d97706' },
          },
        ],
      },
    },
  ],
}))
</script>

<template>
  <div class="capm">
    <div class="result">
      <div class="result-item">
        <span class="result-label">CAPM 期望收益</span>
        <strong class="result-value primary">{{ expRet.toFixed(2) }}%</strong>
      </div>
      <div class="result-item">
        <span class="result-label">公式</span>
        <strong class="result-value formula" v-html="formulaHtml"></strong>
      </div>
      <div class="result-item">
        <span class="result-label">定位</span>
        <strong class="result-value sm">{{ status }}</strong>
      </div>
    </div>

    <VChart class="chart" :option="option" autoresize />

    <div class="controls">
      <div class="control-row">
        <span class="control-label">β</span>
        <input v-model.number="beta" type="range" min="0" max="2" step="0.05" class="slider" />
        <span class="control-value">{{ beta.toFixed(2) }}</span>
      </div>
      <div class="control-row">
        <span class="control-label">无风险 rf</span>
        <input v-model.number="rf" type="range" min="0" max="6" step="0.5" class="slider" />
        <span class="control-value">{{ rf.toFixed(1) }}%</span>
      </div>
      <div class="control-row">
        <span class="control-label">市场 Rm</span>
        <input v-model.number="rm" type="range" min="4" max="18" step="0.5" class="slider" />
        <span class="control-value">{{ rm.toFixed(1) }}%</span>
      </div>
      <div class="tip">
        SML 上方的资产被低估（实际收益高于 β 对应的要求收益），下方被高估。β 只衡量「市场系统性风险」暴露——这是 CAPM 唯一获得补偿的风险。
      </div>
    </div>
  </div>
</template>

<style scoped>
.capm { padding: 16px; }
.chart { height: 300px; }
.result { display: flex; gap: 20px; margin-bottom: 12px; padding: 12px 16px; background: var(--primary-soft); border-radius: var(--radius-sm); flex-wrap: wrap; }
.result-item { display: flex; flex-direction: column; gap: 2px; }
.result-label { font-size: 12px; color: var(--text-3); }
.result-value { font-size: 18px; font-weight: 700; }
.result-value.primary { color: var(--primary); }
.result-value.formula { font-size: 14px; color: var(--text-2); font-family: var(--font-mono); }
.result-value.formula :deep(.katex) { font-size: 1em; }
.result-value.sm { font-size: 13px; color: var(--text-2); }
.controls { margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border); display: flex; flex-direction: column; gap: 10px; }
.control-row { display: flex; align-items: center; gap: 12px; }
.control-label { width: 72px; font-size: 13px; color: var(--text-2); flex-shrink: 0; }
.slider { flex: 1; accent-color: var(--primary); cursor: pointer; }
.control-value { width: 64px; font-size: 13px; font-weight: 600; color: var(--primary); text-align: right; flex-shrink: 0; }
.tip { margin-top: 4px; font-size: 12.5px; color: var(--text-3); line-height: 1.7; }
</style>
