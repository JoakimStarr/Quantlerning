<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { fetchFactorSummary, fetchFactors } from '@/api'
import AppSpinner from '@/components/common/AppSpinner.vue'
import AppError from '@/components/common/AppError.vue'

// 因子库：展示 QuantLab factor 表的真实数据
interface Factor {
  name: string
  expression: string
  category: string
  ic: number | null
  rank_ic: number | null
  icir: number | null
  turnover: number | null
  eval_start: string | null
  eval_end: string | null
  status: string
}

const summary = ref<any>(null)
const factors = ref<Factor[]>([])
const category = ref('')
const orderBy = ref('ic')
const loading = ref(true)
const error = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [sum, list] = await Promise.all([
      fetchFactorSummary(),
      fetchFactors({ status: 'active', category: category.value, limit: 100, order_by: orderBy.value }),
    ])
    summary.value = sum
    factors.value = list
  } catch (e: any) {
    error.value = e.message || '加载失败（后端是否已启动？）'
  } finally {
    loading.value = false
  }
}

onMounted(load)

function fmt(x: number | null, digits = 4): string {
  return x == null ? '-' : x.toFixed(digits)
}

// 按 category 过滤
const filtered = ref(false)
function onCategoryChange() {
  filtered.value = !!category.value
  load()
}
function onOrderChange() {
  load()
}
</script>

<template>
  <div class="page">
    <div class="page-head">
      <h1>因子库</h1>
      <p class="muted">QuantLab 挖掘的真实因子 · 数据源：factor 表</p>
    </div>

    <AppSpinner v-if="loading" />
    <AppError v-else-if="error" :message="error" @retry="load" />

    <template v-else-if="summary">
      <!-- 概览（真实计数） -->
      <div class="stat-row">
        <div class="stat-card">
          <div class="stat-num">{{ summary.total }}</div>
          <div class="faint stat-label">因子总数</div>
        </div>
        <div class="stat-card">
          <div class="stat-num">{{ summary.active }}</div>
          <div class="faint stat-label">活跃因子</div>
        </div>
        <div class="stat-card">
          <div class="stat-num">{{ summary.categories.length }}</div>
          <div class="faint stat-label">类别数</div>
        </div>
      </div>

      <!-- 类别标签（点击过滤） -->
      <div class="card section">
        <div class="chip-row">
          <button class="chip" :class="{ active: !category }" @click="category = ''; onCategoryChange()">全部</button>
          <button
            v-for="c in summary.categories"
            :key="c"
            class="chip"
            :class="{ active: category === c }"
            @click="category = c; onCategoryChange()"
          >{{ c }}</button>
        </div>
      </div>

      <!-- 排序 + 因子表格 -->
      <div class="card section">
        <div class="table-toolbar">
          <h2 class="section-title">因子列表</h2>
          <select v-model="orderBy" class="select" @change="onOrderChange">
            <option value="ic">按 IC 排序</option>
            <option value="icir">按 ICIR 排序</option>
            <option value="rank_ic">按 RankIC 排序</option>
            <option value="turnover">按换手率排序</option>
          </select>
        </div>

        <div v-if="factors.length === 0" class="muted empty">该分类暂无因子</div>
        <div v-else class="table-wrap">
          <table class="table">
            <thead>
              <tr>
                <th>因子名</th>
                <th>类别</th>
                <th>IC</th>
                <th>RankIC</th>
                <th>ICIR</th>
                <th>换手</th>
                <th>评估区间</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="f in factors" :key="f.name">
                <td class="mono">{{ f.name }}</td>
                <td><span class="badge">{{ f.category }}</span></td>
                <td :class="{ 'pos': (f.ic ?? 0) > 0 }">{{ fmt(f.ic) }}</td>
                <td>{{ fmt(f.rank_ic) }}</td>
                <td>{{ fmt(f.icir) }}</td>
                <td>{{ fmt(f.turnover, 2) }}</td>
                <td class="faint eval">{{ f.eval_start }} ~ {{ f.eval_end }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.page { max-width: 1000px; }
.page-head { margin-bottom: 24px; }
.page-head h1 { font-size: 24px; margin-bottom: 4px; }
.status { padding: 40px; text-align: center; }

.stat-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin-bottom: 20px; }
.stat-card { background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius-md); padding: 18px; text-align: center; box-shadow: var(--shadow-sm); }
.stat-num { font-size: 28px; font-weight: 700; color: var(--primary); }
.stat-label { font-size: 13px; }

.section { margin-bottom: 16px; }
.section-title { font-size: 16px; margin: 0; }
.chip-row { display: flex; gap: 8px; flex-wrap: wrap; }
.chip {
  font-size: 12px; padding: 4px 12px; border-radius: 999px; border: 1px solid var(--border-strong);
  background: var(--bg-card); color: var(--text-2); cursor: pointer; transition: all 0.12s;
}
.chip:hover { border-color: var(--primary); color: var(--primary); }
.chip.active { background: var(--primary-soft); border-color: var(--primary); color: var(--primary); }

.table-toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
.select {
  padding: 6px 10px; font-size: 13px; border: 1px solid var(--border-strong); border-radius: var(--radius-sm);
  background: var(--bg-card); color: var(--text-1); outline: none; cursor: pointer;
}
.select:focus { border-color: var(--primary); }

.empty { padding: 20px; text-align: center; }
.table-wrap { overflow-x: auto; }
.table { width: 100%; border-collapse: collapse; font-size: 13px; }
.table th, .table td { padding: 9px 10px; text-align: left; border-bottom: 1px solid var(--bg-hover); white-space: nowrap; }
.table th { color: var(--text-3); font-weight: 600; font-size: 12px; }
.table tbody tr:hover { background: var(--bg-hover); }
.mono { font-family: var(--font-mono); font-size: 12.5px; }
.pos { color: var(--success); font-weight: 600; }
.eval { font-size: 12px; }
</style>
