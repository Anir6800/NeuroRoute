# Model Comparison screen: local design spec (+ cross-screen continuity)

- **Stitch screen:** `projects/11953126075048924226/screens/22bbc11cef9747d5bd0e274daca47805`, title "NeuroRoute AI - Model Comparison", desktop capture 2560 x 5522 (H1 in the HTML: "Policy Model Comparison & Statistical Validation").
- **Captured:** 2026-10-22, from the screen's exported HTML (read-only via Stitch MCP `download_file`; sha256 prefix `d55c77c327c0`, 60,600 chars). The HTML is **not committed** (CDN dependencies, see [HANDOFF.md](../HANDOFF.md)). No screenshot was captured.
- **Prompt provenance:** the "exact" Model Comparison prompt named in the task was **not supplied**, and no screen was generated (that writes to the Stitch account). The task asked to generate this screen and Experiments *separately* and then compare continuity: both specs describe the **existing** screens ([experiments.md](experiments.md)); continuity is section 6 below.
- **Tokens:** [../../tokens.json](../../tokens.json) -> `frontend/src/styles/tokens.css`. CSS variables below are real names from that file.
- **Legend:** **[Stitch]** = drawn in the design. **[PROPOSED]** = not in Stitch; not approved design.

> **Data warning.** Every metric, confidence interval, p-value and path on this screen is Stitch sample data: "N=500,000 packets", "10 seeds", "KS D=0.612, p<10^-15", "Empirical p<0.001", `/var/neuro/benchmarks/...db`, DQN and ablation checkpoints. **No simulator, baseline, trained model, evaluation code or statistics code exists in this repository yet.** Nothing may be shown as a result, and no figure may be called a measurement; results from this project will be **simulated**.

## 1. Purpose

Compare routing policies (static shortest path, a congestion-aware heuristic, the learned policy) on the same scenario with confidence intervals and significance tests, and state the limits of the comparison.

## 2. Layout (desktop) [Stitch]

Shell **variant B** (56 px top bar with border, `-low` sidebar), as on Experiments.

| # | Region | Contents |
|---|---|---|
| 1 | State preview strip | Buttons including "High-Churn Stress Test", "Cold Start / No Baseline", "Confidence Interval Error State" (design aid, **none are wired** to behavior in the HTML script); "Local Eval DB" path chip; "SYNTHETIC RESEARCH SUITE" badge; seed chip |
| 2 | Page header | H1; "N=500,000 Pkts, 95% Bootstrap CI"; description; **Linear / Logarithmic** toggle; **Export CSV / JSON**; **Run Benchmark Suite** (`⌘B`) |
| 3 | Parameter strip | Traffic Ingestion Vector `<select>` (3 profiles), Fabric Underlay `<select>` (3), Ablation Overlay chip ("Flap Damping ON"), Manifest link |
| 4 | Candidate cards | Three cards A, B, C: name, artifact file, tag (STATIC BASELINE / RULE-BASED HEURISTIC / ACTIVE RL POLICY); six metric rows each (Mean Delay with CI, P95 Tail Latency, Packet Loss Ratio, Route Churn, Convergence Stability, Inference cost) with deltas versus baseline; C is the highlighted "Champion" |
| 5a | CDF plot | "Cumulative Distribution Function: Latency Under Burst Ingestion"; three series, 95% bootstrap bands, per-series show/hide buttons, tail-knee annotation, KS-test footnote |
| 5b | Packet drop vs load | line chart, load 2G-14G, 10G line-rate marker, annotations |
| 5c | Route churn timeline | flap rate over 180 s with three burst markers (T=30/90/150 s) |
| 6 | Checkpoint matrix | 10-column table x 6 models: candidate + checkpoint, Mean Delay (95% CI), P90, P95, P99, Packet Drop %, Flap Rate, Memory, Significance (p-value), Actions; "CURRENT BEST" tag; footer "Displaying 6 models", **Download Checkpoints (.pt)**, **Copy Table LaTeX** |
| 7 | Scientific rigor | Methodology and CI, Model limitations, deterministic CLI replay; links "Raw Parquet Dump", "Jupyter Notebook" |

Responsive [Stitch]: `sm`/`md`/`lg`/`xl` utilities (3 `overflow-x-auto` wrappers); **no tablet or mobile design**.

## 3. States

| State | Status | Notes |
|---|---|---|
| Default, populated | [Stitch] | |
| Series toggled off (per curve) | [Stitch], **functional** (hides the curve, dims the button) | all three can be hidden, leaving an empty plot with no message |
| Linear / Logarithmic scale | [Stitch] **cosmetic only** | the script only restyles the two buttons; it never rescales an axis |
| High-churn stress, cold start (no baseline), confidence-interval error | [Stitch] button names only | **no behavior and no designed screen** for any of them |
| **Empty (no runs / no baseline yet)** | **not designed** (despite the "Cold Start" label) | **[PROPOSED]** |
| **Single candidate selected, insufficient samples, CI undefined** | **not designed** | **[PROPOSED]** |
| **Loading / backend error / unauthenticated** | **not designed** | needed |
| **Disabled controls** | **not designed** (0 `disabled` attributes, no `disabled:` styles) | **[PROPOSED]**: Run Benchmark Suite, Export, Copy LaTeX, Download Checkpoints disabled with reasons when no data |
| **Comparison validity warning** (different scenarios or seeds across candidates) | **not designed** | **[PROPOSED]**: block or warn; a comparison is only valid on the same `config_hash` and seed set |

### [PROPOSED] Empty and insufficient-data states

Empty: "No comparable runs yet. Train a policy and run the baselines on the same scenario." Header actions disabled with reasons. Insufficient data: show the point estimate, replace the CI with "n too small (n=1)", suppress p-values, and never print a significance claim.

## 4. Readability audit (comparative plots and table)

Measured from the exported HTML and the Stitch palette:

| Check | Result |
|---|---|
| Text size | 121 of 186 text-size uses are 10-11 px (`code-sm` 77, `label-caps` 31); axis ticks and legends are among them |
| Dim text `text-on-surface-variant/60` | 14 uses at **4.35-4.63:1**: borderline, **fails AA** on the card surfaces (4.35 and 4.43) |
| `text-on-surface-variant/40` | 1 use at **2.69:1**: fails |
| Alpha `outline-variant` variants | 1.16-1.25:1: decorative only, not readable text |
| Series separation | three series differ by color (`#bdc2ff`, `#ffba50`, `#ffb4ab` / `#908f9e`) **and** by dash pattern (`6,4`, `2,2`, `4,4`, `3,3`), with direct annotations: **readable without color** (good) |
| Packet-drop plot scale | y axis is 0-3 %; the headline PPO value is **0.038 %**, about **1.3 %** of the axis height, so it is **visually indistinguishable from 0**; this is exactly the case the log scale is for, but the Logarithmic toggle does nothing |
| Plot accessibility | 3 SVGs, 0 `title`/`desc`/`aria`; no data-table alternative |
| Table | 10 columns at 12 px with mono numbers; **no sticky header or first column** (`sticky` 0), no minimum widths, horizontal scroll only; first column is two lines (model + artifact) |
| Table significance | p-values printed as `p < 10^-15` etc.; meaningless unless computed; no multiple-comparison note |

**Verdict:** readable at the 2560 px capture for the CDF and the churn plot; **not readable** for the packet-drop plot (headline value invisible) and borderline for dim labels. **[PROPOSED] fixes:** a real log-scale axis (or an inset/zoom) for rates near zero; mark the series with distinct marker shapes as well as dash; replace `/60` and `/40` text with `--color-muted` (10.12:1 on `--color-surface`); 12 px minimum for tick labels and legends; sticky header and first column with minimum column widths; right-align numeric columns; a "View as table" toggle plus `<title>`/`<desc>` for each plot; prevent hiding the last visible series.

## 5. Token references

| Element | Token (CSS variable) |
|---|---|
| Page, sidebar, content | `--color-bg`, `--color-surface` |
| Candidate cards, chart cards, matrix | `--glass-bg`, `--glass-blur`, `--color-border`, `--radius-surface`, `--shadow-low` |
| Buttons, segmented toggles, series toggles | `--radius-control`; press `--motion-press-scale` over `--motion-fast` |
| Inputs, selects | `--radius-surface`, `--color-border`, `--focus-ring`, `--color-accent` |
| Champion highlight, selected series | `--color-accent`, `--color-accent-soft`, `--color-accent-text` |
| Baseline / heuristic / learned series | three distinguishable roles: `--color-muted` (baseline, dashed), `--status-warning` (heuristic), `--color-accent` (learned) |
| Improvement / regression deltas | `--color-ok`, `--color-error` (always with sign and "vs baseline") |
| Table cells, ids, numbers | `--type-code-md-*` (12 px); tertiary info `--type-code-sm-*` |
| Tick labels, eyebrows | `--type-label-caps-*` (raise to 12 px where it carries data) |
| Headings, body | `--type-headline-lg-*`, `--type-headline-md-*`, `--type-body-md-*`, `--type-body-sm-*` |
| Spacing | `--space-sm` ... `--space-xl` |

Gaps: palette mismatch with `tokens.json`; no token for the dimmest readable text (`text_subtle`) or for chart series colors (propose `chart.series_1..3`); shell sizes; hosted Material Symbols; `⌘B`, `⌘D` shortcut notation; 4 `aria`-less SVG/table structures (1 `aria-*`, 0 `role`, 0 `alt` in the page). Not added in this task.

## 6. Continuity across the five exported screens

Compared programmatically from the HTML of Overview, Topology Studio, Training Lab, Experiments and Model Comparison (2026-10-22).

### Shell and chrome

| Aspect | Overview, Topology, Training (variant A) | Experiments, Comparison (variant B) |
|---|---|---|
| Top bar height | 64 px (`h-16`) | **56 px** (`h-14`) with a bottom border |
| Sidebar fill / layer | `-lowest` surface, z-40 | **`-low` surface**, z-50 |
| Nav icons | Routing Topology `hub`, Policy Models `model_training` | **`schema`**, **`psychology`** |
| User role label | "Lead Researcher" | **"Principal AI Net Eng"** |
| Sample-data badge | "Sample Data" | **"SAMPLE DATA"** |
| Breadcrumb | reads "Overview" on **all three**, wrong on Topology and Training | reads "Experiments & Runs" on **both**, wrong on Comparison |

### Shared and consistent

Palette family and the two typefaces (Inter, JetBrains Mono); sidebar width 248 px; status color semantics; the 8 px rhythm utilities; seed `4208-BURST`; experiment id style (`#EXP-142`); checkpoint name `ppo_routing_ep400.pt`; "Local: Ready (v0.8.4-dev)".

### Data and naming contradictions (even for sample data, one fixture must feed every screen)

| Item | Values seen |
|---|---|
| Learned-policy P99 latency | **3.42 ms** (Overview, Training, Experiments) vs **5.88 ms** (Comparison table) |
| Baseline (OSPF/Dijkstra) P99 | **8.14 ms** (Overview, Training, Experiments) vs **15.92 ms** (Comparison) |
| Learned-policy packet loss | **0.042 %** vs **0.038 %** |
| Checkpoint size | **14.8 MB** (Overview, Training, Experiments) vs **14.2 MB** (Comparison) |
| Checkpoint hash `8a4f9c...` | on four screens, **absent** on Comparison |
| Hardware | "Apple M3 Max / MPS" (Overview, Training) vs "DPDK + CUDA FP16" (Experiments) |
| Policy name | `PPO-ActorCritic-v4.1`, `PPO-Actor-Critic-v4.1`, `NeuroRoute PPO v4.1`, `PPO RL v4.1` |
| Topology name | `64-SpineLeaf-v2`, `64-Spine-Leaf (v2)`, `64-Node Datacenter Spine-Leaf (v2.4)`, `64-Spine-Leaf Fabric (v2, Radix 32)` |
| Failure vocabulary | Experiments: Diverged / OOM / Aborted / Stalled; Training: preflight failure only; Comparison: none |

### [PROPOSED] Continuity rules

1. **One shell component.** Pick variant A (64 px) or B (56 px with border) once; recommendation: A, because three of five screens and the earlier specs use it. One nav icon set, one user chip (`/me` email and role), one badge style ("Sample data"), breadcrumbs generated from the route.
2. **One name registry and one set of sample fixtures** (clearly labelled "Sample data"), consumed by every screen, so the same run shows the same numbers everywhere. Real data replaces the fixtures screen by screen.
3. **One status vocabulary and glyph set** (see experiments.md section 4), used by Training Lab, Experiments and Comparison.
4. **A comparison is valid only on one `config_hash` and one seed set;** the UI shows both and blocks or warns otherwise.
5. **Results are labelled simulated;** nothing is called measured until Mininet validation exists (it is not installed).

## 7. Data honesty: what each element may show in NeuroRoute today

| Stitch element | Real source today | Status |
|---|---|---|
| Static Dijkstra baseline | a weight-based shortest path on `Scenario.links[].weight` is deterministic and computable with NetworkX (installed) | **feasible**; not implemented yet |
| Congestion-aware ECMP heuristic | needs a simulator for queue state | **blocked** |
| Learned policy (PPO v4.1), DQN, ablations, checkpoints | no model trained; MaskablePPO planned, runs in `.venv-rl` | **blocked**; remove DQN and fabricated ablations |
| Mean / P95 / P99 delay, packet loss, flap rate, memory, inference cost | simulator output; none exists | **blocked** |
| 95% bootstrap CI, KS test, p-values | computable with numpy/scipy-class code once samples exist (scipy not installed); the p-values shown are made up | **blocked**; compute honestly or omit; apply a multiple-comparison correction if showing many |
| "N=500,000 packets, 10 seeds" | claims about a run that does not exist | **remove**; show the actual n and seeds |
| CDF, drop-vs-load, churn plots | built from per-packet samples once a simulator exists | **blocked** |
| Traffic and fabric selectors | `Scenario.traffic`, scenarios in `experiments/configs/` | **partial** (needs a scenario API) |
| Ablation overlay (flap damping) | no such parameter in the schema | **remove** |
| Config identity | `Scenario.config_hash`, `Scenario.seed` | **available**; show on the page |
| Export CSV/JSON | computable from real results | **feasible** once results exist |
| Copy LaTeX table | string formatting from real results | **feasible** later |
| Download checkpoints | SB3 `.zip` in git-ignored `checkpoints/` | **feasible** later |
| "Raw Parquet Dump", "Jupyter Notebook", `python -m neuroroute.benchmark`, `/var/neuro/...` | none exists; Linux path | **remove** |
| "Methodology" and "Limitations" prose | must describe what was actually run | **write after** the first real evaluation |

## 8. First buildable slice

The comparison page needs data that does not exist. Honest slice: page shell, the empty state, the comparison-validity rule, and the **baseline-only view** once a shortest-path router and a simulator exist. Components: `CandidateCard`, `CdfPlot`, `RateVsLoadPlot` (with log axis), `ComparisonTable` (sticky header/first column), `ValidityBanner`, `EmptyState`.

## 9. Open questions for the owner

1. Provide the original Model Comparison (and Experiments) prompts if they should be stored.
2. Should Stitch be re-prompted to unify the shell, drop fabricated statistics, and draw the empty, insufficient-data and disabled states?
3. Shell variant A or B as the standard?
