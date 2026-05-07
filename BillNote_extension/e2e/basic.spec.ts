import { expect, isDevArtifact, name, test } from './fixtures'

test('example test', async ({ page }, testInfo) => {
  testInfo.skip(!isDevArtifact(), 'contentScript is in closed ShadowRoot mode')

  await page.goto('https://example.com')

  await page.locator(`#${name} button`).click()
  await expect(page.locator(`#${name} h1`)).toHaveText('Vitesse WebExt')
})

test('popup page', async ({ page, extensionId }) => {
  await page.goto(`chrome-extension://${extensionId}/dist/popup/index.html`)
  await expect(page.locator('button')).toHaveText('Open Options')
})

test('options page', async ({ page, extensionId }) => {
  await page.goto(`chrome-extension://${extensionId}/dist/options/index.html`)
  await expect(page.locator('img')).toHaveAttribute('alt', 'extension icon')
})
