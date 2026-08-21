import { computed, ref } from 'vue'

// ============================================
// 图表主题：ECharts 走 Canvas，无法用 CSS 变量，
// 这里维护一份随 <html data-theme> 变化的响应式色板，
// 供所有模拟器共享，保证深浅色模式下图表与页面风格一致。
// ============================================

export interface ChartColors {
  primary: string
  primaryHover: string
  primaryDeep: string
  danger: string
  success: string
  warning: string
  violet: string
  cyan: string
  teal: string
  slate: string
  slateStrong: string
  ink: string // 主文字（近黑/近白）
  text: string // 坐标轴/图例/次要文字
  textWeak: string
  grid: string // 网格分隔线
  tooltipBg: string
  tooltipBorder: string
}

// 浅色（系列色对齐设计包 --chart-1..6 与 main.css 语义色）
const LIGHT: ChartColors = {
  primary: '#2f6ae8', // ≈ chart-1（主蓝，与 --primary 一致）
  primaryHover: '#2456d1',
  primaryDeep: '#1e3a8a', // 对齐 --primary-deep
  danger: '#e03131', // chart-5（红/涨）
  success: '#16a34a',
  warning: '#d97706', // chart-4（琥珀）
  violet: '#7c3aed', // chart-2（紫）
  cyan: '#0891b2', // chart-3（青）
  teal: '#0d9488',
  slate: '#94a3b8',
  slateStrong: '#64748b',
  ink: '#242936',
  text: '#5f6873',
  textWeak: '#868e9b',
  grid: '#e1e3e8',
  tooltipBg: '#ffffff',
  tooltipBorder: '#cfd2d9',
}

const DARK: ChartColors = {
  primary: '#5c93f5',
  primaryHover: '#7aa7ff',
  primaryDeep: '#172554',
  danger: '#f87171',
  success: '#4ade80',
  warning: '#fbbf24',
  violet: '#a78bfa',
  cyan: '#22d3ee',
  teal: '#2dd4bf',
  slate: '#8f9db3',
  slateStrong: '#7d8899',
  ink: '#e7eaf1',
  text: '#a7b0c0',
  textWeak: '#6d7688',
  grid: '#2b3448',
  tooltipBg: '#161d2e',
  tooltipBorder: '#3c4760',
}

// 当前主题（跟随 <html data-theme>）
const theme = ref<'light' | 'dark'>(
  typeof document !== 'undefined' &&
    document.documentElement.getAttribute('data-theme') === 'dark'
    ? 'dark'
    : 'light',
)

// 监听 html 上 data-theme 变化（main.ts 初始化 / App.vue 切换都会改它）
if (typeof window !== 'undefined' && typeof MutationObserver !== 'undefined') {
  const observer = new MutationObserver(() => {
    theme.value =
      document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light'
  })
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['data-theme'],
  })
}

export const chartColors = computed<ChartColors>(() =>
  theme.value === 'dark' ? DARK : LIGHT,
)

// 便捷引用：组件内 `C.value.primary` 即可拿到当前主题色
export const C = chartColors

// 十六进制色 → 带透明度的 rgba（用于 areaStyle / 阴影填充）
export function withAlpha(hex: string, a: number): string {
  const h = hex.replace('#', '')
  const r = parseInt(h.slice(0, 2), 16)
  const g = parseInt(h.slice(2, 4), 16)
  const b = parseInt(h.slice(4, 6), 16)
  return `rgba(${r}, ${g}, ${b}, ${a})`
}

// 给 ECharts option 注入主题化的文字/网格/提示框颜色。
// 只在组件已声明对应配置时补充（不改变原有交互行为），
// 坐标轴标签、图例、tooltip、分隔线在深浅色下都可读。
export function withChartTheme<T extends Record<string, any>>(option: T): T {
  const c = chartColors.value
  const out: Record<string, any> = {
    ...option,
    textStyle: { color: c.text, ...(option.textStyle ?? {}) },
  }

  if (option.axisPointer) {
    out.axisPointer = {
      ...option.axisPointer,
      label: {
        color: '#fff',
        backgroundColor: c.text,
        ...(option.axisPointer.label ?? {}),
      },
    }
  }

  if (option.tooltip) {
    out.tooltip = {
      backgroundColor: c.tooltipBg,
      borderColor: c.tooltipBorder,
      textStyle: { color: c.text, ...(option.tooltip.textStyle ?? {}) },
      ...option.tooltip,
    }
  }

  if (option.legend) {
    out.legend = {
      ...option.legend,
      textStyle: { color: c.text, ...(option.legend.textStyle ?? {}) },
    }
  }

  // 坐标轴：标签文字 + 轴线 + 分隔线颜色
  for (const k of ['xAxis', 'yAxis']) {
    const a = option[k]
    if (a == null) continue
    const decorate = (ax: Record<string, any>) => ({
      ...ax,
      axisLine:
        ax.axisLine === undefined ? { lineStyle: { color: c.slate } } : ax.axisLine,
      axisLabel:
        ax.axisLabel === undefined
          ? { color: c.text }
          : { ...ax.axisLabel, color: ax.axisLabel.color ?? c.text },
      splitLine:
        ax.splitLine === undefined
          ? { lineStyle: { color: c.grid } }
          : {
              ...ax.splitLine,
              lineStyle: {
                ...(ax.splitLine.lineStyle ?? {}),
                color: ax.splitLine.lineStyle?.color ?? c.grid,
              },
            },
    })
    out[k] = Array.isArray(a) ? a.map(decorate) : decorate(a)
  }

  // 网格分隔线
  const g = option.grid
  if (g != null) {
    const decorateG = (gr: Record<string, any>) => ({
      ...gr,
      splitLine:
        gr.splitLine === undefined
          ? { lineStyle: { color: c.grid } }
          : {
              ...gr.splitLine,
              lineStyle: {
                ...(gr.splitLine.lineStyle ?? {}),
                color: gr.splitLine.lineStyle?.color ?? c.grid,
              },
            },
    })
    out.grid = Array.isArray(g) ? g.map(decorateG) : decorateG(g)
  }

  return out as T
}