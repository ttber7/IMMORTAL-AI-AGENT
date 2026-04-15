# 📌 NHỮNG ĐIỂM LƯU Ý TRIỂN KHAI - GIAI ĐOẠN 6
**Tên Phase:** The Microservices Layer (FastAPI Backend + Streamlit Dumb Client)  
**Ngày hoàn thành:** 2026-04-15  
**Trạng thái:** ✅ Hoàn thành / Production  
**Architecture:** FastAPI (Port 8000) + Streamlit (Port 8501)

---

## 🔴 CÁC SAO ĐỎ KHÔNG ĐƯỢC PHÉP VI PHẠM

1. **LUÔN khởi động Backend TRƯỚC Frontend**: `uvicorn` phải chạy hoàn toàn trước khi mở Streamlit.
2. **KHÔNG đặt logic AI trong `app.py`**: Streamlit chỉ được gọi HTTP và render kết quả. Mọi logic phải nằm trong `server.py`.
3. **KHÔNG expose `/admin/reload-rag` ra internet**: Endpoint này không có auth — chỉ dùng nội bộ (`localhost` only).

---

## ⚠️ LƯU Ý KỸ THUẬT CHÍNH

### 1. SSE Event Format - Hợp đồng giữa Backend và Frontend
```
# Backend phát ra (server.py):
data: {"event": "THINK", "data": "Đang phân tích câu hỏi..."}
data: {"event": "ACT", "data": "Gọi tool: search_document"}
data: {"event": "OBSERVE", "data": "Tìm thấy 3 kết quả..."}
data: {"event": "FINAL_ANSWER", "data": "Câu trả lời cuối cùng..."}
data: {"event": "ERROR", "data": "Thông báo lỗi..."}
data: {"event": "PING", "data": "keep-alive"}
```
**KHÔNG thay đổi các `event` key này** nếu không cập nhật đồng thời parser ở Frontend.

### 2. Stateless Request - Frontend gửi toàn bộ History
```python
# app.py
data = {
    "message": user_message,
    "chat_history": st.session_state.messages  # Full history mỗi lần
}
async with httpx.AsyncClient() as client:
    async with client.stream("POST", BACKEND_URL, json=data, timeout=180) as r:
        ...
```
Không có Server-side Session. Backend hoàn toàn stateless.

### 3. VRAM Gateway - Semaphore tĩnh
```python
# Thay vì tự viết PriorityQueue phức tạp, chặn cứng ở 2 worker đồng thời.
GLOBAL_SEMAPHORE = asyncio.Semaphore(2)

if GLOBAL_SEMAPHORE.locked():
    yield "QUEUE_WAITING"

async with GLOBAL_SEMAPHORE:
    # Worker bắt đầu chạy
```

### 4. PII Log - Kiểm tra Regex trước khi deploy
Chạy test sau để xác nhận masking hoạt động đúng:
```python
from core.telemetry import anonymize_text
assert "0901234567" not in anonymize_text("SĐT: 0901234567")
assert "123456789" not in anonymize_text("CMND: 123456789")
```

### 5. RAG Reload API - Workflow đúng
```bash
# 1. Copy file mới vào knowledge_base/
cp new_doc.txt knowledge_base/internal_docs/

# 2. Gọi API reload (không cần restart)
curl -X POST http://localhost:8000/admin/reload-rag

# 3. Kiểm tra log
# Server sẽ log: "Đang reload RAG... LocalRAG reloaded successfully"
```

### 6. Semantic Cache - Giới hạn dung lượng
Cache lưu trong RAM, không có TTL. Nếu hệ thống chạy liên tục nhiều ngày, cache có thể phình to.
Thêm giới hạn LRU nếu cần:
```python
from functools import lru_cache
# Hoặc dùng cachetools.LRUCache(maxsize=500)
```

### 7. Graceful Shutdown
```bash
# Dừng đúng thứ tự: Frontend trước, Backend sau
# 1. Ctrl+C ở terminal Streamlit
# 2. Ctrl+C ở terminal Uvicorn
```

---

## 📋 CHECKLIST KIỂM TRA SAU TRIỂN KHAI PHASE 6

- [ ] `http://localhost:8000/health` trả về `{"status": "ok"}`
- [ ] `http://localhost:8501` hiển thị UI Streamlit
- [ ] Request từ UI stream được THINK/ACT/OBSERVE/FINAL
- [ ] Khi ngắt kết nối browser, backend cancel task và giải phóng VRAM
- [ ] `/admin/reload-rag` rebuild index thành công với file mới
- [ ] Log `logs/agent_errors.jsonl` không chứa số điện thoại/CMND thật
- [ ] Worker Semaphore tự động chặn VRAM quá mức (giới hạn cứng 2 luồng)
- [ ] Semantic cache trả về kết quả cũ khi gõ câu hỏi giống hệt trước
