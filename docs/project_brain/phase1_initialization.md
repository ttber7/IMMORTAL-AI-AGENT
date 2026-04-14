# IMMORTAL AI ARCHITECTURE: Tóm tắt Cải tiến Phase 1 (Foundation)

Tài liệu này lưu trữ các quyết định kiến trúc đầu tiên nhằm đặt nền móng cho một Agent AI có thể chạy "sống" trên GPU 4GB VRAM.

---

## 🚀 GIAI ĐOẠN 1: KHỞI TẠO NỀN TẢNG & TỐI ƯU VRAM

Mục tiêu chính của Phase 1 là thiết lập lớp `AgentEngine` đầu tiên và tìm ra các tham số "điểm ngọt" để Ollama không làm sập hệ thống.

### 1. Cấu trúc AgentEngine Sơ khởi
**Mục đích**: Thiết lập luồng `messages` và khả năng gọi công cụ (function calling) đơn giản nhất.
**Đoạn code lưu ý (`core/agent_engine.py`)**:
```python
class AgentEngine:
    def __init__(self, model="llama3:latest"):
        self.model = model
        self.messages = []
        self.tools = {
            "tool_calculate": tool_calculate,
            "tool_system_check": tool_system_check
        }
```

### 2. Tối ưu hóa GPU Layers (VRAM Management)
**Mục đích**: Ép mô hình 8B hoạt động trong giới hạn 4GB bằng cách chia nhỏ các lớp xử lý trên GPU.
**Cấu hình quan trọng**:
- **num_ctx**: Cố định ở `2048` để tránh tràn RAM khi lưu trữ KV Cache.
- **num_gpu**: Điều chỉnh linh hoạt từ `16 đến 24` layers tùy theo model (Llama3 vs Phi-3).
- **repeat_penalty**: Thiết lập `1.1` để ngăn chặn Agent bị lặp văn bản ngay từ đầu.

### 3. Tích hợp Tool Check Phần cứng
**Mục đích**: Cho phép Agent tự biết mình còn bao nhiêu VRAM để quyết định có tiếp tục suy luận hay không.
**Đoạn code lưu ý (`core/resource_monitor.py`)**:
```python
def check_vram():
    """Kiểm tra VRAM thực tế của Quadro T2000"""
    # Sử dụng NVML để lấy thông số chính xác thay vì ước lượng
    info = pynvml.nvmlDeviceGetMemoryInfo(handle)
    used_vram = info.used / 1024**2
    return used_vram # Trả về MB
```

---

## 🐞 Các Bug "Triệu USD" đã xử lý ở Phase 1

| Bug | Nguyên nhân | Cách Fix |
| :--- | :--- | :--- |
| **Connection Refused** | Ollama chưa sẵn sàng hoặc cổng 11434 bị chiếm dụng. | Thêm `Initial Warm-up` check ở `app.py` trước khi khởi chạy Engine. |
| **VRAM Spike (6GB+)** | Model load mặc định lên tới 32 layers. | Ép tham số `options={"num_gpu": 20}` trong mọi request gọi API Ollama. |
| **Agent "Nín thở" (Timeout)** | Request quá lâu mà không có phản hồi stream. | Triển khai chế độ `stream=True` và in kết quả ra console để theo dõi thời gian thực. |

---
**Trạng thái: Giai đoạn 1 HOÀN THÀNH ✅**
Tiền đề để tiến vào Giai đoạn 2 (Hardening logic).
