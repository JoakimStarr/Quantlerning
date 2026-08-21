<script setup lang="ts">
import { ref } from 'vue'
import { ArrowLeftRight } from 'lucide-vue-next'
import HomeView2 from '@/views/HomeView2.vue'
import HomeView from '@/views/HomeView.vue'

// 首页版本偏好：v2（新版，默认）/ classic（经典版）。持久化到 localStorage，重进首页保持选择
const KEY = 'ql:homeVersion'
function loadVersion(): 'v2' | 'classic' {
  try {
    return localStorage.getItem(KEY) === 'classic' ? 'classic' : 'v2'
  } catch {
    return 'v2'
  }
}

const version = ref<'v2' | 'classic'>(loadVersion())

function toggleVersion() {
  version.value = version.value === 'v2' ? 'classic' : 'v2'
  try {
    localStorage.setItem(KEY, version.value)
  } catch {
    // 存储不可用：仅本次会话生效
  }
}
</script>

<template>
  <div class="home-host">
    <HomeView2 v-if="version === 'v2'" />
    <HomeView v-else />

    <!-- 首页版本切换（浮层小胶囊，随时可回到原版） -->
    <button class="ver-toggle" type="button" :title="version === 'v2' ? '切换到经典版首页' : '切换到新版首页'" @click="toggleVersion">
      <ArrowLeftRight :size="13" />
      {{ version === 'v2' ? '恢复经典版首页' : '体验新版首页' }}
    </button>
  </div>
</template>

<style scoped>
.ver-toggle {
  position: fixed;
  right: 16px;
  bottom: 16px;
  z-index: 60;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  font-family: var(--font-base);
  font-size: 12.5px;
  font-weight: 600;
  line-height: 1;
  color: var(--text-2);
  background: var(--bg-card);
  border: 1px solid var(--border-strong);
  border-radius: 999px;
  box-shadow: var(--shadow-md);
  cursor: pointer;
  user-select: none;
  transition: color 0.15s, border-color 0.15s, background 0.15s, box-shadow 0.15s;
}
.ver-toggle:hover {
  color: var(--primary);
  border-color: var(--primary);
  background: var(--primary-soft);
  box-shadow: var(--shadow-lg);
}
.ver-toggle:focus-visible {
  outline: 2px solid var(--primary);
  outline-offset: 2px;
}
</style>
