import { chromium } from '../vehicle-assembly-preview/node_modules/playwright/index.mjs'
import fs from 'node:fs/promises'

const browser = await chromium.launch({
  executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  headless: true,
  args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'],
})
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 })
const errors = []
page.on('pageerror', error => errors.push(error.message))
page.on('console', message => { if (message.type() === 'error') errors.push(message.text()) })
await page.goto('http://localhost:7100/', { waitUntil: 'networkidle', timeout: 60000 })
await page.waitForFunction(() => { const p = document.getElementById('app')?.edit3dProject; return document.getElementById('app')?.edit3dPreview || p?.currentEditor }, { timeout: 60000 })
await page.screenshot({ path: 'C:/Users/25298/Desktop/FPGA/离线规划/输出/全车三维主视角.png' })
const info = await page.evaluate(async () => {
  const project = document.getElementById('app').edit3dProject
  const preview = document.getElementById('app').edit3dPreview || project.currentEditor
  const { scene } = preview.getScene ? preview.getScene() : { scene: preview.scene }
  const materials = new Map(), names = []
  let meshes = 0, triangles = 0
  scene.traverse(o => {
    if (o.name) names.push(o.name)
    if (!o.isMesh) return
    meshes++
    triangles += (o.geometry.index?.count || o.geometry.attributes.position.count) / 3
    for (const m of [o.material].flat()) materials.set(m.uuid, m.name)
  })
  const { contactSheet } = await import('/src/kit/edit3d.js')
  contactSheet({ subject: 'vehicle' })
  return { meshes, triangles, materials: [...materials.values()], names, errors: [] }
})
await new Promise(resolve => setTimeout(resolve, 700))
await page.screenshot({ path: 'C:/Users/25298/Desktop/FPGA/离线规划/输出/全车三维多视角.png' })
await fs.writeFile('C:/Users/25298/Desktop/FPGA/离线规划/输出/全车三维运行检查.json', JSON.stringify({ ...info, errors }, null, 2))
console.log(JSON.stringify({ ...info, errors }, null, 2))
await browser.close()
