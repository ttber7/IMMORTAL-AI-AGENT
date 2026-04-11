# IMMORTAL AI AGENT: ARCHITECTURE vFINAL 2026 (PHASE 3)

Giai đoạn 3 đánh dấu sự chuyển mình của The Immortal AI Agent từ một hệ thống console đơn thuần thành một hệ thống Command Center có khả năng hiển thị thời gian thực, giám sát tiến trình và tinh chỉnh thông số động ngay trong khi hoạt động trên môi trường siêu tối giản (NVIDIA Quadro T2000 - 4GB VRAM). 

Dưới đây là kiến trúc và các thay đổi cực kỳ quan trọng đã hoàn thành:

## 1. BẢO VỆ VRAM "ONE-IN, ONE-OUT" VÀ CACHE MANAGEMENT
- **Vấn đề Cốt lõi**: VRAM 4GB rất dễ bị tràn (OOM) nếu load song song nhiều LLM model khi thao tác frontend UI.
- **Giải pháp Kiến trúc**:
  - `st.cache_resource` được chuyển đổi thành kiến trúc lưu trữ theo dạng đối tượng Dictionary `get_engine_cache()`. 
  - Khi user chuyển đổi model (llama3.2 -> phi3 -> qwen), ứng dụng kích hoạt chế độ dọn rác thủ công `st.cache_resource.clear()`, đẩy hoàn toàn model cũ ra khỏi bộ nhớ rồi mới nạp model mới (Clear before load).

## 2. DYNAMIC ROUTING & MANUAL OVERRIDE
- **Vấn đề Cốt lõi**: Model không được thay đổi đồng nhất giữa UI Streamlit và AgentEngine Core, gây sai lệch luồng dữ liệu.
- **Giải pháp Kiến trúc**:
  - Giao diện bổ sung Dropdown: `Auto (Smart Router)`, `llama3.2:3b`, `phi3:mini`, `qwen2.5:3b`.
  - Tham số `target_model` được đẩy xuyên suốt qua luồng EventLoop Async (từ `app.py` -> `gateway_entry` -> `AgentEngine.run`). 
  - Khóa mõm Router khi phát hiện "Manual Override", ưu tiên tuyệt đối quyền chọn model của User. 

## 3. PROMPTING ENGINE (JSON ENFORCEMENT & INFINITE LOOP)
- **Vấn đề Cốt lõi**: Hành vi tản mạn của LLM (xin lỗi, diễn giải rườm rà) và lỗi lặp vô tận khi gọi công cụ sai cú pháp.
- **Giải pháp Kiến trúc**:
  - Tích hợp System Prompt dạng "Quy Nhất": Định nghĩa duy nhất 1 cấu trúc JSON bắt buộc: `{"thought": "...", "answer": "..."}`.
  - Ngắt mạch khẩn cấp (Circuit Breaker): Tại lượt lặp cuối cùng `iteration == max_iterations`, chèn thẳng lệnh **"FORCE FINAL ANSWER: ĐÂY LÀ LƯỢT CUỐI CÙNG"** vào prompt, ép LLM chốt hạ câu trả lời, không vướng vào suy luận hay gọi công cụ.

## 4. UI METRICS & TÍNH TẬP TRUNG NGÔN NGỮ (VIỆT NAM)
- **Vấn đề Cốt lõi**: Tiếng Việt bị lỗi bộ gõ khi xuất file và giao diện Metric bị nhảy layout mỗi khi luồng suy luận in thêm dòng mới.
- **Giải pháp Kiến trúc**:
  - Áp dụng `ensure_ascii=False` và `encoding="utf-8"` cho Data Persistence (`agent_metrics.json`), giữ nguyên font chữ Tiếng Việt khi load Dashboard.
  - Cố định Layout bằng khối `container.container()` trong Frontend. Đảm bảo Hardware Radar luôn neo tại sidebar mà không bị UI sinh mã đè lên.

## 5. EXPERT TURBO MODE (TỐI ƯU HIỆU NĂNG)
- **Vấn đề Cốt lõi**: Không phải Task nào cũng có nhu cầu suy luận logic quá lâu và tốn GPU (VD: Các câu hỏi lập trình mã ngắn).
- **Giải pháp Kiến trúc**:
  - Nút Switcher đặc biệt: Áp lệnh khóa cứng độ sáng tạo (Temperature = 0.0) và vòng lặp (Max Iterations = 3).
  - Tăng độ nhạy (Latency) lên mức cực đại, hạn chế triệt để VRAM Spikes. Kèm theo tính năng "Reset To Default" trả độ sáng tạo về 0.2.
