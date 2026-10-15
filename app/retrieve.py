from __future__ import annotations

import re
from datetime import date

from app.embed import cosine
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
        if not engine.applies(user, document):
            continue
        if document.effective_from > on:
            continue
        if document.effective_to is not None and document.effective_to < on:
            continue
        selected.append(document)
    return selected


def rank_statements(
    documents: list[Document],
    question: str,
    vectors: dict[tuple[str, int], list[float]],
    query_vector: list[float] | None,
    limit: int = 4,
    floor: float = 0.0,
) -> tuple[str, list[tuple[float, str, Document]]]:
    scored: list[tuple[float, str, Document]] = []
    terms = query_terms(question) or tokens(question)
    for document in documents:
        vector = vectors.get((document.version_id, 0))
        if query_vector is not None and vector is not None:
            score = cosine(query_vector, vector)
            method = "embedding"
            if score < floor:
                continue
        else:
            text = f"{document.title} {document.statement}".casefold()
            score = float(sum(1 for term in terms if term in text))
            method = "keyword"
        scored.append((score, method, document))
    if query_vector is not None and not any(method == "embedding" for _score, method, _document in scored):
        return rank_statements(documents, question, {}, None, limit, 0.0)
    scored.sort(key=lambda item: item[0], reverse=True)
    method = scored[0][1] if scored else ("embedding" if query_vector is not None else "keyword")
    return method, scored[:limit]


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
    del engine, user, question, on
    if decision.outcome != "answered" or decision.winner is None:
        return []
    selected = [decision.winner.statement]
    for document in decision.supplements:
        if document.statement not in selected:
            selected.append(document.statement)
    return selected
