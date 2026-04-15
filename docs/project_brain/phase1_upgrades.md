# 🚀 NÂNG CẤP & ƯU TIÊN - GIAI ĐOẠN 1
**Tên Phase:** Foundation & VRAM Initialization  
**Ngày tạo:** 2026-03-24 | **Cập nhật cuối:** 2026-04-15

---

## ✅ ĐÃ HOÀN THÀNH TRONG PHASE 1

| Hạng mục | Mô tả | Kết quả |
|---|---|---|
| Nền tảng AgentEngine | Vòng lặp Thought→Action→Observation đầu tiên | ✅ Hoạt động |
| VRAM Hard-lock | Ép num_ctx=2048, num_gpu=20 | ✅ VRAM ổn định <3GB |
| Tool Calculate | Công cụ tính toán với Regex bảo mật | ✅ Hoạt động |
| Resource Monitor | Đọc NVML theo thời gian thực | ✅ Accurate |
| Cold-Start Fix | Timeout 120s cho lần nạp model đầu | ✅ Không crash |

---

## 🎯 NHỮNG GÌ PHASE 1 CHƯA CÓ (=> Basis cho các Phase sau)

1. **Không có vòng lặp Self-Repair**: Nếu LLM trả JSON sai, Agent bị crash ngay. *(Đã fix ở Phase 2)*
2. **Không có Adaptive Router**: Luôn dùng cùng 1 model, không xét VRAM. *(Đã fix ở Phase 2)*
3. **Không có UI (Terminal only)**: Kỹ sư phải đọc console thủ công. *(Đã fix ở Phase 3)*
4. **Không có tìm kiếm Internet hay RAG**: Chỉ trả lời từ training data. *(Đã fix ở Phase 4)*

---

## 💡 NHỮNG GÌ CÓ THỂ NÂNG CẤP TƯƠNG LAI

### Ưu tiên Cao
- **🔧 Dynamic num_gpu**: Tự động điều chỉnh số layers GPU dựa trên kích thước model (3B vs 8B vs 14B).
  - Logic: Nếu model < 4B → 20 layers / Nếu 4-8B → 16-18 layers / Nếu > 8B → reject.
  
- **🔧 Quantized Models (Q4/Q5)**: Nạp các phiên bản quantized để giảm 30-40% VRAM.
  - Ví dụ: `llama3.2:3b-instruct-q4_K_M` thay vì `llama3.2:3b`.

### Ưu tiên Trung bình
- **📊 VRAM Profiler**: Ghi lại VRAM trước/sau mỗi request để phân tích xu hướng memory leak.
- **🔁 Auto Model Reload**: Nếu phát hiện VRAM leak, tự restart Ollama process.

### Ưu tiên Thấp (Tương lai xa)
- **GPU Sharing**: Nghiên cứu tách VRAM cho 2 model nhỏ chạy song song thay vì 1 model lớn.
- **CPU Offloading**: Dùng RAM CPU để offload một phần model khi VRAM bị áp lực.

---

## 📝 BÀI HỌC RÚT RA TỪ PHASE 1

> **"Không bao giờ để Ollama tự quyết định số layers. Phần cứng 4GB không thể tha thứ sai lầm nào."**

- num_gpu là thông số QUAN TRỌNG nhất, quyết định toàn bộ sự ổn định.
- Cold start 70-90s là BÌNH THƯỜNG với model phi3:mini/llama3.2:3b trên T2000.
- `pynvml` chính xác hơn `nvidia-smi` cho mục đích monitor real-time.
