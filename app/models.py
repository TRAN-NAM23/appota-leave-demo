from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


CLEARANCE_RANK = {"internal": 1, "confidential": 2, "restricted": 3}


@dataclass(frozen=True)
class Org:
    id: str
    parent_id: str | None
    name: str
    kind: str


@dataclass(frozen=True)
class RoleAssignment:
    role: str
    scope: str


@dataclass(frozen=True)
class User:
    id: str
    name: str
    org: str
    employment_type: str
    clearance: str
    roles: tuple[RoleAssignment, ...]


@dataclass(frozen=True)
class AclException:
    user_id: str
    document_id: str
    version: int | None
    effect: str
    reason: str
    valid_from: date
    valid_to: date | None


@dataclass(frozen=True)
class Document:
    document_id: str
    version_id: str
    version: int
    title: str
    topic: str
    doc_type: str
    owner_org: str
    audience_orgs: tuple[str, ...]
    audience_type: str
    classification: str
    allowed_contract_types: tuple[str, ...]
    status: str
    effective_from: date
    effective_to: date | None
    override_mode: str
    supersedes: int | None
    supplement_target: str | None
    required_role: str | None
    content: str
    created_at: date
    published_at: date | None
    match_phrases: tuple[str, ...] = ()

    @property
    def key(self) -> str:
        return f"{self.document_id} v{self.version}"

    @property
    def statement(self) -> str:
        return self.chunks[0]

    @property
    def chunks(self) -> tuple[str, ...]:
        return tuple(part.strip() for part in self.content.split("\n\n") if part.strip())


@dataclass
class Corpus:
    orgs: dict[str, Org]
    users: dict[str, User]
    documents: tuple[Document, ...]
    exceptions: list[AclException] = field(default_factory=list)

    def org_name(self, org_id: str) -> str:
        return self.orgs[org_id].name

    def ancestors(self, org_id: str) -> list[Org]:
        chain: list[Org] = []
        current = org_id
        while current:
            org = self.orgs[current]
            chain.append(org)
            current = org.parent_id
        chain.reverse()
        return chain

    def children(self, org_id: str) -> list[Org]:
        return [org for org in self.orgs.values() if org.parent_id == org_id]

    def siblings(self, org_id: str) -> list[Org]:
        parent_id = self.orgs[org_id].parent_id
        return [
            org
            for org in self.orgs.values()
            if org.parent_id == parent_id and org.id != org_id
        ]
