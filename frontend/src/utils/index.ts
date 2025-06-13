// 解析URL
export function parseUrl(url: string): { protocol: string, host: string, path: string } {
  const urlObj = new URL(url);
  return {
    protocol: urlObj.protocol,
    host: urlObj.host,
    path: urlObj.pathname
  };
}