import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Button } from '../../components/ui/Button'
import { LoadingState } from '../../components/ui/States'
import { getIdToken } from '../../lib/session'
import { createTopologyApi, type ApiError, type TopologyApi, type TopologySummary } from './api'
import {
  addLink,
  addNode,
  docKey,
  EMPTY_DOC,
  isDirty,
  moveNode,
  removeLinks,
  removeNodes,
  renameNode,
  setNodeKind,
  sixRouterExample,
  updateLink,
  type LinkPatch,
  type NodeKind,
  type TopologyDoc,
} from './model'
import { TopologyCanvas, type Selection } from './TopologyCanvas'
import { TopologyInspector } from './TopologyInspector'
import { issuesFromReasons, validateDoc, type Issue } from './validate'

const LAST_KEY = 'neuroroute.topology.last'

function readLast(): string | null {
  try {
    return localStorage.getItem(LAST_KEY)
  } catch {
    return null // storage blocked: the editor still works, it just does not reopen the last network
  }
}
function writeLast(id: string | null): void {
  try {
    if (id) localStorage.setItem(LAST_KEY, id)
    else localStorage.removeItem(LAST_KEY)
  } catch {
    // ignore
  }
}

type Session = 'unknown' | 'in' | 'out'
type Notice = { tone: 'ok' | 'error'; text: string } | null

const defaultApi = () => createTopologyApi({ getToken: getIdToken })

/** Create, edit, validate, save and reopen a topology. All server access goes through `api`, so tests can supply a fake. */
export function TopologyStudio({ api: apiProp }: { api?: TopologyApi }) {
  const api = useMemo(() => apiProp ?? defaultApi(), [apiProp])

  const [doc, setDoc] = useState<TopologyDoc>(EMPTY_DOC)
  const [savedKey, setSavedKey] = useState(() => docKey(EMPTY_DOC))
  const [selected, setSelected] = useState<Selection | null>(null)
  const [fitKey, setFitKey] = useState('0')
  const [serverIssues, setServerIssues] = useState<Issue[]>([])
  const [conflict, setConflict] = useState<{ currentVersion: number | null } | null>(null)
  const [notice, setNotice] = useState<Notice>(null)
  const [banner, setBanner] = useState<ApiError | null>(null)
  const [session, setSession] = useState<Session>('unknown')
  const [starting, setStarting] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState<TopologySummary[]>([])
  const loadCount = useRef(0)

  const localIssues = useMemo(() => validateDoc(doc), [doc])
  const issues = useMemo(() => [...localIssues, ...serverIssues], [localIssues, serverIssues])
  const dirty = isDirty(doc, savedKey)

  /** Any edit makes earlier server verdicts stale. */
  const edit = useCallback((change: (d: TopologyDoc) => TopologyDoc) => {
    setDoc(change)
    setServerIssues([])
    setConflict(null)
    setNotice(null)
  }, [])

  const show = useCallback((d: TopologyDoc) => {
    loadCount.current += 1
    setDoc(d)
    setSavedKey(docKey(d))
    setSelected(null)
    setServerIssues([])
    setConflict(null)
    setNotice(null)
    setFitKey(`load-${loadCount.current}`)
  }, [])

  const handleError = useCallback((e: ApiError) => {
    if (e.kind === 'unauthorized') setSession('out')
    setBanner(e)
  }, [])

  const refreshList = useCallback(async () => {
    const r = await api.list()
    if (r.ok) {
      setSession('in')
      setSaved(r.data)
      setBanner(null)
    } else handleError(r)
    return r
  }, [api, handleError])

  const open = useCallback(
    async (id: string) => {
      const r = await api.get(id)
      if (r.ok) {
        show(r.data)
        writeLast(r.data.id)
        setSession('in')
        setBanner(null)
      } else {
        if (r.kind === 'not_found') writeLast(null)
        handleError(r)
      }
      return r.ok
    },
    [api, handleError, show],
  )

  const load = useCallback(async () => {
    const r = await refreshList()
    const last = readLast()
    if (r.ok && last && r.data.some((t) => t.id === last)) await open(last)
    else if (r.ok && last) writeLast(null)
    setStarting(false)
  }, [open, refreshList])

  useEffect(() => {
    // Loading from the server on mount is synchronising with an external system; every setState inside `load` runs after an await.
    // oxlint-disable-next-line react/set-state-in-effect
    void load()
  }, [load])

  const retry = () => {
    setStarting(true)
    void load()
  }

  useEffect(() => {
    if (!dirty) return
    const warn = (e: BeforeUnloadEvent) => e.preventDefault()
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [dirty])

  const confirmDiscard = () => !dirty || window.confirm('Discard your unsaved changes?')

  // ---- editing
  const onAddNode = (kind: NodeKind) => {
    const added = addNode(doc, kind)
    edit(() => added.doc)
    setSelected({ kind: 'node', id: added.id })
  }
  const onMoveNode = useCallback((id: string, x: number, y: number) => edit((d) => moveNode(d, id, x, y)), [edit])
  const onAddLink = (source: string, target: string): string | null => {
    const r = addLink(doc, source, target)
    if (!r.ok) return r.error
    edit(() => r.doc)
    setSelected({ kind: 'link', id: r.id })
    return null
  }
  const onConnect = (source: string, target: string) => {
    const err = onAddLink(source, target)
    setNotice(err ? { tone: 'error', text: err } : null)
  }
  const onDelete = ({ nodes, links }: { nodes: string[]; links: string[] }) => {
    edit((d) => removeLinks(removeNodes(d, nodes), links))
    setSelected(null)
  }

  // ---- toolbar
  const onNew = () => {
    if (!confirmDiscard()) return
    show(EMPTY_DOC)
    writeLast(null)
  }
  const onExample = () => {
    edit((d) => ({ ...sixRouterExample(), id: d.id, version: d.version }))
    setSelected(null)
    setFitKey(`example-${Date.now()}`)
  }

  const onSave = async () => {
    setSaving(true)
    setNotice(null)
    setConflict(null)
    const r = await api.save(doc)
    setSaving(false)
    if (r.ok) {
      setDoc(r.data)
      setSavedKey(docKey(r.data))
      setServerIssues([])
      setSession('in')
      setBanner(null)
      writeLast(r.data.id)
      setNotice({ tone: 'ok', text: `Saved as version ${r.data.version}.` })
      void refreshList()
    } else if (r.kind === 'invalid') {
      setServerIssues(issuesFromReasons(r.reasons, doc))
      setNotice({ tone: 'error', text: `The server rejected the topology (${r.reasons.length} problem${r.reasons.length === 1 ? '' : 's'}). Nothing was saved.` })
    } else if (r.kind === 'conflict') {
      setConflict({ currentVersion: r.currentVersion })
    } else {
      handleError(r)
      setNotice({ tone: 'error', text: `Not saved: ${r.message}` })
    }
  }

  const reloadServerVersion = async () => {
    if (doc.id) await open(doc.id)
  }

  const saveBlock =
    session === 'out'
      ? 'Sign in to save.'
      : localIssues.length > 0
        ? `Fix ${localIssues.length} problem${localIssues.length === 1 ? '' : 's'} first.`
        : doc.id !== null && !dirty
          ? 'Nothing to save.'
          : undefined

  if (starting) return <LoadingState label="Loading topologies" />

  return (
    <div className="topo">
      {banner && (
        <div className="topo-banner" role="alert">
          <span>
            {banner.kind === 'unauthorized' ? (
              <>
                {banner.message} <Link to="/login">Sign in</Link> to save and reopen topologies. You can still edit here.
              </>
            ) : (
              banner.message
            )}
          </span>
          {banner.kind !== 'unauthorized' && <Button onClick={retry}>Try again</Button>}
        </div>
      )}

      <div className="topo-toolbar" role="toolbar" aria-label="Topology actions">
        <Button onClick={onNew}>New</Button>
        <Button onClick={() => onAddNode('router')}>Add router</Button>
        <Button onClick={() => onAddNode('host')}>Add host</Button>
        <Button onClick={onExample} disabledReason={doc.nodes.length > 0 ? 'Clear the canvas first (New).' : undefined}>
          Six-router example
        </Button>
        <label className="topo-toolbar__open">
          <span className="sr-only">Open a saved topology</span>
          <select
            value=""
            disabled={saved.length === 0}
            onChange={(e) => {
              const id = e.target.value
              if (id && confirmDiscard()) void open(id)
            }}
          >
            <option value="">{saved.length ? 'Open saved topology...' : 'No saved topologies'}</option>
            {saved.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name} (v{t.version}, {t.n_nodes} nodes)
              </option>
            ))}
          </select>
        </label>
        <span className="topo-toolbar__spacer" />
        <span className={`pill ${dirty ? 'pill--warning' : 'pill--healthy'}`}>
          <span aria-hidden="true">{dirty ? '●' : '✓'}</span> {dirty ? 'Unsaved changes' : doc.version !== null ? `Saved (v${doc.version})` : 'Empty'}
        </span>
        <Button variant="primary" onClick={() => void onSave()} disabled={saving} disabledReason={saveBlock}>
          {saving ? 'Saving...' : doc.id === null ? 'Save' : 'Save changes'}
        </Button>
      </div>

      <div aria-live="polite" role="status" className="topo-notice">
        {notice && <span className={notice.tone === 'ok' ? 'msg--ok' : 'msg--error'}>{notice.text}</span>}
      </div>
      {conflict && (
        <div className="topo-banner" role="alert">
          <span>
            Someone changed this topology since you opened it{conflict.currentVersion !== null ? ` (server version ${conflict.currentVersion}, yours ${doc.version})` : ''}. Your edits were not saved.
          </span>
          <Button onClick={() => void reloadServerVersion()}>Load server version (discards my edits)</Button>
        </div>
      )}

      {doc.nodes.length === 0 && (
        <p className="topo-hint">Empty canvas. Add routers and hosts, then connect them. Or start with the six-router example.</p>
      )}
      <div className="topo-body">
        <TopologyCanvas
          doc={doc}
          selected={selected}
          issues={issues}
          fitKey={fitKey}
          onSelect={setSelected}
          onMoveNode={onMoveNode}
          onConnect={onConnect}
          onDelete={onDelete}
        />
        <TopologyInspector
          doc={doc}
          selected={selected}
          issues={issues}
          onSelect={setSelected}
          onRename={(name) => edit((d) => ({ ...d, name }))}
          onRenameNode={(oldId, newId) => {
            const r = renameNode(doc, oldId, newId)
            if (r.ok) {
              edit(() => r.doc)
              setSelected({ kind: 'node', id: newId })
            }
            return r
          }}
          onSetKind={(id, kind) => edit((d) => setNodeKind(d, id, kind))}
          onDeleteNode={(id) => onDelete({ nodes: [id], links: [] })}
          onUpdateLink={(id, patch: LinkPatch) => edit((d) => updateLink(d, id, patch))}
          onDeleteLink={(id) => onDelete({ nodes: [], links: [id] })}
          onAddLink={onAddLink}
          onAddReverse={(id) => {
            const l = doc.links.find((x) => x.id === id)
            return l ? onAddLink(l.target, l.source) : null
          }}
        />
      </div>
    </div>
  )
}
