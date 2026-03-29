import json
import time
import urllib.request

OLLAMA_URL = "http://localhost:11434/api/generate"

def test_ollama():
    print("🚀 Bắt đầu gọi API trực tiếp không qua Gateway...")
    data = {"model": "phi3:mini", "prompt": "Trả lời 'OK' nếu bạn còn sống.", "stream": False}
    req = urllib.request.Request(OLLAMA_URL, json.dumps(data).encode('utf-8'))
    req.add_header('Content-Type', 'application/json')
    
    start = time.time()
    try:
        response = urllib.request.urlopen(req)
        result = json.loads(response.read().decode('utf-8'))
        end = time.time()
        print(f"✅ OLLAMA ĐÃ TRẢ LỜI SAU: {end - start:.2f} GIÂY")
        print(f"Nội dung: {result.get('response', '')}")
    except Exception as e:
        end = time.time()
        print(f"❌ LỖI GỌI API OLLAMA (thời gian chờ: {end - start:.2f}s): {str(e)}")

if __name__ == "__main__":
    test_ollama()
