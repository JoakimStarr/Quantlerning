// 技术指标纯函数库（真实数据实时计算用）
// 教学用途：公式与课程正文一致，前端可读、可复算

/** 指数移动平均：SMA 种子 + 递推。预热段返回 null（与课程死叉/金叉叙事一致） */
export function ema(values: number[], period: number): (number | null)[] {
  const out: (number | null)[] = []
  if (values.length === 0 || period <= 0) return out
  const k = 2 / (period + 1)
  let prev: number | null = null
  for (let i = 0; i < values.length; i++) {
    if (i < period - 1) {
      out.push(null)
      continue
    }
    if (i === period - 1) {
      // SMA 种子
      let s = 0
      for (let j = i - period + 1; j <= i; j++) s += values[j]
      prev = s / period
    } else {
      prev = values[i] * k + prev! * (1 - k)
    }
    out.push(prev)
  }
  return out
}

export interface MacdResult {
  dif: (number | null)[]
  dea: (number | null)[]
  hist: (number | null)[] // (DIF − DEA) × 2
}

/** MACD：DIF = EMA(fast) − EMA(slow)，DEA = DIF 的 signal 日 EMA，柱 = (DIF−DEA)×2 */
export function macd(closes: number[], fast: number, slow: number, signal: number): MacdResult {
  const emaFast = ema(closes, fast)
  const emaSlow = ema(closes, slow)
  const dif: (number | null)[] = closes.map((_, i) => {
    if (emaFast[i] === null || emaSlow[i] === null) return null
    return emaFast[i]! - emaSlow[i]!
  })
  // DEA：对 DIF 再做 signal 日 EMA（预热段丢弃 null）
  const difClean = dif.filter((v): v is number => v !== null)
  const deaRaw = ema(difClean, signal)
  const dea: (number | null)[] = []
  let j = 0
  for (let i = 0; i < closes.length; i++) {
    if (dif[i] === null) {
      dea.push(null)
    } else {
      dea.push(deaRaw[j] ?? null)
      j++
    }
  }
  const hist: (number | null)[] = dif.map((v, i) =>
    v !== null && dea[i] !== null ? (v - dea[i]!) * 2 : null,
  )
  return { dif, dea, hist }
}

/** RSI（Wilder 平滑）。返回与输入等长的数组，预热段为 null */
export function rsi(closes: number[], period: number): (number | null)[] {
  const out: (number | null)[] = []
  if (closes.length <= period || period <= 0) return out
  let avgGain = 0
  let avgLoss = 0
  // 首周期用简单平均作为种子
  for (let i = 1; i <= period; i++) {
    const chg = closes[i] - closes[i - 1]
    if (chg >= 0) avgGain += chg
    else avgLoss -= chg
  }
  avgGain /= period
  avgLoss /= period
  out.push(avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss))
  // 递推：Wilder 平滑
  for (let i = period + 1; i < closes.length; i++) {
    const chg = closes[i] - closes[i - 1]
    const gain = chg > 0 ? chg : 0
    const loss = chg < 0 ? -chg : 0
    avgGain = (avgGain * (period - 1) + gain) / period
    avgLoss = (avgLoss * (period - 1) + loss) / period
    out.push(avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss))
  }
  // 前 period 个交易日为预热段（无值）
  return [...new Array(period).fill(null), ...out]
}

export interface DrawdownResult {
  drawdown: number[] // 与 nav 等长，回撤 = nav/peak − 1
  mdd: number // 最大回撤（负值）
  peakIdx: number
  troughIdx: number
}

/** 最大回撤：遍历维护历史峰值，回撤 = 当前值/峰值 − 1 */
export function maxDrawdown(nav: number[]): DrawdownResult {
  const drawdown: number[] = []
  let peak = -Infinity
  let peakIdx = 0
  let mdd = 0
  let mddPeak = 0
  let mddTrough = 0
  nav.forEach((v, i) => {
    if (v > peak) {
      peak = v
      peakIdx = i
    }
    const dd = v / peak - 1
    drawdown.push(dd)
    if (dd < mdd) {
      mdd = dd
      mddPeak = peakIdx
      mddTrough = i
    }
  })
  return { drawdown, mdd, peakIdx: mddPeak, troughIdx: mddTrough }
}

/** 回撤 d（负值）需要上涨多少比例才回本：1/(1−d) − 1 */
export function recoveryNeeded(d: number): number {
  if (d >= 0) return 0
  return 1 / (1 + d) - 1
}
