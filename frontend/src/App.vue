<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch, type Component } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import {
  BarChart3, BookMarked, Check, ChevronDown, ChevronRight, ChevronUp,
  ClipboardList, Dna, FlaskConical, Menu, Microscope, Moon, Settings, Sun, TrendingUp,
} from 'lucide-vue-next'
import { fetchCourses, fetchLesson } from '@/api'
import { isCompleted } from '@/stores/progress'
import { aiPanelLayout } from '@/stores/aiPanel'
import { chapterLabel, PHASE_STATUS as phaseStatus } from '@/utils/chapter'
import { useTheme } from '@/utils/theme'

const route = useRoute()
const router = useRouter()

// 记忆最近访问的课程/页面：路由变化时写入 localStorage，落地首页时显示「继续上次学习」
// 首页本身不写入，避免回首页后 lastPath 被覆盖成 '/' 导致 resume 卡片失效
const LAST_PATH_KEY = 'ql:lastPath'
watch(
  () => route.fullPath,
  (p) => {
    if (!p || p === '/') return
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
// 顶栏「更多」下拉（点击展开，点击外部收起）
const moreOpen = ref(false)
const moreRef = ref<HTMLElement | null>(null)
// 点击菜单外部时收起
function onDocClick(e: MouseEvent) {
  if (toolsOpen.value && toolsRef.value && !toolsRef.value.contains(e.target as Node)) {
    toolsOpen.value = false
  }
  if (moreOpen.value && moreRef.value && !moreRef.value.contains(e.target as Node)) {
    moreOpen.value = false
  }
}
onMounted(() => document.addEventListener('click', onDocClick))
// 路由变化时收起弹层（导航后不再遮挡内容）
watch(
  () => route.fullPath,
  () => {
    toolsOpen.value = false
    moreOpen.value = false
  },
)

// ---------- 深色模式 ----------
const { theme, toggleTheme } = useTheme()

// 顶栏当前课程名（移动端显示）
const currentLessonTitle = computed(() => {
  if (!currentLessonId.value) return ''
  for (const v of volumes.value) {
    const l = v.lessons?.find((x: any) => x.id === currentLessonId.value)
    if (l) return l.title
  }
  return ''
})

// 顶栏「课程」导航激活态：课程页 / 阶段页
const isCoursePath = computed(
  () => route.path.startsWith('/lesson/') || route.path.startsWith('/phase/'),
)

// 首页：隐藏左侧课程目录（首页自带课程地图，无需重复目录）
const isHome = computed(() => route.path === '/')

// 顶栏主导航：核心四项（桌面端全站导航，侧边栏只留课程目录）
const topNav = computed(() => [
  { label: '首页', to: '/', active: route.path === '/' },
  { label: '课程', to: '/phase/0', active: isCoursePath.value },
  { label: '数据', to: '/data-browser', active: route.path === '/data-browser' },
  { label: '设置', to: '/settings', active: route.path === '/settings' },
])

// 顶栏「更多」下拉：次要工具页 + 外链 QuantLab
const moreNav = computed(() => [
  { label: '可视化实验室', to: '/lab', active: route.path === '/lab' },
  { label: '速查表', to: '/cheatsheet', active: route.path === '/cheatsheet' },
  { label: '因子库', to: '/factors', active: route.path === '/factors' },
  { label: '学习统计', to: '/stats', active: route.path === '/stats' },
])
const isMoreActive = computed(() => moreNav.value.some((n) => n.active))

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

// 点击卷头：跳转该卷首页
function goVolume(v: any) {
  if (v.lessons.length) {
    closeMenu()
    router.push(`/phase/${v.phase}`)
  }
}

// 键盘激活（Enter/空格触发），保证目录可用 Tab 操作
function keyActivate(e: KeyboardEvent, fn: () => void) {
  e.preventDefault()
  fn()
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

// 底部功能入口
const tools: { to?: string; href?: string; label: string; icon: Component; external?: boolean }[] = [
  { to: '/lab', label: '可视化实验室', icon: FlaskConical },
  { to: '/cheatsheet', label: '速查表', icon: ClipboardList },
  { to: '/data-browser', label: '数据浏览器', icon: BarChart3 },
  { to: '/factors', label: '因子库', icon: Dna },
  { to: '/stats', label: '学习统计', icon: TrendingUp },
  { to: '/settings', label: '设置', icon: Settings },
  { href: 'http://localhost:3000', label: 'QuantLab 回测', icon: Microscope, external: true },
]
</script>

<template>
  <div class="layout">
    <!-- 顶部导航栏（借鉴设计包 lesson.html）：品牌 + 导航 + 操作区 -->
    <header class="app-topbar">
      <button v-if="!isHome" class="menu-btn" aria-label="切换目录" @click="menuOpen = !menuOpen"><Menu :size="20" /></button>
      <RouterLink to="/" class="topbar-brand" @click="closeMenu">
        <img src="/icon.svg" class="brand-mark" alt="Quantlerning" />
        <span class="brand-name"><span class="q">Quant</span>lerning</span>
      </RouterLink>
      <nav class="topbar-nav" aria-label="主导航">
        <RouterLink
          v-for="n in topNav"
          :key="n.to"
          :to="n.to"
          class="nav-link"
          :class="{ active: n.active }"
        >{{ n.label }}</RouterLink>

        <!-- 更多下拉：次要工具页 + 外链 -->
        <div ref="moreRef" class="more">
          <button
            class="nav-link more-btn"
            :class="{ active: isMoreActive }"
            :aria-expanded="moreOpen"
            aria-haspopup="menu"
            @click="moreOpen = !moreOpen"
          >
            更多
            <ChevronDown :size="13" :class="{ up: moreOpen }" />
          </button>
          <Transition name="more-pop">
            <div v-if="moreOpen" class="more-pop" role="menu">
              <RouterLink
                v-for="n in moreNav"
                :key="n.to"
                :to="n.to"
                class="more-item"
                :class="{ active: n.active }"
                role="menuitem"
                @click="moreOpen = false"
              >{{ n.label }}</RouterLink>
            </div>
          </Transition>
        </div>
      </nav>
      <span class="topbar-title">{{ currentLessonTitle || 'Quantlerning' }}</span>
      <div class="topbar-actions">
        <a class="icon-btn" href="http://localhost:3000" target="_blank" rel="noopener" title="QuantLab 回测（外链）" aria-label="QuantLab 回测">
          <Microscope :size="18" />
        </a>
        <button class="theme-btn" :title="theme === 'dark' ? '切换到浅色模式' : '切换到深色模式'" aria-label="切换深浅色模式" @click="toggleTheme">
          <Transition name="theme-icon" mode="out-in">
            <Sun v-if="theme === 'dark'" key="sun" :size="18" />
            <Moon v-else key="moon" :size="18" />
          </Transition>
        </button>
      </div>
    </header>

    <!-- 抽屉遮罩（移动端） -->
    <div v-if="menuOpen" class="drawer-mask" @click="closeMenu"></div>

    <!-- 左侧：书的目录（首页不显示，首页自带课程地图） -->
    <aside v-if="!isHome" class="sidebar" :class="{ open: menuOpen }">
      <div class="toc-label"><BookMarked :size="13" class="toc-icon" /> 目录</div>

      <div class="toc-search">
        <input v-model="searchQuery" type="search" placeholder="搜索课程…" spellcheck="false" />
      </div>

      <nav class="toc">
        <div v-if="!loaded" class="toc-status">加载目录...</div>
        <div v-else-if="filteredVolumes.length === 0" class="toc-status">无匹配课程</div>
        <div v-for="v in filteredVolumes" :key="v.phase" class="volume">
          <!-- 卷头 -->
          <div
            class="volume-head"
            role="button"
            tabindex="0"
            :aria-expanded="v.lessons.length > 0"
            @click="goVolume(v)"
            @keydown.enter="keyActivate($event, () => goVolume(v))"
            @keydown.space.prevent="keyActivate($event, () => goVolume(v))"
          >
            <span class="volume-title">{{ chapterLabel(v.phase) }}</span>
            <span class="volume-name">{{ v.title }}</span>
            <span v-if="v.status !== 'planned' || v.lessons.length" :class="phaseStatus[v.status]?.cls || 'badge'">{{ phaseStatus[v.status]?.label || v.status }}</span>
          </div>

          <!-- 卷下的章（课程） -->
          <div v-for="l in v.lessons" :key="l.id" class="chapter">
            <div
              class="chapter-head"
              :class="{ active: currentLessonId === l.id }"
              role="button"
              tabindex="0"
              :aria-expanded="openLessons.has(l.id)"
              @click="toggleLesson(l)"
              @keydown.enter="keyActivate($event, () => toggleLesson(l))"
              @keydown.space.prevent="keyActivate($event, () => toggleLesson(l))"
            >
              <span class="chapter-icon">
                <ChevronDown v-if="openLessons.has(l.id)" :size="12" />
                <Check v-else-if="isCompleted(l.id)" :size="12" />
                <ChevronRight v-else :size="12" />
              </span>
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
                  role="link"
                  tabindex="0"
                  @click="goToSection(l.id, s.id)"
                  @keydown.enter="keyActivate($event, () => goToSection(l.id, s.id))"
                  @keydown.space.prevent="keyActivate($event, () => goToSection(l.id, s.id))"
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
          工具 <span class="tools-arrow"><ChevronUp v-if="toolsOpen" :size="11" /><ChevronDown v-else :size="11" /></span>
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
                @click="closeMenu"
              >
                <component :is="t.icon" :size="15" />
                <span>{{ t.label }}</span>
              </a>
              <RouterLink v-else :to="t.to!" class="tool-item" @click="closeMenu">
                <component :is="t.icon" :size="15" />
                <span>{{ t.label }}</span>
              </RouterLink>
            </template>
          </div>
        </Transition>
      </div>
    </aside>

    <!-- 右侧内容区（body 滚动，浏览器原生恢复滚动位置） -->
    <!-- ai-split：AI 面板分栏时正文与面板分割剩余空间（宽度由分隔条拖拽驱动） -->
    <div
      class="main"
      :class="{ 'ai-split': aiPanelLayout.split, 'ai-dragging': aiPanelLayout.dragging, 'no-sidebar': isHome }"
      :style="aiPanelLayout.split ? { '--ai-panel-w': `${aiPanelLayout.width}px` } : undefined"
    >
      <RouterView />
    </div>
  </div>
</template>

<style scoped>
/* 布局：body 作为滚动容器（浏览器原生滚动恢复），侧边栏 fixed 固定 */
.layout { min-height: 100vh; min-height: 100dvh; }

/* 顶部导航栏（借鉴设计包 lesson.html 的 topbar）：
   全屏 sticky 显示，毛玻璃背景；品牌 + 导航 + 操作区 */
.app-topbar {
  position: sticky;
  top: 0; left: 0; right: 0;
  z-index: 40;
  height: var(--topbar-h);
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 16px;
  background: color-mix(in srgb, var(--bg-page) 85%, transparent);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border);
}
.app-topbar .topbar-brand {
  display: flex; align-items: center; gap: 10px;
  font-size: 17px; font-weight: 700; letter-spacing: -0.01em;
  color: var(--text-1);
  flex-shrink: 0;
}
.app-topbar .topbar-brand .brand-mark { width: 30px; height: 30px; border-radius: 8px; }
.app-topbar .topbar-brand .brand-name .q { color: var(--primary); }
.app-topbar .topbar-nav { display: flex; gap: 4px; margin-left: 4px; }
.app-topbar .nav-link {
  padding: 7px 13px;
  border-radius: var(--radius-sm);
  color: var(--text-2); font-size: 13px; font-weight: 600;
  white-space: nowrap;
  transition: background 0.12s, color 0.12s;
}
.app-topbar .nav-link:hover { background: var(--bg-hover); color: var(--text-1); }
.app-topbar .nav-link.active { background: var(--primary-soft); color: var(--primary); }
.app-topbar .topbar-title {
  flex: 1;
  font-size: 14px; font-weight: 600; color: var(--text-1);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.app-topbar .topbar-actions { display: flex; align-items: center; gap: 6px; margin-left: auto; flex-shrink: 0; }
.app-topbar .icon-btn {
  border: none; background: none;
  width: 40px; height: 40px;
  display: flex; align-items: center; justify-content: center;
  border-radius: var(--radius-sm);
  color: var(--text-2); cursor: pointer;
  flex-shrink: 0;
  transition: background 0.12s, color 0.12s;
}
.app-topbar .icon-btn:hover { background: var(--bg-hover); color: var(--text-1); }

/* 「更多」下拉菜单 */
.app-topbar .more { position: relative; }
.app-topbar .more-btn {
  display: inline-flex; align-items: center; gap: 3px;
  border: none; background: transparent;
  cursor: pointer; font-family: inherit;
}
.app-topbar .more-btn svg { transition: transform 0.15s; }
.app-topbar .more-btn svg.up { transform: rotate(180deg); }
.more-pop {
  position: absolute;
  top: calc(100% + 8px);
  left: 0;
  min-width: 176px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 6px;
  z-index: 60;
}
.more-item {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 12px; border-radius: var(--radius-sm);
  color: var(--text-2); font-size: 13px; font-weight: 500;
  transition: background 0.12s, color 0.12s;
}
.more-item:hover { background: var(--bg-hover); color: var(--text-1); }
.more-item.active { background: var(--bg-active); color: var(--primary); font-weight: 600; }
.more-pop-enter-active, .more-pop-leave-active { transition: opacity 0.15s, transform 0.15s; }
.more-pop-enter-from, .more-pop-leave-to { opacity: 0; transform: translateY(6px); }

.menu-btn {
  border: none; background: none;
  font-size: 20px; line-height: 1;
  color: var(--text-1);
  width: 40px; height: 40px;
  display: flex; align-items: center; justify-content: center;
  border-radius: var(--radius-sm);
  cursor: pointer;
  flex-shrink: 0;
}
.menu-btn:active { background: var(--bg-hover); }
.theme-btn {
  border: none; background: none;
  font-size: 18px; line-height: 1;
  color: var(--text-2);
  width: 40px; height: 40px;
  display: flex; align-items: center; justify-content: center;
  border-radius: var(--radius-sm);
  cursor: pointer;
  flex-shrink: 0;
  transition: background 0.12s, color 0.12s;
}
.theme-btn:hover { background: var(--bg-hover); color: var(--text-1); }
.theme-btn:active { background: var(--bg-hover); }

/* 主题图标切换动效：旧图标淡出旋转、新图标淡入旋转，避免「啪」地硬换 */
.theme-icon-enter-active,
.theme-icon-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}
.theme-icon-enter-from {
  opacity: 0;
  transform: rotate(-70deg) scale(0.6);
}
.theme-icon-leave-to {
  opacity: 0;
  transform: rotate(70deg) scale(0.6);
}

/* 抽屉遮罩（移动端） */
.drawer-mask {
  position: fixed; inset: 0;
  background: rgba(15, 20, 32, 0.45);
  z-index: 25;
}

/* 侧边栏：fixed 固定，位于顶栏下方（body 滚动时保持原位） */
.sidebar {
  position: fixed;
  top: var(--topbar-h); bottom: 0; left: 0;
  width: var(--sidebar-w);
  z-index: 30;
  background: var(--bg-card);
  border-right: 1px solid var(--border);
  display: flex; flex-direction: column;
}
.brand-mark {
  width: 30px; height: 30px; border-radius: 8px;
  display: block;
  object-fit: contain;
  flex-shrink: 0;
}

.toc-label { font-size: 12px; color: var(--text-3); font-weight: 600; padding: 12px 20px 6px; letter-spacing: 0.5px; display: flex; align-items: center; gap: 6px; }
.toc-icon { flex-shrink: 0; }
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
  transition: margin-right 0.2s ease;
}

/* 首页：无左侧目录，正文占满全宽 */
.main.no-sidebar {
  margin-left: 0;
}

/* AI 面板分栏：正文让位给面板宽度（--ai-panel-w）+ 面板右侧边距 24px + 间隙 16px，
   余下空间全部留给正文——与面板共同分割剩余空间 */
.main.ai-split {
  margin-right: calc(var(--ai-panel-w, 440px) + 40px);
}
.main.ai-split.ai-dragging {
  transition: none; /* 拖拽分隔条期间实时跟随，禁用过渡 */
}

/* ---------- 桌面端（>900px）：顶栏显示导航与文字标，隐藏汉堡、当前课程与侧边栏工具菜单 ---------- */
@media (min-width: 901px) {
  .app-topbar .menu-btn { display: none; }
  .app-topbar .topbar-title { display: none; }
  .sidebar .tools { display: none; }
}

/* ---------- 移动端适配（≤900px） ---------- */
@media (max-width: 900px) {
  .app-topbar .brand-name { display: none; }
  .app-topbar .topbar-nav { display: none; }

  .sidebar {
    transform: translateX(-100%);
    transition: transform 0.25s ease;
    box-shadow: var(--shadow-lg);
  }
  .sidebar.open { transform: translateX(0); }

  .main {
    margin-left: 0;
    padding: 20px 16px 84px;
  }

  /* 目录触控目标加大 */
  .chapter-head { padding: 9px 10px 9px 20px; }
  .subsection { padding: 8px 10px; }
  .tool-item { padding: 9px 12px; }
}
</style>
