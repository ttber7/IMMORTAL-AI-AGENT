# 🚀 NÂNG CẤP & ƯU TIÊN - GIAI ĐOẠN 2
**Tên Phase:** Hardening Core Engine (The Immortal Core)  
**Ngày tạo:** 2026-03-30 | **Cập nhật cuối:** 2026-04-15  

---

## ✅ ĐÃ HOÀN THÀNH TRONG PHASE 2

| Hạng mục | Mô tả | Kết quả |
|---|---|---|
| While-loop Architecture | Tách iteration và retry_count | ✅ Không mất lượt khi lỗi |
| Self-Repair JSON | Bơm prompt sửa lỗi vào Context | ✅ 3 lần sửa/bước |
| Circuit Breaker | Ngắt tự động khi lỗi nghiêm trọng | ✅ Bảo vệ hệ thống |
| Exponential Backoff | Chờ 2/4/8s khi lỗi mạng | ✅ Giảm tải Ollama |
| Sliding Window | Cắt History về 10 tin nhắn | ✅ Không tràn Context |
| Math Security | Regex chặn code injection | ✅ An toàn |
| Temperature Cooling | Hạ Temperature dần khi lỗi | ✅ Hạn chế Hallucination |

---

## 🎯 NHỮNG GÌ PHASE 2 CHƯA CÓ

1. **Không có UI**: Vẫn chỉ chạy qua terminal. *(Đã fix ở Phase 3)*
2. **Không có Web Search / RAG**: Ai cũng mù thông tin bên ngoài. *(Đã fix ở Phase 4)*
3. **Không có Priority Queue**: Không thể xử lý nhiều request cùng lúc. *(Đã fix ở Phase 5)*

---

## 💡 NHỮNG GÌ CÓ THỂ NÂNG CẤP TƯƠNG LAI

### Ưu tiên Cao
- **🔧 Smart Retry Strategy**: Phân loại lỗi tinh tế hơn:
  - `LLM_HALLUCINATION` → Giảm Temperature + Thêm ví dụ JSON vào prompt.
  - `TOOL_NOT_FOUND` → Hướng dẫn LLM các tool hợp lệ.
  - `VRAM_OVERFLOW` → Ngắt và báo người dùng nghỉ ngơi 30 giây.

- **🔧 Adaptive max_iterations**: Thay vì cố định 5, tự điều chỉnh dựa trên độ phức tạp của câu hỏi:
  - Câu hỏi ngắn (< 30 ký tự): max_iterations = 3.
  - Câu hỏi dài/phức tạp: max_iterations = 7.

### Ưu tiên Trung bình
- **📊 Error Pattern Analysis**: Ghi log kiểu lỗi JSON thường gặp nhất của từng model để điều chỉnh System Prompt.
- **🔁 Model Fallback Chain**: phi3:mini → llama3.2:3b → từ chối task thay vì crash.

### Ưu tiên Thấp
- **Fine-tuning**: Sau khi thu thập đủ dữ liệu lỗi, fine-tune model 3B để hiểu JSON schema tốt hơn mà không cần nhiều lần retry.

---

## 📝 BÀI HỌC RÚT RA TỪ PHASE 2

> **"LLM 3B không đáng tin tuyệt đối. Hệ thống phải được thiết kế để LLM có thể SAI và vẫn hồi phục được."**

- Tất cả các bug quan trọng nhất đều sinh ra từ việc TIN TƯỞNG quá mức vào LLM.
- `is_temp` là kỹ thuật đơn giản nhất nhưng giải quyết được lớp bug tinh vi nhất (Context Pollution).
- Exponential Backoff không phải là "chờ bừa" mà là nghệ thuật cho hệ thống thở.
