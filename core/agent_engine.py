import json
import re
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

def tool_get_weather(location: str) -> str:
    """Công cụ lấy thời tiết (Mock)"""
    return f"Thời tiết tại {location} là 28 độ C."

async def tool_notion_search(query: str) -> str:
    """Tìm kiếm thông tin trong Workspace Notion"""
    try:
        # Giả lập gọi MCP (Thực tế sẽ gọi mcp_notion-mcp-server_API-post-search)
        return f"Tìm thấy 3 tài liệu về '{query}' trong Notion."
    except Exception as e:
        return f"Lỗi Notion: {e}"

async def tool_notebook_query(notebook_id: str, query: str) -> str:
    """Hỏi đáp chuyên sâu về tài liệu trong NotebookLM"""
    try:
        # Giả lập gọi MCP (Thực tế sẽ gọi mcp_notebooklm_notebook_query)
        return f"NotebookLM: Dựa trên tài liệu, '{query}' được giải thích là..."
    except Exception as e:
        return f"Lỗi NotebookLM: {e}"

AVAILABLE_TOOLS = {
    "calculate": tool_calculate,
    "get_weather": tool_get_weather,
    "notion_search": tool_notion_search,
    "notebook_query": tool_notebook_query
}

SYSTEM_PROMPT = """
Bạn là THE IMMORTAL AI AGENT.

LỆNH CƯỠNG CHẾ (BẤT BIẾN):
1. BẠN PHẢI TRẢ VỀ JSON HỢP LỆ. KHÔNG giải thích, KHÔNG chào hỏi, KHÔNG bọc trong markdown.
2. JSON của bạn PHẢI tuân thủ 1 trong 2 cấu trúc:
   - Trả lời: {"thought": "suy luận", "answer": "nội dung"}
   - Dùng tool: {"thought": "suy luận", "action": "tên_tool", "params": {...}}
3. TỰ SỬA LỖI: Nếu nhận được thông báo lỗi JSON từ hệ thống, hãy phân tích lỗi và trả về bản JSON đã sửa đúng format.
4. THỰC DỤNG: Nếu đã đủ thông tin, hãy trả lời ngay bằng 'answer'.

CÔNG CỤ:
- "calculate": {"expression": "..."}
- "get_weather": {"location": "..."}
- "notion_search": {"query": "..."}
- "notebook_query": {"notebook_id": "...", "query": "..."}
"""

def extract_json_safe(text: str) -> str:
    """Trích xuất JSON an toàn bằng cách tìm block { } ngoài cùng"""
    start = text.find('{')
    end = text.rfind('}')
    if start == -1 or end == -1:
         raise ValueError("LLM_NO_JSON_FOUND: Không tìm thấy block JSON trong phản hồi.")
    return text[start:end+1]

class AgentEngine:
    def __init__(self, model_name=None):
        self.default_model_name = model_name
        self.model_name = model_name or "llama3.2:3b"
        self.router = AdaptiveRouter()
        
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
                with open(self.metrics_file, "r") as f:
                    data = json.load(f)
                    return {**default_metrics, **data}
        except Exception as e:
            logger.error(f"Lỗi khi nạp metrics: {e}")
        return default_metrics

    def _save_metrics(self):
        """Lưu Metrics xuống file JSON"""
        try:
            with open(self.metrics_file, "w") as f:
                json.dump(self.metrics, f, indent=4)
            logger.info("📊 METRICS UPDATED: Đã lưu bộ chỉ số hiệu năng.")
        except Exception as e:
            logger.error(f"Lỗi khi lưu metrics: {e}")

    async def _call_llm(self, prompt: str, temperature: float = 0.2, is_retry: bool = False) -> str:
        """Hàm bọc gọi Ollama LLM với BẢNG PHONG THẦN: Dynamic VRAM & Dual-Layer Timeout"""
        
        # [RESOURCE LAYER] Lấy tham số động dựa trên VRAM thực tế
        dynamic_opts = self.router.get_dynamic_params(is_retry=is_retry)
        dynamic_opts["temperature"] = temperature
        
        data = {
            "model": self.model_name,
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

    async def run(self, user_input: str, max_iterations=5):
        """Vòng lặp Agent chuẩn sản xuất với BẢNG PHONG THẦN"""
        import time
        start_time = time.time()
        
        self.current_action = None
        self.observation = None
        self.failed_actions = []
        self.last_action_signature = None
        self.circuit_breaker = {"network": 0, "json": 0, "tool": 0}
        logger.info(f"--- NEW RUN: {user_input} ---")
        
        current_temp = 0.2
        self.messages = [{"role": "user", "content": user_input}]
        
        iteration = 1
        retry_count = 0
        network_retries = 0

        # [ROUTER LAYER] Kích hoạt não bộ phân luồng
        selected_model = self.router.route_task(user_input)
        if selected_model == "REJECT_TASK":
            self.metrics["fail"] += 1
            return "Task bị từ chối do hệ thống đang cạn kiệt VRAM. Vui lòng thử lại sau."
        self.model_name = selected_model
        
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

            print(f"🔄 Vòng lặp {iteration}/{max_iterations} (Temp: {current_temp:.1f})...")
            
            # [INTELLIGENCE LAYER] Immutable State
            # Mặc định dùng history sạch từ self.messages
            current_prompt = "\n".join([f"{m['role']}: {m['content']}" for m in self.messages])
            
            async def task_wrapper(u_input, task_id, trace_id):
                # is_retry = True nếu đang ở vòng lặp sau hoặc vừa gặp lỗi định dạng
                res = await self._call_llm(u_input["prompt"], temperature=u_input["temperature"], is_retry=(iteration > 1 or retry_count > 0))
                return {"status": "success", "data": res}

            try:
                gateway_res = await gateway_entry(
                    {"prompt": current_prompt, "temperature": current_temp}, 
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
                    if action_signature == self.last_action_signature:
                        raise ValueError(f"PHÁT HIỆN VÒNG LẶP HÀNH ĐỘNG: Đừng gọi lại {tool_name} với cùng tham số này!")
                    
                    if action_signature in self.failed_actions:
                        raise ValueError(f"Hành động {tool_name} này đã từng thất bại. Hãy chọn cách khác.")

                    if tool_name not in AVAILABLE_TOOLS:
                        raise ValueError(f"Công cụ '{tool_name}' không tồn tại trong hệ thống.")

                    if tool_name == "calculate" and not isinstance(params.get("expression"), str):
                        raise ValueError("Tham số 'expression' của calculate BẮT BUỘC phải là chuỗi (string).")
                    if tool_name == "get_weather" and not isinstance(params.get("location"), str):
                        raise ValueError("Tham số 'location' của get_weather BẮT BUỘC phải là chuỗi (string).")
                    
                    self.last_action_signature = action_signature
                    self.current_action = tool_name
                    logger.info(f"🛠️ CALLING TOOL: {tool_name}")
                    
                    tool_func = AVAILABLE_TOOLS[tool_name]
                    try:
                        if asyncio.iscoroutinefunction(tool_func):
                            self.observation = await tool_func(**params)
                        else:
                            self.observation = tool_func(**params)
                    except Exception as e:
                        # 🔴 FIX BUG: Ghi nhớ tool lỗi để lần sau AI chừa mặt nó ra
                        self.failed_actions.append(action_signature)
                        self.observation = f"LỖI THỰC THI TOOL: {str(e)}. HÃY TÌM CÁCH KHÁC!"
                    
                    # LƯU VÀO LỊCH SỬ CHÍNH THỨC (STATE)
                    self.messages.append({"role": "assistant", "content": json_str})
                    self.messages.append({"role": "system", "content": f"Observation: {self.observation}"})
                    
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
                
                # Bơm thẳng lời nhắc lỗi vào self.messages NHƯNG ĐÁNH DẤU NÓ LÀ TEMP
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
            
        print("❌ Quá số lượt lặp (Max Iterations), bắt buộc dừng Agent lại để chống lặp vĩnh viễn!")
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

