# 📌 NHỮNG ĐIỂM LƯU Ý TRIỂN KHAI - GIAI ĐOẠN 3
**Tên Phase:** The Command Center (Streamlit UI & Telemetry)  
**Ngày hoàn thành:** 2026-04-11  
**Trạng thái:** ✅ Hoàn thành  

---

## 🔴 CÁC SAO ĐỎ KHÔNG ĐƯỢC PHÉP VI PHẠM

1. **KHÔNG khởi tạo AgentEngine ngoài `@st.cache_resource`**: Mỗi lần Streamlit re-run sẽ tạo lại instance mới → VRAM leak.
2. **KHÔNG gọi `asyncio.run()` trong Streamlit thread thẳng**: Phải dùng `AsyncBridge` để tách sang thread mới.
3. **KHÔNG dùng NVML quá thường xuyên**: Bọc qua `@st.cache_data(ttl=1)` để tránh spam GPU driver.

---

## ⚠️ LƯU Ý KỸ THUẬT CHÍNH

### 1. Cache 3-Tầng - Trái tim của Phase 3
```python
@st.cache_resource
def get_embedder_cache():         # Lớp 1: Model embedding
    ...
    
@st.cache_resource
def get_vector_store_cache(_emb): # Lớp 2: FAISS index
    ...
    
@st.cache_resource
def get_local_rag_cache(...):     # Lớp 3: RAG object
    ...
```
**Quy tắc**: Không bao giờ gọi `clear()` trên các cache này khi đổi model — để Ollama tự quản lý VRAM.

### 2. AsyncBridge - Cầu nối giữa 2 thế giới
Streamlit chạy đồng bộ (sync). AgentEngine chạy bất đồng bộ (async). Cần dùng pattern:
```python
try:
    return asyncio.run(_run())
except RuntimeError:  # Event loop đã tồn tại
    loop = asyncio.new_event_loop()
    return loop.run_until_complete(_run())
```

### 3. Status Placeholder - Tránh bị ghi đè UI
Dùng `st.empty()` + `.container()` để ngăn các status update ghi đè lên nhau:
```python
status_placeholder = st.status("...", expanded=True)
with status_placeholder:  # Viết nội dung vào đây
    st.markdown("...")
status_placeholder.empty()  # Dọn sạch sau khi xong
```

### 4. Render Telemetry - 3 Thời điểm Vàng
- **Moment 1 (Init)**: Khi trang load lần đầu.
- **Moment 2 (Pre-Run)**: Ngay trước khi Agent xử lý request.
- **Moment 3 (Post-Run)**: Sau khi có kết quả.

### 5. Lỗi Model Change (Quan trọng)
Khi User chọn model mới qua Dropdown:
- Chỉ cần `st.rerun()` - KHÔNG xóa cache.
- Ollama sẽ tự load model mới vào VRAM khi có request.

---

## 📋 CHECKLIST KIỂM TRA SAU TRIỂN KHAI PHASE 3

- [ ] VRAM không tăng mỗi lần refresh/rerun Streamlit
- [ ] Model thay đổi trong Dropdown không crash app
- [ ] THINK/ACT/OBSERVE hiện lên đúng thứ tự trong `st.status`
- [ ] Thanh VRAM % cập nhật sau mỗi request
- [ ] JSON raw data hiện đúng trong "Raw Data Viewer"
