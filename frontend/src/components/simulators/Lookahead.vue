<script setup lang="ts">
import { computed, ref } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { useStockDaily } from '@/composables/useStockDaily'
import { maCrossSignal, strategyNav, backtestArrays } from '@/utils/strategies'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent])

// 前视偏差演示：✓ 信号次日开盘成交 vs ✗ 信号当日收盘前视成交
const props = defineProps<{
  params?: Record<string, unknown>
}>()

const code = computed(() => (typeof props.params?.code === 'string' ? props.params.code : 'sh600519'))
const start = computed(() => (typeof props.params?.start === 'string' ? props.params.start : '2020-01-01'))
const end = computed(() => (typeof props.params?.end === 'string' ? props.params.end : '2026-08-10'))
const { data, loading, error } = useStockDaily(code, start.value, end.value)

const fast = ref(20)
const slow = ref(60)
const effFast = computed(() => Math.min(fast.value, slow.value - 1))

const com = computed(() => {
  if (!data.value) return null
  const arr = backtestArrays(data.value)
  const rawSig = maCrossSignal(arr.closes, effFast.value, slow.value)
  // ✓ 合规：持仓 = 信号 shift 1（次日才生效）→ 净值起点 100，逐日 r*pos
  const posCompliant: number[] = rawSig.map((_, i) => (i === 0 ? 0 : rawSig[i - 1]))
  // ✗ 前视：当日收盘看到金叉 → 当日收盘价就成交（信号用当日数据）
  const posLookahead = rawSig.slice(0)
  const compliantNav = strategyNav(arr.ret, posCompliant)
  const lookaheadNav = strategyNav(arr.ret, posLookahead)
  const diff = lookaheadNav[lookaheadNav.length - 1] - compliantNav[compliantNav.length - 1]
  return { arr, compliantNav, lookaheadNav, diff }
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
        const ok = ps.find((p: any) => p.seriesName === '✓ 合规（次日成交）')
        const bad = ps.find((p: any) => p.seriesName === '✗ 前视（当日成交）')
        const parts = [ps[0].name]
        if (ok) parts.push(`合规 ${Number(ok.value[1]).toFixed(1)}`)
        if (bad) parts.push(`前视 ${Number(bad.value[1]).toFixed(1)}`)
        return parts.join('<br/>')
      },
    },
    legend: { top: 0, textStyle: { fontSize: 12 }, data: ['✓ 合规（次日成交）', '✗ 前视（当日成交）'] },
    xAxis: { type: 'category', data: c.arr.dates, axisLabel: { fontSize: 10, hideOverlap: true } },
    yAxis: { type: 'value', name: '净值（起点=100）', nameLocation: 'middle', nameGap: 44, scale: true, axisLabel: { fontSize: 10 } },
    series: [
      {
        name: '✓ 合规（次日成交）',
        type: 'line',
        data: c.compliantNav.map((v) => +v.toFixed(1)),
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 1.8, color: C.value.success },
      },
      {
        name: '✗ 前视（当日成交）',
        type: 'line',
        data: c.lookaheadNav.map((v) => +v.toFixed(1)),
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 1.8, color: C.value.danger },
      },
    ],
  }
})
</script>

<template>
  <div class="la">
    <div v-if="loading" class="status">数据加载中…</div>
    <div v-else-if="error" class="status">数据不可用</div>
    <template v-else-if="com">
      <div class="result">
        <div class="result-item">
          <span class="result-label">✓ 合规累计</span>
          <strong class="result-value" style="color: var(--success, #16a34a)">{{ (((com.compliantNav[com.compliantNav.length - 1] / 100 - 1) * 100)).toFixed(1) }}%</strong>
        </div>
        <div class="result-item">
          <span class="result-label">✗ 前视累计</span>
          <strong class="result-value" style="color: var(--danger, #dc2626)">{{ (((com.lookaheadNav[com.lookaheadNav.length - 1] / 100 - 1) * 100)).toFixed(1) }}%</strong>
        </div>
        <div class="result-item">
          <span class="result-label">虚假超额</span>
          <strong class="result-value" style="color: var(--warning, #d97706)">{{ com.diff.toFixed(1) }} 点</strong>
        </div>
      </div>
      <ThemedChart class="chart" :option="option" autoresize />
      <div class="controls">
        <div class="control-row">
          <span class="control-label">快线 MA</span>
          <input v-model.number="fast" type="range" min="5" max="120" step="1" class="slider" />
          <span class="control-value">{{ effFast }}</span>
        </div>
        <div class="control-row">
          <span class="control-label">慢线 MA</span>
          <input v-model.number="slow" type="range" min="10" max="250" step="1" class="slider" />
          <span class="control-value">{{ slow }}</span>
        </div>
        <p class="hint">两条曲线的差距 = 前视偏差的「虚假超额」：把明天才知道的方向用在了今天。参数越敏感，差距越大。</p>
      </div>
    </template>
  </div>
</template>

<style scoped>
.la { padding: 16px; }
.status { height: 340px; display: flex; align-items: center; justify-content: center; color: var(--text-3); font-size: 14px; }
.chart { height: 320px; }
.result { display: flex; gap: 22px; margin-bottom: 12px; padding: 12px 16px; background: var(--primary-soft); border-radius: var(--radius-sm); flex-wrap: wrap; }
.result-item { display: flex; flex-direction: column; gap: 2px; }
.result-label { font-size: 12px; color: var(--text-3); }
.result-value { font-size: 18px; font-weight: 700; }
.controls { margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--border); display: flex; flex-direction: column; gap: 10px; }
.control-row { display: flex; align-items: center; gap: 12px; }
.control-label { width: 72px; font-size: 13px; color: var(--text-2); flex-shrink: 0; }
.slider { flex: 1; accent-color: var(--primary); cursor: pointer; }
.control-value { width: 44px; font-size: 13px; font-weight: 600; color: var(--primary); text-align: right; flex-shrink: 0; }
.hint { margin-top: 10px; font-size: 12px; color: var(--text-3); line-height: 1.7; }
</style>