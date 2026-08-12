<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { fetchCourses } from '@/api'
import { isCompleted, totalQuizPassed, learningDays, totalExercises } from '@/stores/progress'
import { chapterLabel } from '@/utils/chapter'
import AppSpinner from '@/components/common/AppSpinner.vue'

// 学习统计：进度/活跃度（数据来自前端 localStorage 单一真源）
const phases = ref<any[]>([])
const loading = ref(true)

onMounted(async () => {
  try {
    phases.value = await fetchCourses()
  } finally {
    loading.value = false
  }
})

const done = computed(() => phases.value.flatMap((p: any) => p.lessons).filter((l: any) => isCompleted(l.id)).length)
const total = computed(() => phases.value.reduce((n: number, p: any) => n + p.lessons.length, 0))
const pct = computed(() => (total.value ? Math.round((done.value / total.value) * 100) : 0))

const stats = computed(() => [
  { label: '已完成课程', value: `${done.value}/${total.value}`, hint: `共 ${total.value} 课` },
  { label: '完成率', value: `${pct.value}%`, hint: '总体进度' },
  { label: '学习天数', value: `${learningDays()}`, hint: '有学习活动的天数' },
  { label: '练习提交', value: `${totalExercises()}`, hint: '测验 + 应用题 + 代码运行' },
  { label: '测验通过', value: `${totalQuizPassed()}`, hint: '已答对的知识点测验' },
])
</script>

<template>
  <div class="page">
    <div class="page-head">
      <h1>学习统计</h1>
      <p class="muted">学习进度与活跃度 · 数据本地保存</p>
    </div>

    <AppSpinner v-if="loading" />

    <template v-else>
      <div class="stat-grid">
        <div v-for="s in stats" :key="s.label" class="stat-card">
          <div class="stat-value">{{ s.value }}</div>
          <div class="stat-label">{{ s.label }}</div>
          <div class="faint stat-hint">{{ s.hint }}</div>
        </div>
      </div>

      <!-- 各阶段进度 -->
      <div class="card section">
        <h2 class="section-title">各阶段进度</h2>
        <div v-for="p in phases" :key="p.phase" class="phase-row">
          <span class="muted phase-name">{{ chapterLabel(p.phase) }} · {{ p.title }}</span>
          <div class="bar-track">
            <div class="bar-fill" :style="{ width: p.lessons.length ? (p.lessons.filter((l: any) => isCompleted(l.id)).length / p.lessons.length) * 100 + '%' : '0%' }"></div>
          </div>
          <span class="faint phase-count">
            {{ p.lessons.filter((l: any) => isCompleted(l.id)).length }}/{{ p.lessons.length }}
          </span>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.page { max-width: 900px; margin: 0 auto; }
.page-head { margin-bottom: 24px; }
.page-head h1 { font-size: 24px; margin-bottom: 4px; }
.status { padding: 40px; text-align: center; }

.stat-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 14px; margin-bottom: 20px; }
.stat-card { background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius-md); padding: 18px; text-align: center; box-shadow: var(--shadow-sm); }
.stat-value { font-size: 24px; font-weight: 700; color: var(--primary); }
.stat-label { font-size: 13px; color: var(--text-2); margin: 2px 0; }
.stat-hint { font-size: 12px; }

.section { margin-bottom: 16px; }
.section-title { font-size: 16px; margin-bottom: 16px; }
.phase-row { display: flex; align-items: center; gap: 14px; padding: 8px 0; border-bottom: 1px solid var(--bg-hover); }
.phase-row:last-child { border-bottom: none; }
.phase-name { width: 220px; flex-shrink: 0; font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.bar-track { flex: 1; height: 8px; background: var(--bg-hover); border-radius: 4px; overflow: hidden; }
.bar-fill { height: 100%; background: var(--primary); border-radius: 4px; transition: width 0.3s; }
.phase-count { font-size: 12px; width: 50px; text-align: right; flex-shrink: 0; }
</style>
