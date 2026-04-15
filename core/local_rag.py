import os
import faiss
import numpy as np
import re
import time
from sentence_transformers import SentenceTransformer
import logging
import threading

logger = logging.getLogger(__name__)

# Constants
KNOWLEDGE_DIR = "knowledge_base"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
MAX_CHUNKS = 2
MAX_WORDS_PER_CHUNK = 100 # roughly 130-150 tokens. Two chunks <= 300 tokens
MAX_TOTAL_CHUNKS = 5000 # Giới hạn tối đa 5000 chunks (Anti RAM bomb)

# Lấy ngưỡng Threshold từ biến môi trường
THRESHOLD = float(os.getenv("RAG_THRESHOLD", "0.05"))

class LocalRAG:
    def __init__(self, embedder=None, vector_store=None, chunks=None):
        self.knowledge_dir = KNOWLEDGE_DIR
        self.embedder = embedder
        self.index = vector_store
        self.chunks = chunks or []

        self._lock = threading.Lock() # Khóa an toàn
        self._embed_lock = threading.Lock() # Khóa an toàn cho model PyTorch

    def reload(self):
        """Tải lại thư mục knowledge_base vào FAISS Index hiện tại"""
        logger.info("🔄 Bắt đầu tải lại Knowledge Base...")
        start_time = time.time() # Đo lường thời gian

        if not self.embedder:
            logger.error("Không có Embedder để reload.")
            return False
        
        try:
            # Chạy lại logic tạo vector store nhưng dùng embedder hiện có
            new_index, new_chunks = self.initialize_vector_store(self.embedder, self._embed_lock)

            with self._lock:
                self.index = new_index
                self.chunks = new_chunks

            elapsed = time.time() - start_time
            logger.info(f"✅ Tải lại Knowledge Base thành công sau {elapsed:.2f}s!")
            return True
        except Exception as e:
            logger.error(f"❌ Lỗi khi tải lại KB: {e}")
            return False
    
    @staticmethod
    def initialize_embedder():
        logger.info("Đang nạp Embedder Model vào RAM...")
        return SentenceTransformer(EMBEDDING_MODEL)
    
    @staticmethod
    def initialize_vector_store(embedder, embed_lock=None):
        if not os.path.exists(KNOWLEDGE_DIR):
            os.makedirs(KNOWLEDGE_DIR)
            
        chunks = []
        stop_loading = False # 🟢 Bổ sung cờ

        for filename in os.listdir(KNOWLEDGE_DIR):
            if filename.endswith(".md") or filename.endswith(".txt"):
                if stop_loading: # 🟢 Kiểm tra ngay đầu vòng lặp ngoài
                    break

                filepath = os.path.join(KNOWLEDGE_DIR, filename)

                # Bảo vệ RAM, bỏ qua file text > 1MB
                if os.path.getsize(filepath) > 1_000_000:
                    logger.warning(f"⚠️ Bỏ qua {filename} vì dung lượng > 1MB.")
                    continue

                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        content = f.read()

                    # Tách đoạn
                    paragraphs = content.split("\n\n")

                    for i, p in enumerate(paragraphs):
                        p = p.strip()

                        if len(p) > 20:
                            # --- CLEAN TEXT ---
                            p = p.replace("\n", " ").strip()

                            # Tách câu thông minh, hỗ trợ tiếng Việt chuẩn
                            sentences = re.split(r'(?<=[.!?])\s+', p)
                            result = []
                            total_words = 0

                            for s in sentences:
                                words = s.split()
                                if total_words + len(words) > MAX_WORDS_PER_CHUNK:
                                    break
                                result.append(s)
                                total_words += len(words)

                            compressed = ". ".join(result).strip()

                            # fallback nếu lỗi
                            if not compressed:
                                words = p.split()
                                compressed = " ".join(words[:MAX_WORDS_PER_CHUNK])

                            # --- FORMAT CHUẨN ---
                            chunks.append({
                                "id": f"{filename}_{i}",
                                "context": compressed,
                                "source": filename
                            })

                            # Ngắt khẩn cấp nếu vượt rào
                            if len(chunks) >= MAX_TOTAL_CHUNKS:
                                logger.warning(f"Đã đạt giới hạn {MAX_TOTAL_CHUNKS} chunks. Ngừng nạp thêm.")
                                stop_loading = True
                                break
                
                    # Thoát vòng lặp ngoài nếu đã đầy
                    if len(chunks) >= MAX_TOTAL_CHUNKS:
                        break

                except Exception as e:
                    logger.error(f"Lỗi đọc file {filepath}: {e}")

        dimension = embedder.get_embedding_dimension()
        # Dùng cosine similarity (IP + normalize)
        index = faiss.IndexFlatIP(dimension)
        
        if chunks:
            logger.info(f"Đang băm {len(chunks)} chunks vào FAISS...")

            # 👉 CHỈ embed phần context
            texts = [chunk["context"] for chunk in chunks]

            if embed_lock:
                with embed_lock:
                    # Do hàm này chạy ở khởi tạo hoặc reload, có thể không lo tranh chấp,
                    # nhưng về sau nếu có luồng khác gọi thì tốt nhất không dùng chung instance với search.
                    # Ở đây ta giả định việc reload diễn ra an toàn.
                    embeddings = embedder.encode(
                        texts,
                        batch_size=32,
                        show_progress_bar=False, # Tắt progress bar để tránh trôi log server
                        convert_to_numpy=True
                    )
            else:
                embeddings = embedder.encode(texts, batch_size=32, show_progress_bar=False, convert_to_numpy=True)
            
            # Chuẩn hóa vector (bắt buộc khi dùng cosine/IP)
            faiss.normalize_L2(embeddings)

            # 🟢 Lá chắn thép chống Crash FAISS C++
            if index.d != embeddings.shape[1]:
                raise ValueError(f"Lỗi Dimension: FAISS Index ({index.d}) không khớp với Embeddings ({embeddings.shape[1]})")

            index.add(embeddings)
            logger.info("Nạp dữ liệu FAISS hoàn tất!")
        else:
            logger.warning("Thư mục knowledge_base trống! Quá trình lấy chunks bỏ qua.")
            
        return index, chunks
        
    def search(self, query: str, top_k: int = MAX_CHUNKS) -> str:
        # Chặn query rỗng
        if not query or not query.strip():
            return "RAG Info: Câu hỏi truy vấn rỗng."

        # Trích xuất local variables một cách an toàn
        with self._lock:
            current_embedder = self.embedder
            current_index = self.index
            current_chunks = self.chunks

        if not current_embedder or not current_index:
            return "RAG Error: Hệ thống chưa được khởi tạo đúng."

        # 🟢 Micro-opt: Check integer trước khi check list
        if current_index.ntotal == 0 or not current_chunks:
            return "RAG Info: Không có dữ liệu trong Knowledge Base."
        
        # Khóa embedder để chống văng lỗi PyTorch đa luồng
        with self._embed_lock:
            query_vector = current_embedder.encode([query], convert_to_numpy=True)
            
        faiss.normalize_L2(query_vector)
        distances, indices = current_index.search(query_vector, top_k)

        # --- [FIX]: Ép Threshold cực thấp (0.05) để vớt tài liệu tiếng Việt ---
        if len(distances[0]) > 0:
            TOP_SCORE = distances[0][0]
            # 🟢 FIX 3: Log điểm số để Admin dễ dàng tinh chỉnh (Tuning) Threshold
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"[RAG] Top similarity score: {TOP_SCORE:.4f} for query: '{query[:30]}...'")
            if TOP_SCORE < THRESHOLD: 
                return "Không tìm thấy thông tin liên quan trong tài liệu nội bộ."
        else:
            return "Không tìm thấy thông tin liên quan trong tài liệu nội bộ."
        # ----------------------------------------------------------------------

        scored_results = []

        for i in range(len(indices[0])):
            idx = indices[0][i]
            score = distances[0][i]

            if idx != -1 and idx < len(current_chunks) and score >= THRESHOLD:
                scored_results.append((score, current_chunks[idx]))

        scored_results.sort(key=lambda x: x[0], reverse=True)   
        results = [item[1] for item in scored_results]

        if not results:
            return (
                "[DOCUMENT CONTEXT]\n"
                "Không tìm thấy thông tin liên quan trong tài liệu nội bộ.\n"
                "[QUESTION]\n"
                f"{query}"
            )

        formatted_context = ""
        for i, res in enumerate(results, 1):
            formatted_context += (
                f"Tài liệu {i} (Nguồn: {res['source']}):\n"
                f"{res['context']}\n\n"
            )

        # Hard limit bảo vệ model
        formatted_context = formatted_context[:1200]
            
        return (
            "[DOCUMENT CONTEXT]\n"
            f"{formatted_context.strip()}\n"
            "[QUESTION]\n"
            f"{query}"
        )
