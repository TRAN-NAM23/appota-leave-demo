from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.answer import AnswerService
from app.catalog import (
    CatalogError,
    catalog_options,
    document_detail,
    document_summaries,
    org_tree,
    save_document,
)
from app.db import delete_document, ensure_database, load_corpus
from app.policy import PolicyEngine


DIST = Path(__file__).resolve().parent.parent / "web" / "dist"
ENGINE: PolicyEngine | None = None
SERVICE: AnswerService | None = None


def default_db_path() -> Path:
    configured = os.environ.get("APPOTA_DB")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parent.parent / "data" / "appota.sqlite"


def init_state(path: Path) -> AnswerService:
    global ENGINE, SERVICE
    ensure_database(path)
    return reload_state(path)


def reload_state(path: Path) -> AnswerService:
    global ENGINE, SERVICE
    ENGINE = PolicyEngine(load_corpus(path))
    SERVICE = AnswerService(ENGINE, db_path=path)
    return SERVICE


def get_service() -> AnswerService:
    if SERVICE is None:
        return init_state(default_db_path())
    return SERVICE


@asynccontextmanager
async def lifespan(_app: FastAPI):
    get_service()
    yield


app = FastAPI(title="Appota_leave-demo", lifespan=lifespan)


class AskRequest(BaseModel):
    persona_id: str
    question: str = Field(min_length=1)
    as_of: date


class CompareRequest(BaseModel):
    left_id: str
    right_id: str
    question: str = Field(min_length=1)
    as_of: date


class DocumentRequest(BaseModel):
    document_id: str = Field(min_length=1)
    version: int = Field(ge=1)
    title: str = Field(min_length=3)
    topic: str = Field(min_length=1)
    match_phrases: list[str] = Field(default_factory=list)
    doc_type: str = "quy_dinh"
    owner_org: str
    audience_orgs: list[str] = Field(min_length=1)
    audience_type: str = "subtree"
    classification: str = "internal"
    allowed_contract_types: list[str] = Field(min_length=1)
    status: str = "published"
    effective_from: date
    effective_to: date | None = None
    override_mode: str = "default"
    supersedes: int | None = Field(default=None, ge=1)
    supplement_target: str | None = None
    required_role: str | None = None
    content: str = Field(min_length=10)
    published_at: date | None = None


@app.get("/api/personas")
def personas() -> list[dict]:
    service = get_service()
    return [service._persona(user) for user in service.engine.corpus.users.values()]


@app.post("/api/chat")
def chat(request: AskRequest) -> dict:
    service = get_service()
    user = service.engine.corpus.users.get(request.persona_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Không có người dùng này trong dữ liệu giả lập.")
    return service.chat(user, request.question, request.as_of)


@app.post("/api/ask")
def ask(request: AskRequest) -> dict:
    service = get_service()
    user = service.engine.corpus.users.get(request.persona_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Không có người dùng này trong dữ liệu giả lập.")
    return service.ask(user, request.question, request.as_of)


@app.get("/api/catalog")
def catalog() -> dict:
    service = get_service()
    return catalog_options(service.engine.corpus)


@app.get("/api/org-tree")
def organization_tree() -> dict:
    service = get_service()
    return org_tree(service.engine.corpus)


@app.get("/api/documents")
def documents() -> list[dict]:
    service = get_service()
    return document_summaries(service.engine.corpus)


@app.get("/api/documents/{version_id}")
def document(version_id: str) -> dict:
    service = get_service()
    detail = document_detail(service.engine.corpus, version_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Không có phiên bản tài liệu này.")
    return detail


@app.delete("/api/documents/{version_id}")
def remove_document(version_id: str) -> dict:
    service = get_service()
    path = service.db_path or default_db_path()
    if not delete_document(path, version_id):
        raise HTTPException(status_code=404, detail="Không có phiên bản tài liệu này.")
    reload_state(path)
    return {"version_id": version_id}


@app.post("/api/documents", status_code=201)
def create_document(request: DocumentRequest) -> dict:
    service = get_service()
    path = service.db_path or default_db_path()
    try:
        document = save_document(path, service.engine.corpus, request.model_dump())
    except CatalogError as error:
        raise HTTPException(status_code=error.status, detail=str(error)) from error
    reload_state(path)
    return {
        "version_id": document.version_id,
        "document_id": document.document_id,
        "version": document.version,
        "title": document.title,
        "topic": document.topic,
    }


@app.post("/api/compare")
def compare(request: CompareRequest) -> dict:
    service = get_service()
    left = service.engine.corpus.users.get(request.left_id)
    right = service.engine.corpus.users.get(request.right_id)
    if left is None or right is None:
        raise HTTPException(status_code=404, detail="Không có người dùng này trong dữ liệu giả lập.")
    return {
        "left": service.ask(left, request.question, request.as_of),
        "right": service.ask(right, request.question, request.as_of),
    }


if DIST.is_dir():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="frontend")
