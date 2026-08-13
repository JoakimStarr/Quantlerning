<script setup lang="ts">
import { computed, ref } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { useStockDaily } from '@/composables/useStockDaily'
import { maCrossSignal, shiftPosition, strategyNav, stats, backtestArrays } from '@/utils/strategies'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent])

// 成本敏感性（真实茅台 2020-2026，均线交叉）：滑块调单边成本(bp)
const props = defineProps<{
  params?: Record<string, unknown>
}>()

const code = computed(() => (typeof props.params?.code === 'string' ? props.params.code : 'sh600519'))
const start = computed(() => (typeof props.params?.start === 'string' ? props.params.start : '2020-01-01'))
const end = computed(() => (typeof props.params?.end === 'string' ? props.params.end : '2026-08-10'))
const { data, loading, error } = useStockDaily(code, start.value, end.value)

const slow = ref(60)
const bp = ref(5)

const fast = computed(() => 20)

const com = computed(() => {
  if (!data.value) return null
  const arr = backtestArrays(data.value)
  const pos = shiftPosition(maCrossSignal(arr.closes, fast.value, slow.value))
  // 成本：每次持仓切换按开盘价成交，单边成本 bp（万分比）
  const cost = bp.value / 10000
  const netRet = arr.ret.map((r, i) => {
    const turnover = i > 0 ? Math.abs(pos[i] - pos[i - 1]) : 0 // 0/1 全仓切换
    const costHit = i > 0 ? arr.ret.slice(0, i).reduce((s) => s, 0) * 0 : 0
    void costHit
    // 切换到满仓需付买入成本，切到空仓需付卖出成本，方向与 turnover 相关
    return r * pos[i] - turnover * cost
  })
  const nav = strategyNav(netRet, pos)
  const zeroNav = strategyNav(arr.ret, pos)
  const zeroSt = stats(arr.ret, pos)
  const st = stats(netRet, pos)
  return { arr, pos, nav, zeroNav, zeroSt, st, cost }
})

const option = computed(() => {
  if (!com.value) return {}
  const c = com.value
  return {
    animation: true,
    grid: { left: 52, right: 24, top: 36, bottom: 44 },
    tooltip: {
      trigger: 'axis',
      formatter: (ps: any[]) => {
        const zero = ps.find((p: any) => p.seriesName === '零成本')
        const net = ps.find((p: any) => p.seriesName === '含成本')
        const parts = [ps[0].name]
        if (zero) parts.push(`零成本 ${Number(zero.value[1]).toFixed(1)}`)
        if (net) parts.push(`含${bp.value}bp ${Number(net.value[1]).toFixed(1)}`)
        return parts.join('<br/>')
      },
    },
    legend: { top: 0, textStyle: { fontSize: 12 }, data: ['零成本', '含成本'] },
    xAxis: { type: 'category', data: c.arr.dates, axisLabel: { fontSize: 10, hideOverlap: true } },
    yAxis: { type: 'value', name: '净值（起点=100）', nameLocation: 'middle', nameGap: 44, scale: true, axisLabel: { fontSize: 10 } },
    series: [
      {
        name: '零成本',
        type: 'line',
        data: c.zeroNav.map((v) => +v.toFixed(1)),
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 1.4, color: C.value.slate, type: 'dashed' },
      },
      {
        name: '含成本',
        type: 'line',
        data: c.nav.map((v) => +v.toFixed(1)),
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 2, color: C.value.warning },
      },
    ],
  }
})
</script>

<template>
  <div class="ci">
    <div v-if="loading" class="status">数据加载中…</div>
    <div v-else-if="error" class="status">数据不可用</div>
    <template v-else-if="com">
      <div class="result">
        <div class="result-item">
          <span class="result-label">零成本累计</span>
          <strong class="result-value">{{ (com.zeroSt.cum * 100).toFixed(1) }}%</strong>
        </div>
        <div class="result-item">
          <span class="result-label">含 {{ bp }}bp 累计</span>
          <strong class="result-value" :style="{ color: com.st.cum >= 0 ? 'var(--success, #16a34a)' : 'var(--danger, #dc2626)' }">{{ (com.st.cum * 100).toFixed(1) }}%</strong>
        </div>
        <div class="result-item">
          <span class="result-label">侵蚀</span>
          <strong class="result-value" style="color: var(--danger, #dc2626)">{{ ((com.zeroSt.cum - com.st.cum) * 100).toFixed(1) }}%</strong>
        </div>
        <div class="result-item">
          <span class="result-label">信号次数</span>
          <strong class="result-value">{{ com.zeroSt.switches }}</strong>
        </div>
      </div>
      <ThemedChart class="chart" :option="option" autoresize />
      <div class="controls">
        <div class="control-row">
          <span class="control-label">单边成本</span>
          <input v-model.number="bp" type="range" min="0" max="30" step="1" class="slider" />
          <span class="control-value">{{ bp }} bp</span>
        </div>
        <div class="control-row">
          <span class="control-label">慢线 MA</span>
          <input v-model.number="slow" type="range" min="10" max="250" step="1" class="slider" />
          <span class="control-value">{{ slow }}</span>
        </div>
        <p class="hint">
          快线固定 MA20。每次满仓/空仓切换按成交额 × 单边成本扣费。策略换手越高，成本侵蚀越明显。
        </p>
      </div>
    </template>
  </div>
</template>

<style scoped>
.ci { padding: 16px; }
.status { height: 340px; display: flex; align-items: center; justify-content: center; color: var(--text-3); font-size: 14px; }
.chart { height: 320px; }
.result { display: flex; gap: 22px; margin-bottom: 12px; padding: 12px 16px; background: var(--primary-soft); border-radius: var(--radius-sm); flex-wrap: wrap; }
.result-item { display: flex; flex-direction: column; gap: 2px; }
.result-label { font-size: 12px; color: var(--text-3); }
.result-value { font-size: 18px; font-weight: 700; }
.controls { margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--border); display: flex; flex-direction: column; gap: 10px; }
.control-row { display: flex; align-items: center; gap: 12px; }
.control-label { width: 76px; font-size: 13px; color: var(--text-2); flex-shrink: 0; }
.slider { flex: 1; accent-color: var(--primary); cursor: pointer; }
.control-value { width: 56px; font-size: 13px; font-weight: 600; color: var(--primary); text-align: right; flex-shrink: 0; }
.hint { margin-top: 10px; font-size: 12px; color: var(--text-3); line-height: 1.7; }
</style>