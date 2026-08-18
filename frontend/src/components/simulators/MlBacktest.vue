<script setup lang="ts">
import { computed, ref } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C, withAlpha } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, MarkLineComponent, DataZoomComponent, TitleComponent } from 'echarts/components'
import { useStockDaily } from '@/composables/useStockDaily'
import { buildFeatures, standardize, trainLogistic, logitPredict, probToPos, mlxStats, navFromReturns } from '@/utils/ml'
import { maCrossSignal, shiftPosition } from '@/utils/strategies'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent, DataZoomComponent, TitleComponent])

// 阶段产出：ML 策略 vs 传统策略（茅台真实数据，walk-forward）
// ML：前 70% 训练逻辑回归 → 预测后 30% 涨跌概率 → 概率仓位
// 传统：双均线交叉（20/60）
const props = defineProps<{
  params?: Record<string, unknown>
}>()

const code = computed(() => (typeof props.params?.code === 'string' ? props.params.code : 'sh600519'))
const { data, loading, error } = useStockDaily(code)

const trainRatio = ref(0.7) // 训练段占比
const threshold = ref(0.5) // 概率阈值
const mode = ref<'binary' | 'scaled'>('binary') // 仓位模式

const rets = computed<number[]>(() => (data.value ? data.value.map((d) => d.pct_chg / 100) : []))
const dates = computed<string[]>(() => (data.value ? data.value.map((d) => d.date) : []))
const closes = computed<number[]>(() => (data.value ? data.value.map((d) => d.close) : []))

// 回测期：训练段预测信号次日生效，测试段逐步预测（walk-forward 简化：单次切分）
const result = computed(() => {
  if (rets.value.length < 120 || closes.value.length < 120) return null
  const ret = rets.value
  const close = closes.value
  const n = ret.length
  const cut = Math.floor(n * trainRatio.value)

  // ---- 特征与行情的日期对齐 ----
  // buildFeatures 剔除预热期（约 26 行）：特征行 fi 对应数据行 (offset + fi)，
  // 不能直接用数据空间下标 cut 去切特征空间，否则长度错位、ML 净值产生 NaN
  const feats = buildFeatures(data.value!)
  const offset = dates.value.indexOf(feats.dates[0])
  if (offset < 0) return null
  const cutF = cut - offset // 切分点换算到特征空间
  if (cutF < 40 || feats.X.length - cutF < 10) return null

  const trainX = feats.X.slice(0, cutF)
  const trainY = feats.y.slice(0, cutF)
  const { Xs, means, stds } = standardize(trainX)
  const model = trainLogistic(Xs, trainY, { lr: 0.3, epochs: 1200, l2: 0.01 })
  const testX = feats.X.slice(cutF)
  const testXs = testX.map((r) => r.map((v, j) => (v - means[j]) / stds[j]))
  const probs = logitPredict(testXs, model.weights, model.bias)
  const testPos = probToPos(probs, mode.value, threshold.value)

  // 映射回行情时间轴：特征在数据行 t 生成（只用 t 及之前信息）→ 预测 t+1 收益 → 仓位在 t+1 生效
  const mlPos: number[] = new Array(n).fill(0)
  for (let fi = 0; fi < testPos.length; fi++) {
    const t = offset + cutF + fi
    if (t + 1 < n) mlPos[t + 1] = testPos[fi]
  }

  // 传统双均线（20/60）——整段
  const maSig = maCrossSignal(close, 20, 60)
  const maPos = shiftPosition(maSig.map((v) => (v === null ? 0 : v)))

  // 只看测试段的绩效（从数据下标 cut 起，测试段与行情严格对齐）
  const testRet = ret.slice(cut)
  const testDates = dates.value.slice(cut)
  const mlPosTest = mlPos.slice(cut)
  const maPosTest = maPos.slice(cut)

  const mlNav = navFromReturns(testRet, mlPosTest)
  const maNav = navFromReturns(testRet, maPosTest)
  const bhNav = navFromReturns(testRet, testRet.map(() => 1))

  const mlS = mlxStats(testRet, mlPosTest)
  const maS = mlxStats(testRet, maPosTest)
  const bhS = mlxStats(testRet, testRet.map(() => 1))

  // 概率序列对齐测试窗口（首日无预测，置 null）
  const probSeries: (number | null)[] = [null, ...probs.map((p) => +p.toFixed(3))]

  return {
    cut,
    testDates,
    testRet,
    mlNav,
    maNav,
    bhNav,
    mlS,
    maS,
    bhS,
    model,
    probs: probSeries,
    testPos: mlPosTest,
    nTest: testRet.length,
  }
})

const navOption = computed(() => {
  if (!result.value) return {}
  const r = result.value
  return {
    animation: false,
    grid: { left: 56, right: 24, top: 36, bottom: 44 },
    title: [
      {
        text: '测试段净值对比（起点 100）',
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
    xAxis: { type: 'category', data: r.testDates.map((d) => d.slice(5)), axisLabel: { fontSize: 9, hideOverlap: true } },
    yAxis: { type: 'value', name: '净值', nameLocation: 'middle', nameGap: 40, scale: true, axisLabel: { fontSize: 10 } },
    series: [
      { name: 'ML 逻辑回归', type: 'line', data: r.mlNav, symbol: 'none', lineStyle: { color: C.value.primary, width: 2 } },
      { name: '传统双均线', type: 'line', data: r.maNav, symbol: 'none', lineStyle: { color: C.value.warning, width: 2 } },
      { name: '买入持有', type: 'line', data: r.bhNav, symbol: 'none', lineStyle: { color: C.value.slateStrong, width: 1.5, type: 'dashed' } },
    ],
  }
})

const posOption = computed(() => {
  if (!result.value) return {}
  const r = result.value
  return {
    animation: false,
    grid: { left: 56, right: 24, top: 36, bottom: 44 },
    title: [
      {
        text: 'ML 概率预测与仓位',
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
    xAxis: { type: 'category', data: r.testDates.map((d) => d.slice(5)), axisLabel: { fontSize: 9, hideOverlap: true } },
    yAxis: { type: 'value', name: '仓位', nameLocation: 'middle', nameGap: 36, min: 0, max: 1, axisLabel: { fontSize: 10 } },
    series: [
      { name: 'ML 仓位', type: 'line', data: r.testPos.map((p) => +p.toFixed(2)), symbol: 'none', lineStyle: { color: C.value.success, width: 1.5 } },
      { name: '概率预测', type: 'line', data: r.probs.map((p) => (p == null ? null : +p)), symbol: 'none', lineStyle: { color: C.value.slate, width: 1, type: 'dotted' }, connectNulls: false },
      {
        name: `阈值 ${threshold.value}`,
        type: 'line',
        data: r.probs.map(() => threshold.value),
        symbol: 'none',
        lineStyle: { color: C.value.danger, width: 1, type: 'dashed' },
        markLine: { silent: true, symbol: 'none', data: [{ yAxis: threshold.value, lineStyle: { color: C.value.danger, type: 'dashed' }, label: { formatter: '阈值', position: 'insideEndTop' } }] },
      },
    ],
  }
})

const fmt = (v: number, suffix = '%') => `${(v * 100).toFixed(2)}${suffix}`
</script>

<template>
  <div class="ml-backtest">
    <div v-if="loading" class="status">数据加载中…</div>
    <div v-else-if="error" class="status">数据不可用</div>
    <template v-else-if="result">
      <div class="controls">
        <label>训练段占比 <input type="range" v-model.number="trainRatio" min="0.5" max="0.9" step="0.05" /> {{ (trainRatio * 100).toFixed(0) }}%</label>
        <label>概率阈值 <input type="range" v-model.number="threshold" min="0.45" max="0.65" step="0.01" /> {{ threshold.toFixed(2) }}</label>
        <label>仓位模式
          <select v-model="mode">
            <option value="binary">二值</option>
            <option value="scaled">概率缩放</option>
          </select>
        </label>
      </div>
      <p class="sub">测试段净值：ML（逻辑回归） vs 传统双均线 vs 买入持有（茅台真实数据，{{ result.nTest }} 个交易日）</p>
      <ThemedChart class="chart" :option="navOption" autoresize />
      <p class="sub">ML 概率预测与仓位（虚线=阈值）</p>
      <ThemedChart class="chart small" :option="posOption" autoresize />
      <div class="table-wrap">
        <table class="perf">
          <thead>
            <tr><th>指标</th><th>ML 逻辑回归</th><th>传统双均线</th><th>买入持有</th></tr>
          </thead>
          <tbody>
            <tr><td>累计收益</td><td>{{ fmt(result.mlS.cum) }}</td><td>{{ fmt(result.maS.cum) }}</td><td>{{ fmt(result.bhS.cum) }}</td></tr>
            <tr><td>年化收益</td><td>{{ fmt(result.mlS.ann) }}</td><td>{{ fmt(result.maS.ann) }}</td><td>{{ fmt(result.bhS.ann) }}</td></tr>
            <tr><td>年化波动</td><td>{{ fmt(result.mlS.vol) }}</td><td>{{ fmt(result.maS.vol) }}</td><td>{{ fmt(result.bhS.vol) }}</td></tr>
            <tr><td>夏普 (rf=2%)</td><td>{{ result.mlS.sharpe.toFixed(2) }}</td><td>{{ result.maS.sharpe.toFixed(2) }}</td><td>{{ result.bhS.sharpe.toFixed(2) }}</td></tr>
            <tr><td>最大回撤</td><td>{{ fmt(result.mlS.mdd) }}</td><td>{{ fmt(result.maS.mdd) }}</td><td>{{ fmt(result.bhS.mdd) }}</td></tr>
            <tr><td>平均持仓</td><td>{{ (result.mlS.posMean * 100).toFixed(0) }}%</td><td>{{ (result.maS.posMean * 100).toFixed(0) }}%</td><td>100%</td></tr>
          </tbody>
        </table>
      </div>
      <p class="note">真实锚点：贵州茅台 SH600519 2024。方法：前 {{ (trainRatio * 100).toFixed(0) }}% 训练逻辑回归（8 个技术特征，L2=0.01），后 {{ (100 - trainRatio * 100).toFixed(0) }}% 测试，信号次日生效。教学点：ML 模型在单只股票上未必跑赢简单均线——「模型有用 ≠ 策略赚钱」，这正是第五章要反复强调的。</p>
    </template>
  </div>
</template>

<style scoped>
.ml-backtest { padding: 16px; }
.status { height: 300px; display: flex; align-items: center; justify-content: center; color: var(--text-3); font-size: 14px; }
.controls { display: flex; gap: 16px; flex-wrap: wrap; align-items: center; margin-bottom: 10px; font-size: 12.5px; color: var(--text-2); }
.controls label { display: flex; align-items: center; gap: 6px; }
.controls input[type='range'] { width: 110px; }
.controls select { padding: 3px 6px; border: 1px solid var(--border); border-radius: 6px; background: var(--bg-card); color: var(--text-2); font-size: 12px; }
.chart { height: 260px; margin-bottom: 6px; }
.small { height: 180px; }
.sub { font-size: 12px; color: var(--text-3); margin: 6px 0 2px; }
.table-wrap { margin: 10px 0; overflow-x: auto; }
.perf { width: 100%; border-collapse: collapse; font-size: 12.5px; }
.perf th, .perf td { border: 1px solid var(--border); padding: 5px 10px; text-align: right; }
.perf th { background: var(--bg-hover); color: var(--text-2); font-weight: 600; }
.perf td:first-child { text-align: left; color: var(--text-2); }
.note { font-size: 12.5px; color: var(--text-3); margin-top: 10px; line-height: 1.6; }
</style>
