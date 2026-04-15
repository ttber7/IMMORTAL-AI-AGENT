import os
import warnings
os.environ["TRANSFORMERS_VERBOSITY"] = "error" 
warnings.filterwarnings("ignore", message=".*Accessing.*__path__.*")
warnings.filterwarnings("ignore", category=DeprecationWarning)

import streamlit as st
import json
import httpx
import time

from core.resource_monitor import monitor

st.set_page_config(
    page_title="THE IMMORTAL AI - Command Center",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Khởi tạo Session State
if "messages" not in st.session_state:
    st.session_state.messages = []

if "is_running" not in st.session_state:
    st.session_state.is_running = False

if "last_ui_update" not in st.session_state:
    st.session_state.last_ui_update = 0.0

# Settings State
if "temp_val" not in st.session_state: st.session_state.temp_val = 0.2
if "iter_val" not in st.session_state: st.session_state.iter_val = 5
if "turbo_mode" not in st.session_state: st.session_state.turbo_mode = False
if "base_model" not in st.session_state: st.session_state.base_model = "llama3.2:3b"

BACKEND_URL = "http://localhost:8000"

@st.cache_data(ttl=1)
def get_cached_gpu_stats():
    return monitor.get_gpu_stats()

@st.cache_data(ttl=2)
def get_cached_metrics():
    try:
        with open("agent_metrics.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"success": 0, "fail": 0, "total_runs": 0, "avg_latency": 0.0}

def render_telemetry(container):
    raw_stats = get_cached_gpu_stats()
    stats = raw_stats or {
        "vram_used": 0, "vram_total": 4096, "vram_percent": 0.0,
        "temp": 0, "gpu_util": 0, "status": "offline"
    }

    agent_metrics = get_cached_metrics()

    with container.container(): 
        st.subheader("🖥️ Hardware Radar")
        if not raw_stats:
            st.error("❌ NVML Offline: Đang hiển thị Mock Data")

        col1, col2 = st.columns([2, 1])
        with col1:
            vram_usage = min(stats["vram_percent"] / 100.0, 1.0)
            st.progress(vram_usage, text=f"VRAM: {stats['vram_percent']}%")
        with col2:
            st.write(f"{stats['vram_used']}/{stats['vram_total']} MB")
        
        temp = stats["temp"]
        gpu_util = stats.get("gpu_util", 0) 
        temp_color = "red" if temp > 80 else ("orange" if temp > 70 else "green")
        st.markdown(f"🌡️ **Temperature:** :{temp_color}[{temp}°C] | ⚡ **Core Load:** {gpu_util}%")
        
        if temp > 85:
            st.error("⚠️ CRITICAL: GPU quá nóng! Hãy tạm dừng để hạ nhiệt.")
        elif stats["vram_percent"] > 90:
            st.warning("⚠️ VRAM Check: Bộ nhớ sắp đầy!")
            
        st.caption(f"Status: {stats['status'].upper()} | Driver: NVIDIA NVML")
        st.divider() 

        st.subheader("📈 Agent Metrics")
        success = agent_metrics.get("success", 0)
        total = agent_metrics.get("total_runs", 0)
        success_rate = (success / total * 100) if total > 0 else 0.0

        m_col1, m_col2, m_col3 = st.columns(3)
        m_col1.metric("Tổng Runs", total)
        m_col2.metric("Tỉ lệ mượt", f"{success_rate:.1f}%") 
        m_col3.metric("Độ trễ (s)", f"{agent_metrics.get('avg_latency', 0):.2f}")

# ==========================================
# SIDEBAR
# ==========================================
with st.sidebar:
    st.title("📟 Control Center")
    st.markdown("---")
    telemetry_container = st.empty()
    render_telemetry(telemetry_container)
    st.markdown("---")
    
    st.subheader("⚙️ Engine Settings")
    available_models = ["Auto (Smart Router)", "llama3.2:3b", "phi3:mini", "qwen2.5:3b"]
    
    selected_model = st.selectbox(
        "🧠 Base Model", 
        available_models, 
        index=available_models.index(st.session_state.base_model)
    )

    if selected_model != st.session_state.base_model:
        st.session_state.base_model = selected_model
        st.rerun() 

    st.markdown("---") 
    turbo = st.toggle("🚀 Turbo Mode", value=st.session_state.turbo_mode, help="Ép phản hồi nhanh nhất (Temp=0, Iter=3)")
    st.session_state.turbo_mode = turbo
    
    temp_input = st.slider("Creativity (Temp)", 0.0, 1.0, 
                          value=0.0 if turbo else st.session_state.temp_val, 
                          disabled=turbo)
    iter_input = st.slider("Brain Power (Iter)", 1, 10, 
                          value=3 if turbo else st.session_state.iter_val, 
                          disabled=turbo)
    
    if not turbo:
        st.session_state.temp_val = temp_input
        st.session_state.iter_val = iter_input

    if st.button("♻️ Reset to Default", use_container_width=True):
        st.session_state.temp_val = 0.2
        st.session_state.iter_val = 5
        st.session_state.turbo_mode = False
        st.rerun()

    st.markdown("---")
    if st.button("🔄 Reload RAG (Admin)", use_container_width=True):
        try:
            res = httpx.post(f"{BACKEND_URL}/admin/reload-rag", timeout=30.0)
            if res.status_code == 200:
                st.success("Tải lại tri thức thành công!")
            else:
                st.error("Lỗi khi tải lại tri thức.")
        except Exception as e:
            st.error(f"Không thể kết nối đến Backend: {e}")

    if st.button("🗑️ Clear History", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# ==========================================
# MAIN UI
# ==========================================
st.title("🤖 THE IMMORTAL AI AGENT")
st.caption("Quadro T2000 Edition | Microservices v6.0")

for message in st.session_state.messages:
    if not message.get("is_temp", False):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

user_input = st.chat_input("Hỏi tôi bất cứ điều gì...", disabled=st.session_state.is_running)

if user_input:
    render_telemetry(telemetry_container)
    
    st.session_state.messages.append({"role": "user", "content": user_input, "is_temp": False})
    with st.chat_message("user"):
        st.markdown(user_input)

    st.session_state.is_running = True
    st.session_state.last_ui_update = 0.0
    
    with st.chat_message("assistant"):
        status_placeholder = st.status("🔮 Đang kết nối Backend...", expanded=True)
            
        final_temp = 0.0 if st.session_state.turbo_mode else st.session_state.temp_val
        final_iter = 3 if st.session_state.turbo_mode else st.session_state.iter_val
        
        payload = {
            "messages": st.session_state.messages,
            "model": st.session_state.base_model,
            "temperature": final_temp,
            "max_iterations": final_iter,
            "turbo_mode": st.session_state.turbo_mode
        }

        response_text = ""
        try:
            # 🟢 FIX 3: Timeout Tối ưu & Tường minh
            timeout_config = httpx.Timeout(connect=5.0, read=120.0, write=10.0, pool=5.0)
            
            with httpx.Client(timeout=timeout_config) as client:
                with client.stream("POST", f"{BACKEND_URL}/chat", json=payload) as response:
                    for line in response.iter_lines():
                        # 🟢 FIX 1: Parsing SSE An toàn tuyệt đối (Chống rác)
                        if not line:
                            continue
                            
                        line = line.strip()
                        
                        # Bỏ qua Heartbeat mặc định của SSE (dòng bắt đầu bằng dấu hai chấm)
                        if line.startswith(":"): 
                            continue

                        if not line.startswith("data:"):
                            continue
                            
                        json_str = line.replace("data:", "", 1).strip()
                        
                        try:
                            data = json.loads(json_str)
                            event = data.get("event")
                            event_data = data.get("data", "")
                            
                            current_time = time.time()
                            is_fast = (current_time - st.session_state.last_ui_update) < 0.2
                            
                            display_data = str(event_data)
                            if len(display_data) > 300:
                                display_data = display_data[:300] + "..."

                            with status_placeholder:
                                if event == "FINAL_ANSWER":
                                    response_text = event_data
                                # 🟢 ƯU TIÊN 2: Hứng từng Token (Streaming Nâng cấp)
                                elif event == "ANSWER_CHUNK":
                                    response_text += event_data
                                    # Streaming mượt mà trên UI (bạn có thể cải tiến render sau)
                                    status_placeholder.update(label="✍️ Đang viết câu trả lời...")
                                elif event == "THINK":
                                    if not is_fast: st.markdown(f"**🤔 THINK:** _{display_data}_")
                                    status_placeholder.update(label="🤔 Đang suy nghĩ...")
                                elif event == "ACT":
                                    if not is_fast: st.markdown(f"🛠️ **ACT:** `{display_data}`")
                                    status_placeholder.update(label="🛠️ Đang sử dụng công cụ...")
                                elif event == "OBSERVE":
                                    if not is_fast: st.info(f"👁️ **OBSERVE:** {display_data}")
                                    status_placeholder.update(label="👁️ Phân tích kết quả...")
                                elif event == "REPAIR":
                                    st.warning(f"⚠️ **SELF-REPAIR:** {display_data}")
                                    status_placeholder.update(label="⚠️ Tự động sửa lỗi...")
                                elif event == "QUEUE_WAITING":
                                    status_placeholder.update(label=f"⏳ Đang chờ GPU (Vị trí: {display_data})...")
                                # 🟢 FIX 2: Bắt Heartbeat từ Server để giữ UI "Sống"
                                elif event == "PING":
                                    status_placeholder.update(label="💓 Đang duy trì kết nối...")
                                elif event == "ERROR":
                                    raise Exception(event_data)
                                    
                            st.session_state.last_ui_update = current_time
                            
                        except json.JSONDecodeError:
                            continue

            status_placeholder.empty()
            if response_text:
                st.markdown(response_text)
                st.session_state.messages.append({"role": "assistant", "content": response_text, "is_temp": False})
            else:
                raise Exception("Không nhận được kết quả cuối cùng từ server.")
            
        except httpx.ConnectError:
            status_placeholder.update(label="❌ Backend Server không phản hồi!", state="error", expanded=False)
            st.error("Không thể kết nối đến AI Engine (FastAPI). Hãy chắc chắn server.py đang chạy.")
        except Exception as e:
            status_placeholder.update(label="❌ Xử lý thất bại!", state="error", expanded=False)
            st.error(f"Hệ thống gặp sự cố: {str(e)}")

    st.session_state.is_running = False
    st.rerun()

st.markdown("---")
with st.expander("🔍 Raw Data Viewer (Context Research)"):
    st.json(st.session_state.messages)