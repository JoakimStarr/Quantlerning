<script setup lang="ts">
import { computed, ref } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C, withAlpha } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import katex from 'katex'
use([CanvasRenderer, BarChart, LineChart, GridComponent, TooltipComponent, LegendComponent])

// 分布浏览器：一个图切换多种分布，观察形状与期望/方差（教学示意，非真实数据）

const props = defineProps<{
  params?: Record<string, unknown>
}>()

type DistKey = 'bernoulli' | 'binomial' | 'poisson' | 'uniform' | 'normal'

const DISTS: { key: DistKey; label: string; kind: 'discrete' | 'continuous'; formula: string }[] = [
  { key: 'bernoulli', label: '伯努利', kind: 'discrete', formula: 'P(X=1)=p,\\ P(X=0)=1-p' },
  { key: 'binomial', label: '二项', kind: 'discrete', formula: 'P(X=k)=\\binom{n}{k}p^k(1-p)^{n-k}' },
  { key: 'poisson', label: '泊松', kind: 'discrete', formula: 'P(X=k)=\\frac{\\lambda^k e^{-\\lambda}}{k!}' },
  { key: 'uniform', label: '均匀', kind: 'continuous', formula: 'f(x)=\\frac{1}{b-a},\\ a\\le x\\le b' },
  { key: 'normal', label: '正态', kind: 'continuous', formula: 'f(x)=\\frac{1}{\\sigma\\sqrt{2\\pi}}\\exp\\left(-\\frac{(x-\\mu)^2}{2\\sigma^2}\\right)' },
]

const dist = ref<DistKey>(
  DISTS.some((d) => d.key === props.params?.dist) ? (props.params!.dist as DistKey) : 'binomial',
)

// 各分布参数（切换分布时各自保留）
const p = ref(0.5)
const n = ref(20)
const lambda = ref(4)
const uniCenter = ref(5)
const uniWidth = ref(6)
const mu = ref(0)
const sigma = ref(1)
const showNormal = ref(false) // 仅二项分布：叠加正态逼近

const current = computed(() => DISTS.find((d) => d.key === dist.value)!)

// ---------- log-gamma（Lanczos 近似），稳定计算组合数 ----------
function lgamma(x: number): number {
  const g = 7
  const c = [
    0.99999999999980993, 676.5203681218851, -1259.1392167224028,
    771.32342877765313, -176.61502916214059, 12.507343278686905,
    -0.13857109526572012, 9.9843695780195716e-6, 1.5056327351493116e-7,
  ]
  if (x < 0.5) return Math.log(Math.PI / Math.sin(Math.PI * x)) - lgamma(1 - x)
  x -= 1
  let a = c[0]
  const t = x + g + 0.5
  for (let i = 1; i < g + 2; i++) a += c[i] / (x + i)
  return 0.5 * Math.log(2 * Math.PI) + (x + 0.5) * Math.log(t) - t + Math.log(a)
}
function logComb(nn: number, k: number) {
  return lgamma(nn + 1) - lgamma(k + 1) - lgamma(nn - k + 1)
}

const stats = computed(() => {
  switch (dist.value) {
    case 'bernoulli':
      return { mean: p.value, variance: p.value * (1 - p.value) }
    case 'binomial':
      return { mean: n.value * p.value, variance: n.value * p.value * (1 - p.value) }
    case 'poisson':
      return { mean: lambda.value, variance: lambda.value }
    case 'uniform': {
      const w = uniWidth.value
      return { mean: uniCenter.value, variance: (w * w) / 12 }
    }
    case 'normal':
      return { mean: mu.value, variance: sigma.value * sigma.value }
  }
})

type DiscreteChart = { kind: 'discrete'; bars: [number, number][]; normalCurve: [number, number][]; xMax: number }
type ContinuousChart = { kind: 'continuous'; line: [number, number][]; xMin: number; xMax: number }
const chart = computed<DiscreteChart | ContinuousChart>(() => {
  if (current.value.kind === 'discrete') {
    let bars: [number, number][] = []
    let xMax = 1
    if (dist.value === 'bernoulli') {
      bars = [
        [0, Number((1 - p.value).toFixed(5))],
        [1, Number(p.value.toFixed(5))],
      ]
      xMax = 1
    } else if (dist.value === 'binomial') {
      for (let k = 0; k <= n.value; k++) {
        bars.push([
          k,
          Number(Math.exp(logComb(n.value, k) + k * Math.log(p.value) + (n.value - k) * Math.log(1 - p.value)).toFixed(5)),
        ])
      }
      xMax = n.value
    } else {
      // 泊松：右尾截断到 λ + 5σ 附近
      const K = Math.max(5, Math.ceil(lambda.value + 5 * Math.sqrt(lambda.value)))
      for (let k = 0; k <= K; k++) {
        bars.push([k, Number(Math.exp(k * Math.log(lambda.value) - lambda.value - lgamma(k + 1)).toFixed(5))])
      }
      xMax = K
    }
    // 二项分布的正态逼近曲线
    let normalCurve: [number, number][] = []
    if (dist.value === 'binomial' && showNormal.value) {
      const mean = n.value * p.value
      const sd = Math.sqrt(n.value * p.value * (1 - p.value))
      if (sd > 0) {
        const lo = Math.max(0, mean - 3.5 * sd)
        const hi = Math.min(n.value, mean + 3.5 * sd)
        for (let i = 0; i <= 100; i++) {
          const x = lo + ((hi - lo) * i) / 100
          const y = (1 / (sd * Math.sqrt(2 * Math.PI))) * Math.exp(-((x - mean) ** 2) / (2 * sd * sd))
          normalCurve.push([Number(x.toFixed(3)), Number(y.toFixed(5))])
        }
      }
    }
    return { kind: 'discrete', bars, normalCurve, xMax }
  }

  if (dist.value === 'uniform') {
    const a = uniCenter.value - uniWidth.value / 2
    const b = uniCenter.value + uniWidth.value / 2
    const density = 1 / (b - a)
    return {
      kind: 'continuous',
      line: [
        [a - 0.4, 0], [a, 0], [a, density], [b, density], [b, 0], [b + 0.4, 0],
      ],
      xMin: a - 0.5,
      xMax: b + 0.5,
    }
  }

  // 正态
  const xMin = mu.value - 4 * sigma.value
  const xMax = mu.value + 4 * sigma.value
  const line: [number, number][] = []
  for (let i = 0; i <= 200; i++) {
    const x = xMin + ((xMax - xMin) * i) / 200
    const y = (1 / (sigma.value * Math.sqrt(2 * Math.PI))) * Math.exp(-((x - mu.value) ** 2) / (2 * sigma.value * sigma.value))
    line.push([Number(x.toFixed(3)), Number(y.toFixed(6))])
  }
  return { kind: 'continuous', line, xMin, xMax }
})

// 分布记号 + PMF/PDF 公式（katex 渲染）
const distNotation = computed(() => {
  switch (dist.value) {
    case 'bernoulli':
      return `X \\sim \\text{Bernoulli}(${p.value})`
    case 'binomial':
      return `X \\sim \\text{Bin}(${n.value},\\ ${p.value})`
    case 'poisson':
      return `X \\sim \\text{Poisson}(${lambda.value})`
    case 'uniform':
      return `X \\sim U(${fmtNum(uniCenter.value - uniWidth.value / 2)},\\ ${fmtNum(uniCenter.value + uniWidth.value / 2)})`
    case 'normal':
      return `X \\sim N(${mu.value},\\ ${sigma.value}^2)`
  }
})
const notationHtml = computed(() => katex.renderToString(distNotation.value, { throwOnError: false, strict: false }))
const formulaHtml = computed(() => katex.renderToString(current.value.formula, { throwOnError: false, displayMode: true, strict: false }))

const option = computed(() => {
  const c = chart.value
  const isDiscrete = c.kind === 'discrete'
  const series: any[] = isDiscrete
    ? [
        {
          name: 'P(X=k)',
          type: 'bar',
          data: c.bars,
          barWidth: '60%',
          itemStyle: { color: withAlpha(C.value.primary, 0.55), borderRadius: [2, 2, 0, 0] },
        },
        ...(c.normalCurve.length
          ? [
              {
                name: '正态逼近',
                type: 'line',
                smooth: true,
                symbol: 'none',
                data: c.normalCurve,
                lineStyle: { width: 2.5, color: C.value.warning },
                itemStyle: { color: C.value.warning },
              },
            ]
          : []),
      ]
    : [
        {
          name: '密度 f(x)',
          type: 'line',
          smooth: true,
          symbol: 'none',
          data: c.line,
          lineStyle: { width: 2.5, color: C.value.primary },
          itemStyle: { color: C.value.primary },
          areaStyle: { color: withAlpha(C.value.primary, 0.12) },
        },
      ]

  return {
    animation: true,
    grid: { left: 55, right: 20, top: 36, bottom: 40 },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: isDiscrete ? 'shadow' : 'line' },
      formatter: (params: any) => {
        const arr = Array.isArray(params) ? params : [params]
        return arr
          .map((pa: any) => {
            // 数据项是 [x, y] 数组时 value 为数组，需取分量
            const isArr = Array.isArray(pa.value)
            const x = isArr ? pa.value[0] : pa.axisValue
            const y = isArr ? pa.value[1] : pa.value
            const xLabel = isDiscrete ? `k=${x}` : `x=${Number(x).toFixed(2)}`
            return `${pa.seriesName}｜${xLabel}: ${Number(y).toFixed(4)}`
          })
          .join('<br/>')
      },
    },
    legend: { top: 0, textStyle: { fontSize: 12 } },
    xAxis: {
      type: 'value',
      name: isDiscrete ? 'k（取值）' : 'x',
      nameLocation: 'middle',
      nameGap: 28,
      min: isDiscrete ? 0 : c.xMin,
      max: c.xMax,
      interval: isDiscrete ? Math.max(1, Math.floor(c.xMax / 10)) : undefined,
      axisLabel: { fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      name: isDiscrete ? 'P(X=k)' : '密度',
      nameLocation: 'middle',
      nameGap: 40,
      axisLabel: { fontSize: 11 },
    },
    series,
  }
})

const fmtNum = (v: number) => Number(v.toFixed(3))
const fmtPct = (v: number) => `${(v * 100).toFixed(0)}%`
const fmt2 = (v: number) => `${Number(v.toFixed(2))}`
</script>

<template>
  <div class="dist-explorer">
    <!-- 分布选择 -->
    <div class="chips">
      <button
        v-for="d in DISTS"
        :key="d.key"
        class="chip"
        :class="{ active: dist === d.key }"
        @click="dist = d.key"
      >
        {{ d.label }}
      </button>
    </div>

    <!-- 记号 + 公式 -->
    <div class="formula">
      <div class="notation" v-html="notationHtml"></div>
      <div class="pmf-pdf" v-html="formulaHtml"></div>
    </div>

    <ThemedChart class="chart" :option="option" autoresize />

    <!-- 参数滑块（随分布变化） -->
    <div class="controls">
      <template v-if="dist === 'bernoulli'">
        <div class="control-row">
          <span class="control-label">p</span>
          <input v-model.number="p" type="range" min="0.05" max="0.95" step="0.01" class="slider" />
          <span class="control-value">{{ fmtPct(p) }}</span>
        </div>
      </template>
      <template v-else-if="dist === 'binomial'">
        <div class="control-row">
          <span class="control-label">试验次数 n</span>
          <input v-model.number="n" type="range" min="1" max="50" step="1" class="slider" />
          <span class="control-value">{{ n }}</span>
        </div>
        <div class="control-row">
          <span class="control-label">成功概率 p</span>
          <input v-model.number="p" type="range" min="0.05" max="0.95" step="0.01" class="slider" />
          <span class="control-value">{{ fmtPct(p) }}</span>
        </div>
      </template>
      <template v-else-if="dist === 'poisson'">
        <div class="control-row">
          <span class="control-label">λ（均值）</span>
          <input v-model.number="lambda" type="range" min="0.1" max="20" step="0.1" class="slider" />
          <span class="control-value">{{ fmt2(lambda) }}</span>
        </div>
      </template>
      <template v-else-if="dist === 'uniform'">
        <div class="control-row">
          <span class="control-label">中心 m</span>
          <input v-model.number="uniCenter" type="range" min="0" max="10" step="0.1" class="slider" />
          <span class="control-value">{{ fmt2(uniCenter) }}</span>
        </div>
        <div class="control-row">
          <span class="control-label">宽度 w</span>
          <input v-model.number="uniWidth" type="range" min="0.5" max="10" step="0.1" class="slider" />
          <span class="control-value">{{ fmt2(uniWidth) }}</span>
        </div>
      </template>
      <template v-else>
        <div class="control-row">
          <span class="control-label">μ</span>
          <input v-model.number="mu" type="range" min="-8" max="8" step="0.1" class="slider" />
          <span class="control-value">{{ fmt2(mu) }}</span>
        </div>
        <div class="control-row">
          <span class="control-label">σ</span>
          <input v-model.number="sigma" type="range" min="0.1" max="5" step="0.1" class="slider" />
          <span class="control-value">{{ fmt2(sigma) }}</span>
        </div>
      </template>
    </div>

    <div class="bottom-row">
      <label v-if="dist === 'binomial'" class="toggle">
        <input v-model="showNormal" type="checkbox" class="checkbox" />
        正态逼近
      </label>
      <span v-else />
      <div class="stats">
        <span class="stat-chip">期望 = <strong>{{ fmtNum(stats.mean) }}</strong></span>
        <span class="stat-chip">方差 = <strong>{{ fmtNum(stats.variance) }}</strong></span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dist-explorer { padding: 16px; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; justify-content: center; margin-bottom: 8px; }
.chip {
  border: 1px solid var(--border);
  background: var(--bg-card);
  color: var(--text-2);
  font-size: 12.5px;
  padding: 3px 12px;
  border-radius: 999px;
  cursor: pointer;
}
.chip:hover { border-color: var(--primary); color: var(--primary); }
.chip.active { background: var(--primary); border-color: var(--primary); color: #fff; }
.formula { text-align: center; margin-bottom: 4px; }
.notation { font-size: 14px; color: var(--text-1); }
.pmf-pdf { font-size: 12.5px; color: var(--text-2); }
.chart { height: 300px; }
.controls { margin-top: 10px; padding-top: 10px; border-top: 1px solid var(--border); display: flex; flex-direction: column; gap: 8px; }
.control-row { display: flex; align-items: center; gap: 12px; }
.control-label { width: 92px; font-size: 12.5px; color: var(--text-2); flex-shrink: 0; }
.slider { flex: 1; accent-color: var(--primary); cursor: pointer; }
.control-value { width: 52px; font-size: 12.5px; font-weight: 600; color: var(--primary); text-align: right; flex-shrink: 0; }
.bottom-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-top: 8px; }
.toggle { display: flex; align-items: center; gap: 6px; font-size: 13px; color: var(--text-2); cursor: pointer; }
.checkbox { accent-color: var(--primary); cursor: pointer; }
.stats { display: flex; gap: 8px; }
.stat-chip {
  font-size: 12.5px; color: var(--text-3);
  padding: 4px 10px; border-radius: 999px; background: var(--bg-hover);
}
.stat-chip strong { color: var(--primary); }
</style>
