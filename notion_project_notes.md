# PROJECT: IMMORTAL AI AGENT

This is a comprehensive Mermaid flowchart for an "Immortal AI Agent" system. Here's what I can help you with:

Code Improvements:

* The --> syntax should be --> for Mermaid arrows
* Consider adding subgraph blocks to visually group related components (e.g., Initialization, Memory, Execution)
* The retry logic E3 -- Low Score --> E2[Retry < 2] could be made more explicit with a decision node
Architecture Highlights:

* Resilience patterns: Circuit breaker, idempotency checks, backpressure handling, and timeout controls
* Adaptive routing: Smart selection between small/large models based on task complexity
* Partial failure handling: New logic to handle tool failures gracefully with partial results
* Data quality: Drift detection and dead letter queue for outlier handling
* Learning loop: Memory updates and skill refinement with dataset curation for Unsloth
Potential Enhancements:

* Add monitoring/alerting nodes after the observability layer
* Consider adding a feedback loop from DLQ back to earlier stages
* Add error handling paths for each major component
* Include metrics collection points (latency, success rate, etc.)
Would you like me to help you fix the arrow syntax, add subgraphs for better organization, or explain any specific component in more detail?



> [!NOTE]
> 🧪 Thông số Kỹ thuật "Cứng" (System Config - Lock)
- VRAM Limit: 4GB (Quadro T2000)
- Global Timeout: 60s (Cancellation Token)
- Tool Timeout: 30s
- Max LLM Retry: 2 lần (Hạ Temperature mỗi lần)
- Prompt Versioning: Luôn gắn tag vX.X vào mỗi lần thay đổi câu lệnh

## 🛡️ Danh mục Module & Trạng thái Triển khai (Master Task List)



## 📓 Nhật ký Dead Letter Queue (DLQ Manual Log)

Dán các log lỗi vào bên dưới đây:

> [!NOTE]
> CHECK-POINT CUỐI NGÀY 25/03/2026:
- Gateway v1: ✅ Hoàn thành (Đã test thành công với GlobalMonitor).
- Token Budget: ✅ Hoàn thành (Sliding window hoạt động tốt).
- Adaptive Router: 🔵 Đang làm (Mai bắt đầu code Logic chọn model).

Ghi chú: Đã test Gateway thành công, bảo vệ được VRAM 4GB. Mai bắt đầu code Logic cho Router để tự động chọn model 3B vs 8B.

📝 Cập nhật (25/03/2026): Đã thay đổi Global Timeout thành 180s (Điều chỉnh dựa trên thực tế nạp model phi3:mini trên Quadro T2000 tốn ~70-90s).

🚨 KHẨN (Bug Fix - Tình trạng Timeout kéo dài): Kiến trúc Gateway vừa tái thiết kế: Phân tách Queue Timeout (600s) và Execution Timeout trên GPU (300s) để tránh việc Task tiếp theo bị tính sai thời gian ngâm hàng đợi. (Cập nhật sau chạy thực tế phi3:mini ngốn nhiều hơn 180s cho Cold Start + Gen text).

🔒 Lệnh bài VRAM (25/03/2026): Để đảm bảo model phi3:mini không "ăn lẹm" lên 5GB VRAM do cơ chế tự nới rộng KV Cache mặc định của Ollama, mọi lệnh gọi API sẽ bị ép thông số `{"num_ctx": 2048}`. Việc này khóa chặt KV cache ở mức ~400MB, giữ tổng VRAM luôn < 3.0GB (Tuyệt đối an toàn cho Quadro T2000).

🏆 KẾT QUẢ DEBUG (25/03/2026): Đã thiết lập thành công Kiến trúc Bảo vệ VRAM 4GB. Các lỗi sinh ra do CPU Fallback (WinError 10061) và Tràn Shared Memory (Dung lượng VRAM > 5.0GB) đã được fix bằng 4 tùy chọn bắt buộc gửi cho Ollama API: "num_gpu: 32" (Đẩy hết layer lên GPU), "num_ctx: 2048" (Nén KV Cache), "num_thread: 4" và "low_vram: True". Thời gian trả lời rút từ 180s xuống còn 14-20s (Tuy model Phi-3 có hiện tượng sinh text hơi linh tinh nhưng kiến trúc chốt chặn VRAM đã hoàn toàn vững vàng).

## 🚀 Giai đoạn 2: Phát triển Core Engine Agent

[x] 1. Xây dựng Agent Engine: Vòng lặp Tư duy (Thought -> Action -> Observation) gọi Tools để xử lý tác vụ tương tác thật.
[x] 2. Cơ chế Self-Correction (Bất tử): Bắt các phản hồi "rác" của LLM -> Tự giảm Temperature -> Tự động Retry.
[x] 3. Hoàn thiện Bộ Định Tuyến (Adaptive Router): Phân loại Task để quyết định gọi phi3:mini (nhẹ) hay llama3 (nặng).
> [!NOTE]
> Giai đoạn 2: Phát triển Core Engine Agent đã hoàn thành (30/03/2026). Agent đã đạt độ hoàn thiện cao với cơ chế Bất Tử (Self-Repair), Hardening VRAM 4GB và Cấp phát Tài nguyên Động.



## Nhật ký Hoàn thiện Core Engine - Immortal AI Agent (30/03/2026)

Hôm nay chúng ta đã đạt được cột mốc quan trọng: 🏗️ Hoàn thiện Giai đoạn 2 (Core Engine) với độ ổn định cực cao, sẵn sàng cho các phần cứng hạn chế (VRAM 4GB).

### 🏆 Những gì đã làm được

* 1. Sửa lỗi Logic Vòng lặp (The Core Fix): Chuyển sang while loop với retry_count để cho phép Agent tự sửa lỗi mà không mất lượt suy nghĩ chính.
* 2. Hardening Tầng Tài nguyên: Tự độ hạ GPU layers và giới hạn tokens khi phát hiện VRAM thấp hoặc đang Retry.
* 3. Fail-Safe & Resilience: Exponential Backoff cho lỗi mạng và Sliding Window Context để tối ưu bộ nhớ.
* 4. Bảo mật & Kiểm soát: Regex chặn mã độc toán học và Type Safety cho tham số công cụ.
### 🐞 Các Bug đã gặp và Phương pháp Fix

Chi tiết các lỗi logic vòng lặp, tràn KV Cache và rò rỉ Context đã được xử lý triệt để trong phiên làm việc hôm nay. Hệ thống hiện tại đã đạt trạng thái Bất Tử (Immortal) về mặt vận hành.

# Giai đoạn 3: The Command Center (Trực quan hóa & Giám sát Hệ thống)

Mục tiêu Tiêu điểm: Đưa "The Immortal AI Agent" từ Terminal lên một Web Dashboard (Streamlit). Biến nó thành một trạm điều khiển (Command Center) cho phép kỹ sư nhìn thấu luồng suy nghĩ (X-Ray Vision), can thiệp trực tiếp vào siêu tham số (Hyperparameters), và giám sát VRAM theo thời gian thực.

### 🛠️ Epic 1: Khởi tạo Giao diện Lõi (Core UI Integration)

[ ] 1. Thiết lập Không gian làm việc: Tạo file app.py. Cấu hình Streamlit layout dạng "Wide" để có không gian cho Dashboard.
[ ] 2. Tích hợp Async-Sync: Xử lý cầu nối giữa kiến trúc bất đồng bộ (asyncio) của Agent Engine và kiến trúc đồng bộ (Sync) của Streamlit.
[ ] 3. Quản lý Trạng thái (Session State): Dùng st.session_state để lưu trữ đối tượng AgentEngine và lịch sử chat, đảm bảo không bị khởi tạo lại model mỗi lần UI render.
### 🔬 Epic 2: X-Ray Vision (Bóc tách Luồng Suy nghĩ FSM)

[ ] 1. Cửa sổ Lõi (User Chat): Xây dựng giao diện chat truyền thống (st.chat_message) để nhập prompt và hiển thị Final Answer.
[ ] 2. Giám sát Vòng lặp ReAct (Real-time Streamer): - Hiển thị theo thời gian thực các bước: THINK -> ACT -> OBSERVE (Sử dụng st.status hoặc st.expander để nhóm các logs lại một cách gọn gàng).
[ ] 3. Chế độ Gỡ lỗi (Dev Inspector): - Tạo một Tab/Sidebar hiển thị Raw JSON Response từ LLM để kiểm chứng lỗi sinh text mà không cần nhìn Console.
### 📊 Epic 3: Telemetry Dashboard (Giám sát Tài nguyên & Sức khỏe)

[ ] 1. Radar VRAM: Gọi module pynvml (đã có trong Adaptive Router) để hiển thị thanh Progress Bar VRAM thực tế của Quadro T2000 ngay trên giao diện.
[ ] 2. Thống kê Hiệu năng (Metrics Board): - Đọc file agent_metrics.json và hiển thị các chỉ số (st.metric): Tổng số Runs, Tỉ lệ Thành công, Độ trễ trung bình (Avg Latency).
[ ] 3. Đèn báo Cầu dao (Circuit Breaker Status): - Đèn tín hiệu hiển thị số lần Retry hiện tại của Network, JSON, và Tools.
### 🎛️ Epic 4: Dynamic Control Panel (Bảng Điều khiển Động)

[ ] 1. Ghi đè Định tuyến (Router Override): - Một Dropdown menu cho phép tắt Adaptive Router để ép hệ thống chạy llama3.2:3b hoặc phi3:mini phục vụ mục đích Stress Test.
[ ] 2. Thanh trượt Siêu Tham Số (Hyperparameter Sliders): - Điều chỉnh trực tiếp Temperature và Max Iterations trên UI để kiểm tra ngưỡng ảo giác (Hallucination Threshold) của SLM.
[ ] 3. System Prompt Editor: - Một Text Area cho phép chỉnh sửa "Lệnh Cưỡng Chế" trực tiếp trên web và lưu vào Session để test các chiến thuật Prompt Engineering ngay lập tức.
---



