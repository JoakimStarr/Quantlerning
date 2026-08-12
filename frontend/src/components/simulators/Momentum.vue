<script setup lang="ts">
import { computed, ref } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, MarkAreaComponent } from 'echarts/components'
import { useStockDaily } from '@/composables/useStockDaily'
import { momentumSignal, shiftPosition, strategyNav, stats, backtestArrays } from '@/utils/strategies'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent, MarkAreaComponent])

// 时序动量（真实茅台 2020-2026）：过去 N 日涨则持有
const props = defineProps<{
  params?: Record<string, unknown>
}>()

const code = computed(() => (typeof props.params?.code === 'string' ? props.params.code : 'sh600519'))
const start = computed(() => (typeof props.params?.start === 'string' ? props.params.start : '2020-01-01'))
const end = computed(() => (typeof props.params?.end === 'string' ? props.params.end : '2026-08-10'))
const { data, loading, error } = useStockDaily(code, start.value, end.value)

const lookback = ref(20)

const com = computed(() => {
  if (!data.value) return null
  const arr = backtestArrays(data.value)
  const pos = shiftPosition(momentumSignal(arr.closes, lookback.value))
  const nav = strategyNav(arr.ret, pos)
  const buyNav = strategyNav(arr.ret, arr.closes.map(() => 1))
  const st = stats(arr.ret, pos)
  const bh = stats(arr.ret, arr.closes.map(() => 1))
  // 过去 lookback 日收益
  const pastRet = arr.closes.map((_, i) => (i < lookback.value ? null : +((arr.closes[i] / arr.closes[i - lookback.value] - 1) * 100).toFixed(1)))
  return { arr, pos, nav, buyNav, st, bh, pastRet }
})

const option = computed(() => {
  if (!com.value) return {}
  const c = com.value
  // 主图：价格 + 持仓色区
  return {
    animation: true,
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    tooltip: {
      trigger: 'axis',
      formatter: (ps: any[]) => {
        const nav = ps.find((p: any) => p.seriesName === '策略净值')
        const bh = ps.find((p: any) => p.seriesName === '买入持有')
        const pr = ps.find((p: any) => p.seriesName === '过去收益')
        const parts = [nav ? `策略净值 ${Number(nav.value[1]).toFixed(1)}` : pr?.name ?? '']
        if (bh) parts.push(`买入持有 ${Number(bh.value[1]).toFixed(1)}`)
        if (pr && pr.value[1] !== '-') parts.push(`过去${lookback.value}日收益 ${pr.value[1]}%`)
        return parts.join('<br/>')
      },
    },
    legend: { top: 0, textStyle: { fontSize: 12 }, data: ['收盘价', '策略净值', '买入持有', '过去 20 日收益'] },
    grid: [
      { left: 52, right: 24, top: 40, height: '58%' },
      { left: 52, right: 24, top: '72%', height: '16%' },
    ],
    xAxis: [
      { type: 'category', data: c.arr.dates, gridIndex: 0, axisLabel: { show: false }, axisPointer: { label: { show: false } } },
      { type: 'category', data: c.arr.dates, gridIndex: 1, axisLabel: { fontSize: 10, hideOverlap: true } },
    ],
    yAxis: [
      { type: 'value', gridIndex: 0, scale: true, axisLabel: { fontSize: 11 } },
      { type: 'value', gridIndex: 1, scale: true, axisLabel: { fontSize: 10 } },
    ],
    series: [
      {
        name: '收盘价',
        type: 'line',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: c.arr.closes.map((v, i) => [c.arr.dates[i], v]),
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 1.3, color: '#2563eb' },
        itemStyle: { color: '#2563eb' },
        markArea: {
          silent: true,
          data: (() => {
            const segs: { name: string; itemStyle: { color: string }; data: [{ xAxis: string }, { xAxis: string }] }[] = []
            let i = 1
            while (i < c.pos.length) {
              if (c.pos[i] === 1) {
                const s = i
                while (i < c.pos.length && c.pos[i] === 1) i++
                segs.push({ name: '持', itemStyle: { color: 'rgba(22, 163, 74, 0.08)' }, data: [{ xAxis: c.arr.dates[s] }, { xAxis: c.arr.dates[i - 1] }] })
              } else {
                i++
              }
            }
            return segs
          })(),
        },
      },
      {
        name: '策略净值',
        type: 'line',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: c.nav.map((v, i) => [c.arr.dates[i], +v.toFixed(1)]),
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 2, color: '#d97706' },
        itemStyle: { color: '#d97706' },
      },
      {
        name: '买入持有',
        type: 'line',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: c.buyNav.map((v, i) => [c.arr.dates[i], +v.toFixed(1)]),
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 1.2, color: '#64748b', type: 'dashed' },
        itemStyle: { color: '#64748b' },
      },
      {
        name: '过去收益',
        type: 'line',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: c.pastRet.map((v, i) => [c.arr.dates[i], v === null ? '-' : v]),
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 1, color: '#7c3aed', opacity: 0.7 },
        itemStyle: { color: '#7c3aed' },
      },
    ],
  }
})

const st = computed(() => com.value?.st)

</script>

<template>
  <div class="mm">
    <div v-if="loading" class="status">数据加载中…</div>
    <div v-else-if="error" class="status">数据不可用</div>
    <template v-else-if="com && st">
      <div class="result">
        <div class="result-item">
          <span class="result-label">累计收益</span>
          <strong class="result-value" :style="{ color: st.cum >= 0 ? '#16a34a' : '#dc2626' }">{{ (st.cum * 100).toFixed(1) }}%</strong>
        </div>
        <div class="result-item">
          <span class="result-label">最大回撤</span>
          <strong class="result-value" style="color: #dc2626">{{ (st.mdd * 100).toFixed(1) }}%</strong>
        </div>
        <div class="result-item">
          <span class="result-label">持仓占比</span>
          <strong class="result-value">{{ (st.posMean * 100).toFixed(1) }}%</strong>
        </div>
        <div class="result-item">
          <span class="result-label">信号次数</span>
          <strong class="result-value">{{ st.switches }}</strong>
        </div>
      </div>
      <VChart class="chart" :option="option" autoresize />
      <div class="controls">
        <div class="control-row">
          <span class="control-label">回看 N</span>
          <input v-model.number="lookback" type="range" min="5" max="120" step="1" class="slider" />
          <span class="control-value">{{ lookback }}</span>
        </div>
        <p class="hint">
          主图绿色底色为持仓期；「过去收益」> 0 时持有。N 越大越「慢」——参数即世界观。
        </p>
      </div>
    </template>
  </div>
</template>

<style scoped>
.mm { padding: 16px; }
.status { height: 400px; display: flex; align-items: center; justify-content: center; color: var(--text-3); font-size: 14px; }
.chart { height: 400px; }
.result { display: flex; gap: 22px; margin-bottom: 12px; padding: 12px 16px; background: var(--primary-soft); border-radius: var(--radius-sm); flex-wrap: wrap; }
.result-item { display: flex; flex-direction: column; gap: 2px; }
.result-label { font-size: 12px; color: var(--text-3); }
.result-value { font-size: 18px; font-weight: 700; }
.controls { margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--border); display: flex; flex-direction: column; gap: 10px; }
.control-row { display: flex; align-items: center; gap: 12px; }
.control-label { width: 72px; font-size: 13px; color: var(--text-2); flex-shrink: 0; }
.slider { flex: 1; accent-color: var(--primary); cursor: pointer; }
.control-value { width: 56px; font-size: 13px; font-weight: 600; color: var(--primary); text-align: right; flex-shrink: 0; }
.hint { margin-top: 10px; font-size: 12px; color: var(--text-3); line-height: 1.7; }
</style>