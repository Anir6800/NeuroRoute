# Codebase audit

## 2026-10-21 (NR-D1-S01)
- Repository was empty: no source, README, architecture doc, tests or CI. Nothing to audit yet.
- Not a Git repository.
- Environment findings: see [setup/local-machine.md](setup/local-machine.md).

## 2026-10-21 (NR-D1-S02)
- Still no source code or tests. Added README, architecture doc (intended layering only) and full `.gitignore`.
- Risk: architecture.md is a plan, not a description of existing code. Torch-less 3.15 API means model inference needs a subprocess design.

## 2026-10-21 (NR-D1-S03)
- Folder tree and package markers only; still no application logic. Layout enforced by tests/test_layout.py (22 cases).
- Boundary rule (research must not import app) is documented but not yet machine-checked.

## 2026-10-21 (NR-D1-S04)
- First real code: settings (loopback-only host, port range) and /health. No route/service/repository layers exercised yet.
- Deprecation warning from Starlette TestClient + httpx; revisit when pinning dependencies.

## 2026-10-21 (NR-D1-S05)
- Frontend shell with typed, timeout-guarded health call and honest error state; tokens in styles/tokens.css. No dummy metrics.
- Risk: Stitch design not yet imported; only a handful of tokens defined by hand. TypeScript 7 / Vite 8 are very new, watch for tooling breakage.

## 2026-10-21 (NR-D1-S06)
- First research-layer code: scenario contract with hash. Import direction app -> research verified by grep, not yet enforced by a test.
- Risk: base_scenario values (capacities, demands) are illustrative inputs, not measurements; any future results must cite the config_hash that produced them.

## 2026-10-21 (NR-D1-S07)
- Auth is dev-only by construction (demo- project, loopback host enforced in Settings). Any move to a real project needs a separate, signature-verifying path.
- Risk: expiry is checked by our code because the SDK skips it in emulator mode; tests cover it. 401-vs-403 for wrong project relies on reading the unverified `aud`.
- Risk: npm audit highs in unused firestore transitive dep.

## 2026-10-21 (NR-D1-S08)
- Scripts are bash-only; PID handling uses /proc/<pid>/winpid + taskkill on Git Bash and plain kill elsewhere (Linux/macOS path untested).
- Test credentials in the README/script output are throwaway emulator values, not secrets.

## 2026-10-21 (NR-D2-S01)
- Tokens: JSON is the source, CSS is generated and drift-tested. Existing components now render in dark mode by default; not visually reviewed.
- Risk: brand-fill text contrast (4.12:1) is a design-level gap; Inter/JetBrains Mono not loaded so rendering uses fallbacks; derived light-mode text colors are our choice, not Stitch's.

## 2026-10-21 (NR-D2-S02)
- Docs only plus a repo-wide secret-scan test (patterns: Google API key, X-Goog-Api-Key with value, private key block, oauth token, sk- key). The scan is pattern-based, not exhaustive.
- Risk: the Stitch API key sits in plaintext in `~/.claude.json` (outside the repo); `.mcp.json` ignored as a safety net only.

## 2026-10-22 (NR-D2-S03)
- Spec only (no app code). Biggest risk: building from the Stitch screen would display fabricated metrics and non-existent hardware; spec section 5 maps each element to a real source or marks it blocked.
- Overview v1 can use only /health and /me today; scenarios, runs, models and metrics have no backend yet.

## 2026-10-22 (NR-D2-S04)
- Spec only. The test file imports `backend.research.simulation.models`, coupling the spec to schema v1.0: a schema change must update the spec (intended).
- Risk: three of the requested states exist only as proposals; if Stitch is later re-prompted, reconcile this file with the approved designs.

## 2026-10-22 (NR-D2-S05)
- Spec only. Training Lab cannot be built until environment, baselines, trainer CLI (`.venv-rl` subprocess) and a job API exist; the spec records that order.
- Risk: the Stitch design implies capabilities (4 algorithms, GNN, GPU, pause) that conflict with the project's MaskablePPO/CPU plan.

## 2026-10-22 (NR-D2-S06)
- Specs only. Two tests assert "scipy/pyarrow not installed": installing either will fail the test on purpose so the specs get re-read.
- Risk: the five Stitch screens disagree on shell, naming and sample numbers; building screens one by one from them would bake in the inconsistencies. The continuity rules in model-comparison.md section 6 (one shell component, one fixture set, one status vocabulary) should be adopted before UI work.

## 2026-10-22 (NR-D2-S07)
- First real UI code: shell + primitives, tested for behavior, tokens-only CSS, and no hosted assets. Pages are still the S05 ones (Overview=Home, Login, 404); five MVP routes arrive in S08.
- Risks: unseen visually; light theme values are partly derived; Firebase SDK ~370 kB bundle (auth only, tree-shaking not audited); mobile drawer has no focus trap; icon set is hand-drawn and minimal.

## 2026-10-22 (NR-D2-S08)
- Five screen skeletons + router. All content is empty-state text; no data layer exists, so `status` is a prop defaulting to `empty` (used by tests and future wiring), not real state.
- Risks: pages will need real data hooks (loading/error are only exercised in tests); shell not seen visually; `/login` chunk is lazy, so a slow network shows a blank content area briefly (no Suspense fallback beyond React Router's default).

## 2026-10-22 (UI-FIX-01)
- Navigation is now a bottom pill dock everywhere; the Stitch sidebar is gone from the implementation (docs say so). Pages still show empty states only.
- Risks: animations are judged from code and static shots only; the dock has 5 fixed slots (a sixth destination needs the width formula revisited); `scripts/ui-audit.mjs` assumes Chrome and the dev stack; the icon set is hand-drawn.
- Process lesson: a check that cannot fail is worse than none. The audit's overflow check hid itself behind mobile emulation until a mutation exposed it.

## 2026-10-22 (UI-FIX-02)
- Sign-in is a centered auth panel; centering math depends on the shell paddings and the dock height tokens (if either changes, `.auth` min-height must follow; the audit will flag drift).

## 2026-10-22 (NR-D3-S01)
- First model code. It is analytic and open-loop; its numbers are estimates, not measurements, and must be labelled simulated.
- Risks: delay is conservative near saturation (see the error table); byte-identical results depend on the numpy version (golden digest test will flag a numpy upgrade that changes Poisson draws: re-verify, then update the digest and docs together); fixed-point convergence is empirical, not proven (flag recorded per step); Python loops over steps and flows are fine for the MVP but would need vectorising for very large scenarios.

## 2026-10-22 (NR-D3-S02)
- Policies and a closed-loop runner exist; nothing in the API or UI calls them yet.
- Risks: the oracle and random-valid depend on a candidate cap (64 / 256) so very path-rich graphs are only partly searched; the oracle is greedy per flow; hysteresis defaults (5 s, 0.1) are untuned; policies assume one packet size and instant failure reaction (inherited from the simulator model).
- Script hazard (dev-neuro.sh stop): it kills whatever the PID file lists; after a reboot those PIDs may belong to unrelated processes. Mitigation idea: record and check the process start time or command line before killing. Not fixed in this task.

## 2026-10-22 (NR-D3-S03)
- Two Yen-based path enumerations now exist (baselines Topology.simple_paths and candidates.py); a test keeps them consistent on integer-weight graphs, but they should be merged when the environment lands.
- Risks: candidate ordering is by static weight (the best path under load may fall outside the K cheapest on route-rich graphs); the no-route penalty convention is unproven until a reward function uses it; property-test runtime is about 10 s per interpreter.

## 2026-10-22 (NR-D3-S04)
- Reward weights (1.0 / 1.0 / 0.05 / 1.0) are untuned placeholders; no sensitivity study exists. Do not draw conclusions from rewards before one is run.
- Only one flow is controlled; others use a fixed background policy. Observations use previous-step link metrics (no future leakage, tested).
- A masked action is substituted rather than rejected (required for gymnasium check_env); masked policies never trigger it.
- `.venv-rl` lacks fastapi/jwt, so run the API tests under `.venv` only.

## 2026-10-22 (NR-D3-S05)
- Schema 1.0 gained an optional `Flow.shape`. It is backward compatible (hash and traffic of scenarios without it are unchanged, tested), but the version string was not bumped; a v2 would be cleaner if the schema grows further.
- Poisson draws with a shape and a zero factor may consume no randomness, so downstream draws for that flow depend on the shape; each result is still deterministic.
- Only one topology: the suite tests load, failure and burst handling, not topology generalisation. The "shift" is a dynamics shift on the same graph (needed so one trained policy's observation shape applies).
- Fixture parameters (loads, alpha, periods) were chosen by me to give clear regimes; they are not calibrated to real traffic.

## 2026-10-22 (NR-D3-S06)
- Topologies are not yet used by the simulator or frontend; the API stores them only. Connection to scenarios (choose a stored topology for a run) is future work.
- Weak connectivity is accepted; a stored topology may have pairs with no directed route.
- No request-body size cap: a huge JSON body is parsed before the node/link limits apply. Fine on localhost, add a body-size limit before any wider use.
- The global 422 handler replaces FastAPI's default for every route (the shape `{loc, msg, type}` is kept; `input` and `ctx` are dropped).
- SQLite file default is `backend/.data/` (git-ignored); no migrations tool, schema is `CREATE TABLE IF NOT EXISTS`.
- Auth tokens are the forgeable emulator kind (existing, documented); ownership checks inherit that weakness.
