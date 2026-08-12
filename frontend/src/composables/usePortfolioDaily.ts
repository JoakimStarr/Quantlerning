// 多股票日线并行拉取 + 同步收益矩阵对齐
// 第六章组合分析用：马科维茨/风险平价/BL 需要多股票同日期收益
import { computed, onMounted, ref, type Ref } from 'vue'
import { fetchStockDaily, type StockDaily } from '@/api'

export interface PortfolioUniverse {
  code: string
  name: string
}

const cache = new Map<string, StockDaily[]>()

/** 拉单只股票（模块级缓存，与 useStockDaily 共用同一数据源） */
async function fetchOne(code: string, start: string, end: string): Promise<StockDaily[]> {
  const key = `${code}_${start}_${end}`
  const hit = cache.get(key)
  if (hit) return hit
  const rows = await fetchStockDaily(code, start, end)
  cache.set(key, rows)
  return rows
}

export function usePortfolioDaily(
  universe: Ref<PortfolioUniverse[]>,
  start = '2024-01-01',
  end = '2024-12-31',
) {
  const loading = ref(true)
  const error = ref<string | null>(null)
  // 对齐后的数据：dates + per-stock 收益矩阵 + 名称
  const dates = ref<string[]>([])
  const returns = ref<number[][]>([]) // [date][stock] 小数收益
  const names = ref<string[]>([])
  const codes = ref<string[]>([])
  const closes = ref<number[][]>([]) // [date][stock]

  async function load() {
    loading.value = true
    error.value = null
    try {
      const u = universe.value
      // 并行拉取；逐只记录失败，避免静默用 0 收益污染协方差
      const entries = await Promise.all(
        u.map(async (s) => {
          try {
            const rows = await fetchOne(s.code, start, end)
            return { name: s.name, code: s.code, rows }
          } catch {
            return { name: s.name, code: s.code, rows: [] as StockDaily[] }
          }
        }),
      )
      const failed = entries.filter((e) => e.rows.length === 0)
      if (failed.length) {
        error.value = `数据不可用：${failed.map((f) => f.name).join('、')}`
        dates.value = []
        returns.value = []
        closes.value = []
        names.value = []
        codes.value = []
        return
      }
      const all = entries.map((e) => e.rows)
      // 找共同交易日
      let common = new Set<string>(all[0]?.map((d) => d.date) ?? [])
      for (const rows of all) {
        common = new Set([...common].filter((d) => rows.some((r) => r.date === d)))
      }
      const dateList = [...common].sort()
      if (!dateList.length) {
        error.value = '数据不可用'
        return
      }
      dates.value = dateList
      names.value = u.map((s) => s.name)
      codes.value = u.map((s) => s.code)
      // 收益矩阵（pct_chg/100）：共同交易日的真实日收益（与单股口径一致，首日即真实涨跌）
      returns.value = dateList.map((d) =>
        all.map((rows) => {
          const row = rows.find((r) => r.date === d)
          return row ? row.pct_chg / 100 : 0
        }),
      )
      // 收盘矩阵
      closes.value = dateList.map((d) =>
        all.map((rows) => {
          const row = rows.find((r) => r.date === d)
          return row ? row.close : NaN
        }),
      )
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
    } finally {
      loading.value = false
    }
  }

  onMounted(load)

  // 对数收益矩阵（用于统计/协方差，与算术收益差异可忽略且数学性质更好）
  const logReturns = computed<number[][]>(() =>
    returns.value.map((row) => row.map((r) => Math.log(1 + r))),
  )

  return { dates, returns, logReturns, names, codes, closes, loading, error, load }
}
