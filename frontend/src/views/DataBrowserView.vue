<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { fetchIndices, searchStock, fetchMacroIndicators } from '@/api'
import AppSpinner from '@/components/common/AppSpinner.vue'
import AppError from '@/components/common/AppError.vue'
import PageBreadcrumb from '@/components/common/PageBreadcrumb.vue'

// 数据浏览器：浏览真实行情/宏观数据
const stocks = ref<any[]>([])
const searchQ = ref('')
const searching = ref(false)
const searchError = ref('')

const indices = ref<any[]>([])
const macros = ref<any[]>([])
const loading = ref(true)
const loadError = ref('')

const sampleNames: Record<string, string> = {
  sh600519: '贵州茅台', sh601318: '中国平安', sz000001: '平安银行', sz300750: '宁德时代',
}

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    const [idx, mac] = await Promise.all([fetchIndices('index'), fetchMacroIndicators()])
    indices.value = idx
    macros.value = mac
  } catch (e: any) {
    loadError.value = e?.message || '加载失败（后端是否已启动？）'
  } finally {
    loading.value = false
  }
}

onMounted(load)

async function doSearch() {
  if (!searchQ.value.trim()) return
  searching.value = true
  searchError.value = ''
  try {
    stocks.value = await searchStock(searchQ.value.trim())
  } catch (e: any) {
    stocks.value = []
    searchError.value = e?.message || '搜索失败（后端是否已启动？）'
  } finally {
    searching.value = false
  }
}
</script>

<template>
  <div class="page">
    <div class="page-head">
      <PageBreadcrumb current="数据浏览器" />
      <h1>数据浏览器</h1>
      <p class="muted">浏览 quantlab 库中的真实 A 股 · 财务 · 宏观数据</p>
    </div>

    <AppSpinner v-if="loading" />
    <AppError v-else-if="loadError" :message="loadError" @retry="load" />

    <template v-else>
      <!-- 个股搜索 -->
      <div class="card section">
        <h2 class="section-title">个股搜索</h2>
        <div class="search-row">
          <input v-model="searchQ" class="input" placeholder="输入代码或名称，如 600519 / 茅台" @keyup.enter="doSearch" />
          <button class="btn btn-primary" :disabled="searching" @click="doSearch">{{ searching ? '搜索中…' : '搜索' }}</button>
        </div>
        <p v-if="searchError" class="error-text search-error">{{ searchError }}</p>
        <div v-if="stocks.length" class="stock-list">
          <div v-for="s in stocks" :key="s.code" class="stock-item">
            <code class="stock-code">{{ s.code }}</code>
            <span>{{ s.name }}</span>
            <span class="faint">{{ s.type === '1' ? 'A股' : s.type }}</span>
          </div>
        </div>
        <div class="quick-samples">
          <span class="faint quick-label">示例：</span>
          <button v-for="(name, code) in sampleNames" :key="code" class="chip" @click="searchQ = code; doSearch()">{{ name }}</button>
        </div>
      </div>

      <!-- 指数清单 -->
      <div class="card section">
        <h2 class="section-title">指数（元数据）</h2>
        <p class="faint note">日线数据源：宽基指数在 QuantLab qlib_bin，学习站 Phase 1 引入 baostock 后补齐</p>
        <div class="index-grid">
          <div v-for="idx in indices" :key="idx.code" class="index-item">
            <code>{{ idx.code }}</code>
            <span class="muted">{{ idx.name }}</span>
          </div>
        </div>
      </div>

      <!-- 宏观指标 -->
      <div class="card section">
        <h2 class="section-title">宏观指标</h2>
        <div class="macro-grid">
          <span v-for="m in macros" :key="m" class="badge">{{ m }}</span>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.page { max-width: 960px; margin: 0 auto; }
.page-head { margin-bottom: 24px; }
.page-head h1 { font-size: 24px; margin-bottom: 4px; }
.status { padding: 40px; text-align: center; }

.section { margin-bottom: 16px; }
.section-title { font-size: 16px; margin-bottom: 12px; }
.note { font-size: 12px; margin-bottom: 10px; }

.search-row { display: flex; gap: 10px; margin-bottom: 12px; }
.search-error { margin: -4px 0 10px; font-size: 13px; }
.input {
  flex: 1; max-width: 360px; padding: 8px 12px; font-size: 14px;
  border: 1px solid var(--border-strong); border-radius: var(--radius-sm);
  outline: none; transition: border-color 0.15s;
}
.input:focus { border-color: var(--primary); }

.stock-list { display: flex; flex-direction: column; margin-bottom: 12px; }
.stock-item { display: flex; gap: 12px; padding: 6px 0; border-bottom: 1px solid var(--bg-hover); font-size: 13px; }
.stock-code { width: 90px; flex-shrink: 0; }

.quick-samples { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.quick-label { font-size: 12px; }
.chip {
  font-size: 12px; padding: 3px 10px; border-radius: 999px; border: 1px solid var(--border-strong);
  background: var(--bg-card); color: var(--text-2); cursor: pointer;
}
.chip:hover { border-color: var(--primary); color: var(--primary); }

.index-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 8px; }
.index-item { display: flex; flex-direction: column; padding: 10px; background: var(--bg-hover); border-radius: var(--radius-sm); font-size: 13px; }

.macro-grid { display: flex; flex-wrap: wrap; gap: 8px; }
</style>
