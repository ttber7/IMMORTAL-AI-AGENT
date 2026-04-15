# 📌 NHỮNG ĐIỂM LƯU Ý TRIỂN KHAI - GIAI ĐOẠN 5
**Tên Phase:** The Concurrency Layer (Priority Queue & Graceful Degradation)  
**Ngày hoàn thành:** 2026-04-13  
**Trạng thái:** ✅ Hoàn thành  

---

## 🔴 CÁC SAO ĐỎ KHÔNG ĐƯỢC PHÉP VI PHẠM

1. **KHÔNG cho phép hàng đợi chứa hơn 10 tác vụ**: Backpressure limit = 10. Vượt quá → Reject ngay lập tức.
2. **KHÔNG dùng `asyncio.Queue` trực tiếp từ Streamlit thread**: Phải dùng `asyncio.run_coroutine_threadsafe` để submit task vào loop của Gateway.
3. **KHÔNG để Task Level 0 bị Aging vượt qua**: Level 0 (HIGHEST) là BẤT KHẢ XÂM PHẠM. Aging chỉ áp dụng từ Level 1 trở xuống.

---

## ⚠️ LƯU Ý KỸ THUẬT CHÍNH

### 1. Priority Mapping - 4 Cấp độ Ưu tiên
```python
PRIORITY_MAP = {
    "HIGHEST": 0,  # Real-time Chat, Calculate → Trả lời gần như lập tức
    "HIGH":    1,  # Local RAG → Cần đọc FAISS nhưng nhanh
    "NORMAL":  2,  # General reasoning
    "LOW":     3   # Web Search → Chờ API ngoài chậm nhất
}
```

### 2. Aging Mechanism - Chống Starvation
```python
# Cứ mỗi 10 giây, nâng cấp ưu tiên tối đa lên 1 bậc (không vượt Level 1)
age_bonus = min(2, int(wait_time // 10))
new_level = max(1, task.level - age_bonus)  # Không bao giờ vượt Level 1
```

### 3. Task Cancellation Flow
```python
# Khi timeout:
with gateway.pending_lock:
    task = gateway.pending_tasks.get(task_id)
    if task:
        task.is_cancelled = True  # Bật cờ hủy

# Trong Worker Loop - Check cờ trước khi chạy:
if not task_obj or task_obj.is_cancelled:
    continue
```

### 4. Harvested Data - Graceful Degradation
```python
# Sau mỗi Tool call thành công:
self.harvested_data.append(f"Tool `{tool_name}` quan sát được: {self.observation}")

# Khi hết max_iterations:
if self.harvested_data:
    formatted = "\n\n".join([f"- {item}" for item in self.harvested_data[:3]])
    return f"Thông tin tôi thu thập được:\n\n{formatted}"
```

### 5. UI Queue Status - Chỉ update Label, không spam Content
```python
elif event_type == "QUEUE_WAITING":
    # KHÔNG gọi st.markdown() ở đây - chỉ update label
    status_placeholder.update(label=f"⏳ Đang chờ GPU (Vị trí: {display_data})...")
```

### 6. Thread-Safety - Threading Lock bắt buộc
```python
# Mọi truy cập vào self.pending_tasks PHẢI qua lock:
with self.pending_lock:
    task_obj = self.pending_tasks.get(task_id)
```

---

## 📋 CHECKLIST KIỂM TRA SAU TRIỂN KHAI PHASE 5

- [ ] Task Level 0 không bao giờ bị Aging vượt qua Level 0
- [ ] Backpressure từ chối khi > 10 tasks trong hàng đợi
- [ ] Khi đạt max_iterations, Agent trả về Harvested Data thay vì error rỗng
- [ ] Thread-safety: Không có Race Condition khi 2 request đến cùng lúc
- [ ] Timeout 120 giây kích hoạt đúng khi task bị treo
- [ ] UI hiển thị vị trí hàng đợi (Position: N) chính xác
