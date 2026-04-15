import asyncio
from core.agent_engine import AgentEngine

async def run_tests():
    print("="*60)
    print("🧪 BẮT ĐẦU KIỂM THỬ GIAI ĐOẠN 2 (ADAPTIVE ROUTER & IMMORTALITY)")
    print("="*60)

    # Khởi tạo KHÔNG truyền model_name để Adaptive Router tự động định tuyến
    engine = AgentEngine()

    print("\n\n" + "#"*60)
    print("▶️ TEST CASE 1: TOÁN HỌC / CÔNG CỤ (Dự kiến sẽ bị ép vào Phi-3 vì từ khóa '+', 'tính')")
    print("#"*60)
    await engine.run("Tính giúp tôi 1245 + 5600 bằng bao nhiêu hả AI?", max_iterations=3)

    print("\n\n" + "#"*60)
    print("▶️ TEST CASE 2: LÝ LUẬN SÂU SẮC (Dự kiến Llama-3 nếu đủ VRAM, Phi-3 nếu thiếu)")
    print("#"*60)
    await engine.run("Hãy phân tích ưu và nhược điểm của kiến trúc Microservices so với Monolithic trong việc thiết kế Agent. Tôi cần bạn bóc tách sâu.", max_iterations=3)

    print("\n\n" + "#"*60)
    print("▶️ TEST CASE 3: GIAO TIẾP NHANH (Dự kiến sẽ dùng Phi-3 cho text ngắn)")
    print("#"*60)
    await engine.run("Chào bạn, bạn là ai và ai thiết kế ra bạn?", max_iterations=3)

    print("\n" + "="*60)
    print("🏁 HOÀN TẤT KIỂM THỬ GIAI ĐOẠN 2")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(run_tests())
