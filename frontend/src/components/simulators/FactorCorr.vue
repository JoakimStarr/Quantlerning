<script setup lang="ts">
import { computed, ref } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { HeatmapChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, VisualMapComponent } from 'echarts/components'

use([CanvasRenderer, HeatmapChart, GridComponent, TooltipComponent, VisualMapComponent])

// 因子相关性矩阵（教学示意，数值为构造示例，非真实因子库计算）：
// 动量类因子（ROC20/ROC60/MA5）之间高相关——捕捉同一信息；
// 动量类与波动/流动性类低相关——提供不同维度的 alpha
// 教学点：合成前先看相关性，>0.7 视为冗余

const names = ['ROC20', 'ROC60', 'MA5', 'VOL20', 'TURN', 'AMT']
// 对称相关矩阵：动量类内部高相关，跨类低相关
const base = [
  [1.0, 0.82, 0.71, 0.12, 0.08, 0.05],
  [0.82, 1.0, 0.75, 0.10, 0.06, 0.04],
  [0.71, 0.75, 1.0, 0.15, 0.12, 0.09],
  [0.12, 0.10, 0.15, 1.0, 0.58, 0.46],
  [0.08, 0.06, 0.12, 0.58, 1.0, 0.83],
  [0.05, 0.04, 0.09, 0.46, 0.83, 1.0],
]

const threshold = ref(0.7) // 冗余阈值

const cells = computed<[number, number, number][]>(() => {
  const out: [number, number, number][] = []
  base.forEach((row, i) => row.forEach((v, j) => out.push([j, i, v])))
  return out
})

const option = computed(() => ({
  animation: false,
  grid: { left: 80, right: 40, top: 30, bottom: 70 },
  tooltip: {
    position: 'top',
    formatter: (p: any) => {
      const v = base[p.value[1]][p.value[0]]
      return `${names[p.value[1]]} × ${names[p.value[0]]}<br/>相关 ${v.toFixed(2)}<br/>${v > threshold.value ? '⚠ 高于阈值，视为冗余' : v > 0.5 ? '中高相关' : '低相关'}`
    },
  },
  xAxis: { type: 'category', data: names, axisLabel: { fontSize: 11, rotate: 20 } },
  yAxis: { type: 'category', data: names, axisLabel: { fontSize: 11 } },
  visualMap: {
    min: 0,
    max: 1,
    calculable: false,
    orient: 'horizontal',
    left: 'center',
    bottom: 4,
    inRange: { color: ['#f8fafc', '#93c5fd', C.value.primary, C.value.primaryDeep] },
    textStyle: { fontSize: 10 },
  },
  series: [
    {
      type: 'heatmap',
      data: cells.value,
      label: { show: true, fontSize: 11, formatter: (p: any) => base[p.value[1]][p.value[0]].toFixed(2) },
      itemStyle: { borderColor: '#fff', borderWidth: 2 },
    },
  ],
}))

// 高相关对数
const redundant = computed(() => {
  const out: string[] = []
  for (let i = 0; i < names.length; i++) {
    for (let j = i + 1; j < names.length; j++) {
      if (base[i][j] > threshold.value) out.push(`${names[i]} × ${names[j]} (${base[i][j].toFixed(2)})`)
    }
  }
  return out
})
</script>

<template>
  <div class="factor-corr">
    <div class="stats">
      <span class="chip">动量类（ROC/MA）内部高相关</span>
      <span class="chip">动量 × 波动/流动性 低相关</span>
      <span class="chip" v-if="redundant.length">冗余对（&gt;{{ threshold.toFixed(1) }}）：{{ redundant.join('，') }}</span>
    </div>

    <ThemedChart class="chart" :option="option" autoresize />

    <div class="controls">
      <div class="control-row">
        <span class="control-label">冗余阈值</span>
        <input v-model.number="threshold" type="range" min="0.5" max="0.9" step="0.05" class="slider" />
        <span class="control-value">{{ threshold.toFixed(2) }}</span>
      </div>
      <div class="tip">
        因子相关矩阵的读法：同一类因子（如动量族的 ROC20/ROC60/MA5）之间高度相关——它们捕捉的是同一信息，
        合成时重复加权等于「同一个信号买三遍」；跨类（动量 vs 波动 vs 流动性）相关性低，才真正提供不同维度的 alpha。
        合成前把相关性 > 阈值（常用 0.7）的因子视为冗余、保留代表性因子即可。教学示意：矩阵数值为构造示例，反映真实因子库的典型结构。
      </div>
    </div>
  </div>
</template>

<style scoped>
.factor-corr { padding: 16px; }
.chart { height: 340px; }
.stats { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
.chip {
  font-size: 12px; color: var(--text-3);
  padding: 4px 10px; border-radius: 999px; background: var(--bg-hover);
}
.controls { margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border); }
.control-row { display: flex; align-items: center; gap: 12px; }
.control-label { width: 88px; font-size: 13px; color: var(--text-2); flex-shrink: 0; }
.slider { flex: 1; accent-color: var(--primary); cursor: pointer; }
.control-value { width: 48px; font-size: 13px; font-weight: 600; color: var(--primary); text-align: right; flex-shrink: 0; }
.tip { margin-top: 10px; font-size: 12.5px; color: var(--text-3); line-height: 1.7; }
</style>
