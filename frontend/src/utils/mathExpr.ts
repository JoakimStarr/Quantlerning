/**
 * 单变量/双变量数学表达式工具（基于 mathjs 安全解析器）。
 *
 * 支持：x/y、+ - * / ^、括号、隐式乘法（2x、x(x+1)、2abs(x)）、
 * 常量 pi/e，函数 sin/cos/tan/sqrt/log/ln/exp/abs/sign，
 * 以及 |x| 绝对值（预处理为 abs(x)，支持嵌套与隐式乘法）。
 *
 * 不执行任意代码：mathjs 自带安全解析器（非 eval）。mathjs 无 ln 函数
 * （log 即自然对数），故预处理时把 ln 归一为 log。
 *
 * 对外 API 与原手写解析器一致：
 *  - parseFunction / parseBinaryFunction：编译成求值函数（语法非法或含多余符号时返回 null）
 *  - exprToLatex：表达式 → LaTeX（含 |x| 预处理）
 *  - parseAst / evaluateAst / astToLatex / differentiate：AST 级操作（供泰勒系数/凹凸拐点用）
 *  - taylorCoefficients：符号微分逐阶求导
 */
import { parse, derivative, type MathNode } from 'mathjs/number'

export type ExprNode = MathNode

// ---------- 预处理：ln → log、|...| → abs(...) ----------

/** ln 归一为 log（mathjs 无 ln，log 即自然对数） */
function normalizeLn(src: string): string {
  return src.replace(/\bln\b/g, 'log')
}

/**
 * 把 |...| 绝对值语法转为 abs(...)，支持嵌套与 `|x|*|y|` 等隐式乘法。
 *
 * 判定规则：深度为 0 时 | 必为开符；深度 >0 时，若前一个有效字符是运算符/左括号/
 * 逗号/竖线（即「此处期望一个值」）则开符，否则闭符。闭符后紧跟值起始字符时补 *。
 */
function normalizeAbs(src: string): string {
  let out = ''
  let depth = 0
  let i = 0
  while (i < src.length) {
    const c = src[i]
    if (c !== '|') {
      out += c
      i++
      continue
    }
    if (depth === 0) {
      out += 'abs('
      depth = 1
      i++
      continue
    }
    // 深度 >0：看前一个有效字符决定开/闭
    let j = i - 1
    while (j >= 0 && /\s/.test(src[j])) j--
    const prev = j < 0 ? '' : src[j]
    if (prev === '' || '+-*/^,(|'.includes(prev)) {
      // 嵌套绝对值或运算后：期望一个值 → 开
      out += 'abs('
      depth++
    } else {
      // 闭
      out += ')'
      depth--
      // 闭符后紧跟值起始字符（数字/字母/左括号/竖线）→ 隐式乘法，补 *
      let k = i + 1
      while (k < src.length && /\s/.test(src[k])) k++
      if (k < src.length && /[a-zA-Z0-9(|]/.test(src[k])) out += '*'
    }
    i++
  }
  return out
}

function preprocess(src: string): string {
  return normalizeAbs(normalizeLn(src))
}

function tryParse(src: string): ExprNode | null {
  const s = preprocess(src)
  if (!s.trim()) return null
  try {
    return parse(s)
  } catch {
    return null
  }
}

/** 编译缓存：同一 AST 只 compile 一次（曲线逐点求值场景避免重复编译） */
const compiledCache = new WeakMap<ExprNode, { evaluate: (scope?: Record<string, number>) => number }>()

function compileNode(n: ExprNode): { evaluate: (scope?: Record<string, number>) => number } {
  let c = compiledCache.get(n)
  if (!c) {
    c = n.compile() as { evaluate: (scope?: Record<string, number>) => number }
    compiledCache.set(n, c)
  }
  return c
}

/** 表达式中的符号集合（不含函数名，如 sin/abs 的 fn 子节点） */
function symbolSet(n: ExprNode): Set<string> {
  const s = new Set<string>()
  n.traverse((node: MathNode, _path, parent) => {
    const sym = node as unknown as { isSymbolNode?: boolean; name?: string }
    const par = parent as unknown as { isFunctionNode?: boolean } | null
    if (sym.isSymbolNode && sym.name && !par?.isFunctionNode) s.add(sym.name)
  })
  return s
}

/**
 * 解析单变量函数表达式，返回 f(x)；语法非法或含 x/pi/e 之外的符号（如 y）时返回 null。
 */
export function parseFunction(src: string): ((x: number) => number) | null {
  const node = tryParse(src)
  if (!node) return null
  const syms = symbolSet(node)
  for (const s of syms) {
    if (s !== 'x' && s !== 'pi' && s !== 'e') return null
  }
  const compiled = compileNode(node)
  return (x: number) => compiled.evaluate({ x, pi: Math.PI, e: Math.E }) as number
}

/**
 * 解析二元函数表达式，返回 f(x, y)；语法非法时返回 null。
 */
export function parseBinaryFunction(src: string): ((x: number, y: number) => number) | null {
  const node = tryParse(src)
  if (!node) return null
  const syms = symbolSet(node)
  for (const s of syms) {
    if (s !== 'x' && s !== 'y' && s !== 'pi' && s !== 'e') return null
  }
  const compiled = compileNode(node)
  return (x: number, y: number) => compiled.evaluate({ x, y, pi: Math.PI, e: Math.E }) as number
}

/**
 * 将表达式转为 LaTeX 公式字符串（如 "x^3/3" → "\\frac{{ x}^{3}}{3}"）；
 * 语法非法时返回 null。
 */
export function exprToLatex(src: string): string | null {
  const node = tryParse(src)
  if (!node) return null
  try {
    return node.toTex()
  } catch {
    return null
  }
}

/** 解析为 AST；语法非法时返回 null（供符号微分等扩展使用） */
export function parseAst(src: string): ExprNode | null {
  return tryParse(src)
}

/** 求值 AST（同一 AST 编译结果缓存复用） */
export function evaluateAst(n: ExprNode, x: number, y: number): number {
  return compileNode(n).evaluate({ x, y, pi: Math.PI, e: Math.E }) as number
}

/** AST → LaTeX */
export function astToLatex(n: ExprNode): string {
  try {
    return n.toTex()
  } catch {
    return ''
  }
}

/** 符号微分：返回 f 对变量 v 的导数的 AST（mathjs derivative，精确） */
export function differentiate(n: ExprNode, v: 'x' | 'y'): ExprNode {
  return derivative(n, v)
}

/** 求 f 在 a 处的前 maxOrder 阶泰勒系数（c_k = f⁽ᵏ⁾(a)/k!），用符号微分逐阶求导 */
export function taylorCoefficients(
  src: string,
  a: number,
  maxOrder: number,
): { coeffs: number[]; error: boolean } {
  const node = tryParse(src)
  if (!node) return { coeffs: [], error: true }
  const coeffs: number[] = []
  let d: ExprNode = node
  let fact = 1
  for (let k = 0; k <= maxOrder; k++) {
    let val = Number.NaN
    try {
      val = compileNode(d).evaluate({ x: a, pi: Math.PI, e: Math.E }) as number
    } catch {
      val = Number.NaN
    }
    coeffs.push(Number.isFinite(val) ? val / fact : 0)
    fact *= k + 1
    try {
      d = derivative(d, 'x')
    } catch {
      break
    }
  }
  return { coeffs, error: false }
}
