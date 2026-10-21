# Local machine audit (NR-D1-S01)

Audited 2026-10-21 on the developer laptop. Values are observed command output, not assumptions.

| Item | Observed | Required | Status |
|---|---|---|---|
| OS | Windows 11 Home Single Language 10.0.26300, 64-bit | any | OK |
| CPU | Intel Core i7-13650HX | — | OK |
| RAM | 23.7 GB | ≥ 8 GB | OK |
| Python 3.11 | **Not installed.** Installed: 3.15.0 (default `python`), 3.13, uv-managed 3.14.3 | 3.11 | **MISSING** |
| Node.js | v24.12.0 (`process.release.lts` = "Krypton", i.e. LTS) | LTS | OK |
| npm | 11.12.1 | — | OK |
| Git | 2.56.0.windows.2 | any | OK |
| VS Code | 1.142.0 | — | OK |
| Docker | CLI 29.7.2 present; **daemon not running** (Docker Desktop engine pipe missing) | optional | PARTIAL |
| uv | 0.10.7 (can fetch `cpython-3.11.14`) | optional | OK |
| WSL2 Ubuntu | Ubuntu 24.04.4 LTS, kernel 6.6.87.2-microsoft-standard-WSL2, system Python 3.12.3 (state: Stopped when audited) | for Mininet | AVAILABLE |
| Mininet / Open vSwitch in Ubuntu | `mn` and `ovs-vsctl` not found; `sudo` needs a password | optional validation | **NOT INSTALLED** |

## Decision (user, 2026-10-21): use newest Python and newest dependency versions

Python 3.11 is no longer the target; `.venv` was created with Python 3.15.0 and unpinned latest packages were installed.

Installed in `.venv` (observed `pip list`): networkx 3.7, gymnasium 1.4.0, numpy 2.5.4, fastapi 0.157.0, uvicorn 0.54.0, pytest 9.1.1, ruff 0.17.1.

**BLOCKED on 3.15: PyTorch** (`pip` finds no `torch` distribution), so stable-baselines3 / sb3-contrib (MaskablePPO) are not installed. `pip install --dry-run torch sb3-contrib` succeeds on Python 3.13, so 3.13 is the newest interpreter here that can train. Options: (a) keep 3.15 for everything except training and make a second venv on 3.13 for RL, or (b) use 3.13 for all. Not decided; no installs done for this. Nothing in `.venv` was imported or run beyond `pip`, so "works" is not yet verified there.

**Resolved (user chose two venvs):** `.venv-rl` on Python 3.13.7 holds the RL stack: torch 2.14.1 (CPU build), stable-baselines3 2.9.0, sb3-contrib 2.9.0, gymnasium 1.4.0, networkx 3.7, numpy 2.5.4, pytest 9.1.1, ruff 0.17.1. Verified: `from sb3_contrib import MaskablePPO; import torch` succeeds. Training has not been run. Rule: API/simulation code must stay importable on both interpreters, since the trained model is loaded by the 3.15 API only if torch is available there (it is not), so model inference should be a separate step run under `.venv-rl`.

## Findings

1. **Python 3.11 is missing; superseded by the decision above.** The default `python` is 3.15.0, and PyTorch has no 3.15 distribution (verified by `pip install --dry-run`).
2. **Mininet is optional and currently unavailable.** Ubuntu 24.04 on WSL2 exists, so it is the likely host. Installing needs `sudo apt install mininet openvswitch-switch`; WSL2 kernel support for OVS/network namespaces is **untested**. Until verified, treat Mininet validation as BLOCKED and rely on the NetworkX/Gymnasium simulation. Never present simulated numbers as Mininet measurements.
3. **Docker is not needed for the MVP** and its daemon is down. Do not add it as a dependency.
4. Node 24 LTS is used; the Vite/React toolchain was not installed or built here.

## Reproduce

```powershell
python --version; py -0p; node --version; npm --version; git --version
code --version; docker --version; uv --version; wsl --list --verbose
wsl -d Ubuntu -- bash -c 'cat /etc/os-release; which mn ovs-vsctl'
```
