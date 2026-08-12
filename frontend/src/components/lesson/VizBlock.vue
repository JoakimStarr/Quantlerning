<script setup lang="ts">
import { computed } from 'vue'
import MarkdownIt from 'markdown-it'
import mathPlugin from '../../utils/markdownMath'
import { vizRegistry, type VizKey } from './vizRegistry'

// 图注渲染器：支持 LaTeX（与正文同一套 markdown-it + katex）
const captionMd = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: false,
}).use(mathPlugin, {
  throwOnError: false,
  errorColor: '#dc2626',
})

const props = defineProps<{
  component: VizKey
  params?: Record<string, unknown>
  caption?: string  // 图注
}>()

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
      <!-- 已实现：渲染真实组件 -->
      <component :is="info?.comp" v-if="hasComp && info" :params="params" />

      <!-- 未实现：插图占位 -->
      <div v-else class="viz-placeholder">
        <span class="viz-icon">🖼️</span>
        <div class="viz-text">
          <div class="viz-name">{{ title }}</div>
          <div class="viz-desc">{{ desc }}</div>
        </div>
      </div>
    </div>
    <!-- 图注：说明这张"图"是什么、怎么互动（支持 LaTeX） -->
    <figcaption class="viz-caption" v-html="captionHtml"></figcaption>
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
.viz-caption {
  margin-top: 8px;
  font-size: 12.5px;
  color: var(--text-3);
  line-height: 1.6;
}
.viz-caption :deep(p) {
  margin: 0;
}
.viz-caption :deep(.katex) {
  font-size: 1em;
}
</style>
