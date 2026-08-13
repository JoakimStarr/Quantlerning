<script setup lang="ts">
import { computed, useAttrs } from 'vue'
import VChart from 'vue-echarts'
import { withChartTheme } from '@/utils/chartTheme'

// ECharts 图表包装：自动注入主题化的文字/网格/提示框颜色，
// 使所有模拟器在深浅色模式下与页面风格一致。
// 用法与 VChart 完全一致：<ThemedChart class="chart" :option="opt" autoresize />

defineOptions({ inheritAttrs: false })

const props = defineProps<{
  option: Record<string, any>
}>()

const attrs = useAttrs()
const opt = computed(() => withChartTheme(props.option))
</script>

<template>
  <VChart v-bind="attrs" :option="opt" />
</template>