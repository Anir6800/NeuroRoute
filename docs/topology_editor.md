# Topology Studio (React Flow editor)

`/topology` draws, checks, saves and reopens a network through the local topology API ([topology_api.md](topology_api.md)).
Code is in `frontend/src/features/topology/`; the page `pages/Topology.tsx` only adds the header.

| File | Role |
|---|---|
| `TopologyCanvas.tsx` | React Flow canvas. Controlled: the document is the single source of truth. Drag moves nodes, dragging from a node's right dot to another node's left dot adds a link, Delete/Backspace removes the selection. |
| `TopologyInspector.tsx` | Side panel: network name, the selected node or link (id, type, capacity, delay, buffer, weight, delete, add reverse link), an "Add a link" form, and the Problems list. |
| `TopologyStudio.tsx` | Toolbar and state: new, add router/host, six-router example, open saved, save; load/save/conflict handling. |
| `model.ts`, `validate.ts`, `api.ts`, `geometry.ts`, `FloatingEdge.tsx` | Pure document operations, local validation, typed API client, edge geometry, the edge component. |
| `lib/session.ts` | The signed-in user's ID token, loaded on demand so Firebase stays out of the main bundle. |

## How it behaves

- **Create:** Add router / Add host place nodes on a grid; links are created by dragging between handles or with the form (a keyboard-friendly alternative). Links are directed; a cable is two links, and the two directions are drawn side by side.
  The six-router example is a convenience template (ring plus one chord), offered only on an empty canvas.
- **Validate:** every edit is checked locally with the same reason codes as the backend (a test fails if the backend gains a code the editor lacks).
  Problems are listed, the affected node or link is outlined, and Save is blocked with a visible reason. The server still validates every save; its 400 reasons are shown and
  attached to the elements they name until the next edit.
- **Save:** the first save creates (POST), later saves update (PUT with the version). Positions are saved with the graph (rounded to 0.1) and do not change its `content_hash`.
  A stale version shows a conflict banner with "Load server version" (discarding local edits); nothing is overwritten.
- **Reload:** the last saved id is remembered in `localStorage` (a per-browser convenience, ignored if storage is blocked), so a page reload reopens the same network at the same positions.
  "Open saved topology" lists your other topologies. Leaving with unsaved changes asks the browser to confirm.
- **Not signed in / backend down:** a banner says so (with a link to `/login`, or Try again). Editing still works; saving is disabled with a reason. Nothing is faked.

## Verification

- `npm test` (frontend, from `frontend/`): model, validation, API client, edge geometry and the studio flows with a fake API in jsdom, including create six routers by hand, save, and reopen after a "reload".
- `node scripts/topology-e2e.mjs` (stack running, `scripts/dev-neuro.sh`): the same flow in real headless Chrome against the real backend and Auth emulator, with real mouse drags (move a node, connect two nodes by dragging handles, refuse a self-link), a save, a full page reload and a comparison of every node position. Screenshots go to `.ui-audit/`.

## Limits

- Not a layout tool: no auto-layout, undo/redo, multi-select moves, or copy/paste.
- Weak connectivity only (see the API doc); a saved topology can still have pairs with no directed route.
- The top-bar "Sign in" link is not session-aware (existing); the studio reads the session itself.
- A stored topology is not yet used by the simulator or training; scenarios still come from `experiments/configs/`.
- jsdom cannot drag, so mouse dragging and handle connections are covered only by the browser script, which is run by hand, not in CI.
- React Flow shows its small attribution link; it is left on.
