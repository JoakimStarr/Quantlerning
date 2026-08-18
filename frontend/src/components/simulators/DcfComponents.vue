<script setup lang="ts">
import { computed, ref } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'

use([CanvasRenderer, BarChart, GridComponent, TooltipComponent])

// 两阶段 DCF 价值构成（教学示意）：显式期现值 vs 终值现值，直观展示「终值占 60-80%」
const props = defineProps<{
  params?: Record<string, unknown>
}>()

const fcf0 = ref(typeof props.params?.f0 === 'number' ? props.params.f0 : 100) // 初始自由现金流
const g = ref(typeof props.params?.g === 'number' ? props.params.g : 10) // 显式期增长率 %
const n = ref(typeof props.params?.n === 'number' ? props.params.n : 5) // 显式期年数
const r = ref(typeof props.params?.r === 'number' ? props.params.r : 9) // WACC %
const gInf = ref(typeof props.params?.gi === 'number' ? props.params.gi : 3) // 永续增长率 %

// 两阶段 DCF 计算
const calc = computed(() => {
  const R = r.value / 100
  const GG = g.value / 100
  const GI = gInf.value / 100
  if (R <= GI) return null // 分母必须为正
  let fcf = fcf0.value
  let explicit = 0
  const years: number[] = []
  for (let t = 1; t <= n.value; t++) {
    fcf *= 1 + GG
    const pv = fcf / (1 + R) ** t
    explicit += pv
    years.push(+pv.toFixed(0))
  }
  const tv = (fcf * (1 + GI)) / (R - GI)
  const tvPv = tv / (1 + R) ** n.value
  const total = explicit + tvPv
  return {
    years,
    explicit,
    tv,
    tvPv,
    total,
    tvPct: total > 0 ? (tvPv / total) * 100 : 0,
  }
})

const option = computed(() => {
  const c = calc.value
  if (!c) return {}
  const expPct = 100 - c.tvPct
  return {
    animation: true,
    tooltip: {
      trigger: 'item',
      formatter: (p: any) => `${p.name}<br/>　${p.value.toFixed(0)} 亿（${p.percent.toFixed(0)}%）`,
    },
    grid: { left: 60, right: 30, top: 10, bottom: 30 },
    xAxis: { type: 'value', axisLabel: { fontSize: 10 }, splitLine: { lineStyle: { color: C.value.grid } } },
    yAxis: { type: 'category', data: ['价值构成'], axisLabel: { fontSize: 11 } },
    series: [
      {
        name: '价值',
        type: 'bar',
        stack: 'total',
        barWidth: 34,
        data: [{ value: +c.explicit.toFixed(0), itemStyle: { color: C.value.primary }, name: `显式期现值（${expPct.toFixed(0)}%）` }],
      },
      {
        name: '终值',
        type: 'bar',
        stack: 'total',
        barWidth: 34,
        data: [{ value: +c.tvPv.toFixed(0), itemStyle: { color: C.value.warning }, name: `终值现值（${c.tvPct.toFixed(0)}%）` }],
      },
    ],
  }
})

const fmt = (v: number) => `${v.toFixed(0)} 亿`
</script>

<template>
  <div class="dcf">
    <div class="controls">
      <div class="control-row">
        <span class="control-label">FCF₀</span>
        <input v-model.number="fcf0" type="range" min="50" max="300" step="10" class="slider" />
        <span class="control-value">{{ fcf0 }}</span>
      </div>
      <div class="control-row">
        <span class="control-label">显式期增长 g</span>
        <input v-model.number="g" type="range" min="3" max="20" step="1" class="slider" />
        <span class="control-value">{{ g }}%</span>
      </div>
      <div class="control-row">
        <span class="control-label">显式期年数 N</span>
        <input v-model.number="n" type="range" min="3" max="10" step="1" class="slider" />
        <span class="control-value">{{ n }} 年</span>
      </div>
      <div class="control-row">
        <span class="control-label">WACC r</span>
        <input v-model.number="r" type="range" min="6" max="15" step="0.5" class="slider" />
        <span class="control-value">{{ r }}%</span>
      </div>
      <div class="control-row">
        <span class="control-label">永续增长 g∞</span>
        <input v-model.number="gInf" type="range" min="0" max="6" step="0.5" class="slider" />
        <span class="control-value">{{ gInf }}%</span>
      </div>
    </div>

    <div v-if="!calc" class="status">参数无效：永续增长率必须小于 WACC</div>
    <template v-else>
      <div class="cards">
        <div class="card"><span>显式期现值</span><strong>{{ fmt(calc.explicit) }}</strong></div>
        <div class="card"><span>终值现值</span><strong>{{ fmt(calc.tvPv) }}</strong></div>
        <div class="card"><span>内在价值</span><strong>{{ fmt(calc.total) }}</strong></div>
        <div class="card"><span>终值占比</span><strong>{{ calc.tvPct.toFixed(0) }}%</strong></div>
      </div>
      <ThemedChart class="chart" :option="option" autoresize />
      <p class="hint">
        教学示意（非真实数据）：横条长度 = 两段各自对内在价值的贡献。注意「终值占比」——拉动 g∞ 或 r，看它如何剧烈变动。默认参数（FCF₀=100、g=10%、N=5、r=9%、g∞=3%）下终值占约 78%：估值的八成押在「第 5 年后永续 3%、折现 9%」两个假设上，这就是 DCF 必须做敏感性分析的原因。
      </p>
    </template>
  </div>
</template>

<style scoped>
.dcf { padding: 16px; }
.status { height: 180px; display: flex; align-items: center; justify-content: center; color: var(--text-3); font-size: 14px; }
.chart { height: 180px; }
.controls { display: flex; flex-direction: column; gap: 8px; margin-bottom: 14px; }
.control-row { display: flex; align-items: center; gap: 12px; }
.control-label { width: 110px; font-size: 12.5px; color: var(--text-2); flex-shrink: 0; }
.slider { flex: 1; accent-color: var(--primary); cursor: pointer; }
.control-value { width: 52px; font-size: 12.5px; font-weight: 600; color: var(--primary); text-align: right; flex-shrink: 0; }
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(110px, 1fr)); gap: 10px; margin-bottom: 12px; }
.card { display: flex; flex-direction: column; gap: 2px; padding: 9px 12px; background: var(--primary-soft); border-radius: var(--radius-sm); font-size: 11.5px; color: var(--text-3); }
.card strong { font-size: 15px; font-weight: 700; color: var(--text-1); }
.hint { margin-top: 10px; font-size: 12px; color: var(--text-3); line-height: 1.7; }
</style>
