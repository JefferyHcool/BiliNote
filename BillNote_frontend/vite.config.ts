import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import { fileURLToPath } from 'url'
import tailwindcss from '@tailwindcss/vite'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd() + '/../')

  const apiBaseUrl = env.VITE_API_BASE_URL || 'http://127.0.0.1:8483'
  const port = parseInt(env.VITE_FRONTEND_PORT || '3015', 10)

  return {
    base: './',
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    build: {
      rollupOptions: {
        output: {
          manualChunks: {
            markdown: ['react-markdown', 'react-syntax-highlighter', 'remark-gfm', 'remark-math', 'rehype-katex'],
            markmap: ['markmap-lib', 'markmap-view', 'markmap-toolbar', 'markmap-common'],
            vendor: ['react', 'react-dom', 'react-router-dom'],
          },
        },
      },
    },
    server: {
      host: '0.0.0.0',
      port: port,
      allowedHosts: true, // 允许任意域名访问
      proxy: {
        '/api': {
          target: apiBaseUrl,
          changeOrigin: true,
          rewrite: path => path.replace(/^\/api/, '/api'),
        },
        '/static': {
          target: apiBaseUrl,
          changeOrigin: true,
          rewrite: path => path.replace(/^\/static/, '/static'),
        },
      },
    },
  }
})
