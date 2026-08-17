<script setup lang="ts">
import { computed, inject, ref } from 'vue'
import { getInstanceByDom } from 'echarts/core'
import { Image, MessageSquareText, RotateCcw } from 'lucide-vue-next'
import { createMarkdown } from '../../utils/markdownIt'
import { chartDataToText } from '../../utils/chartToText'
import { ASK_AI_KEY } from '../../utils/aiAskKey'
import { vizRegistry, type VizKey } from './vizRegistry'

// 图注渲染器：支持 LaTeX（与正文同一套 markdown-it + katex）
const captionMd = createMarkdown({ breaks: false })

const props = defineProps<{
  component: VizKey
  params?: Record<string, unknown>
  caption?: string  // 图注
  lessonId?: string
  sectionIndex?: number
}>()

// 重置：递增 key 强制重挂载模拟器组件，一键回到初始设置值
const resetKey = ref(0)
function reset() {
  resetKey.value++
}

const figRef = ref<HTMLElement | null>(null)

// 「问 AI」：由课程页注入（打开 AI 追问面板并预填问题），图表问 AI 入口
const askAi = inject(ASK_AI_KEY, undefined)

// 从渲染出的 ECharts 实例提取真实数据文本（模型无视觉，但能读数值）；
// 非 ECharts 或提取失败时回退为纯元信息
function extractChartData(): string {
  try {
    const el = figRef.value?.querySelector<HTMLElement>('[_echarts_instance_]')
    if (!el) return ''
    const inst = getInstanceByDom(el)
    if (!inst || typeof inst.getOption !== 'function') return ''
    return chartDataToText(inst.getOption())
  } catch {
    return ''
  }
}

function askAboutChart() {
  if (!askAi) return
  const paramText = props.params ? JSON.stringify(props.params) : ''
  const chartText = extractChartData()
  const parts = [
    `请讲解这张可视化图：${props.component}`,
    props.caption ? `图注：${props.caption}` : '',
    paramText ? `参数：${paramText}` : '',
  ]
  if (chartText) parts.push(`图表数据（节选）：\n${chartText}`)
  parts.push('我看不懂，请结合当前小节用 2-4 句话讲清楚图表达什么、怎么看。')
  askAi(parts.join('。'))
}

const info = computed(() => vizRegistry[props.component])
const hasComp = computed(() => !!info.value?.comp)
const title = computed(() => info.value?.title || props.component)
const desc = computed(() => info.value?.desc || '未知组件')
// 图注走 markdown 渲染（含 LaTeX）；无 caption 时回退「图：标题——描述」
const captionHtml = computed(() =>
  captionMd.render(props.caption || `图：${title.value}——${desc.value}`)
)
</script>

<template>
  <!-- 插图式可视化：像书中的图，居中、带图注 -->
  <figure ref="figRef" class="viz-figure">
    <div class="viz-frame">
      <!-- 已实现：渲染真实组件（:key 变化时重挂载，重置交互状态） -->
      <component
        :is="info?.comp"
        v-if="hasComp && info"
        :key="resetKey"
        :params="params"
      />

      <!-- 未实现：插图占位 -->
      <div v-else class="viz-placeholder">
        <span class="viz-icon"><Image :size="28" /></span>
        <div class="viz-text">
          <div class="viz-name">{{ title }}</div>
          <div class="viz-desc">{{ desc }}</div>
        </div>
      </div>
    </div>
    <!-- 图注行：说明这张"图"是什么、怎么互动（支持 LaTeX）；右侧是「问 AI」与重置按钮 -->
    <div class="viz-bottom">
      <div class="viz-caption" v-html="captionHtml"></div>
      <button
        v-if="askAi"
        class="viz-reset"
        title="看不懂这张图？问 AI 结合当前小节讲解"
        aria-label="看不懂这张图？问 AI"
        @click="askAboutChart"
      >
        <span class="viz-reset-icon"><MessageSquareText :size="13" /></span>
        <span>问 AI</span>
      </button>
      <button
        v-if="hasComp"
        class="viz-reset"
        title="重置为初始设置"
        aria-label="重置为初始设置"
        @click="reset"
      >
        <span class="viz-reset-icon"><RotateCcw :size="13" /></span>
        <span>重置</span>
      </button>
    </div>
  </figure>
</template>

<style scoped>
.viz-figure {
  margin: 22px 0;
  text-align: center;
}
.viz-frame {
  display: inline-block;
  width: 100%;
  max-width: 720px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
  background: var(--bg-card);
  box-shadow: var(--shadow-sm);
  text-align: left;
}
/* 图注行：图注文字 + 右侧重置按钮 */
.viz-bottom {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin: 8px auto 0;
  max-width: 720px;
  text-align: left;
}
.viz-caption {
  flex: 1;
  font-size: 12.5px;
  color: var(--text-3);
  line-height: 1.6;
}
.viz-reset {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-top: 2px;
  padding: 2px 10px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--bg-card);
  color: var(--text-3);
  font-size: 12px;
  line-height: 1.5;
  cursor: pointer;
  transition: all 0.15s;
}
.viz-reset:hover {
  color: var(--primary);
  border-color: var(--primary);
}
.viz-reset-icon { font-size: 12px; line-height: 1; }
.viz-placeholder {
  height: 200px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 14px;
  background: linear-gradient(180deg, var(--bg-card), var(--bg-hover));
  color: var(--text-3);
  text-align: left;
}
.viz-icon { font-size: 30px; }
.viz-name { font-family: var(--font-mono); font-size: 13px; color: var(--primary); margin-bottom: 4px; }
.viz-desc { font-size: 13px; color: var(--text-2); }
.viz-caption :deep(p) {
  margin: 0;
}
.viz-caption :deep(.katex) {
  font-size: 1em;
}
</style>
