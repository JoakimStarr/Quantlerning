// 图表数据 → 文本：把 ECharts 图表的实际数据（series 数据点）序列化成可读文本，
// 供「图表问 AI」把真实数据随问题发给模型（模型无视觉能力，但能读文本数值）。
// 只提取 series + 分类 x 轴，忽略样式类字段；数据量大时截断并注明总点数。

const MAX_POINTS_PER_SERIES = 100
const MAX_SERIES = 5

function fmt(v: unknown): string {
  if (v === null || v === undefined) return 'null'
  if (Array.isArray(v)) return `[${v.map(fmt).join(', ')}]`
  if (typeof v === 'object') {
    const obj = v as Record<string, unknown>
    const name = obj.name ?? obj.x ?? obj.date ?? obj.time ?? ''
    const val = obj.value ?? obj.y
    if (name !== '' && val !== undefined) return `${name}: ${fmt(val)}`
    return JSON.stringify(obj)
  }
  if (typeof v === 'number') {
    return Math.abs(v) >= 100
      ? String(Math.round(v))
      : String(Math.round(v * 100) / 100)
  }
  return String(v)
}

/** 从 series 数据里提取数值（对象取 value/y，数组取第一个数值，逐层展开） */
function numericValues(data: unknown[]): number[] {
  const nums: number[] = []
  const walk = (v: unknown): void => {
    if (typeof v === 'number' && Number.isFinite(v)) {
      nums.push(v)
    } else if (Array.isArray(v)) {
      for (const c of v) if (typeof c === 'number' && Number.isFinite(c)) nums.push(c)
    } else if (v && typeof v === 'object') {
      const obj = v as Record<string, unknown>
      const val = obj.value ?? obj.y
      if (typeof val === 'number' && Number.isFinite(val)) nums.push(val)
    }
  }
  for (const d of data) walk(d)
  return nums
}

const round = (n: number) => (Math.abs(n) >= 100 ? Math.round(n) : Math.round(n * 100) / 100)

/** 数值序列统计摘要：min / max / 均值 / 最新值（数据点较多时给模型整体概念） */
function statsText(data: unknown[]): string {
  const nums = numericValues(data)
  if (nums.length < 5) return ''
  const min = Math.min(...nums)
  const max = Math.max(...nums)
  const mean = nums.reduce((s, n) => s + n, 0) / nums.length
  const last = nums[nums.length - 1]
  return `统计：min=${round(min)}，max=${round(max)}，均值=${round(mean)}，最新=${round(last)}`
}

/** 从 ECharts getOption() 结果提取数据文本；无 series 时返回空串。 */
export function chartDataToText(option: unknown): string {
  const opt = option as Record<string, any> | null
  const series = opt?.series
  if (!Array.isArray(series) || series.length === 0) return ''

  const xAxis = opt?.xAxis
  const xCat = Array.isArray(xAxis)
    ? (xAxis[0]?.data as unknown[] | undefined)
    : (xAxis?.data as unknown[] | undefined)

  const lines: string[] = []
  for (const s of series.slice(0, MAX_SERIES)) {
    const data = s?.data
    if (!Array.isArray(data)) continue
    const name = s?.name ? String(s.name) : '序列'
    const total = data.length
    let shown: string[]
    if (Array.isArray(xCat) && xCat.length === total) {
      shown = data.map((v: unknown, i: number) => `${fmt(xCat[i])}: ${fmt(v)}`)
    } else {
      shown = data.map((v: unknown) => fmt(v))
    }
    const head = shown.slice(0, MAX_POINTS_PER_SERIES)
    const trunc = total > head.length ? `（共 ${total} 个数据点，显示前 ${head.length} 个）` : ''
    lines.push(`${name}${trunc}：${head.join('，')}`)
    const stats = statsText(data)
    if (stats) lines.push(`${name} ${stats}`)
  }
  return lines.join('\n')
}
