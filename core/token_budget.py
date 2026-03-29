# Cần cài đặt thư viện: pip install tiktoken
import tiktoken

def token_budget_control(messages, max_tokens=3000):
    """
    Hàm gọt tỉa Token (Tránh OOM cho card 4GB VRAM).
    Đảm bảo tổng số token đầu vào luôn dưới max_tokens (mặc định 3000) 
    để dành 1000 tokens cho mô hình sinh văn bản (Output).
    """
    try:
        encoding = tiktoken.get_encoding("cl100k_base") # Chuẩn cho các model hiện đại
    except Exception as e:
        print("Vui lòng cài đặt tiktoken: pip install tiktoken")
        raise e
    
    total_tokens = sum([len(encoding.encode(m.get('content', ''))) for m in messages])
    
    # Chiến lược Sliding Window: Cắt bớt history nếu quá tải
    # Giữ lại messages có index 0 (System Prompt) và index cuối (User Query hiện tại)
    while total_tokens > max_tokens and len(messages) > 2:
        # Loại bỏ message cũ thứ 2 (sau system prompt)
        removed_msg = messages.pop(1)
        removed_tokens = len(encoding.encode(removed_msg.get('content', '')))
        total_tokens -= removed_tokens
        print(f"⚠️ Đã cắt bớt tin nhắn (độ dài {removed_tokens} tokens) để cứu VRAM 4GB!")
        
    return messages

if __name__ == "__main__":
    # Ví dụ kiểm tra thuật toán:
    mock_messages = [
        {"role": "system", "content": "You are a helpful assistant architecture."},
        {"role": "user", "content": "Hello, this is the 1st history msg." * 200}, # Cố tình làm content dài
        {"role": "assistant", "content": "I understand." * 200},
        {"role": "user", "content": "What is the token budget limit?"}
    ]
    
    print(f"Số lượng tin nhắn ban đầu: {len(mock_messages)}")
    trimmed_messages = token_budget_control(mock_messages, max_tokens=3000)
    print(f"Số lượng tin nhắn sau khi gọt: {len(trimmed_messages)}")
    for msg in trimmed_messages:
        print(f" - Role: {msg['role']}, Độ dài: {len(msg['content'])} kí tự")
