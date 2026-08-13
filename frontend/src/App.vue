<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import { fetchCourses, fetchLesson } from '@/api'
import { isCompleted } from '@/stores/progress'
import { chapterLabel } from '@/utils/chapter'

const route = useRoute()
const router = useRouter()

// 记忆最近访问的页面：路由变化时写入 localStorage，落地首页时自动跳回
const LAST_PATH_KEY = 'ql:lastPath'
watch(
  () => route.fullPath,
  (p) => {
    try {
      localStorage.setItem(LAST_PATH_KEY, p)
    } catch {
      // 存储不可用：忽略
    }
  },
)

// 目录数据：卷(Phase) → 章(课程) → 概念子节
const volumes = ref<any[]>([])
const loaded = ref(false)

// 目录搜索：按课程标题/概念过滤（59+ 课时快速定位）
const searchQuery = ref('')
const filteredVolumes = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return volumes.value
  return volumes.value
    .map((v) => ({
      ...v,
      lessons: v.lessons.filter(
        (l: any) =>
          l.title.toLowerCase().includes(q) ||
          (l.concepts ?? []).some((c: string) => c.toLowerCase().includes(q)),
      ),
    }))
    .filter((v) => v.lessons.length)
})

// 已展开子节的课程集合（可收起）
const openLessons = reactive<Set<string>>(new Set())
// 子节缓存：lesson_id → {title, id}[]（id 与 LessonView 的 sec-N 对齐）
const sectionsCache = reactive<Record<string, { title: string; id: string }[]>>({})
const currentLessonId = ref('')

// 当前路由是课程页时：高亮该章，并自动展开其子节
watch(
  () => route.params.id,
  (id) => {
    const lessonId = typeof id === 'string' ? id : ''
    currentLessonId.value = lessonId
    if (lessonId && !openLessons.has(lessonId)) {
      openLessons.add(lessonId)
      loadSections(lessonId)
    }
  },
  { immediate: true },
)

// ---------- 移动端抽屉目录 ----------
const menuOpen = ref(false)
function closeMenu() {
  menuOpen.value = false
}

// 侧边栏「工具」二级菜单（点击展开，点击外部收起）
const toolsOpen = ref(false)
const toolsRef = ref<HTMLElement | null>(null)
// 点击菜单外部时收起
function onDocClick(e: MouseEvent) {
  if (toolsOpen.value && toolsRef.value && !toolsRef.value.contains(e.target as Node)) {
    toolsOpen.value = false
  }
}
onMounted(() => document.addEventListener('click', onDocClick))
// 路由变化时收起弹层（导航后不再遮挡内容）
watch(
  () => route.fullPath,
  () => {
    toolsOpen.value = false
  },
)

// ---------- 深色模式 ----------
const theme = ref<'light' | 'dark'>(
  document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light',
)

// 未手动设置过主题时，跟随系统偏好（用户一旦手动切换即固定）
let mql: MediaQueryList | null = null
let followSystem = false
try {
  followSystem = !localStorage.getItem('ql:theme')
} catch {
  followSystem = true
}
function applySystemTheme(e?: MediaQueryListEvent) {
  if (!followSystem) return
  theme.value = e ? (e.matches ? 'dark' : 'light') : (mql?.matches ? 'dark' : 'light')
  document.documentElement.setAttribute('data-theme', theme.value)
}
if (followSystem && typeof window.matchMedia === 'function') {
  mql = window.matchMedia('(prefers-color-scheme: dark)')
  applySystemTheme() // 与 main.ts 初始化保持一致（如系统在挂载后变化）
  mql.addEventListener('change', applySystemTheme)
}

function toggleTheme() {
  // 手动选择后固定，不再跟随系统
  followSystem = false
  mql?.removeEventListener('change', applySystemTheme)
  mql = null
  theme.value = theme.value === 'dark' ? 'light' : 'dark'
  document.documentElement.setAttribute('data-theme', theme.value)
  try {
    localStorage.setItem('ql:theme', theme.value)
  } catch {
    // 存储不可用：忽略
  }
}

// 顶栏当前课程名（移动端显示）
const currentLessonTitle = computed(() => {
  if (!currentLessonId.value) return ''
  for (const v of volumes.value) {
    const l = v.lessons?.find((x: any) => x.id === currentLessonId.value)
    if (l) return l.title
  }
  return ''
})

onMounted(async () => {
  try {
    volumes.value = await fetchCourses()
  } finally {
    loaded.value = true
  }
})

// 加载并缓存某课程的子节（与 LessonView 的 sections 对齐）
async function loadSections(lessonId: string) {
  if (sectionsCache[lessonId]) return
  try {
    const detail = await fetchLesson(lessonId)
    const items = (detail.sections ?? []).map((s: any, i: number) => ({
      title: s.title,
      id: `sec-${i}`,
    }))
    sectionsCache[lessonId] = items
  } catch {
    sectionsCache[lessonId] = []
  }
}

// 点击课程：跳转 + 展开/收起子节
function toggleLesson(lesson: any) {
  currentLessonId.value = lesson.id
  closeMenu() // 移动端：点击后收起抽屉
  router.push(`/lesson/${lesson.id}`)
  if (openLessons.has(lesson.id)) {
    // 再点收起
    openLessons.delete(lesson.id)
  } else {
    openLessons.add(lesson.id)
    loadSections(lesson.id)
  }
}

// 点击概念子节 → 跳转课程页并滚动到对应区块
function goToSection(lessonId: string, sectionId: string) {
  closeMenu() // 移动端：点击后收起抽屉
  if (route.params.id !== lessonId) {
    router.push(`/lesson/${lessonId}?section=${sectionId}`)
  } else {
    document.getElementById(sectionId)?.scrollIntoView({ behavior: 'smooth' })
  }
}

const phaseStatus: Record<string, { label: string; cls: string }> = {
  prereq: { label: '前置', cls: 'badge' },
  completed: { label: '✓ 完成', cls: 'badge badge-success' },
  in_progress: { label: '进行中', cls: 'badge badge-primary' },
  planned: { label: '计划', cls: 'badge' },
}

// 底部功能入口
const tools: { to?: string; href?: string; label: string; icon: string; external?: boolean }[] = [
  { to: '/lab', label: '可视化实验室', icon: '🧪' },
  { to: '/cheatsheet', label: '速查表', icon: '📋' },
  { to: '/data-browser', label: '数据浏览器', icon: '📊' },
  { to: '/factors', label: '因子库', icon: '🧬' },
  { to: '/stats', label: '学习统计', icon: '📈' },
  { to: '/settings', label: '设置', icon: '⚙️' },
  { href: 'http://localhost:3000', label: 'QuantLab 回测', icon: '🔬', external: true },
]
</script>

<template>
  <div class="layout">
    <!-- 移动端顶栏（≤900px 显示）：汉堡 + 品牌 + 当前课程 -->
    <header class="topbar">
      <button class="menu-btn" aria-label="切换目录" @click="menuOpen = !menuOpen">☰</button>
      <RouterLink to="/" class="topbar-brand" @click="closeMenu">
        <span class="brand-mark">Q</span>
      </RouterLink>
      <span class="topbar-title">{{ currentLessonTitle || 'Quantlerning' }}</span>
      <button class="theme-btn" :title="theme === 'dark' ? '切换到浅色模式' : '切换到深色模式'" aria-label="切换深浅色模式" @click="toggleTheme">
        {{ theme === 'dark' ? '☀️' : '🌙' }}
      </button>
    </header>

    <!-- 抽屉遮罩（移动端） -->
    <div v-if="menuOpen" class="drawer-mask" @click="closeMenu"></div>

    <!-- 左侧：书的目录 -->
    <aside class="sidebar" :class="{ open: menuOpen }">
      <RouterLink to="/" class="brand" @click="closeMenu">
        <span class="brand-mark">Q</span>
        <span class="brand-name">Quantlerning</span>
      </RouterLink>

      <div class="toc-label">📑 目录</div>

      <div class="toc-search">
        <input v-model="searchQuery" type="search" placeholder="搜索课程…" spellcheck="false" />
      </div>

      <nav class="toc">
        <div v-if="!loaded" class="toc-status">加载目录...</div>
        <div v-else-if="filteredVolumes.length === 0" class="toc-status">无匹配课程</div>
        <div v-for="v in filteredVolumes" :key="v.phase" class="volume">
          <!-- 卷头 -->
          <div class="volume-head" @click="v.lessons.length && (closeMenu(), router.push(`/phase/${v.phase}`))">
            <span class="volume-title">{{ chapterLabel(v.phase) }}</span>
            <span class="volume-name">{{ v.title }}</span>
            <span v-if="v.status !== 'planned' || v.lessons.length" :class="phaseStatus[v.status]?.cls || 'badge'">{{ phaseStatus[v.status]?.label || v.status }}</span>
          </div>

          <!-- 卷下的章（课程） -->
          <div v-for="l in v.lessons" :key="l.id" class="chapter">
            <div
              class="chapter-head"
              :class="{ active: currentLessonId === l.id }"
              @click="toggleLesson(l)"
            >
              <span class="chapter-icon">{{ openLessons.has(l.id) ? '▾' : (isCompleted(l.id) ? '✓' : '▸') }}</span>
              <span class="chapter-title" :class="{ done: isCompleted(l.id) }">{{ l.title }}</span>
            </div>

            <!-- 展开的子节 -->
            <div v-if="openLessons.has(l.id)" class="subsections">
              <div v-if="sectionsCache[l.id]?.length">
                <div
                  v-for="s in sectionsCache[l.id]"
                  :key="s.id"
                  class="subsection"
                  :class="{ active: currentLessonId === l.id }"
                  @click="goToSection(l.id, s.id)"
                >{{ s.title }}</div>
              </div>
              <div v-else class="subsection loading">加载中...</div>
            </div>
          </div>
        </div>
      </nav>

      <!-- 底部功能入口：二级菜单，点击「工具」展开/收起 -->
      <div ref="toolsRef" class="tools">
        <button class="tools-toggle" :aria-expanded="toolsOpen" @click="toolsOpen = !toolsOpen">
          工具 <span class="tools-arrow">{{ toolsOpen ? '▴' : '▾' }}</span>
        </button>
        <Transition name="tools-pop">
          <div v-if="toolsOpen" class="tools-popup">
            <template v-for="t in tools" :key="t.to ?? t.href">
              <a
                v-if="t.external"
                :href="t.href"
                target="_blank"
                rel="noopener"
                class="tool-item"
                :class="{ 'tool-desktop': t.external }"
                @click="closeMenu"
              >
                <span>{{ t.icon }}</span>
                <span>{{ t.label }}</span>
              </a>
              <RouterLink v-else :to="t.to!" class="tool-item" @click="closeMenu">
                <span>{{ t.icon }}</span>
                <span>{{ t.label }}</span>
              </RouterLink>
            </template>
          </div>
        </Transition>
      </div>
    </aside>

    <!-- 桌面端深色模式切换（固定右上角，不放导航栏） -->
    <button
      class="theme-fab"
      :title="theme === 'dark' ? '切换到浅色模式' : '切换到深色模式'"
      aria-label="切换深浅色模式"
      @click="toggleTheme"
    >
      {{ theme === 'dark' ? '☀️' : '🌙' }}
    </button>

    <!-- 右侧内容区（body 滚动，浏览器原生恢复滚动位置） -->
    <div class="main">
      <RouterView />
    </div>
  </div>
</template>

<style scoped>
/* 布局：body 作为滚动容器（浏览器原生滚动恢复），侧边栏 fixed 固定 */
.layout { min-height: 100vh; min-height: 100dvh; }

/* 移动端顶栏（默认隐藏，≤900px 显示） */
.topbar {
  display: none;
  position: fixed;
  top: 0; left: 0; right: 0;
  height: var(--topbar-h);
  align-items: center;
  gap: 10px;
  padding: 0 12px;
  background: var(--bg-card);
  border-bottom: 1px solid var(--border);
  z-index: 20;
}
.menu-btn {
  border: none; background: none;
  font-size: 20px; line-height: 1;
  color: var(--text-1);
  width: 40px; height: 40px;
  display: flex; align-items: center; justify-content: center;
  border-radius: var(--radius-sm);
  cursor: pointer;
}
.menu-btn:active { background: var(--bg-hover); }
.theme-btn {
  border: none; background: none;
  font-size: 18px; line-height: 1;
  width: 40px; height: 40px;
  display: flex; align-items: center; justify-content: center;
  border-radius: var(--radius-sm);
  cursor: pointer;
  flex-shrink: 0;
}
.theme-btn:active { background: var(--bg-hover); }

/* 桌面端深色模式切换（固定右上角） */
.theme-fab {
  position: fixed;
  top: 12px; right: 16px;
  z-index: 45;
  width: 36px; height: 36px;
  border: 1px solid var(--border-strong);
  border-radius: 50%;
  background: var(--bg-card);
  font-size: 16px;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer;
  box-shadow: var(--shadow-md);
}
.theme-fab:hover { border-color: var(--primary); }

.topbar-brand { display: flex; }
.topbar-title {
  flex: 1;
  font-size: 14px; font-weight: 600; color: var(--text-1);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}

/* 抽屉遮罩（移动端） */
.drawer-mask {
  position: fixed; inset: 0;
  background: rgba(15, 20, 32, 0.45);
  z-index: 25;
}

/* 侧边栏：fixed 固定（body 滚动时保持原位） */
.sidebar {
  position: fixed;
  top: 0; bottom: 0; left: 0;
  width: var(--sidebar-w);
  z-index: 30;
  background: var(--bg-card);
  border-right: 1px solid var(--border);
  display: flex; flex-direction: column;
}
.brand {
  display: flex; align-items: center; gap: 10px;
  padding: 16px 20px; font-weight: 700; font-size: 16px;
  color: var(--text-1); border-bottom: 1px solid var(--border);
}
.brand:hover { color: var(--text-1); }
.brand-mark {
  width: 30px; height: 30px; border-radius: 8px;
  background: var(--primary); color: #fff;
  display: flex; align-items: center; justify-content: center;
  font-size: 16px; font-weight: 700;
}

.toc-label { font-size: 12px; color: var(--text-3); font-weight: 600; padding: 12px 20px 6px; letter-spacing: 0.5px; }
.toc-status { padding: 8px 20px; color: var(--text-3); font-size: 13px; }

.toc-search { padding: 0 12px 8px; }
.toc-search input {
  width: 100%;
  padding: 7px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-page);
  color: var(--text-1);
  font-size: 13px;
}
.toc-search input:focus { outline: none; border-color: var(--primary); }

.toc { flex: 1; overflow-y: auto; padding: 0 8px 12px; }

.volume { margin-bottom: 4px; }
.volume-head {
  display: flex; align-items: center; gap: 6px;
  padding: 7px 10px; cursor: pointer; border-radius: var(--radius-sm);
  transition: background 0.12s;
}
.volume-head:hover { background: var(--bg-hover); }
.volume-title { font-weight: 700; color: var(--primary); font-size: 13px; flex-shrink: 0; }
.volume-name { font-size: 13px; color: var(--text-1); font-weight: 600; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.volume-head .badge { font-size: 10px; padding: 1px 6px; flex-shrink: 0; }

.chapter-head {
  display: flex; align-items: center; gap: 6px;
  padding: 5px 10px 5px 20px; border-radius: var(--radius-sm);
  cursor: pointer; transition: background 0.12s;
}
.chapter-head:hover { background: var(--bg-hover); }
.chapter-head.active { background: var(--bg-active); }
.chapter-icon { font-size: 10px; color: var(--text-3); width: 12px; text-align: center; flex-shrink: 0; }
.chapter-title { font-size: 13px; color: var(--text-2); }
.chapter-title.done { color: var(--success); }
.chapter-head.active .chapter-title { color: var(--primary); font-weight: 600; }

.subsections { padding-left: 32px; }
.subsection {
  padding: 4px 10px; font-size: 12.5px; color: var(--text-3);
  cursor: pointer; border-radius: var(--radius-sm);
  transition: all 0.12s;
}
.subsection:hover { color: var(--primary); background: var(--bg-hover); }
.subsection.active { color: var(--primary); background: var(--bg-active); }
.subsection.loading { cursor: default; }

/* 底部工具（二级菜单：悬停/点击浮出面板） */
.tools { position: relative; border-top: 1px solid var(--border); padding: 8px; }
.tools-toggle {
  width: 100%;
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 12px;
  border: none; background: none;
  color: var(--text-3); font-size: 12px; font-weight: 600;
  cursor: pointer; font-family: inherit;
  border-radius: var(--radius-sm);
  transition: background 0.12s;
}
.tools-toggle:hover { background: var(--bg-hover); color: var(--text-1); }
.tools-arrow { font-size: 10px; }
.tools-popup {
  position: absolute;
  left: 0;
  right: 0;
  bottom: calc(100% + 8px); /* 向上弹出（工具条上方） */
  min-width: 190px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  padding: 6px;
  z-index: 60;
}
.tools-pop-enter-active, .tools-pop-leave-active { transition: opacity 0.15s, transform 0.15s; }
.tools-pop-enter-from, .tools-pop-leave-to { opacity: 0; transform: translateY(6px); }
.tool-item {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 12px; border-radius: var(--radius-sm);
  color: var(--text-2); font-size: 13px; transition: all 0.12s;
}
.tool-item:hover { background: var(--bg-hover); color: var(--text-1); }
.tool-item.router-link-active { background: var(--bg-active); color: var(--primary); font-weight: 600; }

/* 内容区（body 滚动，浏览器原生恢复） */
.main {
  margin-left: var(--sidebar-w);
  padding: 32px 40px 64px;
}

/* ---------- 移动端适配（≤900px） ---------- */
@media (max-width: 900px) {
  .topbar { display: flex; }

  .sidebar {
    transform: translateX(-100%);
    transition: transform 0.25s ease;
    box-shadow: var(--shadow-lg);
  }
  .sidebar.open { transform: translateX(0); }

  .main {
    margin-left: 0;
    padding: calc(var(--topbar-h) + 12px) 16px 84px;
  }

  /* 目录触控目标加大 */
  .chapter-head { padding: 9px 10px 9px 20px; }
  .subsection { padding: 8px 10px; }
  .tool-item { padding: 9px 12px; }

  /* 移动端隐藏指向 localhost 的外链工具（手机上无意义） */
  .tool-desktop { display: none; }

  /* 移动端隐藏右上角深色按钮（顶栏已有） */
  .theme-fab { display: none; }
}
</style>
