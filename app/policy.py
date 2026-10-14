from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.models import CLEARANCE_RANK, Corpus, Document, User


READ_ROLES = {"employee", "intern", "manager", "policy_admin", "contractor"}
CURRENT_STATUSES = {"published", "superseded"}


@dataclass(frozen=True)
class Access:
    allowed: bool
    reason: str


@dataclass
class Decision:
    outcome: str
    winner: Document | None = None
    supplements: list[Document] = field(default_factory=list)
    overridden: list[Document] = field(default_factory=list)
    conflicts: list[Document] = field(default_factory=list)
    visible_rejected: list[tuple[Document, str]] = field(default_factory=list)
    hidden_rejected: list[tuple[Document, str]] = field(default_factory=list)


def scope_covers(scope: str, org_id: str) -> bool:
    return org_id == scope or org_id.startswith(scope + "/")


def audience_covers_org(document: Document, org_id: str) -> bool:
    if document.audience_type == "subtree":
        return any(org_id == audience or org_id.startswith(audience + "/") for audience in document.audience_orgs)
    return org_id in document.audience_orgs


def _has_role(user: User, role_name: str) -> bool:
    return any(role.role == role_name for role in user.roles)


def _exception_active(item, on: date) -> bool:
    if item.valid_from > on:
        return False
    return item.valid_to is None or on <= item.valid_to


def _matching_exceptions(corpus: Corpus, user: User, document: Document, on: date):
    return [
        item
        for item in corpus.exceptions
        if item.user_id == user.id
        and item.document_id == document.document_id
        and (item.version is None or item.version == document.version)
        and _exception_active(item, on)
    ]


class PolicyEngine:
    def __init__(self, corpus: Corpus):
        self.corpus = corpus

    def can_read(self, user: User, document: Document, action: str, on: date) -> Access:
        if action not in {"read", "search", "cite"}:
            return Access(False, "action_forbidden")
        if CLEARANCE_RANK[user.clearance] < CLEARANCE_RANK[document.classification]:
            return Access(False, "insufficient_clearance")

        matches = _matching_exceptions(self.corpus, user, document, on)
        if any(item.effect == "deny" for item in matches):
            return Access(False, "denied")

        published_like = document.status in CURRENT_STATUSES
        if document.status == "published" and document.published_at and document.published_at > on:
            return Access(False, "not_yet_published")

        explicit_allow = any(item.effect == "allow" for item in matches)
        if explicit_allow and published_like:
            return Access(True, "allowed_exception")

        if not self._audience_visible(user, document):
            return Access(False, "out_of_audience")
        if document.required_role and not _has_role(user, document.required_role):
            return Access(False, "role_forbidden")
        if not any(role.role in READ_ROLES for role in user.roles):
            return Access(False, "role_forbidden")
        if published_like:
            return Access(True, "allowed")
        if document.status in {"draft", "archived"} and self._admin_covers_owner(user, document):
            return Access(True, "allowed")
        if document.status == "draft":
            return Access(False, "draft_forbidden")
        return Access(False, "not_published")

    def applies(self, user: User, document: Document) -> bool:
        return (
            audience_covers_org(document, user.org)
            and user.employment_type in document.allowed_contract_types
        )

    def resolve_effective(self, user: User, topic: str, on: date) -> Decision:
        decision = Decision(outcome="no_policy")
        candidates: list[Document] = []
        for document in self.corpus.documents:
            if document.topic != topic:
                continue
            access = self.can_read(user, document, "read", on)
            if not access.allowed:
                decision.hidden_rejected.append((document, access.reason))
                continue
            if not self.applies(user, document):
                decision.visible_rejected.append((document, "not_applicable"))
                continue
            if document.status not in CURRENT_STATUSES:
                decision.visible_rejected.append((document, "not_published"))
                continue
            if document.effective_from > on:
                decision.visible_rejected.append((document, "not_yet_effective"))
                continue
            if document.effective_to is not None and document.effective_to < on:
                decision.visible_rejected.append((document, "expired"))
                continue
            candidates.append(document)

        if not candidates:
            return decision

        floors = [document for document in candidates if document.override_mode == "mandatory"]
        if floors:
            return self._resolve_mandatory(decision, floors, candidates)
        return self._resolve_deepest(decision, user, candidates)

    def _audience_visible(self, user: User, document: Document) -> bool:
        if audience_covers_org(document, user.org):
            return True
        return any(
            role.role in {"manager", "policy_admin"}
            and any(scope_covers(role.scope, audience) for audience in document.audience_orgs)
            for role in user.roles
        )

    def _admin_covers_owner(self, user: User, document: Document) -> bool:
        return any(
            role.role == "policy_admin" and scope_covers(role.scope, document.owner_org)
            for role in user.roles
        )

    def _resolve_mandatory(
        self,
        decision: Decision,
        floors: list[Document],
        candidates: list[Document],
    ) -> Decision:
        floor_group = self._deepest(floors)
        if len(floor_group) > 1:
            decision.outcome = "conflict"
            decision.conflicts = floor_group
            return decision
        floor = floor_group[0]
        blocked: list[Document] = []
        for document in candidates:
            if document == floor:
                continue
            supplements_floor = (
                document.override_mode == "supplement" and document.supplement_target == floor.document_id
            )
            if supplements_floor:
                decision.supplements.append(document)
            else:
                blocked.append(document)
        if blocked:
            decision.outcome = "conflict"
            decision.conflicts = [floor, *blocked]
            return decision
        decision.outcome = "answered"
        decision.winner = floor
        return decision

    def _resolve_deepest(self, decision: Decision, user: User, candidates: list[Document]) -> Decision:
        top = self._deepest(candidates, user)
        if len(top) > 1:
            decision.outcome = "conflict"
            decision.conflicts = top
            return decision
        decision.outcome = "answered"
        decision.winner = top[0]
        decision.overridden = [document for document in candidates if document != top[0]]
        return decision

    def _deepest(self, documents: list[Document], user: User | None = None) -> list[Document]:
        scored = [(self._specificity(document, user), document) for document in documents]
        depth = max(score for score, _ in scored)
        return [document for score, document in scored if score == depth]

    def _specificity(self, document: Document, user: User | None) -> int:
        org_id = user.org if user else document.audience_orgs[0]
        matching = [
            audience
            for audience in document.audience_orgs
            if org_id == audience or org_id.startswith(audience + "/") or audience == org_id
        ]
        if not matching:
            matching = list(document.audience_orgs)
        return max(len(audience.split("/")) for audience in matching)
