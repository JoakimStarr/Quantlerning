<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, MarkLineComponent } from 'echarts/components'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent])

// 大数法则：抛硬币模拟，样本均值收敛到真实概率 p
// 随机模拟（非真实数据）

const props = defineProps<{
  params?: Record<string, unknown>
}>()

const p = ref(typeof props.params?.p === 'number' ? props.params.p : 0.5)
const flips = ref<number[]>([])

// p 变化时清空重来，避免旧样本来自不同分布
watch(p, () => {
  flips.value = []
})

function addFlips(count: number) {
  const arr = flips.value.slice()
  for (let i = 0; i < count; i++) {
    arr.push(Math.random() < p.value ? 1 : 0)
  }
  flips.value = arr
}

function reset() {
  flips.value = []
}

// 累积样本均值曲线：[[n, mean_n], ...]，每 1 个样本一个点
const meanCurve = computed<[number, number][]>(() => {
  const out: [number, number][] = []
  let sum = 0
  for (let i = 0; i < flips.value.length; i++) {
    sum += flips.value[i]
    out.push([i + 1, Number((sum / (i + 1)).toFixed(5))])
  }
  return out
})

const currentMean = computed(() =>
  flips.value.length === 0 ? 0 : flips.value.reduce((s, v) => s + v, 0) / flips.value.length,
)

const deviation = computed(() => Math.abs(currentMean.value - p.value))

const option = computed(() => ({
  animation: true,
  grid: { left: 55, right: 25, top: 40, bottom: 45 },
  tooltip: {
    trigger: 'axis',
    formatter: (params: any) => {
      const arr = Array.isArray(params) ? params : [params]
      return arr
        .map((pa: any) => {
          const v = pa.value as number[]
          return `${pa.seriesName}: ${Number(v[1]).toFixed(4)}（n=${v[0]}）`
        })
        .join('<br/>')
    },
  },
  legend: { top: 0, textStyle: { fontSize: 12 } },
  xAxis: {
    type: 'value',
    name: '样本量 n',
    nameLocation: 'middle',
    nameGap: 30,
    min: 0,
    max: Math.max(100, flips.value.length + 10),
    axisLabel: { fontSize: 11 },
  },
  yAxis: {
    type: 'value',
    name: '样本均值',
    nameLocation: 'middle',
    nameGap: 42,
    min: 0,
    max: 1,
    axisLabel: { fontSize: 11 },
  },
  series: [
    {
      name: '样本均值',
      type: 'line',
      showSymbol: false,
      data: meanCurve.value,
      lineStyle: { width: 2.5, color: '#2563eb' },
      itemStyle: { color: '#2563eb' },
      markLine: {
        silent: true,
        symbol: 'none',
        lineStyle: { type: 'dashed', color: '#d97706' },
        label: { fontSize: 11, color: '#d97706', formatter: `p = ${(p.value * 100).toFixed(0)}%` },
        data: [{ yAxis: p.value }],
      },
    },
  ],
}))
</script>

<template>
  <div class="lln">
    <VChart class="chart" :option="option" autoresize />

    <div class="controls">
      <div class="control-row">
        <span class="control-label">真实概率 p</span>
        <input v-model.number="p" type="range" min="0.2" max="0.8" step="0.05" class="slider" />
        <span class="control-value">{{ (p * 100).toFixed(0) }}%</span>
      </div>
      <div class="btn-row">
        <button class="btn" @click="addFlips(100)">再投 100 次</button>
        <button class="btn" @click="addFlips(1000)">再投 1000 次</button>
        <button class="btn btn-reset" @click="reset">重置</button>
        <div class="lln-stats">
          <span class="stat-chip">n = <strong>{{ flips.length }}</strong></span>
          <span class="stat-chip">样本均值 = <strong>{{ (currentMean * 100).toFixed(2) }}%</strong></span>
          <span class="stat-chip">偏差 |均值−p| = <strong>{{ (deviation * 100).toFixed(2) }}%</strong></span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.lln { padding: 16px; }
.chart { height: 320px; }
.controls { margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border); display: flex; flex-direction: column; gap: 10px; }
.control-row { display: flex; align-items: center; gap: 12px; }
.control-label { width: 84px; font-size: 13px; color: var(--text-2); flex-shrink: 0; }
.slider { flex: 1; accent-color: var(--primary); cursor: pointer; }
.control-value { width: 48px; font-size: 13px; font-weight: 600; color: var(--primary); text-align: right; flex-shrink: 0; }
.btn-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-top: 4px; }
.btn {
  padding: 5px 14px; border: 1px solid var(--border); border-radius: var(--radius-sm);
  background: var(--bg-card); color: var(--text-1); font-size: 13px; cursor: pointer;
  transition: all 0.15s;
}
.btn:hover { border-color: var(--primary); color: var(--primary); }
.btn-reset { color: var(--text-3); }
.btn-reset:hover { border-color: var(--warning); color: var(--warning); }
.lln-stats { display: flex; gap: 8px; margin-left: auto; flex-wrap: wrap; }
.stat-chip {
  font-size: 12.5px; color: var(--text-3);
  padding: 4px 10px; border-radius: 999px; background: var(--bg-hover);
}
.stat-chip strong { color: var(--primary); }
</style>
