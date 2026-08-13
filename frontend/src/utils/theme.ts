import { ref } from 'vue'

// ============================================
// 深色模式：优先级 用户手动选择(ql:theme) > 系统偏好(prefers-color-scheme)
// main.ts 在挂载前调用 initTheme() 避免首屏闪烁；App.vue 用 useTheme() 切换。
// ============================================

const KEY = 'ql:theme'

// 挂载前初始化 <html data-theme>（用户选择或跟随系统）
export function initTheme(): void {
  if (typeof document === 'undefined') return
  let stored: string | null = null
  try {
    stored = localStorage.getItem(KEY)
  } catch {
    // 存储不可用：忽略
  }
  if (stored === 'dark' || stored === 'light') {
    document.documentElement.setAttribute('data-theme', stored)
  } else if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
    document.documentElement.setAttribute('data-theme', 'dark')
  }
}

// 组件内使用：未手动设置时跟随系统偏好，用户一旦切换即固定
export function useTheme() {
  const theme = ref<'light' | 'dark'>(
    document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light',
  )

  let mql: MediaQueryList | null = null
  let followSystem = false
  try {
    followSystem = !localStorage.getItem(KEY)
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
    applySystemTheme() // 与 initTheme 保持一致（如系统在挂载后变化）
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
      localStorage.setItem(KEY, theme.value)
    } catch {
      // 存储不可用：忽略
    }
  }

  return { theme, toggleTheme }
}