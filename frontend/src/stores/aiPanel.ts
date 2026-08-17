import { reactive } from 'vue'

// AI 面板分栏状态：面板展开且屏幕够宽时，正文与面板分割剩余空间（可拖拽分隔条调整）。
// AiAskPanel 写入，App.vue 据此给 .main 让位（共享单例，无需跨层 props）。
export const aiPanelLayout = reactive({
  split: false,
  dragging: false, // 拖拽分隔条期间：正文/面板禁用过渡，跟随光标实时更新
  width: 440, // 分栏时面板宽度（px），用户可拖拽调整并持久化
})
