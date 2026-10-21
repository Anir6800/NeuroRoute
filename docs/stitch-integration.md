# Stitch integration (optional MCP + manual fallback)

Google Stitch is the design tool used to explore the NeuroRoute UI. **Nothing in the build, tests or runtime depends on Stitch.** The app is built from `design/tokens.json` and hand-written React components; Stitch output is reference material only.

There are two ways to get designs out of Stitch:

| Path | When | Needs |
|---|---|---|
| **Manual export** (always available) | Always. Default. | A browser and your Stitch account. See [design/stitch/HANDOFF.md](../design/stitch/HANDOFF.md). |
| **Stitch MCP** (optional) | If your editor supports remote MCP servers and you have an API key. | API key, network. |

If MCP is unavailable, broken, rate-limited or you would rather not hold a key, use the manual path; the result is identical.

## Stitch MCP (optional)

Shape of the server entry verified on the dev laptop (2026-10-21, value redacted): a **remote HTTP** MCP server at `https://stitch.googleapis.com/mcp` authenticated with an `X-Goog-Api-Key` header. It is stored in the user-level Claude Code config (`~/.claude.json`), outside this repo.

Add it in Claude Code (command form per Claude Code's `claude mcp add` documentation; not re-run here because the server was already configured):

```bash
export STITCH_API_KEY=...            # your key; never write it into a file in this repo
claude mcp add --transport http --scope user stitch https://stitch.googleapis.com/mcp \
  --header "X-Goog-Api-Key: $STITCH_API_KEY"
```

Use `--scope user` (or `local`). **Do not use `--scope project`**: that writes `.mcp.json` into the repo with the key inside. `.mcp.json` is git-ignored here as a safety net, but do not rely on it.

Other MCP-capable editors (the dev laptop also has Antigravity IDE) should accept the same three facts: `type: http`, the URL above, and the header. Their exact menus were **not** verified; check that editor's MCP docs.

### Tools seen on the dev laptop

Read-only (safe to call, verified working 2026-10-21): `list_projects`, `get_project`, `list_screens`, `get_screen`, `download_file`, `list_design_systems` (pass a `projectId`; calling it with no argument returned "invalid argument").

Writes to your Stitch account (confirm before using): `create_project`, `delete_project`, `generate_screen_from_text`, `edit_screens`, `generate_variants`, and the design-system create/update/apply tools. They create or change cloud data and may consume quota. Agents working on this repo should not call them unless you ask.

Verified behavior and quirks:

- `list_screens` returns each screen's `title`, `width`, `height`, `deviceType`, `htmlCode.name` and `screenshot.name` (resource names ending in `/fileEntries/html` and `/fileEntries/screenshot`). A screen can have no screenshot (`{}`).
- `download_file` with such a name returns `{html: string}` (about 58 KB for one screen) or image bytes. Do not fetch the raw `downloadUrl` values: they need credentials.
- Outputs are large (`list_projects` was 84 KB). Save to a file and probe it with `jq`/Python instead of reading it into a chat.
- **Exported HTML is not self-contained.** The sample screen loaded the Tailwind CDN (`cdn.tailwindcss.com`), Google Fonts, Material Symbols and a `googleusercontent.com` image. Under the project's no-hosted-assets rule it must never be copied into `frontend/` or served; extract tokens and rebuild components instead.

## Key safety

- The key is a credential. Keep it only in your user-level MCP config or an environment variable. Never commit it, paste it into docs/issues/chat, or put it in `.env.example`.
- `~/.claude.json` stores it in plaintext. Treat that file as secret; redact `headers` when sharing it.
- Prefer a key restricted to the Stitch API in Google Cloud console (API restriction), and rotate/revoke it there if it leaks or appears in a diff. (Recommendation; not configured by this repo.)
- Guardrails in this repo: `.mcp.json` is git-ignored, and `tests/test_stitch_docs.py` scans tracked files for key-shaped strings (Google API keys, `X-Goog-Api-Key` with a value, private-key blocks).
- Stitch project and screen ids are resource names, not credentials, but they identify your private project; they appear in `design/stitch/MASTER_PROMPT.md` and `HANDOFF.md` on purpose.

## Failure and fallback

| Symptom | Likely cause | Do this |
|---|---|---|
| Stitch tools missing in the editor | Server not configured/connected | Use the manual path. |
| 401/403 from the server | Missing, wrong or restricted key | Re-check the key in your user config; never paste it into the repo. |
| Quota / rate errors | Account limits | Wait, or use the manual path. |
| Output too large for the chat | Big JSON/HTML | Save to a file, inspect with `jq`/Python. |
| Screen has no screenshot | Not rendered yet | Screenshot it from the browser (manual path). |
| Exported HTML looks right but needs CDNs | By design | Rebuild with tokens/components; never ship it. |

## What was and was not verified

Verified here: MCP server shape (redacted), the read-only tools above, the `{html}` download format, the CDN dependencies of an exported screen.
Not verified: exact Stitch web-UI menu names for export, other editors' MCP setup screens, key restrictions, rate limits.
