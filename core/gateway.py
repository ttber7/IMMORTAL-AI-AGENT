import concurrent.futures
import asyncio
import threading
import uuid
import time
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Callable

logger = logging.getLogger(__name__)

# 📊 PRIORITY LEVELS
PRIORITY_MAP = {
    "HIGHEST": 0,    # Real-time Chat / Calculate
    "HIGH": 1,       # Local RAG
    "NORMAL": 2,     # Default
    "LOW": 3         # Web Search / Complex Reasoning
}

@dataclass(order=True)
class QueuedTask:
    priority: int
    entry_count: int
    task_id: str = field(compare=False)
    payload: Any = field(compare=False)
    future: concurrent.futures.Future = field(compare=False)
    timestamp: float = field(compare=False)
    level: int = field(compare=False)
    is_cancelled: bool = field(default=False, compare=False)

class PriorityGateway:
    _instance = None
    _singleton_lock = threading.Lock()

    def __new__(cls):
        with cls._singleton_lock:
            if cls._instance is None:
                cls._instance = super(PriorityGateway, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized: return
        
        self.loop = None
        self.worker_thread = None
        self.queue = None
        self.semaphore = None
        self.pending_tasks: Dict[str, QueuedTask] = {}
        # 🔥 FIX: Thêm Lock bảo vệ Dictionary khỏi Race Condition đa luồng
        self.pending_lock = threading.Lock() 
        
        self.entry_counter = 0
        self.max_queue_size = 50
        
        self._start_worker_thread()
        self._initialized = True

    def _start_worker_thread(self):
        """Khởi tạo một thread riêng biệt chạy Event Loop cho Gateway toàn cục"""
        self.worker_thread = threading.Thread(target=self._run_loop, daemon=True)
        self.worker_thread.start()
        
        # Chờ loop khởi động
        while self.loop is None or not self.loop.is_running():
            time.sleep(0.1)
        logger.info("🛡️ [GATEWAY] Background worker thread started.")

    def _run_loop(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        # Khởi tạo Queue và Semaphore trong đúng loop
        self.queue = asyncio.PriorityQueue()
        self.semaphore = asyncio.Semaphore(1) # 1 Worker duy nhất bảo vệ VRAM
        
        # Chạy worker và aging loop
        self.loop.create_task(self._worker_loop())
        self.loop.create_task(self._aging_loop())
        
        self.loop.run_forever()

    async def _worker_loop(self):
        """Consumer loop: Rút task từ hàng đợi và thực thi"""
        logger.info("🚀 [GATEWAY] Worker loop is active.")
        while True:
            try:
                # Lấy task (ưu tiên thấp nhất/số nhỏ nhất ra trước)
                priority, entry_count, task_id = await self.queue.get()
                
                # KHÔNG POP NỮA, CHỈ GET ĐỂ KIỂM TRA
                with self.pending_lock:
                    task_obj = self.pending_tasks.get(task_id)
                    
                if not task_obj or task_obj.is_cancelled:
                    self.queue.task_done()
                    # TIỆN TAY DỌN RÁC LUÔN
                    with self.pending_lock:
                        self.pending_tasks.pop(task_id, None)
                    continue
                
                async with self.semaphore:
                    # DOUBLE CHECK TRƯỚC KHI CHẠY (Advanced Fix của bạn)
                    if task_obj.is_cancelled:
                        self.queue.task_done()
                        with self.pending_lock:
                            self.pending_tasks.pop(task_id, None)
                        continue
                    logger.info(f"⚙️ [GATEWAY] Processing task {task_id} (Level: {task_obj.level}, Priority: {priority})")
                    try:
                        # Thực thi task_func được truyền qua payload
                        task_func = task_obj.payload['func']
                        func_args = task_obj.payload['args']
                        
                        # Chạy task thực tế
                        result = await task_func(*func_args)
                        
                        # Trả kết quả về Future
                        if not task_obj.future.done():
                            task_obj.future.set_result(result)
                            
                    except Exception as e:
                        logger.error(f"🔥 [GATEWAY] Task {task_id} failed: {e}")
                        if not task_obj.future.done():
                            task_obj.future.set_exception(e)
                    finally:
                        self.queue.task_done()
                        # 🔥 FIX: ĐẢM BẢO POP LUÔN XẢY RA, TRÁNH LEAK MEMORY
                        with self.pending_lock:
                            self.pending_tasks.pop(task_id, None)
                        
            except Exception as e:
                # 🟢 FIX: Chặn lỗi UnboundLocalError do task_id chưa khởi tạo
                # Chỉ Log và ngủ, để vòng lặp tự phục hồi. KHÔNG POP ở đây.
                logger.error(f"⚠️ [GATEWAY] Fatal Worker loop error: {e}")
                await asyncio.sleep(1)

    async def _aging_loop(self):
        """Aging Mechanism: Đẩy ưu tiên cho các task chờ quá lâu"""
        while True:
            await asyncio.sleep(10) # Kiểm tra mỗi 10 giây
            if self.queue.empty(): continue
            
            now = time.time()
            
            temp_list = []
            while not self.queue.empty():
                item = await self.queue.get()
                temp_list.append(item)
                # 🔥 FIX: BÁO TASK_DONE NGAY LẬP TỨC ĐỂ KHÔNG HỎNG INTERNAL COUNTER
                self.queue.task_done()
            
            for p, ec, tid in temp_list:
                # 🔥 FIX: Thread-safe Read
                with self.pending_lock:
                    task = self.pending_tasks.get(tid)

                # BỎ QUA NẾU TASK KHÔNG TỒN TẠI HOẶC ĐÃ BỊ HỦY
                if not task or task.is_cancelled:
                    continue
                    
                if task:
                    wait_time = now - task.timestamp
                    
                    # Cứ mỗi 10s chờ, giảm 1 cấp level (tối đa giảm 2 cấp để không lấn át Task Real-time)
                    age_bonus = min(2, int(wait_time // 10))
                    new_level = max(0, task.level - age_bonus)
                    
                    new_priority = new_level * 1000 + task.entry_count
                    await self.queue.put((new_priority, task.entry_count, tid))
                else:
                    # Task đã bị hủy hoặc xử lý xong
                    pass

    def submit(self, task_func: Callable, args: tuple, priority_level: int = 2):
        """Gửi task vào hàng đợi từ bất kỳ thread nào"""
        # 🔥 FIX: Thread-safe Check length
        with self.pending_lock:
            if len(self.pending_tasks) >= self.max_queue_size:
                raise RuntimeError("Hàng đợi quá tải (Backpressure). Vui lòng thử lại sau.")

        task_id = str(uuid.uuid4())
        fut = concurrent.futures.Future() 

        injected_args = list(args)
        if len(injected_args) >= 2 and injected_args[1] is None:
            injected_args[1] = task_id
        injected_args = tuple(injected_args)

        self.entry_counter += 1
        priority = priority_level * 1000 + self.entry_counter
        
        task_obj = QueuedTask(
            priority=priority,
            entry_count=self.entry_counter,
            task_id=task_id,
payload={'func': task_func, 'args': injected_args}, # <-- Dùng args đã inject
            future=fut,
            timestamp=time.time(),
            level=priority_level
        )
        
        # 🔥 FIX: Thread-safe Write
        with self.pending_lock:
            self.pending_tasks[task_id] = task_obj
            queue_len = len(self.pending_tasks)
        
        # Đẩy vào queue của loop nền một cách an toàn
        asyncio.run_coroutine_threadsafe(
            self.queue.put((priority, self.entry_counter, task_id)), 
            self.loop
        )
        
        logger.info(f"📥 [GATEWAY] Task queued: {task_id} (Level: {priority_level}) | Đang chờ: {queue_len}/{self.max_queue_size}")
        return task_id, fut

    def get_queue_status(self, task_id: str) -> Dict[str, Any]:
        """Lấy thông tin vị trí trong hàng đợi"""
        # 🔥 FIX: Thread-safe Read
        with self.pending_lock:
            if task_id not in self.pending_tasks:
                return {"status": "processing_or_done", "position": 0}
            
            my_priority = self.pending_tasks[task_id].priority
            position = 1
            for tid, t in self.pending_tasks.items():
                if tid != task_id and t.priority < my_priority:
                    position += 1
                    
        return {"status": "waiting", "position": position}

# Singleton instance
gateway = PriorityGateway()

async def gateway_entry(user_input_dict, task_func, priority_level: int = 2, status_callback: Optional[Callable] = None):
    """Entry point tương thích với code cũ nhưng chạy qua Priority Queue"""
    try:
        # Submit task và nhận trực tiếp task_id cùng Future
        task_id, future = gateway.submit(task_func, (user_input_dict, None, "trace_id"), priority_level)

        # Chờ kết quả và cập nhật trạng thái
        MAX_WAIT_TIME = 120
        start_time = time.time()
        
        # 🔥 FIX: Timeout nằm đúng bên TRONG vòng lặp
        while not future.done():
            if time.time() - start_time > MAX_WAIT_TIME:
                future.cancel()
                
                # 🔥 FIX: Hủy Hard Cancel, xóa triệt để khỏi Queue
                with gateway.pending_lock:
                    task = gateway.pending_tasks.get(task_id)
                    if task:
                        task.is_cancelled = True # 🟢 BẬT CỜ HỦY CHO WORKER BIẾT
                
                logger.warning(f"⚠️ [GATEWAY] Task {task_id} timeout. Đã xóa khỏi hàng đợi.")
                return {"status": "error", "msg": "Timeout: Task bị treo quá lâu."}
                
            if task_id and status_callback:
                status = gateway.get_queue_status(task_id)
                if status["status"] == "waiting":
                    status_callback("QUEUE_WAITING", status["position"])
            await asyncio.sleep(1.0)
            
        # 🟢 FIX CRITICAL: KHÔNG ĐƯỢC BLOCK EVENT LOOP
        result = await asyncio.wrap_future(future)
        return {"status": "success", "data": result}
    except Exception as e:
        logger.error(f"🔥 [GATEWAY ENTRY] Error: {e}")
        return {"status": "error", "msg": str(e)}

if __name__ == "__main__":
    # Test nhanh
    logging.basicConfig(level=logging.INFO)
    async def mock_task(data, tid, trid):
        print(f"Working on {data}...")
        await asyncio.sleep(2)
        return f"Done {data}"

    async def test():
        print("Submitting tasks...")
        f1 = await gateway_entry({"input": "Task 1"}, mock_task, priority_level=3)
        print(f"Result 1: {f1}")

    asyncio.run(test())