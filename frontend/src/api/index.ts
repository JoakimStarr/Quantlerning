import axios from 'axios'

// 开发环境经 Vite 代理 /api → http://localhost:8100
const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
})

// ---------- 课程 ----------
export async function fetchCourses() {
  const { data } = await api.get('/courses')
  return data
}

export async function fetchLesson(id: string) {
  const { data } = await api.get(`/courses/${id}`)
  return data
}

// ---------- 数据 ----------
export interface StockDaily {
  date: string // YYYY-MM-DD
  open: number
  high: number
  low: number
  close: number
  volume: number
  amount: number
  pct_chg: number
  turn: number
  pe_ttm: number
  pb_mrq: number
}

export async function searchStock(q: string) {
  const { data } = await api.get('/data/search', { params: { q } })
  return data
}

// 个股日线模块级缓存：同 (code,start,end) 只请求一次
// 缓存下沉到 API 层，让 useStockDaily / usePortfolioDaily 共享同一份数据
const stockDailyCache = new Map<string, StockDaily[]>()

export async function fetchStockDaily(code: string, start: string, end: string) {
  const key = `${code.toLowerCase()}_${start}_${end}`
  const hit = stockDailyCache.get(key)
  if (hit) return hit
  const { data } = await api.get(`/data/stock/${code}/daily`, { params: { start, end } })
  const rows = data as StockDaily[]
  stockDailyCache.set(key, rows)
  return rows
}

export interface MarketPeDistribution {
  date: string
  count: number
  median: number | null
  p90: number | null
  bins: { lo: number | null; hi: number; count: number }[]
}

export async function fetchMarketPeDistribution(tradeDate: string, bins = 40) {
  const { data } = await api.get('/data/market/pe-distribution', { params: { trade_date: tradeDate, bins } })
  return data as MarketPeDistribution
}

export async function fetchIndices(type = 'all') {
  const { data } = await api.get('/data/indices', { params: { index_type: type } })
  return data
}

export async function fetchFactors(params: { status?: string; category?: string; limit?: number; order_by?: string } = {}) {
  const { data } = await api.get('/data/factors', { params })
  return data
}

export async function fetchFactorSummary() {
  const { data } = await api.get('/data/factors/summary')
  return data
}

export interface IcDistribution {
  count: number
  lo: number
  hi: number
  median: number
  mean: number
  p90: number
  bins: { center: number; count: number }[]
}

export async function fetchIcDistribution(bins = 30) {
  const { data } = await api.get('/data/factors/ic-distribution', { params: { bins } })
  return data as IcDistribution
}

export interface PeLayers {
  dates: string[]
  groups: string[]
  matrix: (number | null)[][]
  counts: number[][]
  n_groups: number
}

export async function fetchPeLayers(start: string, end: string, nGroups = 5) {
  const { data } = await api.get('/data/factors/pe-layers', {
    params: { start, end, n_groups: nGroups },
  })
  return data as PeLayers
}

export interface PeIc {
  dates: string[]
  ic: number[]
  mean: number | null
  std: number | null
  icir: number | null
  n_obs: number
}

export async function fetchPeIc(start: string, end: string) {
  const { data } = await api.get('/data/factors/pe-ic', { params: { start, end } })
  return data as PeIc
}

export interface IndustryPe {
  date: string
  count: number
  industries: { industry: string; n: number; median: number | null; lo: number | null; hi: number | null }[]
}

export async function fetchIndustryPe(tradeDate: string, minStocks = 30) {
  const { data } = await api.get('/data/factors/industry-pe', {
    params: { trade_date: tradeDate, min_stocks: minStocks },
  })
  return data as IndustryPe
}

export interface BacktestResult {
  id: number
  combination_method: string
  benchmark: string
  topk: number
  n_drop: number
  rebalance_freq: string
  annual_return: number
  annual_volatility: number
  sharpe: number
  max_drawdown: number
  excess_return: number
  nav: { dates: string[]; portfolio: number[]; benchmark: number[] } | null
}

export async function fetchBacktests(limit = 20) {
  const { data } = await api.get('/data/backtests', { params: { limit } })
  return data as BacktestResult[]
}

export async function fetchMacroIndicators() {
  const { data } = await api.get('/data/macro/indicators')
  return data
}

export async function fetchMacro(indicator: string, start: string, end: string) {
  const { data } = await api.get(`/data/macro/${indicator}`, { params: { start, end } })
  return data
}

// ---------- 练习沙箱 ----------
export interface ExecResult {
  ok: boolean
  stdout: string
  stderr: string
  duration_ms: number
  blocked: string[]
  images: string[] // matplotlib 图形（base64 PNG）
}

export async function runCode(code: string): Promise<ExecResult> {
  const { data } = await api.post('/exec/run', { code })
  return data as ExecResult
}

// ---------- AI 追问（SSE 流式）----------
export interface ChatTurn {
  role: 'user' | 'assistant'
  content: string
}

/**
 * 通用 SSE 流式 POST：解析 {"delta"} / {"done"} / {"error"} 事件。
 * @returns 若发生错误返回 {error}，否则 {}（正常结束或被取消）
 */
async function streamSSE(
  url: string,
  payload: unknown,
  onDelta: (text: string) => void,
  signal?: AbortSignal,
): Promise<{ error?: string }> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal,
  })
  if (!res.ok || !res.body) {
    return { error: `请求失败（HTTP ${res.status}）` }
  }
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let sep: number
    while ((sep = buffer.indexOf('\n\n')) !== -1) {
      const raw = buffer.slice(0, sep)
      buffer = buffer.slice(sep + 2)
      const line = raw.split('\n').find((l) => l.trim().startsWith('data:'))
      if (!line) continue
      try {
        const evt = JSON.parse(line.slice(line.indexOf('data:') + 5).trim())
        if (typeof evt.delta === 'string' && evt.delta) onDelta(evt.delta)
        if (evt.error) return { error: String(evt.error) }
        if (evt.done) return {}
      } catch {
        // 忽略无法解析的帧
      }
    }
  }
  return {}
}

/**
 * 围绕当前课程小节追问，SSE 流式返回。
 * @param payload.model 覆盖模型（空=用当前配置）；payload.deep 深度思考开关
 * @returns 若发生错误返回 {error}，否则 {}（正常结束或被取消）
 */
export async function streamChat(
  payload: {
    lesson_id: string
    section_index: number
    messages: ChatTurn[]
    model?: string
    deep?: boolean
  },
  onDelta: (text: string) => void,
  signal?: AbortSignal,
): Promise<{ error?: string }> {
  return streamSSE('/api/v1/chat/stream', payload, onDelta, signal)
}

/**
 * AI 批改应用题，SSE 流式返回批改结果。
 * @returns 若发生错误返回 {error}，否则 {}（正常结束或被取消）
 */
export async function judgeAnswer(
  payload: { lesson_id: string; section_index: number; question: string; answer: string },
  onDelta: (text: string) => void,
  signal?: AbortSignal,
): Promise<{ error?: string }> {
  return streamSSE('/api/v1/chat/judge', payload, onDelta, signal)
}

/**
 * 批改后追问：结合题目、学生答案与上轮批改反馈，回答学生对批改的疑问（SSE 流式）。
 * @returns 若发生错误返回 {error}，否则 {}（正常结束或被取消）
 */
export async function streamJudgeFollowup(
  payload: {
    lesson_id: string
    section_index: number
    question: string
    answer: string
    feedback: string
    messages: ChatTurn[]
  },
  onDelta: (text: string) => void,
  signal?: AbortSignal,
): Promise<{ error?: string }> {
  return streamSSE('/api/v1/chat/judge-followup', payload, onDelta, signal)
}

/**
 * 生成变式应用题：依据原题与学生表现，出同知识点、相近难度的练习题（SSE 流式）。
 * @returns 若发生错误返回 {error}，否则 {}（正常结束或被取消）
 */
export async function streamGenExercise(
  payload: {
    lesson_id: string
    section_index: number
    question: string
    answer: string
    feedback: string
  },
  onDelta: (text: string) => void,
  signal?: AbortSignal,
): Promise<{ error?: string }> {
  return streamSSE('/api/v1/chat/gen-exercise', payload, onDelta, signal)
}

/**
 * 学习路径规划：基于进度数据，输出复习重点与下一步建议（SSE 流式）。
 * @returns 若发生错误返回 {error}，否则 {}（正常结束或被取消）
 */
export async function streamPlan(
  payload: { summary: string },
  onDelta: (text: string) => void,
  signal?: AbortSignal,
): Promise<{ error?: string }> {
  return streamSSE('/api/v1/chat/plan', payload, onDelta, signal)
}

export default api

// ---------- 设置（AI 模型配置）----------
export interface AISettings {
  base_url: string
  model: string
  max_tokens: number
  temperature: number
  api_key_masked: string
  configured: boolean
  fallback_base_url: string
  fallback_model: string
  fallback_max_tokens: number | null
  fallback_api_key_masked: string
  fallback_configured: boolean
}

export async function fetchAISettings(): Promise<AISettings> {
  const { data } = await api.get('/settings/ai')
  return data
}

export async function saveAISettings(payload: {
  base_url: string
  api_key?: string
  model: string
  max_tokens?: number | null
  temperature?: number | null
  fallback_base_url?: string
  fallback_api_key?: string
  fallback_model?: string
  fallback_max_tokens?: number | null
}): Promise<AISettings> {
  const { data } = await api.put('/settings/ai', payload)
  return data
}

export async function testAISettings(payload: {
  base_url: string
  api_key?: string
  model: string
  max_tokens?: number | null
  temperature?: number | null
}): Promise<{ ok: boolean; message: string; reply?: string }> {
  const { data } = await api.post('/settings/ai/test', payload)
  return data
}

/** 当前提供商可用模型列表（后端已兜底并入主/备用配置模型） */
export async function fetchAIModels(): Promise<{ models: string[]; current: string }> {
  const { data } = await api.get('/settings/ai/models')
  return data
}

/** 按表单提交的 base_url/api_key 拉取模型列表（未填项后端回退已保存/环境配置）；失败返回 error 字段 */
export async function fetchAIModelsByConfig(payload: {
  base_url?: string
  api_key?: string
  model?: string
}): Promise<{ models: string[]; current: string; error?: string }> {
  const { data } = await api.post('/settings/ai/models', payload)
  return data
}
