import type { InjectionKey } from 'vue'

// 「问 AI」注入键：LessonView 提供（调 AiAskPanel.ask 预填问题），
// 深层组件（如 VizBlock 图表问 AI、CodeSandbox 代码问 AI）注入后直接触发课程 AI 追问面板。
// 第二个参数 context 为附加上下文（如沙箱代码与运行结果），仅注入下一次发送，不进聊天历史。
export const ASK_AI_KEY: InjectionKey<(text: string, context?: string) => void> = Symbol('askAi')
