<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C, withAlpha } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, TitleComponent } from 'echarts/components'
import { useStockDaily } from '@/composables/useStockDaily'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, TitleComponent])

// 几何布朗运动 vs 真实茅台 2024 净值
// 教学点：随机游走的核心假设是「独立增量」——未来波动不可预测，但统计性质（漂移+波动）可度量
const props = defineProps<{
  params?: Record<string, unknown>
}>()

const code = computed(() => (typeof props.params?.code === 'string' ? props.params.code : 'sh600519'))
const { data, nav } = useStockDaily(code, '2024-01-01', '2024-12-31')

const steps = ref(242)
const drift = ref(0) // 年化漂移 %
const sigma = ref(27.55) // 年化波动 %
const seedCount = ref(3)

// 用真实茅台收益估计 σ（官方口径年化波动 27.55%）
const realVol = computed(() => {
  if (!data.value || data.value.length < 2) return null
  const rets = data.value.map((d) => d.pct_chg).slice(1)
  const m = rets.reduce((s, v) => s + v, 0) / rets.length
  const sd = Math.sqrt(rets.reduce((s, v) => s + (v - m) ** 2, 0) / (rets.length - 1))
  return sd * Math.sqrt(252)
})

function gauss(): number {
  let u = 0
  let v = 0
  while (u === 0) u = Math.random()
  while (v === 0) v = Math.random()
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v)
}

function gbmPaths(n: number, steps: number, mu: number, sigma: number): number[][] {
  const dt = 1 / 252
  const paths: number[][] = []
  for (let s = 0; s < n; s++) {
    const p: number[] = [100]
    for (let i = 1; i < steps; i++) {
      const z = gauss()
      p.push(p[i - 1] * Math.exp((mu / 100 - (sigma / 100) ** 2 / 2) * dt + (sigma / 100) * Math.sqrt(dt) * z))
    }
    paths.push(p)
  }
  return paths
}

const simulated = ref<number[][]>([])
const running = ref(false)
let timer: ReturnType<typeof setInterval> | null = null

function regenerate() {
  simulated.value = gbmPaths(seedCount.value, steps.value, drift.value, sigma.value)
}

function animate() {
  if (running.value) {
    stop()
    return
  }
  running.value = true
  timer = setInterval(() => {
    simulated.value = gbmPaths(seedCount.value, steps.value, drift.value, sigma.value)
  }, 900)
}

function stop() {
  running.value = false
  if (timer) {
    clearInterval(timer)
    timer = null
  }
}

onMounted(regenerate)
onUnmounted(stop)

const option = computed(() => {
  const x = Array.from({ length: steps.value }, (_, i) => i)
  const series: any[] = simulated.value.map((p, i) => ({
    name: `模拟路径 ${i + 1}`,
    type: 'line',
    data: p.map((v) => +v.toFixed(1)),
    smooth: false,
    symbol: 'none',
    lineStyle: { width: 1.2, opacity: 0.8 },
  }))
  // 真实茅台净值（归一化到 100 起点）
  if (nav.value && nav.value.length >= steps.value) {
    const base = nav.value[0]
    series.push({
      name: '真实茅台 2024',
      type: 'line',
      data: nav.value.slice(0, steps.value).map((v) => +((v / base) * 100).toFixed(1)),
      smooth: true,
      symbol: 'none',
      lineStyle: { width: 2.2, color: C.value.warning },
    })
  }
  return {
    animation: false,
    grid: { left: 52, right: 24, top: 36, bottom: 40 },
    title: [
      {
        text: '模拟 GBM 路径 vs 真实茅台（起点 100）',
        left: 52,
        top: 8,
        textStyle: { fontSize: 12, fontWeight: 600, color: C.value.text },
      },
    ],
    tooltip: { trigger: 'axis' },
    legend: { top: 0, textStyle: { fontSize: 11 } },
    dataZoom: [
      {
        type: 'inside',
        xAxisIndex: [0],
        start: 0,
        end: 100,
        zoomOnMouseWheel: true,
        moveOnMouseMove: true,
      },
      {
        type: 'slider',
        xAxisIndex: [0],
        start: 0,
        end: 100,
        bottom: 2,
        height: 16,
        borderColor: C.value.grid,
        backgroundColor: 'transparent',
        fillerColor: withAlpha(C.value.primary, 0.15),
        handleStyle: { color: C.value.primary },
        textStyle: { color: C.value.text, fontSize: 10 },
        dataBackground: {
          lineStyle: { color: C.value.slate, opacity: 0.5 },
          areaStyle: { color: withAlpha(C.value.slate, 0.1) },
        },
        selectedDataBackground: {
          lineStyle: { color: C.value.primary, opacity: 0.6 },
          areaStyle: { color: withAlpha(C.value.primary, 0.12) },
        },
      },
    ],
    xAxis: { type: 'category', data: x, name: '交易日', nameLocation: 'middle', nameGap: 28, axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', name: '净值（起点=100）', nameLocation: 'middle', nameGap: 44, scale: true, axisLabel: { fontSize: 10 } },
    series,
  }
})
</script>

<template>
  <div class="rw">
    <div class="controls">
      <label>步数 <input type="range" v-model.number="steps" min="50" max="300" @change="regenerate" /> {{ steps }}</label>
      <label>年化漂移 μ <input type="range" v-model.number="drift" min="-20" max="20" step="0.5" @change="regenerate" /> {{ drift }}%</label>
      <label>年化波动 σ <input type="range" v-model.number="sigma" min="5" max="60" step="0.5" @change="regenerate" /> {{ sigma }}%</label>
      <label>路径数 <input type="range" v-model.number="seedCount" min="1" max="8" @change="regenerate" /> {{ seedCount }}</label>
      <button class="btn" @click="animate">{{ running ? '停止' : '动画' }}</button>
      <button class="btn" @click="regenerate">重新生成</button>
    </div>
    <p v-if="realVol" class="note">真实茅台 2024 年化波动 = {{ realVol.toFixed(2) }}%（quantlab 库，官方口径）。默认 σ 即取此值——模拟路径与真实净值对比，看「随机游走」能否重现真实走势的统计特征。</p>
    <ThemedChart class="chart" :option="option" autoresize />
  </div>
</template>

<style scoped>
.rw { padding: 16px; }
.chart { height: 320px; }
.controls { display: flex; gap: 14px; flex-wrap: wrap; align-items: center; margin-bottom: 10px; font-size: 12.5px; color: var(--text-2); }
.controls label { display: flex; align-items: center; gap: 6px; }
.controls input[type='range'] { width: 90px; }
.btn {
  padding: 5px 14px; border: 1px solid var(--border-strong); border-radius: 999px;
  background: var(--bg-card); color: var(--text-1); font-size: 12.5px; cursor: pointer; transition: all 0.15s;
}
.btn:hover { border-color: var(--primary); color: var(--primary); }
.note { font-size: 12.5px; color: var(--text-3); margin-bottom: 10px; line-height: 1.6; }
</style>