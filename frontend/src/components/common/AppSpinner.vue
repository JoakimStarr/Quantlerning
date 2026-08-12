<template>
  <div class="app-loading" role="status" aria-live="polite">
    <span class="spinner" aria-hidden="true"></span>
    <span v-if="text" class="app-loading-text">{{ text }}</span>
  </div>
</template>

<script setup lang="ts">
defineProps<{ text?: string }>()
</script>

<style scoped>
.app-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 48px 20px;
  color: var(--text-3);
  font-size: 14px;
}
.spinner {
  width: 20px;
  height: 20px;
  border: 2px solid var(--border-strong);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: app-spin 0.8s linear infinite;
  flex-shrink: 0;
}
@keyframes app-spin {
  to { transform: rotate(360deg); }
}
</style>
