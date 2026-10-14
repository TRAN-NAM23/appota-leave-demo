from __future__ import annotations

import re
from datetime import date

from app.db import insert_document
from app.models import CLEARANCE_RANK, Corpus, Document
from app.policy import READ_ROLES


DOCUMENT_ID_PATTERN = re.compile(r"^[A-Z]+-[A-Z]+-\d+$")
TOPIC_PATTERN = re.compile(r"^[a-z][a-z0-9_.]{0,40}$")
TOPIC_LABELS = {
    "leave.annual": "Nghỉ phép năm",
    "leave.minimum": "Nghỉ phép tối thiểu",
    "leave.sick": "Nghỉ ốm",
    "work.remote": "Làm việc từ xa",
    "pay.schedule": "Lịch trả lương",
    "pay.process": "Tính lương",
    "pay.benefit": "Phụ cấp",
    "pay.restricted": "Lương mật",
    "pay.bonus": "Thưởng",
}
AUDIENCE_TYPES = ("subtree", "exact", "explicit")
STATUSES = ("draft", "published", "superseded", "archived")
OVERRIDE_MODES = ("default", "mandatory", "supplement")
CONTRACTS = ("full_time", "intern", "contractor")
DOC_TYPES = ("quy_dinh", "quy_trinh")


class CatalogError(ValueError):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def catalog_options(corpus: Corpus) -> dict:
    return {
        "orgs": [
            {
                "id": org.id,
                "label": " / ".join(item.name for item in corpus.ancestors(org.id)),
            }
            for org in _orgs_in_tree_order(corpus)
        ],
        "topics": [{"id": topic, "label": label} for topic, label in TOPIC_LABELS.items()],
        "classifications": list(CLEARANCE_RANK),
        "statuses": list(STATUSES),
        "audience_types": list(AUDIENCE_TYPES),
        "override_modes": list(OVERRIDE_MODES),
        "contracts": list(CONTRACTS),
        "roles": sorted(READ_ROLES),
        "doc_types": list(DOC_TYPES),
    }


def document_detail(corpus: Corpus, version_id: str) -> dict | None:
    document = next((item for item in corpus.documents if item.version_id == version_id), None)
    if document is None:
        return None
    owner = corpus.orgs.get(document.owner_org)
    return {
        "version_id": document.version_id,
        "document_id": document.document_id,
        "version": document.version,
        "title": document.title,
        "topic": document.topic,
        "status": document.status,
        "owner_org": document.owner_org,
        "owner_name": owner.name if owner else document.owner_org,
        "classification": document.classification,
        "effective_from": document.effective_from.isoformat(),
        "effective_to": document.effective_to.isoformat() if document.effective_to else None,
        "content": document.content,
    }


KIND_LABELS = {
    "group": "Tập đoàn",
    "company": "Công ty",
    "department": "Phòng",
    "team": "Nhóm",
}
AUDIENCE_LABELS = {
    "subtree": "gồm cả cấp dưới",
    "exact": "đúng đơn vị này",
    "explicit": "đúng các đơn vị được chọn",
}


def org_tree(corpus: Corpus) -> dict:
    by_audience: dict[str, list[Document]] = {org_id: [] for org_id in corpus.orgs}
    for document in corpus.documents:
        for audience in document.audience_orgs:
            if audience in by_audience:
                by_audience[audience].append(document)

    people: dict[str, list] = {org_id: [] for org_id in corpus.orgs}
    for user in corpus.users.values():
        people.setdefault(user.org, []).append(user)

    def node(org) -> dict:
        documents = sorted(by_audience.get(org.id, []), key=lambda item: (item.document_id, item.version))
        members = sorted(people.get(org.id, []), key=lambda item: item.name)
        children = [node(child) for child in sorted(corpus.children(org.id), key=lambda item: item.id)]
        return {
            "id": org.id,
            "name": org.name,
            "kind": org.kind,
            "kind_label": KIND_LABELS.get(org.kind, org.kind),
            "documents": [_tree_document(corpus, document) for document in documents],
            "people": [
                {"id": user.id, "name": user.name, "employment_type": user.employment_type}
                for user in members
            ],
            "children": children,
        }

    roots = sorted(
        (org for org in corpus.orgs.values() if org.parent_id is None),
        key=lambda item: item.id,
    )
    levels = []
    for kind, label in KIND_LABELS.items():
        covered = {
            document.version_id
            for document in corpus.documents
            if _audience_kind(corpus, document, kind)
        }
        levels.append(
            {
                "kind": kind,
                "label": label,
                "units": sum(org.kind == kind for org in corpus.orgs.values()),
                "documents": len(covered),
            }
        )
    return {"levels": levels, "tree": [node(org) for org in roots]}


def _audience_kind(corpus: Corpus, document: Document, kind: str) -> bool:
    for audience in document.audience_orgs:
        org = corpus.orgs.get(audience)
        if org is not None and org.kind == kind:
            return True
    return False


def _tree_document(corpus: Corpus, document: Document) -> dict:
    owner = corpus.orgs.get(document.owner_org)
    return {
        "version_id": document.version_id,
        "document_id": document.document_id,
        "version": document.version,
        "title": document.title,
        "status": document.status,
        "owner_org": document.owner_org,
        "owner_name": owner.name if owner else document.owner_org,
        "audience_type": document.audience_type,
        "audience_label": AUDIENCE_LABELS.get(document.audience_type, document.audience_type),
    }


def document_summaries(corpus: Corpus) -> list[dict]:
    return [
        {
            "version_id": document.version_id,
            "document_id": document.document_id,
            "version": document.version,
            "title": document.title,
            "topic": document.topic,
            "status": document.status,
            "owner_org": document.owner_org,
        }
        for document in corpus.documents
    ]


def save_document(path, corpus: Corpus, raw: dict) -> Document:
    document = _build_document(corpus, raw)
    insert_document(path, document)
    return document


def _orgs_in_tree_order(corpus: Corpus) -> list:
    ordered = []

    def walk(org_id: str) -> None:
        ordered.append(corpus.orgs[org_id])
        for child in sorted(corpus.children(org_id), key=lambda item: item.id):
            walk(child.id)

    walk("apx")
    return ordered


def _build_document(corpus: Corpus, raw: dict) -> Document:
    document_id = raw["document_id"].strip().upper()
    if DOCUMENT_ID_PATTERN.fullmatch(document_id) is None:
        raise CatalogError("Mã tài liệu phải có dạng APT-LV-099.")
    version = raw["version"]
    if any(
        item.document_id == document_id and item.version == version
        for item in corpus.documents
    ):
        raise CatalogError("Phiên bản này đã có trong cơ sở dữ liệu.", status=409)

    topic = raw["topic"].strip()
    if TOPIC_PATTERN.fullmatch(topic) is None:
        raise CatalogError("Chủ đề chỉ dùng chữ thường, số, dấu chấm hoặc gạch dưới.")
    phrases = _phrases(raw.get("match_phrases") or [])
    if topic not in TOPIC_LABELS and not phrases:
        raise CatalogError("Chủ đề mới cần ít nhất một cụm từ để nhận ra câu hỏi.")

    owner_org = raw["owner_org"]
    audience_orgs = list(dict.fromkeys(raw["audience_orgs"]))
    missing = [org_id for org_id in [owner_org, *audience_orgs] if org_id not in corpus.orgs]
    if missing:
        raise CatalogError("Đơn vị ban hành và phạm vi áp dụng phải nằm trong cây tổ chức.")
    if raw["audience_type"] not in AUDIENCE_TYPES:
        raise CatalogError("Kiểu phạm vi không hợp lệ.")
    if raw["classification"] not in CLEARANCE_RANK:
        raise CatalogError("Mức bảo mật không hợp lệ.")
    contracts = list(dict.fromkeys(raw["allowed_contract_types"]))
    if not contracts or any(item not in CONTRACTS for item in contracts):
        raise CatalogError("Loại hợp đồng không hợp lệ.")
    if raw["status"] not in STATUSES:
        raise CatalogError("Trạng thái tài liệu không hợp lệ.")
    if raw["override_mode"] not in OVERRIDE_MODES:
        raise CatalogError("Quy tắc ghi đè không hợp lệ.")
    if raw["doc_type"] not in DOC_TYPES:
        raise CatalogError("Loại tài liệu không hợp lệ.")

    effective_from = raw["effective_from"]
    effective_to = raw.get("effective_to")
    if effective_to is not None and effective_to < effective_from:
        raise CatalogError("Ngày hết hiệu lực phải sau ngày bắt đầu.")
    supersedes = raw.get("supersedes")
    if supersedes is not None and supersedes == version:
        raise CatalogError("Phiên bản không thể thay chính nó.")
    supplement_target = (raw.get("supplement_target") or "").strip() or None
    if raw["override_mode"] == "supplement" and supplement_target is None:
        raise CatalogError("Quy định bổ sung cần mã tài liệu gốc.")
    if supplement_target and DOCUMENT_ID_PATTERN.fullmatch(supplement_target) is None:
        raise CatalogError("Mã tài liệu gốc phải có dạng APT-LV-099.")
    required_role = raw.get("required_role") or None
    if required_role is not None and required_role not in READ_ROLES:
        raise CatalogError("Vai trò yêu cầu không hợp lệ.")

    published_at = raw.get("published_at")
    if raw["status"] in {"published", "superseded"} and published_at is None:
        published_at = effective_from

    return Document(
        document_id=document_id,
        version_id=f"{document_id}-v{version}",
        version=version,
        title=raw["title"].strip(),
        topic=topic,
        doc_type=raw["doc_type"],
        owner_org=owner_org,
        audience_orgs=tuple(audience_orgs),
        audience_type=raw["audience_type"],
        classification=raw["classification"],
        allowed_contract_types=tuple(contracts),
        status=raw["status"],
        effective_from=effective_from,
        effective_to=effective_to,
        override_mode=raw["override_mode"],
        supersedes=supersedes,
        supplement_target=supplement_target,
        required_role=required_role,
        content=raw["content"].strip(),
        created_at=date.today(),
        published_at=published_at,
        match_phrases=tuple(phrases),
    )


def _phrases(values: list[str]) -> list[str]:
    phrases = []
    for value in values:
        phrase = " ".join(value.casefold().split())
        if phrase and phrase not in phrases:
            if len(phrase) < 2:
                raise CatalogError("Cụm từ nhận diện phải có ít nhất 2 ký tự.")
            phrases.append(phrase)
    return phrases
