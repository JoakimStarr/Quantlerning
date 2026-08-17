// 把 AI 输出里的课程标题替换为可点击链接（复习建议/学习规划跳转到对应课程）。
// 已知全部课程（title → id），按标题长度降序替换，避免短标题先被长标题子串覆盖；
// 用负向后顾跳过已存在的 markdown 链接文本，避免双重包裹。

export interface CourseRef {
  title: string
  id: string
}

export function linkifyCourses(text: string, lessons: CourseRef[]): string {
  if (!text || !lessons.length) return text
  const sorted = [...lessons].sort((a, b) => b.title.length - a.title.length)
  let out = text
  for (const l of sorted) {
    if (!l.title) continue
    const escaped = l.title.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    const re = new RegExp(`(?<!\\[)${escaped}`, 'g')
    out = out.replace(re, `[${l.title}](/lesson/${l.id})`)
  }
  return out
}
