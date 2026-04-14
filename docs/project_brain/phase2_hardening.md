# Nhật ký Hoàn thiện Core Engine - Immortal AI Agent (30/03/2026)

Hôm nay chúng ta đã đạt được cột mốc quan trọng: **Hoàn thiện Giai đoạn 2 (Core Engine)** với độ ổn định cực cao, sẵn sàng cho các phần cứng hạn chế (VRAM 4GB).

## 🏆 Những gì đã làm được

### 1. Sửa lỗi Logic Vòng lặp (The Core Fix)
- **Bug**: Sử dụng `for` loop khiến lệnh `iteration -= 1` bị vô hiệu hóa, làm Agent mất lượt khi gặp lỗi định dạng.
- **Giải pháp**: Chuyển sang **`while` loop** với cấu trúc 2 tầng đếm:
    - `iteration`: Đếm bước tiến triển thật (Tool call thành công).
    - `retry_count`: Đếm số lần tự sửa lỗi (Self-Repair) cho mỗi bước (tối đa 3 lần).
- **Kết quả**: Agent có thể "vấp ngã" và tự đứng dậy mà không bị trừ điểm "thể lực" (iteration).

### 2. Hardening Tầng Tài nguyên (VRAM & Token)
- **Cơ chế**: Tích hợp `AdaptiveRouter` vào ngay đầu mỗi phiên chạy để chọn model (3B vs 8B) dựa trên VRAM thực tế.
- **Chốt chặn**: 
    - Hạ GPU layers xuống mức an toàn (16-24 layers) khi VRAM thấp hoặc đang Retry.
    - Ép `num_predict` xuống **150-200 tokens** khi sửa lỗi để chống hiện tượng LLM "nói nhảm" (hallucination).

### 3. Fail-Safe & Resilience (Tính Bất tử)
- **Exponential Backoff**: Tự động đợi (2s, 4s, 8s) khi gặp lỗi mạng/timeout từ Ollama.
- **Sliding Window Context**: Tự động cắt tỉa lịch sử hội thoại (giữ lại 10 tin nhắn gần nhất và câu hỏi gốc) để tránh tràn Context Window.
- **Circuit Breaker**: Tự ngắt nếu hệ thống gặp > 5 lỗi mạng hoặc JSON liên tiếp.

### 4. Bảo mật & Kiểm soát (Validation)
- **Math Security**: Dùng Regex chặn các ký tự nguy hiểm trong `tool_calculate` trước khi `eval`.
- **Type Safety**: Kiểm tra kiểu dữ liệu của tham số tool (phải là string, v.v.) trước khi thực thi.

## 🐞 Các Bug đã gặp và Phương pháp Fix

| Bug | Nguyên nhân | Cách Fix |
| :--- | :--- | :--- |
| **For-loop Deadlock** | Logic `iteration -= 1` không hoạt động trong Python for-loop. | Chuyển sang `while iteration <= max_iterations`. |
| **KV Cache Explosion** | LLM sinh text vô tận khi gặp lỗi -> tràn VRAM. | Khóa cứng `num_ctx: 2048` và giảm `num_predict` xuống 150 khi Retry. |
| **Context Pollution** | Các tin nhắn nhắc lỗi làm LLM bị rối ở vòng sau. | Gán tag `is_temp: True` cho tin nhắn lỗi và lọc sạch ở đầu mỗi bước. |
| **Tool Crash Silent** | Tool gặp lỗi (ví dụ: chia cho 0) làm Agent dừng lại. | Bọc `try-except` quanh tool call, ghi vào `failed_actions` và gửi Observation lỗi cho LLM. |

---
**Trạng thái: Giai đoạn 2 HOÀN THÀNH ✅**
Next Step: Kết nối MCP thực tế (Notion, NotebookLM) và triển khai Interface người dùng.