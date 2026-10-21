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
