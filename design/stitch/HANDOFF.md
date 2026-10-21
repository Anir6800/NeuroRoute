# Stitch -> React handoff (manual workflow, always available)

This works with only a browser and your Stitch account. No MCP, no API key. (The optional MCP route is in [docs/stitch-integration.md](../../docs/stitch-integration.md).)

Source project: **"AI Network Design System"** (`projects/11953126075048924226`). Approved tokens: [../tokens.json](../tokens.json). Verbatim brief: [MASTER_PROMPT.md](MASTER_PROMPT.md).

## Screens (as of 2026-10-21)

| Title | Stitch screen id |
|---|---|
| NeuroRoute AI Lab Prototype | `b56f019e88d645bfa2fcf2553388deab` |
| NeuroRoute AI - Research Workspace Overview | `2439df6b3eba4b949daa74db7b322d54` |
| NeuroRoute AI - Topology Studio | `bee8e9555edb4fbda649a48a5ef3c5d2` |
| NeuroRoute AI - Route Explorer & Scenario Playback | `33a83716633d4d368b06a1c05c8728b8` |
| NeuroRoute AI - Training Lab | `5ec94870acca4d5b88ce996827dd5f04` |
| NeuroRoute AI - Model Comparison | `22bbc11cef9747d5bd0e274daca47805` |
| NeuroRoute AI - Experiments & Runs | `3f7210fb06d244cbb7aa15f7d248696f` |
| NeuroRoute AI - Research Reports & Publication Canvas | `c811b425eefd4beab24e35ebd16dd839` |
| NeuroRoute AI - Settings & Local Environment | `58e1837246e0450d8f78d6a4779bc5b9` |
| Design System & Component DNA | `ab0d4c46467d4a588395450ffc512753` |

## Steps

1. **Open** the project in Stitch (web) and select a screen.
2. **Capture two things** per screen, using whatever export/copy options Stitch currently offers (exact menu names are not verified here and may change):
   - a **screenshot** (Stitch's export, or a browser/OS screenshot at 1x), saved as `design/stitch/screens/<slug>/screenshot.png`;
   - optionally the screen's **HTML**, saved as `design/stitch/screens/<slug>/source.html` for local reference only.
3. **Do not commit or ship the HTML.** Stitch HTML loads the Tailwind CDN, Google Fonts, Material Symbols and hosted images; `.gitignore` excludes `design/stitch/screens/**/*.html`. Screenshots and notes are committed.
4. **Write `design/stitch/screens/<slug>/notes.md`** from the template below.
5. **Tokens first.** If the screen needs a color, size, radius or motion value that is not in `design/tokens.json`, add it there (mark it `derived` if it is not in Stitch), then run `.venv/Scripts/python scripts/build_tokens.py`. Never hard-code values in components.
6. **Rebuild, don't paste.** Create small reusable components under `frontend/src/components/` that consume the CSS variables. Never copy a full screen's markup into React.
7. **Real data only.** Every number on a screen must come from a real source (backend endpoint or recorded run). Stitch's sample metrics are placeholders; do not display them as live (project rule 7).
8. **Verify:** `npm run typecheck && npm test && npm run build` in `frontend/`, `python -m pytest -q tests` at the root, then look at the page via `scripts/dev-neuro.sh`.

## `notes.md` template

```markdown
# <Screen title>
- Stitch screen: projects/<project>/screens/<id>   Exported: <YYYY-MM-DD>
- Components identified: <list, each -> frontend/src/components/<Name>.tsx>
- Tokens used / added: <names; mark any new ones>
- Data needed: <endpoint or recorded-run source for every number shown>
- Deviations from Stitch (and why): <contrast fixes, removed placeholder data, no CDN assets>
- Status: not started | in progress | done (commit <hash>)
```

## Checklist before any screen-derived code is merged

- [ ] No `cdn.tailwindcss.com`, `fonts.googleapis.com`, `googleusercontent.com` or other hosted URL in `frontend/`.
- [ ] No hard-coded colors/sizes; only `var(--...)` from `tokens.css`.
- [ ] Text contrast >= 4.5:1 (or documented large-text exception); `tests/test_tokens.py` passes.
- [ ] No placeholder metrics presented as live; empty/error states exist.
- [ ] No keys, tokens or signed URLs in any committed file.
