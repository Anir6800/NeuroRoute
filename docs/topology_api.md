# Topology API

Local, authenticated REST API to validate and save network topologies (nodes + links, no flows). Layering is
`api/topologies.py` (route) -> `services/topologies.py` (rules) -> `repositories/topologies.py` (SQLite). Routes only delegate;
`api/errors.py` turns domain errors into HTTP. Everything binds to localhost and uses the same emulator-token auth as `/me`.

| Method and path | Purpose | Success | Errors |
|---|---|---|---|
| `POST /topologies/validate` | check without saving | 200 `{valid, n_nodes, n_links, content_hash}` | 400, 401, 422 |
| `POST /topologies` | create | 201 `TopologyOut` (version 1) | 400, 401, 422 |
| `GET /topologies?limit=&offset=` | list your topologies (limit 1-100, default 50) | 200 `{items, total, limit, offset}` | 401, 422 |
| `GET /topologies/{id}` | read | 200 `TopologyOut` | 401, 404 |
| `PUT /topologies/{id}` | replace; body carries `version` | 200 `TopologyOut` (version + 1) | 400, 401, 404, 409, 422 |

Topologies belong to the user who created them; other users get 404 (not 403), so ids are not probeable.

## Request body (schema 1.0)

```json
{"name": "diamond", "schema_version": "1.0",
 "nodes": [{"id": "a", "kind": "host"}, {"id": "r1"}],
 "links": [{"id": "a-r1", "source": "a", "target": "r1", "capacity_mbps": 100, "prop_delay_ms": 1, "buffer_pkts": 50, "weight": 1}]}
```

`kind` is `router` (default) or `host`; a node may carry `x` and `y` (editor layout, within +-1e6; not part of the graph, so excluded from `content_hash`); `weight` defaults to 1. Links are directed (model a cable as two links). `PUT` adds an integer `version`.
Responses add `id`, `version`, `content_hash` (SHA-256 of the graph only, independent of order and name), `created_at`, `updated_at`.
The fields match the research `Node`/`Link` models, so a saved topology plus flows is a valid `Scenario`. The research schema itself is
unchanged, and the scenario hashes pinned in `experiments/configs/suite.json` still hold (a test checks).

## Status codes

- **422** malformed: bad JSON, wrong types (numbers must be real JSON numbers, not strings), missing or unknown fields, non-finite numbers, a bad `version`, `limit` out of range.
  Body: `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}`. The offending input is not echoed back.
- **400** well-formed but not a valid graph. Body: `{"detail": {"code": "invalid_topology", "message": "...", "reasons": [{"code", "message", "path"}]}}` listing every
  problem (at most 50). Nothing is saved. Reason codes:
  `too_many_nodes`, `too_many_links` (checked first; nothing else is evaluated on an oversized request), `too_few_nodes`, `too_few_links`,
  `invalid_node_id`, `invalid_link_id` (must match `[A-Za-z0-9_-]{1,32}`), `duplicate_node_id`, `duplicate_link_id`, `duplicate_link` (two links with the same source and target),
  `unknown_endpoint`, `self_loop`, `non_positive_capacity`, `non_positive_delay`, `non_positive_buffer`, `negative_weight`, `disconnected`.
- **409** stale `version`: `{"detail": {"code": "version_conflict", "current_version": n, ...}}`. Nothing changed. Reload and retry.
- **404** unknown id (or someone else's). **401** missing/invalid/expired token; **403** wrong role or project. **503** the database is unavailable (details only in the log).

## Decisions and limits

- **Connectivity is weak** (link direction ignored). The shipped fixtures are one-way `a -> r -> b` diamonds, which strong connectivity would reject. A weakly connected graph can still have unreachable pairs; the simulator reports those as no-route.
- **Delay must be > 0** here (the research model allows 0), as the task required. `buffer_pkts` > 0 and `weight` >= 0.
- An invalid body is reported (400) even when the version is also stale; the version is compared only for a valid body.
- **Optimistic concurrency** is one atomic `UPDATE ... WHERE version = ?`, so two writers with the same version cannot both win (tested with 8 threads).
- Limits come from settings: `NEUROROUTE_MAX_TOPOLOGY_NODES` (64), `NEUROROUTE_MAX_TOPOLOGY_LINKS` (512). The database file defaults to `backend/.data/neuroroute.sqlite3` (git-ignored) with a 5 s timeout.
- Not built: delete, pagination cursors, admin access to other users' topologies, a request-body size cap (the list limits apply only after parsing; acceptable on localhost), and the frontend wiring.
