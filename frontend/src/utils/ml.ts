// 前端轻量 ML 工具库：无 sklearn 依赖，纯 TS 手写
// 用于第五章：真实茅台特征 → 标准化 → 逻辑回归（梯度下降）→ 预测 / 评估
// 口径与课程正文一致：复权 pct_chg、不含首日、ddof=1
import type { StockDaily } from '@/api'
import { macd } from './indicators'

// ---------- 基础统计 ----------
export function mean(vals: number[]): number {
  return vals.reduce((s, v) => s + v, 0) / vals.length
}

export function std(vals: number[]): number {
  if (vals.length < 2) return 0
  const m = mean(vals)
  return Math.sqrt(vals.reduce((s, v) => s + (v - m) ** 2, 0) / (vals.length - 1))
}

export function median(vals: number[]): number {
  const s = [...vals].sort((a, b) => a - b)
  const m = Math.floor(s.length / 2)
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2
}

// ---------- 特征工程 ----------
export interface Features {
  names: string[]
  X: number[][] // 每行一个样本，每列一个特征
  y: number[] // 标签
  dates: string[]
}

/** 简单移动平均：预热段 null */
function sma(vals: number[], period: number): (number | null)[] {
  const out: (number | null)[] = []
  for (let i = 0; i < vals.length; i++) {
    if (i < period - 1) {
      out.push(null)
      continue
    }
    let s = 0
    for (let j = i - period + 1; j <= i; j++) s += vals[j]
    out.push(s / period)
  }
  return out
}

/** RSI (Wilder 简化) */
function rsi(vals: number[], period: number): (number | null)[] {
  const out: (number | null)[] = []
  let gain = 0
  let loss = 0
  for (let i = 0; i < vals.length; i++) {
    if (i === 0) {
      out.push(null)
      continue
    }
    const diff = vals[i] - vals[i - 1]
    const g = Math.max(diff, 0)
    const l = Math.max(-diff, 0)
    if (i <= period) {
      gain += g
      loss += l
      if (i === period) {
        gain /= period
        loss /= period
      }
      out.push(i === period ? (100 - 100 / (1 + gain / (loss || 1e-9))) : null)
    } else {
      gain = (gain * (period - 1) + g) / period
      loss = (loss * (period - 1) + l) / period
      out.push(100 - 100 / (1 + gain / (loss || 1e-9)))
    }
  }
  return out
}

/** 滚动标准差（样本 ddof=1），预热 null */
function rollingStd(vals: number[], period: number): (number | null)[] {
  const out: (number | null)[] = []
  for (let i = 0; i < vals.length; i++) {
    if (i < period - 1) {
      out.push(null)
      continue
    }
    const window = vals.slice(i - period + 1, i + 1)
    out.push(std(window))
  }
  return out
}

/**
 * 从真实日线构造 ML 特征矩阵。
 * 特征（全部只用 t 及之前信息，杜绝前视）：
 *  - mom5 / mom10 / mom20：过去 N 日累计涨跌幅
 *  - vol20：20 日收益滚动标准差（波动率）
 *  - rsi14：相对强弱
 *  - macd_hist：DIF-DEA（12/26/9）
 *  - dist_ma20：收盘价相对 20 日均线偏离
 *  - turnover：换手率（有则取）
 * 标签（前瞻 1 日）：次日收益 > 0 → 1，否则 0
 */
export function buildFeatures(rows: StockDaily[], lookahead = 1): Features {
  const closes = rows.map((r) => r.close)
  const rets = rows.map((r) => r.pct_chg / 100)
  const n = rows.length

  const names = ['mom5', 'mom10', 'mom20', 'vol20', 'rsi14', 'macd_hist', 'dist_ma20', 'turnover']
  const nFeat = names.length

  // 预计算指标数组（一次性）：避免每 t 重算 rollingStd/rsi/sma/ema → O(n) 而非 O(n²)
  const volArr = rollingStd(rets, 20)
  const rsiArr = rsi(closes, 14)
  const ma20Arr = sma(closes, 20)
  // MACD 柱与模拟器同口径（indicators.ts：SMA 种子 EMA，柱 = (DIF−DEA)×2）
  const macdHistArr = macd(closes, 12, 26, 9).hist

  // 逐特征构造（t 时刻可用值；前视特征置 null）
  const mat: (number | null)[][] = Array.from({ length: n }, () => new Array(nFeat).fill(null))

  for (let t = 0; t < n; t++) {
    // 动量：过去 N 日累计收益
    for (const [fi, N] of [[0, 5], [1, 10], [2, 20]] as const) {
      if (t >= N) mat[t][fi] = closes[t] / closes[t - N] - 1
    }
    mat[t][3] = volArr[t]
    mat[t][4] = rsiArr[t]
    mat[t][5] = macdHistArr[t]
    if (ma20Arr[t] !== null && ma20Arr[t] !== 0) mat[t][6] = closes[t] / ma20Arr[t]! - 1
    mat[t][7] = rows[t].turn ?? null
  }

  // 标签：t 的前瞻 lookahead 日收益 > 0
  const y: number[] = []
  for (let t = 0; t < n; t++) {
    if (t + lookahead >= n) y.push(0)
    else {
      const fwd = rets[t + lookahead]
      y.push(fwd > 0 ? 1 : 0)
    }
  }

  // 只保留所有特征完整的样本（前面预热期剔除）
  const X: number[][] = []
  const yKeep: number[] = []
  const dates: string[] = []
  for (let t = 0; t < n; t++) {
    const row = mat[t]
    if (row.some((v) => v === null || !isFinite(v as number))) continue
    X.push(row as number[])
    yKeep.push(y[t])
    dates.push(rows[t].date)
  }

  return { names, X, y: yKeep, dates }
}

// ---------- 标准化（z-score）----------
export function standardize(X: number[][]): { Xs: number[][]; means: number[]; stds: number[] } {
  const nFeat = X[0].length
  const means: number[] = []
  const stds: number[] = []
  const Xs: number[][] = []
  for (let j = 0; j < nFeat; j++) {
    const col = X.map((r) => r[j])
    means.push(mean(col))
    stds.push(std(col) || 1)
  }
  for (const row of X) {
    Xs.push(row.map((v, j) => (v - means[j]) / stds[j]))
  }
  return { Xs, means, stds }
}

/** 用训练集统计量标准化任意新数据 */
export function applyStandardize(X: number[][], means: number[], stds: number[]): number[][] {
  return X.map((r) => r.map((v, j) => (v - means[j]) / stds[j]))
}

// ---------- 逻辑回归（批量梯度下降）----------
export interface LogRegResult {
  weights: number[]
  bias: number
  iterations: number
  lossHistory: number[]
}

export function sigmoid(z: number): number {
  if (z >= 0) {
    const e = Math.exp(-z)
    return 1 / (1 + e)
  }
  const e = Math.exp(z)
  return e / (1 + e)
}

export function logitPredict(X: number[][], w: number[], b: number): number[] {
  return X.map((row) => sigmoid(row.reduce((s, v, j) => s + v * w[j], b)))
}

/**
 * 批量梯度下降训练逻辑回归（二分类）。
 * 支持 L2 正则（weight_decay）与早停（验证集可选）。
 */
export function trainLogistic(
  X: number[][],
  y: number[],
  opts: {
    lr?: number
    epochs?: number
    l2?: number
    Xv?: number[][]
    yv?: number[]
    verbose?: boolean
  } = {},
): LogRegResult {
  const { lr = 0.1, epochs = 2000, l2 = 0, Xv, yv } = opts
  const m = X.length
  const nFeat = X[0].length
  let w = new Array(nFeat).fill(0)
  let b = 0
  const lossHistory: number[] = []
  let bestAcc = -Infinity
  let bestW = w.slice()
  let bestB = b
  let bestIt = 0

  for (let it = 1; it <= epochs; it++) {
    const preds = logitPredict(X, w, b)
    // 梯度
    const gradW = new Array(nFeat).fill(0)
    let gradB = 0
    let loss = 0
    for (let i = 0; i < m; i++) {
      const p = preds[i]
      loss += -(y[i] * Math.log(p + 1e-12) + (1 - y[i]) * Math.log(1 - p + 1e-12))
      const err = p - y[i]
      gradB += err
      for (let j = 0; j < nFeat; j++) gradW[j] += err * X[i][j]
    }
    for (let j = 0; j < nFeat; j++) gradW[j] = gradW[j] / m + l2 * w[j]
    gradB /= m
    loss = loss / m + (l2 / 2) * w.reduce((s, v) => s + v * v, 0)

    // 更新
    for (let j = 0; j < nFeat; j++) w[j] -= lr * gradW[j]
    b -= lr * gradB

    if (it % 10 === 0 || it === epochs) {
      lossHistory.push(loss)
      // 早停：验证集准确率不再提升
      if (Xv && yv) {
        const acc = accuracy(logitPredict(Xv, w, b), yv)
        if (acc > bestAcc) {
          bestAcc = acc
          bestW = w.slice()
          bestB = b
          bestIt = it
        }
      }
    }
  }
  if (Xv && yv) return { weights: bestW, bias: bestB, iterations: bestIt, lossHistory }
  return { weights: w, bias: b, iterations: epochs, lossHistory }
}

export function accuracy(preds: number[], y: number[], threshold = 0.5): number {
  let correct = 0
  for (let i = 0; i < y.length; i++) {
    if ((preds[i] >= threshold ? 1 : 0) === y[i]) correct++
  }
  return correct / y.length
}

// ---------- 多项式拟合（正规方程，用于过拟合演示）----------
export function polyFit(
  x: number[],
  y: number[],
  degree: number,
): { coef: number[]; predict: (t: number) => number } {
  const m = x.length
  const X: number[][] = []
  for (let i = 0; i < m; i++) {
    const row: number[] = []
    let p = 1
    for (let d = 0; d <= degree; d++) {
      row.push(p)
      p *= x[i]
    }
    X.push(row)
  }
  // 正规方程 (X^T X)^-1 X^T y（高斯消元）
  const nCols = degree + 1
  const A: number[][] = Array.from({ length: nCols }, () => new Array(nCols + 1).fill(0))
  const rhs: number[] = new Array(nCols).fill(0)
  for (let a = 0; a < nCols; a++) {
    for (let c = 0; c < nCols; c++) {
      let s = 0
      for (let i = 0; i < m; i++) s += X[i][a] * X[i][c]
      A[a][c] = s
    }
    for (let i = 0; i < m; i++) rhs[a] += X[i][a] * y[i]
  }
  for (let a = 0; a < nCols; a++) A[a][nCols] = rhs[a]
  // 高斯消元
  const sol = gaussianSolve(A, nCols)
  const coef = sol
  const predict = (t: number) => {
    let s = 0
    let p = 1
    for (let d = 0; d < coef.length; d++) {
      s += coef[d] * p
      p *= t
    }
    return s
  }
  return { coef, predict }
}

function gaussianSolve(A: number[][], n: number): number[] {
  for (let col = 0; col < n; col++) {
    // 选主元
    let maxRow = col
    for (let r = col + 1; r < n; r++) {
      if (Math.abs(A[r][col]) > Math.abs(A[maxRow][col])) maxRow = r
    }
    if (maxRow !== col) {
      const tmp = A[col]
      A[col] = A[maxRow]
      A[maxRow] = tmp
    }
    const piv = A[col][col]
    if (Math.abs(piv) < 1e-12) continue
    for (let c = col; c <= n; c++) A[col][c] /= piv
    for (let r = 0; r < n; r++) {
      if (r === col) continue
      const f = A[r][col]
      if (Math.abs(f) < 1e-12) continue
      for (let c = col; c <= n; c++) A[r][c] -= f * A[col][c]
    }
  }
  return A.map((row) => row[n])
}

export function mse(yPred: number[], yTrue: number[]): number {
  let s = 0
  for (let i = 0; i < yTrue.length; i++) s += (yPred[i] - yTrue[i]) ** 2
  return s / yTrue.length
}

// ---------- 回测与绩效 ----------
export interface MlxStats {
  cum: number
  ann: number
  vol: number
  mdd: number
  sharpe: number
  posMean: number
  switches: number
}

/** 净值（起点 100），ret 为小数收益、pos 对齐且次日生效 */
export function navFromReturns(ret: number[], pos: number[]): number[] {
  const out: number[] = []
  let v = 100
  out.push(v)
  for (let i = 1; i < ret.length; i++) {
    v *= 1 + ret[i] * pos[i]
    out.push(Number(v.toFixed(4)))
  }
  return out
}

/** 绩效口径：与第二章一致（几何年化、ddof=1、rf=2%） */
export function mlxStats(ret: number[], pos: number[]): MlxStats {
  const n = ret.length - 1
  const nav = navFromReturns(ret, pos)
  const last = nav[nav.length - 1]
  const cum = last / 100 - 1
  // 几何年化：(1+累计)^(252/n) − 1；last 是 100 起点的净值，须先归一为 1+累计
  const ann = Math.pow(last / 100, 252 / Math.max(n, 1)) - 1
  const stratRet: number[] = []
  for (let i = 1; i < ret.length; i++) stratRet.push(ret[i] * pos[i])
  const m = stratRet.reduce((s, v) => s + v, 0) / stratRet.length
  const varr = stratRet.reduce((s, v) => s + (v - m) ** 2, 0) / (stratRet.length - 1)
  const vol = Math.sqrt(varr) * Math.sqrt(252)
  let peak = -Infinity
  let mdd = 0
  for (const v of nav) {
    if (v > peak) peak = v
    const d = v / peak - 1
    if (d < mdd) mdd = d
  }
  const posMean = n > 0 ? pos.slice(1).reduce((a, b) => a + b, 0) / n : 0
  let switches = 0
  for (let i = 1; i < n; i++) if (pos[i] !== pos[i - 1]) switches++
  return { cum, ann, vol, mdd, sharpe: vol > 0 ? (ann - 0.02) / vol : 0, posMean, switches }
}

/** 预测概率 → 仓位（阈值化或按概率缩放） */
export function probToPos(probs: number[], mode: 'binary' | 'scaled', threshold = 0.5): number[] {
  return probs.map((p) => (mode === 'binary' ? (p >= threshold ? 1 : 0) : Math.max(0, Math.min(1, (p - 0.5) * 2))))
}
