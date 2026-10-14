from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path

from app.models import AclException, Corpus, Document, Org, RoleAssignment, User
from app.seed import build_corpus


SCHEMA = """
CREATE TABLE IF NOT EXISTS orgs (
    id TEXT PRIMARY KEY,
    parent_id TEXT,
    name TEXT NOT NULL,
    kind TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    org_id TEXT NOT NULL,
    employment_type TEXT NOT NULL,
    clearance TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS role_assignments (
    user_id TEXT NOT NULL,
    role TEXT NOT NULL,
    scope TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS document_versions (
    version_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    title TEXT NOT NULL,
    topic TEXT NOT NULL,
    doc_type TEXT NOT NULL,
    owner_org TEXT NOT NULL,
    audience_orgs TEXT NOT NULL,
    audience_type TEXT NOT NULL,
    classification TEXT NOT NULL,
    allowed_contract_types TEXT NOT NULL,
    status TEXT NOT NULL,
    effective_from TEXT NOT NULL,
    effective_to TEXT,
    override_mode TEXT NOT NULL,
    supersedes INTEGER,
    supplement_target TEXT,
    required_role TEXT,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    published_at TEXT,
    match_phrases TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version_id TEXT NOT NULL,
    position INTEGER NOT NULL,
    text TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS acl_exceptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    version INTEGER,
    effect TEXT NOT NULL,
    reason TEXT NOT NULL,
    valid_from TEXT NOT NULL,
    valid_to TEXT
);
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    user_id TEXT NOT NULL,
    question TEXT NOT NULL,
    as_of TEXT NOT NULL,
    topic TEXT,
    outcome TEXT NOT NULL,
    winner_document_id TEXT,
    winner_version INTEGER,
    answer TEXT NOT NULL,
    llm_used INTEGER NOT NULL,
    detail_json TEXT NOT NULL
);
"""


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    _migrate(connection)
    return connection


def _migrate(connection: sqlite3.Connection) -> None:
    connection.executescript(SCHEMA)
    columns = {row["name"] for row in connection.execute("PRAGMA table_info(document_versions)")}
    if columns and "match_phrases" not in columns:
        connection.execute(
            "ALTER TABLE document_versions ADD COLUMN match_phrases TEXT NOT NULL DEFAULT '[]'"
        )
    connection.commit()


def _iso(value: date | None) -> str | None:
    return value.isoformat() if value else None


def ensure_database(path: Path) -> None:
    connection = connect(path)
    try:
        count = connection.execute("SELECT COUNT(*) AS total FROM orgs").fetchone()["total"]
    finally:
        connection.close()
    if count == 0:
        seed_database(path)


def insert_document(path: Path, document: Document) -> None:
    connection = connect(path)
    try:
        connection.execute(
            """
            INSERT INTO document_versions (
                version_id, document_id, version, title, topic, doc_type, owner_org,
                audience_orgs, audience_type, classification, allowed_contract_types,
                status, effective_from, effective_to, override_mode, supersedes,
                supplement_target, required_role, content, created_at, published_at,
                match_phrases
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                document.version_id,
                document.document_id,
                document.version,
                document.title,
                document.topic,
                document.doc_type,
                document.owner_org,
                json.dumps(document.audience_orgs, ensure_ascii=False),
                document.audience_type,
                document.classification,
                json.dumps(document.allowed_contract_types, ensure_ascii=False),
                document.status,
                document.effective_from.isoformat(),
                _iso(document.effective_to),
                document.override_mode,
                document.supersedes,
                document.supplement_target,
                document.required_role,
                document.content,
                document.created_at.isoformat(),
                _iso(document.published_at),
                json.dumps(document.match_phrases, ensure_ascii=False),
            ),
        )
        connection.executemany(
            "INSERT INTO chunks (version_id, position, text) VALUES (?, ?, ?)",
            [
                (document.version_id, position, text)
                for position, text in enumerate(document.chunks)
            ],
        )
        connection.commit()
    finally:
        connection.close()


def delete_document(path: Path, version_id: str) -> bool:
    connection = connect(path)
    try:
        row = connection.execute(
            "SELECT document_id, version FROM document_versions WHERE version_id = ?",
            (version_id,),
        ).fetchone()
        if row is None:
            return False
        connection.execute("DELETE FROM chunks WHERE version_id = ?", (version_id,))
        connection.execute(
            "DELETE FROM acl_exceptions WHERE document_id = ? AND version = ?",
            (row["document_id"], row["version"]),
        )
        connection.execute("DELETE FROM document_versions WHERE version_id = ?", (version_id,))
        connection.commit()
        return True
    finally:
        connection.close()


def seed_database(path: Path) -> Corpus:
    corpus = build_corpus()
    connection = connect(path)
    try:
        connection.executescript(SCHEMA)
        connection.executescript(
            """
            DELETE FROM chunks;
            DELETE FROM acl_exceptions;
            DELETE FROM document_versions;
            DELETE FROM role_assignments;
            DELETE FROM users;
            DELETE FROM orgs;
            """
        )
        connection.executemany(
            "INSERT INTO orgs (id, parent_id, name, kind) VALUES (?, ?, ?, ?)",
            [(org.id, org.parent_id, org.name, org.kind) for org in corpus.orgs.values()],
        )
        connection.executemany(
            """
            INSERT INTO users (id, name, org_id, employment_type, clearance)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (user.id, user.name, user.org, user.employment_type, user.clearance)
                for user in corpus.users.values()
            ],
        )
        connection.executemany(
            "INSERT INTO role_assignments (user_id, role, scope) VALUES (?, ?, ?)",
            [
                (user.id, role.role, role.scope)
                for user in corpus.users.values()
                for role in user.roles
            ],
        )
        connection.executemany(
            """
            INSERT INTO document_versions (
                version_id, document_id, version, title, topic, doc_type, owner_org,
                audience_orgs, audience_type, classification, allowed_contract_types,
                status, effective_from, effective_to, override_mode, supersedes,
                supplement_target, required_role, content, created_at, published_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    document.version_id,
                    document.document_id,
                    document.version,
                    document.title,
                    document.topic,
                    document.doc_type,
                    document.owner_org,
                    json.dumps(document.audience_orgs, ensure_ascii=False),
                    document.audience_type,
                    document.classification,
                    json.dumps(document.allowed_contract_types, ensure_ascii=False),
                    document.status,
                    document.effective_from.isoformat(),
                    _iso(document.effective_to),
                    document.override_mode,
                    document.supersedes,
                    document.supplement_target,
                    document.required_role,
                    document.content,
                    document.created_at.isoformat(),
                    _iso(document.published_at),
                )
                for document in corpus.documents
            ],
        )
        chunk_rows = []
        for document in corpus.documents:
            for position, text in enumerate(document.chunks):
                chunk_rows.append((document.version_id, position, text))
        connection.executemany(
            "INSERT INTO chunks (version_id, position, text) VALUES (?, ?, ?)",
            chunk_rows,
        )
        connection.commit()
    finally:
        connection.close()
    return corpus


def load_corpus(path: Path) -> Corpus:
    connection = connect(path)
    try:
        orgs = {
            row["id"]: Org(row["id"], row["parent_id"], row["name"], row["kind"])
            for row in connection.execute("SELECT * FROM orgs")
        }
        role_rows = list(connection.execute("SELECT * FROM role_assignments"))
        users = {}
        for row in connection.execute("SELECT * FROM users"):
            roles = tuple(
                RoleAssignment(item["role"], item["scope"])
                for item in role_rows
                if item["user_id"] == row["id"]
            )
            users[row["id"]] = User(
                row["id"],
                row["name"],
                row["org_id"],
                row["employment_type"],
                row["clearance"],
                roles,
            )
        documents = []
        for row in connection.execute("SELECT * FROM document_versions ORDER BY document_id, version"):
            documents.append(
                Document(
                    document_id=row["document_id"],
                    version_id=row["version_id"],
                    version=row["version"],
                    title=row["title"],
                    topic=row["topic"],
                    doc_type=row["doc_type"],
                    owner_org=row["owner_org"],
                    audience_orgs=tuple(json.loads(row["audience_orgs"])),
                    audience_type=row["audience_type"],
                    classification=row["classification"],
                    allowed_contract_types=tuple(json.loads(row["allowed_contract_types"])),
                    status=row["status"],
                    effective_from=date.fromisoformat(row["effective_from"]),
                    effective_to=date.fromisoformat(row["effective_to"]) if row["effective_to"] else None,
                    override_mode=row["override_mode"],
                    supersedes=row["supersedes"],
                    supplement_target=row["supplement_target"],
                    required_role=row["required_role"],
                    content=row["content"],
                    created_at=date.fromisoformat(row["created_at"]),
                    published_at=date.fromisoformat(row["published_at"]) if row["published_at"] else None,
                    match_phrases=tuple(json.loads(row["match_phrases"] or "[]")),
                )
            )
        exceptions = [
            AclException(
                user_id=row["user_id"],
                document_id=row["document_id"],
                version=row["version"],
                effect=row["effect"],
                reason=row["reason"],
                valid_from=date.fromisoformat(row["valid_from"]),
                valid_to=date.fromisoformat(row["valid_to"]) if row["valid_to"] else None,
            )
            for row in connection.execute("SELECT * FROM acl_exceptions")
        ]
        return Corpus(orgs=orgs, users=users, documents=tuple(documents), exceptions=exceptions)
    finally:
        connection.close()


def write_audit(
    path: Path,
    *,
    user_id: str,
    question: str,
    as_of: date,
    topic: str | None,
    outcome: str,
    winner_document_id: str | None,
    winner_version: int | None,
    answer: str,
    llm_used: bool,
    detail: dict,
) -> None:
    connection = connect(path)
    try:
        connection.executescript(SCHEMA)
        connection.execute(
            """
            INSERT INTO audit_log (
                created_at, user_id, question, as_of, topic, outcome,
                winner_document_id, winner_version, answer, llm_used, detail_json
            ) VALUES (datetime('now'), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                question,
                as_of.isoformat(),
                topic,
                outcome,
                winner_document_id,
                winner_version,
                answer,
                int(llm_used),
                json.dumps(detail, ensure_ascii=False),
            ),
        )
        connection.commit()
    finally:
        connection.close()
