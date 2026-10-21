// UI audit: drives headless Chrome over the DevTools Protocol (no extra dependencies; Node 22+).
// Needs the dev stack running (scripts/dev-neuro.sh). Usage:  node scripts/ui-audit.mjs [outDir]
// Env: CHROME_PATH (default: Windows Chrome), NEUROROUTE_URL (default http://127.0.0.1:5173).
// Checks, at phone/tablet/desktop sizes in light and dark: horizontal overflow, console errors/warnings,
// a stray hamburger, and real dock clicks (route, title, pill position, focus, scroll reset, theme toggle).
// Exits 1 if any check fails. Screenshots and audit.json go to outDir (default .ui-audit/, git-ignored).
import { spawn } from 'node:child_process'
import { writeFileSync, mkdirSync } from 'node:fs'
import { resolve } from 'node:path'

const OUT = resolve(process.argv[2] ?? '.ui-audit') // Chrome needs an absolute profile path
const BASE = process.env.NEUROROUTE_URL ?? 'http://127.0.0.1:5173'
const PORT = 9333
mkdirSync(OUT, { recursive: true })

const chrome = spawn(process.env.CHROME_PATH ?? 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', [
  '--headless=new', '--disable-gpu', `--remote-debugging-port=${PORT}`, `--user-data-dir=${OUT}/cdp-profile`, 'about:blank',
], { stdio: 'ignore' })
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

async function connect() {
  for (let i = 0; i < 50; i++) {
    try {
      const res = await fetch(`http://127.0.0.1:${PORT}/json/list`)
      const page = (await res.json()).find((t) => t.type === 'page')
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
const consoleProblems = []
ws.onmessage = (ev) => {
  const m = JSON.parse(ev.data)
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id) }
  if (m.method === 'Runtime.consoleAPICalled' && ['error', 'warning'].includes(m.params.type)) {
    consoleProblems.push(`${m.params.type}: ${m.params.args.map((a) => a.value ?? a.description).join(' ').slice(0, 200)}`)
  }
  if (m.method === 'Runtime.exceptionThrown') consoleProblems.push(`exception: ${m.params.exceptionDetails.text} ${m.params.exceptionDetails.exception?.description ?? ''}`.slice(0, 300))
  if (m.method === 'Log.entryAdded' && ['error', 'warning'].includes(m.params.entry.level)) consoleProblems.push(`log ${m.params.entry.level}: ${m.params.entry.text} ${m.params.entry.url ?? ''}`.slice(0, 220))
}
const send = (method, params = {}) => new Promise((res) => { const i = ++id; pending.set(i, res); ws.send(JSON.stringify({ id: i, method, params })) })
const evaluate = async (expression) => { const r = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true }); return r.result?.result?.value }
await send('Runtime.enable'); await send('Log.enable'); await send('Page.enable')

async function open(url, { w, h, mobile = false, scheme = 'dark', reduced = false }) {
  await send('Emulation.setDeviceMetricsOverride', { width: w, height: h, deviceScaleFactor: 1, mobile })
  await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: scheme }, { name: 'prefers-reduced-motion', value: reduced ? 'reduce' : 'no-preference' }] })
  await send('Page.navigate', { url })
  await sleep(600)
  await evaluate(`new Promise(r => { const t0 = Date.now(); const tick = () => (document.querySelector('.state, .card') && document.getAnimations().every(a => a.playState !== 'running') ) || Date.now() - t0 > 4000 ? r(true) : setTimeout(tick, 100); tick() })`)
}
async function shot(name) {
  const r = await send('Page.captureScreenshot', { format: 'png' })
  writeFileSync(`${OUT}/${name}.png`, Buffer.from(r.result.data, 'base64'))
}
// W is the viewport width we asked for. Mobile emulation grows the layout viewport to fit overflowing
// content (innerWidth would then match scrollWidth), so overflow must be judged against W, not innerWidth.
const metrics = (W) => `(() => { const d = document.documentElement; const q = (s) => document.querySelector(s);
  const vis = (s) => { const e = q(s); if (!e) return 'absent'; const cs = getComputedStyle(e); const r = e.getBoundingClientRect(); return cs.display === 'none' || cs.visibility === 'hidden' ? 'hidden' : Math.round(r.width) + 'x' + Math.round(r.height) + '@' + Math.round(r.left) + ',' + Math.round(r.top) };
  const overflow = [...document.querySelectorAll('body *')].filter((e) => { const r = e.getBoundingClientRect(); return r.width > 0 && (r.right > ${W} + 1) && getComputedStyle(e).position !== 'fixed' }).slice(0, 4).map((e) => e.tagName + '.' + e.className);
  return JSON.stringify({ vw: innerWidth, scrollW: d.scrollWidth, hOverflow: Math.max(d.scrollWidth, innerWidth) > ${W} + 1, overflowers: overflow, theme: d.dataset.theme ?? '(none)', bg: getComputedStyle(document.body).backgroundColor,
    topbar: vis('.topbar'), dock: vis('.dock'), pill: vis('.dock__pill'), hamburger: vis('.topbar__menu, [aria-label*="navigation" i]'), brandName: vis('.brand__name'), signin: vis('.topbar__right a'), h1: q('h1')?.textContent, title: document.title }) })()`

const report = []
const scenarios = [
  { name: 'desktop-dark-overview', url: `${BASE}/`, w: 1440, h: 900 },
  { name: 'desktop-light-training', url: `${BASE}/training`, w: 1440, h: 900, scheme: 'light' },
  { name: 'tablet-dark-topology', url: `${BASE}/topology`, w: 768, h: 1024, mobile: true },
  { name: 'phone390-dark-overview', url: `${BASE}/`, w: 390, h: 844, mobile: true },
  { name: 'phone360-light-experiments', url: `${BASE}/experiments`, w: 360, h: 740, mobile: true, scheme: 'light' },
  { name: 'phone320-dark-comparison', url: `${BASE}/comparison`, w: 320, h: 640, mobile: true },
  { name: 'phone390-dark-login', url: `${BASE}/login`, w: 390, h: 844, mobile: true },
  { name: 'desktop-dark-404', url: `${BASE}/nope`, w: 1440, h: 700 },
]
for (const s of scenarios) {
  await open(s.url, s)
  const m = JSON.parse(await evaluate(metrics(s.w)))
  await shot(s.name)
  report.push({ scenario: s.name, ...m })
}

// real-browser interaction: click every dock link, check URL, pill, focus, scroll reset, title
await open(`${BASE}/`, { w: 1440, h: 900 })
const nav = []
for (const label of ['Topology Studio', 'Training Lab', 'Experiments', 'Model Comparison', 'Overview']) {
  await evaluate(`window.scrollTo(0, 200); document.querySelector('a[aria-label="${label}"]').click(); true`)
  await sleep(700)
  nav.push(JSON.parse(await evaluate(`JSON.stringify({ clicked: ${JSON.stringify(label)}, path: location.pathname, h1: document.querySelector('h1')?.textContent, title: document.title, pill: document.querySelector('.dock__pill')?.style.transform, current: document.querySelector('.dock [aria-current=page]')?.getAttribute('aria-label'), focusIsMain: document.activeElement?.id === 'main', scrollY: Math.round(scrollY) })`)))
}
// theme toggle in a real browser
await evaluate(`document.querySelector('button[aria-label^="Switch to"]').click(); true`)
await sleep(300)
const theme = JSON.parse(await evaluate(`JSON.stringify({ theme: document.documentElement.dataset.theme, bg: getComputedStyle(document.body).backgroundColor, stored: localStorage.getItem('neuroroute.theme') })`))
await shot('theme-toggled')

const failures = [
  ...report.filter((r) => r.hOverflow).map((r) => `horizontal overflow: ${r.scenario} ${JSON.stringify(r.overflowers)}`),
  ...report.filter((r) => r.hamburger !== 'absent').map((r) => `unexpected menu button: ${r.scenario}`),
  ...report.filter((r) => r.topbar === 'absent' || r.dock === 'absent' || r.dock === 'hidden').map((r) => `shell missing: ${r.scenario}`),
  ...nav.filter((n) => !(n.focusIsMain && n.scrollY === 0 && n.title.startsWith(n.h1) && n.current === n.clicked)).map((n) => `navigation problem: ${JSON.stringify(n)}`),
  ...(theme.stored === theme.theme && theme.theme ? [] : [`theme toggle did not persist: ${JSON.stringify(theme)}`]),
  ...consoleProblems.map((c) => `console: ${c}`),
]
writeFileSync(`${OUT}/audit.json`, JSON.stringify({ report, nav, theme, consoleProblems, failures }, null, 2))
const lines = failures.length
  ? ['UI audit FAILED:', ...failures.map((f) => ` - ${f}`)]
  : [`UI audit passed: ${report.length} viewports, ${nav.length} dock clicks, console clean. Output: ${OUT}`]
console.log(lines.join('\n'))
ws.close(); chrome.kill()
process.exit(failures.length ? 1 : 0)
