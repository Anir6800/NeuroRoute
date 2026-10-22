// End-to-end check of the Topology Studio in real headless Chrome (DevTools Protocol, no extra dependencies; Node 22+).
// Needs the dev stack running (scripts/dev-neuro.sh). Usage:  node scripts/topology-e2e.mjs [outDir]
// Env: CHROME_PATH (default: Windows Chrome), NEUROROUTE_URL (default http://127.0.0.1:5173).
// Flow: sign in with the emulator test user -> open Topology Studio -> add six routers -> drag one node -> draw one link by
// dragging between handles -> add five more links with the form -> Save -> reload the page -> check the same network came back.
// Exits 1 if any check fails. Saves screenshots and e2e.json to outDir (default .ui-audit/, git-ignored).
import { spawn } from 'node:child_process'
import { mkdirSync, rmSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

const OUT = resolve(process.argv[2] ?? '.ui-audit')
const BASE = process.env.NEUROROUTE_URL ?? 'http://127.0.0.1:5173'
const PORT = 9334
const EMAIL = process.env.NEUROROUTE_EMAIL ?? 'dev@neuroroute.test'
const PASSWORD = process.env.NEUROROUTE_PASSWORD ?? 'devpass123'
mkdirSync(OUT, { recursive: true })
rmSync(`${OUT}/cdp-profile-e2e`, { recursive: true, force: true }) // a clean browser every run: no leftover session or last-opened topology

const chrome = spawn(process.env.CHROME_PATH ?? 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', [
  '--headless=new', '--disable-gpu', `--remote-debugging-port=${PORT}`, `--user-data-dir=${OUT}/cdp-profile-e2e`, 'about:blank',
], { stdio: 'ignore' })
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

async function connect() {
  for (let i = 0; i < 50; i++) {
    try {
      const page = (await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json()).find((t) => t.type === 'page')
      if (page) return page.webSocketDebuggerUrl
    } catch { /* not ready */ }
    await sleep(200)
  }
  throw new Error('Chrome did not start')
}

const ws = new WebSocket(await connect())
await new Promise((r) => (ws.onopen = r))
let id = 0
const pending = new Map()
const problems = []
ws.onmessage = (ev) => {
  const m = JSON.parse(ev.data)
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id) }
  if (m.method === 'Runtime.consoleAPICalled' && ['error', 'warning'].includes(m.params.type)) {
    problems.push(`${m.params.type}: ${m.params.args.map((a) => a.value ?? a.description).join(' ').slice(0, 200)}`)
  }
  if (m.method === 'Runtime.exceptionThrown') problems.push(`exception: ${m.params.exceptionDetails.text} ${m.params.exceptionDetails.exception?.description ?? ''}`.slice(0, 300))
  if (m.method === 'Log.entryAdded' && ['error', 'warning'].includes(m.params.entry.level)) problems.push(`log ${m.params.entry.level}: ${m.params.entry.text} ${m.params.entry.url ?? ''}`.slice(0, 220))
}
const send = (method, params = {}) => new Promise((res) => { const i = ++id; pending.set(i, res); ws.send(JSON.stringify({ id: i, method, params })) })
const evaluate = async (expression) => {
  const r = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })
  if (r.result?.exceptionDetails) throw new Error(`evaluate failed: ${r.result.exceptionDetails.exception?.description ?? r.result.exceptionDetails.text}`)
  return r.result?.result?.value
}
await send('Runtime.enable'); await send('Log.enable'); await send('Page.enable')
await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false })

const checks = []
const check = (name, ok, detail = '') => { checks.push({ name, ok: Boolean(ok), detail }); console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? '  ' + detail : ''}`) }
const until = async (what, fn, timeout = 8000) => {
  const t0 = Date.now()
  while (Date.now() - t0 < timeout) { if (await evaluate(fn)) return true; await sleep(100) }
  throw new Error(`timed out waiting for: ${what}`)
}
const shot = async (name) => writeFileSync(`${OUT}/${name}.png`, Buffer.from((await send('Page.captureScreenshot', { format: 'png' })).result.data, 'base64'))
const go = async (path) => { await send('Page.navigate', { url: BASE + path }); await sleep(500) }

const centre = (selector) => evaluate(`(() => { const e = document.querySelector(${JSON.stringify(selector)}); if (!e) return null; const r = e.getBoundingClientRect(); return { x: r.x + r.width / 2, y: r.y + r.height / 2 } })()`)
const mouse = (type, x, y, extra = {}) => send('Input.dispatchMouseEvent', { type, x, y, button: 'left', buttons: type === 'mouseReleased' ? 0 : 1, clickCount: 1, ...extra })
async function drag(from, to, steps = 8) {
  await mouse('mouseMoved', from.x, from.y); await mouse('mousePressed', from.x, from.y)
  for (let i = 1; i <= steps; i++) { await mouse('mouseMoved', from.x + ((to.x - from.x) * i) / steps, from.y + ((to.y - from.y) * i) / steps); await sleep(15) }
  await mouse('mouseReleased', to.x, to.y)
}
const clickButton = (name) => evaluate(`(() => { const b = [...document.querySelectorAll('button')].find((x) => x.textContent.trim() === ${JSON.stringify(name)}); if (!b) return false; b.click(); return true })()`)
const setSelect = (label, value) => evaluate(`(() => {
  const l = [...document.querySelectorAll('label')].find((x) => x.textContent.trim() === ${JSON.stringify(label)}); const s = document.getElementById(l.htmlFor);
  Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set.call(s, ${JSON.stringify(value)}); s.dispatchEvent(new Event('change', { bubbles: true })); return s.value })()`)
const setInput = (label, value) => evaluate(`(() => {
  const l = [...document.querySelectorAll('label')].find((x) => x.textContent.trim() === ${JSON.stringify(label)}); const s = document.getElementById(l.htmlFor);
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(s, ${JSON.stringify(value)}); s.dispatchEvent(new Event('input', { bubbles: true })); return s.value })()`)
const snapshot = () => evaluate(`(() => ({
  nodes: [...document.querySelectorAll('.react-flow__node')].map((n) => ({ id: n.dataset.id, t: n.style.transform })).sort((a, b) => a.id.localeCompare(b.id)),
  edges: document.querySelectorAll('.react-flow__edge').length,
  name: document.getElementById([...document.querySelectorAll('label')].find((x) => x.textContent.trim() === 'Name')?.htmlFor)?.value,
  pill: document.querySelector('.topo-toolbar .pill')?.textContent.trim(),
  meta: [...document.querySelectorAll('.topo-form__meta')].map((p) => p.textContent.trim()).find((t) => /nodes? ·/.test(t)),
}))()`)

try {
  // 1. sign in (Firebase Auth emulator) on the login page
  await go('/login')
  await until('login form', `!!document.querySelector('input[type=email]')`)
  await evaluate(`(() => { const set = (el, v) => { Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(el, v); el.dispatchEvent(new Event('input', { bubbles: true })) };
    set(document.querySelector('input[type=email]'), ${JSON.stringify(EMAIL)}); set(document.querySelector('input[type=password]'), ${JSON.stringify(PASSWORD)});
    document.querySelector('button[type=submit]').click() })()`)
  await until('signed in', `/Signed in as/.test(document.body.textContent)`, 15000)
  check('signs in with the emulator test user', true)

  // 2. open the studio in a fresh page load (the session must survive it)
  await go('/topology')
  await until('studio toolbar', `!!document.querySelector('[role=toolbar][aria-label="Topology actions"]')`)
  const first = await snapshot()
  check('the studio opens empty (no invented network)', first.nodes.length === 0 && /Empty canvas/.test(await evaluate('document.body.textContent')))
  check('no sign-in banner while signed in', !(await evaluate(`[...document.querySelectorAll('[role=alert]')].some((a) => /not signed in/i.test(a.textContent))`)))
  await shot('topology-1-empty')

  // 3. six routers
  for (let i = 0; i < 6; i++) await clickButton('Add router')
  await until('six nodes measured and visible', `document.querySelectorAll('.react-flow__node').length === 6 && [...document.querySelectorAll('.react-flow__node')].every((n) => n.style.visibility !== 'hidden')`)
  check('six routers on the canvas', (await snapshot()).nodes.length === 6)

  // 4. drag r1 with the mouse
  const before = (await snapshot()).nodes.find((n) => n.id === 'r1').t
  const r1 = await centre('.react-flow__node[data-id="r1"]')
  await drag(r1, { x: r1.x + 70, y: r1.y + 50 })
  await sleep(300)
  const after = (await snapshot()).nodes.find((n) => n.id === 'r1').t
  check('dragging a node moves it', before !== after, `${before} -> ${after}`)

  // 5. draw a link by dragging from r1's right handle to r2's left handle
  const handleOut = await centre('.react-flow__node[data-id="r1"] .react-flow__handle.source')
  const handleIn = await centre('.react-flow__node[data-id="r2"] .react-flow__handle.target')
  await drag(handleOut, handleIn, 12)
  await sleep(300)
  check('dragging between handles adds a link', (await snapshot()).edges === 1 && (await evaluate('document.body.textContent')).includes('Link r1-r2'))

  // 5b. a drag from a node's output back onto its own input must not create a link
  const selfOut = await centre('.react-flow__node[data-id="r3"] .react-flow__handle.source')
  const selfIn = await centre('.react-flow__node[data-id="r3"] .react-flow__handle.target')
  await drag(selfOut, selfIn, 12)
  await sleep(300)
  check('dragging a node onto itself adds no link', (await snapshot()).edges === 1 && !/same node/i.test(await evaluate(`document.querySelector('.topo-notice')?.textContent ?? ''`)))

  // 6. the other five links with the form
  for (const [a, b] of [['r2', 'r3'], ['r3', 'r4'], ['r4', 'r5'], ['r5', 'r6'], ['r6', 'r1']]) {
    await setSelect('From', a); await setSelect('To', b)
    await clickButton('Add link')
  }
  await until('six links', `document.querySelectorAll('.react-flow__edge').length === 6`)
  check('six links and no problems', (await evaluate('document.body.textContent')).includes('No problems found.'))

  // 7. name, save
  await setInput('Name', 'Six-router ring (e2e)')
  await shot('topology-2-before-save')
  await clickButton('Save')
  await until('saved', `/Saved as version 1\\./.test(document.body.textContent)`)
  const saved = await snapshot()
  check('saving reports version 1', saved.pill === '✓ Saved (v1)', saved.pill)

  // 8. reload the whole page
  await go('/topology')
  await until('studio back', `document.querySelectorAll('.react-flow__node').length === 6 && document.querySelectorAll('.react-flow__edge').length === 6`)
  await until('nodes visible', `[...document.querySelectorAll('.react-flow__node')].every((n) => n.style.visibility !== 'hidden')`)
  const reloaded = await snapshot()
  check('reload brings back six routers and six links', reloaded.nodes.length === 6 && reloaded.edges === 6)
  check('reload keeps the name', reloaded.name === 'Six-router ring (e2e)', reloaded.name)
  check('reload keeps every node position', JSON.stringify(reloaded.nodes) === JSON.stringify(saved.nodes), `${JSON.stringify(reloaded.nodes.find((n) => n.id === 'r1'))}`)
  check('reload shows the saved version', reloaded.pill === '✓ Saved (v1)' && /6 nodes · 6 links · saved as version 1/.test(reloaded.meta ?? ''), `${reloaded.pill} | ${reloaded.meta}`)
  await shot('topology-3-after-reload')

  // 9. nothing noisy in the console
  const noise = problems.filter((p) => !/favicon/i.test(p))
  check('no console errors or warnings', noise.length === 0, noise.slice(0, 3).join(' | '))
} catch (e) {
  check('run completed', false, String(e.message ?? e))
  await shot('topology-failure').catch(() => {})
} finally {
  writeFileSync(`${OUT}/e2e.json`, JSON.stringify({ checks, problems }, null, 2))
  ws.close()
  chrome.kill()
}
const failed = checks.filter((c) => !c.ok)
console.log(`\n${checks.length - failed.length}/${checks.length} checks passed`)
process.exit(failed.length ? 1 : 0)
