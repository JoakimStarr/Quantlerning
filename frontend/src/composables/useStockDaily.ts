// 拉取个股日线（缓存统一在 API 层），供 MACD/RSI/MDD 模拟器复用
import { computed, onMounted, ref, watch, type Ref } from 'vue'
import { fetchStockDaily, type StockDaily } from '@/api'

export function useStockDaily(
  code: Ref<string>,
  start = '2024-01-01',
  end = '2024-12-31',
) {
  const data = ref<StockDaily[] | null>(null)
  const loading = ref(true)
  const error = ref<string | null>(null)
  let reqId = 0 // 竞态防护：只接受最新一次请求的结果

  async function load() {
    const id = ++reqId
    data.value = null // 换股票/区间时清空旧数据，避免串号
    loading.value = true
    error.value = null
    try {
      const rows = await fetchStockDaily(code.value, start, end)
      if (id !== reqId) return // 已被更新的请求取代
      data.value = rows
    } catch (e) {
      if (id !== reqId) return
      error.value = e instanceof Error ? e.message : String(e)
    } finally {
      if (id === reqId) loading.value = false
    }
  }

  // code 变化时重载（支持股票切换的组件）；日期区间为静态入参，无需监听
  watch(code, () => load())

  onMounted(load)

  // 复权净值：从 100 起点，按 pct_chg 逐日累积（与课程主线口径一致）
  const nav = computed<number[] | null>(() => {
    if (!data.value || data.value.length === 0) return null
    const out: number[] = []
    let v = 100
    out.push(v)
    for (let i = 1; i < data.value.length; i++) {
      v *= 1 + data.value[i].pct_chg / 100
      out.push(v)
    }
    return out
  })

  return { data, nav, loading, error, load }
}
