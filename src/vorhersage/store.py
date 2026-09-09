"""Transactional workflow state with immutable artifacts and optimistic writes."""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .common import canonical, digest, identifier, now, require

PROFILES = [
    {"id": "general", "description": "General binary event research",
     "domains": ["base_rates", "current_state", "actors_and_process", "contrary_evidence"]},
    {"id": "team_championship", "description": "Team championship fundamentals",
     "domains": ["prior_performance", "quarterback", "coaching", "roster_changes", "schedule", "health"]},
    {"id": "market_baseline", "description": "Explicitly limited market-price baseline",
     "domains": ["market_prices", "contract_and_timing"]},
]

DDL = """
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE profiles(id TEXT PRIMARY KEY, body TEXT NOT NULL);
CREATE TABLE questions(id TEXT, version INTEGER, body TEXT NOT NULL, created_at TEXT NOT NULL,
 PRIMARY KEY(id,version));
CREATE TABLE runs(id TEXT PRIMARY KEY, body TEXT NOT NULL, state TEXT NOT NULL, revision INTEGER NOT NULL);
CREATE TABLE artifacts(id TEXT PRIMARY KEY, kind TEXT NOT NULL, run_id TEXT,
 body TEXT NOT NULL, sha256 TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX artifacts_kind ON artifacts(kind);
CREATE TABLE receipts(scope TEXT, key TEXT, request_hash TEXT NOT NULL, result TEXT NOT NULL,
 PRIMARY KEY(scope,key));
CREATE TABLE events(seq INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, body TEXT, recorded_at TEXT);
"""


class Store:
    def __init__(self, project):
        self.root = Path(project).resolve()
        self.path = self.root / ".vorhersage" / "state.sqlite"

    def init(self, name):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Reserve the file atomically; never initialize an existing project.
        with self.path.open("xb"):
            pass
        with sqlite3.connect(self.path) as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.executescript(DDL)
            c.executemany("INSERT INTO meta VALUES (?,?)", [("schema_version", "1"), ("name", name), ("project_id", identifier("prj"))])
            for profile in PROFILES:
                c.execute("INSERT INTO profiles VALUES (?,?)", (profile["id"], canonical(profile)))
            for table in ("meta", "profiles", "questions", "artifacts", "receipts", "events"):
                for operation in ("UPDATE", "DELETE"):
                    c.execute(f"CREATE TRIGGER immutable_{table}_{operation} BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT,'immutable history'); END")
        return {"project": str(self.root), "database": str(self.path), "name": name}

    @contextmanager
    def connect(self, write=False):
        require(self.path.exists(), "Project is not initialized; run vorhersage init.", "uninitialized_project")
        uri = self.path.as_uri() + ("?mode=rw" if write else "?mode=ro")
        c = sqlite3.connect(uri, uri=True, timeout=10)
        c.row_factory = sqlite3.Row
        try:
            require(c.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0] == "1", "Unsupported project schema.")
            c.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield c
            c.commit()
        except Exception:
            c.rollback()
            raise
        finally:
            c.close()

    @staticmethod
    def artifact(c, id, kind=None):
        row = c.execute("SELECT * FROM artifacts WHERE id=?", (id,)).fetchone()
        require(row is not None and (kind is None or row["kind"] == kind), "Unknown artifact: " + id, "not_found")
        body = json.loads(row["body"])
        require(digest(body) == row["sha256"], "Artifact integrity check failed: " + id, "integrity_error")
        return body

    @staticmethod
    def put(c, kind, body, run_id=None, id=None):
        id = id or identifier(kind)
        existing = c.execute("SELECT body FROM artifacts WHERE id=?", (id,)).fetchone()
        if existing:
            require(json.loads(existing[0]) == body, "Artifact ID collision.")
            return id
        c.execute("INSERT INTO artifacts VALUES (?,?,?,?,?,?)", (id, kind, run_id, canonical(body), digest(body), now()))
        return id

    @staticmethod
    def event(c, kind, body):
        c.execute("INSERT INTO events(kind,body,recorded_at) VALUES (?,?,?)", (kind, canonical(body), now()))

    @staticmethod
    def question(c, id, version=None):
        row = c.execute("SELECT * FROM questions WHERE id=? AND (? IS NULL OR version=?) ORDER BY version DESC LIMIT 1", (id, version, version)).fetchone()
        require(row is not None, "Unknown question/version: " + id, "not_found")
        return {"specification": json.loads(row["body"]), "version": row["version"], "created_at": row["created_at"]}

    @staticmethod
    def run(c, id):
        row = c.execute("SELECT * FROM runs WHERE id=?", (id,)).fetchone()
        require(row is not None, "Unknown run: " + id, "not_found")
        body, state = json.loads(row["body"]), json.loads(row["state"])
        body["initial_information_as_of"] = body["information_as_of"]
        body["information_as_of"] = state.get("information_as_of", body["information_as_of"])
        body["cutoff_policy"] = body.get("cutoff_policy", "live" if body["mode"] == "prospective" else "fixed")
        return body, state, row["revision"]

    @staticmethod
    def all(c, kind):
        return [{"id": r["id"], **json.loads(r["body"])} for r in c.execute("SELECT * FROM artifacts WHERE kind=? ORDER BY created_at,id", (kind,))]

    @staticmethod
    def receipt(c, scope, key, request):
        row = c.execute("SELECT * FROM receipts WHERE scope=? AND key=?", (scope, key)).fetchone()
        if row:
            require(row["request_hash"] == digest(request), "Idempotency key reused with different content.", "idempotency_conflict")
            return {**json.loads(row["result"]), "duplicate": True}

    @staticmethod
    def remember(c, scope, key, request, result):
        c.execute("INSERT INTO receipts VALUES (?,?,?,?)", (scope, key, digest(request), canonical(result)))
