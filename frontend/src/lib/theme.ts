import { useCallback, useEffect, useState } from 'react'

export type Theme = 'light' | 'dark'

const STORAGE_KEY = 'neuroroute.theme'
const LIGHT_QUERY = '(prefers-color-scheme: light)'

function readStored(): Theme | null {
  try {
    const v = localStorage.getItem(STORAGE_KEY)
    return v === 'light' || v === 'dark' ? v : null
  } catch {
    return null // storage blocked (private mode): fall back to the OS preference
  }
}

function writeStored(theme: Theme): void {
  try {
    localStorage.setItem(STORAGE_KEY, theme)
  } catch {
    // keep the choice in memory only
  }
}

function systemTheme(): Theme {
  return window.matchMedia?.(LIGHT_QUERY)?.matches ? 'light' : 'dark'
}

/** Apply a saved choice before React renders, to avoid a flash of the wrong theme. */
export function applyStoredTheme(): void {
  const stored = readStored()
  if (stored) document.documentElement.dataset.theme = stored
}

/** Dark is the default; with no saved choice the CSS follows the OS preference. */
export function useTheme() {
  const [chosen, setChosen] = useState<Theme | null>(readStored)
  const [system, setSystem] = useState<Theme>(systemTheme)

  useEffect(() => {
    const mq = window.matchMedia?.(LIGHT_QUERY)
    if (!mq) return
    const onChange = () => setSystem(mq.matches ? 'light' : 'dark')
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])

  useEffect(() => {
    const root = document.documentElement
    if (chosen) root.dataset.theme = chosen
    else delete root.dataset.theme
  }, [chosen])

  const effective: Theme = chosen ?? system
  const toggle = useCallback(() => {
    const next: Theme = effective === 'dark' ? 'light' : 'dark'
    setChosen(next)
    writeStored(next)
  }, [effective])

  return { effective, toggle }
}
