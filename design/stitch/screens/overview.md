# Overview screen: local design spec

- **Stitch screen:** `projects/11953126075048924226/screens/2439df6b3eba4b949daa74db7b322d54`, title "NeuroRoute AI - Research Workspace Overview", desktop capture 2560 x 3764.
- **Captured:** 2026-10-21, from the screen's exported HTML (read-only via Stitch MCP `download_file`). HTML sha256 prefix `343bf2cf842b`. The HTML is **not committed** (CDN dependencies, see [HANDOFF.md](../HANDOFF.md)). No screenshot was captured.
- **Prompt provenance:** the "exact NeuroRoute Overview screen prompt" named in the task was **not supplied**, and no new screen was generated (that writes to the Stitch account). This spec describes the **existing** generated screen. The screen "NeuroRoute AI Lab Prototype" (`b56f019e88d645bfa2fcf2553388deab`) returned byte-identical HTML, so it is a duplicate of this design.
- **Tokens:** [../../tokens.json](../../tokens.json) -> `frontend/src/styles/tokens.css`. CSS variables below are real names from that file.

> **Data warning.** Every number, name and status on this screen is Stitch **sample data** (the screen itself labels it "DEMO / SAMPLE DATA"). Much of it describes hardware and software this project does not have (Apple M3 Max, MPS, DPDK, PyTorch 2.3, a 64-node spine-leaf mesh, trained PPO policies, past runs). None of it may be shown as live or as a research result. See "Data honesty" below.

## 1. Purpose

Landing page of the research workspace: what study is loaded, whether the local engine is ready, headline comparison of the learned routing policy against a static baseline, recent runs, and quick actions (fault injection, export, new experiment).

## 2. Layout (desktop)

Shell: fixed **left sidebar 248 px** (`--color-bg`, no border, `--shadow-low`), fixed **top bar 64 px** offset by the sidebar (`--glass-bg` + `backdrop-filter: blur(var(--glass-blur))`), content below the bar on `--color-surface`, centered, **max width 1680 px**. Content is a vertical stack with `--space-lg` gaps.

| # | Region | Contents | Grid |
|---|---|---|---|
| 0 | Sidebar | Brand + "Local Lab (Offline / Isolated)"; workspace switcher; nav: Overview (active), Routing Topology, Policy Models, Experiments & Runs, Benchmarks, Hardware & Sim Engine, Settings; "Device Node" card (ACTIVE, engine, CPU %, MEM, mode toggle) | fixed column |
| 1 | Top bar | Breadcrumb Workspaces / NeuroRoute / Overview; status chip "Local: Ready (vX)"; "Sample Data" badge; links Documentation, Handoff Tokens; notifications; user chip (name, role) | flex row, space-between |
| 2 | State switcher strip | Three buttons that flip the screen between the Stitch variants (design aid, **not** a product feature) | row |
| 3 | Study header | Breadcrumb (suite / experiment id), "DEMO / SAMPLE DATA" tag, H1 study title, objective sentence, three actions: Simulate Fault Injection, Export Telemetry, Start New Experiment; chip row: Topology, Policy, Local Device, Status, buffer info; in-flight progress bar with epoch, frames, ETA | stacked |
| 4 | KPI tiles | P99 Latency, Packet Drop Rate, Jitter StdDev, Sim Engine Throughput; each: label, value + unit, baseline comparison, delta badge, footnote | 1 col / `sm` 2 cols / `xl` 4 cols |
| 5a | Latency profile chart | Title, "Sample Telemetry" tag, range toggle (10k / 100k / Stress), two series + legend, burst-window band, hover inspection card, x-axis ticks, 4 summary stats | `lg` 12-col grid, **8 cols** |
| 5b | Simulation & Hardware card | Status chip, 3 capability rows, "Pre-Flight Verification" checklist (3 items), "Re-run Diagnostic Self-Test" button | `lg` **4 cols** |
| 6 | Recent Experiment Runs | Title + caption; search input; filter toggle All / Completed / Interrupted; "Compare Selected (0/2)"; table: select, Run ID, Timestamp, Agent / Algorithm, Topology & Traffic, P99 Latency, Packet Loss, Status, Actions (insights, replay, download) | full width |
| 7 | Fault-injection modal | Title, close, description, Target select (3 options), Fault Type segmented (Spike Delay +25 ms, Link Flap 3 Hz, Blackhole Drop), freeze-clock note, Cancel / Apply Perturbation | overlay, `max-w-4xl` |

Responsive: only the 2560 desktop capture exists. The HTML uses `sm`/`md`/`lg`/`xl` breakpoints for the KPI and chart grids, but there is **no tablet or mobile design**. The brief says rails collapse to slide-overs on tablet and metric tiles stack on mobile; that is not drawn.

## 3. States

| State | In Stitch | Visible changes |
|---|---|---|
| Complete data | yes ("Active State") | all KPIs, chart, table populated; status Ready |
| Simulation in flight (68%) | yes | progress bar with epoch/frames/ETA; pulsing activity; KPIs partially live |
| Pre-run empty canvas | yes | empty-state card "No Telemetry Recorded for Active Topology" with actions "Load Sample Baseline Run" and "Select Topology Preset" |
| Fault modal open | yes | modal over a dimmed screen |
| Row/button hover, focus | partly (8 `hover:`, 5 `focus:`, 1 `active:` utility uses) | no designed disabled state |
| **Loading** (data fetching) | **no** | needed |
| **Backend unreachable / error** | **no** | needed; app already has this text state (`BackendStatus`: "Backend unavailable: ...") |
| **No scenario / no runs yet** | partly (empty canvas) | needed, and it is the **real** first-run state |
| **Run failed / interrupted** | row status only ("Manual Halt") | needs detail view |
| **Unauthenticated** | **no** | needed; `/me` returns 401/403 |

## 4. Token references

| Element | Token (CSS variable) |
|---|---|
| Page / sidebar background | `--color-bg` (sidebar), `--color-surface` (content) |
| Cards, table block | `--glass-bg`, `--glass-blur`, `--color-border`, `--radius-surface`, `--shadow-low` |
| Modal, command overlays | `--radius-overlay`, `--shadow-high`, `--glass-bg` |
| Buttons, chips, badges, toggles | `--radius-control`; press: `--motion-press-scale` over `--motion-fast` |
| Inputs, selects | `--radius-surface`, `--color-border`, focus `--focus-ring` / `--color-accent` |
| Status pills / LED dots (healthy, warning, critical, telemetry) | `--status-healthy`, `--status-warning`, `--status-critical`, `--status-telemetry` |
| Status **text** (AA contrast) | `--color-ok`, `--color-warn`, `--color-error`, `--color-info` |
| Brand fill (primary buttons, active nav) | `--color-accent` (white text only bold/large: 4.12:1) |
| Links, active nav text | `--color-accent-text` |
| Hover overlay on rows/nav | `--color-hover` |
| Body, muted, captions | `--color-text`, `--color-muted` |
| Page title, section titles | `--type-headline-lg-*`, `--type-headline-md-*` |
| Body / table text | `--type-body-md-*`, `--type-body-sm-*` |
| IDs, latencies, hashes, numbers | `--type-code-md-*`, `--type-code-sm-*` (mono, tabular figures) |
| Eyebrow labels (e.g. "ACTIVE") | `--type-label-caps-*` |
| Spacing | `--space-xs` ... `--space-xl` (Stitch uses `space-xs/sm/md/lg` utilities, same scale) |
| Live-data transitions | `--motion-live` with `--motion-ease` |

### Gaps and conflicts found

1. **Palette mismatch.** The Stitch HTML is painted with the YAML palette (canvas `#0f131b`, primary `#bdc2ff`, container `#7d88ee`), not the prose palette in `tokens.json` (canvas `#10141C`, brand `#6974D9`). `tokens.json` is the approved source; accept the small visual drift and do not copy hex values from the HTML.
2. **Missing layout tokens.** Sidebar width 248 px, top-bar height 64 px, content max width 1680 px, modal max width are not tokens. Proposal: add `layout.sidebar_width`, `layout.topbar_height`, `layout.content_max` to `design/tokens.json` when the shell is built. Not added in this task.
3. **Icons.** The screen uses the Material Symbols icon **font** (names like `grid_view`) from Google Fonts: a hosted asset. A local icon approach (inline SVG or an icon package) must be chosen; none is installed.
4. **Motion.** Stitch uses bare `transition-all` / `transition-colors` (no durations) and one `duration-300`; use `--motion-fast`/`--motion-live`. `animate-pulse` / `animate-spin` must stop under `prefers-reduced-motion` (already zeroes the duration tokens; keyframe animations need their own guard).
5. **Accessibility.** The HTML has 37 buttons, 7 inputs and a table but only 1 `aria-*`, 1 `role` and 1 `alt` attribute. Icon-only buttons need accessible names; table needs a caption and labelled row checkboxes; progress needs `role="progressbar"` with values; modal needs `role="dialog"`, focus trap and Esc.
6. **Shortcut.** Stitch shows `⌘N`; this is a Windows laptop and Ctrl+N is the browser's. Avoid or choose another binding.

## 5. Data honesty: what each element may show in NeuroRoute today

| Stitch element | Real source today | Status |
|---|---|---|
| "Local: Ready (v0.8.4-dev)" | backend `GET /health` (`version` 0.1.0) | **available** |
| Signed-in user chip (name, role) | `GET /me` (uid, email, role) behind the Auth emulator | **available** (no display name field) |
| "Sample Data" / "DEMO" badge | n/a | keep on anything that is fixture data; hide only when data is real |
| Study title, topology name, seed | `Scenario` schema (`name`, `seed`, `config_hash`); `experiments/configs/base_scenario.json` is a 4-node diamond | schema exists, **no API route or repository serves scenarios yet** |
| Policy "PPO-ActorCritic-v4.1", checkpoint file + SHA256 | none: no model has been trained | **blocked**: show "No model trained" |
| KPI tiles, latency chart, run table, deltas, "reward converged" | none: no simulator, environment or evaluation code exists | **blocked**: show empty/"No runs yet"; never render the sample numbers |
| Device Node: CPU %, MEM, "Engine: PyTorch 2.3 + DPDK", "M3 Max / MPS" | none; this machine is Windows, Core i7-13650HX, torch 2.14.1 **CPU**, no DPDK/MPS | **remove**; a real system-info endpoint would be a new task |
| "DPDK ring buffers", "/dev/shm ring", "Zero Cloud Egress / Airgap" | not applicable / unverifiable | **remove**; the verifiable claim is "services bound to 127.0.0.1" |
| Fault injection: target component, Spike Delay, Link Flap 3 Hz, Blackhole Drop | schema supports failure events `down`/`up` on a link at a time; no delay-spike or flap type | **partial**: only link down/up is modelled |
| Experiment table, Export Telemetry (CSV/JSON), Compare Selected | none: no runs repository | **blocked** |
| Mininet / hardware checks | Mininet not installed | **blocked**; show "not available" |

## 6. First buildable slice (honest Overview v1)

Using only what exists: Sidebar + TopBar shell, backend status pill (health), signed-in user chip (`/me`), page header with the "no scenario loaded / no runs yet" empty state and a "Sample Data" fixture toggle that is off by default. Everything else waits for the simulation, evaluation and runs services. Suggested components (each a small file under `frontend/src/components/`, consuming only CSS variables): `AppShell`, `Sidebar`, `TopBar`, `StatusPill`, `PageHeader`, `EmptyState`, `Card`, `KpiTile` (accepts real values, renders an empty state when none).

## 7. Open questions for the owner

1. Provide the original Overview prompt if it should be stored (add it to `MASTER_PROMPT.md`).
2. Is Overview v1 (section 6) the right first slice, or should Stitch be re-prompted to drop the hardware/DPDK content?
3. Icon strategy (inline SVG vs a package) and whether to add the layout tokens now.
