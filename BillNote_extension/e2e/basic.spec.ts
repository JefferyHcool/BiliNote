import { expect, isDevArtifact, name, test } from './fixtures'

test('content script injects floating button on video pages', async ({ page }, testInfo) => {
  testInfo.skip(!isDevArtifact(), 'contentScript is in closed ShadowRoot mode in production builds')

  // Mock a Bilibili video page so the content script detects the platform without real network
  await page.route('https://www.bilibili.com/**', route => route.fulfill({
    status: 200,
    contentType: 'text/html',
    body: '<html><body></body></html>',
  }))

  await page.goto('https://www.bilibili.com/video/BV1xx411c7mD')

  // Content script mounts a container with id=<extension-name> only on supported video pages
  await expect(page.locator(`#${name}`)).toBeAttached()
  // In dev mode (open shadow DOM) the floating BiliNote button is visible inside
  await expect(page.locator(`#${name} button`)).toContainText('BiliNote')
})

test('popup page', async ({ page, extensionId }) => {
  await page.goto(`chrome-extension://${extensionId}/dist/popup/index.html`)

  // Popup shows BiliNote branding
  await expect(page.locator('header')).toContainText('BiliNote')
  // Settings link is present
  await expect(page.getByRole('button', { name: '设置', exact: true })).toBeVisible()
  // Main generate action is rendered (may be disabled when no provider configured)
  await expect(page.getByRole('button', { name: /生成笔记|提交中/ })).toBeVisible()
})

test('options page', async ({ page, extensionId }) => {
  await page.goto(`chrome-extension://${extensionId}/dist/options/index.html`)

  // Options page shows BiliNote branding in the sidebar
  await expect(page.getByText('BiliNote').first()).toBeVisible()
  await expect(page.getByText('浏览器插件设置')).toBeVisible()
  // Navigation tabs are rendered
  await expect(page.getByRole('button', { name: '通用' })).toBeVisible()
  await expect(page.getByRole('button', { name: '模型供应商' })).toBeVisible()
})
