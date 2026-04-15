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
        self.pending_tasks: Dict[str, QueuedTask] = {}
        self.pending_lock = threading.Lock() 
        
        self.entry_counter = 0
        self.max_queue_size = 25
        
        # Quản lý Worker động (Hysteresis)
        self.max_workers = 1
        self.last_free_time = None
        
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
        
        self.queue = asyncio.PriorityQueue()
        
        # Chạy 2 luồng công nhân, worker 1 chỉ chạy khi max_workers = 2
        self.loop.create_task(self._worker_loop(worker_id=0))
        self.loop.create_task(self._worker_loop(worker_id=1))
        
        self.loop.create_task(self._aging_loop())
        self.loop.create_task(self._vram_monitor_loop())
        
        self.loop.run_forever()

    async def _vram_monitor_loop(self):
        """Monitor VRAM và thay đổi max_workers (Hysteresis Timer)"""
        from core.resource_monitor import monitor
        while True:
            await asyncio.sleep(1)
            try:
                stats = monitor.get_gpu_stats()
                if not stats: continue
                
                vram_used = stats.get('vram_used', 4096)
                
                # Coi VRAM trống là dưới 1500 MB
                if vram_used < 1500:
                    if self.last_free_time is None:
                        self.last_free_time = time.time()
                    elif time.time() - self.last_free_time >= 5.0:
                        if self.max_workers < 2:
                            self.max_workers = 2
                            logger.info("🟢 [GATEWAY] VRAM trống 5s liên tục. Nâng Worker = 2.")
                else:
                    self.last_free_time = None
                    if self.max_workers > 1:
                        self.max_workers = 1
                        logger.info("🔴 [GATEWAY] VRAM chiếm dụng cao. Giảm Worker = 1 ngay lập tức.")
            except Exception as e:
                logger.error(f"Lỗi VRAM Monitor: {e}")

    async def _worker_loop(self, worker_id: int):
        """Consumer loop dynamically enabled/disabled"""
        logger.info(f"🚀 [GATEWAY] Worker {worker_id} loop is active.")
        while True:
            # Ngừng xử lý nếu bị giảm max_workers
            if worker_id >= self.max_workers:
                await asyncio.sleep(0.5)
                continue

            try:
                priority, entry_count, task_id = await asyncio.wait_for(self.queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue
                
            try:
                with self.pending_lock:
                    task_obj = self.pending_tasks.get(task_id)
                    
                if not task_obj or task_obj.is_cancelled:
                    continue
                
                logger.info(f"⚙️ [GATEWAY] Worker {worker_id} processing task {task_id} (Level: {task_obj.level}, Priority: {priority})")
                
                try:
                    task_func = task_obj.payload['func']
                    func_args = task_obj.payload['args']
                    
                    # Cung cấp cờ chạy timeout
                    result = await asyncio.wait_for(task_func(*func_args), timeout=120.0)
                    
                    if not task_obj.future.done():
                        task_obj.future.set_result(result)

                except asyncio.TimeoutError:
                    logger.error(f"🔥 [GATEWAY] Task {task_id} timeout chạy (120s).")
                    if not task_obj.future.done():
                        task_obj.future.set_exception(TimeoutError("Hàm thực thi (LLM) bị treo."))      
                except Exception as e:
                    logger.error(f"🔥 [GATEWAY] Task {task_id} failed: {e}")
                    if not task_obj.future.done():
                        task_obj.future.set_exception(e)
            finally:
                self.queue.task_done()
                with self.pending_lock:
                    self.pending_tasks.pop(task_id, None)

    async def _aging_loop(self):
        """Aging Mechanism: Đẩy ưu tiên cho các task chờ quá lâu"""
        while True:
            await asyncio.sleep(10) # Kiểm tra mỗi 10 giây
            if self.queue.empty(): continue
            
            now = time.time()
            temp_list = []
            
            while not self.queue.empty():
                try:
                    item = self.queue.get_nowait()
                    temp_list.append(item)
                    self.queue.task_done()
                except asyncio.QueueEmpty:
                    break
            
            for p, ec, tid in temp_list:
                with self.pending_lock:
                    task = self.pending_tasks.get(tid)

                if not task or task.is_cancelled:
                    continue
                    
                wait_time = now - task.timestamp
                age_bonus = min(2, int(wait_time // 10))
                
                if task.level > 0:
                    new_level = max(1, task.level - age_bonus) # Không vượt lên hạng 0
                else:
                    new_level = 0
                
                new_priority = new_level * 1000 + task.entry_count
                await self.queue.put((new_priority, task.entry_count, tid))

    def submit(self, task_func: Callable, args: tuple, priority_level: int = 2):
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
            payload={'func': task_func, 'args': injected_args},
            future=fut,
            timestamp=time.time(),
            level=priority_level
        )
        
        with self.pending_lock:
            self.pending_tasks[task_id] = task_obj
            queue_len = len(self.pending_tasks)
        
        asyncio.run_coroutine_threadsafe(
            self.queue.put((priority, self.entry_counter, task_id)), 
            self.loop
        )
        
        logger.info(f"📥 [GATEWAY] Task queued: {task_id} (Level: {priority_level}) | Đang chờ: {queue_len}/{self.max_queue_size}")
        return task_id, fut

    def get_queue_status(self, task_id: str) -> Dict[str, Any]:
        with self.pending_lock:
            if task_id not in self.pending_tasks:
                return {"status": "processing_or_done", "position": 0}
            
            my_priority = self.pending_tasks[task_id].priority
            position = 1
            for tid, t in self.pending_tasks.items():
                if tid != task_id and t.priority < my_priority:
                    position += 1
                    
        return {"status": "waiting", "position": position}

    def cancel_task(self, task_id: str):
        """Cho phép FastAPI hủy Task từ bên ngoài khi Client Disconnect"""
        with self.pending_lock:
            task = self.pending_tasks.get(task_id)
            if task:
                task.is_cancelled = True
                logger.warning(f"🛑 [GATEWAY] Yêu cầu hủy Task {task_id} thành công.")
                # Chúng ta không tự future.cancel() vì có thể FastAPI bên ngoài đã catch CancelledError rồi

# Singleton instance
gateway = PriorityGateway()

# --- Async Bridge function has been removed from here as we will not use synchronous bridging anymore in Phase 6 ---