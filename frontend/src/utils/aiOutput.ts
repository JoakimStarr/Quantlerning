/** AI 输出归一化工具 */

/** 剥掉外层代码围栏：模型把整段 Markdown 包在 ```…``` 里时会整块显示为代码框。
 * 仅当围栏语言为空或 markdown/md 且内部无嵌套围栏时才剥掉，其余保留原样。 */
export function unwrapOuterFence(content: string): string {
  const m = content.trim().match(/^```[ \t]*([^\r\n]*)\r?\n([\s\S]*?)\r?\n```[ \t]*$/)
  if (!m) return content
  const lang = m[1].trim().toLowerCase()
  if ((lang && lang !== 'markdown' && lang !== 'md') || m[2].includes('```')) return content
  return m[2].trim()
}