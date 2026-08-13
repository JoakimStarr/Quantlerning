<script setup lang="ts">
import { AlertTriangle } from 'lucide-vue-next'
defineProps<{ message?: string }>()
defineEmits<{ (e: 'retry'): void }>()
</script>

<template>
  <div class="app-error" role="alert">
    <p class="app-error-msg"><AlertTriangle :size="16" class="err-icon" /> {{ message || '加载失败' }}</p>
    <button class="btn btn-primary btn-sm" @click="$emit('retry')">重试</button>
  </div>
</template>

<style scoped>
.app-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 48px 20px;
  color: var(--text-2);
  font-size: 14px;
  text-align: center;
}
.app-error-msg { color: var(--danger); line-height: 1.7; display: flex; align-items: center; justify-content: center; gap: 6px; }
.err-icon { flex-shrink: 0; }
</style>
