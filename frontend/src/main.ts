import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import './styles/main.css'

// 使用浏览器原生滚动位置恢复（文档滚动容器；配合 layout 改为 body 滚动）
// 显式设为 auto（部分站点会设为 manual 禁止恢复，这里需要原生行为）
if ('scrollRestoration' in history) {
  history.scrollRestoration = 'auto'
}

// 深色模式初始化（在 Vue 挂载前设置，避免首屏闪烁）
// 优先级：用户手动选择（ql:theme）> 系统偏好（prefers-color-scheme）
try {
  const stored = localStorage.getItem('ql:theme')
  if (stored === 'dark' || stored === 'light') {
    document.documentElement.setAttribute('data-theme', stored)
  } else if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
    document.documentElement.setAttribute('data-theme', 'dark')
  }
} catch {
  // 存储不可用：忽略
}

createApp(App).use(router).mount('#app')
