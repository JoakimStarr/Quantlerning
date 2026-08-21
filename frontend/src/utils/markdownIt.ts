/**
 * markdown-it 统一工厂：全站共用同一套渲染配置（数学插件 + 代码块语法高亮）。
 *
 * 替换各组件各自 `new MarkdownIt(...)` 的写法，保证：
 * 1. 渲染行为一致（html:false / linkify:true / mathPlugin）
 * 2. 代码块统一走 highlight.js 语法高亮（python/bash/javascript/json 按需注册）
 *
 * highlight.js 用 core + 按需语言，避免全量打包；token 颜色在 main.css
 * 用设计变量定义（.hljs-* 类），深浅色自动自适应。
 */
import MarkdownIt from 'markdown-it'
import type { MarkdownIt as MarkdownItType, MarkdownItOptions } from 'markdown-it'
import hljs from 'highlight.js/lib/core'
import python from 'highlight.js/lib/languages/python'
import bash from 'highlight.js/lib/languages/bash'
import javascript from 'highlight.js/lib/languages/javascript'
import json from 'highlight.js/lib/languages/json'
import mathPlugin from './markdownMath'

hljs.registerLanguage('python', python)
hljs.registerLanguage('bash', bash)
hljs.registerLanguage('javascript', javascript)
hljs.registerLanguage('json', json)

/**
 * 代码块高亮回调：有注册语言则高亮；否则返回空串，交给 markdown-it 默认
 * 兜底逻辑（转义原文本 + 原样包裹），避免为取 escapeHtml 而 new 一个 MarkdownIt 实例。
 */
function highlightCode(str: string, lang: string): string {
  if (lang && hljs.getLanguage(lang)) {
    return `<pre class="hljs"><code>${hljs.highlight(str, { language: lang }).value}</code></pre>`
  }
  return ''
}

/**
 * 创建统一配置的 markdown-it 实例。
 * @param extra 额外覆盖的 options（如 MarkdownRenderer 需要 breaks:false）
 */
export function createMarkdown(extra: MarkdownItOptions = {}): MarkdownItType {
  return new MarkdownIt({
    html: false,
    linkify: true,
    highlight: highlightCode,
    ...extra,
  }).use(mathPlugin, { throwOnError: false, errorColor: '#dc2626' })
}
