import { defineConfig, type Plugin } from 'vite'
import vue from '@vitejs/plugin-vue'
import viteCompression from 'vite-plugin-compression'
import { fileURLToPath, URL } from 'node:url'
import type { OutputBundle } from 'rollup'

// katex 字体裁剪：CSS 里 src 顺序是 woff2, woff, ttf，现代浏览器只下载 woff2。
// 删除 woff/ttf 冗余（约 876K），缺失文件不影响（浏览器首选 woff2）。
const stripKatexFonts: Plugin = {
  name: 'strip-katex-fonts',
  generateBundle(_opts, bundle: OutputBundle) {
    for (const key of Object.keys(bundle)) {
      if (/^assets\/KaTeX_.*\.(woff|ttf)$/.test(key)) delete bundle[key]
    }
  },
}

// 端口规划（避免冲突）：
//   5432 PostgreSQL | 8000 QuantLab 后端 | 8100 Quantlerning 后端 | 5173 前端
export default defineConfig({
  plugins: [
    vue(),
    // 预压缩静态资源：后端按 Accept-Encoding 分发（.br 优先，.gz 兜底），比运行时 gzip 更小
    viteCompression({ algorithm: 'brotliCompress', ext: '.br', threshold: 1024 }),
    viteCompression({ algorithm: 'gzip', ext: '.gz', threshold: 1024 }),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    host: true, // 监听所有网卡：局域网设备/手机可经本机 IP 访问
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
  build: {
    chunkSizeWarningLimit: 900, // 大 vendor 拆分后仍超 500KB 的 chunk 不报警
    rollupOptions: {
      plugins: [stripKatexFonts],
      output: {
        manualChunks: {
          'vue-vendor': ['vue', 'vue-router'],
          'echarts': ['echarts', 'zrender', 'vue-echarts'],
          'katex': ['katex'],
          'mathjs': ['mathjs'],
        },
      },
    },
  },
})
