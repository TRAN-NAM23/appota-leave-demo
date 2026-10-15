from __future__ import annotations

import re
from datetime import date

from app.catalog import TOPIC_LABELS
from app.db import write_audit
from app.embed import embed_texts, ensure_statement_embeddings
from app.llm import complete
from app.models import Document, User
from app.policy import Decision, PolicyEngine
from app.retrieve import chunks_for_answer, passages_for_question, query_terms, rank_statements, readable_effective


REASON_LABELS = {
    "not_published": "Chưa ban hành",
    "not_yet_effective": "Chưa tới ngày hiệu lực",
    "expired": "Hết hiệu lực",
    "not_applicable": "Không áp dụng cho loại hợp đồng hoặc đơn vị",
    "less_specific": "Cấp rộng hơn, đã bị thay",
    "out_of_audience": "Ngoài phạm vi đơn vị",
    "insufficient_clearance": "Không đủ mức tiếp cận",
    "draft_forbidden": "Bản nháp ngoài quyền",
    "role_forbidden": "Role không được đọc",
    "denied": "Bị cấm bởi ngoại lệ",
    "not_yet_published": "Chưa tới ngày ban hành",
    "action_forbidden": "Hành động không được phép",
    "superseded": "Đã có phiên bản mới hơn đang hiệu lực",
    "unmatched_supplement": "Không bổ sung cho bản đang áp dụng",
}

TOPIC_RULES = (
    (("ốm",), "leave.sick"),
    (("tối thiểu", "theo luật"), "leave.minimum"),
    (("thưởng",), "pay.bonus"),
    (("lương chi tiết", "bảng lương chi tiết", "giám đốc"), "pay.restricted"),
    (("phụ cấp",), "pay.benefit"),
    (("chốt bảng lương", "tính lương"), "pay.process"),
    (("trả lương", "lịch lương", "ngày lương"), "pay.schedule"),
    (("từ xa",), "work.remote"),
    (("nghỉ phép", "phép năm"), "leave.annual"),
)

DOC_ID_PATTERN = re.compile(r"\b[A-Z]+-[A-Z]+-\d+\b")
ROLE_LABELS = {
    "employee": "nhân viên",
    "intern": "thực tập",
    "manager": "quản lý",
    "policy_admin": "quản trị chính sách",
    "contractor": "cộng tác viên",
}
CONTRACT_LABELS = {
    "full_time": "chính thức",
    "intern": "thực tập",
    "contractor": "cộng tác viên",
}


def detect_topic(
    question: str,
    extra: tuple[tuple[tuple[str, ...], str], ...] = (),
) -> str | None:
    normalized = question.casefold()
    for phrases, topic in TOPIC_RULES:
        if any(phrase in normalized for phrase in phrases):
            return topic
    for phrases, topic in extra:
        if any(phrase.casefold() in normalized for phrase in phrases):
            return topic
    return None


def citations_ok(text: str, allowed_ids: set[str]) -> bool:
    found = set(DOC_ID_PATTERN.findall(text))
    return bool(found) and found <= allowed_ids


def build_context(chunks: list[tuple[Document, str]]) -> str:
    blocks = []
    for document, chunk in chunks:
        blocks.append(f"Tài liệu {document.document_id} phiên bản {document.version}:\n{chunk}")
    return "\n\n".join(blocks)


class AnswerService:
    def __init__(self, engine: PolicyEngine, db_path=None):
        self.engine = engine
        self.db_path = db_path

    def ask(self, user: User, question: str, on: date) -> dict:
        extra = tuple(
            (document.match_phrases, document.topic)
            for document in self.engine.corpus.documents
            if document.match_phrases
        )
        topic = detect_topic(question, extra)
        decision = Decision(outcome="unknown_topic")
        chunks: list[str] = []
        cited_chunks: list[tuple[Document, str]] = []
        llm_used = False
        steps = [self._identity_step(user)]
        passages: list[dict] = []
        if topic is None:
            answer = "Bản demo này trả lời các câu hỏi về nghỉ phép, làm việc từ xa, lương và thưởng."
            steps.extend([
                {
                    "tool": "classify",
                    "title": "Chọn công cụ",
                    "detail": "Câu hỏi không thuộc chủ đề có sẵn, nên tab này không truy xuất tài liệu.",
                },
                {
                    "tool": "compose",
                    "title": "Viết câu trả lời",
                    "detail": "Không gọi LLM vì chưa xác định được chủ đề.",
                },
            ])
        else:
            decision = self.engine.resolve_effective(user, topic, on)
            steps.append({
                "tool": "classify",
                "title": "Chọn công cụ",
                "detail": f"Câu thuộc {TOPIC_LABELS.get(topic, topic)}. Policy chọn bản hiệu lực, RAG chỉ lấy đoạn trong tập đó.",
            })
            steps.append(self._policy_step(decision))
            passages = self._policy_passages(question, decision)
            steps.append(self._retrieve_step(passages))
            chunks = chunks_for_answer(self.engine, user, question, on, decision)
            cited_chunks = self._tag_chunks(decision, chunks)
            answer, llm_used = self._compose(question, decision, cited_chunks)
            steps.append(self._compose_step(decision, llm_used))
        payload = self._public(user, question, on, topic, decision, answer, llm_used, steps, passages)
        if self.db_path is not None:
            write_audit(
                self.db_path,
                user_id=user.id,
                question=question,
                as_of=on,
                topic=topic,
                outcome=payload["outcome"],
                winner_document_id=None if decision.winner is None else decision.winner.document_id,
                winner_version=None if decision.winner is None else decision.winner.version,
                answer=answer,
                llm_used=llm_used,
                detail={
                    "hidden": [
                        {"document_id": document.document_id, "version": document.version, "reason": reason}
                        for document, reason in decision.hidden_rejected
                    ],
                    "visible": [
                        {"document_id": document.document_id, "version": document.version, "reason": reason}
                        for document, reason in decision.visible_rejected
                    ],
                    "steps": [step["tool"] for step in steps],
                    "passages": [item["document_id"] for item in passages],
                },
            )
        return payload

    def chat(self, user: User, question: str, on: date) -> dict:
        extra = tuple(
            (document.match_phrases, document.topic)
            for document in self.engine.corpus.documents
            if document.match_phrases
        )
        topic = detect_topic(question, extra)
        if topic:
            payload = self.ask(user, question, on)
            sources = [
                item
                for item in [payload["winner"], *payload["supplements"]]
                if item is not None
            ]
            if payload["outcome"] == "conflict":
                decision = self.engine.resolve_effective(user, topic, on)
                sources = [self._source(document) for document in decision.conflicts]
            return {
                "mode": "policy",
                "outcome": payload["outcome"],
                "answer": payload["answer"],
                "reason": payload["reason"],
                "sources": sources,
                "persona": payload["persona"],
                "as_of": payload["as_of"],
                "question": question,
                "llm_used": payload["llm_used"],
                "steps": payload["steps"],
                "passages": payload["passages"],
            }

        allowed = readable_effective(self.engine, user, on)
        vectors, query_vector = self._embedding_space(allowed, question)
        method, ranked = rank_statements(allowed, question, vectors, query_vector, floor=0.28)
        if method == "embedding":
            cited = [(document, document.statement) for _score, _item_method, document in ranked]
            passage_rows = [
                self._passage(document, score, item_method, True)
                for score, item_method, document in ranked
            ]
        else:
            cited = passages_for_question(self.engine, user, question, on)
            passage_rows = [
                self._passage(
                    document,
                    float(sum(1 for term in (query_terms(question) or []) if term in f"{document.title} {chunk}".casefold())),
                    "keyword",
                    True,
                )
                for document, chunk in cited
            ]
        steps = [
            self._identity_step(user),
            {
                "tool": "classify",
                "title": "Chọn công cụ",
                "detail": "Câu không thuộc chủ đề có sẵn. Agent tìm ngữ nghĩa trong tài liệu được xem và còn hiệu lực.",
            },
            self._retrieve_step(passage_rows),
        ]
        if not cited:
            answer = (
                "Chưa thấy căn cứ trong các tài liệu bạn được phép xem và còn hiệu lực. "
                "Hãy hỏi theo đúng đơn vị của bạn hoặc bổ sung tài liệu."
            )
            reason = "Không có đoạn tài liệu được phép dùng cho câu hỏi này."
            outcome = "no_policy"
            llm_used = False
            steps.append({
                "tool": "compose",
                "title": "Viết câu trả lời",
                "detail": "Không gọi LLM vì không có đoạn được phép.",
            })
        else:
            fallback = self._passages_fallback(cited)
            generated = complete(question, build_context(cited))
            allowed_ids = {document.document_id for document, _chunk in cited}
            if generated and citations_ok(generated, allowed_ids):
                answer = generated
                llm_used = True
            else:
                answer = fallback
                llm_used = False
            reason = "Các đoạn này thuộc tài liệu bạn được xem và còn hiệu lực vào ngày hỏi."
            outcome = "answered"
            steps.append({
                "tool": "compose",
                "title": "Viết câu trả lời",
                "detail": "LLM diễn đạt các đoạn RAG đã lấy." if llm_used else "Dùng câu trích từ các đoạn RAG đã lấy.",
            })
        payload = {
            "mode": "passages",
            "outcome": outcome,
            "answer": answer,
            "reason": reason,
            "sources": [self._source(document) for document, _chunk in cited],
            "persona": self._persona(user),
            "as_of": on.isoformat(),
            "question": question,
            "llm_used": llm_used,
            "steps": steps,
            "passages": passage_rows,
        }
        if self.db_path is not None:
            first = None if not cited else cited[0][0]
            write_audit(
                self.db_path,
                user_id=user.id,
                question=question,
                as_of=on,
                topic=None,
                outcome=outcome,
                winner_document_id=None if first is None else first.document_id,
                winner_version=None if first is None else first.version,
                answer=answer,
                llm_used=llm_used,
                detail={
                    "mode": "passages",
                    "method": method,
                    "sources": [document.document_id for document, _chunk in cited],
                    "steps": [step["tool"] for step in steps],
                },
            )
        return payload

    def _identity_step(self, user: User) -> dict:
        roles = ", ".join(ROLE_LABELS.get(role.role, role.role) for role in user.roles)
        contract = CONTRACT_LABELS.get(user.employment_type, user.employment_type)
        return {
            "tool": "identity",
            "title": "Gắn danh tính",
            "detail": f"{user.name} · {self.engine.corpus.org_name(user.org)} · {roles} · {contract} · mức {user.clearance}.",
        }

    def _policy_step(self, decision: Decision) -> dict:
        hidden = len(decision.hidden_rejected)
        hidden_note = f" Đã loại {hidden} tài liệu ngoài quyền xem." if hidden else ""
        if decision.outcome == "answered" and decision.winner is not None:
            detail = f"Chọn {decision.winner.document_id} phiên bản {decision.winner.version}.{hidden_note}"
        elif decision.outcome == "conflict":
            detail = f"Các bản cùng cấp đang xung đột, không tự chọn.{hidden_note}"
        else:
            detail = f"Không có tài liệu vừa được xem, vừa áp dụng, vừa còn hiệu lực.{hidden_note}"
        return {"tool": "policy", "title": "Policy Engine", "detail": detail}

    def _retrieve_step(self, passages: list[dict]) -> dict:
        from app.embed import LAST_ERROR

        if not passages:
            detail = "Không có đoạn được phép để truy xuất."
        elif passages[0]["method"] == "embedding":
            detail = f"So embedding và lấy {len(passages)} đoạn gần nhất trong tập đã được phép."
        elif LAST_ERROR == "http 429":
            detail = f"Embedding đang bị giới hạn lượt gọi, nên xếp {len(passages)} đoạn theo từ khóa."
        elif LAST_ERROR and LAST_ERROR != "no_key":
            detail = f"Embedding chưa dùng được, nên xếp {len(passages)} đoạn theo từ khóa."
        else:
            detail = f"Chưa có vector, xếp {len(passages)} đoạn theo từ khóa trong tập đã được phép."
        return {"tool": "retrieve", "title": "RAG", "detail": detail}

    def _compose_step(self, decision: Decision, llm_used: bool) -> dict:
        if decision.outcome != "answered":
            detail = "Không gọi LLM vì chưa có một bản kết luận."
        elif llm_used:
            detail = "LLM chỉ diễn đạt các đoạn đã chọn."
        else:
            detail = "Dùng câu trích từ đoạn đã chọn."
        return {"tool": "compose", "title": "Viết câu trả lời", "detail": detail}

    def _policy_passages(self, question: str, decision: Decision) -> list[dict]:
        used = [document for document in [decision.winner, *decision.supplements] if document is not None]
        visible = [*used, *decision.overridden, *decision.conflicts]
        if not visible:
            return []
        vectors, query_vector = self._embedding_space(visible, question)
        _method, ranked = rank_statements(visible, question, vectors, query_vector)
        used_ids = {document.version_id for document in used}
        used_rows = []
        other_rows = []
        for score, method, document in ranked:
            row = self._passage(document, score, method, document.version_id in used_ids)
            if document.version_id in used_ids:
                used_rows.append(row)
            elif score > 0:
                other_rows.append(row)
        return (used_rows + other_rows)[:4]

    def _embedding_space(self, documents: list[Document], question: str):
        if not documents or self.db_path is None:
            return {}, None
        vectors = ensure_statement_embeddings(self.db_path, documents)
        if not vectors or any((document.version_id, 0) not in vectors for document in documents):
            return {}, None
        query = embed_texts([question])
        if not query:
            return {}, None
        return vectors, query[0]

    def _passage(self, document: Document, score: float, method: str, used: bool) -> dict:
        excerpt = " ".join(document.statement.split())
        if len(excerpt) > 160:
            excerpt = excerpt[:157] + "..."
        shown = round(score, 2) if method == "embedding" else int(score)
        return {
            "document_id": document.document_id,
            "version": document.version,
            "title": document.title,
            "excerpt": excerpt,
            "score": shown,
            "method": method,
            "used": used,
        }

    def _passages_fallback(self, cited: list[tuple[Document, str]]) -> str:
        lines = ["Trong các tài liệu bạn được xem, có những đoạn sau.", ""]
        for document, chunk in cited:
            lines.append(f"- {self._cite(document)}: {chunk}")
        return "\n".join(lines)

    def _compose(self, question: str, decision: Decision, cited_chunks: list[tuple[Document, str]]) -> tuple[str, bool]:
        fallback = self._fallback(decision)
        if decision.outcome != "answered":
            return fallback, False
        context = build_context(cited_chunks)
        generated = complete(question, context)
        allowed_ids = {document.document_id for document, _chunk in cited_chunks}
        if generated and citations_ok(generated, allowed_ids):
            return generated, True
        return fallback, False

    def _tag_chunks(self, decision: Decision, chunks: list[str]) -> list[tuple[Document, str]]:
        owned: list[tuple[Document, str]] = []
        documents = [decision.winner, *decision.supplements] if decision.winner else []
        for chunk in chunks:
            owner = next((document for document in documents if chunk in document.chunks), None)
            if owner is not None:
                owned.append((owner, chunk))
        return owned

    def _fallback(self, decision: Decision) -> str:
        if decision.outcome == "no_policy":
            return (
                "Chưa có quy định đang hiệu lực cho đơn vị và loại hợp đồng của bạn. "
                "Hãy hỏi Phòng Nhân sự của đơn vị."
            )
        if decision.outcome == "conflict":
            lines = ["Chưa thể kết luận vì có nhiều quy định cùng cấp đang cùng hiệu lực.", ""]
            for document in decision.conflicts:
                lines.append(f"- {self._cite(document)}: {document.statement}")
            lines.extend(["", "Cần chủ nội dung xử lý trước khi áp dụng."])
            return "\n".join(lines)
        if decision.winner is None:
            return "Chưa thể kết luận."
        lines = [decision.winner.statement, "", f"Nguồn: {self._cite(decision.winner)}."]
        for document in decision.supplements:
            lines.extend(["", f"Bổ sung: {document.statement}", f"Nguồn: {self._cite(document)}."])
        if decision.overridden:
            replaced = ", ".join(document.key for document in decision.overridden)
            lines.extend(["", f"Đã thay quy định cấp rộng hơn: {replaced}. Nội dung cấp rộng hơn không được dùng."])
        return "\n".join(lines)

    def _cite(self, document: Document) -> str:
        end = ""
        if document.effective_to is not None:
            end = f" đến {document.effective_to.strftime('%d/%m/%Y')}"
        return (
            f"{document.document_id} phiên bản {document.version}, "
            f"hiệu lực từ {document.effective_from.strftime('%d/%m/%Y')}{end}, "
            f"do {self.engine.corpus.org_name(document.owner_org)} ban hành"
        )

    def _public(
        self,
        user: User,
        question: str,
        on: date,
        topic: str | None,
        decision: Decision,
        answer: str,
        llm_used: bool,
        steps: list[dict] | None = None,
        passages: list[dict] | None = None,
    ) -> dict:
        return {
            "outcome": decision.outcome if topic else "unknown_topic",
            "topic": topic,
            "answer": answer,
            "winner": None if decision.winner is None else self._source(decision.winner),
            "supplements": [self._source(document) for document in decision.supplements],
            "overridden": [
                {**self._card(document), "reason": REASON_LABELS["less_specific"]}
                for document in decision.overridden
            ],
            "visible_rejected": [
                {**self._card(document), "reason": REASON_LABELS.get(reason, reason)}
                for document, reason in decision.visible_rejected
            ],
            "reason": self._winner_reason(decision),
            "persona": self._persona(user),
            "as_of": on.isoformat(),
            "question": question,
            "llm_used": llm_used,
            "steps": steps or [],
            "passages": passages or [],
        }

    def _winner_reason(self, decision: Decision) -> str:
        if decision.outcome == "conflict":
            return "Hai quy định cùng cấp đang cùng hiệu lực, nên hệ thống không tự chọn."
        if decision.outcome == "no_policy":
            return "Không có tài liệu vừa được phép xem, vừa áp dụng, vừa còn hiệu lực."
        if decision.outcome != "answered":
            return "Câu hỏi chưa thuộc chủ đề mà bản demo đang hỗ trợ."
        if decision.supplements:
            if decision.winner is not None and decision.winner.override_mode == "mandatory":
                return "Quy định cấp trên là mức bắt buộc. Bản cấp dưới chỉ được bổ sung."
            return "Bản đang áp dụng được giữ. Bản bổ sung chỉ thêm điều khoản."
        if decision.overridden:
            return "Bản của cấp gần người hỏi hơn đang có hiệu lực và thay bản cấp rộng hơn."
        return "Đây là bản đã ban hành, còn hiệu lực và áp dụng cho người hỏi."

    def _source(self, document: Document) -> dict:
        card = self._card(document)
        card["statement"] = document.statement
        card["owner"] = self.engine.corpus.org_name(document.owner_org)
        card["effective_from"] = document.effective_from.isoformat()
        card["effective_to"] = document.effective_to.isoformat() if document.effective_to else None
        return card

    def _card(self, document: Document) -> dict:
        return {
            "document_id": document.document_id,
            "version": document.version,
            "title": document.title,
        }

    def _persona(self, user: User) -> dict:
        chain = " / ".join(org.name for org in self.engine.corpus.ancestors(user.org))
        return {
            "id": user.id,
            "name": user.name,
            "org": self.engine.corpus.org_name(user.org),
            "org_path": chain,
            "employment_type": user.employment_type,
            "clearance": user.clearance,
            "roles": [role.role for role in user.roles],
        }
