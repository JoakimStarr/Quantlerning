<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { C, withAlpha } from '@/utils/chartTheme'

// 经典梯度下降图（3D 曲面版）：
// 把 f(x,y)=x²+a·y² 的碗状曲面用 canvas 透视投影画出来（蓝低、红高），
// 红色路径从起点沿 -∇f 滚向谷底 (0,0)，地面上虚线是路径在底面的投影。
// 教学点：学习率太大 → 震荡/发散；适中 → 收敛；太小 → 龟速。
// 教学演示（函数为示意，非真实数据）

const props = defineProps<{
  params?: Record<string, unknown>
}>()

const aCoeff = ref(typeof props.params?.a === 'number' ? (props.params.a as number) : 10) // 椭圆系数，越大 y 方向越陡 → zigzag 越明显
const lr = ref(typeof props.params?.lr === 'number' ? (props.params.lr as number) : 0.08) // 学习率（a=10 时收敛要求 η<0.1）
const x0 = ref(typeof props.params?.x0 === 'number' ? (props.params.x0 as number) : 2)
const y0 = ref(typeof props.params?.y0 === 'number' ? (props.params.y0 as number) : 1)

const DOMAIN = 3
const MAX_STEPS = 120

// 目标函数 f = x² + a·y²，梯度 (2x, 2a·y)
const f = (x: number, y: number) => x * x + aCoeff.value * y * y
const grad = (x: number, y: number): [number, number] => [2 * x, 2 * aCoeff.value * y]

// ---------- 3D 投影 ----------
const AZ = -0.72 // 绕 z 轴旋转（水平视角）
const EL = 0.52 // 绕 x 轴旋转（俯仰角）
const CAM_D = 10 // 相机距离

function project(x: number, y: number, z: number): { sx: number; sy: number; depth: number } {
  const c1 = Math.cos(AZ)
  const s1 = Math.sin(AZ)
  const x1 = x * c1 - y * s1
  const y1 = x * s1 + y * c1
  const c2 = Math.cos(EL)
  const s2 = Math.sin(EL)
  const y2 = y1 * c2 - z * s2
  const z2 = y1 * s2 + z * c2
  const denom = CAM_D - z2
  return { sx: x1 / denom, sy: y2 / denom, depth: z2 }
}

// 显示 z 缩放：让碗的最大高度稳定在 3 左右（与 x/y 范围 6 相当）
const zScale = () => 3 / (9 * (1 + aCoeff.value))

// ---------- 下降路径 ----------
const fullPath = ref<[number, number][]>([])
const shown = ref(0)
const running = ref(false)
const status = ref('')
let timer: number | undefined

function computePath(): [number, number][] {
  const path: [number, number][] = [[x0.value, y0.value]]
  let x = x0.value
  let y = y0.value
  for (let i = 0; i < MAX_STEPS; i++) {
    const [gx, gy] = grad(x, y)
    if (Math.hypot(gx, gy) < 1e-4) break
    x -= lr.value * gx
    y -= lr.value * gy
    path.push([x, y])
    if (Math.abs(x) > DOMAIN + 2 || Math.abs(y) > DOMAIN + 2) break // 发散
  }
  return path
}

function run() {
  stop()
  fullPath.value = computePath()
  shown.value = 1
  running.value = true
  timer = window.setInterval(() => {
    shown.value += 1
    draw()
    if (shown.value >= fullPath.value.length) {
      const last = fullPath.value[fullPath.value.length - 1]
      const [gx, gy] = grad(last[0], last[1])
      status.value =
        Math.hypot(gx, gy) < 1e-3 || Math.hypot(last[0], last[1]) < 1e-3
          ? '✅ 已收敛到极小点（谷底）'
          : '⚠️ 学习率过大：路径震荡/发散，没有收敛'
      stop()
    }
  }, 50)
}
function stop() {
  running.value = false
  if (timer) {
    window.clearInterval(timer)
    timer = undefined
  }
}
function reset() {
  stop()
  fullPath.value = []
  shown.value = 0
  status.value = ''
  draw()
}

// 参数变化 → 自动重画（若没在运行则重新铺路径的初始起点标记）
watch([aCoeff, lr, x0, y0], () => {
  if (!running.value) {
    fullPath.value = []
    shown.value = 0
    status.value = ''
    draw()
  }
})

// ---------- canvas ----------
const wrapRef = ref<HTMLDivElement | null>(null)
const canvasRef = ref<HTMLCanvasElement | null>(null)
let ctx: CanvasRenderingContext2D | null = null
let ro: ResizeObserver | null = null
let W = 0
let H = 0

function resize() {
  const wrap = wrapRef.value
  const canvas = canvasRef.value
  if (!wrap || !canvas) return
  const dpr = window.devicePixelRatio || 1
  W = wrap.clientWidth
  H = Math.max(240, Math.min(420, Math.round(W * 0.62)))
  canvas.width = W * dpr
  canvas.height = H * dpr
  canvas.style.width = `${W}px`
  canvas.style.height = `${H}px`
  ctx = canvas.getContext('2d')
  ctx?.setTransform(dpr, 0, 0, dpr, 0, 0)
  draw()
}

function colorFor(t: number): [number, number, number] {
  const stops: [number, [number, number, number]][] = [
    [0, [47, 106, 232]],
    [0.32, [16, 185, 129]],
    [0.62, [245, 158, 11]],
    [1, [220, 38, 38]],
  ]
  const tt = Math.max(0, Math.min(1, t))
  for (let i = 0; i < stops.length - 1; i++) {
    const [t0, c0] = stops[i]
    const [t1, c1] = stops[i + 1]
    if (tt >= t0 && tt <= t1) {
      const u = (tt - t0) / (t1 - t0 || 1)
      return [Math.round(c0[0] + (c1[0] - c0[0]) * u), Math.round(c0[1] + (c1[1] - c0[1]) * u), Math.round(c0[2] + (c1[2] - c0[2]) * u)]
    }
  }
  return stops[stops.length - 1][1]
}

function rgb(c: [number, number, number], alpha = 1) {
  return `rgba(${c[0]}, ${c[1]}, ${c[2]}, ${alpha})`
}

function draw() {
  if (!ctx || !W || !H) return
  const c = ctx
  c.clearRect(0, 0, W, H)
  const zk = zScale()

  // 采样曲面网格
  const N = 28
  const world: number[][][] = []
  const proj: ReturnType<typeof project>[][] = []
  for (let i = 0; i <= N; i++) {
    world.push([])
    proj.push([])
    for (let j = 0; j <= N; j++) {
      const x = -DOMAIN + (2 * DOMAIN * i) / N
      const y = -DOMAIN + (2 * DOMAIN * j) / N
      const z = f(x, y) * zk
      world[i].push([x, y, z])
      proj[i].push(project(x, y, z))
    }
  }

  // 收集所有点确定包围盒（含路径、底面）
  const pts: { sx: number; sy: number }[] = []
  for (const row of proj) for (const p of row) pts.push(p)
  // 底面 4 角
  for (const [x, y] of [
    [-DOMAIN, -DOMAIN],
    [DOMAIN, -DOMAIN],
    [DOMAIN, DOMAIN],
    [-DOMAIN, DOMAIN],
  ])
    pts.push(project(x, y, 0))
  // 路径点（曲面 + 底面投影）
  for (const [x, y] of fullPath.value.slice(0, shown.value)) {
    pts.push(project(x, y, f(x, y) * zk))
    pts.push(project(x, y, 0))
  }
  let minX = Infinity
  let maxX = -Infinity
  let minY = Infinity
  let maxY = -Infinity
  for (const p of pts) {
    if (p.sx < minX) minX = p.sx
    if (p.sx > maxX) maxX = p.sx
    if (p.sy < minY) minY = p.sy
    if (p.sy > maxY) maxY = p.sy
  }
  const scale = Math.min((W - 60) / (maxX - minX || 1), (H - 50) / (maxY - minY || 1))
  const ox = W / 2 - ((minX + maxX) / 2) * scale
  const oy = H / 2 - ((minY + maxY) / 2) * scale
  const toXY = (p: { sx: number; sy: number }) => [ox + p.sx * scale, oy + p.sy * scale] as const

  // ---------- 底面（z=0）：网格 + 等高线椭圆 ----------
  c.lineWidth = 1
  c.strokeStyle = withAlpha(C.value.slate, 0.35)
  for (let i = 0; i <= N; i++) {
    const x = -DOMAIN + (2 * DOMAIN * i) / N
    const a0 = toXY(project(x, -DOMAIN, 0))
    const a1 = toXY(project(x, DOMAIN, 0))
    const b0 = toXY(project(-DOMAIN, x, 0))
    const b1 = toXY(project(DOMAIN, x, 0))
    c.beginPath()
    c.moveTo(a0[0], a0[1])
    c.lineTo(a1[0], a1[1])
    c.moveTo(b0[0], b0[1])
    c.lineTo(b1[0], b1[1])
    c.stroke()
  }
  // 底面等高线（椭圆），虚线
  const maxF = 9 * (1 + aCoeff.value)
  c.setLineDash([3, 3])
  c.strokeStyle = withAlpha(C.value.ink, 0.35)
  const levels = [0.04, 0.09, 0.16, 0.25, 0.38, 0.55, 0.78, 1.0].map((t) => t * maxF)
  for (const L of levels) {
    const rx = Math.sqrt(L)
    const ry = Math.sqrt(L / aCoeff.value)
    if (rx > DOMAIN * 1.4 || ry > DOMAIN * 1.4) continue
    c.beginPath()
    for (let t = 0; t <= 64; t++) {
      const ang = (2 * Math.PI * t) / 64
      const [sx, sy] = toXY(project(rx * Math.cos(ang), ry * Math.sin(ang), 0))
      if (t === 0) c.moveTo(sx, sy)
      else c.lineTo(sx, sy)
    }
    c.stroke()
  }
  c.setLineDash([])

  // ---------- 曲面（painter 算法：远先画、近后画） ----------
  type Quad = { depth: number; draw: () => void }
  const quads: Quad[] = []
  for (let i = 0; i < N; i++) {
    for (let j = 0; j < N; j++) {
      const p00 = proj[i][j]
      const p10 = proj[i + 1][j]
      const p11 = proj[i + 1][j + 1]
      const p01 = proj[i][j + 1]
      const depth = (p00.depth + p10.depth + p11.depth + p01.depth) / 4
      const [x00, y00, z00] = world[i][j]
      const [x10, y10, z10] = world[i + 1][j]
      const [x01, y01, z01] = world[i][j + 1]
      // 光照：用两个边叉乘得法线
      const ux = x10 - x00
      const uy = y10 - y00
      const uz = z10 - z00
      const vx = x01 - x00
      const vy = y01 - y00
      const vz = z01 - z00
      let nx = uy * vz - uz * vy
      let ny = uz * vx - ux * vz
      let nz = ux * vy - uy * vx
      const nl = Math.hypot(nx, ny, nz) || 1
      nx /= nl
      ny /= nl
      nz /= nl
      const light = [0.35, 0.45, 0.85]
      const ll = Math.hypot(...light)
      let diff = (nx * light[0] + ny * light[1] + nz * light[2]) / ll
      diff = Math.max(0.25, 0.55 + 0.45 * diff)
      const hAvg = (z00 + z10 + z01) / 3 / (3 * zk) // 归一化高度
      const base = colorFor(hAvg)
      const col: [number, number, number] = [Math.min(255, Math.round(base[0] * diff)), Math.min(255, Math.round(base[1] * diff)), Math.min(255, Math.round(base[2] * diff))]
      const s00 = toXY(p00)
      const s10 = toXY(p10)
      const s11 = toXY(p11)
      const s01 = toXY(p01)
      quads.push({
        depth,
        draw: () => {
          c.beginPath()
          c.moveTo(s00[0], s00[1])
          c.lineTo(s10[0], s10[1])
          c.lineTo(s11[0], s11[1])
          c.lineTo(s01[0], s01[1])
          c.closePath()
          c.fillStyle = rgb(col)
          c.fill()
          c.strokeStyle = withAlpha(C.value.ink, 0.10)
          c.stroke()
        },
      })
    }
  }
  quads.sort((a, b) => a.depth - b.depth)
  for (const q of quads) q.draw()

  // ---------- 曲面上的等高线环 ----------
  c.lineWidth = 1
  c.strokeStyle = withAlpha(C.value.ink, 0.4)
  for (const L of levels) {
    const rx = Math.sqrt(L)
    const ry = Math.sqrt(L / aCoeff.value)
    if (rx > DOMAIN * 1.2 || ry > DOMAIN * 1.2) continue
    c.beginPath()
    for (let t = 0; t <= 64; t++) {
      const ang = (2 * Math.PI * t) / 64
      const [sx, sy] = toXY(project(rx * Math.cos(ang), ry * Math.sin(ang), L * zk))
      if (t === 0) c.moveTo(sx, sy)
      else c.lineTo(sx, sy)
    }
    c.stroke()
  }

  // ---------- 下降路径 ----------
  const pathPts = fullPath.value.slice(0, shown.value)
  if (pathPts.length >= 2) {
    // 地面投影（虚线）
    c.setLineDash([4, 4])
    c.strokeStyle = withAlpha(C.value.danger, 0.35)
    c.lineWidth = 1.2
    c.beginPath()
    pathPts.forEach(([x, y], i) => {
      const [sx, sy] = toXY(project(x, y, 0))
      if (i === 0) c.moveTo(sx, sy)
      else c.lineTo(sx, sy)
    })
    c.stroke()
    c.setLineDash([])
    // 曲面上路径
    c.strokeStyle = C.value.danger
    c.lineWidth = 2.4
    c.beginPath()
    pathPts.forEach(([x, y], i) => {
      const [sx, sy] = toXY(project(x, y, f(x, y) * zk))
      if (i === 0) c.moveTo(sx, sy)
      else c.lineTo(sx, sy)
    })
    c.stroke()
    // 路径节点
    for (const [x, y] of pathPts) {
      const [sx, sy] = toXY(project(x, y, f(x, y) * zk))
      c.beginPath()
      c.arc(sx, sy, 2.6, 0, Math.PI * 2)
      c.fillStyle = C.value.danger
      c.fill()
    }
  }

  // ---------- 标记 ----------
  const marker = (x: number, y: number, color: string, z = f(x, y) * zk) => {
    const [sx, sy] = toXY(project(x, y, z))
    c.beginPath()
    c.arc(sx, sy, 5.5, 0, Math.PI * 2)
    c.fillStyle = color
    c.fill()
    c.lineWidth = 1.6
    c.strokeStyle = '#fff'
    c.stroke()
  }
  marker(x0.value, y0.value, C.value.warning) // 起点
  marker(0, 0, C.value.success, 0) // 极小点
  if (pathPts.length > 0) {
    const [cx, cy] = pathPts[pathPts.length - 1]
    marker(cx, cy, C.value.danger) // 当前位置
  }

  // ---------- 坐标轴 ----------
  c.font = '11px system-ui, sans-serif'
  c.fillStyle = withAlpha(C.value.ink, 0.7)
  const xl = toXY(project(DOMAIN + 0.4, 0, 0))
  const yl = toXY(project(0, DOMAIN + 0.4, 0))
  c.fillText('x', xl[0], xl[1])
  c.fillText('y', yl[0], yl[1])
}

// 自动运行一次（默认参数展示经典 zigzag）
function init() {
  resize()
  if (!fullPath.value.length) run()
}

onMounted(() => {
  ro = new ResizeObserver(() => resize())
  if (wrapRef.value) ro.observe(wrapRef.value)
  init()
})
onBeforeUnmount(() => {
  stop()
  ro?.disconnect()
})

const currentPoint = computed(() => {
  const last = fullPath.value.length ? fullPath.value[Math.min(shown.value, fullPath.value.length) - 1] : [x0.value, y0.value]
  return last
})
const currentF = computed(() => f(currentPoint.value[0], currentPoint.value[1]))

const fmt2 = (v: number) => (Number.isFinite(v) ? v.toFixed(2) : '—')
</script>

<template>
  <div class="gd-demo">
    <div ref="wrapRef" class="canvas-wrap">
      <canvas ref="canvasRef" class="gd-canvas"></canvas>
    </div>

    <div class="controls">
      <div class="control-row">
        <span class="control-label">学习率 η</span>
        <input v-model.number="lr" type="range" min="0.01" max="0.5" step="0.01" class="slider" />
        <span class="control-value">{{ lr.toFixed(2) }}</span>
      </div>
      <div class="control-row">
        <span class="control-label">椭圆系数 a</span>
        <input v-model.number="aCoeff" type="range" min="1" max="20" step="0.5" class="slider" />
        <span class="control-value">{{ aCoeff.toFixed(1) }}</span>
      </div>
      <div class="control-row">
        <span class="control-label">起点 x₀</span>
        <input v-model.number="x0" type="range" :min="-2" :max="2" step="0.1" class="slider" />
        <span class="control-value">{{ x0.toFixed(1) }}</span>
      </div>
      <div class="control-row">
        <span class="control-label">起点 y₀</span>
        <input v-model.number="y0" type="range" :min="-2" :max="2" step="0.1" class="slider" />
        <span class="control-value">{{ y0.toFixed(1) }}</span>
      </div>
      <div class="btn-row">
        <button class="run-btn" :disabled="running" @click="run">▶ 运行梯度下降</button>
        <button class="run-btn plain" @click="reset">重置</button>
      </div>
      <div v-if="status" class="status" :class="{ bad: status.startsWith('⚠️'), ok: status.startsWith('✅') }">
        {{ status }}
      </div>
      <div class="result-row">
        <div class="result-box"><span class="muted">当前步数</span><strong>{{ shown }}</strong></div>
        <div class="result-box"><span class="muted">当前 (x, y)</span><strong>{{ fmt2(currentPoint[0]) }}, {{ fmt2(currentPoint[1]) }}</strong></div>
        <div class="result-box"><span class="muted">f(x, y)</span><strong>{{ fmt2(currentF) }}</strong></div>
      </div>
      <p class="hint">
        这是教科书里的经典梯度下降图：<strong>碗状曲面</strong>是 $f(x,y)=x^2+a y^2$（蓝低、红高），红色路径从起点沿 −∇f
        滚向谷底 (0,0)，地面虚线是路径的投影。收敛要求 $\eta &lt; 1/a$（a=10 时 η&lt;0.1）。<strong>试着调 η</strong>：
        η≈0.08 走出一条 zigzag 快速收敛；η≥0.1 就在 y 方向来回震荡、发散不收敛；η 很小（如 0.02）则龟速接近。
      </p>
    </div>
  </div>
</template>

<style scoped>
.gd-demo { padding: 16px; }
.canvas-wrap { width: 100%; background: linear-gradient(180deg, var(--bg-hover), var(--bg-card)); border-radius: var(--radius-sm); }
.gd-canvas { display: block; max-width: 100%; }
.controls { margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border); display: flex; flex-direction: column; gap: 8px; }
.control-row { display: flex; align-items: center; gap: 12px; }
.control-label { width: 88px; font-size: 12.5px; color: var(--text-2); flex-shrink: 0; }
.slider { flex: 1; accent-color: var(--primary); cursor: pointer; }
.control-value { width: 48px; font-size: 12.5px; font-weight: 600; color: var(--primary); text-align: right; flex-shrink: 0; }
.btn-row { display: flex; gap: 8px; }
.run-btn {
  flex: 1; font-size: 13px; padding: 7px 10px; border: 1px solid var(--primary);
  border-radius: var(--radius-sm); background: var(--primary); color: #fff; cursor: pointer;
}
.run-btn:hover { filter: brightness(1.06); }
.run-btn:disabled { opacity: 0.6; cursor: not-allowed; }
.run-btn.plain { background: var(--bg-card); color: var(--text-2); border-color: var(--border); }
.status {
  font-size: 13px; font-weight: 600; text-align: center; padding: 6px 10px;
  border-radius: var(--radius-sm);
}
.status.ok { color: var(--success, #16a34a); background: color-mix(in srgb, var(--success) 10%, transparent); }
.status.bad { color: var(--danger, #dc2626); background: color-mix(in srgb, var(--danger) 10%, transparent); }
.result-row { display: flex; gap: 8px; }
.result-box { flex: 1; padding: 8px 6px; border-radius: var(--radius-sm); background: var(--bg-hover); text-align: center; display: flex; flex-direction: column; gap: 2px; }
.result-box strong { font-size: 13px; }
.muted { font-size: 11.5px; color: var(--text-3); }
.hint { margin-top: 8px; font-size: 12px; color: var(--text-3); line-height: 1.7; }
</style>
