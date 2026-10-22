import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { Topology } from '../../pages/Topology'
import { sixRouterExample } from './model'
import { FakeApi, stubReactFlowEnvironment } from './testing'
import { TopologyCanvas } from './TopologyCanvas'
import type { Issue } from './validate'

beforeAll(stubReactFlowEnvironment)
beforeEach(() => localStorage.clear())
afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

function renderStudio(api: FakeApi) {
  return render(
    <MemoryRouter>
      <Topology api={api} />
    </MemoryRouter>,
  )
}
const ready = async () => screen.findByRole('toolbar', { name: 'Topology actions' })
const click = (name: string | RegExp) => fireEvent.click(screen.getByRole('button', { name }))
const nodeElements = (c: HTMLElement = document.body) => [...c.querySelectorAll('.react-flow__node')] as HTMLElement[]
const edgeElements = () => [...document.querySelectorAll('.react-flow__edge')]
const nodeIds = () => nodeElements().map((n) => n.querySelector('.topo-node__id')?.textContent)

function addLinkViaForm(from: string, to: string) {
  fireEvent.change(screen.getByLabelText('From'), { target: { value: from } })
  fireEvent.change(screen.getByLabelText('To'), { target: { value: to } })
  click('Add link')
}
async function buildSixRouterRing() {
  for (let i = 0; i < 6; i++) click('Add router')
  for (let i = 1; i <= 6; i++) addLinkViaForm(`r${i}`, `r${(i % 6) + 1}`)
}

describe('create, save and reload a six-router network', () => {
  it('builds six routers and six links by hand, saves them, and finds the same network after a reload', async () => {
    const api = new FakeApi()
    const first = renderStudio(api)
    await ready()
    expect(screen.getByText(/Empty canvas/)).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Save' }).getAttribute('aria-disabled')).toBe('true')
    expect(screen.getByText('Fix 2 problems first.')).toBeTruthy() // nothing to save yet, and why

    await buildSixRouterRing()
    await waitFor(() => expect(nodeIds()).toEqual(['r1', 'r2', 'r3', 'r4', 'r5', 'r6']))
    await waitFor(() => expect(edgeElements()).toHaveLength(6))
    expect(screen.getByText('No problems found.')).toBeTruthy()
    expect(screen.getByText(/Unsaved changes/)).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Save' }).getAttribute('aria-disabled')).toBeNull()

    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Ring six' } })
    click('Save')
    expect(await screen.findByText('Saved as version 1.')).toBeTruthy()
    expect(screen.getByText('Saved (v1)')).toBeTruthy()

    // what the server holds
    expect(api.calls.save).toBe(1)
    const stored = [...api.rows.values()][0]
    expect(stored).toMatchObject({ name: 'Ring six', version: 1 })
    expect(stored.nodes.map((n) => n.id)).toEqual(['r1', 'r2', 'r3', 'r4', 'r5', 'r6'])
    expect(stored.nodes.every((n) => n.kind === 'router' && Number.isFinite(n.x) && Number.isFinite(n.y))).toBe(true)
    expect(stored.links.map((l) => l.id)).toEqual(['r1-r2', 'r2-r3', 'r3-r4', 'r4-r5', 'r5-r6', 'r6-r1'])

    // reload: a fresh page (new component tree, same browser storage, same server)
    first.unmount()
    renderStudio(api)
    await ready()
    await waitFor(() => expect(nodeIds()).toEqual(['r1', 'r2', 'r3', 'r4', 'r5', 'r6']))
    await waitFor(() => expect(edgeElements()).toHaveLength(6))
    expect((screen.getByLabelText('Name') as HTMLInputElement).value).toBe('Ring six')
    expect(screen.getByText('Saved (v1)')).toBeTruthy()
    expect(screen.getByText(/6 nodes · 6 links · saved as version 1/)).toBeTruthy()
    const moved = nodeElements().map((n) => n.style.transform)
    expect(moved[1]).toContain('translate(180px,0px)') // r2's saved position, not a re-laid-out one
    expect(api.calls.save).toBe(1) // loading did not write anything
  })

  it('reopens a saved network from the list when the browser has forgotten the last one', async () => {
    const api = new FakeApi()
    const first = renderStudio(api)
    await ready()
    click('Six-router example')
    click('Save')
    await screen.findByText('Saved as version 1.')
    first.unmount()
    localStorage.clear()

    renderStudio(api)
    await ready()
    expect(nodeElements()).toHaveLength(0)
    const picker = screen.getByRole('combobox', { name: 'Open a saved topology' })
    fireEvent.change(picker, { target: { value: [...api.rows.keys()][0] } })
    await waitFor(() => expect(nodeIds()).toHaveLength(6))
    await waitFor(() => expect(edgeElements()).toHaveLength(14))
  })

  it('saving again updates the same topology (version 2) instead of creating another', async () => {
    const api = new FakeApi()
    renderStudio(api)
    await ready()
    click('Six-router example')
    click('Save')
    await screen.findByText('Saved as version 1.')
    click('Add host')
    addLinkViaForm('h1', 'r1')
    click('Save changes')
    expect(await screen.findByText('Saved as version 2.')).toBeTruthy()
    expect(api.rows.size).toBe(1)
    expect([...api.rows.values()][0].nodes).toHaveLength(7)
  })
})

describe('six-router example', () => {
  it('fills the canvas with a valid ring and is offered only on an empty canvas', async () => {
    renderStudio(new FakeApi())
    await ready()
    click('Six-router example')
    await waitFor(() => expect(nodeIds()).toHaveLength(6))
    expect(screen.getByText('No problems found.')).toBeTruthy()
    expect(screen.getByText('Clear the canvas first (New).')).toBeTruthy()
    const before = nodeElements().length
    click('Six-router example')
    expect(nodeElements()).toHaveLength(before)
  })
})

describe('validation is visible', () => {
  it('lists problems, flags the elements, and blocks saving until they are fixed', async () => {
    const api = new FakeApi()
    renderStudio(api)
    await ready()
    click('Add router')
    click('Add router')
    click('Add router')
    addLinkViaForm('r1', 'r2')
    expect(screen.getByText(/separate parts/)).toBeTruthy() // r3 is not connected
    expect(screen.getByRole('button', { name: 'Save' }).getAttribute('aria-disabled')).toBe('true')
    expect(screen.getByText('Fix 1 problem first.')).toBeTruthy()
    click('Save')
    expect(api.calls.save).toBe(0)
    addLinkViaForm('r2', 'r3')
    expect(screen.getByText('No problems found.')).toBeTruthy()
  })

  it('shows a non-positive capacity on the link and on the problem list, and clears it when fixed', async () => {
    renderStudio(new FakeApi())
    await ready()
    click('Add router')
    click('Add router')
    addLinkViaForm('r1', 'r2') // selects the new link
    const capacity = screen.getByLabelText('Capacity (Mbps)') as HTMLInputElement
    fireEvent.change(capacity, { target: { value: '0' } })
    expect(screen.getAllByText(/capacity must be greater than 0/).length).toBeGreaterThan(0)
    expect(capacity.getAttribute('aria-invalid')).toBe('true')
    await waitFor(() => expect(document.querySelector('.topo-edge--invalid')).not.toBeNull())
    expect(screen.getByRole('button', { name: 'Save' }).getAttribute('aria-disabled')).toBe('true')
    fireEvent.change(capacity, { target: { value: '250' } })
    expect(screen.getByText('No problems found.')).toBeTruthy()
    expect(capacity.getAttribute('aria-invalid')).toBeNull()
  })

  it('shows what the server rejected, points at the element, and drops it after the next edit', async () => {
    const api = new FakeApi()
    renderStudio(api)
    await ready()
    click('Six-router example')
    api.rejectNextSave = [{ code: 'non_positive_capacity', message: 'server says capacity is wrong', path: 'links[2].capacity_mbps' }]
    click('Save')
    expect(await screen.findByText(/The server rejected the topology \(1 problem\)\. Nothing was saved\./)).toBeTruthy()
    const issue = screen.getByRole('button', { name: 'server says capacity is wrong' })
    expect(within(issue.closest('li') as HTMLElement).getByText('Server')).toBeTruthy()
    fireEvent.click(issue)
    expect(screen.getByRole('heading', { name: 'Link r2-r3' })).toBeTruthy() // links[2] of the ring example
    expect(api.rows.size).toBe(0)
    fireEvent.change(screen.getByLabelText('Routing weight'), { target: { value: '2' } })
    expect(screen.queryByRole('button', { name: 'server says capacity is wrong' })).toBeNull() // an edit makes the verdict stale
  })
})

describe('editing', () => {
  async function withExample() {
    const api = new FakeApi()
    renderStudio(api)
    await ready()
    click('Six-router example')
    await waitFor(() => expect(nodeIds()).toHaveLength(6))
    return api
  }

  it('selecting a node shows its inspector; renaming updates the links that use it; bad names are refused', async () => {
    await withExample()
    fireEvent.click(nodeElements()[0])
    expect(await screen.findByRole('heading', { name: 'Router r1' })).toBeTruthy()
    const id = screen.getByLabelText('Node id') as HTMLInputElement
    fireEvent.change(id, { target: { value: 'bad id' } })
    fireEvent.keyDown(id, { key: 'Enter' })
    expect((await screen.findByRole('alert')).textContent).toContain('Use 1-32 letters')
    fireEvent.change(id, { target: { value: 'r2' } })
    fireEvent.keyDown(id, { key: 'Enter' })
    expect(screen.getByRole('alert').textContent).toContain('already exists')
    fireEvent.change(id, { target: { value: 'core' } })
    fireEvent.keyDown(id, { key: 'Enter' })
    await waitFor(() => expect(nodeIds()).toContain('core'))
    expect(nodeIds()).not.toContain('r1')
    expect(await screen.findByRole('heading', { name: 'Router core' })).toBeTruthy()
    expect(screen.getByText('No problems found.')).toBeTruthy()
    expect(screen.getByText(/Position .* · 6 links attached/)).toBeTruthy() // r1: ring neighbours r2 and r6 plus the r4 chord, each as two directed links
  })

  it('changing the type, and deleting a node together with its links', async () => {
    await withExample()
    fireEvent.click(nodeElements()[2]) // r3: neighbours r2 and r4, so 4 directed links
    await screen.findByRole('heading', { name: 'Router r3' })
    fireEvent.change(screen.getByLabelText('Type'), { target: { value: 'host' } })
    expect(await screen.findByRole('heading', { name: 'Host r3' })).toBeTruthy()
    click('Delete node and 4 links')
    await waitFor(() => expect(nodeIds()).toEqual(['r1', 'r2', 'r4', 'r5', 'r6']))
    expect(screen.getByText(/5 nodes · 10 links/)).toBeTruthy()
    expect(screen.queryByRole('heading', { name: /r3/ })).toBeNull()
  })

  it('adds the reverse of a link only once', async () => {
    renderStudio(new FakeApi())
    await ready()
    click('Add router')
    click('Add router')
    addLinkViaForm('r1', 'r2')
    click('Add reverse link')
    expect(await screen.findByRole('heading', { name: 'Link r2-r1' })).toBeTruthy()
    click('Add reverse link')
    expect(screen.getByText('r1 → r2 already exists.')).toBeTruthy() // the button explains why it does nothing
    expect(screen.getByText(/2 nodes · 2 links/)).toBeTruthy()
  })

  it('refuses a repeated or self link from the form with a reason', async () => {
    renderStudio(new FakeApi())
    await ready()
    click('Add router')
    click('Add router')
    addLinkViaForm('r1', 'r2')
    addLinkViaForm('r1', 'r2')
    expect((await screen.findByRole('alert')).textContent).toContain('already exists')
    fireEvent.change(screen.getByLabelText('To'), { target: { value: 'r1' } })
    expect(screen.getByText('A link needs two different nodes.')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Add link' }).hasAttribute('disabled')).toBe(true)
  })

  it('warns before leaving with unsaved changes, and not otherwise', async () => {
    renderStudio(new FakeApi())
    await ready()
    const leave = () => {
      const e = new Event('beforeunload', { cancelable: true })
      window.dispatchEvent(e)
      return e.defaultPrevented
    }
    expect(leave()).toBe(false)
    click('Add router')
    expect(leave()).toBe(true)
  })

  it('New asks before throwing away unsaved work', async () => {
    renderStudio(new FakeApi())
    await ready()
    click('Add router')
    const confirm = vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValueOnce(true)
    click('New')
    expect(nodeIds()).toEqual(['r1'])
    click('New')
    await waitFor(() => expect(nodeIds()).toEqual([]))
    expect(confirm).toHaveBeenCalledTimes(2)
  })
})

describe('failure states', () => {
  it('without a session: says so with a sign-in link, still lets the user edit, and will not save', async () => {
    const api = new FakeApi()
    api.failNext.list = { ok: false, kind: 'unauthorized', message: 'You are not signed in.' }
    renderStudio(api)
    await ready()
    const banner = screen.getByRole('alert')
    expect(within(banner).getByRole('link', { name: 'Sign in' }).getAttribute('href')).toBe('/login')
    click('Six-router example')
    expect(screen.getByText('Sign in to save.')).toBeTruthy()
    click('Save')
    expect(api.calls.save).toBe(0)
  })

  it('backend unreachable: shows the problem and recovers on Try again', async () => {
    const api = new FakeApi()
    api.failNext.list = { ok: false, kind: 'network', message: 'The backend is unreachable.' }
    renderStudio(api)
    await ready()
    expect(screen.getByRole('alert').textContent).toContain('The backend is unreachable.')
    click('Try again')
    await waitFor(() => expect(screen.queryByText('The backend is unreachable.')).toBeNull())
    expect(api.calls.list).toBe(2)
  })

  it('a failed save keeps the work and says why', async () => {
    const api = new FakeApi()
    renderStudio(api)
    await ready()
    click('Six-router example')
    api.failNext.save = { ok: false, kind: 'network', message: 'The backend is unreachable.' }
    click('Save')
    expect(await screen.findByText('Not saved: The backend is unreachable.')).toBeTruthy()
    expect(nodeIds()).toHaveLength(6)
    expect(screen.getByText(/Unsaved changes/)).toBeTruthy()
    click('Save') // the retry works
    expect(await screen.findByText('Saved as version 1.')).toBeTruthy()
  })

  it('a stale version is a conflict: nothing is overwritten, and the server version can be loaded', async () => {
    const api = new FakeApi()
    renderStudio(api)
    await ready()
    click('Six-router example')
    click('Save')
    await screen.findByText('Saved as version 1.')
    const id = [...api.rows.keys()][0]
    await act(async () => {
      const theirs = { ...(api.rows.get(id) as NonNullable<ReturnType<typeof api.rows.get>>), name: 'Their edit' }
      await api.save(theirs) // another browser saves version 2
    })
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'My edit' } })
    click('Save changes')
    const warning = await screen.findByText(/Someone changed this topology/)
    expect(warning.textContent).toContain('server version 2, yours 1')
    expect(api.rows.get(id)?.name).toBe('Their edit')
    click(/Load server version/)
    await waitFor(() => expect((screen.getByLabelText('Name') as HTMLInputElement).value).toBe('Their edit'))
    expect(screen.getByText('Saved (v2)')).toBeTruthy()
    expect(screen.queryByText(/Someone changed this topology/)).toBeNull()
  })

  it('forgets a last-opened id that no longer exists on the server', async () => {
    localStorage.setItem('neuroroute.topology.last', 'gone')
    renderStudio(new FakeApi())
    await ready()
    expect(localStorage.getItem('neuroroute.topology.last')).toBeNull()
    expect(screen.getByText(/Empty canvas/)).toBeTruthy()
  })
})

describe('TopologyCanvas', () => {
  const doc = sixRouterExample()
  const noop = () => {}

  it('draws one element per node and link and reports a click as a selection', async () => {
    const onSelect = vi.fn()
    render(<TopologyCanvas doc={doc} selected={null} issues={[]} fitKey="a" onSelect={onSelect} onMoveNode={noop} onConnect={noop} onDelete={noop} />)
    await waitFor(() => expect(nodeElements()).toHaveLength(6))
    await waitFor(() => expect(edgeElements()).toHaveLength(14))
    fireEvent.click(nodeElements()[3])
    expect(onSelect).toHaveBeenCalledWith({ kind: 'node', id: 'r4' })
    expect(screen.getByRole('group', { name: 'Topology canvas' })).toBeTruthy()
  })

  it('marks the selected node and the nodes and links that have problems', async () => {
    const issues: Issue[] = [
      { code: 'x', message: 'm', origin: 'local', ref: { kind: 'node', id: 'r2' } },
      { code: 'y', message: 'm', origin: 'local', ref: { kind: 'link', id: 'r1-r2' } },
    ]
    render(<TopologyCanvas doc={doc} selected={{ kind: 'node', id: 'r5' }} issues={issues} fitKey="a" onSelect={noop} onMoveNode={noop} onConnect={noop} onDelete={noop} />)
    await waitFor(() => expect(nodeElements()).toHaveLength(6))
    expect(nodeElements().filter((n) => n.classList.contains('selected')).map((n) => n.dataset.id)).toEqual(['r5'])
    expect(nodeElements().filter((n) => n.querySelector('[data-invalid]')).map((n) => n.dataset.id)).toEqual(['r2'])
    expect(document.querySelectorAll('.topo-edge--invalid')).toHaveLength(1)
  })

  it('describes the keyboard and drag controls for assistive technology', () => {
    render(<TopologyCanvas doc={doc} selected={null} issues={[]} fitKey="a" onSelect={noop} onMoveNode={noop} onConnect={noop} onDelete={noop} />)
    const group = screen.getByRole('group', { name: 'Topology canvas' })
    const help = document.getElementById(group.getAttribute('aria-describedby') as string)
    expect(help?.textContent).toMatch(/Drag a node.*Delete/s)
  })
})

describe('TopologyCanvas keyboard', () => {
  const doc = sixRouterExample()
  const noop = () => {}

  it('arrow keys move a focused, selected node and report the new position', async () => {
    const onMoveNode = vi.fn()
    render(<TopologyCanvas doc={doc} selected={{ kind: 'node', id: 'r2' }} issues={[]} fitKey="a" onSelect={noop} onMoveNode={onMoveNode} onConnect={noop} onDelete={noop} />)
    await waitFor(() => expect(nodeElements()).toHaveLength(6))
    const r2 = nodeElements().find((n) => n.dataset.id === 'r2') as HTMLElement
    r2.focus()
    fireEvent.keyDown(r2, { key: 'ArrowRight' })
    await waitFor(() => expect(onMoveNode).toHaveBeenCalled())
    const [id, x, y] = onMoveNode.mock.calls[0]
    expect(id).toBe('r2')
    expect(x).toBeGreaterThan(doc.nodes[1].x)
    expect(y).toBe(doc.nodes[1].y)
  })

  it('Delete on a selected node and on a selected link reports exactly those ids', async () => {
    const onDelete = vi.fn()
    const { rerender } = render(<TopologyCanvas doc={doc} selected={{ kind: 'node', id: 'r3' }} issues={[]} fitKey="a" onSelect={noop} onMoveNode={noop} onConnect={noop} onDelete={onDelete} />)
    await waitFor(() => expect(edgeElements()).toHaveLength(14))
    fireEvent.keyDown(document.body, { key: 'Delete', code: 'Delete' })
    await waitFor(() => expect(onDelete).toHaveBeenCalledTimes(1))
    expect(onDelete.mock.calls[0][0].nodes).toEqual(['r3'])
    expect([...onDelete.mock.calls[0][0].links].sort()).toEqual(['r2-r3', 'r3-r2', 'r3-r4', 'r4-r3'])

    fireEvent.keyUp(document.body, { key: 'Delete', code: 'Delete' }) // a real key press ends; React Flow tracks the key state
    onDelete.mockClear()
    rerender(<TopologyCanvas doc={doc} selected={{ kind: 'link', id: 'r5-r6' }} issues={[]} fitKey="a" onSelect={noop} onMoveNode={noop} onConnect={noop} onDelete={onDelete} />)
    fireEvent.keyDown(document.body, { key: 'Delete', code: 'Delete' })
    await waitFor(() => expect(onDelete).toHaveBeenCalledTimes(1))
    expect(onDelete.mock.calls[0][0]).toEqual({ nodes: [], links: ['r5-r6'] })
  })
})
