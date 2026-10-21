import { API_BASE_URL, API_TIMEOUT_MS } from '../config'

export interface Health {
  status: string
  app: string
  version: string
}

export type HealthResult = { ok: true; data: Health } | { ok: false; error: string }

/** GET /health with an explicit timeout; never throws. */
export async function fetchHealth(
  fetchImpl: typeof fetch = fetch,
  baseUrl: string = API_BASE_URL,
  timeoutMs: number = API_TIMEOUT_MS,
): Promise<HealthResult> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const res = await fetchImpl(`${baseUrl}/health`, { signal: controller.signal })
    if (!res.ok) return { ok: false, error: `HTTP ${res.status}` }
    const body = (await res.json()) as Partial<Health>
    if (
      typeof body.status !== 'string' ||
      typeof body.app !== 'string' ||
      typeof body.version !== 'string'
    ) {
      return { ok: false, error: 'Unexpected response shape' }
    }
    return { ok: true, data: { status: body.status, app: body.app, version: body.version } }
  } catch (e) {
    const timedOut = e instanceof DOMException && e.name === 'AbortError'
    return { ok: false, error: timedOut ? `Timed out after ${timeoutMs} ms` : 'Backend unreachable' }
  } finally {
    clearTimeout(timer)
  }
}
