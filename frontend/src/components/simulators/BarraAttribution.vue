<script setup lang="ts">
import { computed, ref } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, MarkLineComponent } from 'echarts/components'

use([CanvasRenderer, BarChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent])

// Barra 归因演示（教学示意，数值为构造示例）：
// 总收益 = 行业因子贡献 + 风格因子贡献 + 选股 alpha（残差）
// 教学点：超额收益可能主要来自行业/风格暴露而非选股能力——归因账本识别它

const props = defineProps<{
  params?: Record<string, unknown>
}>()

const totalRet = ref(typeof props.params?.total === 'number' ? props.params.total : 25) // 组合总收益 %
const benchRet = ref(typeof props.params?.bench === 'number' ? props.params.bench : 10) // 基准收益 %
const industry = ref(typeof props.params?.industry === 'number' ? props.params.industry : 12) // 行业贡献 %
const style = ref(typeof props.params?.style === 'number' ? props.params.style : 8) // 风格贡献 %
const alpha = ref(5) // 选股 alpha %

// 归因等式校验
const check = computed(() => {
  const sum = industry.value + style.value + alpha.value
  return { sum, ok: Math.abs(sum - totalRet.value) < 0.01 }
})

// 组合超额 vs 基准
const excess = computed(() => totalRet.value - benchRet.value)
const factorContrib = computed(() => industry.value + style.value)

// 归因柱状图：行业 / 风格 / 选股 alpha
const barOption = computed(() => ({
  animation: true,
  grid: { left: 52, right: 24, top: 30, bottom: 36 },
  tooltip: {
    trigger: 'axis',
    formatter: (ps: any) => {
      const p = Array.isArray(ps) ? ps[0] : ps
      return `${p.name}<br/>贡献 ${Number(p.value).toFixed(1)}%`
    },
  },
  xAxis: {
    type: 'category',
    data: ['行业因子', '风格因子', '选股 alpha'],
    axisLabel: { fontSize: 11 },
  },
  yAxis: { type: 'value', name: '贡献 %', nameLocation: 'middle', nameGap: 38, axisLabel: { fontSize: 11 } },
  series: [
    {
      name: '归因贡献',
      type: 'bar',
      barMaxWidth: 64,
      data: [
        { value: +industry.value.toFixed(1), itemStyle: { color: '#2563eb' } },
        { value: +style.value.toFixed(1), itemStyle: { color: '#0891b2' } },
        { value: +alpha.value.toFixed(1), itemStyle: { color: '#d97706' } },
      ],
      label: { show: true, position: 'top', fontSize: 11, formatter: (p: any) => `${p.value.toFixed(1)}%` },
    },
  ],
}))

// 超额来源占比：因子贡献 vs 选股 alpha
const shareOption = computed(() => {
  const total = Math.abs(excess.value)
  const fact = Math.abs(factorContrib.value)
  const alp = Math.abs(alpha.value)
  const factShare = total > 0 ? (fact / (fact + alp)) * 100 : 0
  const alpShare = 100 - factShare
  return {
    animation: true,
    grid: { left: 52, right: 24, top: 30, bottom: 36 },
    tooltip: { trigger: 'axis' },
    legend: { top: 0, textStyle: { fontSize: 11 } },
    xAxis: { type: 'category', data: ['超额来源占比'], axisLabel: { fontSize: 11 } },
    yAxis: { type: 'value', name: '%', nameLocation: 'middle', nameGap: 32, max: 100, axisLabel: { fontSize: 11, formatter: '{value}%' } },
    series: [
      {
        name: '行业/风格暴露',
        type: 'bar',
        stack: 's',
        data: [+factShare.toFixed(1)],
        itemStyle: { color: '#2563eb' },
        label: { show: true, fontSize: 11, formatter: `${factShare.toFixed(0)}%` },
      },
      {
        name: '选股 alpha',
        type: 'bar',
        stack: 's',
        data: [+alpShare.toFixed(1)],
        itemStyle: { color: '#d97706' },
        label: { show: true, fontSize: 11, formatter: `${alpShare.toFixed(0)}%` },
      },
    ],
  }
})
</script>

<template>
  <div class="barra-attrib">
    <div class="result-row">
      <div class="result-box">
        <span class="muted">组合总收益</span>
        <strong class="res-main">{{ totalRet.toFixed(0) }}%</strong>
        <span class="res-sub" v-if="check.ok">= 行业 {{ industry }}% + 风格 {{ style }}% + alpha {{ alpha }}%</span>
        <span class="res-err" v-else>归因等式不平衡！{{ industry + style + alpha }}% ≠ {{ totalRet }}%</span>
      </div>
      <div class="result-box">
        <span class="muted">基准收益</span>
        <strong class="res-sub">{{ benchRet.toFixed(0) }}%</strong>
      </div>
      <div class="result-box">
        <span class="muted">超额收益</span>
        <strong class="res-main" :class="{ neg: excess < 0 }">{{ excess > 0 ? '+' : '' }}{{ excess.toFixed(1) }}%</strong>
      </div>
      <div class="result-box">
        <span class="muted">超额中暴露占</span>
        <strong class="res-main" :class="{ warn: factorContrib / Math.max(Math.abs(excess), 1e-9) > 1 }">
          {{ (factorContrib / Math.max(Math.abs(excess), 1e-9) * 100).toFixed(0) }}%
        </strong>
      </div>
    </div>

    <VChart class="chart" :option="barOption" autoresize />
    <VChart class="chart" :option="shareOption" autoresize />

    <div class="controls">
      <div class="control-row">
        <span class="control-label">组合收益</span>
        <input v-model.number="totalRet" type="range" min="-10" max="50" step="1" class="slider" />
        <span class="control-value">{{ totalRet.toFixed(0) }}%</span>
      </div>
      <div class="control-row">
        <span class="control-label">行业贡献</span>
        <input v-model.number="industry" type="range" min="-20" max="30" step="0.5" class="slider" />
        <span class="control-value">{{ industry.toFixed(1) }}%</span>
      </div>
      <div class="control-row">
        <span class="control-label">风格贡献</span>
        <input v-model.number="style" type="range" min="-20" max="30" step="0.5" class="slider" />
        <span class="control-value">{{ style.toFixed(1) }}%</span>
      </div>
      <div class="control-row">
        <span class="control-label">选股 alpha</span>
        <input v-model.number="alpha" type="range" min="-10" max="20" step="0.5" class="slider" />
        <span class="control-value">{{ alpha.toFixed(1) }}%</span>
      </div>
      <div class="tip">
        Barra 归因把总收益拆成「行业因子 + 风格因子 + 选股 alpha」。真实回测中很多「超额」其实只是行业/风格暴露
        （β 收益）——比如重仓了 2020 的消费、2021 的成长。教学示意：数值为构造示例，非真实归因结果。当前示例超额
        {{ excess > 0 ? '+' : '' }}{{ excess.toFixed(1) }}% 中，行业+风格暴露占
        {{ (factorContrib / Math.max(Math.abs(excess), 1e-9) * 100).toFixed(0) }}%——识别「超额来自运气还是选股能力」是 Barra 的核心用途。
      </div>
    </div>
  </div>
</template>

<style scoped>
.barra-attrib { padding: 16px; }
.chart { height: 230px; }
.result-row { display: flex; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; }
.result-box {
  flex: 1; min-width: 130px; padding: 10px 12px; border-radius: var(--radius-sm);
  background: var(--primary-soft); text-align: center;
  display: flex; flex-direction: column; gap: 2px;
}
.muted { font-size: 12px; color: var(--text-3); }
.res-main { font-size: 18px; font-weight: 700; color: var(--primary); }
.res-main.neg { color: #dc2626; }
.res-main.warn { color: #d97706; }
.res-sub { font-size: 13px; color: var(--text-2); }
.res-err { font-size: 12px; color: #dc2626; }
.controls { margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border); }
.control-row { display: flex; align-items: center; gap: 12px; }
.control-label { width: 88px; font-size: 13px; color: var(--text-2); flex-shrink: 0; }
.slider { flex: 1; accent-color: var(--primary); cursor: pointer; }
.control-value { width: 56px; font-size: 13px; font-weight: 600; color: var(--primary); text-align: right; flex-shrink: 0; }
.tip { margin-top: 10px; font-size: 12.5px; color: var(--text-3); line-height: 1.7; }
</style>
