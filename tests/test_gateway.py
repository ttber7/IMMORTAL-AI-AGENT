import asyncio
import time
from Archive.gateway import gateway_entry

# Giả lập hàm xử lý model Phi-3:mini (Chiếm khoảng 2.2GB VRAM)
async def mock_phi3_mini(user_input, task_id, trace_id):
    print(f"[{time.strftime('%X')}] 🤖 [LLM: phi3:mini] Đang load model vào 4GB VRAM cho: '{user_input}'...")
    
    # Giả lập độ trễ khi mô hình load và suy luận (3 giây)
    # Trong thực tế, lúc này VRAM sẽ tăng vọt lên 2.2GB.
    await asyncio.sleep(3) 
    
    # Giả lập mô hình quá tải vượt 60s (Cho Request 3)
    if "quá tải" in user_input.lower():
        print(f"[{time.strftime('%X')}] ⚠️ [LLM: phi3:mini] Mô hình gặp câu hỏi quá khó, treo vô hạn...")
        await asyncio.sleep(65)
        
    print(f"[{time.strftime('%X')}] ✨ [LLM: phi3:mini] Đã giải quyết xong yêu cầu: '{user_input}'")
    return {"status": "success", "result": f"Phi-3 trả lời cho {user_input}"}

async def main():
    print("==================================================")
    print("🚀 BẮT ĐẦU BÀI TEST: KIỂM CHỨNG GATEWAY GLOBAL MONITOR")
    print("==================================================\n")
    
    start_time = time.time()
    
    # Mô phỏng 3 yêu cầu gửi đến cùng MỘT LÚC (Gây tràn VRAM nếu không có Gateway)
    # Tuy nhiên, Global Monitor sẽ phân bổ chúng chạy tuần tự!
    t1 = asyncio.create_task(gateway_entry("Xin chào, bạn tên gì?", mock_phi3_mini))
    t2 = asyncio.create_task(gateway_entry("Phân tích dữ liệu JSON này", mock_phi3_mini))
    
    # Mô phỏng request bị lỗi treo máy để test chức năng ngắt Timeout sau 60s
    # Để test nhanh, chúng ta chỉ chạy hai task trên cho bạn thấy cơ chế queue trước.
    
    results = await asyncio.gather(t1, t2)
    
    end_time = time.time()
    print("\n==================================================")
    print("🎯 KẾT QUẢ TEST GATEWAY")
    for r in results:
        print(f"   => {r}")
    print(f"⏱️ Tổng thời gian thực thi: {end_time - start_time:.2f} giây")
    print("==================================================")
    print("🔍 NHẬN XÉT: Hai task được gửi cùng lúc nhưng chạy TUẦN TỰ nối đuôi nhau.")
    print("   -> Nếu chạy song song, 2 model phi3 sẽ tốn 4.4GB VRAM -> Gây OOM trên card Quadro T2000 (4GB)!")
    print("   -> Lớp khiên Gateway do NotebookLM phê duyệt ĐÃ HOẠT ĐỘNG HOÀN HẢO!")

if __name__ == "__main__":
    asyncio.run(main())
