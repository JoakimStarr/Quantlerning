<script setup lang="ts">
// 波动率微笑（教学示意，非真实期权数据）：IV vs 行权价曲线
// 教学点：BS 假设 σ 恒定，但市场用不同行权价报出不同 IV——
// 微笑（两端高、平值低）与偏斜（低行权价 IV 显著更高）是 BS 假设失效的图形证据
import { computed, ref } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, MarkLineComponent } from 'echarts/components'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent])

// 教学示意参数
const S = ref(100)
const smileDepth = ref(6) // 微笑深度（两端高于平值的百分点）

// 微笑形状：两端高、中间低；偏斜：低行权价显著高、高行权价略低
function smileIv(moneyness: number, mode: 'smile' | 'skew'): number {
  const atm = 0.22 // 平值 IV 基准
  if (mode === 'smile') {
    // 抛物线：|m| 越大 IV 越高
    return atm + (smileDepth.value / 100) * moneyness * moneyness
  }
  // 偏斜：m<0（价内看跌/价外看涨一侧）IV 高，线性下降
  return atm - 0.06 * moneyness + (smileDepth.value / 100) * 0.3
}

const mode = ref<'smile' | 'skew'>('smile')

const curve = computed(() => {
  // moneyness m = K/S - 1，范围 -0.3 ~ +0.3
  const xs = Array.from({ length: 25 }, (_, i) => -0.3 + i * 0.025)
  return xs.map((m) => ({
    k: S.value * (1 + m),
    iv: smileIv(m, mode.value),
  }))
})

const option = computed(() => {
  const c = curve.value
  return {
    animation: false,
    grid: { left: 52, right: 24, top: 36, bottom: 44 },
    tooltip: {
      trigger: 'axis',
      formatter: (ps: any[]) => {
        const p = ps[0]
        return `行权价 K = ${p.data[0].toFixed(0)}<br/>隐含波动率 = ${(p.data[1] * 100).toFixed(1)}%`
      },
    },
    legend: { top: 0, textStyle: { fontSize: 11 } },
    xAxis: { type: 'value', name: '行权价 K', nameLocation: 'middle', nameGap: 30, axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', name: '隐含波动率', nameLocation: 'middle', nameGap: 36, axisLabel: { fontSize: 10, formatter: (v: number) => `${(v * 100).toFixed(0)}%` } },
    series: [
      {
        name: mode.value === 'smile' ? '微笑（两端高）' : '偏斜（低 K 高）',
        type: 'line',
        data: c.map((p) => [+p.k.toFixed(1), +p.iv.toFixed(4)]),
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 2.5, color: C.value.primary },
        areaStyle: { color: C.value.primary, opacity: 0.08 },
        markLine: {
          silent: true,
          symbol: 'none',
          data: [
            { xAxis: S.value, label: { formatter: '平值 K=S', position: 'insideEndTop' }, lineStyle: { color: C.value.slate, type: 'dashed' } },
            { yAxis: 0.22, label: { formatter: 'BS 恒定 σ=22%', position: 'insideEndRight' }, lineStyle: { color: C.value.danger, type: 'dotted' } },
          ],
        },
      },
    ],
  }
})
</script>

<template>
  <div class="vol-smile">
    <div class="controls">
      <label>S <input type="range" v-model.number="S" min="80" max="120" step="1" /> {{ S }}</label>
      <label>微笑深度 <input type="range" v-model.number="smileDepth" min="1" max="15" step="1" /> {{ smileDepth }}%</label>
    </div>
    <div class="switch">
      <button :class="['gbtn', { on: mode === 'smile' }]" @click="mode = 'smile'">微笑（对称）</button>
      <button :class="['gbtn', { on: mode === 'skew' }]" @click="mode = 'skew'">偏斜（股市常见）</button>
    </div>
    <ThemedChart class="chart" :option="option" autoresize />
    <p class="note">波动率微笑（教学示意，非真实期权数据；暂无 A 股期权行情）。红色虚线 = BS 假设的恒定 $\sigma$。若 BS 完全正确，IV 曲线应是水平虚线；实际曲线两端翘起（微笑）或左端显著更高（偏斜）——这就是「BS 恒定 $\sigma$ 假设失效」的图形证据。</p>
  </div>
</template>

<style scoped>
.vol-smile { padding: 16px; }
.chart { height: 320px; }
.controls { display: flex; gap: 14px; flex-wrap: wrap; align-items: center; margin-bottom: 10px; font-size: 12.5px; color: var(--text-2); }
.controls label { display: flex; align-items: center; gap: 6px; }
.controls input[type='range'] { width: 90px; }
.switch { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 10px; }
.gbtn {
  font-size: 12.5px; padding: 4px 14px; border-radius: 999px; cursor: pointer;
  border: 1px solid var(--border, rgba(128,128,128,0.3)); background: transparent; color: var(--text-2);
}
.gbtn.on { background: var(--primary); color: #fff; border-color: var(--primary); }
.note { font-size: 12.5px; color: var(--text-3); margin-top: 10px; line-height: 1.6; }
</style>
