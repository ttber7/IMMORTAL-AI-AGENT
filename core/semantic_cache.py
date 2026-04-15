import hashlib
import re
import logging
import threading
import unicodedata # 🟢 THÊM THƯ VIỆN NÀY (Có sẵn trong Python)
from typing import Optional
from cachetools import LRUCache

logger = logging.getLogger(__name__)

class SemanticCache:
    def __init__(self, maxsize=1000):
        self._cache = LRUCache(maxsize=maxsize)
        # Lưu trữ nội bộ: hash_key -> response_string
        # Trong tương lai có thể mở rộng lưu ra Redis/SQLite
        # 🟢 FIX: Dùng LRUCache giới hạn 1000 câu hỏi thay vì Dict thường
        # Khi user hỏi câu 1001, câu hỏi cũ nhất (ít dùng nhất) sẽ tự động bị xóa khỏi RAM
        # 🟢 FIX 1: Thread-safety cho Cache
        self._lock = threading.Lock()

    def _remove_accents(self, input_str: str) -> str:
        """🟢 HÀM MỚI: Xóa hoàn toàn dấu tiếng Việt"""
        nfkd_form = unicodedata.normalize('NFKD', input_str)
        only_ascii = nfkd_form.encode('ASCII', 'ignore').decode('utf-8')
        # Xử lý riêng chữ đ/Đ
        only_ascii = only_ascii.replace('đ', 'd').replace('Đ', 'D')
        return only_ascii

    def _normalize_query(self, query: str) -> str:
        """Chuẩn hóa câu hỏi siêu sạch"""
        if not query:
            return ""
        q = query.lower()
        q = self._remove_accents(q) # 🟢 GỌI HÀM XÓA DẤU TẠI ĐÂY
        q = re.sub(r'[^\w\s]', '', q)
        q = re.sub(r'\s+', ' ', q).strip()
        return q

    def _hash_query(self, normalized_query: str) -> str:
        return hashlib.md5(normalized_query.encode('utf-8')).hexdigest()

    def get(self, query: str) -> Optional[str]:
        normalized = self._normalize_query(query)
        if not normalized: # 🟢 FIX: Chặn query rỗng sau khi đã chuẩn hóa
            return None
        
        cache_key = self._hash_query(normalized)
        # 🟢 FIX 1: Đọc an toàn trong Lock
        with self._lock:
            if cache_key in self._cache:
                # 🟢 FIX 4: Log nội dung câu hỏi thay vì chỉ mã Hash
                logger.info(f"⚡ [CACHE HIT] {normalized[:50]}...")
                return self._cache[cache_key]
        return None

    def set(self, query: str, response: str) -> None:
        if not response or not query:
            return
            
        normalized = self._normalize_query(query)
        if not normalized: # 🟢 FIX: Không lưu rác vào bộ nhớ đệm
            return
        
        cache_key = self._hash_query(normalized)
        # 🟢 FIX 1: Ghi an toàn trong Lock
        with self._lock:
            self._cache[cache_key] = response
            logger.info(f"💾 [CACHE SET] Lưu vào cache ({len(self._cache)}/1000).")

    def clear(self):
        """Dùng khi cần xóa trắng Cache (Ví dụ: Khi Admin Reload RAG)"""
        with self._lock:
            self._cache.clear()
            logger.info("🗑️ [CACHE CLEARED] Bộ nhớ đệm đã được dọn sạch.")
# Khởi tạo instance Global (Giống như RAG)
# Khởi tạo instance Global chứa tối đa 1000 keys
semantic_cache = SemanticCache(maxsize=1000)
