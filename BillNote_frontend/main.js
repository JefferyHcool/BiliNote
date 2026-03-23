import express from 'express'
import { createProxyMiddleware } from 'http-proxy-middleware'
import path from 'path'
import { fileURLToPath } from 'url'

const app = express()
const host = 'localhost'
const port = 4001
const target = 'http://localhost:8483'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const distDir = path.join(__dirname, 'dist')
const indexFile = path.join(distDir, 'index.html')

// /api 请求优先转发到后端（保留 /api 前缀）
app.use(createProxyMiddleware({
  pathFilter: '/api',
  target,
  changeOrigin: true,
  pathRewrite: path => (path.startsWith('/api') ? path : `/api${path}`),
}))

// 静态资源服务
app.use(express.static(distDir))

// SPA 路由回退（Express 5 避免使用 '*'）
app.get('/{*path}', (_req, res) => {
  res.sendFile(indexFile)
})

app.listen(port, host, () => {
  console.log(`Express 静态服务 + 代理启动：http://${host}:${port}`)
})