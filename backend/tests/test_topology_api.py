"""Topology API over HTTP with unsigned emulator-style tokens (same path as /me), a temporary SQLite file per test."""
import ast
import copy
import json
import threading
import time
from pathlib import Path

import jwt
import pytest
from fastapi.testclient import TestClient

from app.api import topologies as routes
from app.core.config import Settings, get_settings
from app.main import app
from app.repositories.topologies import TopologyRepository
from app.schemas.topology_api import ErrorResponse, TopologyOut
from research.scenarios import load_suite
from research.simulation.engine import simulate
from research.simulation.models import Scenario

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "backend" / "app"
PROJECT = "demo-neuroroute"
MAX_NODES, MAX_LINKS = 6, 8


def token(uid: str = "uid-1", **over) -> str:
    now = int(time.time())
    claims = {"iss": f"https://securetoken.google.com/{PROJECT}", "aud": PROJECT, "sub": uid, "iat": now, "exp": now + 3600,
              "role": "researcher", "email": f"{uid}@neuroroute.test"}
    claims.update(over)
    return jwt.encode({k: v for k, v in claims.items() if v is not None}, None, algorithm="none")


def auth(uid: str = "uid-1") -> dict[str, str]:
    return {"Authorization": f"Bearer {token(uid)}"}


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "topologies.sqlite3"


@pytest.fixture
def client(db_path: Path):
    settings = Settings(db_path=db_path, max_topology_nodes=MAX_NODES, max_topology_links=MAX_LINKS)
    app.dependency_overrides[get_settings] = lambda: settings
    yield TestClient(app)
    app.dependency_overrides.clear()


def link(id_: str, s: str, t: str, cap: float = 100.0, delay: float = 1.0, buf: int = 50, weight: float = 1.0) -> dict:
    return {"id": id_, "source": s, "target": t, "capacity_mbps": cap, "prop_delay_ms": delay, "buffer_pkts": buf, "weight": weight}


def diamond(name: str = "diamond") -> dict:
    return {"name": name, "nodes": [{"id": "a", "kind": "host"}, {"id": "r1"}, {"id": "r2"}, {"id": "b", "kind": "host"}],
            "links": [link("a-r1", "a", "r1"), link("a-r2", "a", "r2", delay=2.0), link("r1-b", "r1", "b", cap=50.0),
                      link("r2-b", "r2", "b", cap=50.0, delay=2.0, weight=2.0)]}


def mutated(**changes) -> dict:
    body = diamond()
    body.update(changes)
    return body


def codes(response) -> list[str]:
    assert response.status_code == 400, response.text
    parsed = ErrorResponse.model_validate(response.json())  # the 400 body always has the documented shape
    assert parsed.detail.code == "invalid_topology"
    return [r.code for r in parsed.detail.reasons]


def create(client: TestClient, body: dict | None = None, uid: str = "uid-1") -> TopologyOut:
    r = client.post("/topologies", json=body or diamond(), headers=auth(uid))
    assert r.status_code == 201, r.text
    return TopologyOut.model_validate(r.json())


# ----------------------------------------------------------------------------- valid input
def test_create_get_list_roundtrip(client: TestClient) -> None:
    created = create(client)
    assert created.version == 1 and created.schema_version == "1.0" and len(created.content_hash) == 64
    assert len(created.nodes) == 4 and len(created.links) == 4 and created.created_at == created.updated_at
    got = client.get(f"/topologies/{created.id}", headers=auth())
    assert got.status_code == 200 and TopologyOut.model_validate(got.json()) == created
    listing = client.get("/topologies", headers=auth()).json()
    assert listing["total"] == 1 and listing["limit"] == 50 and listing["offset"] == 0
    assert listing["items"] == [{"id": created.id, "name": "diamond", "version": 1, "content_hash": created.content_hash,
                                 "n_nodes": 4, "n_links": 4, "updated_at": created.updated_at}]


def test_the_stored_topology_is_persisted_in_the_database_file(client: TestClient, db_path: Path) -> None:
    created = create(client)
    row = TopologyRepository(db_path).get("uid-1", created.id)  # a brand-new repository object reads it back
    assert row is not None and row.name == "diamond" and row.version == 1 and json.loads(row.links_json)[0]["id"] == "a-r1"


def test_validate_endpoint_does_not_save(client: TestClient) -> None:
    r = client.post("/topologies/validate", json=diamond(), headers=auth())
    assert r.status_code == 200 and r.json()["valid"] is True and (r.json()["n_nodes"], r.json()["n_links"]) == (4, 4)
    assert client.get("/topologies", headers=auth()).json()["total"] == 0
    bad = client.post("/topologies/validate", json=mutated(links=[link("x", "a", "a")]), headers=auth())
    assert "self_loop" in codes(bad)


def test_defaults_are_applied_and_names_are_trimmed(client: TestClient) -> None:
    body = {"name": "  spaced  ", "nodes": [{"id": "a"}, {"id": "b"}],
            "links": [{"id": "l", "source": "a", "target": "b", "capacity_mbps": 10, "prop_delay_ms": 1, "buffer_pkts": 5}]}
    t = create(client, body)
    assert t.name == "spaced" and t.nodes[0].kind == "router" and t.links[0].weight == 1.0


def test_a_one_way_chain_is_connected_but_two_separate_chains_are_not(client: TestClient) -> None:
    chain = {"name": "chain", "nodes": [{"id": n} for n in "abc"], "links": [link("ab", "a", "b"), link("bc", "b", "c")]}
    create(client, chain)  # weak connectivity: the shipped fixtures are one-way a -> r -> b graphs
    split = {"name": "split", "nodes": [{"id": n} for n in "abcd"], "links": [link("ab", "a", "b"), link("cd", "c", "d")]}
    assert codes(client.post("/topologies", json=split, headers=auth())) == ["disconnected"]


def test_every_shipped_fixture_topology_is_accepted_and_runs_in_the_simulator(client: TestClient) -> None:
    suite = load_suite()
    for name in suite.names("train"):
        sc = suite.base_scenario(name)
        body = {"name": name, "nodes": [n.model_dump() for n in sc.nodes], "links": [lk.model_dump() for lk in sc.links]}
        t = create(client, body)
        rebuilt = sc.model_dump(mode="json")  # a saved topology + the scenario's flows is a valid, simulatable scenario
        rebuilt["nodes"], rebuilt["links"] = [n.model_dump(exclude={"x", "y"}) for n in t.nodes], [lk.model_dump() for lk in t.links]
        assert simulate(Scenario.model_validate(rebuilt)).digest() == simulate(sc).digest()


def test_research_scenario_hashes_pinned_in_the_suite_are_unchanged() -> None:
    suite = load_suite()
    for e in suite.scenarios:
        assert suite.base_scenario(e.name).config_hash == e.config_hash  # raises if any pin or the shared schema moved


def test_content_hash_ignores_order_and_name_but_not_the_graph(client: TestClient) -> None:
    a = create(client, diamond("one"))
    shuffled = diamond("two")
    shuffled["nodes"].reverse()
    shuffled["links"].reverse()
    b = create(client, shuffled)
    assert a.content_hash == b.content_hash and a.id != b.id
    changed = diamond()
    changed["links"][0]["capacity_mbps"] = 101.0
    assert create(client, changed).content_hash != a.content_hash


# ----------------------------------------------------------------------------- malformed input: 422
def test_malformed_json_is_422(client: TestClient) -> None:
    for raw in (b"{not json", b"", b'{"name": "x", "nodes": [', b"[1, 2]", b"null"):
        r = client.post("/topologies", content=raw, headers={**auth(), "Content-Type": "application/json"})
        assert r.status_code == 422, raw


@pytest.mark.parametrize("body", [
    {},
    {"name": "x"},
    {"name": "x", "nodes": "a", "links": []},
    {"name": "", "nodes": [{"id": "a"}, {"id": "b"}], "links": [link("l", "a", "b")]},
    {"name": "x" * 65, "nodes": [{"id": "a"}, {"id": "b"}], "links": [link("l", "a", "b")]},
    {"name": "x", "nodes": [{"id": "a", "kind": "switch"}, {"id": "b"}], "links": [link("l", "a", "b")]},
    {"name": "x", "nodes": [{"id": "a", "colour": "red"}, {"id": "b"}], "links": [link("l", "a", "b")]},
    {"name": "x", "nodes": [{"id": "a"}, {"id": "b"}], "links": [{**link("l", "a", "b"), "capacity_mbps": "fast"}]},
    {"name": "x", "nodes": [{"id": "a"}, {"id": "b"}], "links": [{**link("l", "a", "b"), "buffer_pkts": 1.5}]},
    {"name": "x", "nodes": [{"id": "a"}, {"id": "b"}], "links": [{**link("l", "a", "b"), "capacity_mbps": None}]},
    {"name": "x", "schema_version": "2.0", "nodes": [{"id": "a"}, {"id": "b"}], "links": [link("l", "a", "b")]},
    {"name": "x", "extra": 1, "nodes": [{"id": "a"}, {"id": "b"}], "links": [link("l", "a", "b")]},
    {"name": "x", "nodes": [{"id": ""}, {"id": "b"}], "links": [link("l", "a", "b")]},
])
def test_wrong_types_missing_and_unknown_fields_are_422(client: TestClient, body) -> None:
    r = client.post("/topologies", json=body, headers=auth())
    assert r.status_code == 422, r.text
    assert client.get("/topologies", headers=auth()).json()["total"] == 0


@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_numbers_are_422(client: TestClient, literal: str) -> None:
    text = json.dumps(diamond()).replace('"capacity_mbps": 100.0', f'"capacity_mbps": {literal}', 1)
    r = client.post("/topologies", content=text, headers={**auth(), "Content-Type": "application/json"})
    assert r.status_code == 422


# ----------------------------------------------------------------------------- invalid graph: 400 with reasons
def test_disconnected_graph(client: TestClient) -> None:
    body = mutated(nodes=[*diamond()["nodes"], {"id": "island"}])
    r = client.post("/topologies", json=body, headers=auth())
    assert codes(r) == ["disconnected"] and "island" in r.json()["detail"]["reasons"][0]["message"]
    assert client.get("/topologies", headers=auth()).json()["total"] == 0  # nothing was saved


def test_self_loop(client: TestClient) -> None:
    body = diamond()
    body["links"].append(link("loop", "r1", "r1"))
    r = client.post("/topologies", json=body, headers=auth())
    assert codes(r) == ["self_loop"] and r.json()["detail"]["reasons"][0]["path"] == "links[4]"


def test_duplicate_links(client: TestClient) -> None:
    same_id = diamond()
    same_id["links"].append(link("a-r1", "r2", "r1"))
    assert codes(client.post("/topologies", json=same_id, headers=auth())) == ["duplicate_link_id"]
    parallel = diamond()
    parallel["links"].append(link("a-r1-bis", "a", "r1"))
    r = client.post("/topologies", json=parallel, headers=auth())
    assert codes(r) == ["duplicate_link"] and "a-r1" in r.json()["detail"]["reasons"][0]["message"]
    reverse = diamond()
    reverse["links"].append(link("r1-a", "r1", "a"))  # the opposite direction is a different link: allowed
    create(client, reverse)


def test_duplicate_node_unknown_endpoint_and_bad_ids(client: TestClient) -> None:
    dup = diamond()
    dup["nodes"].append({"id": "a"})
    assert codes(client.post("/topologies", json=dup, headers=auth())) == ["duplicate_node_id"]
    ghost = diamond()
    ghost["links"][0]["target"] = "ghost"
    assert codes(client.post("/topologies", json=ghost, headers=auth())) == ["unknown_endpoint"]
    for bad_id in ("has space", "x" * 33, "a/b", "naïve"):
        body = diamond()
        body["nodes"][1]["id"] = bad_id
        body["links"] = [link("l1", "a", bad_id), link("l2", bad_id, "b"), link("l3", "a", "r2"), link("l4", "r2", "b")]
        assert "invalid_node_id" in codes(client.post("/topologies", json=body, headers=auth())), bad_id
    body = diamond()
    body["links"][0]["id"] = "bad id"
    assert codes(client.post("/topologies", json=body, headers=auth())) == ["invalid_link_id"]


@pytest.mark.parametrize(("field", "value", "code"), [
    ("capacity_mbps", 0, "non_positive_capacity"),
    ("capacity_mbps", -5.5, "non_positive_capacity"),
    ("prop_delay_ms", 0, "non_positive_delay"),
    ("prop_delay_ms", -1, "non_positive_delay"),
    ("buffer_pkts", 0, "non_positive_buffer"),
    ("buffer_pkts", -3, "non_positive_buffer"),
    ("weight", -0.1, "negative_weight"),
])
def test_non_positive_numbers(client: TestClient, field: str, value: float, code: str) -> None:
    body = diamond()
    body["links"][2][field] = value
    r = client.post("/topologies", json=body, headers=auth())
    assert codes(r) == [code] and r.json()["detail"]["reasons"][0]["path"] == f"links[2].{field}"


def test_size_limits_come_from_the_config(client: TestClient, db_path: Path) -> None:
    many_nodes = {"name": "big", "nodes": [{"id": f"n{i}"} for i in range(MAX_NODES + 1)],
                  "links": [link(f"l{i}", f"n{i}", f"n{i + 1}") for i in range(MAX_NODES)]}
    r = client.post("/topologies", json=many_nodes, headers=auth())
    assert codes(r) == ["too_many_nodes"] and str(MAX_NODES) in r.json()["detail"]["reasons"][0]["message"]
    nodes = [{"id": f"n{i}"} for i in range(MAX_NODES)]
    links = [link(f"l{i}_{j}", f"n{i}", f"n{j}") for i in range(MAX_NODES) for j in range(MAX_NODES) if i != j][: MAX_LINKS + 1]
    assert codes(client.post("/topologies", json={"name": "dense", "nodes": nodes, "links": links}, headers=auth())) == ["too_many_links"]
    exactly = {"name": "edge", "nodes": nodes, "links": [link(f"c{i}", f"n{i}", f"n{i + 1}") for i in range(MAX_NODES - 1)]}
    create(client, exactly)  # exactly MAX_NODES nodes: at the limit, valid
    # limits are config, not constants: a tighter setting applies at once
    path = db_path
    app.dependency_overrides[get_settings] = lambda: Settings(db_path=path, max_topology_nodes=3, max_topology_links=8)
    assert "too_many_nodes" in codes(client.post("/topologies", json=diamond(), headers=auth()))


def test_too_few_nodes_and_links(client: TestClient) -> None:
    assert set(codes(client.post("/topologies", json={"name": "x", "nodes": [{"id": "a"}], "links": []}, headers=auth()))) == {
        "too_few_nodes", "too_few_links"}


def test_all_problems_are_reported_together_and_the_list_is_bounded(client: TestClient) -> None:
    body = diamond()
    body["links"][0]["capacity_mbps"] = -1
    body["links"].append(link("loop", "r1", "r1"))
    body["nodes"].append({"id": "island"})
    assert codes(client.post("/topologies", json=body, headers=auth())) == ["non_positive_capacity", "self_loop", "disconnected"]
    flood = {"name": "flood", "nodes": [{"id": "a"}, {"id": "b"}],
             "links": [link(f"l{i}", "a", "a", cap=-1) for i in range(8)]}
    assert len(codes(client.post("/topologies", json=flood, headers=auth()))) <= 50


# ----------------------------------------------------------------------------- authentication
def test_every_endpoint_requires_a_token(client: TestClient) -> None:
    created = create(client)
    calls = [("post", "/topologies", diamond()), ("post", "/topologies/validate", diamond()), ("get", "/topologies", None),
             ("get", f"/topologies/{created.id}", None), ("put", f"/topologies/{created.id}", {**diamond(), "version": 1})]
    for method, url, body in calls:
        r = getattr(client, method)(url, **({"json": body} if body is not None else {}))
        assert r.status_code == 401 and r.headers["www-authenticate"] == "Bearer", (method, url)
        r = getattr(client, method)(url, headers={"Authorization": "Bearer not.a.jwt"}, **({"json": body} if body is not None else {}))
        assert r.status_code == 401, (method, url)
    assert client.get("/topologies", headers={"Authorization": "Basic abc"}).status_code == 401
    expired = {"Authorization": f"Bearer {token(exp=int(time.time()) - 3600)}"}
    assert client.get("/topologies", headers=expired).status_code == 401
    assert client.get("/topologies", headers={"Authorization": f"Bearer {token(role='guest')}"}).status_code == 403
    assert client.get("/topologies", headers={"Authorization": f"Bearer {token(aud='other-project')}"}).status_code == 403


def test_auth_is_checked_before_the_body(client: TestClient) -> None:
    r = client.post("/topologies", content=b"{broken", headers={"Content-Type": "application/json"})
    assert r.status_code in (401, 422)
    assert client.post("/topologies", json=mutated(links=[link("l", "a", "a")])).status_code == 401  # invalid graph, no token: 401 not 400


def test_users_only_see_their_own_topologies(client: TestClient) -> None:
    mine = create(client, uid="alice")
    assert client.get(f"/topologies/{mine.id}", headers=auth("bob")).status_code == 404
    assert client.put(f"/topologies/{mine.id}", json={**diamond("stolen"), "version": 1}, headers=auth("bob")).status_code == 404
    assert client.get("/topologies", headers=auth("bob")).json() == {"items": [], "total": 0, "limit": 50, "offset": 0}
    assert client.get(f"/topologies/{mine.id}", headers=auth("alice")).json()["name"] == "diamond"  # untouched


# ----------------------------------------------------------------------------- not found, paging
def test_unknown_ids_are_404(client: TestClient) -> None:
    for tid in ("nope", "0" * 32, "..%2F..%2Fetc", "a b"):
        r = client.get(f"/topologies/{tid}", headers=auth())
        assert r.status_code == 404, tid  # slash-containing ids never reach the handler; the router answers 404 itself
    assert client.get("/topologies/nope", headers=auth()).json()["detail"]["code"] == "topology_not_found"
    assert client.put("/topologies/nope", json={**diamond(), "version": 1}, headers=auth()).status_code == 404


def test_list_pagination(client: TestClient) -> None:
    ids = [create(client, diamond(f"t{i}")).id for i in range(5)]
    page = client.get("/topologies?limit=2&offset=2", headers=auth()).json()
    assert page["total"] == 5 and [i["id"] for i in page["items"]] == ids[2:4] and (page["limit"], page["offset"]) == (2, 2)
    assert client.get("/topologies?limit=2&offset=4", headers=auth()).json()["items"][0]["id"] == ids[4]
    assert client.get("/topologies?offset=9", headers=auth()).json()["items"] == []
    for q in ("limit=0", "limit=101", "offset=-1", "limit=abc"):
        assert client.get(f"/topologies?{q}", headers=auth()).status_code == 422, q


# ----------------------------------------------------------------------------- optimistic concurrency
def test_update_bumps_the_version_and_a_stale_version_is_409(client: TestClient) -> None:
    t = create(client)
    edited = {**diamond("renamed"), "version": 1}
    edited["links"][0]["capacity_mbps"] = 200.0
    r = client.put(f"/topologies/{t.id}", json=edited, headers=auth())
    assert r.status_code == 200
    v2 = TopologyOut.model_validate(r.json())
    assert v2.version == 2 and v2.name == "renamed" and v2.links[0].capacity_mbps == 200.0
    assert v2.content_hash != t.content_hash and v2.created_at == t.created_at and v2.id == t.id

    stale = client.put(f"/topologies/{t.id}", json={**diamond("lost update"), "version": 1}, headers=auth())
    assert stale.status_code == 409
    body = ErrorResponse.model_validate(stale.json()).detail
    assert body.code == "version_conflict" and body.current_version == 2
    assert client.get(f"/topologies/{t.id}", headers=auth()).json()["name"] == "renamed"  # the stale edit changed nothing

    ahead = client.put(f"/topologies/{t.id}", json={**diamond(), "version": 7}, headers=auth())
    assert ahead.status_code == 409 and ahead.json()["detail"]["current_version"] == 2  # a future version is just as wrong
    ok = client.put(f"/topologies/{t.id}", json={**diamond("again"), "version": 2}, headers=auth())
    assert ok.status_code == 200 and ok.json()["version"] == 3


def test_update_needs_a_valid_version_and_a_valid_graph(client: TestClient) -> None:
    t = create(client)
    assert client.put(f"/topologies/{t.id}", json=diamond(), headers=auth()).status_code == 422  # version missing
    for v in (0, -1, "1", 1.5, None):
        assert client.put(f"/topologies/{t.id}", json={**diamond(), "version": v}, headers=auth()).status_code == 422, v
    bad = {**mutated(links=[link("x", "a", "a")]), "version": 1}
    assert "self_loop" in codes(client.put(f"/topologies/{t.id}", json=bad, headers=auth()))
    stale_and_bad = {**bad, "version": 99}
    assert "self_loop" in codes(client.put(f"/topologies/{t.id}", json=stale_and_bad, headers=auth()))  # invalid wins over stale
    assert client.get(f"/topologies/{t.id}", headers=auth()).json()["version"] == 1


def test_two_writers_with_the_same_version_exactly_one_wins(client: TestClient) -> None:
    t = create(client)
    results: list[int] = []
    gate = threading.Barrier(8)

    def writer(i: int) -> None:
        gate.wait()
        r = client.put(f"/topologies/{t.id}", json={**diamond(f"w{i}"), "version": 1}, headers=auth())
        results.append(r.status_code)

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(8)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    assert sorted(results) == [200] + [409] * 7
    assert client.get(f"/topologies/{t.id}", headers=auth()).json()["version"] == 2


# ----------------------------------------------------------------------------- storage failure
def test_an_unusable_database_is_a_503_that_does_not_leak_paths(tmp_path: Path) -> None:
    settings = Settings(db_path=tmp_path)  # a directory, so SQLite cannot open it as a file
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        r = TestClient(app).get("/topologies", headers=auth())
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 503 and r.json()["detail"]["code"] == "storage_unavailable"
    assert str(tmp_path) not in r.text


# ----------------------------------------------------------------------------- architecture: Route -> Service -> Repository
def _imports(path: Path) -> set[str]:
    out: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            out |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.add(node.module)
    return out


def test_layers_only_import_downwards() -> None:
    service, repo = _imports(APP / "services" / "topologies.py"), _imports(APP / "repositories" / "topologies.py")
    assert not any(m.split(".")[0] in {"fastapi", "starlette", "sqlite3"} or m.startswith("app.api") for m in service)
    assert not any(m.split(".")[0] in {"fastapi", "starlette"} or m.startswith(("app.api", "app.services")) for m in repo)
    assert "sqlite3" in repo and "app.repositories.topologies" in service


def test_route_handlers_only_delegate_to_the_service() -> None:
    tree = ast.parse((APP / "api" / "topologies.py").read_text(encoding="utf-8"))
    handlers = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.decorator_list and n.name != "get_service"]
    assert {h.name for h in handlers} == {"validate", "create", "list_topologies", "get_topology", "update"}
    for h in handlers:
        body = [s for s in h.body if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant))]
        assert len(body) == 1 and isinstance(body[0], ast.Return), h.name
        call = body[0].value
        assert isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) and call.func.value.id == "service", h.name
    assert routes.router.prefix == "/topologies"


def test_openapi_documents_the_error_responses(client: TestClient) -> None:
    spec = client.get("/openapi.json").json()
    put = spec["paths"]["/topologies/{topology_id}"]["put"]["responses"]
    assert {"200", "400", "404", "409", "422"} <= set(put)
    assert "201" in spec["paths"]["/topologies"]["post"]["responses"]
    assert copy.deepcopy(spec["components"]["schemas"]["TopologyIn"]["properties"]["schema_version"])["const"] == "1.0"


def test_exactly_the_maximum_number_of_links_is_accepted(client: TestClient) -> None:
    nodes = [{"id": f"n{i}"} for i in range(4)]
    pairs = [(i, j) for i in range(4) for j in range(4) if i != j][:MAX_LINKS]
    body = {"name": "full", "nodes": nodes, "links": [link(f"l{i}{j}", f"n{i}", f"n{j}") for i, j in pairs]}
    assert len(body["links"]) == MAX_LINKS
    create(client, body)
    body["links"].append(link("one-more", "n3", "n2"))  # a 9th, otherwise valid, link
    assert "too_many_links" in codes(client.post("/topologies", json=body, headers=auth()))


def test_the_503_message_is_fixed_text(tmp_path: Path) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(db_path=tmp_path)
    try:
        r = TestClient(app).get("/topologies", headers=auth())
    finally:
        app.dependency_overrides.clear()
    assert r.json()["detail"]["message"] == "the topology store is unavailable; try again"


def test_the_service_rejects_bad_paging_itself(db_path: Path) -> None:
    from app.services.topologies import Limits, TopologyService

    service = TopologyService(TopologyRepository(db_path), Limits(6, 8))
    for limit, offset in ((0, 0), (101, 0), (10, -1)):
        with pytest.raises(ValueError):
            service.list("u", limit, offset)


def test_node_positions_are_stored_but_are_not_part_of_the_graph_identity(client: TestClient) -> None:
    plain = create(client, diamond("plain"))
    placed = diamond("placed")
    for i, n in enumerate(placed["nodes"]):
        n.update(x=10.5 * i, y=-3.0)
    t = create(client, placed)
    assert [(n.x, n.y) for n in t.nodes] == [(0.0, -3.0), (10.5, -3.0), (21.0, -3.0), (31.5, -3.0)]
    assert client.get(f"/topologies/{t.id}", headers=auth()).json()["nodes"][1] == {"id": "r1", "kind": "router", "x": 10.5, "y": -3.0}
    assert t.content_hash == plain.content_hash  # moving nodes does not change the graph
    assert plain.nodes[0].x is None
    moved = {**placed, "version": 1}
    moved["nodes"][0]["x"] = 99.0
    r = client.put(f"/topologies/{t.id}", json=moved, headers=auth())
    assert r.status_code == 200 and r.json()["nodes"][0]["x"] == 99.0 and r.json()["content_hash"] == t.content_hash


@pytest.mark.parametrize("bad", ["12", float("inf"), 1e7, -1e7, True])
def test_bad_node_positions_are_422(client: TestClient, bad) -> None:
    body = diamond()
    body["nodes"][0]["x"] = bad
    text = json.dumps(body).replace("Infinity", "1e999")
    r = client.post("/topologies", content=text, headers={**auth(), "Content-Type": "application/json"})
    assert r.status_code == 422
