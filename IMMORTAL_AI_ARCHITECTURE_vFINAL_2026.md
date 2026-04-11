# IMMORTAL AI ARCHITECTURE: Tóm tắt Cải tiến Phase 3 & 4

Tài liệu này tổng hợp chi tiết các quyết định kiến trúc và đoạn code trọng yếu đã được thực hiện trong Giai đoạn 3 (Tối ưu Core & Error Handling) và Giai đoạn 4 (Local RAG & Native Search).

---

## 🚀 GIAI ĐOẠN 3: TỐI ƯU CORE ENGINE & ERROR HANDLING
Trong Phase 3, hệ thống đã được "khoác áo giáp" để chống chịu với môi trường 4GB VRAM khắc nghiệt. Các nâng cấp tập trung vào việc quản lý vòng lặp hành động, nhận diện lỗi JSON và trích xuất dữ liệu an toàn.

### 1. Trích xuất JSON an toàn chặn Hallucination
**Mục đích**: Chặn đứng các phản hồi ngớ ngẩn hoặc định dạng markdown bọc ngoài của LLM.
**Đoạn code lưu ý (`core/agent_engine.py`)**:
```python
def extract_json_safe(text: str) -> str:
    """Trích xuất JSON an toàn bằng cách tìm block { } ngoài cùng"""
    start = text.find('{')
    end = text.rfind('}')
    if start == -1 or end == -1:
         raise ValueError("LLM_NO_JSON_FOUND: Không tìm thấy block JSON trong phản hồi.")
    return text[start:end+1]
```

### 2. Sửa Memory Limit (Sliding Window Context)
**Mục đích**: Tránh Token Overflow gây Crash VRAM khi chat kéo dài.
**Đoạn code lưu ý (`core/agent_engine.py`)**:
```python
# 🔴 FIX MEMORY: Sliding Window Context (Giới hạn 10 tin nhắn)
MAX_HISTORY = 10
if len(self.messages) > MAX_HISTORY:
    # Giữ lại Câu hỏi đầu tiên của User (self.messages[0])
    keep_amount = MAX_HISTORY - 1
    if self.messages[-keep_amount]["role"] == "assistant":
        keep_amount += 1
    self.messages = [self.messages[0]] + self.messages[-keep_amount:]
```

### 3. Vòng lặp hành động và Prompt Trừng Phạt
**Mục đích**: Xử lý triệt để lỗi khi LLM cố chấp gọi đi gọi lại 1 công cụ đã lỗi.
**Đoạn code lưu ý (`core/agent_engine.py`)**:
```python
# [NÂNG CẤP]: Đổi role thành user và ép nó phải 'answer'
prompt_hinh_phat = (
    f"KẾT QUẢ TỪ CÔNG CỤ:\n{self.observation}\n\n"
    "-> HÃY ĐỌC KẾT QUẢ TRÊN VÀ TRẢ LỜI NGƯỜI DÙNG BẰNG KEY 'answer'. "
    "TUYỆT ĐỐI KHÔNG GỌI LẠI CÔNG CỤ NỮA!"
)
self.messages.append({"role": "user", "content": prompt_hinh_phat})
```

---

## ⚡ GIAI ĐOẠN 4: NATIVE SEARCH & LOCAL RAG
Bứt phá khỏi rào cản của giao thức MCP rườm rà. Hệ thống được chuyển sang xử lý song song offline RAG và Native Python Search giúp tối giản hóa JSON Parser cho model 3B.

### 1. Native DuckDuckGo Search
**Mục đích**: Thay vì request MCP nặng nề, code tích hợp trực tiếp thư viện `duckduckgo_search` và cố tình nén gọn String (loại bỏ \n, cắt ngắn đoạn) để không là phình to Context LLM.
**Đoạn code lưu ý (`core/agent_engine.py`)**:
```python
def tool_web_search(query: str) -> str:
    """Tìm kiếm trên Internet sử dụng DuckDuckGo"""
    try:
        results = DDGS().text(query, max_results=3)
        formatted_results = []
        for r in results:
            formatted_results.append({
                "title": r.get("title", ""),
                "snippet": r.get("body", "").replace("\n", " ")[:300]
            })
        return json.dumps(formatted_results, ensure_ascii=False)
    except Exception as e:
        return f"Lỗi Web Search: {e}"
```

### 2. Tối Ưu Chunking & Băm FAISS Vector
**Mục đích**: Thay vì băm bừa bãi, chia theo `\n\n` và ngắt nhỏ theo từng câu nhỏ bảo vệ 300 token limit.
**Đoạn code lưu ý (`core/local_rag.py`)**:
```python
# --- SMART COMPRESSION ---
sentences = p.split(". ")
result = []
total_words = 0

for s in sentences:
    words = s.split()
    if total_words + len(words) > MAX_WORDS_PER_CHUNK:
        break
    result.append(s)
    total_words += len(words)
compressed = ". ".join(result).strip()

# Dùng cosine similarity (IP + normalize)
index = faiss.IndexFlatIP(dimension)
...
faiss.normalize_L2(embeddings)
index.add(embeddings)
```

### 3. Caching 3-Layers Chống Sập Streamlit UI
**Mục đích**: Giao diện Streamlit render lại liên tục. 3 lớp `@st.cache_resource` để giữ Model trên GPU và hack tốc độ load ban đầu (Cold-Start Prewarm).
**Đoạn code lưu ý (`app.py`)**:
```python
@st.cache_resource
def get_embedder_cache():
    """Khởi tạo mô hình nhúng văn bản (Cache lớp 1)"""
    embedder = LocalRAG.initialize_embedder()
    # [PRE-WARM HACK]: Khởi động model ngay lập tức để nạp vào RAM
    embedder.encode(["hello"])
    return embedder

@st.cache_resource
def get_vector_store_cache(_embedder):
    """Khởi tạo FAISS Vector Store (Cache lớp 2)"""
    return LocalRAG.initialize_vector_store(_embedder)

@st.cache_resource
def get_engine_cache():
    """Khởi tạo một Dictionary duy nhất để quản lý Engine (Cache lớp 3)"""
    return {} # Trả về một từ điển trống
```

Tất cả đã sẵn sàng hoạt động ở môi trường VRAM < 3.2GB một cách mượt mà nhất!
