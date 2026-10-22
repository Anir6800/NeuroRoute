"""SQLite persistence for topologies (stdlib only, local file). Knows rows, not validation rules."""
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


class StorageError(RuntimeError):
    """The database could not be read or written (locked, unwritable, corrupt)."""


@dataclass(frozen=True)
class TopologyRow:
    id: str
    owner: str
    name: str
    nodes_json: str
    links_json: str
    content_hash: str
    version: int
    created_at: str
    updated_at: str


_SCHEMA = """
CREATE TABLE IF NOT EXISTS topologies (
    id TEXT PRIMARY KEY,
    owner TEXT NOT NULL,
    name TEXT NOT NULL,
    nodes_json TEXT NOT NULL,
    links_json TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    version INTEGER NOT NULL CHECK (version >= 1),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS topologies_owner ON topologies (owner, created_at, id);
"""
_COLUMNS = "id, owner, name, nodes_json, links_json, content_hash, version, created_at, updated_at"


class TopologyRepository:
    def __init__(self, path: Path, timeout_s: float = 5.0) -> None:
        self._path, self._timeout = Path(path), timeout_s
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with closing(self._connect()) as db:
                db.executescript(_SCHEMA)
        except (sqlite3.Error, OSError) as e:
            raise StorageError(f"cannot open topology database: {e}") from e

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self._path, timeout=self._timeout)
        return db

    def _run(self, sql: str, params: tuple = (), *, write: bool = False) -> list | int:
        try:
            with closing(self._connect()) as db, db:  # the inner `with db` commits or rolls back
                cur = db.execute(sql, params)
                return cur.fetchall() if not write else cur.rowcount
        except sqlite3.Error as e:
            raise StorageError(f"database error: {e}") from e

    def insert(self, row: TopologyRow) -> None:
        self._run(f"INSERT INTO topologies ({_COLUMNS}) VALUES (?,?,?,?,?,?,?,?,?)",
                  (row.id, row.owner, row.name, row.nodes_json, row.links_json, row.content_hash, row.version,
                   row.created_at, row.updated_at), write=True)

    def get(self, owner: str, topology_id: str) -> TopologyRow | None:
        rows = self._run(f"SELECT {_COLUMNS} FROM topologies WHERE owner = ? AND id = ?", (owner, topology_id))
        return TopologyRow(*rows[0]) if rows else None

    def list_for_owner(self, owner: str, limit: int, offset: int) -> tuple[list[TopologyRow], int]:
        rows = self._run(f"SELECT {_COLUMNS} FROM topologies WHERE owner = ? ORDER BY created_at, id LIMIT ? OFFSET ?",
                         (owner, limit, offset))
        total = self._run("SELECT COUNT(*) FROM topologies WHERE owner = ?", (owner,))[0][0]
        return [TopologyRow(*r) for r in rows], total

    def update_if_version(self, owner: str, topology_id: str, expected_version: int, *, name: str, nodes_json: str,
                          links_json: str, content_hash: str, updated_at: str) -> bool:
        """Atomic compare-and-set: True if the row had `expected_version` and was updated (version + 1)."""
        changed = self._run(
            "UPDATE topologies SET name = ?, nodes_json = ?, links_json = ?, content_hash = ?, updated_at = ?, "
            "version = version + 1 WHERE owner = ? AND id = ? AND version = ?",
            (name, nodes_json, links_json, content_hash, updated_at, owner, topology_id, expected_version), write=True)
        return changed == 1


@lru_cache(maxsize=8)
def get_repository(path: Path, timeout_s: float) -> TopologyRepository:
    return TopologyRepository(path, timeout_s)
