import json
import os
import re
import threading
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Khóa an toàn cho việc ghi file từ nhiều Thread (Background Tasks)
_file_lock = threading.Lock()

# --- PII Regex Patterns (Vietnam Focus) ---
# Dùng List of Tuples để ĐẢM BẢO TUYỆT ĐỐI thứ tự ưu tiên (Dài/Phức tạp -> Ngắn/Đơn giản). Pre-compile Regex để tăng tốc độ xử lý đệ quy (10-20% boost)
PII_PATTERNS = [
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", re.IGNORECASE)),
    ("IP_ADDRESS", re.compile(r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b", re.IGNORECASE)),
    ("CREDIT_CARD", re.compile(r"\b(?:\d[ -]*?){13,16}\b(?=\D|$)", re.IGNORECASE)),
    ("TAX_CODE", re.compile(r"\b\d{10}(?:-\d{3})?\b", re.IGNORECASE)),
    ("CCCD", re.compile(r"\b\d{12}\b", re.IGNORECASE)),
    ("VN_PHONE", re.compile(r"\b(0|\+84)[35789]\d{8}\b", re.IGNORECASE)),
    ("CMND", re.compile(r"\b\d{9}\b", re.IGNORECASE)),
]

def anonymize_text(text: str) -> str:
    """Xóa bỏ các thông tin PII khỏi văn bản để bảo vệ quyền riêng tư."""
    if not isinstance(text, str):
        return text
        
    sanitized = text
    # Duyệt qua List có thứ tự
    for pii_type, compiled_pattern in PII_PATTERNS:
        # Sử dụng pattern đã compile
        sanitized = compiled_pattern.sub(f"[HIDDEN_{pii_type}]", sanitized)

    return sanitized

def anonymize_dict(data: dict) -> dict:
    """Xóa bỏ PII của toàn bộ value trong dict"""
    sanitized_data = {}
    for key, value in data.items():
        if isinstance(value, str):
            sanitized_data[key] = anonymize_text(value)
        elif isinstance(value, dict):
            sanitized_data[key] = anonymize_dict(value)
        elif isinstance(value, list):
            # Duyệt đệ quy chuẩn xác cho cả Dict nằm trong List
            sanitized_list = []
            for item in value:
                if isinstance(item, str):
                    sanitized_list.append(anonymize_text(item))
                elif isinstance(item, dict):
                    sanitized_list.append(anonymize_dict(item))
                else:
                    sanitized_list.append(item)
            sanitized_data[key] = sanitized_list
        else:
            sanitized_data[key] = value
    return sanitized_data

# Hàm này sẽ chạy trong FastAPI Background Tasks
# Thêm req_id để đồng bộ với log Terminal
def log_agent_interaction(req_id: str, query: str, success: bool, error_msg: str = None, execution_time: float = 0.0):
    """Ghi log non-blocking xuống file JSONL phục vụ Continuous Learning"""
    try:
        # Khởi tạo biến now duy nhất để tránh lệch mili-giây
        now = datetime.now()
        current_date = now.strftime("%Y-%m-%d")
        
        # 🟢 FIX: Dùng đường dẫn tuyệt đối để chắc chắn thư mục logs được tạo ở thư mục gốc của dự án
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        log_dir = os.path.join(base_dir, "logs")
        log_file = os.path.join(log_dir, f"agent_metrics_{current_date}.jsonl")

        os.makedirs(log_dir, exist_ok=True)
        
        # Lưu raw data, sau đó mới đẩy qua hàm lọc
        raw_log_entry = {
            "req_id": req_id,
            "timestamp": now.isoformat(),
            "query": query,
            "success": success,
            "error_message": error_msg if error_msg else None,
            "execution_time_sec": round(execution_time, 2)
        }

        # Lọc sạch toàn bộ object bất kể thêm bao nhiêu key mới
        safe_log_entry = anonymize_dict(raw_log_entry)
        
        # Ghi append siêu tốc
        # Lock luồng trước khi chọc vào file hệ thống
        with _file_lock:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(safe_log_entry, ensure_ascii=False) + "\n")
        
        # Micro-optimization chặn việc khởi tạo f-string nếu đang ở mode INFO
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"[{req_id}] [Telemetry] Saved log entry.")

    except Exception as e:
        logger.error(f"[{req_id}] [Telemetry Error] Không thể ghi log: {e}")
