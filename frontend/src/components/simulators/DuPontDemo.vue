<script setup lang="ts">
import { computed, ref } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'

use([CanvasRenderer, BarChart, LineChart, GridComponent, TooltipComponent, LegendComponent])

// 杜邦分解：ROE = 净利率 × 总资产周转率 × 权益乘数
// 教学点：ROE 提升的三个独立杠杆——盈利、效率、财务杠杆

const props = defineProps<{
  params?: Record<string, unknown>
}>()

const netMargin = ref(typeof props.params?.margin === 'number' ? props.params.margin : 12) // 净利率 %
const turnover = ref(typeof props.params?.turnover === 'number' ? props.params.turnover : 0.6) // 总资产周转率
const leverage = ref(typeof props.params?.leverage === 'number' ? props.params.leverage : 2.5) // 权益乘数

const roe = computed(() => (netMargin.value / 100) * turnover.value * leverage.value * 100)
const roa = computed(() => (netMargin.value / 100) * turnover.value * 100)

// 三个因素对 ROE 的分解柱（标准化贡献示意）
const factors = computed(() => [
  { name: '净利率', value: netMargin.value, unit: '%' },
  { name: '周转率', value: turnover.value, unit: '次' },
  { name: '权益乘数', value: leverage.value, unit: '×' },
])

// 基准组合：净利率 12% / 周转 0.6 / 杠杆 2.5 → ROE = 18%
const baseRoe = 12 / 100 * 0.6 * 2.5 * 100

const barOption = computed(() => ({
  animation: true,
  grid: { left: 52, right: 24, top: 30, bottom: 36 },
  tooltip: { trigger: 'axis' },
  xAxis: { type: 'category', data: ['净利率 %', '周转率 次', '权益乘数 ×'], axisLabel: { fontSize: 11 } },
  yAxis: { type: 'value', name: '取值', nameLocation: 'middle', nameGap: 36, axisLabel: { fontSize: 11 } },
  series: [
    {
      name: '杜邦三因素',
      type: 'bar',
      barMaxWidth: 60,
      data: factors.value.map((f) => ({
        value: +f.value.toFixed(2),
        itemStyle: { color: '#2563eb' },
      })),
      label: { show: true, position: 'top', fontSize: 11, formatter: (p: any) => p.value.toFixed(2) },
    },
  ],
}))

// ROE 随净利率变化的敏感性曲线（固定周转 0.6、杠杆 2.5）
const sensData = computed<[number, number][]>(() => {
  const out: [number, number][] = []
  for (let m = 2; m <= 30; m += 1) out.push([m, +(m / 100 * 0.6 * 2.5 * 100).toFixed(1)])
  return out
})

const sensOption = computed(() => ({
  animation: true,
  grid: { left: 52, right: 24, top: 30, bottom: 36 },
  tooltip: {
    trigger: 'axis',
    formatter: (ps: any) => {
      const a = Array.isArray(ps) ? ps[0] : ps
      return `净利率 ${Number(a.value[0]).toFixed(0)}%<br/>ROE ${Number(a.value[1]).toFixed(1)}%`
    },
  },
  xAxis: { type: 'value', name: '净利率 %', nameLocation: 'middle', nameGap: 26, min: 2, max: 30, axisLabel: { fontSize: 11 } },
  yAxis: { type: 'value', name: 'ROE %', nameLocation: 'middle', nameGap: 36, axisLabel: { fontSize: 11 } },
  series: [
    {
      name: 'ROE 敏感性',
      type: 'line',
      smooth: true,
      symbol: 'none',
      data: sensData.value,
      lineStyle: { width: 2.5, color: '#2563eb' },
      markLine: {
        silent: true,
        symbol: 'none',
        label: { fontSize: 11, formatter: `当前净利率 ${netMargin.value.toFixed(0)}%` },
        data: [{ xAxis: netMargin.value }],
      },
    },
  ],
}))
</script>

<template>
  <div class="dupont">
    <div class="result-row">
      <div class="result-box">
        <span class="muted">ROE</span>
        <strong class="res-main">{{ roe.toFixed(1) }}%</strong>
      </div>
      <div class="result-box">
        <span class="muted">ROA（不乘杠杆）</span>
        <strong class="res-sub">{{ roa.toFixed(1) }}%</strong>
      </div>
      <div class="result-box">
        <span class="muted">基准 ROE（12%/0.6/2.5）</span>
        <strong class="res-sub">{{ baseRoe.toFixed(1) }}%</strong>
      </div>
    </div>

    <VChart class="chart" :option="barOption" autoresize />
    <VChart class="chart" :option="sensOption" autoresize />

    <div class="controls">
      <div class="control-row">
        <span class="control-label">净利率</span>
        <input v-model.number="netMargin" type="range" min="2" max="30" step="0.5" class="slider" />
        <span class="control-value">{{ netMargin.toFixed(1) }}%</span>
      </div>
      <div class="control-row">
        <span class="control-label">周转率</span>
        <input v-model.number="turnover" type="range" min="0.1" max="2" step="0.05" class="slider" />
        <span class="control-value">{{ turnover.toFixed(2) }} 次</span>
      </div>
      <div class="control-row">
        <span class="control-label">权益乘数</span>
        <input v-model.number="leverage" type="range" min="1" max="5" step="0.1" class="slider" />
        <span class="control-value">{{ leverage.toFixed(1) }}×</span>
      </div>
      <div class="tip">
        ROE = 净利率 × 总资产周转率 × 权益乘数。三个因素代表三条提 ROE 的路径：卖得更赚（盈利）、资产转得更快（效率）、借更多钱（杠杆）。
        下图中「ROE 敏感性」固定周转与杠杆、只看净利率的影响——注意杠杆把净利率的改善放大了数倍，这正是高杠杆公司 ROE 波动大的原因。
      </div>
    </div>
  </div>
</template>

<style scoped>
.dupont { padding: 16px; }
.chart { height: 240px; }
.result-row { display: flex; gap: 10px; margin-bottom: 12px; }
.result-box {
  flex: 1; padding: 10px 12px; border-radius: var(--radius-sm);
  background: var(--primary-soft); text-align: center;
  display: flex; flex-direction: column; gap: 2px;
}
.muted { font-size: 12px; color: var(--text-3); }
.res-main { font-size: 20px; font-weight: 700; color: var(--primary); }
.res-sub { font-size: 16px; font-weight: 700; color: var(--text-2); }
.controls { margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border); }
.control-row { display: flex; align-items: center; gap: 12px; }
.control-label { width: 88px; font-size: 13px; color: var(--text-2); flex-shrink: 0; }
.slider { flex: 1; accent-color: var(--primary); cursor: pointer; }
.control-value { width: 72px; font-size: 13px; font-weight: 600; color: var(--primary); text-align: right; flex-shrink: 0; }
.tip { margin-top: 10px; font-size: 12.5px; color: var(--text-3); line-height: 1.7; }
</style>
