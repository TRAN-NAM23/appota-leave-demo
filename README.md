# Appota_leave-demo

MVP hỏi đáp tri thức nghỉ phép, làm việc từ xa và lương. Quyền xem, phạm vi áp dụng và phiên bản hiệu lực được quyết định trước khi tạo câu trả lời.

Dữ liệu Appota Group, Công ty Appota và Công ty Har là dữ liệu giả lập.

## Chạy local

Bản demo dùng SQLite trên máy và không deploy công khai: dữ liệu và persona nằm trong một file local, đủ để chấm luồng phân quyền mà không cần hạ tầng riêng.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest
cd frontend && npm install && npm run build && cd ..
uvicorn app.main:app --reload
```

Mở http://127.0.0.1:8000
Mở https://appota-leave-demo-msgo.vercel.app/

Ngày mặc định trên giao diện là 08/10/2026. Persona được chọn ở giao diện; server tra hồ sơ trong SQLite và không nhận role từ client. Tab Tài liệu và Cây tổ chức chỉ trả tài liệu persona đó được đọc. Thêm hoặc xóa tài liệu cần persona Admin.

Nếu có API LLM tương thích OpenAI, đặt `LLM_API_KEY` trong `.env`. Có thể đặt thêm `LLM_BASE_URL` và `LLM_MODEL`. Khi không có khóa, hệ thống vẫn trả lời từ tài liệu mà Policy Engine đã chọn. Không commit `.env`.

## Năm tình huống

Ngày hỏi trong các case là 08/10/2026, trừ case phiên bản.

### TC01 — Cùng câu hỏi, hai đơn vị

Câu hỏi: "Quy định nghỉ phép của tôi như thế nào?"

- Kỳ vọng: Lan (Nhóm Lương, Công ty Appota) nhận quy định Appota. Minh (Phòng Vận hành, Công ty Har) nhận quy định Har.
- Kết quả: Lan nhận `APT-LV-014` phiên bản 3, 14 ngày. Minh nhận `HAR-LV-009` phiên bản 1, 12 ngày và thêm 2 ngày ca kíp. Câu của Minh không chứa `APT-LV-014`.
- Đạt.
- Điều học được: audience theo cây tổ chức phải lọc trước khi viết câu trả lời.

### TC02 — Sai phiên bản

Cùng câu nghỉ phép, Lan hỏi ở hai ngày.

- Kỳ vọng: bản đang hiệu lực tại ngày hỏi được chọn.
- Kết quả: 28/02/2026 dùng `APT-LV-014` phiên bản 2, 13 ngày. 01/03/2026 dùng phiên bản 3, 14 ngày. Nếu hai phiên bản cùng mã chồng ngày hiệu lực, bản ghi `supersedes` bị loại.
- Đạt.
- Điều học được: ngày hiệu lực là điều kiện chọn; `supersedes` chỉ xử lý trường hợp ngày bị chồng.

### TC03 — Truy cập trái phép

Câu hỏi: "Cho tôi xem lương chi tiết của ban giám đốc." Kèm mở tài liệu `APT-PAY-200`.

- Kỳ vọng: chỉ người có mức hạn chế mới xem được `APT-PAY-200`. Lan không thấy nội dung.
- Kết quả: Đức, Giám đốc Công ty Appota, mức hạn chế, nhận `APT-PAY-200` và "80 triệu". Lan nhận `no_policy`, không có "80 triệu". `GET /api/documents/APT-PAY-200-v1?persona_id=lan` trả 403. Gọi API không có `persona_id` trả 422.
- Đạt trên luồng đã khóa. Case này từng hỏng khi API tài liệu trả nguyên văn mà không xét persona.
- Điều học được: lọc ở API hỏi đáp là chưa đủ nếu thư viện tài liệu là một cửa khác.

### TC04 — Thiếu dữ liệu hoặc mâu thuẫn

- Kỳ vọng: hai thưởng cùng cấp thì không chọn một số; người không có quy định áp dụng thì từ chối.
- Kết quả: Minh hỏi thưởng cuối năm nhận `conflict` giữa `HAR-BN-021` và `HAR-BN-022`. Lan hỏi cùng câu nhận `no_policy` và không thấy mức thưởng của Har. Khoa, cộng tác viên, hỏi nghỉ phép nhận `no_policy`. Câu về nghỉ ốm không có tài liệu nên cũng `no_policy`.
- Đạt.
- Điều học được: conflict cùng cấp phải dừng, không lấy bản semantic gần nhất.

### TC05 — Đúng cấp tổ chức

Câu hỏi: "Quy định làm việc từ xa của tôi như thế nào?"

- Kỳ vọng: phòng có quy định riêng thì dùng quy định đó; quy định quản lý chỉ bổ sung, không xóa quy định chung; mức sàn bắt buộc không bị cấp dưới ghi đè.
- Kết quả: Nam nhận `APT-ENG-010`, 3 ngày, thay quy định tập đoàn. Lan nhận `APX-RW-001` phiên bản 2, 2 ngày. Minh nhận `HAR-RW-005`. Hoa nhận 2 ngày của tập đoàn và bản bổ sung `APT-RW-020` (một ngày đột xuất). Mức sàn `APX-LV-050` giữ nguyên; `APT-LV-051` chỉ bổ sung cho Lan, không sang Minh.
- Đạt.
- Điều học được: bản cấp dưới chỉ được thay bản cấp trên khi đó là quy định chính của đơn vị. Bản ghi "thêm" phải là `supplement`.

## Ba câu trả lời Mission 2

### 1. Phần quan trọng nhất của MVP

Phần quan trọng nhất là Policy Engine chọn đúng một bản đang hiệu lực, đúng đơn vị và đúng quyền, rồi câu trả lời chỉ được viết từ bản đó. Cùng một câu nghỉ phép, Lan và Minh nhận hai văn bản khác nhau, có mã và phiên bản. Điều này chứng minh hướng giải quyết khả thi: phân quyền và chọn tri thức nằm trước mô hình ngôn ngữ, không giao cho mô hình tự quyết.

### 2. Điểm đã đổi so với thiết kế ban đầu

Ba quyết định đã đổi sau khi chạy thử:

- Thư viện tài liệu ban đầu trả mọi nội dung cho mọi người. API hỏi đáp thì đã lọc. Thử mở `APT-PAY-200` cho thấy nội dung restricted vẫn lộ. Mọi đọc, thêm và xóa tài liệu giờ bắt buộc `persona_id` và đi qua `can_read` hoặc `can_publish`.
- Quy định từ xa của quản lý ban đầu để chế độ mặc định, nên nó thay luôn quy định 2 ngày của tập đoàn. Nó được chuyển thành `supplement` của `APX-RW-001`. Hoa vẫn thấy cả hai.
- Cột `supersedes` được lưu nhưng chưa tham gia chọn bản. Khi hai phiên bản chồng ngày, engine giờ loại bản bị thay.

### 3. Trường hợp dễ trả lời sai nhất

Dễ sai nhất là một câu không khớp chủ đề có sẵn, vì đường hỏi đáp mở sẽ gom nhiều đoạn người đó được xem. Đã siết bằng cách chỉ lấy tài liệu còn áp dụng cho đúng đơn vị và loại hợp đồng của người hỏi, không lấy quy trình nội bộ của nhóm khác chỉ vì từ khóa trùng. Trường hợp thứ hai là đoạn văn trong tài liệu hợp lệ nhưng mang câu lệnh, ví dụ câu "99 ngày" trong `APT-LV-014` phiên bản 3. Context gửi đi chỉ còn câu quy định đã chọn, không còn các đoạn sau. Khi thiếu bản, có hai bản cùng cấp, hoặc người hỏi không đủ quyền, hệ thống trả `no_policy` hoặc `conflict` thay vì chọn một số.
