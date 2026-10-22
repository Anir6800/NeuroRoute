import { useId, useState, type ReactNode } from 'react'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import type { Selection } from './TopologyCanvas'
import { NAME_MAX, type LinkPatch, type NodeKind, type RenameResult, type TopologyDoc } from './model'
import type { Issue } from './validate'

interface Props {
  doc: TopologyDoc
  selected: Selection | null
  issues: Issue[]
  onSelect: (selection: Selection | null) => void
  onRename: (name: string) => void
  onRenameNode: (oldId: string, newId: string) => RenameResult
  onSetKind: (id: string, kind: NodeKind) => void
  onDeleteNode: (id: string) => void
  onUpdateLink: (id: string, patch: LinkPatch) => void
  onDeleteLink: (id: string) => void
  onAddLink: (source: string, target: string) => string | null
  onAddReverse: (id: string) => string | null
}

function Field({ label, children, hint }: { label: string; children: (id: string) => ReactNode; hint?: string }) {
  const id = useId()
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      {children(id)}
      {hint && <span className="field__hint">{hint}</span>}
    </div>
  )
}

/** Number input that keeps what the user typed; the parsed value is reported only when it is a finite number. */
function NumberField({ label, value, step, invalid, onValue }: { label: string; value: number; step?: number; invalid: boolean; onValue: (v: number) => void }) {
  const [draft, setDraft] = useState<string | null>(null)
  return (
    <Field label={label}>
      {(id) => (
        <input
          id={id}
          type="number"
          step={step}
          inputMode="decimal"
          value={draft ?? String(value)}
          aria-invalid={invalid || undefined}
          onChange={(e) => {
            setDraft(e.target.value)
            const parsed = e.target.valueAsNumber
            if (Number.isFinite(parsed)) onValue(parsed)
          }}
          onBlur={() => setDraft(null)}
        />
      )}
    </Field>
  )
}

function NodeEditor({ doc, id, issues, onRenameNode, onSetKind, onDeleteNode }: Pick<Props, 'doc' | 'issues' | 'onRenameNode' | 'onSetKind' | 'onDeleteNode'> & { id: string }) {
  const node = doc.nodes.find((n) => n.id === id)
  const [draft, setDraft] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  if (!node) return null
  const touching = doc.links.filter((l) => l.source === id || l.target === id).length

  function commit() {
    if (draft === null) return
    const result = onRenameNode(id, draft.trim())
    if (result.ok) {
      setDraft(null)
      setError(null)
    } else setError(result.error)
  }

  return (
    <Card title={`${node.kind === 'router' ? 'Router' : 'Host'} ${node.id}`} headingLevel={3} className="topo-panel__card">
      <div className="topo-form">
        <Field label="Node id" hint="Letters, digits, _ and -; press Enter or leave the field to apply.">
          {(fid) => (
            <input
              id={fid}
              value={draft ?? node.id}
              maxLength={32}
              aria-invalid={error ? true : undefined}
              aria-describedby={error ? `${fid}-err` : undefined}
              onChange={(e) => setDraft(e.target.value)}
              onBlur={commit}
              onKeyDown={(e) => {
                if (e.key === 'Enter') commit()
                if (e.key === 'Escape') {
                  setDraft(null)
                  setError(null)
                }
              }}
            />
          )}
        </Field>
        {error && <p role="alert" className="msg msg--error topo-form__error">{error}</p>}
        <Field label="Type">
          {(fid) => (
            <select id={fid} value={node.kind} onChange={(e) => onSetKind(id, e.target.value as NodeKind)}>
              <option value="router">Router</option>
              <option value="host">Host</option>
            </select>
          )}
        </Field>
        <p className="topo-form__meta">
          Position {Math.round(node.x)}, {Math.round(node.y)} · {touching} link{touching === 1 ? '' : 's'} attached
        </p>
        {issues.filter((i) => i.ref.kind === 'node' && i.ref.id === id).map((i) => (
          <p key={i.code + i.message} className="msg msg--error topo-form__error">{i.message}</p>
        ))}
        <Button variant="danger" onClick={() => onDeleteNode(id)}>
          Delete node{touching ? ` and ${touching} link${touching === 1 ? '' : 's'}` : ''}
        </Button>
      </div>
    </Card>
  )
}

function LinkEditor({ doc, id, issues, onUpdateLink, onDeleteLink, onAddReverse }: Pick<Props, 'doc' | 'issues' | 'onUpdateLink' | 'onDeleteLink' | 'onAddReverse'> & { id: string }) {
  const link = doc.links.find((l) => l.id === id)
  const [note, setNote] = useState<string | null>(null)
  if (!link) return null
  const mine = issues.filter((i) => i.ref.kind === 'link' && i.ref.id === id)
  const bad = (code: string) => mine.some((i) => i.code === code)
  const reverseExists = doc.links.some((l) => l.source === link.target && l.target === link.source)

  return (
    <Card title={`Link ${link.id}`} headingLevel={3} className="topo-panel__card">
      <div className="topo-form">
        <p className="topo-form__meta">
          {link.source} → {link.target} (directed)
        </p>
        <NumberField label="Capacity (Mbps)" value={link.capacity_mbps} step={10} invalid={bad('non_positive_capacity')} onValue={(v) => onUpdateLink(id, { capacity_mbps: v })} />
        <NumberField label="Propagation delay (ms)" value={link.prop_delay_ms} step={0.5} invalid={bad('non_positive_delay')} onValue={(v) => onUpdateLink(id, { prop_delay_ms: v })} />
        <NumberField label="Buffer (packets)" value={link.buffer_pkts} step={1} invalid={bad('non_positive_buffer')} onValue={(v) => onUpdateLink(id, { buffer_pkts: v })} />
        <NumberField label="Routing weight" value={link.weight} step={0.5} invalid={bad('negative_weight')} onValue={(v) => onUpdateLink(id, { weight: v })} />
        {mine.map((i) => (
          <p key={i.code + i.message} className="msg msg--error topo-form__error">{i.message}</p>
        ))}
        <div className="topo-form__row">
          <Button
            onClick={() => setNote(onAddReverse(id))}
            disabledReason={reverseExists ? `${link.target} → ${link.source} already exists.` : undefined}
          >
            Add reverse link
          </Button>
          <Button variant="danger" onClick={() => onDeleteLink(id)}>
            Delete link
          </Button>
        </div>
        {note && <p role="alert" className="msg msg--error topo-form__error">{note}</p>}
      </div>
    </Card>
  )
}

function AddLinkForm({ doc, onAddLink }: Pick<Props, 'doc' | 'onAddLink'>) {
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [error, setError] = useState<string | null>(null)
  const ids = doc.nodes.map((n) => n.id)
  const same = from !== '' && from === to
  const reason = ids.length < 2 ? 'Add at least two nodes first.' : undefined

  return (
    <Card title="Add a link" headingLevel={3} className="topo-panel__card">
      <form
        className="topo-form"
        onSubmit={(e) => {
          e.preventDefault()
          const err = onAddLink(from, to)
          setError(err)
          if (!err) setTo('')
        }}
      >
        <Field label="From">
          {(id) => (
            <select id={id} value={from} onChange={(e) => setFrom(e.target.value)} disabled={ids.length < 2}>
              <option value="">Choose a node</option>
              {ids.map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
          )}
        </Field>
        <Field label="To">
          {(id) => (
            <select id={id} value={to} onChange={(e) => setTo(e.target.value)} disabled={ids.length < 2}>
              <option value="">Choose a node</option>
              {ids.map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
          )}
        </Field>
        <button type="submit" className="btn btn--primary" disabled={Boolean(reason) || from === '' || to === '' || same}>
          Add link
        </button>
        {reason && <span className="btn-reason">{reason}</span>}
        {same && <span className="btn-reason">A link needs two different nodes.</span>}
        {error && <p role="alert" className="msg msg--error topo-form__error">{error}</p>}
      </form>
    </Card>
  )
}

function IssueList({ issues, onSelect }: { issues: Issue[]; onSelect: Props['onSelect'] }) {
  return (
    <Card title={issues.length ? `Problems (${issues.length})` : 'Problems'} headingLevel={3} className="topo-panel__card">
      <div aria-live="polite">
        {issues.length === 0 ? (
          <p className="topo-form__meta">No problems found.</p>
        ) : (
          <ul className="topo-issues">
            {issues.map((i, n) => (
              <li key={`${i.origin}-${i.code}-${n}`}>
                <span className="topo-issues__origin">{i.origin === 'server' ? 'Server' : 'Check'}</span>
                {i.ref.kind === 'graph' ? (
                  <span>{i.message}</span>
                ) : (
                  <button type="button" className="topo-issues__link" onClick={() => onSelect(i.ref as Selection)}>
                    {i.message}
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </Card>
  )
}

export function TopologyInspector(props: Props) {
  const { doc, selected, issues, onSelect, onRename } = props
  const nameId = useId()
  return (
    <aside className="topo-panel" aria-label="Topology inspector">
      <Card title="Network" headingLevel={3} className="topo-panel__card">
        <div className="field">
          <label htmlFor={nameId}>Name</label>
          <input id={nameId} value={doc.name} maxLength={NAME_MAX} onChange={(e) => onRename(e.target.value)} />
        </div>
        <p className="topo-form__meta">
          {doc.nodes.length} node{doc.nodes.length === 1 ? '' : 's'} · {doc.links.length} link{doc.links.length === 1 ? '' : 's'}
          {doc.version !== null && ` · saved as version ${doc.version}`}
        </p>
      </Card>
      {selected?.kind === 'node' && <NodeEditor key={selected.id} {...props} id={selected.id} />}
      {selected?.kind === 'link' && <LinkEditor key={selected.id} {...props} id={selected.id} />}
      <AddLinkForm doc={doc} onAddLink={props.onAddLink} />
      <IssueList issues={issues} onSelect={onSelect} />
    </aside>
  )
}
