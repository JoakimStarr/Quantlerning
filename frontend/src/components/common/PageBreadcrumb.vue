<template>
  <div class="page-crumb">
    <RouterLink to="/" class="crumb-link">学习地图</RouterLink>
    <span class="crumb-sep">/</span>
    <span class="crumb-current">{{ current }}</span>
  </div>
</template>

<script setup lang="ts">
defineProps<{ current: string }>()
</script>

<style scoped>
.page-crumb {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text-3);
  margin-bottom: 8px;
}
.crumb-link {
  color: var(--primary);
  text-decoration: none;
  background: none;
  border: none;
  cursor: pointer;
  padding: 0;
  font-size: 13px;
  font-family: inherit;
}
.crumb-link:hover {
  color: var(--primary-hover);
}
.crumb-sep,
.crumb-current {
  color: var(--text-3);
}
</style>