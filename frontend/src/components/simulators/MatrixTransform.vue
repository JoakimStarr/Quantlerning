<script setup lang="ts">
import { computed, ref } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C, withAlpha } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, ScatterChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'

use([CanvasRenderer, LineChart, ScatterChart, GridComponent, TooltipComponent, LegendComponent])

// 矩阵变换演示：2×2 矩阵 A 把单位方格/基向量映射成平行四边/列向量
// 教学点：矩阵乘法是线性变换——矩阵的列 = 基向量 (1,0)/(0,1) 的像；行列式 = 面积缩放
// 教学演示（矩阵为示意，非真实数据）

const props = defineProps<{
  params?: Record<string, unknown>
}>()

const a = ref(typeof props.params?.a === 'number' ? props.params.a : 1.5)
const b = ref(typeof props.params?.b === 'number' ? props.params.b : 0.6)
const c = ref(typeof props.params?.c === 'number' ? props.params.c : 0.4)
const d = ref(typeof props.params?.d === 'number' ? props.params.d : 1.2)

// 矩阵 A = [[a, b], [c, d]]
// A·(x, y) = (a x + b y, c x + d y)

function transform(x: number, y: number): [number, number] {
  return [a.value * x + b.value * y, c.value * x + d.value * y]
}

// 单位方格四个角（按顺序围成四边形）
const unitCorners: Array<[number, number]> = [
  [0, 0],
  [1, 0],
  [1, 1],
  [0, 1],
  [0, 0],
]
const imageCorners = computed<Array<[number, number]>>(() => unitCorners.map(([x, y]) => transform(x, y)))

// 基向量的像：A·(1,0) = 第一列，A·(0,1) = 第二列
const col1 = computed<[number, number]>(() => transform(1, 0))
const col2 = computed<[number, number]>(() => transform(0, 1))

// 单位圆 → 椭圆（用于展示整体缩放）
const N = 240
const unitCircle = computed<Array<[number, number]>>(() => {
  const out: Array<[number, number]> = []
  for (let i = 0; i <= N; i++) {
    const theta = (i / N) * 2 * Math.PI
    out.push([Number(Math.cos(theta).toFixed(4)), Number(Math.sin(theta).toFixed(4))])
  }
  return out
})
const imageCircle = computed<Array<[number, number]>>(() =>
  unitCircle.value.map(([x, y]) => {
    const [px, py] = transform(x, y)
    return [Number(px.toFixed(4)), Number(py.toFixed(4))]
  }),
)

// 行列式：面积缩放倍率
const det = computed(() => a.value * d.value - b.value * c.value)
const sense = computed(() => (det.value >= 0 ? '正（保持方向）' : '负（翻转方向）'))

// 可拖动的输入向量 v
const vx = ref(0.8)
const vy = ref(0.5)
const vImage = computed<[number, number]>(() => transform(vx.value, vy.value))

const option = computed(() => {
  const series: any[] = [
    {
      name: '单位圆',
      type: 'line',
      data: unitCircle.value,
      smooth: true,
      symbol: 'none',
      lineStyle: { width: 1, color: C.value.slate, type: 'dashed' },
      itemStyle: { color: C.value.slate },
    },
    {
      name: 'A·单位圆',
      type: 'line',
      data: imageCircle.value,
      smooth: true,
      symbol: 'none',
      lineStyle: { width: 1.5, color: C.value.primary, type: 'dashed' },
      itemStyle: { color: C.value.primary },
    },
    {
      name: '单位方格',
      type: 'line',
      data: unitCorners,
      smooth: false,
      symbol: 'none',
      lineStyle: { width: 1, color: C.value.slateStrong, type: 'dotted' },
      itemStyle: { color: C.value.slateStrong },
    },
    {
      name: 'A·单位方格',
      type: 'line',
      data: imageCorners.value,
      smooth: false,
      symbol: 'none',
      lineStyle: { width: 2, color: C.value.danger },
      itemStyle: { color: C.value.danger },
      areaStyle: { color: withAlpha(C.value.danger, 0.08) },
    },
    {
      name: '基向量 e₁ 的像',
      type: 'line',
      data: [
        [0, 0],
        col1.value,
      ],
      symbol: 'none',
      lineStyle: { width: 2, color: C.value.warning },
      itemStyle: { color: C.value.warning },
    },
    {
      name: '基向量 e₂ 的像',
      type: 'line',
      data: [
        [0, 0],
        col2.value,
      ],
      symbol: 'none',
      lineStyle: { width: 2, color: C.value.success },
      itemStyle: { color: C.value.success },
    },
    {
      name: '输入向量 v',
      type: 'scatter',
      data: [[vx.value, vy.value]],
      symbolSize: 8,
      itemStyle: { color: C.value.warning },
    },
    {
      name: 'A·v',
      type: 'scatter',
      data: [vImage.value],
      symbolSize: 9,
      symbol: 'pin',
      itemStyle: { color: C.value.violet },
    },
  ]
  return {
    animation: true,
    grid: { left: 40, right: 40, top: 36, bottom: 40 },
    tooltip: { trigger: 'item' },
    legend: { top: 0, type: 'scroll', textStyle: { fontSize: 10 } },
    xAxis: { type: 'value', name: 'x', nameLocation: 'middle', nameGap: 26, min: -3, max: 3, splitLine: { lineStyle: { type: 'dashed' } }, axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', name: 'y', nameLocation: 'middle', nameGap: 36, min: -3, max: 3, splitLine: { lineStyle: { type: 'dashed' } }, axisLabel: { fontSize: 10 } },
    series,
  }
})
</script>

<template>
  <div class="matrix-sim">
    <ThemedChart class="chart" :option="option" autoresize />

    <div class="controls">
      <div class="control-row">
        <span class="control-label">矩阵 A₁₁</span>
        <input v-model.number="a" type="range" min="-2" max="2" step="0.1" class="slider" />
        <span class="control-value">{{ a.toFixed(1) }}</span>
      </div>
      <div class="control-row">
        <span class="control-label">矩阵 A₁₂</span>
        <input v-model.number="b" type="range" min="-2" max="2" step="0.1" class="slider" />
        <span class="control-value">{{ b.toFixed(1) }}</span>
      </div>
      <div class="control-row">
        <span class="control-label">矩阵 A₂₁</span>
        <input v-model.number="c" type="range" min="-2" max="2" step="0.1" class="slider" />
        <span class="control-value">{{ c.toFixed(1) }}</span>
      </div>
      <div class="control-row">
        <span class="control-label">矩阵 A₂₂</span>
        <input v-model.number="d" type="range" min="-2" max="2" step="0.1" class="slider" />
        <span class="control-value">{{ d.toFixed(1) }}</span>
      </div>
      <div class="control-row">
        <span class="control-label">向量 v</span>
        <div class="dual">
          <input v-model.number="vx" type="range" min="-3" max="3" step="0.1" class="slider" />
          <input v-model.number="vy" type="range" min="-3" max="3" step="0.1" class="slider" />
        </div>
        <span class="control-value">({{ vx.toFixed(1) }}, {{ vy.toFixed(1) }})</span>
      </div>
      <div class="result-row">
        <div class="result-box">
          <span class="muted">A·v</span>
          <strong class="num-purple">({{ vImage[0].toFixed(2) }}, {{ vImage[1].toFixed(2) }})</strong>
        </div>
        <div class="result-box">
          <span class="muted">行列式 det(A)（面积缩放）</span>
          <strong :class="det >= 0 ? 'num-green' : 'num-red'">{{ det.toFixed(2) }}</strong>
        </div>
        <div class="result-box">
          <span class="muted">变换方向</span>
          <strong :class="det >= 0 ? 'num-green' : 'num-red'">{{ sense }}</strong>
        </div>
      </div>
      <p class="hint">
        红色四边形 = 单位方格被 $A$ 作用后的像，面积缩放倍率正是行列式 $\det(A)$；
        橙色/绿色向量 = 基向量 $e_1, e_2$ 的像——它们恰好是矩阵 $A$ 的两列（$A e_1 = $ 第一列）。
        输入向量 $v$（橙色点）经 $A$ 作用得到 $A v$（紫色点）。这就是「矩阵乘法是线性变换」的几何含义。
      </p>
    </div>
  </div>
</template>

<style scoped>
.matrix-sim { padding: 16px; }
.chart { height: 380px; }
.controls { margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border); display: flex; flex-direction: column; gap: 10px; }
.control-row { display: flex; align-items: center; gap: 12px; }
.control-label { width: 88px; font-size: 13px; color: var(--text-2); flex-shrink: 0; }
.slider { flex: 1; accent-color: var(--primary); cursor: pointer; }
.control-value { width: 64px; font-size: 13px; font-weight: 600; color: var(--primary); text-align: right; flex-shrink: 0; }
.dual { flex: 1; display: flex; flex-direction: column; gap: 2px; }
.result-row { display: flex; gap: 10px; margin-top: 8px; }
.result-box { flex: 1; padding: 8px 10px; border-radius: var(--radius-sm); background: var(--bg-hover); text-align: center; display: flex; flex-direction: column; gap: 2px; }
.result-box strong { font-size: 14px; }
.num-purple { color: var(--violet, #7c3aed); }
.num-green { color: var(--success, #16a34a); }
.num-red { color: var(--danger, #dc2626); }
.muted { font-size: 12px; color: var(--text-3); }
.hint { margin-top: 8px; font-size: 12px; color: var(--text-3); line-height: 1.7; }
</style>
