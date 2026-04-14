# Phase 5: The Concurrency Layer (Tầng Hội Tụ & Song Song)
**Ngày hoàn tất:** 2026-04-13
**Trạng thái:** ✅ Hoàn thành / Ổn định

## 1. Mục tiêu & Tầm nhìn
Mục tiêu cốt lõi của Phase 5 là chuyển đổi Immortal AI từ một hệ thống xử lý tuần tự đơn giản (dễ bị treo khi spam) thành một **Dịch vụ (Service)** vững chãi. Hệ thống hiện có khả năng tiếp nhận nhiều yêu cầu đồng thời, tự động sắp xếp độ ưu tiên và đảm bảo an toàn tuyệt đối cho VRAM 4GB của Quadro T2000.

---

## 2. Các Cải Tiến Kỹ Thuật (Nâng cấp & Fix lỗi)

### 🛡️ Priority Queue Gateway (Thay thế cơ chế Lock cũ)
- **Vấn đề cũ**: Dùng `asyncio.Semaphore` đơn giản gây ra tình trạng "Fake Worker" (các thread Streamlit bị block chờ đợi vô thời hạn) và không thể ưu tiên các tác vụ quan trọng.
- **Giải pháp mới**:
    - Triển khai **PriorityQueueGateway** hoạt động trên một **Background Worker Thread** riêng biệt.
    - **4 Cấp độ Ưu tiên**:
        - `Level 0 (Highest)`: Chat trực tiếp, Tính toán (Calculate).
        - `Level 1 (High)`: Truy vấn RAG tài liệu nội bộ.
        - `Level 2 (Normal)`: Các suy luận mặc định.
        - `Level 3 (Low)`: Web Search (vì thời gian chờ API lâu).
    - **Cơ chế Aging**: Cứ mỗi 10 giây chờ đợi, tác vụ sẽ được tự động tăng mức ưu tiên để tránh tình trạng "đói tài nguyên" (Starvation).

### 🌾 Data Harvesting & Graceful Degradation
- **Vấn đề cũ**: Khi Agent đạt `max_iterations` (bị kẹt loop), nó sẽ trả về một thông báo lỗi trống rỗng, làm phí phạm các kết quả đã tìm thấy trước đó.
- **Giải pháp mới**:
    - Thêm bộ đệm **Harvested Data**: Lưu lại mọi quan sát (Observation) từ các công cụ (RAG, Web Search) trong suốt quá trình suy luận.
    - **Recovery Mode**: Khi hết lượt suy luận, Agent sẽ không báo lỗi mà chuyển sang bước **Tổng hợp cuối cùng (Final Resynthesis)**, sử dụng dữ liệu đã thu hoạch để trả lời tốt nhất có thể cho người dùng.

### 🚥 Backpressure (Chống quá tải)
- Giới hạn hàng đợi tối đa **10 tác vụ**. Nếu vượt quá, hệ thống sẽ từ chối nhận lệnh mới (Reject) để bảo vệ RAM và tránh làm sập Engine.

---

## 3. Nhật ký Fix lỗi (Chỉ dành cho Dev)
- **Fix Thread-Safety**: Giải quyết xung đột giữa loop của Streamlit và loop của Gateway bằng cách sử tại `asyncio.run_coroutine_threadsafe`.
- **Fix JSON Recovery**: Cải tiến logic trích xuất JSON trong trường hợp LLM phản hồi lộn xộn ở bước Recovery.
- **Fix UI Rerender**: Đảm bảo thanh trạng thái (status placeholder) cập nhật vị trí hàng đợi (Position in Queue) một cách mượt mà theo thời gian thực.

---

## 4. Cấu trúc mã nguồn thay đổi
1. `core/gateway.py`: Viết lại toàn bộ để hỗ trợ hệ thống hàng đợi ưu tiên và worker thread.
2. `core/agent_engine.py`: Tích hợp logic thu hoạch dữ liệu và các mức độ ưu tiên động.
3. `app.py`: Cập nhật UI để hiển thị trạng thái hàng đợi và xử lý async bridge mới.

---
**Kết luận:** Phase 5 đã biến **The Immortal AI** thành một hệ thống sẵn sàng cho môi trường đa người dùng, tối ưu hóa tối đa sức mạnh của phần cứng giới hạn.
