import asyncio
import sys
import os

# Thêm thư mục gốc vào path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.agent_engine import AgentEngine

async def test_metrics_and_loop():
    agent = AgentEngine()
    
    print("\n--- TEST 1: Kiểm tra tính toán Metrics ---")
    # Giả lập một câu hỏi đơn giản để lấy kết quả nhanh
    result = await agent.run("Chào bạn, bạn là ai?")
    print(f"Result: {result}")
    print(f"Metrics sau Test 1: {agent.metrics}")

    print("\n--- TEST 2: Kiểm tra Force Final Answer (The Ultimatum) ---")
    # Ép max_iterations thấp để thấy cơ chế chốt hạ
    result_ultimatum = await agent.run("Hãy tính 1+1 nhưng đừng trả lời ngay, hãy trả lời ở lượt cuối cùng.", max_iterations=2)
    print(f"Result Ultimatum: {result_ultimatum}")
    print(f"Metrics sau Test 2: {agent.metrics}")

if __name__ == "__main__":
    asyncio.run(test_metrics_and_loop())
