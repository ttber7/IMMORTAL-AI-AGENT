import os
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
import logging

logger = logging.getLogger(__name__)

# Constants
KNOWLEDGE_DIR = "knowledge_base"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
MAX_CHUNKS = 2
MAX_WORDS_PER_CHUNK = 100 # roughly 130-150 tokens. Two chunks <= 300 tokens

class LocalRAG:
    def __init__(self, embedder=None, vector_store=None, chunks=None):
        self.knowledge_dir = KNOWLEDGE_DIR
        self.embedder = embedder
        self.index = vector_store
        self.chunks = chunks or []
    
    @staticmethod
    def initialize_embedder():
        """Hàm khởi tạo embedder (Cache lớp 1)"""
        logger.info("Đang nạp Embedder Model vào RAM...")
        return SentenceTransformer(EMBEDDING_MODEL)
    
    @staticmethod
    def initialize_vector_store(embedder):
        """Hàm khởi tạo FAISS và nạp dữ liệu (Cache lớp 2)"""
        if not os.path.exists(KNOWLEDGE_DIR):
            os.makedirs(KNOWLEDGE_DIR)
            
        chunks = []
        for filename in os.listdir(KNOWLEDGE_DIR):
            if filename.endswith(".md") or filename.endswith(".txt"):
                filepath = os.path.join(KNOWLEDGE_DIR, filename)
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

                except Exception as e:
                    logger.error(f"Lỗi đọc file {filepath}: {e}")

        dimension = embedder.get_embedding_dimension()
    
        # Dùng cosine similarity (IP + normalize)
        index = faiss.IndexFlatIP(dimension)
        
        if chunks:
            logger.info(f"Đang băm {len(chunks)} chunks vào FAISS...")

            # 👉 CHỈ embed phần context
            texts = [chunk["context"] for chunk in chunks]

            embeddings = embedder.encode(
                texts,
                batch_size=32,
                show_progress_bar=True,
                convert_to_numpy=True
            )
            
            # Chuẩn hóa vector (bắt buộc khi dùng cosine/IP)
            faiss.normalize_L2(embeddings)

            index.add(embeddings)
            logger.info("Nạp dữ liệu FAISS hoàn tất!")
        else:
            logger.warning("Thư mục knowledge_base trống! Quá trình lấy chunks bỏ qua.")
            
        return index, chunks
        
    def search(self, query: str, top_k: int = MAX_CHUNKS) -> str:
        if not self.embedder or not self.index:
            return "RAG Error: Hệ thống chưa được khởi tạo đúng."

        if not self.chunks or self.index.ntotal == 0:
            return "RAG Info: Không có dữ liệu trong Knowledge Base."
            
        query_vector = self.embedder.encode([query], convert_to_numpy=True)
        faiss.normalize_L2(query_vector)
        
        distances, indices = self.index.search(query_vector, top_k)

        # --- [FIX]: Ép Threshold cực thấp (0.05) để vớt tài liệu tiếng Việt ---
        if len(distances[0]) > 0:
            TOP_SCORE = distances[0][0]
            if TOP_SCORE < 0.05: 
                return "Không tìm thấy thông tin liên quan trong tài liệu nội bộ."
            THRESHOLD = 0.05 
        else:
            return "Không tìm thấy thông tin liên quan trong tài liệu nội bộ."
        # ----------------------------------------------------------------------

        scored_results = []

        for i in range(len(indices[0])):
            idx = indices[0][i]
            score = distances[0][i]

            if idx != -1 and idx < len(self.chunks) and score >= THRESHOLD:
                scored_results.append((score, self.chunks[idx]))

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
