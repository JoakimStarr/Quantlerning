<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { fetchBacktests } from '@/api'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent])

// QuantLab 多因子回测真实结果：净值曲线对比 + 绩效表
// 教学点：因子策略的最终验证 = 回测净值的形态与风险调整后收益
const loading = ref(true)
const error = ref<string | null>(null)
const items = ref<Awaited<ReturnType<typeof fetchBacktests>> | null>(null)

async function load() {
  loading.value = true
  error.value = null
  try {
    const list = await fetchBacktests(20)
    items.value = list.filter((x) => x.nav)
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

onMounted(load)

const selected = ref<number[]>([])

const sel = computed(() => items.value?.filter((x) => selected.value.includes(x.id)) ?? [])

function toggle(id: number) {
  if (selected.value.includes(id)) selected.value = selected.value.filter((x) => x !== id)
  else selected.value = [...selected.value, id]
}

function toggleAll() {
  selected.value = sel.value.length === selected.value.length ? [] : (items.value?.map((x) => x.id) ?? [])
}

const allSelected = computed(() => items.value?.length === selected.value.length)

const option = computed(() => {
  if (!sel.value.length) return {}
  // 选取长度最长的日期轴
  const dates = sel.value.map((x) => x.nav!.dates).sort((a, b) => b.length - a.length)[0]
  const series = sel.value.flatMap((x) => {
    const nav = x.nav!
    return [
      {
        name: `组合 #${x.id}（${x.combination_method}, top${x.topk}）`,
        type: 'line' as const,
        data: nav.portfolio,
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 1.6 },
      },
      {
        name: `基准 ${x.benchmark} #${x.id}`,
        type: 'line' as const,
        data: nav.benchmark,
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 1, type: 'dashed' as const, color: '#94a3b8' },
      },
    ]
  })
  return {
    animation: false,
    grid: { left: 52, right: 24, top: 36, bottom: 44 },
    tooltip: { trigger: 'axis' },
    legend: { top: 0, type: 'scroll', textStyle: { fontSize: 10 } },
    xAxis: { type: 'category', data: dates, axisLabel: { fontSize: 9, hideOverlap: true } },
    yAxis: { type: 'value', name: '净值（起点=1）', nameLocation: 'middle', nameGap: 44, scale: true, axisLabel: { fontSize: 10 } },
    series,
  }
})

const table = computed(() =>
  sel.value.map((x) => ({
    id: x.id,
    method: x.combination_method,
    topk: x.topk,
    freq: x.rebalance_freq,
    ret: (x.annual_return * 100).toFixed(1),
    vol: (x.annual_volatility * 100).toFixed(1),
    sharpe: x.sharpe.toFixed(2),
    mdd: (x.max_drawdown * 100).toFixed(1),
    excess: (x.excess_return * 100).toFixed(1),
    nav: x.nav!,
  })),
)
</script>

<template>
  <div class="bt-dash">
    <div v-if="loading" class="status">数据加载中…</div>
    <div v-else-if="error" class="status">数据不可用</div>
    <template v-else-if="items && items.length">
      <div class="chips">
        <button class="chip" :class="{ active: allSelected }" @click="toggleAll">全选</button>
        <button
          v-for="x in items"
          :key="x.id"
          class="chip"
          :class="{ active: selected.includes(x.id) }"
          @click="toggle(x.id)"
        >#{{ x.id }} {{ x.combination_method }} top{{ x.topk }}</button>
      </div>
      <VChart class="chart" :option="option" autoresize />
      <div class="table-wrap">
        <table class="tbl">
          <thead>
            <tr>
              <th>回测</th>
              <th>组合方法</th>
              <th>TopK</th>
              <th>调仓</th>
              <th>年化</th>
              <th>年化波动</th>
              <th>Sharpe</th>
              <th>最大回撤</th>
              <th>超额</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="t in table" :key="t.id">
              <td>#{{ t.id }}</td>
              <td>{{ t.method }}</td>
              <td>{{ t.topk }}</td>
              <td>{{ t.freq }}</td>
              <td>{{ t.ret }}%</td>
              <td>{{ t.vol }}%</td>
              <td :class="{ pos: +t.sharpe > 0 }">{{ t.sharpe }}</td>
              <td>{{ t.mdd }}%</td>
              <td :class="{ pos: +t.excess > 0 }">{{ t.excess }}%</td>
            </tr>
          </tbody>
        </table>
        <p class="note">真实数据：QuantLab factor 回测引擎输出（benchmark 为沪深 300 虚线）。回测口径与第二章一致：不含首日、复权收益。</p>
      </div>
    </template>
  </div>
</template>

<style scoped>
.bt-dash { padding: 16px; }
.status { height: 300px; display: flex; align-items: center; justify-content: center; color: var(--text-3); font-size: 14px; }
.chart { height: 380px; }
.chips { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 12px; }
.chip {
  font-size: 11.5px; padding: 3px 10px; border-radius: 999px; border: 1px solid var(--border-strong);
  background: var(--bg-card); color: var(--text-2); cursor: pointer; transition: all 0.12s;
}
.chip:hover { border-color: var(--primary); color: var(--primary); }
.chip.active { background: var(--primary-soft); border-color: var(--primary); color: var(--primary); }
.table-wrap { margin-top: 14px; overflow-x: auto; }
.tbl { width: 100%; border-collapse: collapse; font-size: 12px; }
.tbl th, .tbl td { padding: 6px 8px; border: 1px solid var(--border); text-align: right; white-space: nowrap; }
.tbl th:first-child, .tbl td:first-child { text-align: left; }
.tbl th { background: var(--bg-hover); color: var(--text-2); font-weight: 600; }
.pos { color: var(--success); font-weight: 600; }
.note { font-size: 12px; color: var(--text-3); margin-top: 10px; }
</style>
