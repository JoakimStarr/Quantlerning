<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowRight, Check } from 'lucide-vue-next'
import { fetchCourses } from '@/api'
import { isCompleted } from '@/stores/progress'
import { chapterLabel, PHASE_STATUS as phaseStatus } from '@/utils/chapter'
import AppSpinner from '@/components/common/AppSpinner.vue'
import AppError from '@/components/common/AppError.vue'

// 新版阶段页：与首页 HomeView2 设计 token 对齐（fluid 字号 / --r-* 大圆角 / card-hover 上浮动效）

const route = useRoute()
const router = useRouter()

const phases = ref<any[]>([])
const loading = ref(true)
const error = ref('')

const phaseNum = computed(() => Number(route.params.phase))
const phase = computed(() => phases.value.find((p) => p.phase === phaseNum.value))

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

// 阶段完成进度（镜像首页 phaseProgress）
const done = computed(() => phase.value?.lessons.filter((l: any) => isCompleted(l.id)).length ?? 0)
const total = computed(() => phase.value?.lessons.length ?? 0)
const pct = computed(() => (total.value ? Math.round((done.value / total.value) * 100) : 0))

// 状态文本
const status = computed(() => phaseStatus[phase.value?.status ?? '']?.label || phase.value?.status || '')
</script>

<template>
  <div class="phase2">
    <AppSpinner v-if="loading" text="加载课程…" />
    <AppError v-else-if="error" :message="error" @retry="load" />

    <template v-else-if="phase">
      <!-- HERO：正面锚点 + CTA + 真实进度（镜像首页 hero 结构） -->
      <section class="hero">
        <div class="hero-main">
          <span class="eyebrow">{{ chapterLabel(phase.phase) }}</span>
          <h1>{{ phase.title }}</h1>
          <p class="lead">{{ phase.subtitle }}<template v-if="phase.weeks"> · {{ phase.weeks }}</template></p>

          <div class="hero-cta">
            <a class="btn btn-primary btn-lg" :href="phase.lessons.length ? `/lesson/${phase.lessons[0].id}` : undefined" @click.prevent="phase.lessons.length && goLesson(phase.lessons[0].id)">
              开始本阶段
            </a>
            <a class="btn btn-outline btn-lg" href="/" @click.prevent="router.push('/')">返回课程地图</a>
          </div>

          <div class="hero-stats">
            <div class="hs"><b class="num">{{ total }}</b><span>课程</span></div>
            <div class="hs"><b class="num">{{ done }}</b><span>已完成</span></div>
            <div class="hs"><b class="num">{{ pct }}<span class="unit">%</span></b><span>本阶段进度</span></div>
          </div>
        </div>

        <!-- hero-visual：真实进度（镜像首页进度卡） -->
        <div class="hero-visual">
          <div class="hv-head">
            <span class="hv-title">本阶段进度</span>
            <span class="badge" :class="pct >= 100 ? 'badge-success' : 'badge-primary'">
              {{ status || (pct >= 100 ? '已完成' : '进行中') }}
            </span>
          </div>
          <div class="hv-val num">{{ pct }}%</div>
          <div class="hv-bar"><div class="hv-fill" :style="{ width: pct + '%' }"></div></div>
          <div class="hv-sub">{{ done }} / {{ total }} 课完成</div>
          <div class="hv-mini">
            <div class="mini"><b class="num">{{ pct }}<span class="unit">%</span></b><span>已掌握</span></div>
            <div class="mini"><b class="num">{{ total - done }}</b><span>待学习</span></div>
            <div class="mini"><b class="num">{{ phase.lessons.length }}</b><span>总计</span></div>
          </div>
        </div>
      </section>

      <!-- 章引言 -->
      <p v-if="phase.intro" class="phase-intro">{{ phase.intro }}</p>

      <!-- 课程列表 -->
      <section class="section">
        <div class="section-head">
          <div>
            <h2>本章课程</h2>
            <p>按顺序学，或跳到你需要的课时。</p>
          </div>
          <span class="badge">{{ done }}/{{ total }} 课</span>
        </div>

        <div class="lesson-list">
          <div
            v-for="(l, i) in phase.lessons"
            :key="l.id"
            class="lesson-item"
            :class="{ done: isCompleted(l.id) }"
            role="button"
            tabindex="0"
            @click="goLesson(l.id)"
            @keydown.enter.prevent="goLesson(l.id)"
            @keydown.space.prevent="goLesson(l.id)"
          >
            <span class="lesson-no" :class="{ done: isCompleted(l.id) }">
              <Check v-if="isCompleted(l.id)" :size="16" />
              <span v-else class="no">{{ i + 1 }}</span>
            </span>

            <div class="lesson-body">
              <div class="lesson-top">
                <div class="lesson-title">{{ l.title }}</div>
                <span v-if="isCompleted(l.id)" class="done-tag"><Check :size="11" /> 已完成</span>
              </div>
              <div class="lesson-concepts">
                <span v-for="c in l.concepts" :key="c" class="chip">{{ c }}</span>
              </div>
            </div>

            <span class="lesson-arrow"><ArrowRight :size="17" /></span>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
/* 设计 token 全部来自全局 main.css，与首页 HomeView2 一致 */

.phase2 {
  max-width: 1080px;
  margin: 0 auto;
}

/* ============ Hero（对齐首页 hero） ============ */
.hero {
  display: grid;
  grid-template-columns: 1.1fr 0.9fr;
  gap: 40px;
  align-items: center;
  padding: clamp(28px, 5vw, 64px) 0 clamp(20px, 4vw, 32px);
}
.hero .eyebrow {
  display: inline-block;
  font-family: var(--font-mono);
  font-size: var(--fs-xs);
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--primary);
  font-weight: 600;
  margin-bottom: 16px;
}
.hero h1 {
  font-size: var(--fs-2xl);
  margin-bottom: 12px;
  max-width: 18ch;
  letter-spacing: -0.02em;
  line-height: 1.15;
}
.hero .lead { color: var(--text-2); font-size: var(--fs-md); max-width: 46ch; margin-bottom: 24px; line-height: 1.7; }
.hero-cta { display: flex; gap: 12px; flex-wrap: wrap; }
.hero-stats { display: flex; gap: 28px; margin-top: 28px; flex-wrap: wrap; }
.hs b { font-family: var(--font-mono); font-size: var(--fs-md); font-weight: 600; line-height: 1.15; display: block; }
.hs .unit { font-size: 0.6em; }
.hs span:not(.unit) { font-size: var(--fs-xs); color: var(--text-3); }

/* hero-visual：真实进度卡（对齐首页） */
.hero-visual {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--r-xl);
  padding: 24px;
  box-shadow: var(--shadow-md);
}
.hv-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
.hv-title { font-family: var(--font-mono); font-size: var(--fs-xs); color: var(--text-3); letter-spacing: 0.06em; }
.hv-val { font-family: var(--font-mono); font-size: var(--fs-num); font-weight: 600; line-height: 1.1; letter-spacing: -0.02em; color: var(--primary); }
.hv-bar { height: 8px; border-radius: var(--r-pill); background: var(--bg-hover); overflow: hidden; margin: 12px 0 6px; }
.hv-fill { height: 100%; border-radius: var(--r-pill); background: var(--primary); transition: width 0.4s var(--ease-out); }
.hv-sub { font-size: var(--fs-sm); color: var(--text-3); }
.hv-mini {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-top: 18px;
  padding-top: 16px;
  border-top: 1px solid var(--border);
}
.hv-mini .mini b { font-family: var(--font-mono); font-size: var(--fs-md); font-weight: 600; display: block; line-height: 1.2; }
.hv-mini .mini .unit { font-size: 0.6em; }
.hv-mini .mini span { font-size: var(--fs-xs); color: var(--text-3); }

/* ============ 按钮（对齐首页） ============ */
.btn {
  display: inline-flex; align-items: center; justify-content: center; gap: 8px;
  padding: 10px 18px;
  font-family: var(--font-base); font-size: var(--fs-base); font-weight: 600; line-height: 1;
  color: var(--text-1); background: var(--bg-card);
  border: 1px solid var(--border-strong); border-radius: var(--r-sm);
  cursor: pointer; user-select: none; white-space: nowrap;
  transition: background 0.16s var(--ease-out), border-color 0.16s var(--ease-out),
              transform 0.16s var(--ease-out), box-shadow 0.16s var(--ease-out);
}
.btn:hover { transform: translateY(-1px); color: var(--text-1); }
.btn:active { transform: translateY(0); }
.btn-primary { background: var(--primary); border-color: var(--primary); color: #fff; }
.btn-primary:hover { background: var(--primary-hover); border-color: var(--primary-hover); box-shadow: var(--shadow-md); color: #fff; }
.btn-outline { background: transparent; border-color: var(--primary); color: var(--primary); }
.btn-outline:hover { background: var(--primary-soft); }
.btn-lg { padding: 13px 24px; font-size: var(--fs-md); }

/* ============ 章引言 ============ */
.phase-intro {
  font-size: var(--fs-md);
  color: var(--text-2);
  line-height: 1.85;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-left: 3px solid var(--primary);
  border-radius: var(--r-lg);
  padding: 18px 22px;
  margin-bottom: 8px;
  box-shadow: var(--shadow-xs);
}

/* ============ 区块节奏 ============ */
.section { padding: clamp(32px, 5vw, 56px) 0 0; }
.section-head { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; margin-bottom: var(--sp-5); flex-wrap: wrap; }
.section-head h2 { font-size: var(--fs-xl); letter-spacing: -0.01em; }
.section-head p { color: var(--text-3); font-size: var(--fs-sm); margin-top: 6px; }

/* ============ 课程列表卡片（card-hover 上浮动效） ============ */
.lesson-list { display: flex; flex-direction: column; gap: var(--sp-4); }
.lesson-item {
  display: flex; align-items: center; gap: 18px;
  padding: 18px 22px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--r-lg);
  box-shadow: var(--shadow-xs);
  cursor: pointer;
  transition: border-color 0.24s var(--ease-out), transform 0.24s var(--ease-out),
              box-shadow 0.24s var(--ease-out);
}
.lesson-item:hover {
  border-color: color-mix(in srgb, var(--primary) 45%, var(--border));
  transform: translateY(-3px);
  box-shadow: var(--shadow-md);
}
.lesson-item:focus-visible { outline: 2px solid var(--primary); outline-offset: 2px; }

/* 序号（浮动圆角盘，镜像首页 phase .no） */
.lesson-no {
  width: 46px; height: 46px; flex: none;
  border-radius: var(--r-md);
  background: var(--primary-soft); color: var(--primary);
  display: grid; place-content: center;
}
.lesson-no .no { font-family: var(--font-display); font-weight: 700; font-size: 14px; letter-spacing: 0.5px; }
.lesson-no.done { background: var(--success-soft); color: var(--success); }

.lesson-body { flex: 1; min-width: 0; }
.lesson-top { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.lesson-title { font-size: var(--fs-md); font-weight: 600; color: var(--text-1); }
.done-tag {
  display: inline-flex; align-items: center; gap: 4px;
  font-size: var(--fs-xs); font-weight: 600;
  color: var(--success);
}
.lesson-concepts { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
.chip {
  font-size: var(--fs-xs);
  color: var(--text-2);
  background: var(--bg-subtle);
  padding: 3px 10px;
  border-radius: var(--r-pill);
  white-space: nowrap;
}
.lesson-arrow { color: var(--text-3); flex-shrink: 0; display: flex; transition: transform 0.24s var(--ease-out), color 0.24s var(--ease-out); }
.lesson-item:hover .lesson-arrow { color: var(--primary); transform: translateX(3px); }

/* ============ 响应式 ============ */
@media (max-width: 820px) {
  .hero { grid-template-columns: 1fr; gap: 28px; }
  .hero-visual { order: -1; }
  .lesson-item { padding: 15px 16px; }
}
</style>