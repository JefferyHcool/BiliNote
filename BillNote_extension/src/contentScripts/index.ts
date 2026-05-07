import { createApp } from 'vue'
import App from './views/App.vue'
import { setupApp } from '~/logic/common-setup'
import { detectPlatform } from '~/logic/platform'

// 只在支持的视频平台上挂悬浮按钮，避免污染其他网站
(() => {
  if (!detectPlatform(window.location.href))
    return

  const container = document.createElement('div')
  container.id = __NAME__
  const root = document.createElement('div')
  const styleEl = document.createElement('link')
  const shadowDOM = container.attachShadow?.({ mode: __DEV__ ? 'open' : 'closed' }) || container
  styleEl.setAttribute('rel', 'stylesheet')
  styleEl.setAttribute('href', browser.runtime.getURL('dist/contentScripts/style.css'))
  shadowDOM.appendChild(styleEl)
  shadowDOM.appendChild(root)
  document.body.appendChild(container)
  const app = createApp(App)
  setupApp(app)
  app.mount(root)
})()
