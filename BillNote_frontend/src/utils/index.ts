/**
 * 安全获取后端 origin，用于将 Markdown 中的根相对图片路径转为绝对 URL。
 *
 * 解析策略（按优先级）：
 * 1. VITE_API_BASE_URL 是完整 URL → 取 origin（如 https://api.example.com）
 * 2. VITE_API_BASE_URL 是根相对路径（如 /api）→ 拼 window.location.origin
 * 3. 未配置 → window.location.origin（Docker/nginx 代理场景，前后端同源）
 */
export function getBackendOrigin(): string {
  const raw = import.meta.env.VITE_API_BASE_URL
  if (!raw) return window.location.origin
  try {
    // 完整 URL（http://...、https://...）→ 直接取 origin
    const url = new URL(raw)
    return url.origin
  } catch {
    // 根相对路径（/api、/static 等）→ 拼当前页面 origin
    return window.location.origin
  }
}

/**
 * 将 Markdown 中根相对路径的图片（如 /static/screenshots/xxx.jpg）
 * 转换为绝对 URL，使复制/下载后的 Markdown 在外部工具中也能正常显示图片。
 * 已经是 http://、https://、data: 的图片不做处理。
 */
export function toPortableMarkdown(md: string, backendBaseUrl: string): string {
  const base = backendBaseUrl.replace(/\/$/, '')
  return md.replace(/!\[([^\]]*)\]\((?!https?:\/\/|data:|\/\/)(\/[^)]+)\)/g, (_, alt, path) => `![${alt}](${base}${path})`)
}

// 解析URL
export function parseUrl(url: string): { protocol: string, host: string, path: string } {
  const urlObj = new URL(url);
  return {
    protocol: urlObj.protocol,
    host: urlObj.host,
    path: urlObj.pathname
  };
}