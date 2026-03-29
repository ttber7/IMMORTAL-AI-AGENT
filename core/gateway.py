import asyncio
import uuid
import time
from contextlib import asynccontextmanager

# 🛡️ GLOBAL MONITOR: Quản lý trạng thái toàn hệ thống
class GlobalMonitor:
    def __init__(self):
        # Chỉ cho phép 1 task nặng chạy (Bảo vệ 4GB VRAM GPU)
        self.semaphore = asyncio.Semaphore(1)  
        self.error_count = 0
        self.total_tasks = 0

    @asynccontextmanager
    async def access_gate(self, task_id):
        async with self.semaphore:
            print(f"🚀 [GATEWAY] Task {task_id} bắt đầu chiếm GPU...")
            yield
            print(f"✅ [GATEWAY] Task {task_id} đã giải phóng tài nguyên.")

# Khởi tạo Singleton Monitor chung cho toàn bộ Gateway
global_monitor = GlobalMonitor()

# 🏗️ GATEWAY ENTRY POINT
async def gateway_entry(user_input, task_func):
    task_id = str(uuid.uuid4())
    trace_id = f"trace-{int(time.time())}"

    print(f"🆔 [ID] Task: {task_id} | Trace: {trace_id}")

    try:
        # Thời gian chờ tối đa trong hàng đợi (Queue Timeout) - 10 phút
        async with asyncio.timeout(600): 
            async with global_monitor.access_gate(task_id):
                try:
                    # Thời gian thực thi thực tế trên GPU (Execution Timeout) - 300s
                    async with asyncio.timeout(300):
                        result = await task_func(user_input, task_id, trace_id)
                        return result
                except asyncio.TimeoutError:
                    print(f"❌ [TIMEOUT] Task {task_id} bị hủy do chạy trên GPU vượt quá 300s!")
                    return {"status": "error", "msg": "GPU execution timeout exceeded"}

    except asyncio.TimeoutError:
        print(f"❌ [TIMEOUT] Task {task_id} bị hủy do chờ xếp hàng quá 600s!")
        return {"status": "error", "msg": "Queue timeout exceeded"}
    except Exception as e:
        print(f"🔥 [CRITICAL] Lỗi hệ thống: {str(e)}")
        return {"status": "error", "msg": str(e)}

# Mẫu hàm tác vụ AI mô phỏng
async def mock_agent_loop(user_input, task_id, trace_id):
    print(f"   -> Đang phân tích: {user_input}")
    await asyncio.sleep(2) # Giả lập LLM inference
    return {"status": "success", "data": "Kết quả giả lập"}

if __name__ == "__main__":
    # Ví dụ chạy thử
    result = asyncio.run(gateway_entry("Nghiên cứu SQL", mock_agent_loop))
    print(result)
