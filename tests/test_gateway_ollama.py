import asyncio
import json
import time
import urllib.request
from Archive.gateway import gateway_entry

# Cấu hình API của máy chủ Ollama chạy trên Local
OLLAMA_URL = "http://localhost:11434/api/generate"

def call_ollama_sync(prompt, model="phi3:mini"):
    """Hàm đồng bộ gọi Ollama qua HTTP API nội bộ."""
    data = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_gpu": 32,         # Ép số lớp chạy trên GPU (Phi-3 có 32 lớp)
            "num_ctx": 2048,       # ⚡ Giới hạn ngữ cảnh 2048
            "num_thread": 4,       # Giới hạn luồng (CPU) để máy bớt nóng
            "low_vram": True,      # Kích hoạt chế độ tiết kiệm VRAM của Ollama
            "temperature": 0.2     # Ngăn chặn AI nói nhảm (Hallucination)
        }
    }
    
    def run_sync():
        try:
            req = urllib.request.Request(OLLAMA_URL, json.dumps(data).encode('utf-8'))
            req.add_header('Content-Type', 'application/json')
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode('utf-8'))
                return result.get('response', '')
        except Exception as e:
            return f"LLM_NETWORK_ERROR: {str(e)}"
            
    return run_sync()

async def real_llm_task(user_input, task_id, trace_id):
    print(f"\n[{time.strftime('%X')}] 🤖 [LLM: phi3:mini] Đang ĐẨY TRỰC TIẾP VÀO VRAM CHO: '{user_input}'...")
    
    # Chuyển call đồng bộ sang luồng riêng để không block Vòng lặp sự kiện (Event Loop) của asyncio
    start_time = time.time()
    response_text = await asyncio.to_thread(call_ollama_sync, user_input, "phi3:mini")
    end_time = time.time()
    
    print(f"[{time.strftime('%X')}] ✨ [LLM: phi3:mini] Đã trả lời trong {end_time - start_time:.2f}s!")
    print(f"👉 Trả lời: {response_text.strip()}\n")
    return {"status": "success", "result": response_text}

async def main():
    print("================================================================")
    print("🚀 BÀI TEST THỰC TẾ TRÊN GPU: GATEWAY + OLLAMA (PHI-3:MINI)")
    print("================================================================\n")
    print("🚨 LƯU Ý: Phải đảm bảo Ollama đã cài đặt và model 'phi3:mini' đã được tải.")
    print("Bạn có thể tải model trước bằng lệnh: ollama run phi3:mini\n")
    
    start_time = time.time()
    
    # Tạo 2 yêu cầu thực tế tới GPU
    t1 = asyncio.create_task(gateway_entry("Giải thích thuyết tương đối hẹp trong 1 câu.", real_llm_task))
    t2 = asyncio.create_task(gateway_entry("Dịch câu 'Hello World' sang tiếng Việt, Pháp và Nhật.", real_llm_task))
    
    await asyncio.gather(t1, t2)
    
    end_time = time.time()
    print("==================================================")
    print("🎯 KẾT QUẢ TEST GATEWAY THỰC TẾ TRÊN OLLAMA")
    print(f"⏱️ Tổng thời gian thực thi: {end_time - start_time:.2f} giây")
    print("==================================================")
    print("🔍 NHẬN XÉT: Lệnh gọi qua API thực tế được Gateway bảo vệ!")
    print("Card NVIDIA của bạn chỉ phải thầu 1 model tại mọi thời điểm!")

if __name__ == "__main__":
    asyncio.run(main())
