<script setup lang="ts">
// AI 学习规划结果渲染（懒加载组件）：把 markdown-it + KaTeX 从 Home 首屏剥离，
// 仅在用户生成规划后才加载。渲染逻辑与 AiAskPanel/ExerciseBlock 的 renderBubble 一致。
import { computed } from 'vue'
import { createMarkdown } from '@/utils/markdownIt'
const props = defineProps<{ plan: string }>()

const md = createMarkdown()

const html = computed(() => {
  const normalized = props.plan
    .replace(/\$\$([\s\S]+?)\$\$/g, (_, m: string) => `$${m.trim()}$`)
    .replace(/\\\[([\s\S]+?)\\\]/g, (_, m: string) => `$${m.trim()}$`)
    .replace(/\\\(([\s\S]+?)\\\)/g, (_, m: string) => `$${m.trim()}$`)
  return md.render(normalized)
})
</script>

<template>
  <div class="plan-body" v-html="html"></div>
</template>

<style scoped>
.plan-body {
  margin-top: 12px;
  font-size: 14px;
  line-height: 1.75;
  color: var(--text-1);
  border-top: 1px dashed var(--border);
  padding-top: 12px;
}
.plan-body :deep(p) { margin: 0 0 8px; }
.plan-body :deep(p:last-child) { margin-bottom: 0; }
.plan-body :deep(ul), .plan-body :deep(ol) { margin: 0 0 8px; padding-left: 1.4em; }
.plan-body :deep(li) { margin-bottom: 2px; }
.plan-body :deep(strong) { font-weight: 600; }
.plan-body :deep(.katex) { font-size: 1em; }
.plan-body :deep(pre) {
  background: var(--bg-code);
  color: var(--text-1);
  border-radius: var(--radius-md);
  padding: 10px 12px;
  overflow-x: auto;
  margin: 0 0 10px;
  font-size: 13px;
  line-height: 1.6;
}
.plan-body :deep(pre code) {
  background: none;
  color: inherit;
  padding: 0;
  font-size: 13px;
}
</style>
