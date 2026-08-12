/**
 * AI 追问对话历史持久化：按「课程 + 小节」存入 localStorage。
 *
 * 职责：
 * - 消息变化（含流式追加）→ 防抖落盘
 * - restore()：载入当前小节历史
 * - clear()：清空当前小节历史
 * - flushSave()：立即落盘（组件卸载/关闭/切换小节时调用）
 */
import { onBeforeUnmount, watch, type Ref } from 'vue'
import type { ChatTurn } from '@/api'

const STORAGE_PREFIX = 'aiask:v1:'
const MAX_STORED = 60 // localStorage 单小节最多保留消息数

function storageKey(lessonId: string, sectionIndex: number) {
  return `${STORAGE_PREFIX}${lessonId}:${sectionIndex}`
}

export function loadHistory(lessonId: string, sectionIndex: number): ChatTurn[] {
  try {
    const raw = localStorage.getItem(storageKey(lessonId, sectionIndex))
    if (!raw) return []
    const arr = JSON.parse(raw)
    if (!Array.isArray(arr)) return []
    return arr
      .filter(
        (m): m is ChatTurn =>
          m &&
          (m.role === 'user' || m.role === 'assistant') &&
          typeof m.content === 'string',
      )
      .slice(-MAX_STORED)
  } catch {
    return []
  }
}

export function saveHistory(lessonId: string, sectionIndex: number, msgs: ChatTurn[]) {
  try {
    const key = storageKey(lessonId, sectionIndex)
    if (!msgs.length) localStorage.removeItem(key)
    else localStorage.setItem(key, JSON.stringify(msgs.slice(-MAX_STORED)))
  } catch {
    // 存储不可用/超配额：忽略，仅影响持久化
  }
}

/**
 * 绑定消息 ref 的历史持久化。
 * @param lessonId 返回当前课程 id 的 getter
 * @param sectionIndex 返回当前小节索引的 getter
 * @param messages 对话消息 ref（由调用方维护）
 */
export function useChatHistory(
  lessonId: () => string,
  sectionIndex: () => number,
  messages: Ref<ChatTurn[]>,
) {
  let saveTimer: number | undefined

  function scheduleSave() {
    window.clearTimeout(saveTimer)
    saveTimer = window.setTimeout(() => {
      saveHistory(lessonId(), sectionIndex(), messages.value)
    }, 400)
  }

  function flushSave() {
    window.clearTimeout(saveTimer)
    saveHistory(lessonId(), sectionIndex(), messages.value)
  }

  // 消息变化（含流式追加）→ 防抖落盘
  watch(messages, scheduleSave, { deep: true })
  onBeforeUnmount(flushSave)

  /** 载入当前小节的历史对话 */
  function restore() {
    messages.value = loadHistory(lessonId(), sectionIndex())
  }

  /** 清空当前小节历史（含存储） */
  function clear() {
    messages.value = []
    saveHistory(lessonId(), sectionIndex(), [])
  }

  return { restore, clear, flushSave, scheduleSave }
}
