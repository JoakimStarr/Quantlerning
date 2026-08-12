// markdown-it-katex 无官方类型声明，补充声明
declare module 'markdown-it-katex' {
  import type MarkdownIt from 'markdown-it'
  const plugin: MarkdownIt.PluginWithOptions<{ throwOnError?: boolean; errorColor?: string }>
  export default plugin
}
