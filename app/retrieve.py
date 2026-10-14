from __future__ import annotations

import re
from datetime import date

from app.models import Document, User
from app.policy import CURRENT_STATUSES, Decision, PolicyEngine

STOPWORDS = {
    "của", "tôi", "cho", "và", "là", "các", "một", "được", "trong", "với",
    "này", "thế", "nào", "như", "không", "theo", "về", "khi", "để", "hay",
    "hoặc", "những", "đang", "bao", "nhiêu", "thì", "có",
}


def tokens(text: str) -> list[str]:
    return [token for token in re.findall(r"\w+", text.casefold(), flags=re.UNICODE) if len(token) > 1]


def query_terms(text: str) -> list[str]:
    return [token for token in tokens(text) if token not in STOPWORDS]


def readable_effective(engine: PolicyEngine, user: User, on: date) -> list[Document]:
    selected = []
    for document in engine.corpus.documents:
        access = engine.can_read(user, document, "read", on)
        if not access.allowed or document.status not in CURRENT_STATUSES:
            continue
        if document.effective_from > on:
            continue
        if document.effective_to is not None and document.effective_to < on:
            continue
        selected.append(document)
    return selected


def passages_for_question(
    engine: PolicyEngine,
    user: User,
    question: str,
    on: date,
    limit: int = 4,
) -> list[tuple[Document, str]]:
    terms = query_terms(question)
    if not terms:
        return []
    scored: list[tuple[int, Document, str]] = []
    for document in readable_effective(engine, user, on):
        folded_title = document.title.casefold()
        title_hits = [term for term in terms if term in folded_title]
        for chunk in document.chunks:
            folded = chunk.casefold()
            hits = {term for term in terms if term in folded or term in folded_title}
            strong = len(hits) >= 2 or any(len(term) >= 5 for term in hits)
            if hits and strong:
                scored.append((len(hits) + len(title_hits), document, chunk))
    scored.sort(key=lambda item: item[0], reverse=True)
    selected: list[tuple[Document, str]] = []
    seen: set[str] = set()
    for _score, document, chunk in scored:
        if document.version_id in seen:
            continue
        seen.add(document.version_id)
        selected.append((document, document.statement if document.statement else chunk))
        if len(selected) >= limit:
            break
    return selected


def keyword_search(
    engine: PolicyEngine,
    user: User,
    question: str,
    on: date,
    topic: str,
) -> list[tuple[Document, str, int]]:
    terms = tokens(question)
    hits: list[tuple[Document, str, int]] = []
    for document in engine.corpus.documents:
        if document.topic != topic:
            continue
        access = engine.can_read(user, document, "search", on)
        if not access.allowed:
            continue
        for chunk in document.chunks:
            score = sum(1 for term in terms if term in chunk.casefold())
            if score:
                hits.append((document, chunk, score))
    hits.sort(key=lambda item: item[2], reverse=True)
    return hits


def chunks_for_answer(
    engine: PolicyEngine,
    user: User,
    question: str,
    on: date,
    decision: Decision,
) -> list[str]:
    if decision.outcome != "answered" or decision.winner is None:
        return []
    allowed = {decision.winner.key, *[document.key for document in decision.supplements]}
    selected: list[str] = []
    for document, chunk, _score in keyword_search(engine, user, question, on, decision.winner.topic):
        if document.key not in allowed or chunk in selected:
            continue
        selected.append(chunk)
    for document in [decision.winner, *decision.supplements]:
        if document.statement not in selected:
            selected.insert(0, document.statement)
    return selected
