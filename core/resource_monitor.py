import pynvml
import logging
import atexit

logger = logging.getLogger(__name__)

class ResourceMonitor:
    def __init__(self):
        self.initialized = False
        try:
            pynvml.nvmlInit()
            self.device_count = pynvml.nvmlDeviceGetCount()
            if self.device_count > 0:
                self.handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                self.name = pynvml.nvmlDeviceGetName(self.handle)
                self.initialized = True
                logger.info(f"✅ NVML Initialized: {self.name}")
                # ĐĂNG KÝ HÀM DỌN DẸP AN TOÀN
                atexit.register(self.shutdown) 
        except Exception as e:
            logger.warning(f"⚠️ NVML Initialization failed: {e}. Running in Mock mode.")

    def shutdown(self):
        if self.initialized:
            try:
                pynvml.nvmlShutdown()
            except: pass

    def get_gpu_stats(self):
        if not self.initialized:
            return None # Trả về None để UI tự xử lý thay vì Mock data giả

        try:
            info = pynvml.nvmlDeviceGetMemoryInfo(self.handle)
            temp = pynvml.nvmlDeviceGetTemperature(self.handle, pynvml.NVML_TEMPERATURE_GPU)
            
            # LẤY GPU UTILIZATION (Hiệu suất lõi CUDA)
            util = pynvml.nvmlDeviceGetUtilizationRates(self.handle)
            gpu_util = util.gpu
            
            used_mb = info.used / 1024**2
            total_mb = info.total / 1024**2
            percent = (used_mb / total_mb) * 100
            
            return {
                "vram_used": int(used_mb),
                "vram_total": int(total_mb),
                "vram_percent": round(percent, 1),
                "temp": temp,
                "gpu_util": gpu_util, # Thêm thuộc tính này
                "status": "online"
            }
        except Exception as e:
            logger.error(f"❌ Error fetching GPU stats: {e}")
            return None

monitor = ResourceMonitor()