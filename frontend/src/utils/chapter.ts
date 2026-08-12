// 数字 → 中文数字（用于"第一章"等标题）
const CN_NUM = ['零', '一', '二', '三', '四', '五', '六', '七', '八', '九']

export function cnNum(n: number | string): string {
  const num = Number(n)
  if (Number.isNaN(num) || num < 0) return String(n)
  if (num <= 9) return CN_NUM[num]
  if (num >= 100) return String(num) // 三位数及以上兜底（教学章节用不到，直接回退阿拉伯数字）
  // 两位数拆解（支持 10-99）
  const tens = Math.floor(num / 10)
  const ones = num % 10
  const tensStr = tens === 1 ? '' : CN_NUM[tens]
  const onesStr = ones === 0 ? '' : CN_NUM[ones]
  return `${tensStr}十${onesStr}`
}

export function chapterLabel(phase: number | string): string {
  const num = Number(phase)
  // Phase 0 是前置知识，不算第一章
  if (num === 0) return '前言'
  // 第一章从 Phase 1 开始
  return `第${cnNum(num)}章`
}
