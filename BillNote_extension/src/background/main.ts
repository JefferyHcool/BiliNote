import { onMessage } from 'webext-bridge/background'

// only on dev mode
if (import.meta.hot) {
  // @ts-expect-error for background HMR
  import('/@vite/client')
  // load latest content script
  import('./contentScriptHMR')
}

// 工具栏图标点击 → 打开 popup（默认行为，无需配置）
// side panel 留给 P3 阶段：在那时把 popup 替换成"action 行为"或加单独命令
// 此处不开启 openPanelOnActionClick，否则会绕过 default_popup

browser.runtime.onInstalled.addListener((): void => {
  // eslint-disable-next-line no-console
  console.log('BiliNote extension installed')
})

// 占位：未来 content script 通过 webext-bridge 触发任务时，由这里转发到后端
onMessage('get-current-tab', async () => {
  try {
    const [tab] = await browser.tabs.query({ active: true, currentWindow: true })
    return { title: tab?.title, url: tab?.url }
  }
  catch {
    return { title: undefined, url: undefined }
  }
})

