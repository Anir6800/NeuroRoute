const raw = import.meta.env.VITE_API_BASE_URL as string | undefined

/** Base URL for the local backend; trailing slashes stripped. */
export const API_BASE_URL: string = (raw && raw.trim() !== '' ? raw : '/api').replace(/\/+$/, '')

export const API_TIMEOUT_MS = 3000
