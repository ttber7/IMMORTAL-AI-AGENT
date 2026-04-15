# 📌 NHỮNG ĐIỂM LƯU Ý TRIỂN KHAI - GIAI ĐOẠN 4
**Tên Phase:** The Knowledge Layer (Local RAG & Web Search)  
**Ngày hoàn thành:** 2026-04-12  
**Trạng thái:** ✅ Hoàn thành  

---

## 🔴 CÁC SAO ĐỎ KHÔNG ĐƯỢC PHÉP VI PHẠM

1. **KHÔNG nạp Embedder lên GPU**: Model `all-MiniLM-L6-v2` BẮT BUỘC chạy CPU-only để nhường toàn bộ VRAM cho LLM.
2. **KHÔNG để FAISS Index trên GPU**: Dùng `faiss-cpu` chứ không phải `faiss-gpu`.
3. **KHÔNG để RAG trả về chuỗi > 500 ký tự**: Chunk quá dài làm phình Context, ảnh hưởng VRAM.

---

## ⚠️ LƯU Ý KỸ THUẬT CHÍNH

### 1. Threshold FAISS quan trọng (Đặc thù tiếng Việt)
```python
THRESHOLD = 0.05  # Cosine similarity tối thiểu
# Nếu score < 0.05 → trả "Không tìm thấy" thay vì kết quả sai
if TOP_SCORE < 0.05: 
    return "Không tìm thấy thông tin liên quan trong tài liệu."
```
Ngưỡng 0.05 được chọn sau nhiều lần thử nghiệm với văn bản tiếng Việt. Không tùy ý tăng/giảm.

### 2. Cấu trúc thư mục Knowledge Base
```
knowledge_base/
├── internal_docs/       # Tài liệu nội bộ công ty
├── project_specs/       # Đặc tả dự án
└── personal_notes/      # Ghi chú cá nhân
```
Chỉ đặt file TXT và Markdown. **KHÔNG đặt file PDF** chưa được convert sang TXT.

### 3. Chunking Strategy - 300 words/chunk
```python
MAX_WORDS_PER_CHUNK = 300
# Chunk nhỏ → tìm kiếm chính xác hơn
# Chunk lớn → context giàu hơn nhưng nhiễu hơn
# 300 words là điểm cân bằng cho model 3B
```

### 4. Web Search - Giới hạn 3 kết quả
```python
results = DDGS().text(query, region='vn-vi', max_results=3)
# region='vn-vi' → ưu tiên kết quả tiếng Việt
# max_results=3 → tránh Context quá dài
```
Cắt snippet xuống còn 300 ký tự để không làm phình JSON.

### 5. Tool Priority Logic (Thứ tự ưu tiên tìm kiếm)
Theo System Prompt:
1. `search_document` trước (tài liệu nội bộ)
2. Nếu "Không tìm thấy" → `web_search` sau
3. KHÔNG gọi web_search khi đã có kết quả RAG tốt

### 6. Tự động Reload RAG (Phase 4 Pre-requisite)
Khi thêm file mới vào `knowledge_base/`, phải restart app để FAISS reindex.  
**Phase 6 mới có API reload online.**

---

## 📋 CHECKLIST KIỂM TRA SAU TRIỂN KHAI PHASE 4

- [ ] Embedder chạy trên CPU (không dùng CUDA)
- [ ] FAISS Index build thành công với file trong knowledge_base/
- [ ] Threshold 0.05 hoạt động đúng (không trả kết quả rác)
- [ ] Web Search trả về JSON hợp lệ trong < 5 giây
- [ ] Agent biết fallback từ RAG sang Web khi không tìm thấy
- [ ] Chunk 300 words không làm tràn context LLM
