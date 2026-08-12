import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

// 端口规划（避免冲突）：
//   5432 PostgreSQL | 8000 QuantLab 后端 | 8100 Quantlerning 后端 | 5173 前端
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    strictPort: true, // 端口被占用时直接报错，避免静默换端口导致 CORS 失配
    allowedHosts: true, // 内网映射（cloudflared/花生壳）使用外部域名访问，放行任意 Host
    proxy: {
      // 开发时代理到后端，前端代码里统一用 /api 前缀
      '/api': {
        target: 'http://localhost:8100',
        changeOrigin: true,
      },
    },
  },
})
