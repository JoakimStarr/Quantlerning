<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { fetchCourses } from '@/api'
import { isCompleted } from '@/stores/progress'
import { chapterLabel } from '@/utils/chapter'
import AppSpinner from '@/components/common/AppSpinner.vue'
import AppError from '@/components/common/AppError.vue'

const route = useRoute()
const router = useRouter()

const phases = ref<any[]>([])
const loading = ref(true)
const error = ref('')

const phaseNum = computed(() => Number(route.params.phase))
const phase = computed(() => phases.value.find((p) => p.phase === phaseNum.value))

const phaseStatus: Record<string, { label: string; cls: string }> = {
  prereq: { label: '前置知识', cls: 'badge' },
  completed: { label: '已完成', cls: 'badge badge-success' },
  in_progress: { label: '进行中', cls: 'badge badge-primary' },
  planned: { label: '计划中', cls: 'badge' },
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    phases.value = await fetchCourses()
  } catch (e: any) {
    error.value = e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)

function goLesson(id: string) {
  router.push(`/lesson/${id}`)
}
</script>

<template>
  <div class="page">
    <AppSpinner v-if="loading" />
    <AppError v-else-if="error" :message="error" @retry="load" />

    <template v-else-if="phase">
      <!-- 阶段头 -->
      <div class="phase-head">
        <div>
          <div class="breadcrumb">
            <button class="link-btn" @click="router.push('/')">学习地图</button>
            <span class="sep">/</span>
            <span>{{ chapterLabel(phase.phase) }}</span>
          </div>
          <h1>{{ phase.title }}</h1>
          <p class="muted">{{ phase.subtitle }} · {{ phase.weeks }}</p>
        </div>
        <span :class="phaseStatus[phase.status]?.cls || 'badge'">{{ phaseStatus[phase.status]?.label || phase.status }}</span>
      </div>

      <!-- 课程列表 -->
      <div class="lesson-list">
        <div v-for="(l, i) in phase.lessons" :key="l.id" class="lesson-item" :class="{ done: isCompleted(l.id) }" @click="goLesson(l.id)">
          <span class="lesson-index" :class="{ done: isCompleted(l.id) }">{{ isCompleted(l.id) ? '✓' : i + 1 }}</span>
          <div class="lesson-body">
            <div class="lesson-title">{{ l.title }}</div>
            <div class="faint lesson-concepts">{{ l.concepts.join(' · ') }}</div>
          </div>
          <span class="faint lesson-arrow">→</span>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.page { max-width: 860px; margin: 0 auto; }
.status { padding: 40px; text-align: center; }

.phase-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; margin-bottom: 28px; }
.breadcrumb { font-size: 13px; color: var(--text-3); margin-bottom: 8px; }
.link-btn { background: none; border: none; color: var(--primary); cursor: pointer; font-size: 13px; padding: 0; }
.link-btn:hover { text-decoration: underline; }
.sep { margin: 0 4px; }
.phase-head h1 { font-size: 24px; margin-bottom: 4px; }

.lesson-list { display: flex; flex-direction: column; gap: 10px; }
.lesson-item {
  display: flex; align-items: center; gap: 14px; padding: 14px 18px;
  background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius-md);
  cursor: pointer; transition: all 0.15s; box-shadow: var(--shadow-sm);
}
.lesson-item:hover { border-color: var(--border-strong); box-shadow: var(--shadow-md); }
.lesson-item.done { border-color: var(--success); }
.lesson-index {
  width: 28px; height: 28px; border-radius: 50%; flex-shrink: 0;
  background: var(--bg-hover); color: var(--text-2);
  display: flex; align-items: center; justify-content: center; font-size: 13px; font-weight: 600;
}
.lesson-index.done { background: var(--success-soft); color: var(--success); }
.lesson-body { flex: 1; }
.lesson-title { font-size: 15px; margin-bottom: 2px; }
.lesson-concepts { font-size: 12px; }
.lesson-arrow { font-size: 15px; }
</style>
