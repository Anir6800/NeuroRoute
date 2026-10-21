# Training Lab screen: local design spec

- **Stitch screen:** `projects/11953126075048924226/screens/5ec94870acca4d5b88ce996827dd5f04`, title "NeuroRoute AI - Training Lab", desktop capture 2560 x 3594.
- **Captured:** 2026-10-22, from the screen's exported HTML (read-only via Stitch MCP `download_file`; sha256 prefix `5c856c53c226`, 50,112 chars). The HTML is **not committed** (CDN dependencies, see [HANDOFF.md](../HANDOFF.md)). No screenshot was captured.
- **Prompt provenance:** the "exact Training Lab screen prompt" named in the task was **not supplied**, and no new screen was generated (that writes to the Stitch account). This spec describes the **existing** screen.
- **Tokens:** [../../tokens.json](../../tokens.json) -> `frontend/src/styles/tokens.css`. CSS variables below are real names from that file.
- **Legend:** **[Stitch]** = drawn in the design. **[PROPOSED]** = not in Stitch; written here because the task requires it. Proposals are not approved design.

> **Data warning.** Every number, name and claim on this screen is Stitch sample data and much of it describes things that do not exist here: PyTorch 2.3 + MPS, DPDK, an "air-gapped" cluster, four RL algorithms, a GNN extractor, a replay buffer, a 64-node mesh, a run "at episode 420". Nothing may be shown as live. **No trainer, environment or training API exists in this repository yet.**

## 1. Purpose

Configure a reinforcement-learning run (algorithm, topology, hyperparameters, reward weights, traffic), check it before launch, start it, watch its progress and convergence, stop it, and find the resulting checkpoints.

## 2. Layout (desktop) [Stitch]

Same shell as Overview/Topology: fixed sidebar 248 px, fixed top bar **64 px** (`--glass-bg`, `blur(var(--glass-blur))`), content on `--color-surface`. Cards are `--radius-surface` on `--color-surface`-level fills with `--shadow-low`.

| # | Region | Contents |
|---|---|---|
| 1 | Page header | H1 "Training Lab & Policy Optimization"; badges ("RL Engine: PyTorch 2.3 + MPS Local", "Air-Gapped Node"); description. A four-button **state preview** switcher (In-Flight, Pre-Run Config Ready, Validation Error, Cold Start / Empty) is a design aid, **not** a product feature |
| 2 | Session strip | "Session: ... Profile: ..." plus **Reset Baseline**, **Dry-Run Preflight**, **Start Training Run** (`⌘Enter`) |
| 3 | State banner | Hidden while running; otherwise a card with a 4 px left border and an action button (see states) |
| 4a | Config column | `lg:` **7 of 12 columns**; four numbered cards (see below) |
| 4b | Run column | `lg:` **5 of 12 columns**: status panel, Convergence Telemetry, Local Hardware Daemon, Latest Checkpoints |

Config cards [Stitch]:

| Card | Controls (range / default as drawn) |
|---|---|
| 01 Model Architecture & Policy Core | RL Agent Algorithm `<select>` (Multi-Agent PPO, SAC-v2, DQN-PER, MADDPG), model-size note; Target Topology Profile `<select>` (4 profiles); Backbone Spatial Feature Extractor radios (GATv2 / Multi-Head MLP) |
| 02 Hyperparameters & Training Budget | PRNG seed text + dice button; Learning rate text (3e-4, linear decay, warmup 2,000, AdamW 1e-4); Episode target limit slider **100-5000** (default 1,000); Minibatch size (128); Replay ring buffer (64,000 slots) |
| 03 Multi-Objective Reward | Formula `R_t = -[(w_l dRTT) + (w_q Q_depth) + (w_d PktDrop) + (w_f dHop)]`; four sliders **0-3**: queue 0.85, loss 1.40, RTT 0.60, flap 0.25 |
| 04 Traffic Generator & Constraint Ingestion | Traffic profile card (Poisson burst, lambda 0.82, 10 Gbps, 400 ms micro-bursts), divert-hops limit, loopless-ECMP guard flag (read-only "ENFORCED") |

Run column [Stitch]: status title with pulse dot, "Episode N / 1000 (x%)", progress bar, Elapsed and Est. Remaining, **Pause Checkpoint** and **Abort Run**; **Convergence Telemetry** (loss chart, reward chart, four tiles: P99 latency, packet drop, buffer occupancy, gradient norm); hardware card (GPU load, temperature, VRAM, ring buffers, shm IPC); checkpoint list with file, SHA-256, **Inspect**, **Export**.

Responsive [Stitch]: `sm`/`md`/`lg`/`xl` grid utilities only; **no tablet or mobile design**.

## 3. States

Status presentation as scripted in the design (`switchState`):

| State | Stitch name | Status title / color | Pulse dot | Progress bar | Banner | Charts and tiles |
|---|---|---|---|---|---|---|
| **Running** | In-Flight | `TRAINING IN-PROGRESS`, secondary (teal) | pulsing | primary fill, e.g. 42% | hidden | full opacity |
| **Idle, ready** | Pre-Run Config Ready | `PRE-RUN READY`, primary | static primary | 0% | "Configuration Validated & Ready for Launch" + **Launch Now**, primary left border | dimmed (`opacity-40`) |
| **Idle, empty** | Cold Start / Empty | `COLD START / IDLE`, outline (grey) | static grey | 0% | "No Active Weights Loaded" + **Load Default Config**, grey left border | dimmed |
| **Failed (preflight)** | Validation Error | `VALIDATION FAILED`, error | static error | 0%, error fill, "Halted on Preflight Step" | "Preflight Check Failed: Incompatible Tensor Dimensions" + detail + **Auto-Fix Dimension**, error left border | dimmed |

What the design does **not** cover:

| Missing state | Notes |
|---|---|
| **Failed mid-run** (process crash, loss diverged / NaN, out of memory, timeout, checkpoint write error) | Only a *pre-launch* validation failure is drawn. The **Experiments** screen already names run failures (`Diverged`, `OOM / Aborted`, `Stalled`), so Training Lab must use the same vocabulary |
| Aborted by user, Completed, Paused/Stopping, Starting | none drawn |
| Disabled controls | **Start, Dry-Run, Reset, Pause and Abort look identical in all four states.** No `disabled` attribute, `cursor-not-allowed` or `disabled:` style exists. Pause/Abort stay visible and enabled even when nothing is running, and Start stays enabled while running. The only inactive treatment is dimming the charts and tiles |
| Loading, backend unreachable, unauthenticated, lost connection to a running job | none drawn |
| Confirmation for destructive actions (Abort, Reset) | none drawn |

### [PROPOSED] Control availability by state

| Control | Idle, empty | Idle, ready | Validating | Running | Stopping | Failed | Completed / Aborted |
|---|---|---|---|---|---|---|---|
| Config fields | enabled | enabled | disabled | **disabled** (read-only) | disabled | enabled | enabled |
| Reset Baseline | enabled | enabled | disabled | disabled | disabled | enabled | enabled |
| Dry-Run Preflight | enabled | enabled | disabled (shows busy) | disabled | disabled | enabled | enabled |
| Start Training Run | disabled, reason "Load a config" | **enabled** | disabled | disabled | disabled | disabled until errors fixed | enabled ("Start new run") |
| Stop & save (was Pause) | hidden | hidden | hidden | **enabled** | disabled | hidden | hidden |
| Abort Run | hidden | hidden | hidden | **enabled, with confirm** | disabled | hidden | hidden |
| View logs | disabled | disabled | enabled | enabled | enabled | enabled | enabled |

Disabled controls use the real `disabled` / `aria-disabled="true"`, `opacity: 0.5`, `cursor: not-allowed`, no hover/press effect, and show **why** in visible text (not hover-only), same rule as the Topology Studio spec.

### [PROPOSED] Failed-run state

Banner in `--color-error`: a reason code from the shared set (`Diverged`, `OOM`, `Timeout`, `Crashed`, `Checkpoint write failed`, `Env unavailable`), the time and step it failed at, the **last lines of the run log**, and actions: **View logs**, **Retry from last checkpoint** (only if one exists), **Edit config**. The run appears in Experiments with the same status. Status text uses `--color-error`; the failure is announced via `role="alert"`.

### [PROPOSED] Status color mapping

Running `--color-info` (+ pulse), idle `--color-muted`, ready `--color-accent-text`, validating `--color-warn`, failed `--color-error`, completed `--color-ok`. Stitch colors "running" with its own teal (`#64d9d0`), which is not a token here.

## 4. Token references

| Element | Token (CSS variable) |
|---|---|
| Page, sidebar, content | `--color-bg`, `--color-surface` |
| Config cards, run cards, banner | `--glass-bg`, `--glass-blur`, `--color-border`, `--radius-surface`, `--shadow-low` |
| Buttons, chips, segmented controls | `--radius-control`; press `--motion-press-scale` over `--motion-fast` |
| Inputs, selects, sliders | `--radius-surface`, `--color-border`, `--focus-ring`, `--color-accent` |
| Progress bar fill / track | `--color-accent` / `--color-accent-soft` |
| Status text and dots | `--color-info`, `--color-ok`, `--color-warn`, `--color-error`, `--color-muted`, `--status-telemetry`, `--status-critical` |
| Text, captions | `--color-text`, `--color-muted` |
| Headings | `--type-headline-lg-*`, `--type-headline-md-*`, `--type-headline-sm-*` |
| Body | `--type-body-md-*`, `--type-body-sm-*` |
| Numbers, hashes, step counts, formula | `--type-code-md-*`, `--type-code-sm-*` |
| Section numbers, eyebrow labels | `--type-label-caps-*` |
| Spacing | `--space-md` ... `--space-xl` |
| Live updates | `--motion-live`, `--motion-ease` |

### Gaps and conflicts found

1. **Palette mismatch.** The HTML uses Stitch's YAML palette (`#0f131b`, `#bdc2ff`, `#64d9d0`), not `tokens.json`. `tokens.json` stays the source.
2. **No token for the dimmest readable text.** The design uses `text-outline` (`#908f9e`) 52 times. On the approved surfaces it is 5.42:1 (surface) and 5.80:1 (canvas), which passes AA, but `--color-muted` (10.12:1) is much lighter, so there is no token for it. Proposal: `color.text_subtle` (dark `#908F9E`; a light value needs a choice, e.g. `#6B7088` is 4.60:1 on the light canvas). Not added in this task.
3. **Sizes.** 77 of 187 text-size uses are 10-11 px (`label-caps`, `code-sm`); 16 are 10 px. Form labels and helper text should be at least 12 px.
4. **Motion.** `animate-pulse` on the status dot needs its own `prefers-reduced-motion` guard.
5. **Breadcrumb bug.** The top bar reads "Workspaces / NeuroRoute / Overview" on this page.
6. **Hosted icons.** Material Symbols font (Google Fonts) is a hosted asset.
7. **Prototype behavior.** "Auto-Fix Dimension" only flips the screen to the pre-run state and claims a fix happened; ship nothing like it.

## 5. Accessibility requirements (the HTML has 0 `aria-*` and 0 `role` attributes)

- Progress bar: `role="progressbar"` with `aria-valuenow/min/max` and text ("Episode 420 of 1000").
- Status changes announced in a live region; banner `role="status"` (info) or `role="alert"` (failure).
- Sliders have labels, `aria-valuetext` (e.g. "queue weight 0.85") and a typed numeric input alternative.
- The seed dice button and icon buttons get accessible names; radio options grouped with `role="radiogroup"`.
- `⌘Enter` is macOS-only; use `Ctrl+Enter` or none, and keep it from firing while a field has focus unintentionally.
- Abort and Reset need a confirmation dialog with focus management.
- Charts need a text/table alternative (see Experiments and Model Comparison specs).

## 6. Data honesty: what each element may show in NeuroRoute today

| Stitch element | Real source today | Status |
|---|---|---|
| Algorithm select (PPO, SAC, DQN-PER, MADDPG) | the project plans **MaskablePPO** (sb3-contrib) only | **only MaskablePPO is real**; other options removed |
| GNN (GATv2) vs MLP extractor | none planned; SB3 defaults to an MLP policy | **remove** (blocked unless a custom extractor is built) |
| Target Topology Profile | scenario configs in `experiments/configs/` (`base_scenario.json`: 4-node diamond); `Scenario.config_hash` | schema exists; **no API serves scenarios yet** |
| PRNG seed | `Scenario.seed` exists; a training seed is not defined yet | **partial**; "Verified Deterministic" must not appear unless a determinism test exists |
| Learning rate, minibatch size, episode target | MaskablePPO has `learning_rate`, `batch_size`, `n_steps`, `total_timesteps` (steps, not episodes) | **needs a training-config schema (not defined)** |
| Warmup steps, AdamW weight decay, replay ring buffer, pinned shared RAM, POSIX shm, DPDK | not applicable (PPO is on-policy: no replay buffer; Adam optimizer) | **remove** |
| Reward weights (queue, loss, RTT, flap) | reward is environment code that does not exist | **blocked** until the environment exists |
| Traffic profile (Poisson burst, lambda, 10 Gbps) | `Scenario.traffic` (`cbr`/`poisson`, packet size) + `flows[].demand_mbps`; no burst or lambda fields | **partial** |
| Divert hops, loopless-ECMP guard | none | **remove** |
| Status panel, progress, ETA, elapsed | would come from a training subprocess; none exists | **blocked** |
| Loss / reward charts, KPI tiles, gradient norm | SB3 logger output once a trainer exists | **blocked**; show "no run yet" |
| Hardware card (MPS GPU, temperature, VRAM) | this laptop: Windows, Core i7-13650HX, torch 2.14.1 **CPU** build in `.venv-rl` | **remove** GPU/MPS/DPDK; CPU/RAM only if a system endpoint is built |
| Dry-Run Preflight | could genuinely check: scenario validates, `.venv-rl` has torch/sb3-contrib, output dir writable | **feasible**, honest |
| Start / Stop / Abort | spawn and stop a subprocess under `.venv-rl` | **blocked** (no job runner) |
| "Pause Checkpoint" | SB3 has no pause | rename **Stop & save**; **blocked** |
| Checkpoint list, SHA-256 | SB3 saves `.zip` (the design shows `.pt`); SHA-256 is computable; `checkpoints/` and `*.zip` are git-ignored | **feasible** once a trainer exists |
| "Air-Gapped", "Zero Cloud Egress" | unverifiable | **remove**; verifiable claim: services bound to 127.0.0.1 |

## 7. Architecture constraints (from this repo)

The API runs in `.venv` (Python 3.15) and **cannot import torch**; training and inference belong to `.venv-rl` (Python 3.13). A training run is therefore a **subprocess** started by the API, reporting progress through a file or pipe, with explicit timeouts and typed error states. One run at a time is reasonable on one laptop. All processes stay on `127.0.0.1`. Results must be labelled **simulated**.

## 8. First buildable slice

Nothing here can run until the environment and trainer exist. Build order: Gymnasium environment -> baselines (shortest path) -> MaskablePPO trainer CLI under `.venv-rl` -> job API -> this screen. UI-first, only honest pieces: the empty state, a read-only config preview from `base_scenario.json`, a Dry-Run Preflight with real checks, and **Start disabled with a stated reason**.

## 9. Open questions for the owner

1. Provide the original Training Lab prompt if it should be stored.
2. Should Stitch be re-prompted for the mid-run failed, completed, aborted and disabled-control states, and to drop SAC/DQN/MADDPG, GNN, DPDK and GPU content?
3. Pause: is "Stop & save checkpoint" acceptable instead?
