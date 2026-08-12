<script setup lang="ts">
import MarkdownRenderer from '@/components/lesson/MarkdownRenderer.vue'

interface CheatItem {
  name: string
  formula?: string  // LaTeX 字符串
  code?: string     // 代码字符串
}

interface CheatSection {
  title: string
  items: CheatItem[]
}

// Phase 0 前置知识速查：LaTeX 公式 + 代码
const sections: CheatSection[] = [
  {
    title: '概率论与数理统计',
    items: [
      { name: '均值', formula: '$\\mu = \\frac{1}{n}\\sum_{i=1}^{n} x_i$' },
      { name: '方差', formula: '$\\sigma^2 = \\frac{1}{n-1}\\sum_{i=1}^{n} (x_i - \\mu)^2$' },
      { name: '标准差', formula: '$\\sigma = \\sqrt{\\sigma^2}$' },
      { name: '协方差', formula: '$\\mathrm{Cov}(X,Y) = E[(X-\\mu_X)(Y-\\mu_Y)]$' },
      { name: '相关系数', formula: '$\\rho = \\frac{\\mathrm{Cov}(X,Y)}{\\sigma_X \\sigma_Y}$' },
      { name: '正态分布', formula: '$X \\sim N(\\mu, \\sigma^2)$' },
      { name: '中心极限定理', formula: '$X_n \\xrightarrow{d} N(\\mu, \\sigma^2/n)$' },
    ],
  },
  {
    title: '线性代数',
    items: [
      { name: '矩阵乘法', formula: '$(AB)_{ij} = \\sum_{k} A_{ik} B_{kj}$' },
      { name: '转置', formula: '$(A^T)_{ij} = A_{ji}$' },
      { name: '逆矩阵', formula: '$A A^{-1} = I$' },
      { name: '特征值', formula: '$A v = \\lambda v$' },
      { name: '正定矩阵', formula: '$x^T A x > 0,\\ \\forall\\ x \\neq 0$' },
    ],
  },
  {
    title: '微积分',
    items: [
      { name: '导数', formula: "$f'(x) = \\lim_{h \\to 0}\\frac{f(x+h)-f(x)}{h}$" },
      { name: '链式法则', formula: "$(f \\circ g)'(x) = f'(g(x)) \\cdot g'(x)$" },
      { name: '泰勒展开', formula: '$f(x) = \\sum_{n=0}^{\\infty} \\frac{f^{(n)}(a)}{n!}(x-a)^n$' },
      { name: '积分', formula: '$\\int_{a}^{b} f(x)\\,dx = F(b) - F(a)$' },
      { name: '梯度', formula: '$\\nabla f = \\left(\\frac{\\partial f}{\\partial x_1},\\ldots,\\frac{\\partial f}{\\partial x_n}\\right)$' },
    ],
  },
  {
    title: 'Python / Pandas',
    items: [
      { name: '读取', code: 'pd.read_csv("data.csv", parse_dates=["date"])' },
      { name: '滚动窗口', code: 'df["ma20"] = df["close"].rolling(20).mean()' },
      { name: '收益率', code: 'df["ret"] = df["close"].pct_change()' },
      { name: '重采样', code: 'df.set_index("date").resample("M").last()' },
      { name: '合并', code: 'pd.merge(df1, df2, on="date", how="inner")' },
    ],
  },
  {
    title: '常用量化公式',
    items: [
      { name: '年化收益率', formula: '$R_{ann} = (1+R)^{252} - 1$' },
      { name: '年化波动率', formula: '$\\sigma_{ann} = \\sigma_{daily} \\times \\sqrt{252}$' },
      { name: '夏普比率', formula: '$\\mathrm{Sharpe} = \\frac{R_{ann} - r_f}{\\sigma_{ann}}$' },
      { name: '最大回撤', formula: '$\\mathrm{MDD} = \\min\\left(\\frac{P - P_{peak}}{P_{peak}}\\right)$' },
      { name: '对数收益', formula: '$r_t = \\ln(P_t / P_{t-1})$' },
    ],
  },
]
</script>

<template>
  <div class="page">
    <div class="page-head">
      <h1>速查表</h1>
      <p class="muted">Phase 0 前置知识速查 · LaTeX 公式渲染 · 学习时随时翻看</p>
    </div>

    <div v-for="s in sections" :key="s.title" class="card section">
      <h2 class="section-title">{{ s.title }}</h2>
      <div class="item-list">
        <div v-for="it in s.items" :key="it.name" class="item">
          <span class="item-name">{{ it.name }}</span>
          <!-- LaTeX 公式 -->
          <div v-if="it.formula" class="item-formula">
            <MarkdownRenderer :content="it.formula" />
          </div>
          <!-- 代码 -->
          <pre v-else class="item-code-pre"><code>{{ it.code }}</code></pre>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page { max-width: 900px; margin: 0 auto; }
.page-head { margin-bottom: 24px; }
.page-head h1 { font-size: 24px; margin-bottom: 4px; }
.section { margin-bottom: 16px; }
.section-title { font-size: 16px; margin-bottom: 12px; }
.item-list { display: flex; flex-direction: column; }
.item { display: flex; align-items: center; gap: 16px; padding: 8px 0; border-bottom: 1px solid var(--bg-hover); }
.item:last-child { border-bottom: none; }
.item-name { width: 130px; flex-shrink: 0; font-size: 13px; color: var(--text-2); }
.item-formula { flex: 1; font-size: 14px; padding: 4px 0; }
.item-code-pre { flex: 1; margin: 0; }
.item-code-pre code {
  font-family: var(--font-mono);
  font-size: 13px;
  background: var(--bg-hover);
  padding: 4px 10px;
  border-radius: 4px;
}
</style>