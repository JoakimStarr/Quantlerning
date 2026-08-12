<template>
  <div class="app-error" role="alert">
    <p class="app-error-msg">⚠️ {{ message || '加载失败' }}</p>
    <button class="btn btn-primary btn-sm" @click="$emit('retry')">重试</button>
  </div>
</template>

<script setup lang="ts">
defineProps<{ message?: string }>()
defineEmits<{ (e: 'retry'): void }>()
</script>

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
.app-error-msg { color: var(--danger); line-height: 1.7; }
</style>
