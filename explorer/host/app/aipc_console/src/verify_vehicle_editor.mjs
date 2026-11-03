import { chromium } from '../vehicle-assembly-preview/node_modules/playwright/index.mjs'
const browser = await chromium.launch({ executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', headless: true, args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] })
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
const errors = []
page.on('pageerror', e => errors.push(e.message))
await page.goto('http://localhost:7100/', { waitUntil: 'networkidle', timeout: 60000 })
await page.waitForFunction(() => document.getElementById('app')?.edit3dProject, { timeout: 60000 })
const result = await page.evaluate(async () => {
  const project = document.getElementById('app').edit3dProject
  const editor = project.currentEditor || project.editor || project
  const materials = editor.asset.getMaterials().map(m => ({ id: m.id, name: m.name }))
  const original = editor.asset.getParam('vehicle', 'position')
  await editor.asset.updateParam('vehicle', 'position', [original[0] + 0.03, original[1], original[2]])
  const changed = editor.asset.getParam('vehicle', 'position')
  await editor.asset.updateParam('vehicle', 'position', original)
  const restored = editor.asset.getParam('vehicle', 'position')
  await editor.save?.()
  return { materials, original, changed, restored }
})
await page.waitForTimeout(900)
await page.reload({ waitUntil: 'networkidle' })
await page.waitForFunction(() => document.getElementById('app')?.edit3dProject, { timeout: 60000 })
result.afterReload = await page.evaluate(() => { const p = document.getElementById('app').edit3dProject; return (p.currentEditor || p.editor || p).asset.getParam('vehicle', 'position') })
result.errors = errors
console.log(JSON.stringify(result, null, 2))
await browser.close()
