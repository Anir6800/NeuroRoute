import { API_BASE_URL, API_TIMEOUT_MS } from '../config'

export interface Me {
  uid: string
  email: string | null
  role: string
}

export type MeResult = { ok: true; data: Me } | { ok: false; error: string }

/** GET /me with a bearer token and an explicit timeout; never throws. */
export async function fetchMe(
  idToken: string,
  fetchImpl: typeof fetch = fetch,
  baseUrl: string = API_BASE_URL,
  timeoutMs: number = API_TIMEOUT_MS,
): Promise<MeResult> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const res = await fetchImpl(`${baseUrl}/me`, {
      headers: { Authorization: `Bearer ${idToken}` },
      signal: controller.signal,
    })
    if (res.status === 401) return { ok: false, error: 'Not signed in (401)' }
    if (res.status === 403) return { ok: false, error: 'Forbidden: role or project not allowed (403)' }
    if (!res.ok) return { ok: false, error: `HTTP ${res.status}` }
    const body = (await res.json()) as Partial<Me>
    if (typeof body.uid !== 'string' || typeof body.role !== 'string') {
      return { ok: false, error: 'Unexpected response shape' }
    }
    return { ok: true, data: { uid: body.uid, email: body.email ?? null, role: body.role } }
  } catch (e) {
    const timedOut = e instanceof DOMException && e.name === 'AbortError'
    return { ok: false, error: timedOut ? `Timed out after ${timeoutMs} ms` : 'Backend unreachable' }
  } finally {
    clearTimeout(timer)
  }
}
