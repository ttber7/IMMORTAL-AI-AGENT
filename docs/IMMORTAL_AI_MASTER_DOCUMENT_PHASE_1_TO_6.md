# IMMORTAL AI AGENT — MASTER DOCUMENT (Phase 1 → 6)
**Version:** v6.0 — Single Source of Truth  
**Cập nhật cuối:** 2026-04-15  
**Hardware:** NVIDIA Quadro T2000 — 4GB VRAM  
**Mục đích:** Tài liệu tổng hợp duy nhất cho học tập, tham khảo và nâng cấp hệ thống

---

## 📌 MỤC LỤC NHANH

1. [Tổng quan Kiến trúc (Phase 6 Final)](#1-tổng-quan-kiến-trúc)
2. [Luồng Chạy Chi tiết (End-to-End Flow)](#2-luồng-chạy-chi-tiết)
3. [Phase 1 — Foundation](#3-phase-1--foundation--vram-initialization)
4. [Phase 2 — Hardening Core](#4-phase-2--hardening-core-engine)
5. [Phase 3 — Command Center UI](#5-phase-3--command-center-streamlit-ui)
6. [Phase 4 — Knowledge Layer](#6-phase-4--knowledge-layer-local-rag--web-search)
7. [Phase 5 — Concurrency Layer](#7-phase-5--concurrency-layer-priority-queue)
8. [Phase 6 — Microservices](#8-phase-6--microservices-fastapi--sse)
9. [Bảng Thông số Hệ thống (Không đổi)](#9-bảng-thông-số-hệ-thống)
10. [Lộ trình Tương lai](#10-lộ-trình-tương-lai)

---

## 1. TỔNG QUAN KIẾN TRÚC

Hệ thống Immortal AI Agent là một AI cục bộ chạy hoàn toàn offline trên GPU 4GB VRAM, được thiết kế để:
- Xử lý ngôn ngữ tự nhiên bằng LLM nhỏ (llama3.2:3b / phi3:mini) qua Ollama
- Tìm kiếm tài liệu nội bộ bằng RAG (FAISS + sentence-transformers)
- Tìm kiếm Internet bằng DuckDuckGo
- Tính toán toán học an toàn
- Hỗ trợ nhiều người dùng đồng thời qua hàng đợi ưu tiên

### Sơ đồ Kiến trúc Tổng thể (Phase 6 Final)

```
┌────────────────────────────────────────────────────────────────┐
│              NGƯỜI DÙNG (Browser)                              │
└────────────────────────┬───────────────────────────────────────┘
                         │ Gửi câu hỏi
                         ▼
┌────────────────────────────────────────────────────────────────┐
│          STREAMLIT FRONTEND (Port 8501) — "Dumb Client"        │
│  - Render giao diện chat (THINK/ACT/OBSERVE/FINAL)             │
│  - Gửi POST request kèm TOÀN BỘ chat_history (Stateless)      │
│  - Nhận Server-Sent Events (SSE) và stream ra màn hình         │
└────────────────────────┬───────────────────────────────────────┘
                         │ HTTP POST + SSE (httpx.stream)
                         ▼
┌────────────────────────────────────────────────────────────────┐
│          FASTAPI BACKEND (Port 8000) — "Central Brain"         │
│                                                                │
│  [1] Nhận request → Kiểm tra Semantic Cache (MD5 lookup)       │
│       ↓ Cache HIT → Trả về ngay (<1ms, không tốn GPU)         │
│       ↓ Cache MISS → Tiếp tục                                  │
│                                                                │
│  [2] PriorityGateway (VRAM Protector)                          │
│       - 4 Cấp ưu tiên: L0(Chat) > L1(RAG) > L2(General) > L3(Web)  │
│       - Aging: Cứ 10s chờ → tăng 1 cấp (chống Starvation)     │
│       - Backpressure: Từ chối nếu > 10 tasks trong hàng đợi   │
│       - Hysteresis: VRAM < 1.5GB trong 5s → Scale lên 2 Workers │
│                                                                │
│  [3] AgentEngine (ReAct Loop)                                  │
│       THINK → ACT → OBSERVE → (lặp ≤ 5 vòng)                  │
│       ↓ Khi ACT: Gọi Tool phù hợp                             │
│       ↓ Khi OBSERVE: Đưa kết quả vào Context                   │
│       ↓ Khi hết vòng: Trả FINAL hoặc Harvested Data            │
│                                                                │
│  [4] Tools Registry                                            │
│       • tool_calculate(expr)   → Tính toán Regex-safe          │
│       • search_document(query) → RAG / FAISS vector search     │
│       • web_search(query)      → DuckDuckGo vn-vi 3 results    │
│                                                                │
│  [5] Telemetry (Non-blocking BackgroundTask)                   │
│       → PII Mask (CMND/SDT/Email/Bank) → logs/agent_errors.jsonl │
└────────────────────────┬───────────────────────────────────────┘
                         │ HTTP API (Ollama format)
                         ▼
┌────────────────────────────────────────────────────────────────┐
│          OLLAMA (Port 11434) — LLM Inference Engine            │
│  Models: llama3.2:3b (primary) / phi3:mini (fallback)          │
│  Config cứng: num_ctx=2048, num_gpu=20-24, low_vram=True       │
└────────────────────────────────────────────────────────────────┘
```

---

## 2. LUỒNG CHẠY CHI TIẾT (End-to-End Flow)

### Bước 1: User gửi tin nhắn từ Streamlit
```python
# app.py — Stateless POST request
data = {
    "message": "Tìm kiếm tài liệu về kiến trúc VRAM",
    "chat_history": [...]  # TOÀN BỘ lịch sử, không giữ state ở server
}
async with httpx.AsyncClient() as client:
    async with client.stream("POST", "http://localhost:8000/chat", json=data, timeout=180) as r:
        async for line in r.aiter_lines():
            # Parse SSE events: THINK, ACT, OBSERVE, FINAL, ERROR, [DONE]
```

### Bước 2: FastAPI kiểm tra Semantic Cache
```python
# core/semantic_cache.py
def normalize(text: str) -> str:
    return re.sub(r'[^\w\s]', '', text.lower().strip())

cache_key = hashlib.md5(normalize(query).encode()).hexdigest()

if cache_key in _cache:
    return _cache[cache_key]  # Trả về ngay, bỏ qua toàn bộ LLM pipeline
```
→ **Cache HIT**: Trả FINAL trong < 1ms, không tiêu tốn GPU  
→ **Cache MISS**: Chuyển sang bước 3

### Bước 3: PriorityGateway xếp hàng và bảo vệ VRAM
```python
# core/gateway.py — Priority assignment
def classify_priority(message: str) -> int:
    if any(kw in message.lower() for kw in ["tính", "cộng", "trừ"]):
        return 0  # HIGHEST — Calculate
    elif any(kw in message.lower() for kw in ["tài liệu", "đọc", "search doc"]):
        return 1  # HIGH — Local RAG
    elif any(kw in message.lower() for kw in ["tìm", "internet", "web"]):
        return 3  # LOW — Web Search
    return 2  # NORMAL — General

# VRAM Hysteresis (Dynamic Worker Scaling)
if vram_mb < 1500 and (time.monotonic() - _vram_low_since) > 5.0:
    target_workers = 2  # Tăng
else:
    _vram_low_since = time.monotonic()
    target_workers = 1  # Giảm ngay

# Aging — Chống Starvation
age_bonus = min(2, int(wait_seconds // 10))
effective_priority = max(1, task.priority - age_bonus)  # L3→L1 sau 20s, không vượt L0
```

### Bước 4: AgentEngine thực thi vòng lặp ReAct
```python
# core/agent_engine.py — Vòng lặp 2-tầng
iteration = 1          # Số bước TIẾN TRIỂN thật (chỉ tăng khi Tool call thành công)
retry_count = 0        # Số lần TỰ SỬA LỖI trong cùng 1 bước (tối đa 3)
current_temp = 0.4

while iteration <= max_iterations:
    # Lọc bỏ tin nhắn tạm thời (is_temp) ở đầu mỗi bước mới
    if retry_count == 0:
        messages = [m for m in messages if not m.get("is_temp", False)]
    
    # [THINK] Gọi LLM → nhận JSON
    response = ollama.chat(model, messages, options={
        "num_ctx": 2048, "num_gpu": 20, "temperature": current_temp
    })
    
    # Parse JSON an toàn
    raw_json = extract_json_safe(response)  # Tìm block { } ngoài cùng
    parsed = json.loads(raw_json)
    
    if "answer" in parsed:  # FINAL → Kết thúc
        return stream("FINAL", parsed["answer"])
    
    if "action" in parsed:  # ACT → Gọi Tool
        tool_name = parsed["action"]["tool"]
        tool_args = parsed["action"]["args"]
        
        # Gọi tool và stream OBSERVE
        result = TOOLS[tool_name](**tool_args)
        harvested_data.append(result)  # Lưu cho Graceful Degradation
        stream("OBSERVE", result)
        
        iteration += 1  # Tăng iteration chỉ khi tool call thành công
        retry_count = 0
    else:
        # LLM trả JSON sai format → Tự sửa lỗi
        retry_count += 1
        current_temp = max(0.0, current_temp - 0.1)  # Hạ nhiệt độ
        if retry_count > 3:
            iteration += 1
            retry_count = 0

# Graceful Degradation — Hết vòng nhưng có dữ liệu
if harvested_data:
    return stream("FINAL", synthesize_from_harvested(harvested_data))
```

### Bước 5: Tool Execution — 3 công cụ chính

**Tool 1: Calculate (Ưu tiên cao nhất)**
```python
def tool_calculate(expression: str) -> str:
    # Regex chặn mã độc trước khi eval
    if re.search(r'[a-zA-Z_]', expression.replace('e', '').replace('pi', '')):
        return "LỖI: Biểu thức không hợp lệ"
    return str(eval(expression))  # An toàn sau khi qua Regex filter
```

**Tool 2: search_document — RAG với FAISS**
```python
# core/local_rag.py
def search(query: str, top_k: int = 3) -> str:
    query_embedding = embedder.encode([query])  # CPU-only (tiết kiệm VRAM)
    faiss.normalize_L2(query_embedding)
    scores, indices = index.search(query_embedding, top_k)
    
    if scores[0][0] < THRESHOLD:  # THRESHOLD = 0.05 (đặc thù tiếng Việt)
        return "Không tìm thấy thông tin liên quan trong tài liệu."
    
    # Trả về top chunks, tối đa 500 ký tự mỗi chunk
    return "\n---\n".join(chunks[i][:500] for i in indices[0] if scores[0][j] >= THRESHOLD)
```

**Tool 3: web_search — DuckDuckGo**
```python
def tool_web_search(query: str) -> str:
    results = DDGS().text(query, region='vn-vi', max_results=3)
    # Nén JSON: loại bỏ \n, cắt ngắn snippet 300 ký tự
    return json.dumps([{
        "title": r["title"],
        "snippet": r.get("body", "").replace("\n", " ")[:300]
    } for r in results], ensure_ascii=False)
```

### Bước 6: Telemetry — PII Anonymization & Logging
```python
# core/telemetry.py — Chạy trong FastAPI BackgroundTask (Non-blocking)
PII_PATTERNS = [
    (r'\b\d{9,12}\b', '[CMND/CCCD]'),          # CMND/CCCD
    (r'\b(0[3-9])\d{8}\b', '[SDT]'),           # Số điện thoại VN
    (r'\b[\w.-]+@[\w.-]+\.\w+\b', '[EMAIL]'),  # Email
    (r'\b\d{10,16}\b', '[ACCOUNT]'),           # Số tài khoản ngân hàng
]

def anonymize_text(text: str) -> str:
    for pattern, replacement in PII_PATTERNS:
        text = re.sub(pattern, replacement, text)
    return text

async def log_interaction(request, response, error=None):
    # Ghi vào logs/agent_errors.jsonl — JSONL format (1 dòng = 1 record)
    record = {
        "timestamp": datetime.now().isoformat(),
        "query_hash": md5(request.message.encode()).hexdigest(),
        "query_masked": anonymize_text(request.message),  # PII đã mask
        "response_preview": anonymize_text(response[:200]),
        "error": str(error) if error else None
    }
    with open("logs/agent_errors.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
```

### Bước 7: SSE Stream về Streamlit
```python
# server.py — FastAPI SSE Generator
async def event_stream(request: ChatRequest):
    try:
        async for event_type, event_data in gateway.process(request):
            yield f"data: {json.dumps({'type': event_type, 'data': event_data})}\n\n"
        yield "data: [DONE]\n\n"
    except asyncio.CancelledError:
        # Client ngắt kết nối → Cancel task → Giải phóng VRAM ngay
        gateway.cancel_task(task_id)
```

---

## 3. PHASE 1 — FOUNDATION (VRAM Initialization)

**Ngày:** 2026-03-24 | **Trạng thái:** ✅ Hoàn thành

### Mục tiêu
Đặt nền móng cho Agent AI chạy trên GPU 4GB VRAM. Tìm ra "điểm ngọt" cấu hình để Ollama không làm sập hệ thống.

### Thành tựu Kỹ thuật
- **AgentEngine v1**: Vòng lặp cơ bản Thought → Action → Observation
- **VRAM Hard-lock**: `num_ctx=2048` (KV Cache), `num_gpu=20-24` layers, `low_vram=True`
- **Resource Monitor**: Đọc NVML real-time (chính xác hơn nvidia-smi)
- **Tool Calculate**: Công cụ tính toán có Regex bảo mật đầu tiên
- **Cold Start Fix**: Timeout 120s cho lần nạp model đầu tiên (~70-90s)

### Cấu hình Options BẮBT BUỘC (không thay đổi đến cuối dự án)
```python
"options": {
    "num_gpu": 20,       # Layers trên GPU — KHÔNG tự ý tăng quá 24
    "num_ctx": 2048,     # KV Cache cứng — Giữ nguyên mãi mãi
    "num_thread": 4,     # CPU threads
    "low_vram": True,    # Chế độ tiết kiệm RAM
    "repeat_penalty": 1.1  # Ngăn lặp văn bản
}
```

### Bug "Triệu USD" đã xử lý
| Bug | Nguyên nhân | Fix |
|---|---|---|
| Connection Refused | Ollama chưa chạy | Thêm warm-up check trước khi start |
| VRAM Spike 6GB+ | Model tự nạp 32 layers | Ép cứng `num_gpu: 20` |
| Agent "Nín thở" | Không có stream | Dùng `stream=True` để theo dõi |

---

## 4. PHASE 2 — HARDENING CORE ENGINE

**Ngày:** 2026-03-30 | **Trạng thái:** ✅ Hoàn thành

### Mục tiêu
Biến Agent thô sơ thành hệ thống "Bất Tử" — có khả năng tự sửa lỗi, không crash dù LLM trả kết quả rác.

### Thành tựu Kỹ thuật

**1. Kiến trúc While-loop 2 tầng (The Core Fix)**
```python
# TRƯỚC (for-loop — 1 lỗi = mất 1 lượt)
for i in range(max_iterations):
    ...

# SAU (while-loop — lỗi không = mất lượt)
iteration = 1; retry_count = 0
while iteration <= max_iterations:
    if retry_count > 3:
        iteration += 1; retry_count = 0  # Bỏ qua bước bị kẹt
```

**2. Self-Repair — Tự sửa lỗi JSON**
- Phát hiện JSON sai → Bơm prompt sửa lỗi vào Context
- Giảm Temperature 0.1 mỗi lần retry (ép LLM nghiêm túc hơn)
- Bơm ví dụ JSON đúng vào prompt khi retry lần 2+

**3. Context Pollution Fix (Bug tinh vi nhất)**
- Tin nhắn sửa lỗi gán `is_temp: True`
- Lọc sạch `is_temp` ở đầu mỗi bước mới (không để nhiễm Context vòng sau)

**4. Circuit Breaker**
- Network errors > 5 → Ngắt toàn bộ
- JSON errors > 5 → Ngắt toàn bộ

**5. Sliding Window Context**
- Giữ tối đa 10 tin nhắn gần nhất + tin nhắn gốc đầu tiên

**6. Exponential Backoff**
- Lỗi mạng: chờ 2s → 4s → 8s (không retry ngay lập tức)

---

## 5. PHASE 3 — COMMAND CENTER (Streamlit UI)

**Ngày:** 2026-04-11 | **Trạng thái:** ✅ Hoàn thành

### Mục tiêu
Đưa Agent từ Terminal ra giao diện Web Dashboard (Streamlit) có khả năng "nhìn thấu" luồng suy nghĩ AI.

### Thành tựu Kỹ thuật

**1. Cache 3-Tầng — Trái tim của Phase 3**
```python
@st.cache_resource
def get_embedder_cache():    # Lớp 1: Model embedding MiniLM

@st.cache_resource
def get_vector_store_cache(_embedder):  # Lớp 2: FAISS index

@st.cache_resource
def get_engine_cache():      # Lớp 3: AgentEngine container
```

**2. AsyncBridge — Cầu nối Sync/Async**
```python
# Streamlit = Sync, AgentEngine = Async → Cần bridge
try:
    return asyncio.run(_run_async())
except RuntimeError:  # Event loop đang chạy
    loop = asyncio.new_event_loop()
    return loop.run_until_complete(_run_async())
```

**3. X-Ray Vision (THINK/ACT/OBSERVE real-time)**
- `st.status()` hiển thị từng bước Agent đang làm
- `st.expander()` gộp logs gọn gàng
- Raw JSON viewer cho debugging

**4. Telemetry Dashboard**
- VRAM Progress Bar real-time (NVML với TTL cache 1s)
- Metrics: Success Rate, Avg Latency, Total Runs
- Circuit Breaker Status: Network/JSON/Tool retry counts

**5. Dynamic Control Panel**
- Model Selector: Chọn llama3.2:3b / phi3:mini hot-swap
- Temperature Slider: 0.0 → 1.0 không cần restart
- Turbo Mode: Ép temp=0.0, max_iter=3 cho câu hỏi nhanh

---

## 6. PHASE 4 — KNOWLEDGE LAYER (Local RAG & Web Search)

**Ngày:** 2026-04-12 | **Trạng thái:** ✅ Hoàn thành

### Mục tiêu
Phá vỡ rào cản "mù thông tin" — Agent có thể đọc tài liệu nội bộ và tìm kiếm Internet.

### Thành tựu Kỹ thuật

**1. Local RAG System (FAISS + MiniLM)**
- Embedder `all-MiniLM-L6-v2` chạy CPU-only (nhường VRAM cho LLM)
- Chunking: 300 words/chunk, tách theo `\n\n` → câu nhỏ
- FAISS IndexFlatIP (cosine similarity sau L2 normalize)
- Threshold 0.05 (đặc biệt cho tiếng Việt — thực nghiệm tìm ra)
- Thư mục: `knowledge_base/` → tự động index khi khởi động

**2. DuckDuckGo Web Search**
- Region `vn-vi` ưu tiên kết quả tiếng Việt
- Lấy tối đa 3 kết quả, nén snippet còn 300 ký tự
- Loại bỏ `\n` để tránh phình JSON → căng Context LLM

**3. Tool Priority Logic (qua System Prompt)**
- Thứ tự: `search_document` → nếu "Không tìm thấy" → `web_search`
- Agent KHÔNG được gọi web_search khi đã có kết quả RAG tốt

**4. Smart Chunking**
```python
MAX_WORDS_PER_CHUNK = 300
# Tách đoạn văn theo ". " (câu)
# Dừng khi tổng từ > 300 → Chunk sạch, không cắt giữa câu
```

---

## 7. PHASE 5 — CONCURRENCY LAYER (Priority Queue)

**Ngày:** 2026-04-13 | **Trạng thái:** ✅ Hoàn thành

### Mục tiêu
Biến Agent thành "Dịch vụ" — xử lý nhiều request đồng thời mà không làm sập VRAM.

### Thành tựu Kỹ thuật

**1. PriorityQueueGateway**
```
asyncio.PriorityQueue
└── Level 0 (HIGHEST): Calculate, Direct Chat
└── Level 1 (HIGH):    Local RAG
└── Level 2 (NORMAL):  General Reasoning
└── Level 3 (LOW):     Web Search (API ngoài chậm)
```

**2. Aging — Chống Starvation**
```python
# Cứ 10s chờ → tăng 1 cấp (tối đa Level 1, không vượt Level 0)
age_bonus = min(2, int(wait_seconds // 10))
effective_priority = max(1, task.priority - age_bonus)
```

**3. Backpressure**
- Queue tối đa 10 tasks
- Vượt quá → từ chối ngay với thông báo "Hệ thống đang bận"

**4. Task Cancellation**
```python
# Cờ để hủy từ bên ngoài (khi client timeout)
task.is_cancelled = True
# Worker check cờ trước khi bắt đầu
if task_obj.is_cancelled: continue
```

**5. Graceful Degradation (Harvested Data)**
```python
# Thu thập mọi Observation trong suốt quá trình
harvested_data.append(f"Tool `{tool}` tìm thấy: {observation}")
# Khi hết max_iterations → Tổng hợp từ dữ liệu đã thu (không trả lỗi rỗng)
```

**6. Thread-Safety**
```python
# Mọi truy cập vào pending_tasks phải qua Lock
with self.pending_lock:
    task_obj = self.pending_tasks.get(task_id)
```

---

## 8. PHASE 6 — MICROSERVICES (FastAPI + SSE)

**Ngày:** 2026-04-15 | **Trạng thái:** ✅ Production

### Mục tiêu
Tách hệ thống thành 2 tiến trình độc lập — FastAPI là "bộ não" và Streamlit là "giao diện hiển thị".

### Thành tựu Kỹ thuật

**Quyết định lớn nhất Phase 6: Archive `gateway.py` cũ**
- `gateway.py` (Phase 5 — PriorityQueueGateway phức tạp) → di chuyển vào `Archive/gateway.py`  
- FastAPI với `asyncio.Semaphore(2)` native = Gateway tối thượng, gọn hơn 5 lần

**4 Lớp Bảo vệ trong server.py:**
```
[LAYER 1] Pydantic Validator    → Giới hạn messages ≤ 20, query ≤ 2000 ký tự
[LAYER 2] Semantic Cache        → MD5 hash lookup, HIT = trả ngay không tốn GPU  
[LAYER 3] asyncio.Queue(100)    → Ngăn spam event làm treo RAM
[LAYER 4] Semaphore(2)          → Tối đa 2 request GPU đồng thời, timeout 120s
```

**Streamlit Dumb Client (app.py) — Port 8501**
```python
# Gửi TOÀN BỘ messages mỗi request (Stateless)
data = {"messages": [...], "model": m, "temperature": t, "max_iterations": n}
async with httpx.AsyncClient() as c:
    async with c.stream("POST", "http://localhost:8000/chat", json=data) as r:
        async for line in r.aiter_lines():
            event = json.loads(line[6:])
            render_event(event["event"], event["data"])  # key là "event" (không phải "type")
```

**SSE Event Contract — Key là `event` (quan trọng)**
```json
{"event": "THINK",         "data": "Đang phân tích..."}
{"event": "ACT",           "data": "Gọi tool: search_document"}
{"event": "OBSERVE",       "data": "Kết quả tool..."}
{"event": "FINAL_ANSWER",  "data": "Câu trả lời cuối..."}
{"event": "QUEUE_WAITING", "data": "Đang chờ VRAM..."}
{"event": "PING",          "data": "keep-alive"}   
{"event": "ERROR",         "data": "Mô tả lỗi..."}
```

**Request ID Tracing**
```python
req_id = str(uuid.uuid4())[:8]  # "a3f7b12c" — trace từ đầu đến cuối
logger.info(f"[{req_id}] ⚙️ Bắt đầu...")   # Mọi log đều kèm req_id
```

**PING Keep-Alive (3s)**
```python
# Nếu 3s không có event → gửi PING để SSE connection không bị timeout
if ping_counter >= 60:  # 60 ticks × 50ms = 3s
    yield f"data: {{\"event\": \"PING\", \"data\": \"keep-alive\"}}"
```

**RAG Reload (Zero-downtime)**
```python
@app.post("/admin/reload-rag")
async def reload_rag():
    await asyncio.to_thread(global_rag.reload)  # ThreadPool, không block event loop
    semantic_cache.clear()                       # Xóa cache cũ
```

### Khởi động Hệ thống
```bash
# Terminal 1 — BẮT BUỘC chạy trước
python -m uvicorn server:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 — Chạy sau khi Backend đã ready
python -m streamlit run app.py --server.port 8501
```

---

## 9. BẢNG THÔNG SỐ HỆ THỐNG

Đây là các thông số **KHÔNG BAO GIỜ THAY ĐỔI** — được xác định qua thực nghiệm trên Quadro T2000.

| Thông số | Giá trị | Lý do cố định |
|---|---|---|
| `num_ctx` | `2048` | Khóa KV Cache ở mức an toàn (~400MB VRAM) |
| `num_gpu` | `20-24` | Tránh tràn VRAM (mặc định 32 layers sẽ phá hệ thống) |
| `num_thread` | `4` | Tối ưu cho CPU i5/i7 thế hệ mới |
| `low_vram` | `True` | Bắt buộc với GPU < 6GB |
| `repeat_penalty` | `1.1` | Ngăn Agent lặp phản hồi |
| `FAISS Threshold` | `0.05` | Thực nghiệm với văn bản tiếng Việt |
| `MAX_HISTORY` | `10` | Sliding Window — tránh tràn Context |
| `MAX_RETRY/step` | `3` | Self-repair limit — sau đó bỏ qua bước |
| `MAX_ITERATIONS` | `5` | Cân bằng chất lượng/tốc độ |
| `Queue Limit` | `10` | Backpressure — bảo vệ RAM |
| `Task Timeout` | `120s` | Force cancel nếu treo |
| `HYSTERESIS_SECONDS` | `5` | Ổn định VRAM trước khi scale worker |
| `LOW_VRAM_THRESHOLD` | `1500MB` | Ngưỡng kích hoạt Worker thứ 2 |
| `Chunk Size` | `300 words` | RAG: đủ context, không phình LLM input |
| `Web Search Results` | `3` | Tránh phình JSON → căng Context |
| `Backend Port` | `8000` | FastAPI |
| `Frontend Port` | `8501` | Streamlit |
| `Ollama Port` | `11434` | Mặc định |

---

## 10. LỘ TRÌNH TƯƠNG LAI

### Ngắn hạn (Tiếp theo sau Phase 6)
1. **JWT Authentication**: Bearer Token bảo vệ tất cả `/chat` và `/admin/*` endpoints
2. **Rate Limiting**: Giới hạn N requests/phút/IP (`slowapi` library)
3. **Persistent Semantic Cache**: Chuyển từ RAM dict sang Redis để tồn tại qua restart
4. **PDF Support**: Đọc thẳng file PDF bằng `pymupdf` không cần convert tay

### Trung hạn
5. **Prometheus + Grafana**: Monitoring dashboard tự động (VRAM, latency, cache hit rate)
6. **Docker Compose**: Container hóa Backend + Frontend + Ollama thành 1 lệnh `docker-compose up`
7. **Hybrid RAG**: Kết hợp BM25 (từ khóa chính xác) + FAISS (ngữ nghĩa) với Reciprocal Rank Fusion

### Dài hạn
8. **React/Next.js Frontend**: Thay Streamlit bằng app đẹp hơn — Backend KHÔNG cần thay đổi
9. **Mobile App**: iOS/Android kết nối FastAPI — Backend KHÔNG cần thay đổi
10. **Cloud Deployment**: Runpod/Vast.ai cho GPU cloud — Scale ra nhiều máy

---

## TÀI LIỆU THAM KHẢO

- **Mã nguồn chính**: `core/gateway.py`, `core/agent_engine.py`, `core/local_rag.py`, `server.py`, `app.py`
- **Logs**: `logs/agent_errors.jsonl` (JSONL với PII đã mask)
- **Metrics**: `agent_metrics.json` (Success rate, latency, model usage)
- **Knowledge Base**: `knowledge_base/` (Tài liệu nội bộ cho RAG)
- **Notion**: [Trang IMMORTAL AI AGENT](https://www.notion.so/ROJECT-IMMORTAL-AI-AGENT-32d882c4ae0c805cb150ed8bca8bcf55)
- **GitHub**: `https://github.com/ttber7/IMMORTAL-AI-AGENT.git` — nhánh `phase5-dev`

---
*Tài liệu này là Single Source of Truth. Mọi câu hỏi về kiến trúc, triển khai và nâng cấp hệ thống đều có thể tìm thấy câu trả lời tại đây.*
