# 📌 NHỮNG ĐIỂM LƯU Ý TRIỂN KHAI - GIAI ĐOẠN 2
**Tên Phase:** Hardening Core Engine (The Immortal Core)  
**Ngày hoàn thành:** 2026-03-30  
**Trạng thái:** ✅ Hoàn thành  

---

## 🔴 CÁC SAO ĐỎ KHÔNG ĐƯỢC PHÉP VI PHẠM

1. **KHÔNG sử dụng `for` loop** cho vòng lặp Agent chính. Bắt buộc dùng `while iteration <= max_iterations + retry_count`.  
2. **KHÔNG để LLM retry vô hạn**: `retry_count` bị giới hạn cứng tối đa `3 lần/bước`. Vượt qua → buộc chuyển sang bước tiếp theo.  
3. **KHÔNG để tin nhắn lỗi nhiễm Context mãi mãi**: Message tạm thời `is_temp: True` bắt buộc phải bị lọc sạch ở đầu mỗi vòng lặp.

---

## ⚠️ LƯU Ý KỸ THUẬT CHÍNH

### 1. Cấu trúc 2-tầng Đếm - Quan trọng nhất Phase 2
```python
iteration = 1       # Số bước tiến triển thật (chỉ tăng khi Tool call thành công)
retry_count = 0     # Số lần tự sửa lỗi trong CÙNG 1 bước (tối đa 3)

while iteration <= max_iterations:
    # [CORE LOOP]
    if retry_count > 3:  # Vượt quá: bỏ qua bước này, tiến lên
        iteration += 1
        retry_count = 0
```
**Lý do**: Nếu LLM sinh JSON sai, không nên mất hẳn một iteration. Chỉ cần sửa lỗi nội bộ trong cùng bước đó.

### 2. Giảm Temperature khi sửa lỗi
```python
# Lỗi JSON → Giảm temp xuống để ép LLM nghiêm túc hơn
current_temp = max(0.0, current_temp - 0.1)
# Lượt cuối cùng → Force temp = 0.0 để đảm bảo chính xác
if iteration == max_iterations: current_temp = 0.0
```

### 3. Context Pollution - Bug Tinh vi nhất
- **Triệu chứng**: LLM bị rối loạn ở vòng sau vì đọc thấy tin nhắn lỗi cũ của vòng trước.
- **Fix**: Gán `is_temp: True` cho tin nhắn nhắc lỗi và lọc sạch ở đầu mỗi iteration.
```python
# Đầu mỗi vòng lặp:
if retry_count == 0:
    self.messages = [m for m in self.messages if not m.get("is_temp", False)]
```

### 4. Circuit Breaker - Cầu dao bảo vệ
- Nếu `circuit_breaker["network"] > 5` hoặc `circuit_breaker["json"] > 5`: Kết thúc ngay lập tức.
- Đây là van an toàn cuối cùng chống vòng lặp vô hạn system-wide.

### 5. Exponential Backoff khi lỗi mạng
```python
await asyncio.sleep(2 ** network_retries)  # 2s, 4s, 8s
```
Đừng retry ngay lập tức - Ollama cần thời gian hồi phục.

---

## 📋 CHECKLIST KIỂM TRA SAU TRIỂN KHAI PHASE 2

- [ ] Agent có thể tự sửa lỗi JSON ít nhất 3 lần mà không bị trừ iteration
- [ ] Lịch sử chat bị cắt về 10 tin nhắn sau khi đủ 10 tin nhắn
- [ ] Circuit Breaker kích hoạt khi có >5 lỗi liên tiếp
- [ ] Temperature tự giảm khi có lỗi định dạng
- [ ] Agent không bị crash khi tool `calculate` nhận ký tự không hợp lệ
