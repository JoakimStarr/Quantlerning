// 组合优化纯函数库：协方差/有效前沿/风险平价/Black-Litterman/协整检验
// 第六章：马科维茨/风险平价/BL/统计套利。全部基于真实收益矩阵（小数收益）
import { mean, std } from './ml'

// ---------- 基础统计 ----------
export function covarianceMatrix(rets: number[][]): number[][] {
  // rets: [date][stock]
  if (!rets.length || !rets[0] || !rets[0].length) return []
  const nStocks = rets[0].length
  const n = rets.length
  const means = Array.from({ length: nStocks }, (_, j) => mean(rets.map((r) => r[j])))
  const cov: number[][] = Array.from({ length: nStocks }, () => new Array(nStocks).fill(0))
  for (let i = 0; i < nStocks; i++) {
    for (let j = 0; j < nStocks; j++) {
      let s = 0
      for (let t = 0; t < n; t++) s += (rets[t][i] - means[i]) * (rets[t][j] - means[j])
      cov[i][j] = s / (n - 1)
    }
  }
  return cov
}

export function correlationMatrix(cov: number[][]): number[][] {
  const n = cov.length
  const corr: number[][] = Array.from({ length: n }, () => new Array(n).fill(0))
  for (let i = 0; i < n; i++) {
    for (let j = 0; j < n; j++) {
      const si = Math.sqrt(cov[i][i])
      const sj = Math.sqrt(cov[j][j])
      corr[i][j] = si === 0 || sj === 0 ? 0 : cov[i][j] / (si * sj)
    }
  }
  return corr
}

export function annualReturns(dailyRets: number[][], periods = 252): number[] {
  if (!dailyRets.length || !dailyRets[0]) return []
  const nStocks = dailyRets[0].length
  return Array.from({ length: nStocks }, (_, j) => {
    const r = dailyRets.map((row) => row[j])
    // 官方口径：几何年化 (1+累计)^(periods/n) − 1（与 metrics.py 一致，非算术年化）
    const cum = r.reduce((s, v) => s * (1 + v), 1) - 1
    return Math.pow(1 + cum, periods / Math.max(r.length, 1)) - 1
  })
}

export function annualVols(cov: number[][], periods = 252): number[] {
  return cov.map((row, i) => Math.sqrt(row[i]) * Math.sqrt(periods))
}

// ---------- 组合统计 ----------
export function portfolioReturn(weights: number[], annRets: number[]): number {
  return weights.reduce((s, w, i) => s + w * annRets[i], 0)
}

export function portfolioVol(weights: number[], cov: number[][]): number {
  const n = weights.length
  let v = 0
  for (let i = 0; i < n; i++) {
    for (let j = 0; j < n; j++) v += weights[i] * weights[j] * cov[i][j]
  }
  return Math.sqrt(Math.max(v, 0))
}

export function portfolioSharpe(weights: number[], annRets: number[], cov: number[][], rf = 0.02): number {
  const r = portfolioReturn(weights, annRets)
  const vol = portfolioVol(weights, cov)
  return vol === 0 ? 0 : (r - rf) / vol
}

// ---------- 有效前沿 ----------
// 网格搜索：对目标收益做权重优化（等比例缩放 + 局部搜索的简化实现，教学够用）
export interface FrontierPoint {
  ret: number
  vol: number
  sharpe: number
  weights: number[]
}

/** 用随机采样逼近有效前沿（无 scipy）：采样大量组合，取收益-风险上包络（非支配点） */
export function efficientFrontier(
  annRets: number[],
  cov: number[][],
  nPoints = 40,
  samples = 30000,
): FrontierPoint[] {
  const n = annRets.length
  const pool: FrontierPoint[] = []
  for (let s = 0; s < samples; s++) {
    let w: number[] = []
    let sum = 0
    for (let i = 0; i < n; i++) {
      const u = -Math.log(Math.random() + 1e-9)
      w.push(u)
      sum += u
    }
    w = w.map((x) => x / sum)
    const ret = portfolioReturn(w, annRets)
    const vol = portfolioVol(w, cov)
    pool.push({ ret, vol, sharpe: (ret - 0.02) / vol, weights: w })
  }
  // 上包络：按波动升序扫描，保留「收益创新高」的点（同波动取更高收益）
  pool.sort((a, b) => a.vol - b.vol)
  const envelope: FrontierPoint[] = []
  let bestRet = -Infinity
  for (const p of pool) {
    if (p.ret > bestRet) {
      bestRet = p.ret
      envelope.push(p)
    }
  }
  // 稀疏化到 nPoints 个点（保留两端 + 均匀取中）
  if (envelope.length <= nPoints) return envelope
  const out: FrontierPoint[] = []
  for (let i = 0; i < nPoints; i++) {
    out.push(envelope[Math.floor((i * (envelope.length - 1)) / (nPoints - 1))])
  }
  return out
}

/** 最小方差组合（随机采样近似） */
export function minVariancePortfolio(cov: number[][], samples = 30000): number[] {
  const n = cov.length
  let bestW: number[] | null = null
  let bestVol = Infinity
  for (let s = 0; s < samples; s++) {
    let w: number[] = []
    let sum = 0
    for (let i = 0; i < n; i++) {
      const u = -Math.log(Math.random() + 1e-9)
      w.push(u)
      sum += u
    }
    w = w.map((x) => x / sum)
    const vol = portfolioVol(w, cov)
    if (vol < bestVol) {
      bestVol = vol
      bestW = w
    }
  }
  return bestW!
}

/** 最大夏普组合（随机采样近似） */
export function maxSharpePortfolio(annRets: number[], cov: number[][], rf = 0.02, samples = 30000): number[] {
  const n = annRets.length
  let bestW: number[] | null = null
  let bestS = -Infinity
  for (let s = 0; s < samples; s++) {
    let w: number[] = []
    let sum = 0
    for (let i = 0; i < n; i++) {
      const u = -Math.log(Math.random() + 1e-9)
      w.push(u)
      sum += u
    }
    w = w.map((x) => x / sum)
    const sharpe = portfolioSharpe(w, annRets, cov, rf)
    if (sharpe > bestS) {
      bestS = sharpe
      bestW = w
    }
  }
  return bestW!
}

// ---------- 风险平价 ----------
/**
 * 风险平价：每个资产对组合的风险贡献相等。
 * 风险贡献 RC_i = w_i * (Σ w_j cov_ij) / σ_p。
 * 阻尼对数迭代：RC 高于均值 → 降权，低于 → 升权（α 为更新步长，教学简化实现）
 */
export function riskParityWeights(cov: number[][], iterations = 1000, tol = 1e-9): number[] {
  const n = cov.length
  let w: number[] = new Array(n).fill(1 / n)
  for (let it = 0; it < iterations; it++) {
    const vol = portfolioVol(w, cov)
    if (vol === 0) break
    // 边际风险贡献
    const rc: number[] = []
    for (let i = 0; i < n; i++) {
      let sum = 0
      for (let j = 0; j < n; j++) sum += w[j] * cov[i][j]
      rc.push((w[i] * sum) / vol)
    }
    const meanRc = rc.reduce((a, b) => a + b, 0) / n
    if (meanRc === 0) break
    const alpha = 0.5
    // 用 map 的下标 i 取对应权重（rc.indexOf 在收敛趋同时会取错下标）
    const wNew = rc.map((x, i) => (x > 1e-12 ? w[i] * Math.pow(meanRc / x, alpha) : 0))
    const sumNew = wNew.reduce((a, b) => a + b, 0)
    if (sumNew === 0) break
    const wNorm = wNew.map((x) => x / sumNew)
    const diff = Math.max(...w.map((x, i) => Math.abs(x - wNorm[i])))
    w = wNorm
    if (diff < tol) break
  }
  return w
}

/** 各资产对组合的风险贡献占比 */
export function riskContributions(weights: number[], cov: number[][]): number[] {
  const n = weights.length
  const vol = portfolioVol(weights, cov)
  if (vol === 0) return new Array(n).fill(0)
  return weights.map((w, i) => {
    let sum = 0
    for (let j = 0; j < n; j++) sum += weights[j] * cov[i][j]
    return (w * sum) / vol
  })
}

// ---------- Black-Litterman ----------
export interface BlView {
  asset: number // 资产下标
  return: number // 观点收益（年化）
  confidence: number // 0~1 观点置信度
}

/**
 * 简化 Black-Litterman：
 * 均衡权重（等权或市值）→ 隐含超额收益 π = δ Σ w_eq
 * 后验收益 μ_BL = [(τΣ)^-1 + P'Ω^-1 P]^-1 [(τΣ)^-1 π + P'Ω^-1 Q]
 * 简化版：用对角近似 Ω，τ = 0.1，δ = 2.5
 */
export function blackLitterman(
  cov: number[][],
  views: BlView[],
  opts: { tau?: number; delta?: number; eqWeights?: number[] } = {},
): { mu: number[]; weights: number[]; implied: number[] } {
  const n = cov.length
  const tau = opts.tau ?? 0.1
  const delta = opts.delta ?? 2.5
  const eq = opts.eqWeights ?? new Array(n).fill(1 / n)

  // 隐含均衡超额收益
  const implied: number[] = []
  for (let i = 0; i < n; i++) {
    let s = 0
    for (let j = 0; j < n; j++) s += cov[i][j] * eq[j]
    implied.push(delta * s)
  }

  // 观点收益 Q：观点相对均衡的超额
  const Q = views.map((v) => v.return - implied[v.asset]) // 观点相对均衡的超额
  const omega = views.map((v) => {
    // 置信度越高方差越小：Ω ∝ (1/conf - 1) * τ * diag(Σ)
    const conf = Math.max(0.01, Math.min(0.99, v.confidence))
    const base = cov[v.asset][v.asset]
    return (1 / conf - 1) * tau * base
  })

  // 后验均值（简化解析式，对角 Ω + P 单位向量的情况）
  // μ_BL = π + τΣ P' (P τΣ P' + Ω)^-1 (Q - P π)
  const mu: number[] = implied.slice()
  if (views.length) {
    // 逐观点更新（近似：观点独立）
    for (let k = 0; k < views.length; k++) {
      const i = views[k].asset
      const pi = implied[i]
      const varI = cov[i][i] * tau
      const kappa = varI / (varI + omega[k])
      mu[i] = pi + kappa * (Q[k] - (pi - implied[i]))
    }
  }

  // 后验权重：w = (δΣ)^-1 μ_BL（简化，忽略约束）
  // 用采样近似组合优化：max Sharpe under mu_BL
  let bestW: number[] | null = null
  let bestS = -Infinity
  for (let s = 0; s < 20000; s++) {
    let w: number[] = []
    let sum = 0
    for (let i = 0; i < n; i++) {
      const u = -Math.log(Math.random() + 1e-9)
      w.push(u)
      sum += u
    }
    w = w.map((x) => x / sum)
    const r = portfolioReturn(w, mu)
    const vol = portfolioVol(w, cov)
    const sharpe = vol === 0 ? 0 : (r - 0.02) / vol
    if (sharpe > bestS) {
      bestS = sharpe
      bestW = w
    }
  }
  return { mu, weights: bestW!, implied }
}

// ---------- 协整检验（ADF 简化，Engle-Granger）----------
export interface CointegrationResult {
  beta: number // 回归系数（对数价格）
  alpha: number
  adf: number // ADF t 统计量
  critical5: number // 5% 临界值（近似 -2.89）
  cointegrated: boolean
  spread: number[] // 价差（对数）
  zscore: number[] // 标准化价差
}

/** OLS 对数价格回归 + 残差 ADF 检验 */
export function cointegrationTest(p1: number[], p2: number[]): CointegrationResult {
  const n = Math.min(p1.length, p2.length)
  const l1 = p1.slice(0, n).map((x) => Math.log(x))
  const l2 = p2.slice(0, n).map((x) => Math.log(x))
  const m1 = mean(l1)
  const m2 = mean(l2)
  let denom = 0
  for (let i = 0; i < n; i++) denom += (l1[i] - m1) ** 2
  const beta = denom === 0 ? 0 : l1.reduce((s, v, i) => s + (v - m1) * (l2[i] - m2), 0) / denom
  const alpha = m2 - beta * m1
  const spread = l2.map((v, i) => v - alpha - beta * l1[i])

  // ADF：Δs_t = ρ s_{t-1} + ε
  const dr = spread.slice(1).map((v, i) => v - spread[i])
  const rp = spread.slice(0, n - 1)
  const mr = mean(dr)
  const mrp = mean(rp)
  let den2 = 0
  for (let i = 0; i < rp.length; i++) den2 += (rp[i] - mrp) ** 2
  let phi = 0
  if (den2 > 0) {
    phi = dr.reduce((s, v, i) => s + (v - mr) * (rp[i] - mrp), 0) / den2
  }
  let sse = 0
  for (let i = 0; i < dr.length; i++) sse += (dr[i] - (mr + phi * (rp[i] - mrp))) ** 2
  const se = den2 > 0 ? Math.sqrt(sse / (dr.length - 2) / den2) : 0
  const adf = se === 0 ? 0 : phi / se

  // 标准化价差 z-score
  const sMean = mean(spread)
  const sStd = std(spread)
  const zscore = spread.map((v) => (sStd === 0 ? 0 : (v - sMean) / sStd))

  const critical5 = -2.89
  return { beta, alpha, adf, critical5, cointegrated: adf < critical5, spread, zscore }
}

/** 配对交易信号：价差 z-score 突破阈值做多/做空价差 */
export function pairTradingSignal(zscore: number[], entry: number, exit: number): number[] {
  const out: number[] = []
  let pos = 0
  for (let i = 0; i < zscore.length; i++) {
    const z = zscore[i]
    if (pos === 0 && z < -entry) pos = 1 // 价差过低 → 做多价差
    else if (pos === 0 && z > entry) pos = -1 // 价差过高 → 做空价差
    else if (pos === 1 && z > -exit) pos = 0
    else if (pos === -1 && z < exit) pos = 0
    out.push(pos)
  }
  return out
}

/** 价差策略净值：价差定义 spread = l2 − β·l1，做多价差日收益 = r2 − β·r1（正负号需与定义一致） */
export function spreadNav(
  ret1: number[],
  ret2: number[],
  beta: number,
  pos: number[],
): number[] {
  const out: number[] = []
  let v = 100
  out.push(v)
  for (let i = 1; i < ret1.length; i++) {
    const spreadRet = ret2[i] - beta * ret1[i]
    v *= 1 + pos[i] * spreadRet
    out.push(Number(v.toFixed(4)))
  }
  return out
}