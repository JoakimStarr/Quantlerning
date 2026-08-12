/**
 * markdown-it 数学渲染插件（基于 katex 0.18.4）。
 *
 * 替代过时的 markdown-it-katex@2.0.3（其内部嵌套 katex@0.6.0，
 * 不支持 \text{中文}、\xrightarrow、\binom 等，导致公式乱码/错位）。
 *
 * 支持：
 * - 行内公式  $...$
 * - 块级公式  $$...$$（支持多行，如 cases 环境）
 * - 转义美元符  \$ 不作为分隔符
 */
import katex from 'katex'

export interface MathOptions {
  throwOnError?: boolean
  errorColor?: string
}

type State = any

// 判断当前位置的 $ 是否可作为开/闭分隔符
// 参考 markdown-it-katex，并保持对金额场景（$5、$100）的容错：
// - 开：$ 后不能是空白（$ 开头接公式内容）
// - 闭：$ 前不能是空白；$ 后紧跟数字时不视为闭合（如 "$5 元"）
function isValidDelim(state: State, pos: number) {
  const prev = pos > 0 ? state.src.charCodeAt(pos - 1) : -1
  const next = pos + 1 <= state.posMax ? state.src.charCodeAt(pos + 1) : -1
  const isSpace = (c: number) => c === 0x20 || c === 0x09
  const isDigit = (c: number) => c >= 0x30 && c <= 0x39
  return {
    canOpen: !isSpace(next),
    canClose: !isSpace(prev) && !isDigit(next),
  }
}

/** 行内规则：$...$ */
function mathInline(state: State, silent: boolean) {
  if (state.src[state.pos] !== '$') return false

  const open = isValidDelim(state, state.pos)
  if (!open.canOpen) {
    if (!silent) state.pending += '$'
    state.pos += 1
    return true
  }

  const start = state.pos + 1
  let match = start
  while ((match = state.src.indexOf('$', match)) !== -1) {
    // 跳过转义的 $（前面是奇数个反斜杠）
    let back = match - 1
    while (state.src[back] === '\\') back -= 1
    if ((match - back) % 2 === 1) break // 未转义，作为闭合候选
    match += 1
  }

  // 没有闭合符：按普通字符处理
  if (match === -1) {
    if (!silent) state.pending += '$'
    state.pos = start
    return true
  }

  // 空内容 $$ 不解析
  if (match === start) {
    if (!silent) state.pending += '$$'
    state.pos = start + 1
    return true
  }

  const close = isValidDelim(state, match)
  if (!close.canClose) {
    if (!silent) state.pending += '$'
    state.pos = start
    return true
  }

  if (!silent) {
    const token = state.push('math_inline', 'math', 0)
    token.markup = '$'
    token.content = state.src.slice(start, match)
  }
  state.pos = match + 1
  return true
}

/** 块级规则：$$...$$（可跨行） */
function mathBlock(state: State, start: number, end: number, silent: boolean) {
  let pos = state.bMarks[start] + state.tShift[start]
  let max = state.eMarks[start]
  if (pos + 2 > max) return false
  if (state.src.slice(pos, pos + 2) !== '$$') return false

  pos += 2
  let firstLine = state.src.slice(pos, max)
  if (silent) return true

  let lastPos = -1
  let found = false
  // 单行：$$...$$
  if (firstLine.trim().slice(-2) === '$$') {
    firstLine = firstLine.trim().slice(0, -2)
    found = true
  }

  let next = start
  for (; !found; ) {
    next++
    if (next >= end) break
    pos = state.bMarks[next] + state.tShift[next]
    max = state.eMarks[next]
    // 缩进不增加的普通段落行，停止
    if (pos < max && state.tShift[next] < state.blkIndent) break
    const line = state.src.slice(pos, max)
    if (line.trim().slice(-2) === '$$') {
      lastPos = state.src.slice(0, max).lastIndexOf('$$')
      found = true
    }
  }

  state.line = next + 1
  const lastLine = found && lastPos >= 0 ? state.src.slice(pos, lastPos) : ''
  const content =
    (firstLine.trim() ? firstLine + '\n' : '') +
    state.getLines(start + 1, next, state.tShift[start], true) +
    (lastLine.trim() ? lastLine : '')

  const token = state.push('math_block', 'math', 0)
  token.block = true
  token.content = content
  token.map = [start, state.line]
  token.markup = '$$'
  return true
}

function renderMath(opts: MathOptions, displayMode: boolean, latex: string) {
  try {
    // 注入 data-latex：选中公式时能还原 LaTeX 源码（供「选中问 AI」等场景使用）
    const escaped = latex
      .replace(/&/g, '&amp;')
      .replace(/"/g, '&quot;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
    const html = katex.renderToString(latex, {
      throwOnError: opts.throwOnError ?? false,
      errorColor: opts.errorColor ?? '#dc2626',
      displayMode,
      trust: false,
      strict: false,
    })
    return html.replace(/<span class="katex">/, `<span class="katex" data-latex="${escaped}">`)
  } catch {
    // 渲染失败时回退原始文本，避免页面崩溃
    return latex
  }
}

type MarkdownItInstance = import('markdown-it').MarkdownIt

export default function mathPlugin(md: MarkdownItInstance, opts: MathOptions = {}) {
  md.inline.ruler.after('escape', 'math_inline', mathInline as any)
  md.block.ruler.after('blockquote', 'math_block', mathBlock as any, {
    alt: ['paragraph', 'reference', 'blockquote', 'list'],
  })
  md.renderer.rules.math_inline = ((tokens: any, idx: number) => renderMath(opts, false, tokens[idx].content)) as any
  md.renderer.rules.math_block = ((tokens: any, idx: number) => `<p>${renderMath(opts, true, tokens[idx].content)}</p>\n`) as any
}
