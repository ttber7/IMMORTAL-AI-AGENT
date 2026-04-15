# 🚀 NÂNG CẤP & ƯU TIÊN - GIAI ĐOẠN 4
**Tên Phase:** The Knowledge Layer (Local RAG & Web Search)  
**Ngày tạo:** 2026-04-12 | **Cập nhật cuối:** 2026-04-15  

---

## ✅ ĐÃ HOÀN THÀNH TRONG PHASE 4

| Hạng mục | Mô tả | Kết quả |
|---|---|---|
| Local RAG (FAISS) | Tìm kiếm tài liệu vectorized CPU | ✅ Score threshold 0.05 |
| DuckDuckGo Search | Web search vùng vn-vi | ✅ 3 kết quả nén gọn |
| Smart Chunking | 300 words/chunk, cosine similarity | ✅ Tốc độ index < 1s |
| Search Fallback Logic | RAG →Web nếu không tìm thấy | ✅ Trong System Prompt |
| Embedder CPU-only | all-MiniLM-L6-v2 không dùng VRAM | ✅ VRAM free cho LLM |
| 3-layer Cache | Embedder/FAISS/RAG cached trên app | ✅ No re-init |

---

## 💡 NHỮNG GÌ CÓ THỂ NÂNG CẤP TƯƠNG LAI

### Ưu tiên Cao
- **🔧 Hybrid Search**: Kết hợp BM25 (từ khóa chính xác) + FAISS (ngữ nghĩa) để tăng recall:
  - FAISS tốt với câu hỏi ngữ nghĩa: "Tình hình tài chính công ty như thế nào?"
  - BM25 tốt với truy vấn chính xác: "Doanh thu quý 3 2025 là bao nhiêu?"
  - Kết hợp 2 điểm số bằng **Reciprocal Rank Fusion (RRF)**.

- **🔧 Better Chunking (Semantic Chunking)**: Thay vì cắt cứng theo số từ, cắt theo ranh giới ngữ nghĩa (hết chủ đề/đoạn văn). Dùng `langchain_text_splitters.SemanticChunker`.

- **🔧 RAG Reload API** *(Phase 6 đã có)*: API `POST /admin/reload-rag` không cần restart server.

### Ưu tiên Trung bình
- **📄 PDF Support**: Thêm `pymupdf` để đọc trực tiếp file PDF mà không cần convert tay.
  ```python
  import fitz  # pymupdf
  doc = fitz.open("file.pdf")
  text = "\n".join([page.get_text() for page in doc])
  ```

- **🔍 Multi-hop RAG**: Cho phép Agent tìm kiếm nhiều lần liên tiếp, tổng hợp từ nhiều chunk khác nhau.

- **📊 RAG Quality Metrics**: Đo `Hit Rate` và `MRR` để biết RAG đang trả lời đúng bao nhiêu % câu hỏi.

### Ưu tiên Thấp
- **🌐 Tavily API**: Thay DuckDuckGo bằng Tavily API (kết quả có cấu trúc tốt hơn, ít bị block hơn).
- **📝 Citation**: Trả về tên file/nguồn khi trả lời từ RAG để người dùng biết thông tin đến từ đâu.

---

## 📝 BÀI HỌC RÚT RA TỪ PHASE 4

> **"RAG không phải giải pháp thần kỳ. Chất lượng kết quả phụ thuộc 70% vào chất lượng tài liệu đầu vào."**

- Tài liệu phải "sạch" (không ký tự lạ, không quá nhiều bảng không có ngữ cảnh).
- Threshold 0.05 cho tiếng Việt phát hiện qua thực nghiệm — khác hẳn với tiếng Anh (thường là 0.3+).
- DuckDuckGo đôi khi bị rate-limit. Nếu cần hệ thống production → Tavily hoặc SerpAPI.
- `max_results=3` là giới hạn vàng cho model 3B. Nhiều hơn sẽ làm phình Context.
