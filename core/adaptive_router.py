import os

# Cần cài đặt: pip install pynvml
try:
    import pynvml
except ImportError:
    print("Vui lòng cài đặt thư viện quản lý GPU: pip install nvidia-ml-py")

class AdaptiveRouter:
    def __init__(self):
        self.vram_threshold_mb = 1500  # Ngưỡng tối thiểu để chạy model 8B
        self.default_model = "llama3.2:3b"  # [ERR-1 FIX] phi3:mini hallucinate -> dùng llama3.2:3b
        try:
            pynvml.nvmlInit()
            self.gpu_available = True
        except Exception as e:
            self.gpu_available = False
            print("⚠️ Không tìm thấy GPU NVIDIA hoặc Driver. Chế độ chạy CPU.")
            
    def __del__(self):
        """Destructor để tránh NVML Memory Leak"""
        if self.gpu_available:
            try:
                pynvml.nvmlShutdown()
            except:
                pass

    def get_free_vram(self):
        if not self.gpu_available:
            return 0
        handle = pynvml.nvmlDeviceGetHandleByIndex(0) # Card Quadro T2000 (Index 0)
        info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        return info.free / 1024**2  # Chuyển sang MiB

    def analyze_complexity(self, user_input: str) -> dict:
        """
        Scoring System (Heuristic) để đánh giá độ phức tạp tránh gọi LLM phân loại tốn VRAM.
        Trả về dict chứa task_type và điểm số.
        """
        score: int = 0
        user_input_lower = user_input.lower()
        
        # 1. Phát hiện Tool Task (Mock)
        tool_keywords = ["tính", "+", "-", "*", "/", "thời tiết"]
        if any(kw in user_input_lower for kw in tool_keywords):
            return {"task_type": "tool", "score": score}
        
        # 2. Chấm điểm theo độ dài
        words = len(user_input.split())
        if words > 100:
            score += 3
        elif words > 40:
            score += 1
            
        # 2. Chấm điểm theo Keyword tư duy (Reasoning)
        reasoning_keywords = ["phân tích", "so sánh", "tổng hợp", "đánh giá", "tại sao", "kế hoạch"]
        for kw in reasoning_keywords:
            if kw in user_input_lower:
                score += 2
                
        # 3. Phân loại Code (Coding Task)
        coding_keywords = ["code", "lập trình", "python", "javascript", "html", "thuật toán", "bug"]
        is_coding = any(kw in user_input_lower for kw in coding_keywords)
        
        # Quyết định Task Type
        if is_coding:
            return {"task_type": "code", "score": score}
        elif score >= 3:
            return {"task_type": "reasoning", "score": score}
        else:
            return {"task_type": "fast", "score": score}

    def route_task(self, user_input: str):
        """
        Quyết định dùng model dựa trên hệ thống điểm ngầm và VRAM thực tế.
        """
        free_vram = self.get_free_vram()
        print(f"📊 [ROUTER] VRAM CPU Check: {free_vram:.2f} MiB")

        if free_vram < 800 and self.gpu_available:
            print("🚨 [CRITICAL] VRAM quá thấp! Trả về trạng thái REJECT_TASK để bảo vệ T2000.")
            return "REJECT_TASK" 

        # 1. Chấm điểm câu hỏi
        analysis = self.analyze_complexity(user_input)
        print(f"⚖️ [ROUTER] Phân tích: Loại Task={analysis['task_type']}, Điểm Khó={analysis['score']}")

        # 2. Multi-model strategy (Khung logic có sẵn, nhưng ưu tiên card 4GB hiện tại)
        if analysis["task_type"] == "code":
            # Nếu máy xịn có thể dùng codellama, nhưng ở T2000 ta map qua llama3 hoặc phi3
            target_model = "llama3:8b" if free_vram > self.vram_threshold_mb else self.default_model
            print(f"💻 Task Lập trình (Yêu cầu Coder) -> Định tuyến: {target_model}")
            return target_model
            
        elif analysis["task_type"] == "reasoning":
            # Task suy luận sâu (có thể map mistral)
            target_model = "llama3:8b" if free_vram > self.vram_threshold_mb else self.default_model
            print(f"🧠 Task Suy luận sâu (Score {analysis['score']}) -> Định tuyến: {target_model}")
            return target_model
            
        elif analysis["task_type"] == "tool":
            print(f"🛠️ Task Công cụ (Tính toán/Thời tiết) -> Định tuyến: {self.default_model} (Tiết kiệm VRAM)")
            return self.default_model
            
        else:
            print(f"⚡ Task Giao tiếp nhanh/Đơn giản -> Định tuyến: {self.default_model}")
            return self.default_model

    def get_dynamic_params(self, is_retry: bool = False) -> dict:
        free_vram = self.get_free_vram()
        
        # Đảm bảo dùng đúng tên biến chứa tên model của AdaptiveRouter
        model_name = getattr(self, "model_name", getattr(self, "default_model", "llama3.2:3b"))
        base_layers = 32 if "phi3" in model_name else 28

        # Mặc định (Trạng thái lý tưởng)
        num_gpu = base_layers
        num_predict = 300

        # 🛡️ BẢO VỆ KÉP: Hạ GPU nếu VRAM thấp HOẶC đang phải Retry (cứu hộ)
        if free_vram < 1200 or is_retry:
            num_gpu = max(16, base_layers - 4)
            print(f"📉 Bảo vệ VRAM (Free: {free_vram:.1f}MB, Retry: {is_retry}) -> Ép GPU layers xuống: {num_gpu}")

        # ✂️ CẮT GIẢM TOKEN: Ép AI trả lời ngắn gọn khi đang sửa lỗi
        if is_retry:
            num_predict = 150 # Siết chặt hơn một chút (150 thay vì 200) để chống ảo giác tuyệt đối
            print(f"🔁 Retry Mode -> Ép num_predict xuống: {num_predict}")

        return {
            "num_gpu": num_gpu,
            "num_predict": num_predict,
            "num_ctx": 2048,
            "num_thread": 4,
            "low_vram": True
        }

# --- VÍ DỤ TÍCH HỢP ---
if __name__ == "__main__":
    router = AdaptiveRouter()
    # Giả lập task nghiên cứu chuyên sâu về code
    target_model = router.route_task("Viết code python tổng hợp và phân tích dữ liệu")
    print(f"🚀 Model được chọn: {target_model}")