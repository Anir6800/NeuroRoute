# Experiments & Runs screen: local design spec

- **Stitch screen:** `projects/11953126075048924226/screens/3f7210fb06d244cbb7aa15f7d248696f`, title "NeuroRoute AI - Experiments & Runs", desktop capture 2560 x 2708.
- **Captured:** 2026-10-22, from the screen's exported HTML (read-only via Stitch MCP `download_file`; sha256 prefix `a5b2717d5e26`, 52,508 chars). The HTML is **not committed** (CDN dependencies, see [HANDOFF.md](../HANDOFF.md)). No screenshot was captured.
- **Prompt provenance:** the "exact" Experiments prompt named in the task was **not supplied**, and no screen was generated (that writes to the Stitch account). The task asked to generate this screen and Model Comparison *separately* and then compare continuity: this spec and [model-comparison.md](model-comparison.md) describe the **existing** screens, and the continuity comparison is in model-comparison.md section 6.
- **Tokens:** [../../tokens.json](../../tokens.json) -> `frontend/src/styles/tokens.css`. CSS variables below are real names from that file.
- **Legend:** **[Stitch]** = drawn in the design. **[PROPOSED]** = not in Stitch; not approved design.

> **Data warning.** Every run, id, hash, latency and path on this screen is Stitch sample data (48 runs, "DPDK + CUDA FP16", `/var/neuro/...` paths, a `neuroroute.train` CLI, "p=0.998"). **No run history, runs repository or training code exists in this repository yet.** Nothing may be shown as live.

## 1. Purpose

Browse, filter and compare past and running experiments, inspect one run in a side drawer (config, logs, checkpoint, telemetry), and reproduce or export it.

## 2. Layout (desktop) [Stitch]

Shell **variant B**: fixed sidebar 248 px on `-low` surface, fixed top bar **56 px** with a bottom border (the Overview/Topology/Training screens use 64 px and a different sidebar fill; see the continuity table).

| # | Region | Contents |
|---|---|---|
| 1 | Page header | H1 "Experiments & Local Run History", "Auto-Sync (5s)" chip, description; actions **Batch Export**, **Compare Selected (2)**, **Flush Logs**, **Run New Experiment** (`⌘N`). A four-button **state preview** switcher is a design aid, not a product feature |
| 2 | Search + filters | Search input (`⌘K` hint); status chips with counts: All 48, Converged 34, In-Flight 1, Stalled 4, Aborted 9; time range "Last 7 Days (Local)"; filter pills Topology, Policy, Traffic, Deterministic Seed (removable) and a "Hardware Acceleration" label |
| 3 | Runs table | `lg:` 12-col grid, table **7 of 12**: select checkbox, Run ID & Status (+ short hash), Started / Time (+ duration), PRNG Seed, Scenario & Topology, P99 Latency (+ delta), Loss %, Actions |
| 3a | Pagination | "Showing 1-6 of 48 runs", rows per page 10/25/50, previous (**disabled on page 1**), pages 1 2 3 ... 8, next |
| 3b | Summary strip | "Deterministic Policy Convergence 87.5%" over 42 batch runs, Global Avg Latency, Mean P99 Gain |
| 4 | Run drawer | `lg:` **5 of 12**; open/close, pin, expand. Run id + status, title, created time + commit; tabs **Config Manifest**, **Logs (4)**, **Checkpoint**, **Telemetry**; reward-convergence chart; latency stats; reproducible hyperparameters; replay command with copy; weights card (Download .pt, ONNX Export, Load in Topology Studio); runtime stdout/stderr panel (PID, log lines); Stream Live Logs; Export Telemetry Dataset; **Clone Run as New Baseline Spec** (`⌘D`) |

Responsive [Stitch]: `sm`/`md`/`lg`/`xl` utilities (5 `overflow-x-auto` wrappers); **no tablet or mobile design**.

## 3. Table design and run statuses [Stitch]

Status is carried by **glyph + text + color** (good, not color alone): `● Converged`, `◌ In-Flight` (with percent), `▲ Stalled`/`▲ Diverged`, `✕ Aborted`/`✕ OOM / Aborted`, `Baseline`. Deltas carry a sign and a reference ("-57.9% vs OSPF", "+57.2% vs Base"). Row actions depend on status:

| Status | Row actions drawn |
|---|---|
| Converged, Baseline | view, replay, download |
| In-Flight | pause, stop |
| Diverged | view, replay (no download) |
| OOM / Aborted | bug report (logs), replay |

## 4. States

| State | Status | Notes |
|---|---|---|
| Populated table + drawer open | [Stitch] "Active: Detail Drawer Open" | default |
| Drawer closed | [Stitch] "Variant: Cold Start" only **hides the drawer**; the table is not replaced | the preview button is named Cold Start, but **no empty state is drawn** (no markup for "no runs") |
| Filtered to fault-injection runs | [Stitch] button only | **no behavior wired** in the HTML script |
| Execution error | [Stitch] button only | **no behavior wired**; failed runs appear only as table rows (Diverged, OOM / Aborted) |
| In-flight row | [Stitch] | progress percent, pause/stop actions |
| Page 1 | [Stitch] | previous-page button is **disabled** (`disabled:opacity-30`): the **only** disabled control in the design |
| **Empty (no runs yet)** | **not designed** | **[PROPOSED]** see below; this is the real first-run state |
| **Loading / backend unreachable / unauthenticated / auto-sync failed** | **not designed** | needed |
| **Compare Selected disabled** (fewer than 2 rows selected) | **not designed** | **[PROPOSED]** disabled with reason "Select 2 runs" |
| **Destructive confirm** (Flush Logs) | **not designed** | **[PROPOSED]** confirmation dialog stating exactly what is deleted |
| **No results for filters** | **not designed** | **[PROPOSED]** "No runs match" with a Clear filters action |

Taxonomy inconsistency in the design: filter chips are Converged / In-Flight / Stalled / Aborted, but rows also show **Baseline** and **Diverged**, which have no chip (34+1+4+9 = 48, so they must be hidden inside other chips). The failure vocabulary must be one shared set across Training Lab, Experiments and Comparison: `Converged`, `Running`, `Diverged`, `OOM`, `Timeout`, `Crashed`, `Aborted`, `Baseline` (reference, not a status of a run's health).

### [PROPOSED] Empty state

Card in place of the table: "No experiments recorded yet", the one-line reason (no run has completed on this machine), and one action that exists (**Open Training Lab**; disabled with reason until a trainer exists). Filters, search, Compare, Batch Export and pagination are disabled and say why.

## 5. Readability audit (data table)

Measured from the exported HTML (class counts) and the Stitch palette (contrast ratios):

| Check | Result |
|---|---|
| Table text size | 119 of 215 text-size uses on the screen are 10-11 px (`code-sm` 88, `label-caps` 15, `[10px]` 13); body cells are 11 px mono |
| Dim text color `text-outline` (`#908f9e`) | 76 uses; 5.14-5.85:1 on the three surfaces used: **passes AA** |
| `text-outline-variant` used as text | 3 uses at 1.75-1.99:1 and alpha variants at 1.1:1: **fails**, probably decorative icons; do not use for text |
| Status | glyph + text + color: **readable without color** |
| Numbers | mono with tabular figures: columns align (tokens set `tabular-nums` globally) |
| Horizontal overflow | `overflow-x-auto` wrappers exist (5), but **no sticky header and no sticky first column** (`sticky` 0), and no minimum column widths, so identity is lost on scroll and columns compress |
| Selection | row checkboxes have no label or `aria` text |
| Plot (reward curve in drawer) | single SVG, no `title`/`desc`/`aria`, dashes `3 3` / `4 2` for reference lines; no text alternative |

**Verdict:** readable at the 2560 px capture. To stay readable at real widths: raise table body to **12 px** (`--type-code-md-*`), keep labels at 12 px minimum, make the header and Run ID column sticky, set minimum widths, give checkboxes `aria-label="Select run EXP-142"`, and add a text alternative for the plot (a small values table). The Stitch screen satisfies "readable" only partially; these fixes are **[PROPOSED]**.

## 6. Token references

| Element | Token (CSS variable) |
|---|---|
| Page, sidebar, content | `--color-bg`, `--color-surface` |
| Table block, drawer, cards | `--glass-bg`, `--glass-blur`, `--color-border`, `--radius-surface`, `--shadow-low` |
| Drawer overlay (narrow screens) | `--radius-overlay`, `--shadow-high` |
| Buttons, chips, tabs | `--radius-control`; press `--motion-press-scale` over `--motion-fast` |
| Inputs, selects | `--radius-surface`, `--color-border`, `--focus-ring`, `--color-accent` |
| Row hover / selected | `--color-hover`, `--color-accent-soft` |
| Status text and glyphs | `--color-ok` (Converged), `--color-info` (Running), `--color-warn` (Stalled), `--color-error` (Diverged/OOM/Aborted), `--color-muted` (Baseline) |
| Status dots | `--status-healthy`, `--status-warning`, `--status-critical`, `--status-telemetry` |
| Text, captions | `--color-text`, `--color-muted` |
| Headings | `--type-headline-lg-*`, `--type-headline-md-*` |
| Table cells, ids, hashes, seeds | `--type-code-md-*` (12 px), `--type-code-sm-*` only for tertiary info |
| Column headers, eyebrows | `--type-label-caps-*` |
| Spacing | `--space-sm` ... `--space-xl` |
| Auto-sync spinner / pulses | `--motion-live`, `--motion-ease` |

### Gaps and conflicts found

1. **Palette mismatch** with `tokens.json` (Stitch `#0f131b`/`#bdc2ff` vs `#10141C`/`#6974D9`); `tokens.json` stays the source.
2. **Shell mismatch** between this screen (variant B) and Overview/Topology/Training (variant A); see model-comparison.md section 6.
3. **Missing tokens:** dimmest readable text (`text_subtle`, dark `#908F9E` is 5.42:1 on `--color-surface`), sticky-header surface, layout sizes, disabled style. Not added in this task.
4. **Hosted icons:** Material Symbols font (Google Fonts).
5. **Shortcuts:** `⌘N`, `⌘K`, `⌘D` are macOS notation; `Ctrl+N` is the browser's new window, `Ctrl+D` bookmarks. Pick different bindings.
6. **Prototype logic:** `fault` and `error` preview buttons do nothing; "Auto-Sync (5s)" is a label, not a mechanism.
7. **A11y:** 51 buttons, 8 inputs, 1 table, 1 `aria-*`, 0 `role`, 0 `alt` in the HTML. Icon-only row actions need names; table needs a caption and `scope="col"`; the drawer needs `role="dialog"` (or complementary landmark), focus management and Esc.

## 7. Data honesty: what each element may show in NeuroRoute today

| Stitch element | Real source today | Status |
|---|---|---|
| Run list, counts (48), status chips, summary strip (87.5%, 3.61 ms, -54.3%) | none: no run history or repository | **blocked**; show the empty state |
| Run id, started time, duration | a future runs repository (DB choice undefined; `*.db`/`*.sqlite3` are git-ignored) | **blocked** |
| PRNG seed | `Scenario.seed` (training seed not defined yet) | **partial** |
| Scenario & topology column | `Scenario.name` + `Scenario.config_hash` (SHA-256 of canonical JSON) | **feasible**: show name + short hash |
| Short hash next to Run ID ("sha256:8a4f...") | should be the **config hash** or **checkpoint hash**, labelled which | **feasible**; do not mix them |
| P99 latency, loss %, deltas "vs OSPF" | evaluation output; no simulator or evaluation code | **blocked**; any figure must say **simulated** |
| Hardware label "DPDK + CUDA FP16" | this machine: CPU torch build, no DPDK/CUDA | **remove** |
| Pause / stop row actions | subprocess control; no job runner | **blocked**; SB3 has no pause (use stop and save) |
| Drawer: config manifest | the scenario JSON + a training config (schema not defined) | **partial** |
| Drawer: commit `git:7e8a01f` | `git rev-parse HEAD` recorded at run time | **feasible** |
| Drawer: replay command `python -m neuroroute.train --config /var/neuro/...` | no such module; `/var/neuro` is a Linux path | **remove**; a real replay command would use `.venv-rl` and repo-relative paths once a trainer CLI exists |
| Drawer: PID, stdout/stderr, Stream Live Logs | subprocess output once runs exist | **blocked** |
| Weights: Download .pt, ONNX export, "Ready for Deploy", "p=0.998" | SB3 saves `.zip` in git-ignored `checkpoints/`; no ONNX export planned; significance claims are not computed | **remove** ONNX/deploy/p-value; checkpoint + SHA-256 **feasible** later |
| Export Telemetry Dataset (Parquet 48 MB) | Parquet needs a library not installed | **remove**; CSV/JSON export is feasible |
| Batch Export, Compare Selected | export/compare of real run records | **blocked** |
| Flush Logs | deleting run logs | **destructive**: confirm and state exactly what is deleted |
| Auto-Sync (5s) | polling the backend; needs explicit timeout and error state | **feasible** later; show last-synced time and failure |
| User chip "Principal AI Net Eng" | `/me` returns uid, email, role only (no title) | **partial**; show email and role |

## 8. First buildable slice

Table shell with the **empty state**, search and filters disabled with reasons, correct column set (Run ID, Started, Seed, Scenario + config hash, Status), and the shared status vocabulary and glyphs as components (`StatusBadge`, `RunTable`, `RunDrawer`, `EmptyState`). Populate only when a runs repository and a trainer exist.

## 9. Open questions for the owner

1. Provide the original Experiments prompt if it should be stored.
2. Should Stitch be re-prompted for the empty, no-results, loading/error, confirm-flush and disabled states?
3. Shell variant: standardize on the 64 px top bar (A) or the 56 px bar with border (B)? See model-comparison.md section 6.
