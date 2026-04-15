# Phase 6: The Microservices Layer (Tầng Dịch vụ Hoàn chỉnh)
**Ngày hoàn thành:** 2026-04-15  
**Trạng thái:** ✅ Hoàn thành / Production  

---

## 1. Mục tiêu & Tầm nhìn

Giai đoạn 6 là bước nâng cấp kiến trúc triệt để nhất. Toàn bộ logic AI được chuyển khỏi Streamlit và đặt vào một **FastAPI Backend** bất đồng bộ. Điều này tách biệt hoàn toàn giao diện người dùng và bộ xử lý trung tâm, tạo ra nền tảng sẵn sàng kết nối với bất kỳ frontend nào (React, Mobile, CLI...).

---

## 2. Quyết định Kiến trúc Quan trọng Nhất: Archive `gateway.py`

### Tại sao `gateway.py` cũ bị loại bỏ?

`gateway.py` cũ (Phase 5) là một **PriorityQueueGateway** phức tạp, tự viết với asyncio.PriorityQueue, Background Thread, và Aging mechanism. Nó giải quyết vấn đề của Streamlit (phải tự tạo queue vì Streamlit chạy sync).

Khi chuyển sang **FastAPI** — vốn đã hoàn toàn bất đồng bộ — cơ chế đó trở nên không cần thiết và dư thừa:

| Thứ | **Phase 5 (gateway.py cũ)** | **Phase 6 (FastAPI native)** |
|---|---|---|
| Concurrency | Tự viết asyncio.PriorityQueue + Background Thread | `asyncio.Semaphore(2)` — native, tối giản |
| VRAM Guard | Hysteresis Timer phức tạp | Semaphore đơn giản, hiệu quả hơn |
| Queue | Thủ công, có thể race condition | asyncio event loop tự động quản lý |
| Timeout | Manual cancel flag | `engine_task.cancel()` + `await engine_task` |

**Kết quả:** `gateway.py` cũ được di chuyển vào **`Archive/gateway.py`** để tham khảo. FastAPI đảm nhận toàn bộ vai trò "gateway" với code gọn hơn 5 lần.

```
THE IMMORTAL AI AGENT/
├── Archive/
│   └── gateway.py          ← Archived (Phase 5 — không còn dùng)
├── core/
│   ├── agent_engine.py
│   ├── local_rag.py
│   ├── semantic_cache.py
│   └── telemetry.py
├── server.py              ← FastAPI Backend (The New Gateway)
└── app.py                 ← Streamlit Dumb Client
```

---

## 3. Kiến trúc Phase 6 — 4 Lớp Bảo vệ

`server.py` được thiết kế theo mô hình **Defense in Depth** — mỗi request đi qua 4 lớp lọc trước khi chạm vào GPU:

```
User Request
│
├── [LAYER 1] Pydantic Validator
│     - Giới hạn messages tối đa 20 tin nhắn
│     - Giới hạn query <= 2000 ký tự
│     - Validate Temperature (0.0-1.0), max_iterations (1-10)
│
├── [LAYER 2] Semantic Cache Check
│     - Normalize query → MD5 hash → dict lookup
│     - HIT: Trả THINK + FINAL ngay, skip toàn bộ pipeline GPU
│     - MISS: Đi tiếp xuống lớp 3
│
├── [LAYER 3] Event Queue (asyncio.Queue maxsize=100)
│     - Ngăn spam event làm treo RAM server
│     - Nếu đầy: Drop oldest và thêm mới (không crash)
│
├── [LAYER 4] GLOBAL_SEMAPHORE (asyncio.Semaphore(2))
│     - Bức tường lửa VRAM — tối đa 2 request chạy đồng thời
│     - Request thứ 3+ nhận QUEUE_WAITING event, chờ slot trống
│     - Timeout cứng 120s — tự cancel nếu treo quá lâu
│
└── AgentEngine → Ollama (GPU)
```

---

## 4. Chi tiết Kỹ thuật

### 4.1 Global Semaphore — Bức tường lửa VRAM mới
```python
# server.py — Khởi tạo 1 lần khi server start
GLOBAL_SEMAPHORE = asyncio.Semaphore(2)  # Tối đa 2 luồng GPU đồng thời

# Trong event_generator():
if GLOBAL_SEMAPHORE.locked():
    yield f"data: {json.dumps({'event': 'QUEUE_WAITING', ...})}\n\n"

async with GLOBAL_SEMAPHORE:  # Request 3+ tự chờ ở đây
    engine = AgentEngine(...)
    engine_task = asyncio.create_task(engine.run(...))
```
> Semaphore tự động xếp hàng các request thừa thông qua asyncio event loop — không cần viết queue thủ công.

### 4.2 Request ID (Distributed Tracing)
```python
req_id = str(uuid.uuid4())[:8]  # 8 ký tự cho gọn — ví dụ: "a3f7b12c"

# Mọi log đều kèm req_id để trace request từ đầu đến cuối
logger.info(f"[{req_id}] ⚙️ Bắt đầu xử lý...")
logger.info(f"[{req_id}] ✅ Hoàn tất.")
logger.warning(f"[{req_id}] ⚠️ Hủy Job. Lý do: Timeout")
```

### 4.3 SSE Event Contract — Hợp đồng Backend ↔ Frontend
**Key quan trọng là `event` (không phải `type`):**
```json
{"event": "THINK",        "data": "Đang phân tích câu hỏi..."}
{"event": "ACT",          "data": "Gọi tool: search_document"}
{"event": "OBSERVE",      "data": "Tìm thấy 3 kết quả..."}
{"event": "FINAL_ANSWER", "data": "Câu trả lời cuối cùng..."}
{"event": "QUEUE_WAITING","data": "Đang chờ cấp phát VRAM..."}
{"event": "PING",         "data": "keep-alive"}
{"event": "ERROR",        "data": "Mô tả lỗi..."}
```
> ⚠️ **Không bao giờ đổi key `event` thành `type`** — Frontend parse theo key này.

### 4.4 PING Keep-Alive (Chống SSE timeout)
```python
wait_timeout = 0.05       # Check queue mỗi 50ms
ping_threshold = 60       # 60 ticks × 50ms = 3 giây không có event → gửi PING

ping_counter += 1
if ping_counter >= ping_threshold:
    yield f"data: {json.dumps({'event': 'PING', 'data': 'keep-alive'})}\n\n"
    ping_counter = 0
```
> Giữ kết nối SSE sống khi Agent đang "suy nghĩ" (không có output trong 3s).

### 4.5 Queue Flush trước khi kết thúc
```python
# Sau khi engine_task.done() → Flush nốt event còn kẹt trong Queue
while not queue.empty():
    try:
        item = queue.get_nowait()
        yield f"data: {json.dumps(item)}\n\n"
    except asyncio.QueueEmpty:
        break
```
> Đảm bảo không bỏ sót event nào dù engine đã kết thúc trước khi kịp yield.

### 4.6 Graceful Cancel (Client Disconnect + Timeout)
```python
if is_timeout or is_disconnected:
    reason = "Timeout" if is_timeout else "Client Disconnected"
    engine_task.cancel()
    try:
        await engine_task   # Đợi cancel thật sự hoàn tất (dọn VRAM)
    except asyncio.CancelledError:
        pass
    yield f"data: {json.dumps({'event': 'ERROR', 'data': f'Hệ thống ngắt ({reason})'})}...\n\n"
    return
```

### 4.7 RAG Reload API (Zero-downtime)
```python
@app.post("/admin/reload-rag")
async def reload_rag():
    success = await asyncio.to_thread(global_rag.reload)  # Chạy trong ThreadPool
    if success:
        semantic_cache.clear()  # Xóa cache cũ để RAG mới phát huy
    return {"status": "success/error"}
```
> Việc reload chạy trong thread riêng (`asyncio.to_thread`) — event loop không bị chặn.

### 4.8 SSE Headers Production (Chống Nginx Buffering)
```python
return StreamingResponse(
    event_generator(),
    media_type="text/event-stream",
    headers={
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no"   # Quan trọng khi đứng sau Nginx proxy
    }
)
```

---

## 5. Stateful RAG — Khởi tạo 1 lần, dùng cho tất cả
```python
# Khởi tạo GLOBAL khi server start (không khởi tạo lại mỗi request)
global_embedder = LocalRAG.initialize_embedder()
global_index, global_chunks = LocalRAG.initialize_vector_store(global_embedder)
global_rag = LocalRAG(embedder=global_embedder, vector_store=global_index, chunks=global_chunks)
```
> MiniLM embedder chạy CPU-only — nhường toàn bộ VRAM cho LLM. FAISS index tồn tại trong RAM suốt vòng đời server.

---

## 6. Nhật ký Fix lỗi (Chỉ dành cho Dev)

| Bug | Nguyên nhân | Fix |
|---|---|---|
| **FIX 1**: Event bị nuốt | Quên `yield item` sau khi lấy từ queue | Thêm `yield f"data: {json.dumps(item)}\n\n"` |
| **FIX 1**: UI giật/đơ | Không nhường CPU cho Event Loop | Thêm `await asyncio.sleep(0)` cuối mỗi tick |
| **FIX 2**: Timeout block SSE | `asyncio.wait_for(engine_task)` chặn stream | Dùng `engine_task.done()` + check trong loop |
| **FIX 3**: UI treo spinner | Không gửi ERROR event khi ngắt | Thêm `yield ERROR event` trước `return` |
| **FIX 3**: Thông báo chờ sai | Hiện QUEUE_WAITING dù Queue chưa đầy | Kiểm tra `GLOBAL_SEMAPHORE.locked()` trước |
| **FIX 4**: VRAM Zombie | `engine_task.cancel()` nhưng không await | `await engine_task` trong try/except CancelledError |
| **FIX 5**: `except` trống | Ẩn lỗi thật sự | Bắt lỗi cụ thể: `asyncio.QueueEmpty`, `asyncio.QueueFull` |

---

## 7. Cấu trúc mã nguồn thay đổi

| File | Vai trò | Thay đổi |
|---|---|---|
| `server.py` | FastAPI Backend — "The New Gateway" | Viết mới hoàn toàn |
| `app.py` | Streamlit Dumb Client | Refactor: chỉ gọi HTTP + render SSE |
| `core/semantic_cache.py` | Cache MD5 | Viết mới |
| `core/telemetry.py` | PII Mask + JSONL log | Viết mới |
| `core/local_rag.py` | LocalRAG + reload() | Thêm `reload()` method |
| `Archive/gateway.py` | PriorityQueueGateway cũ | **Di chuyển vào Archive** |

---

## 8. Khởi động Hệ thống

```bash
# Terminal 1 — Backend (BẮT BUỘC chạy trước)
python -m uvicorn server:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 — Frontend (Chạy sau khi Backend đã ready)
python -m streamlit run app.py --server.port 8501
```

---
**Kết luận:** Phase 6 đã loại bỏ sự phức tạp không cần thiết (gateway.py) và tận dụng sức mạnh của FastAPI async native để tạo ra một hệ thống gọn hơn, ổn định hơn, và dễ mở rộng hơn. FastAPI chính là Gateway tối thượng.
