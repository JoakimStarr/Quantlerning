<script setup lang="ts">
import { computed, ref } from 'vue'
import ThemedChart from '@/components/common/ThemedChart.vue'
import { C } from '@/utils/chartTheme'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { useStockDaily } from '@/composables/useStockDaily'
import { buildFeatures, standardize, trainLogistic, logitPredict, accuracy } from '@/utils/ml'

use([CanvasRenderer, BarChart, LineChart, GridComponent, TooltipComponent, LegendComponent])

// 模型选择演示：真实茅台特征 → 逻辑回归预测次日涨跌
// 教学点：标准化后权重 |w| 即特征重要度；XGBoost 等树的特征重要度同理（gain / split）
const props = defineProps<{
  params?: Record<string, unknown>
}>()

const code = computed(() => (typeof props.params?.code === 'string' ? props.params.code : 'sh600519'))
const { data, loading, error } = useStockDaily(code)

const l2 = ref(0.01) // 正则强度
const testRatio = ref(0.3) // 测试集比例

const feats = computed(() => (data.value ? buildFeatures(data.value) : null))

// 时间顺序切分：前段训练，后段测试（防前视）
const trainTest = computed(() => {
  if (!feats.value || feats.value.X.length < 60) return null
  const { X, y, names, dates } = feats.value
  const cut = Math.floor(X.length * (1 - testRatio.value))
  const trainX = X.slice(0, cut)
  const trainY = y.slice(0, cut)
  const testX = X.slice(cut)
  const testY = y.slice(cut)
  const testDates = dates.slice(cut)
  return { trainX, trainY, testX, testY, names, testDates }
})

const result = computed(() => {
  const tt = trainTest.value
  if (!tt) return null
  const { trainX, trainY, testX, testY } = tt
  const { Xs, means, stds } = standardize(trainX)
  const model = trainLogistic(Xs, trainY, { lr: 0.3, epochs: 1500, l2: l2.value })
  const trainPred = logitPredict(Xs, model.weights, model.bias)
  // 用训练集的 means/stds 标准化测试集
  const testXsScaled = testX.map((r) => r.map((v, j) => (v - means[j]) / stds[j]))
  const testPred = logitPredict(testXsScaled, model.weights, model.bias)
  const trainAcc = accuracy(trainPred, trainY)
  const testAcc = accuracy(testPred, testY)
  return {
    model,
    names: tt.names,
    trainAcc,
    testAcc,
    testProbs: testPred,
    testY,
    testDates: tt.testDates,
    means,
    stds,
  }
})

// 特征重要度：标准化权重的绝对值（排序）
const importance = computed(() => {
  if (!result.value) return []
  const r = result.value
  return r.names
    .map((n, i) => ({ name: n, w: r.model.weights[i], abs: Math.abs(r.model.weights[i]) }))
    .sort((a, b) => b.abs - a.abs)
})

const importOption = computed(() => ({
  animation: false,
  grid: { left: 90, right: 40, top: 24, bottom: 30 },
  tooltip: { trigger: 'item', formatter: (p: any) => `${p.name}<br/>标准化权重 w=${p.value}` },
  xAxis: { type: 'value', name: '|w|（标准化权重）', nameLocation: 'middle', nameGap: 26, axisLabel: { fontSize: 10 } },
  yAxis: { type: 'category', data: importance.value.map((i) => i.name).reverse(), axisLabel: { fontSize: 11 } },
  series: [
    {
      type: 'bar',
      data: importance.value.map((i) => +i.abs.toFixed(3)).reverse(),
      itemStyle: {
        color: (p: any) => (importance.value[importance.value.length - 1 - p.dataIndex].w > 0 ? C.value.primary : C.value.danger),
        opacity: 0.8,
      },
      label: { show: true, position: 'right', fontSize: 10, formatter: (p: any) => (importance.value[importance.value.length - 1 - p.dataIndex].w > 0 ? `+${p.value}` : p.value) },
    },
  ],
}))

const lossOption = computed(() => {
  const r = result.value
  if (!r) return {}
  return {
    animation: false,
    grid: { left: 56, right: 24, top: 24, bottom: 40 },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: r.model.lossHistory.map((_, i) => i * 10), axisLabel: { fontSize: 9 } },
    yAxis: { type: 'value', name: '交叉熵损失', nameLocation: 'middle', nameGap: 40, axisLabel: { fontSize: 10 } },
    series: [
      { name: '训练损失', type: 'line', data: r.model.lossHistory.map((v) => +v.toFixed(3)), symbol: 'none', lineStyle: { color: C.value.primary, width: 2 } },
    ],
  }
})
</script>

<template>
  <div class="feat-imp">
    <div v-if="loading" class="status">数据加载中…</div>
    <div v-else-if="error" class="status">数据不可用</div>
    <template v-else-if="result && importance.length">
      <div class="controls">
        <label>L2 正则 <input type="range" v-model.number="l2" min="0" max="0.5" step="0.01" /> {{ l2.toFixed(2) }}</label>
        <label>测试集占比 <input type="range" v-model.number="testRatio" min="0.2" max="0.5" step="0.05" /> {{ (testRatio * 100).toFixed(0) }}%</label>
      </div>
      <div class="stats">
        <span class="chip">训练准确率 <strong>{{ (result.trainAcc * 100).toFixed(1) }}%</strong></span>
        <span class="chip">测试准确率 <strong>{{ (result.testAcc * 100).toFixed(1) }}%</strong></span>
        <span class="chip">迭代 <strong>{{ result.model.iterations }}</strong> 次</span>
        <span class="chip note">时间顺序切分（防前视）</span>
      </div>
      <p class="sub">特征重要度（逻辑回归标准化权重 |w|，红色=负向，蓝色=正向）</p>
      <ThemedChart class="chart" :option="importOption" autoresize />
      <p class="sub">训练损失随梯度下降收敛（交叉熵）</p>
      <ThemedChart class="chart small" :option="lossOption" autoresize />
      <p class="note">真实锚点：贵州茅台 SH600519 2024，8 个真实技术特征（动量/波动/RSI/MACD/均线偏离/换手）预测次日涨跌。教学点：特征重要度帮助挑选/排除特征；正负号反映方向（如 RSI 高位→次日更可能回调）。示意性模型，不代表可实盘。</p>
    </template>
  </div>
</template>

<style scoped>
.feat-imp { padding: 16px; }
.status { height: 300px; display: flex; align-items: center; justify-content: center; color: var(--text-3); font-size: 14px; }
.controls { display: flex; gap: 16px; flex-wrap: wrap; align-items: center; margin-bottom: 10px; font-size: 12.5px; color: var(--text-2); }
.controls label { display: flex; align-items: center; gap: 6px; }
.controls input[type='range'] { width: 110px; }
.chart { height: 260px; margin-bottom: 6px; }
.small { height: 160px; }
.stats { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
.chip {
  font-size: 12.5px; color: var(--text-3);
  padding: 4px 10px; border-radius: 999px; background: var(--bg-hover);
}
.chip strong { color: var(--primary); }
.chip.note { background: var(--primary-soft); color: var(--text-2); }
.sub { font-size: 12px; color: var(--text-3); margin: 6px 0 2px; }
.note { font-size: 12.5px; color: var(--text-3); margin-top: 10px; line-height: 1.6; }
</style>
