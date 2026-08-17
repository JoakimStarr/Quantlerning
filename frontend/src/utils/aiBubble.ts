import { createMarkdown } from './markdownIt'
import { unwrapOuterFence } from './aiOutput'

// 共享的 AI 输出渲染器：与课程正文同一套 markdown-it + katex，支持公式/代码。
// 供 AiAskPanel / ExerciseBlock / QuizBlock / 章节小结 / 错题复习等所有 AI 流式输出复用。
const bubbleMd = createMarkdown({ breaks: false })

/**
 * 渲染 AI 回答文本。
 * - 公式分隔符不统一（$$...$$、\(...\)、\[...\] 都可能出现），统一归一化为行内 $...$；
 * - trim 掉公式首尾空白，防止 $ 与空白相邻被识别为普通文本；
 * - 先剥掉外层代码围栏：模型把整段 Markdown 包在 ```…``` 里时会整块显示为代码框。
 */
export function renderAiBubble(content: string): string {
  const normalized = unwrapOuterFence(content)
    .replace(/\$\$([\s\S]+?)\$\$/g, (_, m: string) => `$${m.trim()}$`)
    .replace(/\\\[([\s\S]+?)\\\]/g, (_, m: string) => `$${m.trim()}$`)
    .replace(/\\\(([\s\S]+?)\\\)/g, (_, m: string) => `$${m.trim()}$`)
  return bubbleMd.render(normalized)
}
