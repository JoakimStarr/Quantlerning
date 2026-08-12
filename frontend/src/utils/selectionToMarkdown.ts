/**
 * 把当前文本选区转成 Markdown 文本，其中的公式还原为 $...$ LaTeX 源码。
 *
 * 课程正文的公式由 katex 渲染成复杂 HTML，直接 getSelection().toString()
 * 得到的是渲染后的字符而非 LaTeX（还常是乱码）。每个公式根元素带
 * data-latex 属性（见 markdownMath.ts 的 renderMath），这里按选区在
 * DOM 中的顺序重建文本，遇到公式就用 $...$ 替换其源码。
 */

export function getSelectionMarkdown(): string {
  const sel = window.getSelection()
  if (!sel || sel.isCollapsed || sel.rangeCount === 0) return ''
  const range = sel.getRangeAt(0)

  // 选区完全落在某个公式内部：直接返回该公式的 LaTeX 源码
  const anc = range.commonAncestorContainer
  const katexRoot =
    anc.nodeType === Node.ELEMENT_NODE
      ? (anc as HTMLElement).closest<HTMLElement>('.katex[data-latex]')
      : anc.parentElement?.closest<HTMLElement>('.katex[data-latex]')
  if (katexRoot?.dataset.latex) return `$${katexRoot.dataset.latex}$`

  const parts: string[] = []
  collect(range, anc, parts)
  return parts.join('').replace(/\n{3,}/g, '\n\n').trim()
}

/** 按文档序收集选区内的文本节点与公式，块级元素之间补换行 */
function collect(range: Range, node: Node, parts: string[]) {
  if (node.nodeType === Node.TEXT_NODE) {
    if (range.intersectsNode(node)) parts.push(node.textContent ?? '')
    return
  }
  const el = node as HTMLElement
  const latex = el.dataset.latex
  if (latex !== undefined) {
    if (range.intersectsNode(el)) parts.push(`$${latex}$`)
    return
  }
  if (el.closest('.katex')) return // 公式内部节点：跳过（公式已整体取源码）
  if (!range.intersectsNode(el)) return // 与选区无交集：整棵子树跳过

  const isBlock = ['P', 'DIV', 'LI', 'PRE', 'BLOCKQUOTE', 'TR', 'TABLE'].includes(el.tagName)
  if (isBlock && parts.length && !parts[parts.length - 1].endsWith('\n')) parts.push('\n')
  for (const child of Array.from(el.childNodes)) collect(range, child, parts)
  if (el.tagName === 'BR') parts.push('\n')
}
