# Topology Studio screen: local design spec

- **Stitch screen:** `projects/11953126075048924226/screens/bee8e9555edb4fbda649a48a5ef3c5d2`, title "NeuroRoute AI - Topology Studio", desktop capture 2560 x 2490.
- **Captured:** 2026-10-22, from the screen's exported HTML (read-only via Stitch MCP `download_file`; HTML sha256 prefix `3b799ff323fb`, 62,087 chars). The HTML is **not committed** (CDN dependencies, see [HANDOFF.md](../HANDOFF.md)). No screenshot was captured.
- **Prompt provenance:** the "exact Topology Studio screen prompt" named in the task was **not supplied**, and no new screen was generated (that writes to the Stitch account). This spec describes the **existing** screen.
- **Tokens:** [../../tokens.json](../../tokens.json) -> `frontend/src/styles/tokens.css`. CSS variables below are real names from that file.
- **Legend:** **[Stitch]** = drawn in the design. **[PROPOSED]** = not in Stitch; written here because the task requires it. Proposals are not approved design.

> **Data warning.** Every number, name and claim on this screen is Stitch sample data: 64 nodes / 192 interconnects (only about 15 labelled nodes are actually drawn), IPs, ASNs, DPDK, "H100/A100" pods, convergence probabilities, queue depths. None may be shown as live. The screen's own buttons call `alert()` with **fabricated outcomes** (e.g. "Average convergence time = 1.48 ms across all 64 nodes", "written to DPDK kernel cache"); that behavior must never ship.

## 1. Purpose

Build, inspect and validate the network topology and scenario that a routing experiment will use: see the graph, select a node or link, edit its parameters, compare candidate paths, and check the scenario is valid before running.

## 2. Layout (desktop) [Stitch]

Same shell as Overview: fixed sidebar 248 px, fixed top bar 64 px (`--glass-bg`, `blur(var(--glass-blur))`), content on `--color-surface`.

| # | Region | Contents |
|---|---|---|
| 1 | Page header | H1 "Topology Studio & Scenario Builder" + version tag; subtitle; actions: **Run Path Convergence Test** (`⌘Enter`), **Simulate Congestion**, **Export**. A "Preview Workspace State" switcher (Node: CR-01 / RL vs OSPF Path / Validation Alert / Empty State) is a design aid, **not** a product feature |
| 2 | Canvas toolbar | Reset, zoom out / `100%` / zoom in / fit (zoom clamped 0.6-1.8), layout `<select>` (Hierarchical Spine-Leaf, Force-Directed, Circular Chord), **Grid Snap** toggle (on by default), overlay checkboxes: Weights, Congestion, RL Divert, BGP ASNs |
| 3 | Graph canvas | `xl:` 8 of 12 columns; min height 580 px; inset dark background with a 24 px dot grid and three blurred ambient glows (decorative, `pointer-events-none`); SVG graph with tiered nodes (Spine core top, Leaf middle, Gateways/pods/storage bottom); edge labels (`0.42ms W:10`, `3.85ms W:42.8 Drop 0.12%`, `DOWN: 3 Retries`, `RL-BYPASS ACTIVE`, `91% QUEUE SATURATION`); legend (tiers, `<1 ms healthy`, `>3 ms congested`, divert path); path-comparison card (RL divert vs static ECMP) with an "Inspect Vector" text link that opens the Candidate Paths tab |
| 4 | Inspector | `xl:` 4 of 12 columns; three tabs: **Node Attributes**, **Candidate Paths**, **Scenario & Faults** |
| 4a | Node Attributes | Node name + `UP` pill + id; tiles: Queue Depth, P99 Latency, Egress Rate; Hardware Specification list; "Connected Interconnects & Peers" table (Peer, Metric, **Weight** number input, **Link Status** toggle); "RL Policy Weights": sliders Alpha 0-1 step 0.05, Beta 0.1-3 step 0.1, Max Divert Hops stepper (min 1) |
| 4b | Candidate Paths | Two cards: policy-selected path (score, RTT, queue, drops, rationale) vs static OSPF/ECMP path (status Degraded) |
| 4c | Scenario & Faults | Preset (`READY`), injection target, burst duration, PRNG seed, **Trigger Instantaneous Link Jam**; validation panel; **Apply Topology Changes (Local Cache)** and **Discard Edits** |
| 5 | Empty state | Replaces the graph: "No Active Topology Synthesized", actions "Generate Spine-Leaf Matrix (v2)", "Load Demo Benchmark" |

Responsive [Stitch]: grids use `sm`/`md`/`lg`/`xl` utilities (canvas/inspector split at `xl`), so below `xl` they stack; **no tablet or mobile design** was drawn.

## 3. Graph encoding [Stitch]

- Nodes are **circles** (radius 26) with a router-style icon and the label underneath; the active node has a pulsing halo (`animate-pulse`, radius 36) and a glow filter. 12 nodes are clickable via `selectNode()`; one leaf is labelled `[HOT]`.
- Edges: neutral (`#454652` family) by default; **healthy** and **congested** use gradients; **RL divert** path uses an accent glow and `animate-pulse`; dashed patterns (`6 4`, `2 3`, `3 4`, `6 3`, `4 4`) mark special links.
- State is carried mostly by **color and dash**, plus some text labels. Color-only cues are an accessibility gap (see section 6).

## 4. States

| State | Status | What it shows |
|---|---|---|
| **Selected node** (default) | [Stitch] "Node: CR-01" | Node Attributes tab, `Graph Validated` (check icon, secondary color), `0 LOOPS` |
| **Path comparison** | [Stitch] "RL vs OSPF Path" | Candidate Paths tab |
| **Validation alert** | [Stitch] | warning icon + title "Validation Alert", extra micro-loop sub-alert text; graph-level, not tied to one link |
| **Empty** | [Stitch] | graph hidden, empty-state card |
| **Zoom, grid snap, layout switch, overlay toggles** | [Stitch] | interaction only, no persistent state |
| **Edit mode** (add / move / delete node, draw / delete link, edit link fields) | **not designed.** Stitch only edits link **weight** (number input) and link **status** (toggle) on existing adjacencies, plus policy sliders. There is no way to add a node, create a link, or drag nodes | **[PROPOSED]** see below |
| **Invalid link** | **not designed** at link level (only the graph-level alert above, plus a link labelled `DOWN: 3 Retries`, which is a runtime fault, not an invalid config) | **[PROPOSED]** see below |
| **Disabled** | **not designed.** No `disabled` attribute, no `cursor-not-allowed`, no `disabled:` styles anywhere in the HTML. The `opacity-20` / `pointer-events-none` classes belong to the decorative dot grid and glows, not to controls | **[PROPOSED]** see below |
| **Loading / backend error / unauthenticated / saving / save failed** | **not designed** | needed (app already has text error states for health and `/me`) |
| **Read-only / running** (scenario locked while a run is in progress) | **not designed** | needed once runs exist |

### [PROPOSED] Edit mode

Selecting a link opens a **Link** inspector tab with fields mapped 1:1 to the `Link` schema (`id`, `source`, `target`, `capacity_mbps`, `prop_delay_ms`, `buffer_pkts`, `weight`). Toolbar gains Add node, Add link (pick source then target), Delete, Undo/Redo. Unsaved edits show a dirty indicator on **Apply**/**Discard**. Layout positions are view state only; they are not in the scenario and do not change `config_hash`.

### [PROPOSED] Invalid-link states

Validation uses the real rules in `backend/research/simulation/models.py` and shows the first failing message next to the field, the offending edge drawn with a solid `--color-error` stroke **and** an error icon label (not color alone), and a summary count in the validation panel:

| Rule (schema) | Where it appears |
|---|---|
| unknown endpoint (source/target not a node) | edge to a dangling stub; Source/Target field error |
| self-loop (`source == target`) | loop glyph on the node; field error |
| duplicate node / link / flow id | id field error on both items |
| `capacity_mbps <= 0`, `buffer_pkts <= 0` | field error, edge flagged |
| `prop_delay_ms < 0`, `weight < 0` | field error, edge flagged |
| NaN / Infinity, or a non-numeric entry | field error; the value is not accepted |
| id not matching `[A-Za-z0-9_-]{1,32}` | id field error |

While any error exists, **Apply** and **Run** are disabled and say why (tooltip or inline text, not hover-only). The micro-loop / convergence-probability claims in Stitch are not backed by any implemented analysis and are **not** adopted.

### [PROPOSED] Disabled state

Controls that cannot act right now (Apply while invalid or unchanged; Run while invalid, empty or running; Delete with nothing selected; fields while read-only) use the real `disabled` attribute (or `aria-disabled="true"` for buttons that explain themselves), `opacity: 0.5`, `cursor: not-allowed`, no hover or press effect, and the border `--color-border` with text `--color-muted`. Disabled controls stay in the tab order only if they carry an explanation. No disabled token exists yet; add `color.disabled` (or reuse opacity) when building. WCAG exempts inactive controls from contrast minimums, but the reason must be readable.

## 5. Token references

| Element | Token (CSS variable) |
|---|---|
| Page / sidebar / content backgrounds | `--color-bg`, `--color-surface` |
| Toolbar, inspector, legend, cards | `--glass-bg`, `--glass-blur`, `--color-border`, `--radius-surface`, `--shadow-low` |
| Floating inspect card, popovers | `--radius-overlay`, `--shadow-high` |
| Buttons, chips, tabs, toggles | `--radius-control`; press `--motion-press-scale` over `--motion-fast` |
| Inputs, select, number fields | `--radius-surface`, `--color-border`, `--focus-ring`, `--color-accent` |
| Healthy / congested / critical edges and LEDs | `--status-healthy`, `--status-warning`, `--status-critical`, `--status-telemetry` |
| Status text | `--color-ok`, `--color-warn`, `--color-error`, `--color-info` |
| Selected node ring, divert path, active tab | `--color-accent`, `--color-accent-soft`, `--color-accent-text` |
| Row / button hover | `--color-hover` |
| Text, captions | `--color-text`, `--color-muted` |
| Headings | `--type-headline-lg-*`, `--type-headline-md-*` |
| Body, table | `--type-body-md-*`, `--type-body-sm-*` |
| Node ids, IPs, weights, latencies | `--type-code-md-*`, `--type-code-sm-*` |
| Eyebrow / tab labels | `--type-label-caps-*` |
| Spacing | `--space-xs` ... `--space-xl` |
| Graph transitions (zoom, selection) | `--motion-fast`, `--motion-live`, `--motion-ease` |

### Gaps and conflicts found

1. **Palette mismatch.** The HTML uses the YAML palette (canvas `#0f131b`, inset canvas `#0a0e16`, primary `#bdc2ff`, container `#7d88ee`), not `tokens.json` (`#10141C`, brand `#6974D9`). `tokens.json` stays the source; do not copy hex values from the HTML.
2. **Missing tokens.** The darker graph inset (`#0a0e16`), sidebar 248 px, top bar 64 px and the disabled style have no tokens. Proposal: `color.canvas_inset`, `layout.sidebar_width`, `layout.topbar_height`, `color.disabled`. Not added in this task.
3. **Weight input is unconstrained.** Stitch's `<input type="number">` for weights has no `min`, `max` or `step`, so it would accept negative or fractional-garbage values. The schema requires `weight >= 0` and finite. Use `min="0"` plus the same validation as the backend.
4. **Counts do not add up.** Subtitle claims 64 nodes / 192 interconnects; about 15 labelled nodes and 26 `path` elements are drawn. Do not trust counts from the design.
5. **Breadcrumb bug.** The top bar reads "Workspaces / NeuroRoute / Overview" on the Topology page.
6. **Hosted icons.** Material Symbols font from Google Fonts is a hosted asset; choose a local icon approach.
7. **Decorative effects.** Three blurred glows (100-120 px blur) and a dot grid cost rendering time on large canvases; make them optional and off under `prefers-reduced-motion`. `animate-pulse` / `animate-ping` need their own reduced-motion guard (the duration tokens alone do not stop keyframes).

## 6. Accessibility requirements (the HTML has 0 `aria-*` and 0 `role` attributes)

- The SVG needs a text alternative and a **keyboard-operable** structure: nodes and edges focusable, arrow keys to move between neighbours, Enter to select, visible `--focus-ring`; plus an equivalent **table/list view** of nodes and links for screen readers.
- Edge state must not rely on color or dash alone: pair every state with an icon or text label.
- Icon-only buttons (zoom, fit, reset, delete, more) need accessible names; the zoom level is announced.
- Inspector tabs: `role="tablist"` / `tab` / `tabpanel`, arrow-key navigation.
- Validation messages linked to fields with `aria-describedby`; summary in a live region.
- Drag-based editing needs a keyboard alternative (numeric position or add-by-form).
- `⌘Enter` shortcut is macOS-only; this is a Windows laptop (use `Ctrl+Enter` or none; check it does not clash with the form).

## 7. Data honesty: what each element may show in NeuroRoute today

| Stitch element | Real source today | Status |
|---|---|---|
| Node: id, kind | `Scenario.nodes` (`id`, `kind` router or host) | schema exists; **no API route or repository** serves scenarios yet |
| Node IP, ASN, port density, driver/kernel, "H100/A100", tiers | not in schema (v1.0 forbids unknown fields) | **remove**; tiers could be derived from graph structure later |
| Link: capacity, propagation delay, buffer, weight | `Scenario.links` (`capacity_mbps`, `prop_delay_ms`, `buffer_pkts`, `weight`); links are **directed** (Stitch draws undirected adjacencies) | schema exists; show duplex as two links |
| Link "Metric" (0.38 ms), queue %, drop % | runtime measurements; no simulator exists | **blocked**; show configured propagation delay, label it "configured", never as measured |
| Link Status toggle | failure events `down`/`up` at a time (`FailureEvent`); no static up/down flag | **partial**: model as a scheduled event, not a toggle |
| `DOWN: 3 Retries`, saturation, `RL-BYPASS ACTIVE` | simulation output | **blocked** |
| Layout algorithms (hierarchical, force-directed, circular) | none; positions are not in the schema | **frontend-only** view state (client computes layout); must not affect `config_hash` |
| Candidate paths, RTT/queue/drops, scores, "policy selection" | no routing baseline or model | **blocked**; a weight-based shortest path would be the first honest baseline once implemented |
| RL Policy Weights (alpha, beta, max hops), model name | agent hyperparameters, no model | **remove from this screen**; belongs to a training screen |
| Scenario: traffic preset, burst duration, injection target | schema has `traffic` (`cbr`/`poisson`, packet size), `flows`, `failures`; no burst duration | **partial** |
| PRNG seed | `Scenario.seed` | **available** (field exists) |
| Config identity | `Scenario.config_hash` (SHA-256 of canonical JSON; independent of node/link order) | **available**, show it on the page |
| Validation panel ("Graph Validated", "0 loops", "p=0.998") | real validators exist (section 4), no loop/convergence analysis | **partial**: show real validation results only |
| Run Path Convergence Test, Simulate Congestion, Trigger Link Jam | none | **blocked** (disabled with reason) |
| Export | `Scenario` JSON (+ `config_hash`) can be produced from the model | **feasible** once a route exists |
| Apply (Local Cache) / Discard | no save API or repository | **blocked** |
| "Local ONNX runtime loopback", "air-gapped" | not applicable / unverifiable | **remove**; verifiable claim: services bound to 127.0.0.1 |
| Sample data (`base_scenario.json` is a 4-node diamond) | `experiments/configs/base_scenario.json` | use as the first real fixture; label it "example scenario" |

## 8. First buildable slice

With only the schema and `/health`, `/me`: read-only graph view of a loaded scenario (client-side layout, node/link inspector with the real fields, `config_hash`, validation summary using real rules), the empty state, and every action that has no backend shown **disabled with a reason**. Editing and saving wait for a scenario API. Suggested components (small files under `frontend/src/components/`, consuming only CSS variables): `GraphCanvas`, `NodeBadge`, `EdgeLabel`, `InspectorTabs`, `LinkFields`, `ValidationList`, `DisabledReason`, `EmptyState`.

## 9. Open questions for the owner

1. Provide the original Topology Studio prompt if it should be stored.
2. Should Stitch be re-prompted to draw edit mode, invalid-link and disabled states (so the proposals above become approved designs)?
3. Directed links: keep one arrow per direction in the UI, or collapse duplex pairs into one drawn edge?
