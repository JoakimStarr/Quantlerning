// 学习进度与活跃度：单一真源（localStorage，前端持久化，不依赖后端内存）。
// 事件驱动：读课 / 测验 / 应用题 / 代码运行都会记活跃日期，「学习天数」由此统计。
import { reactive } from 'vue'

const STORAGE_KEY = 'quantlerning_progress'
const ACTIVITY_KEY = 'quantlerning_activity'

interface LessonProgress {
  completed: boolean
  quizScore?: number // 答对的知识点测验数（score===100）
  quizzesTotal?: number // 已提交的测验题数
  exercises?: number // 提交的应用题次数
  reads?: number // 打开/阅读次数
  lastReadAt?: string
  updatedAt?: string
}

interface Activity {
  dates: string[] // 有学习活动的日期（YYYY-MM-DD，去重）
  sandboxRuns: number
  sandboxSuccess?: number // 沙箱运行成功次数
  sandboxFail?: number // 沙箱运行失败次数
}

function load<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key)
    return raw ? JSON.parse(raw) : fallback
  } catch {
    return fallback
  }
}

function save(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    // 存储不可用/超配额：仅影响持久化
  }
}

export const progress = reactive<Record<string, LessonProgress>>(load(STORAGE_KEY, {}))
const activity = reactive<Activity>(load(ACTIVITY_KEY, { dates: [], sandboxRuns: 0 }))

function today(): string {
  return new Date().toISOString().slice(0, 10)
}

function markActivity() {
  const d = today()
  if (!activity.dates.includes(d)) {
    activity.dates.push(d)
    save(ACTIVITY_KEY, activity)
  }
}

export function isCompleted(lessonId: string): boolean {
  return progress[lessonId]?.completed ?? false
}

export function totalQuizPassed(): number {
  return Object.values(progress).reduce((n, p) => n + (p.quizScore ?? 0), 0)
}

export function getProgress(lessonId: string): LessonProgress | undefined {
  return progress[lessonId]
}

/** 记录一次阅读（学习行为，驱动「学习天数」；阅读即完成该课，与「进度靠阅读行为」定位一致） */
export function recordLessonRead(lessonId: string) {
  const cur = progress[lessonId] ?? ({} as LessonProgress)
  progress[lessonId] = {
    ...cur,
    completed: true,
    reads: (cur.reads ?? 0) + 1,
    lastReadAt: new Date().toISOString(),
  }
  save(STORAGE_KEY, progress)
  markActivity()
}

/** 记录一次测验提交：passed=答对数，total=已提交题数；全部答对也标记完成（只升不降，避免已读完的课被答错而降级） */
export function recordQuizAttempt(lessonId: string, passed: number, total: number) {
  const cur = progress[lessonId] ?? ({} as LessonProgress)
  const allPass = total > 0 && passed === total
  progress[lessonId] = {
    ...cur,
    completed: cur.completed || allPass,
    quizScore: passed,
    quizzesTotal: total,
    updatedAt: new Date().toISOString(),
  }
  save(STORAGE_KEY, progress)
  markActivity()
}

/** 记录一次应用题提交（AI 判题） */
export function recordExercise(lessonId: string) {
  const cur = progress[lessonId] ?? ({} as LessonProgress)
  progress[lessonId] = {
    ...cur,
    exercises: (cur.exercises ?? 0) + 1,
    updatedAt: new Date().toISOString(),
  }
  save(STORAGE_KEY, progress)
  markActivity()
}

/** 记录一次代码沙箱运行（ok=是否执行成功，驱动「跑通」与「尝试」统计） */
export function recordSandboxRun(ok = true) {
  activity.sandboxRuns += 1
  if (ok) activity.sandboxSuccess = (activity.sandboxSuccess ?? 0) + 1
  else activity.sandboxFail = (activity.sandboxFail ?? 0) + 1
  save(ACTIVITY_KEY, activity)
  markActivity()
}

/** 学习天数：有学习活动的不同自然日数 */
export function learningDays(): number {
  return activity.dates.length
}

/** 练习提交总数：测验答题 + 应用题 + 代码沙箱运行 */
export function totalExercises(): number {
  const quiz = Object.values(progress).reduce((n, p) => n + (p.quizzesTotal ?? 0), 0)
  const ex = Object.values(progress).reduce((n, p) => n + (p.exercises ?? 0), 0)
  return quiz + ex + activity.sandboxRuns
}

/** 代码沙箱运行次数 */
export function sandboxRunCount(): number {
  return activity.sandboxRuns
}
