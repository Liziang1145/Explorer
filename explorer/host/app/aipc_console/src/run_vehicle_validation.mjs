import { spawn, spawnSync } from 'node:child_process'
const root = 'C:/Users/25298/Desktop/FPGA/vehicle-assembly-preview'
const server = spawn('npm', ['run', 'dev', '--', '--host', 'localhost', '--port', '7100'], { cwd: root, shell: true, stdio: 'ignore' })
try {
  let ready = false
  for (let i = 0; i < 60; i++) {
    try { if ((await fetch('http://localhost:7100/')).ok) { ready = true; break } } catch {}
    await new Promise(r => setTimeout(r, 500))
  }
  if (!ready) throw new Error('预览服务启动超时')
  for (const script of ['verify_vehicle_preview.mjs', 'verify_vehicle_editor.mjs']) {
    const result = spawnSync(process.execPath, [`C:/Users/25298/Desktop/FPGA/离线规划/${script}`], { stdio: 'inherit' })
    if (result.status !== 0) throw new Error(`${script} 检查失败`)
  }
} finally {
  if (server.pid) spawnSync('taskkill', ['/PID', String(server.pid), '/T', '/F'], { stdio: 'ignore' })
}
