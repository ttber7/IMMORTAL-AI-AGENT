# 🚀 NÂNG CẤP & ƯU TIÊN - GIAI ĐOẠN 5
**Tên Phase:** The Concurrency Layer (Priority Queue & Graceful Degradation)  
**Ngày tạo:** 2026-04-13 | **Cập nhật cuối:** 2026-04-15  

---

## ✅ ĐÃ HOÀN THÀNH TRONG PHASE 5

| Hạng mục | Mô tả | Kết quả |
|---|---|---|
| PriorityQueueGateway | Background worker thread với asyncio.PriorityQueue | ✅ 4 cấp độ ưu tiên |
| Aging Mechanism | Tăng ưu tiên sau 10s chờ (Starvation prevention) | ✅ Max Level 1 |
| Backpressure | Reject khi > 10 tasks | ✅ Bảo vệ RAM |
| Task Cancellation | Cờ is_cancelled cho phép hủy từ bên ngoài | ✅ Memory safe |
| Harvested Data | Buffer lưu Observations để Graceful Degrade | ✅ Không trả lỗi rỗng |
| Thread-Safety | Pending Lock bảo vệ Dictionary | ✅ Không Race Condition |
| UI Queue Position | Hiển thị vị trí chờ real-time | ✅  |
| Timeout 120s | Force cancel task quá thời gian | ✅ Không treo vĩnh viễn |

---

## 💡 NHỮNG GÌ CÓ THỂ NÂNG CẤP TƯƠNG LAI

### Ưu tiên Cao (Phase 6 đã có một phần)
- **🔧 Dynamic Worker Scaling (Hysteresis)** *(Đã triển khai Phase 6)*:
  - 1 Worker mặc định.
  - Nếu VRAM < 1.5GB liên tục 5 giây → nâng lên 2 Workers.
  - Ngay khi VRAM tăng → giảm về 1 Worker tức thì.

- **🔧 Task Dependency Graph**: Cho phép Task A chờ kết quả của Task B hoàn thành trước.
  - Use case: "Tìm kiếm web trước, sau đó tóm tắt bằng RAG."

### Ưu tiên Trung bình
- **📊 Queue Analytics Dashboard**: Thêm vào UI một bảng theo dõi:
  - Tổng số task đã xử lý.
  - Thời gian chờ trung bình theo từng Level.
  - Số task bị reject vì Backpressure.

- **🔔 Priority 5 (Critical)**: Thêm Level mới cho trường hợp khẩn cấp (Admin tasks / Health check).

- **⏱️ Per-Task Timeout**: Mỗi Level có timeout riêng:
  - Level 0: 30s (tính toán nhanh)
  - Level 1: 60s (RAG)
  - Level 2-3: 120s (Web search phức tạp)

### Ưu tiên Thấp
- **🔄 Dead Letter Queue (DLQ)**: Task thất bại quá 3 lần → chuyển sang DLQ để Admin review.
- **🌐 Distributed Queue**: Khi scale ra nhiều máy, dùng Redis Queue thay vì asyncio.PriorityQueue.

---

## 📝 BÀI HỌC RÚT RA TỪ PHASE 5

> **"Concurrency không phải chạy nhanh hơn, mà là không bị chết khi nhiều người dùng cùng lúc."**

- `asyncio.PriorityQueue` + Background Thread là lựa chọn tốt nhất cho single-process Python app.
- Thread-safety là thứ DUY NHẤT không thể bỏ qua trong multi-thread code. Lock ở mọi nơi cần thiết.
- Aging limit tối đa Level 1 (không cho Level 3 nhảy vọt lên 0) là quyết định đúng đắn nhất Phase 5.
- Graceful Degradation (Harvested Data) quan trọng hơn việc cố gắng trả lời hoàn hảo — user thích câu trả lời "một phần" hơn là error rỗng.
