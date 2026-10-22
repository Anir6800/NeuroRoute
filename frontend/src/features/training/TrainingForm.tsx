import { useState, type FormEvent } from 'react'

export interface TrainingRequest {
  scenario: 'normal'
  seed_count: number
  timesteps: number
  max_episodes: number
  path_count: number
}

interface Props {
  busy: boolean
  onStart(request: TrainingRequest): Promise<void>
}

type Field = 'seeds' | 'timesteps' | 'episodes' | 'paths'

const integer = (value: string, min: number, max: number) => {
  const parsed = Number(value)
  return Number.isInteger(parsed) && parsed >= min && parsed <= max ? parsed : null
}

export function TrainingForm({ busy, onStart }: Props) {
  const [values, setValues] = useState<Record<Field, string>>({ seeds: '3', timesteps: '1000', episodes: '10', paths: '4' })
  const [errors, setErrors] = useState<Partial<Record<Field, string>>>({})

  const field = (name: Field, label: string, min: number, max: number) => (
    <label className="field">
      {label}
      <input
        name={name}
        type="number"
        inputMode="numeric"
        min={min}
        max={max}
        step={1}
        value={values[name]}
        disabled={busy}
        aria-invalid={errors[name] ? true : undefined}
        aria-describedby={errors[name] ? `${name}-error` : undefined}
        onChange={(event) => setValues({ ...values, [name]: event.target.value })}
      />
      {errors[name] && <span id={`${name}-error`} className="field__error">{errors[name]}</span>}
    </label>
  )

  async function submit(event: FormEvent) {
    event.preventDefault()
    const parsed = {
      seeds: integer(values.seeds, 3, 5), timesteps: integer(values.timesteps, 1, 100_000),
      episodes: integer(values.episodes, 1, 1_000), paths: integer(values.paths, 1, 16),
    }
    const nextErrors: Partial<Record<Field, string>> = {}
    if (parsed.seeds === null) nextErrors.seeds = 'Seed count must be an integer from 3 to 5.'
    if (parsed.timesteps === null) nextErrors.timesteps = 'Timesteps must be an integer from 1 to 100,000.'
    if (parsed.episodes === null) nextErrors.episodes = 'Episode cap must be an integer from 1 to 1,000.'
    if (parsed.paths === null) nextErrors.paths = 'Candidate paths must be an integer from 1 to 16.'
    setErrors(nextErrors)
    if (Object.keys(nextErrors).length) return
    await onStart({
      scenario: 'normal', seed_count: parsed.seeds!, timesteps: parsed.timesteps!,
      max_episodes: parsed.episodes!, path_count: parsed.paths!,
    })
  }

  return (
    <form className="form training-form" noValidate onSubmit={submit}>
      <p className="training-form__fixed"><strong>Scenario:</strong> normal · <strong>CPU threads:</strong> 1</p>
      {field('seeds', 'Training seeds', 3, 5)}
      {field('episodes', 'Maximum episodes per seed', 1, 1_000)}
      {field('paths', 'Candidate paths (K)', 1, 16)}
      {field('timesteps', 'Maximum timesteps per seed', 1, 100_000)}
      <button type="submit" className="btn btn--primary" disabled={busy}>
        {busy ? 'Training in progress...' : 'Start controlled run'}
      </button>
    </form>
  )
}
