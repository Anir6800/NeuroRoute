import { initializeApp } from 'firebase/app'
import { connectAuthEmulator, getAuth } from 'firebase/auth'

// Local emulator only. "demo-" project + fake key: nothing here is a secret and nothing
// can reach a real Firebase project.
const app = initializeApp({ apiKey: 'demo-key', projectId: 'demo-neuroroute' })

export const AUTH_EMULATOR_URL: string =
  (import.meta.env.VITE_AUTH_EMULATOR_URL as string | undefined) || 'http://127.0.0.1:9099'

export const auth = getAuth(app)
connectAuthEmulator(auth, AUTH_EMULATOR_URL, { disableWarnings: true })
