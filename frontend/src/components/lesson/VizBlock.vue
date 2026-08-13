<script setup lang="ts">
import { computed, ref } from 'vue'
import { Image, RotateCcw } from 'lucide-vue-next'
import { createMarkdown } from '../../utils/markdownIt'
import { vizRegistry, type VizKey } from './vizRegistry'

// 图注渲染器：支持 LaTeX（与正文同一套 markdown-it + katex）
const captionMd = createMarkdown({ breaks: false })

const props = defineProps<{
  component: VizKey
  params?: Record<string, unknown>
  caption?: string  // 图注
}>()

// 重置：递增 key 强制重挂载模拟器组件，一键回到初始设置值
const resetKey = ref(0)
function reset() {
  resetKey.value++
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
  <figure class="viz-figure">
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
    <!-- 图注行：说明这张"图"是什么、怎么互动（支持 LaTeX）；右侧是重置按钮 -->
    <div class="viz-bottom">
      <figcaption class="viz-caption" v-html="captionHtml"></figcaption>
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
