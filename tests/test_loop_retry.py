import asyncio
import json
from unittest.mock import AsyncMock, patch
from core.agent_engine import AgentEngine

async def test_retry_logic():
    agent = AgentEngine(model_name="llama3.2:3b")
    
    # Giả lập LLM response
    # Lần 1: JSON Lỗi (Thiếu key) -> retry_count=1
    # Lần 2: JSON Lỗi -> retry_count=2
    # Lần 3: JSON Hợp lệ (Action) -> iteration=2, retry_count=0
    # Lần 4: JSON Hợp lệ (Answer) -> RETURN
    
    responses = [
        '{"thought": "Lỗi nè"}', # Thiếu answer/action
        '{"invalid": "format"}', # Thiếu thought/answer
        '{"thought": "Dùng tool", "action": "calculate", "params": {"expression": "1+1"}}',
        '{"thought": "Xong", "answer": "Kết quả là 2"}'
    ]
    
    call_count = 0
    
    async def mock_call_llm(*args, **kwargs):
        nonlocal call_count
        res = responses[call_count]
        call_count += 1
        return res

    with patch.object(AgentEngine, '_call_llm', side_effect=mock_call_llm):
        print("--- Testing Loop Retry Logic ---")
        result = await agent.run("Test prompt", max_iterations=5)
        print(f"Final Result: {result}")
        print(f"Total LLM calls: {call_count}")
        # Nếu logic đúng:
        # Call 1 & 2 là retry (vẫn ở iteration 1)
        # Call 3 là tool call (kết thúc iteration 1, sang iteration 2)
        # Call 4 là final answer (kết thúc iteration 2)
        # Vậy iteration cuối cùng trả về phải là 2, nhưng call_count là 4.
        
if __name__ == "__main__":
    asyncio.run(test_retry_logic())
