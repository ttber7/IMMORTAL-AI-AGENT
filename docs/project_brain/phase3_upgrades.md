# 🚀 NÂNG CẤP & ƯU TIÊN - GIAI ĐOẠN 3
**Tên Phase:** The Command Center (Streamlit UI & Telemetry)  
**Ngày tạo:** 2026-04-11 | **Cập nhật cuối:** 2026-04-15  

---

## ✅ ĐÃ HOÀN THÀNH TRONG PHASE 3

| Hạng mục | Mô tả | Kết quả |
|---|---|---|
| Streamlit UI cơ bản | Layout wide, chat interface | ✅ Hoạt động |
| AsyncBridge | Cầu nối async/sync | ✅ Không crash Event Loop |
| X-Ray Status | Hiển thị THINK/ACT/OBSERVE | ✅ Real-time |
| VRAM Radar | Progress bar VRAM live | ✅ Cập nhật theo TTL=1s |
| Cache 3-tầng | Embedder, FAISS, RAG | ✅ Không VRAM leak |
| Model Selector | Dropdown chọn nhanh model | ✅ Hot-swap |
| Metrics Dashboard | Success rate, Latency | ✅ Từ agent_metrics.json |
| Turbo Mode | Toggle for Speed | ✅ Temp=0, Iter=3 |

---

## 💡 NHỮNG GÌ CÓ THỂ NÂNG CẤP TƯƠNG LAI

### Ưu tiên Cao (Phase 6 sẽ thực hiện)
- **🔧 Multi-page App**: Tách app.py thành nhiều trang (Chat / Dashboard / Admin / Logs).
- **🔧 Real-time Streaming UI**: Hiển thị token của LLM ngay khi sinh ra thay vì chờ hoàn tất. Dùng `st.write_stream()`.
- **🔧 Dumb Client (Phase 6)**: Tách toàn bộ logic Core Engine sang FastAPI, UI chỉ gọi HTTP.

### Ưu tiên Trung bình
- **📊 VRAM Timeline Chart**: Vẽ đồ thị VRAM theo thời gian (dùng `st.line_chart`).
- **🎨 Custom CSS**: Thêm màu sắc, font chữ đẹp hơn (Google Font Inter/Outfit).
- **🔍 Search History**: Cho phép tìm kiếm theo keyword trong lịch sử chat.

### Ưu tiên Thấp (Tương lai xa)
- **Dark/Light Mode Toggle**: Cho phép user chuyển chế độ màu sắc.
- **Export Chat**: Tính năng xuất lịch sử chat ra PDF/Markdown.
- **Mobile Responsive**: Thiết kế tương thích màn hình nhỏ.

---

## 📝 BÀI HỌC RÚT RA TỪ PHASE 3

> **"Streamlit không phải là công cụ hoàn hảo cho AI Chat — nhưng đủ nhanh để prototype. Tách UI ra khi production."**

- `@st.cache_resource` là helper quan trọng nhất của Streamlit với AI workloads.
- `asyncio.run()` bị conflict với Streamlit thread — luôn dùng `new_event_loop()`.
- Status placeholder gọi `empty()` sau khi xong để tránh rác UI tích lũy.
- Đừng render NVML mỗi tick — luôn bọc qua cache TTL=1s-2s.
