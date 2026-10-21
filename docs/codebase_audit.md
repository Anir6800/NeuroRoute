# Codebase audit

## 2026-10-21 (NR-D1-S01)
- Repository was empty: no source, README, architecture doc, tests or CI. Nothing to audit yet.
- Not a Git repository.
- Environment findings: see [setup/local-machine.md](setup/local-machine.md).

## 2026-10-21 (NR-D1-S02)
- Still no source code or tests. Added README, architecture doc (intended layering only) and full `.gitignore`.
- Risk: architecture.md is a plan, not a description of existing code. Torch-less 3.15 API means model inference needs a subprocess design.
