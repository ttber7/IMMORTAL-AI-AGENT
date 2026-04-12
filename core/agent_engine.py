import json
import re
from duckduckgo_search import DDGS
from core.local_rag import LocalRAG
import uuid
import urllib.request
import asyncio
import logging
import os
from typing import List, Dict, Any

from core.gateway import gateway_entry
from core.adaptive_router import AdaptiveRouter

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


OLLAMA_URL = "http://localhost:11434/api/generate"

# === IMPROVED AGENT ENGINE (PRODUCTION GRADE) ===
# 1. extract_json_safe: Dùng find/rfind thay regex dể trích xuất JSON đa tầng.
# 2. Cool-down Temp: Lỗi càng nhiều -> nhiệt độ càng giảm về 0 (để ép AI chính xác).
# 3. Schema Validation: Check sâu action/params và tool registry.
# 4. State Reset: Xóa dấu vết request cũ ở đầu run().
# 5. Circuit Breaker: Phân loại lỗi mạng, JSON, và Tool riêng biệt.
# 6. Structured Output: Tận dụng format: json schema của Ollama.

# Danh sách đăng ký Tool (Tool Registry)
def tool_calculate(expression: str) -> str:
    """Công cụ thực thi phép toán cơ bản"""
    if not re.match(r'^[\d\+\-\*\/\.\(\)\s]+$', expression):
        return "Lỗi bảo mật: Biểu thức toán học chứa ký tự không hợp lệ."
    try:
        result = eval(expression, {"__builtins__": None}, {})
        return f"Kết quả: {result}"
    except Exception as e:
        return f"Lỗi toán học: {e}"

def tool_web_search(query: str) -> str:
    """Tìm kiếm trên Internet sử dụng DuckDuckGo"""
    try:
        results = DDGS().text(query, region='vn-vi', max_results=3)
        formatted_results = []
        for r in results:
            formatted_results.append({
                "title": r.get("title", ""),
                "snippet": r.get("body", "").replace("\n", " ")[:300]
            })
        return json.dumps(formatted_results, ensure_ascii=False)
    except Exception as e:
        return f"Lỗi Web Search: {e}"

# Không khởi tạo AVAILABLE_TOOLS tĩnh nữa, sẽ gắn vào AgentEngine instance để inject local_rag

SYSTEM_PROMPT = """
Bạn là THE IMMORTAL AI AGENT.

LỆNH CƯỠNG CHẾ (BẤT BIẾN):
1. BẮT BUỘC TRẢ VỀ JSON HỢP LỆ. KHÔNG giải thích, KHÔNG chào hỏi, KHÔNG bọc trong markdown.
2. NGÔN NGỮ: BẮT BUỘC SỬ DỤNG TIẾNG VIỆT 100% trong toàn bộ suy luận (thought) và câu trả lời (answer). TUYỆT ĐỐI KHÔNG DÙNG TIẾNG TRUNG.
3. JSON của bạn PHẢI tuân thủ 1 trong 2 cấu trúc:
   - Trả lời trực tiếp: {"thought": "suy luận", "answer": "nội dung trả lời"}
   - Dùng tool (công cụ): {"thought": "suy luận", "action": "tên_tool", "params": {"tên_tham_số": "giá_trị"}}
4. TRẢ LỜI ĐẦY ĐỦ: Nếu người dùng hỏi nhiều ý trong một câu (có chữ VÀ), bạn BẮT BUỘC phải đọc kỹ toàn bộ dữ liệu và trả lời ĐẦY ĐỦ tất cả các vế của câu hỏi, không được bỏ sót.

QUY TẮC ƯU TIÊN TÌM KIẾM (QUAN TRỌNG):
- Nếu câu hỏi về công ty, dự án nội bộ, lịch sử: DÙNG "search_document".
- Nếu câu hỏi về tin tức thời sự, giá cả, sự kiện hiện tại: DÙNG "web_search".
- Nếu "search_document" trả về 'Không tìm thấy thông tin', BẮT BUỘC dùng "web_search" để tìm mạng ngoài.

DANH SÁCH CÔNG CỤ (CHỈ DÙNG CÁC CÔNG CỤ NÀY):
- Tính toán toán học: "calculate" với params {"expression": "ví dụ: 5*3"}
- Tìm kiếm Internet: "web_search" với params {"query": "từ khóa tìm kiếm"}. LƯU Ý: Luôn tự đọc hiểu và tóm tắt kết quả thành câu trả lời tự nhiên.
- Đọc tài liệu nội bộ: "search_document" với params {"query": "từ khóa tìm kiếm"}
. TRẢ LỜI ĐẦY ĐỦ: Nếu người dùng hỏi nhiều ý trong một câu (có chữ VÀ), bạn BẮT BUỘC phải đọc kỹ toàn bộ dữ liệu và trả lời ĐẦY ĐỦ tất cả các vế của câu hỏi, không được bỏ sót.
"""

def extract_json_safe(text: str) -> str:
    """Trích xuất JSON an toàn bằng cách tìm block { } ngoài cùng"""
    start = text.find('{')
    end = text.rfind('}')
    if start == -1 or end == -1:
         raise ValueError("LLM_NO_JSON_FOUND: Không tìm thấy block JSON trong phản hồi.")
    return text[start:end+1]

class AgentEngine:
    def __init__(self, model_name=None, local_rag=None):
        self.default_model_name = model_name
        self.model_name = model_name or "llama3.2:3b"
        self.router = AdaptiveRouter()
        self.local_rag = local_rag
        
        self.available_tools = {
            "calculate": tool_calculate,
            "web_search": tool_web_search
        }
        
        if self.local_rag:
            self.available_tools["search_document"] = self.local_rag.search
        
        # [INTELLIGENCE LAYER] Metrics Tracker với Persistence
        self.metrics_file = "agent_metrics.json"
        self.metrics = self._load_metrics()
        
        # Internal State
        self.current_action = None
        self.observation = None
        self.failed_actions = [] 
        self.last_action_signature = None
        self.circuit_breaker = {"network": 0, "json": 0, "tool": 0}

    def _load_metrics(self) -> Dict[str, Any]:
        """Tải Metrics từ file JSON"""
        default_metrics = {"success": 0, "fail": 0, "total_runs": 0, "avg_latency": 0.0}
        try:
            if os.path.exists(self.metrics_file):
                with open(self.metrics_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return {**default_metrics, **data}
        except Exception as e:
            logger.error(f"Lỗi khi nạp metrics: {e}")
        return default_metrics

    def _save_metrics(self):
        """Lưu Metrics xuống file JSON"""
        try:
            with open(self.metrics_file, "w", encoding="utf-8") as f:
                json.dump(self.metrics, f, ensure_ascii=False, indent=4)
            logger.info("📊 METRICS UPDATED: Đã lưu bộ chỉ số hiệu năng.")
        except Exception as e:
            logger.error(f"Lỗi khi lưu metrics: {e}")

    # [SỬA 1]: Thêm tham số model vào chữ ký hàm
    async def _call_llm(self, prompt: str, model: str, temperature: float = 0.2, is_retry: bool = False) -> str:
        """Hàm bọc gọi Ollama LLM với BẢNG PHONG THẦN: Dynamic VRAM & Dual-Layer Timeout"""
        
        # [RESOURCE LAYER] Lấy tham số động dựa trên VRAM thực tế
        dynamic_opts = self.router.get_dynamic_params(is_retry=is_retry)
        dynamic_opts["temperature"] = temperature
        
        data = {
            "model": model, # [SỬA 2]: Dùng biến model truyền vào, KHÔNG DÙNG self.model_name nữa
            "system": SYSTEM_PROMPT,
            "prompt": prompt,
            "stream": False,
            "format": {
                "type": "object",
                "properties": {
                    "thought": {"type": "string"},
                    "answer": {"type": "string"},
                    "action": {"type": "string"},
                    "params": {"type": "object"}
                },
                "required": ["thought"]
            },
            "options": dynamic_opts
        }
        
        def run_sync():
            try:
                req = urllib.request.Request(OLLAMA_URL, json.dumps(data).encode('utf-8'))
                req.add_header('Content-Type', 'application/json')
                
                # Lớp 1: Socket Timeout (55s)
                with urllib.request.urlopen(req, timeout=55.0) as response:
                    result = json.loads(response.read().decode())
                    return result.get("response", "")
            except Exception as e:
                logger.error(f"Socket/Urllib Error: {e}")
                return "SOCKET_TIMEOUT_OR_ERROR"
        
        # Lớp 2: Asyncio Timeout (60s)
        try:
            async with asyncio.timeout(60.0):
                result_text = await asyncio.to_thread(run_sync)
                if result_text == "SOCKET_TIMEOUT_OR_ERROR":
                    raise TimeoutError("Lỗi kết nối vật lý tới Ollama")
                return result_text
        except TimeoutError:
            self.circuit_breaker["network"] += 1
            logger.error(f"Network Timeout ({self.circuit_breaker['network']})")
            return "NETWORK_TIMEOUT"

    async def run(self, user_input: str, max_iterations=5, temperature=0.2, callback=None):
        """Vòng lặp Agent chuẩn sản xuất với cơ chế Signal (Epic 2)"""
        import time

        def emit(event_type, data):
            if callback:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(event_type, data))
                else:
                    callback(event_type, data)
        start_time = time.time()
        
        self.current_action = None
        self.observation = None
        self.failed_actions = []
        self.last_action_signature = None
        self.circuit_breaker = {"network": 0, "json": 0, "tool": 0}
        logger.info(f"--- NEW RUN: {user_input} ---")
        
        current_temp = temperature
        self.messages = [{"role": "user", "content": user_input}]
        
        iteration = 1
        retry_count = 0
        network_retries = 0

        # [ROUTER LAYER] Áp dụng Manual Override (Epic 4)
        if self.model_name == "Auto (Smart Router)":
            # Nếu User chọn Auto -> Cho phép Router tự động phân tích và chọn model
            target_model = self.router.route_task(user_input)
            if target_model == "REJECT_TASK":
                self.metrics["fail"] += 1
                return "Task bị từ chối do hệ thống đang cạn kiệt VRAM. Vui lòng thử lại sau."
            emit("THINK", f"Router tự động điều hướng sang: {target_model}")
        else:
            # Nếu User đã chọn cứng model ở UI -> Khóa mõm Router, ép dùng model đó
            target_model = self.model_name 
            print(f"[MANUAL OVERRIDE] Tắt Router, ép dùng model: {target_model}")
        
        
        while iteration <= max_iterations:
            # [FIX IMMUTABLE STATE]: Xóa các tin nhắn nhắc lỗi của vòng trước để Context luôn sạch
            if retry_count == 0:
                self.messages = [m for m in self.messages if not m.get("is_temp", False)]
            if self.circuit_breaker["network"] > 5 or self.circuit_breaker["json"] > 5:
                self.metrics["fail"] += 1
                return "Hệ thống tự ngắt (Circuit Breaker) do quá nhiều lỗi liên tiếp."

            # 🔥 THE ULTIMATUM: Chèn Prompt cưỡng chế ở lượt cuối
            if iteration == max_iterations:
                logger.warning("⚠️ Kích hoạt FORCE FINAL ANSWER: Ép LLM chốt hạ!")
                # [FLOW LAYER] Gửi lời nhắc trực diện vào lượt cuối
                self.messages.append({
                    "role": "user", 
                    "content": "ĐÂY LÀ LƯỢT CUỐI CÙNG. BẠN BẮT BUỘC PHẢI TRẢ LỜI NGƯỜI DÙNG. Hãy xuất JSON với duy nhất key 'answer' chứa nội dung trả lời."
                })

            print(f"[RETRY] Vòng lặp {iteration}/{max_iterations} (Temp: {current_temp:.1f})...")
            
            # [INTELLIGENCE LAYER] Immutable State
            # Mặc định dùng history sạch từ self.messages
            current_prompt = "\n".join([f"{m['role']}: {m['content']}" for m in self.messages])
            
            async def task_wrapper(u_input, task_id, trace_id):
                # is_retry = True nếu đang ở vòng lặp sau hoặc vừa gặp lỗi định dạng
                # [SỬA Ở ĐÂY]: Truyền thêm u_input["model"] vào _call_llm
                res = await self._call_llm(
                    prompt=u_input["prompt"], 
                    model=u_input["model"], # <--- Dòng ăn tiền là đây!
                    temperature=u_input["temperature"], 
                    is_retry=(iteration > 1 or retry_count > 0)   
                )
                return {"status": "success", "data": res}

            try:
                # [SỬA Ở ĐÂY]: Đóng gói thêm target_model vào từ điển gửi đi
                gateway_res = await gateway_entry(
                    {"prompt": current_prompt, "temperature": current_temp, "model": target_model},
                    task_wrapper
                )
                raw_response = gateway_res.get("data", "")
                
                if not raw_response or raw_response == "NETWORK_TIMEOUT":
                    network_retries += 1
                    if network_retries > 3:
                        self.metrics["fail"] += 1
                        return "Lỗi kết nối mạng nghiêm trọng. Vui lòng kiểm tra lại hệ thống."
                    
                    logger.warning(f"Lỗi mạng/Timeout lần {network_retries}. Đang thử lại...")
                    await asyncio.sleep(2 ** network_retries) # Exponential Backoff (2s, 4s, 8s)
                    continue # Bỏ qua logic parse JSON bên dưới, quay lại đầu vòng while gọi lại LLM
                logger.info(f"RAW RESPONSE (Iter {iteration}):\n{raw_response}")

                json_str = extract_json_safe(raw_response)
                ai_json = json.loads(json_str)
                
                if "thought" in ai_json:
                    logger.info(f"🤔 Thought: {ai_json['thought']}")
                    emit("THINK", ai_json["thought"])
                
                # CHẶN ĐƯỜNG TRẢ LỜI (FINAL ANSWER)
                if "answer" in ai_json:
                    logger.info(f"✅ FINAL ANSWER: {ai_json['answer']}")
                    # Cập nhật Metrics
                    self.metrics["success"] += 1
                    self.metrics["total_runs"] += 1
                    latency = time.time() - start_time
                    self.metrics["avg_latency"] = (self.metrics["avg_latency"] * (self.metrics["total_runs"]-1) + latency) / self.metrics["total_runs"]
                    self._save_metrics() # Lưu vào file
                    return ai_json["answer"]
                
                # CHẶN ĐƯỜNG HÀNH ĐỘNG (ACTION)
                if "action" in ai_json:
                    tool_name = ai_json["action"]
                    params = ai_json.get("params", {})
                    
                    # [FLOW LAYER] Action Loop Detection
                    action_signature = f"{tool_name}:{json.dumps(params, sort_keys=True)}"
                    if tool_name.lower() == "answer":
                        final_text = params.get("answer", str(params))
                        logger.info(f"✅ FINAL ANSWER (RESCUED): {final_text}")
                        self.metrics["success"] += 1
                        self.metrics["total_runs"] += 1
                        latency = time.time() - start_time
                        self.metrics["avg_latency"] = (self.metrics["avg_latency"] * (self.metrics["total_runs"]-1) + latency) / self.metrics["total_runs"]
                        self._save_metrics()
                        return final_text
                    if action_signature == self.last_action_signature:
                        raise ValueError(f"PHÁT HIỆN VÒNG LẶP HÀNH ĐỘNG: Đừng gọi lại {tool_name} với cùng tham số này!")
                    
                    if action_signature in self.failed_actions:
                        raise ValueError(f"Hành động {tool_name} này đã từng thất bại. Hãy chọn cách khác.")

                    if tool_name not in self.available_tools:
                        raise ValueError(f"Công cụ '{tool_name}' không tồn tại trong hệ thống. Hãy chọn công cụ khác hoặc tự trả lời (answer).")

                    if tool_name == "calculate" and not isinstance(params.get("expression"), str):
                        raise ValueError("Tham số 'expression' của calculate BẮT BUỘC phải là chuỗi (string).")
                    if tool_name in ["web_search", "search_document"] and not isinstance(params.get("query"), str):
                        raise ValueError(f"Tham số 'query' của {tool_name} BẮT BUỘC phải là chuỗi (string).")
                    
                    self.last_action_signature = action_signature
                    self.current_action = tool_name
                    logger.info(f"🛠️ CALLING TOOL: {tool_name}")
                    emit("ACT", f"Gọi công cụ: {tool_name}")
                    
                    tool_func = self.available_tools[tool_name]
                    try:
                        if asyncio.iscoroutinefunction(tool_func):
                            self.observation = await tool_func(**params)
                        else:
                            self.observation = tool_func(**params)
                        emit("OBSERVE", f"Kết quả: {self.observation}")
                    except Exception as e:
                        # 🔴 FIX BUG: Ghi nhớ tool lỗi để lần sau AI chừa mặt nó ra
                        self.failed_actions.append(action_signature)
                        self.observation = f"LỖI THỰC THI TOOL: {str(e)}. HÃY TÌM CÁCH KHÁC!"
                    
                    # LƯU VÀO LỊCH SỬ CHÍNH THỨC (STATE)
                    self.messages.append({"role": "assistant", "content": json_str})
                    
                    # [NÂNG CẤP]: Đổi role thành user và ép nó phải 'answer'
                    prompt_hinh_phat = (
                        f"KẾT QUẢ TỪ CÔNG CỤ:\n{self.observation}\n\n"
                        "-> HÃY ĐỌC KẾT QUẢ TRÊN VÀ TRẢ LỜI NGƯỜI DÙNG BẰNG KEY 'answer'. "
                        "TUYỆT ĐỐI KHÔNG GỌI LẠI CÔNG CỤ NỮA!"
                    )
                    self.messages.append({"role": "user", "content": prompt_hinh_phat})
                    
                    # 🔴 FIX MEMORY: Sliding Window Context (Giới hạn 10 tin nhắn)
                    MAX_HISTORY = 10
                    if len(self.messages) > MAX_HISTORY:
                        # Giữ lại Câu hỏi đầu tiên của User (thường là self.messages[0])
                        # VÀ cắt lấy phần đuôi sao cho tổng số message không vượt MAX_HISTORY
                        # Chú ý: Cần cắt chẵn (1 User + 1 Assistant) để tránh Context bị lệch
                        keep_amount = MAX_HISTORY - 1
                        # Nếu phần đuôi bắt đầu bằng một câu "assistant", lùi lại 1 bước để lấy câu "user" trước đó
                        if self.messages[-keep_amount]["role"] == "assistant":
                            keep_amount += 1
                        
                        self.messages = [self.messages[0]] + self.messages[-keep_amount:]
                    
                    current_temp = 0.2 # Reset nhiệt độ sau khi có thông tin mới
                    
                    # [FLOW LAYER] Tiến tới bước tiếp theo và reset retry_count
                    iteration += 1
                    retry_count = 0
                    continue

                raise ValueError("JSON phản hồi không chứa 'answer' hoặc 'action'.")

            except (ValueError, json.JSONDecodeError) as e:
                self.circuit_breaker["json"] += 1
                current_temp = max(0.0, current_temp - 0.1)
                
                logger.warning(f"⚠️ Trigger Self-Repair: {e}")
                emit("REPAIR", str(e))
                
                # Bơm thẳng lời nhắc lỗi vào self.messages NHƯNG ĐÁNH DẤU NÓ LÀ TEMP
                if "VÒNG LẶP" in str(e) or "thất bại" in str(e):
                    # Nếu đang kẹt vòng lặp, ép nó phải trả lời hoặc tìm cách khác
                    repair_prompt = f"LỖI: {e}. BẠN PHẢI DÙNG KEY 'answer' ĐỂ TỔNG HỢP DỮ LIỆU ĐÃ CÓ."
                else:
                    # Nếu lỗi JSON thông thường
                    repair_prompt = f"LỖI ĐỊNH DẠNG: {e}. HÃY TRẢ VỀ JSON CHUẨN CÓ KEY 'answer' HOẶC 'action'."
                    
                self.messages.append({"role": "user", "content": repair_prompt, "is_temp": True})
                
                # [FIX]: Dùng while loop giúp iteration -= 1 hoặc không tăng iteration có tác dụng.
                # Tuy nhiên, ta dùng retry_count để giới hạn số lần sửa lỗi cho mỗi bước.
                retry_count += 1
                if retry_count > 3:
                    logger.error(f"❌ Quá 3 lần sửa lỗi JSON ở bước {iteration}. Chấp nhận bỏ qua và tiến tới bước tiếp theo.")
                    iteration += 1
                    retry_count = 0
                
                continue
            
        print("[ERROR] Quá số lượt lặp (Max Iterations), bắt buộc dừng Agent lại để chống lặp vĩnh viễn!")
        logger.error("❌ Quá số lượt lặp (Max Iterations). Agent không thể đưa ra đáp án cuối cùng.")
        self.metrics["fail"] += 1
        return "Tôi không thể hoàn thành yêu cầu với các thông tin và công cụ hiện tại. Vui lòng cung cấp thêm chi tiết hoặc thử lại."

# === Test nhanh tích hợp liền tay ===
if __name__ == "__main__":
    async def main():
        engine = AgentEngine(model_name="phi3:mini")
        
        # Test 1: Chat bình thường
        # await engine.run("Chào bạn, bạn là ai và do ai tạo ra?")
        
        # Test 2: Yêu cầu tính toán (Bắt buộc chui qua Tool)
        await engine.run("Tính giúp tôi 1245 + 5600 bằng bao nhiêu hả AI?")
        
    asyncio.run(main())

