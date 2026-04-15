# 📚 IMMORTAL AI AGENT — MASTER DOCUMENTATION INDEX
**Cập nhật:** 2026-04-15  
**Dự án:** The Immortal AI Agent (Quadro T2000 / 4GB VRAM)

---

## 🗺️ Bản đồ Tài liệu

Mỗi giai đoạn có **3 loại tài liệu**:

| Loại | Mô tả | Khi nào đọc |
|---|---|---|
| **`phaseX_yyyy.md`** | Tóm tắt kỹ thuật + changeset | Khi muốn hiểu giai đoạn đó đã làm gì |
| **`phaseX_notes.md`** | Lưu ý & Sao đỏ triển khai | Khi deploy hoặc debug |
| **`phaseX_upgrades.md`** | Nâng cấp & Ưu tiên | Khi lên kế hoạch Phase tiếp theo |

---

## 📋 Danh sách File

### 🏗️ PHASE 1: Foundation (VRAM Initialization)
**Ngày:** 2026-03-24 | **Trạng thái:** ✅
- [phase1_initialization.md](./phase1_initialization.md) — Tóm tắt kỹ thuật
- [phase1_notes.md](./phase1_notes.md) — Lưu ý triển khai (num_gpu, num_ctx, Cold Start)
- [phase1_upgrades.md](./phase1_upgrades.md) — Nâng cấp (Quantized models, VRAM Profiler)

### 🛡️ PHASE 2: Hardening Core Engine (The Immortal Core)
**Ngày:** 2026-03-30 | **Trạng thái:** ✅
- [phase2_hardening.md](./phase2_hardening.md) — Tóm tắt kỹ thuật
- [phase2_notes.md](./phase2_notes.md) — Lưu ý triển khai (While-loop, is_temp, Circuit Breaker)
- [phase2_upgrades.md](./phase2_upgrades.md) — Nâng cấp (Smart Retry, Model Fallback Chain)

### 🖥️ PHASE 3: Command Center (Streamlit UI & Telemetry)
**Ngày:** 2026-04-11 | **Trạng thái:** ✅
- [phase3_rag_engine.md](./phase3_rag_engine.md) — Tóm tắt kỹ thuật
- [phase3_notes.md](./phase3_notes.md) — Lưu ý triển khai (Cache 3-tầng, AsyncBridge)
- [phase3_upgrades.md](./phase3_upgrades.md) — Nâng cấp (Multi-page, Streaming UI, Dumb Client)

### 📚 PHASE 4: Knowledge Layer (Local RAG & Web Search)
**Ngày:** 2026-04-12 | **Trạng thái:** ✅
- [phase4_finalization.md](./phase4_finalization.md) — Tóm tắt kỹ thuật
- [phase4_notes.md](./phase4_notes.md) — Lưu ý triển khai (FAISS Threshold, Chunking, DuckDuckGo)
- [phase4_upgrades.md](./phase4_upgrades.md) — Nâng cấp (Hybrid Search, PDF Support, Citation)

### ⚡ PHASE 5: Concurrency Layer (Priority Queue)
**Ngày:** 2026-04-13 | **Trạng thái:** ✅
- [phase5_concurrency.md](./phase5_concurrency.md) — Tóm tắt kỹ thuật
- [phase5_notes.md](./phase5_notes.md) — Lưu ý triển khai (Priority Map, Aging, Thread-Safety)
- [phase5_upgrades.md](./phase5_upgrades.md) — Nâng cấp (Task Dependency, Redis Queue, DLQ)

### 🏗️ PHASE 6: Microservices Layer (FastAPI + SSE)
**Ngày:** 2026-04-15 | **Trạng thái:** ✅ Production
- [phase6_microservices.md](./phase6_microservices.md) — Tóm tắt kỹ thuật
- [phase6_notes.md](./phase6_notes.md) — Lưu ý triển khai (SSE Contract, Semaphore, RAG Reload)
- [phase6_upgrades.md](./phase6_upgrades.md) — Nâng cấp (JWT Auth, Prometheus, Docker, React)

---

## 📊 Tổng quan Kiến trúc (Phase 6)

```
                    ┌─────────────────────────────────┐
                    │     Streamlit (Port 8501)        │
                    │     "Dumb Client"               │
                    │  Send JSON → Receive SSE Events  │
                    └──────────────┬──────────────────┘
                                   │ HTTP POST + SSE
                    ┌──────────────▼──────────────────┐
                    │     FastAPI (Port 8000)          │
                    │     "Central Brain"             │
                    │  ┌──────────────────────────┐  │
                    │  │  Limiter (Semaphore=2)   │  │
                    │  └──────────┬───────────────┘  │
                    │  ┌──────────▼───────────────┐  │
                    │  │  AgentEngine             │  │
                    │  │  (ReAct loop)            │  │
                    │  └──────────┬───────────────┘  │
                    │  ┌──────────▼───────────────┐  │
                    │  │  LocalRAG / WebSearch    │  │
                    │  │  SemanticCache / Telemetry│  │
                    │  └──────────────────────────┘  │
                    └─────────────────────────────────┘
                                   │
                    ┌──────────────▼──────────────────┐
                    │     Ollama (Port 11434)          │
                    │     llama3.2:3b / phi3:mini      │
                    └─────────────────────────────────┘
```

---

## 🔑 Thông Số Hệ thống (Không Thay Đổi)

| Thông số | Giá trị | Lý do |
|---|---|---|
| VRAM Limit | 4GB | Quadro T2000 |
| num_ctx | 2048 | Khóa KV Cache |
| num_gpu | 20-24 layers | Tránh tràn VRAM |
| Max Iterations | 5 (default) | Cân bằng chất lượng/tốc độ |
| Max Retry/step | 3 | Self-repair limit |
| Queue Backpressure | 10 tasks | Bảo vệ RAM |
| FAISS Threshold | 0.05 | Đặc thù tiếng Việt |
| Worker Scaling | Tĩnh (Semaphore 2) | Giới hạn cứng |
| Backend Port | 8000 | FastAPI |
| Frontend Port | 8501 | Streamlit |
