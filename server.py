from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import asyncio
import json
import logging
import time
import uuid
from typing import List
from core.telemetry import log_agent_interaction

# Import các module nội bộ
from core.agent_engine import AgentEngine
from core.local_rag import LocalRAG
from core.semantic_cache import semantic_cache

# Cấu hình log
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="THE IMMORTAL AI - Backend Engine")

# CORS config
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🟢 FIX 3: Khởi tạo Global Stateful RAG
logger.info("Khởi tạo Embedder và FAISS nội bộ...")
global_embedder = LocalRAG.initialize_embedder()
global_index, global_chunks = LocalRAG.initialize_vector_store(global_embedder)
global_rag = LocalRAG(embedder=global_embedder, vector_store=global_index, chunks=global_chunks)

# 🟢 FIX 2: Bức tường lửa bảo vệ VRAM (Static Semaphore)
# Tiền đề cho Epic 2. Hiện tại khóa cứng ở 2 luồng đồng thời.
GLOBAL_SEMAPHORE = asyncio.Semaphore(2)

# --- [LAYER 1: SIZE VALIDATOR] ---
# Sử dụng Pydantic để giới hạn số lượng tin nhắn gửi lên
class ChatMessage(BaseModel):
    role: str
    content: str
    is_temp: bool = False

class ChatRequest(BaseModel):
    # Giới hạn tối đa 20 tin nhắn lịch sử để tránh tràn ngữ cảnh/VRAM
    messages: List[ChatMessage] = Field(..., max_length=20) 
    model: str = "llama3.2:3b"
    temperature: float = Field(0.2, ge=0.0, le=1.0)
    max_iterations: int = Field(5, ge=1, le=10)
    turbo_mode: bool = False

@app.post("/admin/reload-rag")
async def reload_rag():
    # Đẩy tác vụ nặng ra ThreadPool để Event Loop không bị chết
    success = await asyncio.to_thread(global_rag.reload)
    if success:
        # Dọn dẹp Cache cũ để RAG mới phát huy tác dụng
        semantic_cache.clear() 
        return {"status": "success", "message": "Knowledge base reloaded and Cache cleared."}
        
    return {"status": "error", "message": "Failed to reload knowledge base."}

@app.post("/chat")
async def chat_endpoint(request: Request, body: ChatRequest, bg_tasks: BackgroundTasks):
    # 🟢 FIX 4: Khởi tạo Request ID để theo dõi (Tracing)
    req_id = str(uuid.uuid4())[:8] # Lấy 8 ký tự cho gọn

    # Trích xuất user_query
    user_query = ""
    for msg in reversed(body.messages):
        if msg.role == "user" and not msg.is_temp:
            user_query = msg.content
            break
    
    # --- [LAYER 1.2: QUERY LENGTH VALIDATOR] ---
    if len(user_query) > 2000:
        logger.warning(f"[{req_id}] ❌ Từ chối: Câu hỏi quá dài.")
        raise HTTPException(status_code=400, detail="Câu hỏi quá dài.")
    if not user_query.strip():
        logger.warning(f"[{req_id}] ❌ Từ chối: Câu hỏi trống.")
        raise HTTPException(status_code=400, detail="Câu hỏi không được để trống.")

    # --- [LAYER 2: SEMANTIC CACHE CHECK] ---
    cached_ans = semantic_cache.get(user_query)
    
    async def event_generator():
        if cached_ans:
            logger.info(f"[{req_id}] 🚀 CACHE HIT: Nhả kết quả tức thì. Query Length: {len(user_query)}")
            yield f"data: {json.dumps({'event': 'THINK', 'data': 'Đã tìm thấy phản hồi trong bộ nhớ đệm.'})}\n\n"
            await asyncio.sleep(0.1)
            yield f"data: {json.dumps({'event': 'FINAL_ANSWER', 'data': cached_ans})}\n\n"
            return

        # --- [LAYER 3: QUEUE LIMITS] ---
        # Giới hạn maxsize=100 để tránh spam event làm treo RAM server
        queue = asyncio.Queue(maxsize=100)

        loop = asyncio.get_running_loop()
        
        def emit(event_type, data):
            def _safe_put():
                try:
                    queue.put_nowait({"event": event_type, "data": data})
                except asyncio.QueueFull:
                    try:
                        queue.get_nowait() # Drop oldest
                        queue.put_nowait({"event": event_type, "data": data})
                    except Exception: # 🟢 FIX 5: Bỏ except trống
                        pass
            loop.call_soon_threadsafe(_safe_put)

         # 🟢 VÁ LỖI 3: Chỉ thông báo chờ nếu Semaphore đã full
        if GLOBAL_SEMAPHORE.locked():
            yield f"data: {json.dumps({'event': 'QUEUE_WAITING', 'data': 'Đang chờ cấp phát VRAM GPU...'})}\n\n"

        async with GLOBAL_SEMAPHORE:
            logger.info(f"[{req_id}] ⚙️ Bắt đầu xử lý (Đã cấp VRAM)")

            # Khởi tạo Engine
            engine = AgentEngine(model_name=body.model, local_rag=global_rag)
            engine.messages = [msg.model_dump() for msg in body.messages]

            engine_task = asyncio.create_task(
                engine.run(user_input=user_query, max_iterations=body.max_iterations, 
                        temperature=body.temperature, callback=emit)
            )

            start_time = time.time()
            ping_counter = 0
            timeout_limit = 120.0 # 2 phút guardrail
            # 🟢 TỐI ƯU 3: Giảm timeout để loop check nhạy hơn
            wait_timeout = 0.05 
            ping_threshold = int(3.0 / wait_timeout) # 60 ticks = 3 giây

            try:
                # --- [LAYER 4: ENGINE TIMEOUT] ---
                # Giới hạn task không được chạy quá 120s (2 phút)
                while not engine_task.done():
                    is_timeout = (time.time() - start_time) > timeout_limit
                    is_disconnected = await request.is_disconnected()

                    # 🟢 VÁ LỖI 2.1: Timeout chuẩn xác mà KHÔNG BLOCK SSE STREAMING
                    if is_timeout or is_disconnected:
                        reason = "Timeout" if is_timeout else "Client Disconnected"
                        logger.warning(f"[{req_id}] ⚠️ Hủy Job. Lý do: {reason}")

                        engine_task.cancel()
                        # 🟢 VÁ LỖI 4: Await cancel để dọn dẹp tài nguyên triệt để
                        try:
                            await engine_task
                        except asyncio.CancelledError:
                            pass
                        
                    # 🟢 VÁ LỖI 3: Gửi event ERROR để UI không bị treo spinner
                        yield f"data: {json.dumps({'event': 'ERROR', 'data': f'Hệ thống ngắt kết nối ({reason})'})}\n\n"
                        return

                    try:
                        # Chờ lấy event với timeout ngắn để bơm PING
                        item = await asyncio.wait_for(queue.get(), timeout=wait_timeout)
                        # 🟢 FIX 1: Đã yield item bị thiếu!
                        yield f"data: {json.dumps(item)}\n\n"
                        ping_counter = 0
                    except asyncio.TimeoutError:
                        ping_counter += 1
                        if ping_counter >= ping_threshold:
                            yield f"data: {json.dumps({'event': 'PING', 'data': 'keep-alive'})}\n\n"
                            ping_counter = 0
                    
                    # 🟢 FIX 1: Nhường CPU cho Event Loop
                    await asyncio.sleep(0)
                
                # 🟢 VÁ LỖI 3: Flush nốt các event còn kẹt trước khi kết thúc
                while not queue.empty():
                    try:
                        item = queue.get_nowait()
                        yield f"data: {json.dumps(item)}\n\n"
                    except asyncio.QueueEmpty: # 🟢 FIX 5: Bắt lỗi cụ thể
                        break

            # Trả về kết quả cuối cùng
                if not engine_task.cancelled():
                    # 🟢 VÁ LỖI 4: Dùng await thay vì .result()
                    result = await engine_task
                    yield f"data: {json.dumps({'event': 'FINAL_ANSWER', 'data': result})}\n\n"
                    semantic_cache.set(user_query, result)

                    # 🟢 THÊM DÒNG NÀY: Ghi log thành công
                    exec_time = time.time() - start_time
                    bg_tasks.add_task(log_agent_interaction, req_id, user_query, True, None, exec_time)
                    logger.info(f"[{req_id}] ✅ Hoàn tất thành công.")

            except Exception as e:
                logger.error(f"[{req_id}] 🚨 Server Error: {str(e)}")
                yield f"data: {json.dumps({'event': 'ERROR', 'data': str(e)})}\n\n"

                # 🟢 THÊM DÒNG NÀY: Ghi log thất bại
                exec_time = time.time() - start_time
                bg_tasks.add_task(log_agent_interaction, req_id, user_query, False, str(e), exec_time)
            finally:
                # Bảo hiểm cuối cùng chống Zombie Task
                if not engine_task.done():
                    engine_task.cancel()
                    try: await engine_task
                    except Exception: pass # 🟢 FIX 5

    # 🟢 TỐI ƯU 2: SSE Headers Chuẩn Production (Chống Nginx Buffering)
    return StreamingResponse(
        event_generator(), 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)