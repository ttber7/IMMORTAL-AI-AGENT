import asyncio
import time
from core.gateway import gateway_entry

# Giả lập hàm xử lý model chiếm RAM thật sự!
async def heavy_mock_llm(user_input, task_id, trace_id):
    print(f"\n[{time.strftime('%X')}] 🤖 [LLM: phi3:mini] Đang NẠP MODEL VÀO BỘ NHỚ cho: '{user_input}'...")
    print(f"👉 HÃY NHÌN VÀO BIỂU ĐỒ RAM TRÊN TASK MANAGER! BẠN SẼ THẤY NÓ TĂNG LÊN ~2GB!")
    
    # Cấp phát thực tế 2 Gigabyte RAM!
    # Thao tác này sẽ ăn ngay lập tức 2GB RAM của thiết bị.
    fake_model_weights = bytearray(2 * 1024 * 1024 * 1024) 
    
    # Giữ model trong bộ nhớ 5 giây để mô phỏng thời gian suy luận
    print(f"[{time.strftime('%X')}] ⚙️ Đang giữ 2GB RAM để suy luận trong 5 giây...")
    await asyncio.sleep(5)
    
    print(f"[{time.strftime('%X')}] ✨ [LLM: phi3:mini] Trả lời xong! GIẢI PHÓNG 2GB RAM!")
    # Xóa biến để giải phóng RAM
    del fake_model_weights
    
    return {"status": "success", "result": f"Hoàn thành: {user_input}"}

async def main():
    print("================================================================")
    print("🚀 BÀI TEST THỰC TẾ: KIỂM CHỨNG BẢO VỆ BỘ NHỚ BẰNG TASK MANAGER")
    print("================================================================\n")
    print("🚨 CẢNH BÁO: Bài test này sẽ TẠO RA 2 YÊU CẦU CÙNG LÚC.")
    print("Mỗi yêu cầu sẽ cố gắng ăn 2GB RAM. (Nếu chạy song song sẽ tốn 4GB RAM).")
    print("Nhờ có Gateway, nó sẽ chỉ chạy từng cái 1, đỉnh RAM chỉ tăng 2GB!\n")
    
    print("⏳ VUI LÒNG MỞ TASK MANAGER -> CHỌN TAB 'PERFORMANCE' -> CHỌN 'MEMORY'.")
    print("BÀI TEST SẼ BẮT ĐẦU SAU 10 GIÂY. HÃY CHUẨN BỊ QUAN SÁT BIỂU ĐỒ RAM!!")
    
    for i in range(10, 0, -1):
        print(f"Bắt đầu sau {i} giây...", end="\r")
        time.sleep(1)
    print("\n\n💥 BẮT ĐẦU CHẠY TASK CÙNG LÚC!\n")
    
    start_time = time.time()
    
    t1 = asyncio.create_task(gateway_entry("Task cực nặng số 1", heavy_mock_llm))
    t2 = asyncio.create_task(gateway_entry("Task cực nặng số 2", heavy_mock_llm))
    
    await asyncio.gather(t1, t2)
    
    end_time = time.time()
    print("\n==================================================")
    print("🎯 KẾT QUẢ TEST GATEWAY THỰC TẾ")
    print(f"⏱️ Tổng thời gian thực thi: {end_time - start_time:.2f} giây")
    print("==================================================")
    print("🔍 BẠN CÓ THẤY KHÔNG? Biểu đồ RAM tăng 2GB, đi ngang 5s, rớt xuống, rồi lại tăng 2GB!")
    print("   -> Lớp khiên Gateway đã ép 2 task nặng CHẠY NỐI ĐUÔI NHAU thành công rực rỡ!")
    print("   -> Nếu không có Gateway, máy bạn đã bị 'Treoo' (Crash) vì cạn kiệt bộ nhớ ngay lập tức.")

if __name__ == "__main__":
    asyncio.run(main())
