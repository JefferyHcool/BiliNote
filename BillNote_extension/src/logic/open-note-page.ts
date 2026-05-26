export type SidepanelViewMode = 'markdown' | 'mindmap' | 'chat'

export function buildSidepanelPageUrl(taskId?: string, view?: SidepanelViewMode): string {
  const params = new URLSearchParams()
  if (taskId)
    params.set('taskId', taskId)
  if (view)
    params.set('view', view)

  const query = params.toString()
  return browser.runtime.getURL(`dist/sidepanel/index.html${query ? `?${query}` : ''}`)
}

export async function openSidepanelPage(taskId?: string, view?: SidepanelViewMode) {
  await browser.tabs.create({
    url: buildSidepanelPageUrl(taskId, view),
  })
}
