import type { InjectionKey } from 'vue'

// 「问 AI」注入键：LessonView 提供（调 AiAskPanel.ask 预填问题），
// 深层组件（如 VizBlock 图表问 AI）注入后直接触发课程 AI 追问面板。
export const ASK_AI_KEY: InjectionKey<(text: string) => void> = Symbol('askAi')
