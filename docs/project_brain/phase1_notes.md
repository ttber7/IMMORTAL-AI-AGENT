# 📌 NHỮNG ĐIỂM LƯU Ý TRIỂN KHAI - GIAI ĐOẠN 1
**Tên Phase:** Foundation & VRAM Initialization  
**Ngày hoàn thành:** 2026-03-24  
**Trạng thái:** ✅ Hoàn thành  
**Hardware:** NVIDIA Quadro T2000 (4GB VRAM)

---

## 🔴 CÁC SAO ĐỎ KHÔNG ĐƯỢC PHÉP VI PHẠM

1. **VRAM Ceiling = 4GB.** Không được phép nạp model vượt quá VRAM vật lý. Mọi lệnh gọi Ollama đều phải kèm `"num_ctx": 2048`.
2. **KHÔNG dùng model lớn hơn 8B.** Với VRAM 4GB, llama3:8B là giới hạn tuyệt đối. Model phi3:mini (3.8B) là lựa chọn an toàn nhất.
3. **KHÔNG để Ollama tự quyết định layers.** Luôn ép `num_gpu: 20-24` để ngăn Ollama allocate bừa lên đến 32 layers.

---

## ⚠️ LƯU Ý KỸ THUẬT CHÍNH

### 1. Khởi động Ollama trước khi chạy App
```bash
# Đảm bảo Ollama đang chạy
ollama serve
# Kiểm tra model đã tải chưa
ollama list
```
Nếu model chưa load: `ollama pull phi3:mini` hoặc `ollama pull llama3.2:3b`.

### 2. Cấu hình Options BẮBT BUỘC khi gọi Ollama API
```python
"options": {
    "num_gpu": 20,      # Layers trên GPU - KHÔNG tự ý tăng quá 24
    "num_ctx": 2048,    # KV Cache cứng - Giữ nguyên
    "num_thread": 4,    # CPU threads
    "low_vram": True,   # Chế độ tiết kiệm RAM
    "repeat_penalty": 1.1  # Ngăn lặp văn bản
}
```

### 3. Kiểm tra NVML trước khi deploy
```python
import pynvml
pynvml.nvmlInit()
# Nếu lỗi "NVML not found" -> Cài: pip install pynvml
```

### 4. Lỗi "Connection Refused" (Port 11434)
- Nguyên nhân: Ollama chưa chạy hoặc bị block firewall.
- Fix: Chạy `ollama serve` trên terminal riêng trước khi start app.

### 5. Cold Start (Lần đầu load model rất chậm ~70-90s)
- KHÔNG dùng timeout nhỏ hơn 120s ở lần load đầu.
- Dùng `stream=True` ở mode debug để thấy process.

---

## 📋 CHECKLIST TRƯỚC KHI CHẠY PH 1

- [ ] Ollama service đang chạy (`ollama serve`)
- [ ] Model `llama3.2:3b` hoặc `phi3:mini` đã được tải
- [ ] `pynvml` đã được cài (`pip install pynvml`)
- [ ] VRAM trống tối thiểu 2.5GB trước khi khởi động
- [ ] File `core/resource_monitor.py` đã khởi tạo đúng handle GPU
