import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '@/views/HomeView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: HomeView },
    { path: '/phase/:phase', name: 'phase', component: () => import('@/views/PhaseView.vue') },
    { path: '/lesson/:id', name: 'lesson', component: () => import('@/views/LessonView.vue') },
    { path: '/lab', name: 'lab', component: () => import('@/views/LabView.vue') },
    { path: '/cheatsheet', name: 'cheatsheet', component: () => import('@/views/CheatsheetView.vue') },
    { path: '/data-browser', name: 'data-browser', component: () => import('@/views/DataBrowserView.vue') },
    { path: '/factors', name: 'factors', component: () => import('@/views/FactorsView.vue') },
    { path: '/stats', name: 'stats', component: () => import('@/views/StatsView.vue') },
    { path: '/settings', name: 'settings', component: () => import('@/views/SettingsView.vue') },
  ],
  // 浏览器原生滚动语义：前进/新导航回顶，后退/前进（popstate）恢复浏览器保存的位置
  scrollBehavior(_to, _from, savedPosition) {
    if (savedPosition) {
      return savedPosition
    }
    return { top: 0 }
  },
})

export default router
