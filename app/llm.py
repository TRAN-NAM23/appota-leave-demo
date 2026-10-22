from __future__ import annotations

import json
import os
from pathlib import Path

import httpx


LAST_ERROR = ""


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


def last_error() -> str:
    return LAST_ERROR


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


def understand(question: str, context: str) -> dict | None:
    _load_local_env()
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return None
    api_key = os.environ.get("LLM_API_KEY", "").strip()
    if not api_key or not context.strip():
        return None
    base_url = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.environ.get("LLM_MODEL", "gpt-4o-mini")
    system = (
        "Bạn là agent hỏi đáp. Hãy hiểu người dùng đang hỏi việc gì, "
        "rồi xem các đoạn tài liệu có trả lời đúng việc đó không. "
        "Trùng vài từ không có nghĩa là đúng câu trả lời. "
        "Chỉ dùng đoạn được cung cấp, không bịa thêm quy trình hay số liệu. "
        "Một câu có thể hỏi nhiều việc. Trả lời từng việc mà tài liệu có, "
        "và nói rõ việc nào không có trong tài liệu. "
        "Không bỏ cả câu chỉ vì một việc không có căn cứ. "
        "Trả về một JSON duy nhất với hai khóa: "
        "\"answers\" là true hoặc false, \"reply\" là câu tiếng Việt. "
        "answers là true khi trả lời được ít nhất một việc từ tài liệu. "
        "Khi true, reply nêu mã tài liệu, trả lời các việc có căn cứ, "
        "rồi nói việc nào tài liệu không đề cập. "
        "answers là false chỉ khi không việc nào được tài liệu trả lời. "
        "Khi false, không chép quy định của một câu hỏi khác."
    )
    user = f"Ngữ cảnh:\n{context}\n\nCâu hỏi:\n{question}"
    text = _chat(base_url, api_key, model, system, user, json_mode=True)
    if text is None:
        text = _chat(base_url, api_key, model, system, user, json_mode=False)
    return _parse_judgment(text)


def _chat(base_url: str, api_key: str, model: str, system: str, user: str, json_mode: bool) -> str | None:
    global LAST_ERROR
    payload: dict = {
        "model": model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    try:
        response = httpx.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
            timeout=30,
        )
        if response.status_code == 400 and json_mode:
            return None
        if response.status_code >= 400:
            LAST_ERROR = _error_label(response)
            return None
        LAST_ERROR = ""
        return response.json()["choices"][0]["message"]["content"].strip()
    except (httpx.HTTPError, KeyError, IndexError, TypeError):
        if not LAST_ERROR:
            LAST_ERROR = "request_failed"
        return None


def _error_label(response: httpx.Response) -> str:
    code = ""
    try:
        error = response.json()["error"]
        code = str(error.get("code") or error.get("type") or "")
    except (ValueError, KeyError, TypeError, AttributeError):
        code = ""
    if response.status_code == 429 or code in {"insufficient_quota", "credit_balance_exhausted"}:
        return "quota"
    return f"http {response.status_code}"


def _parse_judgment(text: str | None) -> dict | None:
    if not text:
        return None
    raw = text.strip()
    if raw.startswith("```"):
        raw = raw.strip("`").removeprefix("json").strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            data = json.loads(raw[start:end + 1])
        except json.JSONDecodeError:
            return None
    if not isinstance(data, dict) or "answers" not in data:
        return None
    answers = data["answers"]
    if isinstance(answers, str):
        answers = answers.strip().casefold() in {"true", "yes", "có", "co", "1"}
    reply = str(data.get("reply") or "").strip()
    if not reply:
        return None
    return {"answers": bool(answers), "reply": reply}
