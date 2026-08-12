<script setup lang="ts">
import { computed, ref } from 'vue'
import { vizRegistry, type VizKey } from '@/components/lesson/vizRegistry'

// 可视化实验室：列出全部已注册模拟器（vizRegistry），按阶段分组，点开即玩
// 仅展示已实现（comp 存在）的模拟器；未实现的占位组件不列入

// viz key → 所属阶段（feature_pipeline / gradient_field 跨阶段，归入最早出现的阶段）
const KEY_PHASE: Record<string, number> = {
  // Phase 0 前言：数学基础
  derivative_tangent: 0, gradient_field: 0, integral_area: 0, num_integration: 0, matrix_transform: 0, eigen_demo: 0,
  linear_approx: 0, concavity_demo: 0, taylor_series: 0,
  venn_diagram: 0, normal_dist: 0, distribution_explorer: 0, bayes_update: 0, law_of_large_numbers: 0,
  confidence_interval: 0, sampling_dist: 0, mle_demo: 0, p_value: 0, chi_square: 0, regression_fit: 0,
  feature_pipeline: 0,
  // Phase 1 金融市场
  discount_curve: 1, bond_duration: 1, ddm_valuation: 1, capm_sml: 1, real_vs_log: 1, vol_cluster: 1,
  pe_distribution: 1, compound_growth: 1, sharpe_simulator: 1, mdd_simulator: 1, macd_simulator: 1, rsi_simulator: 1,
  // Phase 2 策略与回测
  strategy_signal: 2, trend_follow: 2, bollinger_bands: 2, momentum: 2, backtest_engine: 2,
  strategy_compare: 2, cost_impact: 2, lookahead: 2, parameter_landscape: 2,
  // Phase 3 因子
  ic_distribution: 3, factor_ic: 3, layer_returns: 3, industry_pe: 3, factor_backtest_dashboard: 3,
  // Phase 4 衍生品
  random_walk: 4, bs_price_slider: 4, binomial_tree: 4, monte_carlo_pricing: 4, var_simulator: 4,
  // Phase 5 ML
  label_design: 5, overfit_demo: 5, feature_importance: 5, ml_backtest: 5,
  // Phase 6 组合
  frontier: 6, risk_parity: 6, black_litterman: 6, pair_trading: 6, portfolio_risk: 6,
}

const PHASES = [
  { phase: 0, label: '前言', title: '数学基础' },
  { phase: 1, label: '第一章', title: '金融市场' },
  { phase: 2, label: '第二章', title: '策略与回测' },
  { phase: 3, label: '第三章', title: '因子投资' },
  { phase: 4, label: '第四章', title: '衍生品' },
  { phase: 5, label: '第五章', title: '机器学习' },
  { phase: 6, label: '第六章', title: '组合优化' },
]

interface SimItem {
  key: VizKey
  title: string
  desc: string
}

// 全部已实现的模拟器
const allSims = computed<SimItem[]>(() =>
  (Object.entries(vizRegistry) as [VizKey, { title: string; desc: string; comp?: unknown }][])
    .filter(([, def]) => !!def.comp)
    .map(([key, def]) => ({ key, title: def.title, desc: def.desc })),
)

// 搜索
const query = ref('')
const activePhase = ref<number | 'all'>('all')

const groups = computed(() => {
  const q = query.value.trim().toLowerCase()
  const filtered = allSims.value.filter((s) => {
    if (activePhase.value !== 'all' && KEY_PHASE[s.key] !== activePhase.value) return false
    if (!q) return true
    return s.title.toLowerCase().includes(q) || s.desc.toLowerCase().includes(q)
  })
  if (activePhase.value !== 'all') {
    return [{ phase: activePhase.value, label: PHASES.find((p) => p.phase === activePhase.value)?.label ?? '', title: PHASES.find((p) => p.phase === activePhase.value)?.title ?? '', sims: filtered }]
  }
  return PHASES.map((p) => ({
    ...p,
    sims: filtered.filter((s) => KEY_PHASE[s.key] === p.phase),
  })).filter((g) => g.sims.length > 0)
})

const total = computed(() => allSims.value.length)

// 展开状态：支持同时打开多个
const openSet = ref<Set<string>>(new Set())
function toggle(key: string) {
  const s = new Set(openSet.value)
  if (s.has(key)) s.delete(key)
  else s.add(key)
  openSet.value = s
}

function countOf(phase: number) {
  return allSims.value.filter((s) => KEY_PHASE[s.key] === phase).length
}
</script>

<template>
  <div class="page">
    <div class="page-head">
      <h1>可视化实验室</h1>
      <p class="muted">共 {{ total }} 个交互模拟器 · 点击卡片展开即玩，不受课程顺序约束</p>
    </div>

    <!-- 搜索 + 阶段过滤 -->
    <div class="toolbar">
      <input v-model="query" class="search" type="search" placeholder="搜索模拟器（如 夏普、前沿、配对）" />
      <div class="chips">
        <button class="chip" :class="{ active: activePhase === 'all' }" @click="activePhase = 'all'">全部</button>
        <button
          v-for="p in PHASES"
          :key="p.phase"
          class="chip"
          :class="{ active: activePhase === p.phase }"
          @click="activePhase = p.phase"
        >
          {{ p.label }} <span class="chip-count">{{ countOf(p.phase) }}</span>
        </button>
      </div>
    </div>

    <!-- 分阶段列表 -->
    <section v-for="g in groups" :key="g.phase" class="phase-block">
      <h2 class="block-title">
        {{ g.label }} · {{ g.title }}
        <span class="block-count">{{ g.sims.length }}</span>
      </h2>

      <div class="sim-grid">
        <div v-for="s in g.sims" :key="s.key" class="sim-card" :class="{ open: openSet.has(s.key) }">
          <button class="sim-head" @click="toggle(s.key)">
            <div class="sim-text">
              <div class="sim-name">{{ s.title }}</div>
              <div class="sim-desc">{{ s.desc }}</div>
            </div>
            <span class="chevron">{{ openSet.has(s.key) ? '▾' : '▸' }}</span>
          </button>

          <div v-if="openSet.has(s.key)" class="sim-body">
            <component :is="vizRegistry[s.key]?.comp" :key="s.key" />
          </div>
        </div>
      </div>
    </section>

    <div v-if="groups.length === 0" class="empty">
      没有匹配的模拟器，换个关键词试试。
    </div>
  </div>
</template>

<style scoped>
.page { max-width: 1000px; margin: 0 auto; }
.page-head { margin-bottom: 20px; }
.page-head h1 { font-size: 24px; margin-bottom: 4px; }

.toolbar { display: flex; flex-direction: column; gap: 10px; margin-bottom: 8px; }
.search {
  padding: 8px 12px; border: 1px solid var(--border); border-radius: var(--radius-sm);
  background: var(--bg-card); color: var(--text-1); font-size: 13.5px; width: 100%;
}
.search:focus { outline: none; border-color: var(--primary); }
.chips { display: flex; flex-wrap: wrap; gap: 6px; }
.chip {
  font-size: 12.5px; padding: 4px 12px; border-radius: 999px; border: 1px solid var(--border);
  background: var(--bg-card); color: var(--text-2); cursor: pointer;
}
.chip:hover { border-color: var(--primary); color: var(--primary); }
.chip.active { background: var(--primary-soft); border-color: var(--primary); color: var(--primary); font-weight: 600; }
.chip-count { opacity: 0.7; font-size: 11px; margin-left: 2px; }

.block-title { font-size: 16px; margin: 24px 0 12px; display: flex; align-items: baseline; gap: 8px; }
.block-count { font-size: 12px; color: var(--text-3); }

.sim-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 12px; align-items: start; }
.sim-card {
  background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius-md);
  overflow: hidden; box-shadow: var(--shadow-sm);
}
.sim-card.open { grid-column: 1 / -1; border-color: var(--primary); }
.sim-head {
  display: flex; align-items: center; gap: 10px; width: 100%; text-align: left;
  padding: 14px 16px; background: none; border: none; cursor: pointer;
}
.sim-head:hover { background: var(--bg-hover); }
.sim-text { flex: 1; min-width: 0; }
.sim-name { font-weight: 600; font-size: 14px; margin-bottom: 3px; }
.sim-desc { font-size: 12.5px; color: var(--text-3); }
.chevron { color: var(--text-3); font-size: 14px; }
.sim-body { border-top: 1px solid var(--border); }
</style>
