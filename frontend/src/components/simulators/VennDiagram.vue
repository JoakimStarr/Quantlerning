<script setup lang="ts">
import { computed, ref } from 'vue'

// 文氏图：事件是样本空间 Ω 的子集
// - 拖动 P(A)、P(B)、P(A∩B) 观察四个区域概率的变化
// - 点击区域 chip 高亮对应集合（交/并/补/差）
// - 「互斥」「独立」按钮展示二者的本质区别（教学示意，区域大小仅示意）
// 几何：两个等圆，圆心距随 P(A∩B) 联动（互斥→分离，包含→重合）

const props = defineProps<{
  params?: Record<string, unknown>
}>()

const pA = ref(num(props.params?.pA, 0.6))
const pB = ref(num(props.params?.pB, 0.5))
const pAB = ref(num(props.params?.pAB, 0.3))

function num(v: unknown, d: number) {
  return typeof v === 'number' && Number.isFinite(v) ? Math.min(1, Math.max(0, v)) : d
}

const maxAB = computed(() => Math.min(pA.value, pB.value))
// 交集概率被 P(A)、P(B) 钳制
const ab = computed(() => Math.min(pAB.value, maxAB.value))
const abSlider = computed({
  get: () => ab.value,
  set: (v: number) => {
    pAB.value = v
  },
})

// 四个互斥区域的概率
const pAonly = computed(() => pA.value - ab.value)
const pBonly = computed(() => pB.value - ab.value)
const pNeither = computed(() => Math.max(0, 1 - (pA.value + pB.value - ab.value)))
const pUnion = computed(() => pA.value + pB.value - ab.value)
const pAgivenB = computed(() => (pB.value > 0 ? ab.value / pB.value : 0))
const pBgivenA = computed(() => (pA.value > 0 ? ab.value / pA.value : 0))

const isIndependent = computed(() => Math.abs(ab.value - pA.value * pB.value) < 0.005)
const isMutuallyExclusive = computed(() => ab.value < 0.005)
const statusText = computed(() => {
  if (isMutuallyExclusive.value) return '互斥：A∩B = ∅，P(A∩B) = 0'
  if (isIndependent.value) return '独立：P(A∩B) = P(A)·P(B)'
  return '一般相关：P(A|B) ≠ P(A)'
})

// ---------- 几何 ----------
const W = 420
const H = 280
const CX = 210
const CY = 150
const R = 62
const OX = 30
const OY = 36
const OW = 360
const OH = 220

const viewRect = `M 0 0 H ${W} V ${H} H 0 Z`
const spaceRect = `M ${OX} ${OY} H ${OX + OW} V ${OY + OH} H ${OX} Z`

const d = computed(() => {
  const m = maxAB.value
  if (m <= 0) return R * 2
  return R * 2 * (1 - ab.value / m)
})
const cxA = computed(() => CX - d.value / 2)
const cxB = computed(() => CX + d.value / 2)

function circlePath(cx: number) {
  return `M ${cx} ${CY - R} A ${R} ${R} 0 1 0 ${cx} ${CY + R} A ${R} ${R} 0 1 0 ${cx} ${CY - R} Z`
}
const circleA = computed(() => circlePath(cxA.value))
const circleB = computed(() => circlePath(cxB.value))

/** 两圆交叠的透镜路径；不重叠时返回 null。
 * 按 SVG 弧线规范（fA≠fS 取正号圆心），两段弧均为 laf=0, sweep=1：
 * 第一段 = 圆 A 右弧（右边界），第二段 = 圆 B 左弧（左边界）。 */
const lens = computed<string | null>(() => {
  const d2 = cxB.value - cxA.value
  if (d2 >= 2 * R) return null
  const h = Math.sqrt(Math.max(0, R * R - (d2 / 2) ** 2))
  const mid = (cxA.value + cxB.value) / 2
  return `M ${mid} ${CY - h} A ${R} ${R} 0 0 1 ${mid} ${CY + h} A ${R} ${R} 0 0 1 ${mid} ${CY - h} Z`
})

// ---------- 区域形状（evenodd 实现差集/补集） ----------
type RegionKey = 'A' | 'B' | 'AB' | 'union' | 'ABar' | 'notAB' | 'Aonly' | 'Bonly'

interface RegionDef {
  label: string
  /** 高亮时绘制的路径 */
  paths: string[]
  fillRule: 'nonzero' | 'evenodd'
  /** 遮罩：除区域外全暗（viewRect + 区域形状，evenodd） */
  dim: string
}

const regions = computed<Record<RegionKey, RegionDef | null>>(() => {
  const cA = circleA.value
  const cB = circleB.value
  const l = lens.value
  const join = (...ps: (string | null)[]) => ps.filter(Boolean).join(' ')

  return {
    A: { label: 'A', paths: [cA], fillRule: 'nonzero', dim: `${viewRect} ${cA}` },
    B: { label: 'B', paths: [cB], fillRule: 'nonzero', dim: `${viewRect} ${cB}` },
    AB: l
      ? { label: 'A∩B', paths: [l], fillRule: 'nonzero', dim: `${viewRect} ${l}` }
      : null,
    union: {
      label: 'A∪B',
      paths: [cA, cB],
      fillRule: 'nonzero',
      dim: join(viewRect, cA, cB, l), // 补 lens 使交叠区也不被遮暗
    },
    ABar: {
      label: 'Ā',
      paths: [join(spaceRect, cA)],
      fillRule: 'evenodd',
      dim: `${viewRect} ${spaceRect} ${cA}`,
    },
    notAB: {
      label: '非A非B',
      paths: [join(spaceRect, cA, cB, l)],
      fillRule: 'evenodd',
      dim: join(viewRect, spaceRect, cA, cB, l),
    },
    Aonly: {
      label: 'A-B',
      paths: [join(cA, l)],
      fillRule: 'evenodd',
      dim: join(viewRect, cA, l),
    },
    Bonly: {
      label: 'B-A',
      paths: [join(cB, l)],
      fillRule: 'evenodd',
      dim: join(viewRect, cB, l),
    },
  }
})

const selected = ref<RegionKey | null>(null)
function toggleRegion(k: RegionKey) {
  if (!regions.value[k]) return
  selected.value = selected.value === k ? null : k
}

// ---------- 条件视图：样本空间收缩为条件事件 ----------
// 实例模式：sets = 第一节「事件是集合」（只展示交/并/补/差）；
//           cond = 第二节「条件概率」（只展示样本空间收缩到条件事件）
type CondMode = 'none' | 'A' | 'B'
const isCondMode = (props.params?.mode ?? 'sets') === 'cond'
const mode = ref<'sets' | 'cond'>(isCondMode ? 'cond' : 'sets')
const cond = ref<CondMode>(
  isCondMode ? (props.params?.cond === 'A' ? 'A' : 'B') : 'none',
)

const condCircle = computed(() => (cond.value === 'A' ? circleA.value : circleB.value))
const condDim = computed(() => `${viewRect} ${condCircle.value}`)
// 被条件事件：以 B 为条件 → P(A|B)，分子是 A∩B，分母是 B
const condDenom = computed(() => (cond.value === 'A' ? pA.value : pB.value))
const condProbText = computed(() => {
  if (cond.value === 'none') return ''
  if (condDenom.value === 0) return '未定义（P=0）'
  return fmtPct(ab.value / condDenom.value)
})

const selRegion = computed(() => (selected.value ? regions.value[selected.value] : null))
// 当前选中区域的概率（与集合表达式对应）
const selProb = computed(() => {
  switch (selected.value) {
    case 'A':
      return pA.value
    case 'B':
      return pB.value
    case 'AB':
      return ab.value
    case 'union':
      return pUnion.value
    case 'ABar':
      return 1 - pA.value
    case 'notAB':
      return pNeither.value
    case 'Aonly':
      return pAonly.value
    case 'Bonly':
      return pBonly.value
    default:
      return null
  }
})

// 快速设定：互斥 / 独立
function setExclusive() {
  pAB.value = 0
}
function setIndependent() {
  pAB.value = pA.value * pB.value
}

const fmt = (v: number) => `${Math.round(v * 100)}%`
const fmtPct = (v: number) => `${(v * 100).toFixed(1)}%`

const REGION_ORDER: RegionKey[] = ['A', 'B', 'AB', 'union', 'ABar', 'notAB', 'Aonly', 'Bonly']
</script>

<template>
  <div class="venn">
    <svg class="diagram" viewBox="0 0 420 280" role="img" aria-label="文氏图">
      <!-- 样本空间 -->
      <rect :x="OX" :y="OY" :width="OW" :height="OH" class="space" />
      <text x="34" y="52" class="omega">Ω</text>

      <!-- 基础集合 -->
      <path :d="circleA" class="set set-a" />
      <path :d="circleB" class="set set-b" />
      <path v-if="lens" :d="lens" class="set set-lens" />

      <!-- 无条件：区域选择高亮 -->
      <template v-if="cond === 'none'">
        <path v-if="selRegion" :d="selRegion.dim" fill-rule="evenodd" class="dim" />
        <g v-if="selRegion" class="hl">
          <path
            v-for="(p, i) in selRegion.paths"
            :key="i"
            :d="p"
            :fill-rule="selRegion.fillRule"
          />
        </g>
      </template>
      <!-- 条件视图：样本空间收缩为条件事件，A∩B 即为 P(A|B) 的分子 -->
      <template v-else>
        <path :d="condDim" fill-rule="evenodd" class="dim" />
        <path v-if="lens" :d="lens" class="lens-hl" />
      </template>

      <!-- 圆框描边 -->
      <path :d="circleA" class="ring" />
      <path :d="circleB" class="ring" />

      <!-- 区域概率标签（条件视图下只保留交叠区，其余属新样本空间外部） -->
      <text v-if="cond === 'none' && pAonly > 0.004" :x="cxA - R * 0.45" :y="CY + 5" class="lbl" text-anchor="middle">{{ fmt(pAonly) }}</text>
      <text v-if="cond === 'none' && pBonly > 0.004" :x="cxB + R * 0.45" :y="CY + 5" class="lbl" text-anchor="middle">{{ fmt(pBonly) }}</text>
      <text v-if="ab > 0.004" :x="CX" :y="CY - 8" class="lbl" text-anchor="middle">{{ fmt(ab) }}</text>
      <text v-if="cond === 'none' && pNeither > 0.004" :x="CX" :y="OY + 26" class="lbl" text-anchor="middle">{{ fmt(pNeither) }}</text>

      <!-- A / B 名称 -->
      <text :x="cxA" :y="CY - R - 8" class="name" text-anchor="middle">A</text>
      <text :x="cxB" :y="CY + R + 16" class="name" text-anchor="middle">B</text>
    </svg>

    <!-- 条件视图（第二节）：切换被条件事件 -->
    <template v-if="mode === 'cond'">
      <div class="cond-btns">
        <button class="chip" :class="{ active: cond === 'B' }" @click="cond = 'B'">以 B 为条件</button>
        <button class="chip" :class="{ active: cond === 'A' }" @click="cond = 'A'">以 A 为条件</button>
      </div>

      <!-- 条件视图读数：P(A|B) = P(A∩B) / P(B) -->
      <div class="readout cond">
        P({{ cond === 'B' ? 'A' : 'B' }} | {{ cond }}) = P(A∩B) / P({{ cond }})
        = {{ fmtPct(ab) }} / {{ fmtPct(condDenom) }}
        = <strong>{{ condProbText }}</strong>
      </div>
    </template>

    <!-- 集合视图（第一节）：交/并/补/差区域选择 -->
    <template v-else>
      <div class="chips">
        <button
          v-for="k in REGION_ORDER"
          :key="k"
          class="chip"
          :class="{ active: selected === k, disabled: !regions[k] }"
          :disabled="!regions[k]"
          @click="toggleRegion(k)"
        >
          {{ regions[k]?.label }}
        </button>
      </div>

      <!-- 选中区域读数 -->
      <div v-if="selRegion" class="readout">
        <span class="readout-set">当前区域：{{ selRegion.label }}</span>
        <span class="readout-prob">P = {{ fmtPct(selProb ?? 0) }}</span>
      </div>
    </template>

    <!-- 关键概率 -->
    <div class="stats">
      <div class="stat"><span class="k">P(A∩B)</span><span class="v">{{ fmtPct(ab) }}</span></div>
      <div class="stat"><span class="k">P(A∪B)</span><span class="v">{{ fmtPct(pUnion) }}</span></div>
      <div class="stat"><span class="k">P(A|B)</span><span class="v">{{ fmtPct(pAgivenB) }}</span></div>
      <div class="stat"><span class="k">P(B|A)</span><span class="v">{{ fmtPct(pBgivenA) }}</span></div>
    </div>
    <div class="status" :class="{ ind: isIndependent, exc: isMutuallyExclusive }">{{ statusText }}</div>

    <!-- 控制 -->
    <div class="controls">
      <div class="control-row">
        <span class="control-label">P(A)</span>
        <input v-model.number="pA" type="range" min="0" max="1" step="0.01" class="slider" />
        <span class="control-value">{{ fmtPct(pA) }}</span>
      </div>
      <div class="control-row">
        <span class="control-label">P(B)</span>
        <input v-model.number="pB" type="range" min="0" max="1" step="0.01" class="slider" />
        <span class="control-value">{{ fmtPct(pB) }}</span>
      </div>
      <div class="control-row">
        <span class="control-label">P(A∩B)</span>
        <input v-model.number="abSlider" type="range" min="0" :max="maxAB" step="0.01" class="slider" />
        <span class="control-value">{{ fmtPct(ab) }}</span>
      </div>
      <div class="quick">
        <button class="quick-btn" :class="{ on: isMutuallyExclusive }" @click="setExclusive">互斥（A∩B=∅）</button>
        <button class="quick-btn" :class="{ on: isIndependent }" @click="setIndependent">独立（P(A∩B)=P(A)P(B)）</button>
      </div>
    </div>

    <div class="tip">区域大小仅示意，概率以数值为准（教学示意，非真实数据）。</div>
  </div>
</template>

<style scoped>
.venn { padding: 16px; }
.diagram { width: 100%; height: auto; max-width: 480px; display: block; margin: 0 auto; }
.space { fill: var(--bg-hover); stroke: var(--border); stroke-width: 1.5; }
.omega { font-size: 18px; font-style: italic; fill: var(--text-3); }
.set { opacity: 0.85; }
.set-a { fill: color-mix(in srgb, var(--primary) 28%, transparent); }
.set-b { fill: color-mix(in srgb, var(--warning) 28%, transparent); }
.set-lens { fill: color-mix(in srgb, var(--violet) 40%, transparent); }
.ring { fill: none; stroke: var(--text-3); stroke-width: 1.5; }
.dim { fill: color-mix(in srgb, var(--ink) 35%, transparent); }
.hl path {
  fill: var(--warning, #f59e0b);
  opacity: 0.92;
  stroke: var(--warning, #b45309);
  stroke-width: 1.5;
}
.lbl { font-size: 12.5px; font-weight: 600; fill: var(--text-2); }
.name { font-size: 15px; font-weight: 700; font-style: italic; fill: var(--text-1); }
.lens-hl { fill: var(--warning, #f59e0b); opacity: 0.92; stroke: var(--warning, #b45309); stroke-width: 1.5; }

.cond-btns { display: flex; flex-wrap: wrap; gap: 6px; justify-content: center; margin: 12px 0 6px; }

.chips { display: flex; flex-wrap: wrap; gap: 6px; justify-content: center; margin: 12px 0 6px; }
.chip {
  border: 1px solid var(--border);
  background: var(--bg-card);
  color: var(--text-2);
  font-size: 12px;
  padding: 3px 10px;
  border-radius: 999px;
  cursor: pointer;
}
.chip:hover { border-color: var(--primary); color: var(--primary); }
.chip.active { background: var(--primary); border-color: var(--primary); color: #fff; }
.chip.disabled { opacity: 0.35; cursor: not-allowed; }

.readout {
  display: flex;
  justify-content: center;
  gap: 10px;
  margin: 4px 0 10px;
  font-size: 13px;
}
.readout-set { color: var(--primary); font-weight: 600; }
.readout-prob { color: var(--text-2); }
.readout.cond { font-size: 13.5px; }
.readout.cond strong { color: var(--primary); font-weight: 700; }

.stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  margin-bottom: 8px;
}
.stat {
  background: var(--bg-hover);
  border-radius: var(--radius-sm);
  padding: 8px 6px;
  text-align: center;
}
.stat .k { display: block; font-size: 11.5px; color: var(--text-3); }
.stat .v { display: block; font-size: 15px; font-weight: 700; color: var(--text-1); }

.status {
  text-align: center;
  font-size: 13px;
  color: var(--text-2);
  margin-bottom: 12px;
  padding: 6px 10px;
  border-radius: var(--radius-sm);
  background: var(--bg-hover);
}
.status.exc { color: var(--danger, #dc2626); background: color-mix(in srgb, var(--danger, #dc2626) 8%, transparent); }
.status.ind { color: var(--primary); background: var(--primary-soft); }

.controls { border-top: 1px solid var(--border); padding-top: 10px; display: flex; flex-direction: column; gap: 8px; }
.control-row { display: flex; align-items: center; gap: 10px; }
.control-label { width: 74px; font-size: 12.5px; color: var(--text-2); flex-shrink: 0; }
.slider { flex: 1; accent-color: var(--primary); cursor: pointer; }
.control-value { width: 52px; font-size: 12.5px; font-weight: 600; color: var(--primary); text-align: right; flex-shrink: 0; }
.quick { display: flex; gap: 8px; }
.quick-btn {
  flex: 1;
  font-size: 12.5px;
  padding: 6px 8px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-card);
  color: var(--text-2);
  cursor: pointer;
}
.quick-btn:hover { border-color: var(--primary); }
.quick-btn.on { border-color: var(--primary); background: var(--primary-soft); color: var(--primary); font-weight: 600; }
.tip { margin-top: 10px; font-size: 12px; color: var(--text-3); text-align: center; }
</style>
