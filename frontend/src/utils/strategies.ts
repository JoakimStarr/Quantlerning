// 策略回测纯函数库（与课程正文口径一致）
// 口径：复权 pct_chg 连乘、不含首日（index 1 起）、ddof=1、几何年化、信号次日生效
import type { StockDaily } from '@/api'

export interface StrategyStats {
  cum: number // 累计收益
  ann: number // 年化收益
  vol: number // 年化波动
  mdd: number // 最大回撤（负值）
  sharpe: number // Sharp(rf=2%)
  posMean: number // 平均持仓
  switches: number // 信号切换次数
}

/** 简单移动平均：预热段返回 null */
export function sma(values: number[], period: number): (number | null)[] {
  const out: (number | null)[] = []
  for (let i = 0; i < values.length; i++) {
    if (i < period - 1) {
      out.push(null)
      continue
    }
    let s = 0
    for (let j = i - period + 1; j <= i; j++) s += values[j]
    out.push(s / period)
  }
  return out
}

/** 滚动标准差（样本，ddof=1） */
export function rollingStd(values: number[], period: number): (number | null)[] {
  const out: (number | null)[] = []
  if (period <= 1) return values.map(() => null)
  for (let i = 0; i < values.length; i++) {
    if (i < period - 1) {
      out.push(null)
      continue
    }
    let m = 0
    for (let j = i - period + 1; j <= i; j++) m += values[j]
    m /= period
    let ss = 0
    for (let j = i - period + 1; j <= i; j++) ss += (values[j] - m) ** 2
    out.push(Math.sqrt(ss / (period - 1)))
  }
  return out
}

/** 信号 → 次日持仓（杜绝前视）。pos[t] = signal[t-1]，首个为 0 */
export function shiftPosition(signal: number[]): number[] {
  const out = signal.slice(0)
  for (let i = signal.length - 1; i >= 1; i--) out[i] = signal[i - 1]
  out[0] = 0
  return out
}

/** 双均线金叉死叉信号：1 看多 / 0 看空 */
export function maCrossSignal(closes: number[], fast: number, slow: number): number[] {
  const f = sma(closes, fast)
  const s = sma(closes, slow)
  return closes.map((_, i) => {
    if (f[i] === null || s[i] === null) return 0
    return f[i]! > s[i]! ? 1 : 0
  })
}

/** 布林带 z-score：z < −k 看多，z > +k 清仓（区段间沿用前值） */
export function bollingerZSignal(closes: number[], period: number, k: number): number[] {
  const mid = sma(closes, period)
  const sd = rollingStd(closes, period)
  const z = closes.map((_, i) => {
    if (mid[i] === null || sd[i] === null || sd[i]! === 0) return 0
    return (closes[i] - mid[i]!) / sd[i]!
  })
  const out: number[] = []
  let cur = 0
  for (let i = 0; i < closes.length; i++) {
    if (i < period) {
      out.push(0)
      continue
    }
    if (z[i] < -k) cur = 1
    else if (z[i] > k) cur = 0
    out.push(cur)
  }
  return out
}

/** 时序动量：过去 lookback 日收益 > 0 持有，否则空仓。此信号本身看 t 日过去收益，仍须次日生效 */
export function momentumSignal(closes: number[], lookback: number): number[] {
  return closes.map((_, i) => {
    if (i < lookback) return 0
    return closes[i] / closes[i - lookback] - 1 > 0 ? 1 : 0
  })
}

/** 唐奇安通道：high 突破过去 n 日最高做多，low 跌破过去 m 日最低清仓 */
export function donchianSignal(
  highs: number[],
  lows: number[],
  n: number,
  m: number,
): number[] {
  const out: number[] = []
  let cur = 0
  for (let i = 0; i < highs.length; i++) {
    if (i - 1 < n || i - 1 < m) {
      out.push(0)
      continue
    }
    let hi = -Infinity
    for (let j = i - n; j < i; j++) hi = Math.max(hi, highs[j])
    let lo = Infinity
    for (let j = i - m; j < i; j++) lo = Math.min(lo, lows[j])
    if (highs[i] > hi) cur = 1
    else if (lows[i] < lo) cur = 0
    out.push(cur)
  }
  return out
}

/** 策略净值（起点 100）：ret 为 pct_chg/100 全序列，pos 与 ret 对齐，首日收益不计入 */
export function strategyNav(ret: number[], pos: number[]): number[] {
  const out: number[] = []
  let v = 100
  out.push(v)
  for (let i = 1; i < ret.length; i++) {
    v *= 1 + ret[i] * pos[i]
    out.push(Number(v.toFixed(4)))
  }
  return out
}

/** 统计口径：与正文表格完全一致 */
export function stats(ret: number[], pos: number[]): StrategyStats {
  const n = ret.length - 1 // 不含首日收益数
  const nav = strategyNav(ret, pos)
  const last = nav[nav.length - 1]
  const cum = last / 100 - 1
  // 几何年化：(1+累计)^(252/n) − 1；last 是 100 起点的净值，须先归一为 1+累计
  const ann = Math.pow(last / 100, 252 / n) - 1
  // 年化波动基于策略日收益（pos>0 才有收益）
  const stratRet: number[] = []
  for (let i = 1; i < ret.length; i++) stratRet.push(ret[i] * pos[i])
  const mean = stratRet.reduce((a, b) => a + b, 0) / stratRet.length
  const varr = stratRet.reduce((a, b) => a + (b - mean) ** 2, 0) / (stratRet.length - 1)
  const vol = Math.sqrt(varr) * Math.sqrt(252)
  // 最大回撤
  let peak = -Infinity
  let mdd = 0
  for (const v of nav) {
    if (v > peak) peak = v
    const d = v / peak - 1
    if (d < mdd) mdd = d
  }
  const posMean = n > 0 ? pos.slice(1).reduce((a, b) => a + b, 0) / n : 0
  let switches = 0
  for (let i = 1; i < n; i++) {
    if (pos[i] !== pos[i - 1]) switches++
  }
  return {
    cum,
    ann,
    vol,
    mdd,
    sharpe: vol > 0 ? (ann - 0.02) / vol : 0,
    posMean,
    switches,
  }
}

/** 回测数据：把 raw 行情折叠成各指标数组（全序列，index 0 为区间首日） */
export function backtestArrays(rows: StockDaily[]) {
  return {
    dates: rows.map((d) => d.date),
    closes: rows.map((d) => d.close),
    highs: rows.map((d) => d.high),
    lows: rows.map((d) => d.low),
    ret: rows.map((d) => d.pct_chg / 100),
  }
}