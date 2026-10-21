import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { Button } from './components/ui/Button'
import { Card } from './components/ui/Card'
import { PageHeader } from './components/ui/PageHeader'
import { ScreenState } from './components/ui/ScreenState'
import { StatusPill } from './components/ui/StatusPill'
import { EmptyState, ErrorState, LoadingState } from './components/ui/States'

afterEach(cleanup)

describe('Button', () => {
  it('runs onClick when enabled', () => {
    const onClick = vi.fn()
    render(<Button onClick={onClick}>Go</Button>)
    fireEvent.click(screen.getByRole('button', { name: 'Go' }))
    expect(onClick).toHaveBeenCalledOnce()
  })

  it('with a disabled reason: ignores clicks, stays focusable, and shows the reason as text', () => {
    const onClick = vi.fn()
    render(
      <Button onClick={onClick} disabledReason="No trainer exists yet">
        Start
      </Button>,
    )
    const button = screen.getByRole('button', { name: 'Start' })
    fireEvent.click(button)
    expect(onClick).not.toHaveBeenCalled()
    expect(button.getAttribute('aria-disabled')).toBe('true')
    expect((button as HTMLButtonElement).disabled).toBe(false) // focusable on purpose
    const reason = screen.getByText('No trainer exists yet')
    expect(button.getAttribute('aria-describedby')).toBe(reason.id)
    button.focus()
    expect(document.activeElement).toBe(button)
  })

  it('uses the native disabled attribute when disabled without a reason', () => {
    render(<Button disabled>Nope</Button>)
    const button = screen.getByRole('button', { name: 'Nope' }) as HTMLButtonElement
    expect(button.disabled).toBe(true)
    expect(button.getAttribute('aria-disabled')).toBe('true')
  })

  it('is always type=button so it never submits a form by accident', () => {
    render(<Button>Plain</Button>)
    expect(screen.getByRole('button', { name: 'Plain' }).getAttribute('type')).toBe('button')
  })
})

describe('StatusPill', () => {
  it('never relies on color: glyph is hidden from assistive tech, text carries the meaning', () => {
    render(<StatusPill status="critical">Backend unavailable</StatusPill>)
    expect(screen.getByText('Backend unavailable')).toBeTruthy()
    expect(screen.getByText('✕').getAttribute('aria-hidden')).toBe('true')
  })
})

describe('state components', () => {
  it('EmptyState renders a heading, text and optional action', () => {
    render(
      <EmptyState title="Nothing here" description="Because nothing exists yet.">
        <button type="button">Do it</button>
      </EmptyState>,
    )
    expect(screen.getByRole('heading', { name: 'Nothing here' })).toBeTruthy()
    expect(screen.getByText('Because nothing exists yet.')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Do it' })).toBeTruthy()
  })

  it('ErrorState is an alert and offers retry only when given a handler', () => {
    const onRetry = vi.fn()
    const { rerender } = render(<ErrorState message="Backend unreachable" onRetry={onRetry} />)
    expect(screen.getByRole('alert').textContent).toContain('Backend unreachable')
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(onRetry).toHaveBeenCalledOnce()
    rerender(<ErrorState message="Backend unreachable" />)
    expect(screen.queryByRole('button', { name: 'Try again' })).toBeNull()
  })

  it('LoadingState is a polite status', () => {
    render(<LoadingState label="Loading runs" />)
    const status = screen.getByRole('status')
    expect(status.getAttribute('aria-live')).toBe('polite')
    expect(status.textContent).toContain('Loading runs')
  })
})

describe('ScreenState', () => {
  const empty = { title: 'No data', description: 'Nothing recorded.' }

  it('renders the right branch for each status', () => {
    const { rerender } = render(
      <ScreenState status="loading" empty={empty}>
        <p>ready content</p>
      </ScreenState>,
    )
    expect(screen.getByRole('status')).toBeTruthy()
    rerender(
      <ScreenState status="empty" empty={empty}>
        <p>ready content</p>
      </ScreenState>,
    )
    expect(screen.getByRole('heading', { name: 'No data' })).toBeTruthy()
    rerender(
      <ScreenState status="error" empty={empty} error={{ message: 'boom' }}>
        <p>ready content</p>
      </ScreenState>,
    )
    expect(screen.getByRole('alert').textContent).toContain('boom')
    rerender(
      <ScreenState status="ready" empty={empty}>
        <p>ready content</p>
      </ScreenState>,
    )
    expect(screen.getByText('ready content')).toBeTruthy()
  })

  it('shows a generic error instead of crashing when the error detail is missing', () => {
    render(<ScreenState status="error" empty={empty} />)
    expect(screen.getByRole('alert').textContent).toContain('Unknown error')
  })
})

describe('Card and PageHeader', () => {
  it('Card is a labelled region when it has a title', () => {
    render(<Card title="Backend">body</Card>)
    expect(screen.getByRole('region', { name: 'Backend' })).toBeTruthy()
  })

  it('PageHeader renders one h1 with optional description and actions', () => {
    render(<PageHeader title="Overview" description="Desc" actions={<button type="button">Act</button>} />)
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
    expect(screen.getByText('Desc')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Act' })).toBeTruthy()
  })
})
