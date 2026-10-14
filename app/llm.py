from __future__ import annotations

import os
from pathlib import Path

import httpx


def _load_local_env() -> None:
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return
    path = Path(__file__).resolve().parent.parent / ".env"
    if not path.is_file():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().removeprefix("export ").strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def llm_configured() -> bool:
    _load_local_env()
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    return bool(os.environ.get("LLM_API_KEY", "").strip())


def complete(question: str, context: str) -> str | None:
    _load_local_env()
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return None
    api_key = os.environ.get("LLM_API_KEY", "").strip()
    if not api_key or not context.strip():
        return None
    base_url = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.environ.get("LLM_MODEL", "gpt-4o-mini")
    payload = {
        "model": model,
        "temperature": 0,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Bạn chỉ được dùng các đoạn tài liệu được cung cấp. "
                    "Không quyết định quyền truy cập và không chọn tài liệu khác. "
                    "Mỗi kết luận phải nêu mã tài liệu có trong ngữ cảnh. "
                    "Nếu ngữ cảnh không đủ, hãy nói chưa thể kết luận."
                ),
            },
            {
                "role": "user",
                "content": f"Ngữ cảnh:\n{context}\n\nCâu hỏi:\n{question}",
            },
        ],
    }
    try:
        response = httpx.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
            timeout=20,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()
    except (httpx.HTTPError, KeyError, IndexError, TypeError):
        return None
