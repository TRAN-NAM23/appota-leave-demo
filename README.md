# Appota_leave-demo

MVP hỏi đáp tri thức nghỉ phép, làm việc từ xa và lương. Quyền xem, phạm vi áp dụng và phiên bản hiệu lực được quyết định trước khi tạo câu trả lời.

Dữ liệu Appota Group, Công ty Appota và Công ty Har là dữ liệu giả lập.

## Chạy

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest
cd frontend && npm install && npm run build && cd ..
uvicorn app.main:app --reload
```

Mở http://127.0.0.1:8000

Giao diện là ứng dụng React trong `frontend/`. Sau khi sửa giao diện, chạy lại `npm run build` trong thư mục đó.

Form **Thêm tài liệu** ghi một phiên bản mới vào SQLite. Bản đã thêm không bị xóa khi mở lại ứng dụng. Câu trả lời vẫn chỉ dùng tài liệu mà Policy Engine cho phép.

Nếu có API LLM tương thích OpenAI, đặt `LLM_API_KEY`. Có thể đặt thêm `LLM_BASE_URL` và `LLM_MODEL`. Khi không có khóa, hệ thống vẫn trả lời từ tài liệu mà Policy Engine đã chọn.
