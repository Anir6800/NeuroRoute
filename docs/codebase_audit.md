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
