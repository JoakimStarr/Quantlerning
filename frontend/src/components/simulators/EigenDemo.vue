<script setup lang="ts">
import { computed, ref } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, ScatterChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, MarkLineComponent } from 'echarts/components'

use([CanvasRenderer, LineChart, ScatterChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent])

// 特征值演示：2×2 矩阵 A 对单位向量作用的效果
// A v = λ v 的可视化——特征方向上，向量只被拉伸/压缩（方向不变）
// 教学演示（矩阵为示意，非真实数据）

const props = defineProps<{
  params?: Record<string, unknown>
}>()

const a = ref(typeof props.params?.a === 'number' ? props.params.a : 1.6)
const b = ref(typeof props.params?.b === 'number' ? props.params.b : 0.6)
const c = ref(typeof props.params?.c === 'number' ? props.params.c : 0.4)
const d = ref(typeof props.params?.d === 'number' ? props.params.d : 1.1)

// 单位圆上的向量（起点在原点，箭头指向圆周）
const N = 360

function transform(i: number) {
  const theta = (i / N) * 2 * Math.PI
  return { x: a.value * Math.cos(theta) + b.value * Math.sin(theta), y: c.value * Math.cos(theta) + d.value * Math.sin(theta) }
}

// 变换后的椭圆（所有单位向量经 A 作用后的轨迹）
const ellipse = computed<[number, number][]>(() => {
  const out: [number, number][] = []
  for (let i = 0; i <= N; i++) {
    const p = transform(i)
    out.push([Number(p.x.toFixed(4)), Number(p.y.toFixed(4))])
  }
  return out
})

// 单位圆
const unitCircle = computed<[number, number][]>(() => {
  const out: [number, number][] = []
  for (let i = 0; i <= N; i++) {
    const theta = (i / N) * 2 * Math.PI
    out.push([Number(Math.cos(theta).toFixed(4)), Number(Math.sin(theta).toFixed(4))])
  }
  return out
})

// 特征值（解析解）
const eig = computed(() => {
  const tr = a.value + d.value
  const det = a.value * d.value - b.value * c.value
  const disc = tr * tr - 4 * det
  if (disc < 0) return null
  const sqrt = Math.sqrt(disc)
  return { l1: (tr + sqrt) / 2, l2: (tr - sqrt) / 2 }
})

// 特征向量（对应特征值 λ1）
const eigVec = computed(() => {
  if (!eig.value) return null
  const l1 = eig.value.l1
  // 解 (A - λI)v = 0
  let vx = 0
  let vy = 0
  if (Math.abs(b.value) > 1e-8) {
    vx = -b.value
    vy = a.value - l1
  } else if (Math.abs(a.value - l1) > 1e-8) {
    vx = c.value
    vy = -(d.value - l1)
  } else {
    vx = 1
    vy = 0
  }
  const norm = Math.hypot(vx, vy)
  return { x: vx / norm, y: vy / norm }
})

const option = computed(() => {
  const eigen = eig.value
  const ev = eigVec.value
  const series: any[] = [
    {
      name: '单位圆',
      type: 'line',
      data: unitCircle.value,
      smooth: true,
      symbol: 'none',
      lineStyle: { width: 1.2, color: C.value.slate, type: 'dashed' },
      itemStyle: { color: C.value.slate },
    },
    {
      name: 'A·单位圆',
      type: 'line',
      data: ellipse.value,
      smooth: true,
      symbol: 'none',
      lineStyle: { width: 2, color: C.value.primary },
      itemStyle: { color: C.value.primary },
    },
  ]
  // 特征方向线（A 作用下方向不变，只缩放）
  if (eigen && ev) {
    for (let k = 0; k < 2; k++) {
      const lambda = k === 0 ? eigen.l1 : eigen.l2
      // λ 的符号决定方向是正向还是反向
      const dir = lambda > 0 ? 1 : -1
      const activeVec = k === 0 ? ev : { x: -ev.x, y: -ev.y } // 反方向也是特征方向
      const u = { x: activeVec.x * dir, y: activeVec.y * dir }
      series.push({
        name: `特征方向 λ${k + 1} = ${lambda.toFixed(2)}`,
        type: 'line',
        data: [
          [0, 0],
          [u.x * Math.abs(lambda), u.y * Math.abs(lambda)],
        ],
        symbol: 'none',
        lineStyle: { width: 2, color: k === 0 ? C.value.warning : C.value.danger, type: 'dashed' },
        itemStyle: { color: k === 0 ? C.value.warning : C.value.danger },
        label: { show: true, fontSize: 10, color: k === 0 ? C.value.warning : C.value.danger, formatter: `λ = ${lambda.toFixed(2)}` },
      })
    }
  }
  series.push({
    name: '参考单位向量 (1,0)',
    type: 'scatter',
    data: [[1, 0]],
    symbolSize: 6,
    itemStyle: { color: C.value.slateStrong },
  })
  return {
    animation: true,
    grid: { left: 40, right: 40, top: 40, bottom: 40 },
    tooltip: {
      trigger: 'item',
      formatter: (p: any) => `${p.seriesName}<br/>(${Number(p.value[0]).toFixed(2)}, ${Number(p.value[1]).toFixed(2)})`,
    },
    legend: { top: 0, type: 'scroll', textStyle: { fontSize: 11 } },
    xAxis: { type: 'value', name: 'x', nameLocation: 'middle', nameGap: 26, min: -3, max: 3, splitLine: { lineStyle: { type: 'dashed' } }, axisLabel: { fontSize: 11 } },
    yAxis: { type: 'value', name: 'y', nameLocation: 'middle', nameGap: 36, min: -3, max: 3, splitLine: { lineStyle: { type: 'dashed' } }, axisLabel: { fontSize: 11 } },
    series,
  }
})
</script>

<template>
  <div class="eigen-sim">
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
      <p class="hint">
        灰色虚线 = 单位圆；蓝色椭圆 = 单位圆所有向量经矩阵 A 作用后的轨迹。
        橙色/红色虚线 = 两个特征方向：落在该方向上的向量，被 A 作用后方向不变、只按特征值 λ 拉伸或压缩——
        这就是「$A v = \\lambda v$」的几何意义。
      </p>
    </div>
  </div>
</template>

<style scoped>
.eigen-sim { padding: 16px; }
.chart { height: 360px; }
.controls { margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border); display: flex; flex-direction: column; gap: 10px; }
.control-row { display: flex; align-items: center; gap: 12px; }
.control-label { width: 88px; font-size: 13px; color: var(--text-2); flex-shrink: 0; }
.slider { flex: 1; accent-color: var(--primary); cursor: pointer; }
.control-value { width: 56px; font-size: 13px; font-weight: 600; color: var(--primary); text-align: right; flex-shrink: 0; }
.hint { margin-top: 8px; font-size: 12px; color: var(--text-3); line-height: 1.7; }
</style>