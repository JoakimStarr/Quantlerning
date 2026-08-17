import { reactive } from 'vue'

// AI 面板分栏状态：面板展开且屏幕够宽时，正文左移贴靠侧边栏、AI 面板独占右侧。
// AiAskPanel 写入，App.vue 据此给 .main 加右侧 margin（共享单例，无需跨层 props）。
export const aiPanelLayout = reactive({
  split: false,
})
