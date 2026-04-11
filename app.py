import streamlit as st
import asyncio
import json
from core.agent_engine import AgentEngine
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

# [EPIC 4] Settings State

if "temp_val" not in st.session_state:
    st.session_state.temp_val = 0.2
if "iter_val" not in st.session_state:
    st.session_state.iter_val = 5
if "turbo_mode" not in st.session_state:
    st.session_state.turbo_mode = False
if "base_model" not in st.session_state: st.session_state.base_model = "llama3.2:3b"

# ==========================================
# [RESOURCE LAYER]: Tối ưu VRAM cấp độ Enterprise (Chống rò rỉ bộ nhớ)
# ==========================================
@st.cache_resource
def get_engine_cache():
    """Khởi tạo một Dictionary duy nhất để quản lý Engine"""
    return {} # Trả về một từ điển trống

# Lấy từ điển quản lý Engine
engine_manager = get_engine_cache()

# Lấy tên Model hiện tại từ UI
current_model = st.session_state.base_model

# Logic "One-In, One-Out" (Chỉ giữ 1 model trong RAM)
if current_model not in engine_manager:
    # Nếu đổi Model -> XÓA SẠCH model cũ khỏi từ điển để giải phóng VRAM
    engine_manager.clear() 
    
    print(f"\n[SYSTEM] [INITIALIZING] AgentEngine with {current_model}...\n")
    engine_manager[current_model] = AgentEngine(model_name=current_model)

# Lấy Engine ra để sử dụng
engine = engine_manager[current_model]

# ==========================================
# [TELEMETRY LAYER]: 3 Golden Moments Strategy
# ==========================================
# ==========================================
# [TELEMETRY LAYER]: 3 Golden Moments Strategy
# ==========================================
# ==========================================
# [TELEMETRY LAYER]: 3 Golden Moments Strategy
# ==========================================
def render_telemetry(container):
    """Render giao diện giám sát Phần cứng & Hiệu năng vào một placeholder"""
    raw_stats = monitor.get_gpu_stats()
    
    # [KHIÊN BẢO VỆ]: Nếu NVML lỗi, dùng data giả để giữ khung UI không bị sập
    stats = raw_stats or {
        "vram_used": 0, "vram_total": 4096, "vram_percent": 0.0,
        "temp": 0, "gpu_util": 0, "status": "offline"
    }

    # Đọc Metrics từ bộ não Agent
    try:
        with open("agent_metrics.json", "r", encoding="utf-8") as f:
            agent_metrics = json.load(f)
    except Exception:
        agent_metrics = {"success": 0, "fail": 0, "total_runs": 0, "avg_latency": 0.0}

    # [FIX LỖI GHI ĐÈ UI TẠI ĐÂY]: Thêm .container()
    with container.container(): 
        # ===============================================
        # 1. RADAR PHẦN CỨNG (SẼ KHÔNG BỊ MẤT NỮA)
        # ===============================================
        st.subheader("🖥️ Hardware Radar")
        
        if not raw_stats:
            st.error("❌ NVML Offline: Đang hiển thị Mock Data")

        col1, col2 = st.columns([2, 1])
        with col1:
            # Vẽ thanh Progress VRAM (Cộng thêm min() để chống lỗi > 100%)
            vram_usage = min(stats["vram_percent"] / 100.0, 1.0)
            st.progress(vram_usage, text=f"VRAM: {stats['vram_percent']}%")
        with col2:
            st.write(f"{stats['vram_used']}/{stats['vram_total']} MB")
        
        # Hiển thị Nhiệt độ & Core Load
        temp = stats["temp"]
        gpu_util = stats.get("gpu_util", 0) 
        temp_color = "red" if temp > 80 else ("orange" if temp > 70 else "green")
        st.markdown(f"🌡️ **Temperature:** :{temp_color}[{temp}°C] | ⚡ **Core Load:** {gpu_util}%")
        
        # Cảnh báo an toàn
        if temp > 85:
            st.error("⚠️ CRITICAL: GPU quá nóng! Hãy tạm dừng để hạ nhiệt.")
        elif stats["vram_percent"] > 90:
            st.warning("⚠️ VRAM Check: Bộ nhớ sắp đầy!")
            
        st.caption(f"Status: {stats['status'].upper()} | Driver: NVIDIA NVML")
        
        st.divider() # Đường kẻ phân cách

        # ===============================================
        # 2. THỐNG KÊ HIỆU NĂNG AI
        # ===============================================
        st.subheader("📈 Agent Metrics")
        success = agent_metrics.get("success", 0)
        total = agent_metrics.get("total_runs", 0)
        success_rate = (success / total * 100) if total > 0 else 0.0

        m_col1, m_col2, m_col3 = st.columns(3)
        m_col1.metric("Tổng Runs", total)
        m_col2.metric("Tỉ lệ mượt", f"{success_rate:.1f}%") 
        m_col3.metric("Độ trễ (s)", f"{agent_metrics.get('avg_latency', 0):.2f}")

# ==========================================
# [BRIDGE LAYER] Wrapper an toàn
# ==========================================
class AsyncBridge:
    @staticmethod
    def run_agent(engine_instance, user_input, max_iter, temp, event_callback=None):
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(engine_instance.run(
                user_input, 
                max_iterations=max_iter, 
                temperature=temp,
                callback=event_callback
            ))
        finally:
            asyncio.set_event_loop(None) 
            loop.close()


# ==========================================
# SIDEBAR & MOMENT 1 (Initialization)
# ==========================================
with st.sidebar:
    st.title("📟 Control Center")
    st.markdown("---")
    
    # Placeholder cho Telemetry
    telemetry_container = st.empty()
    render_telemetry(telemetry_container)
    
    st.markdown("---")
    # [EPIC 4] Settings Section
    st.subheader("⚙️ Engine Settings")

    # Tính năng chọn Model an toàn
   # Thêm "Auto (Smart Router)" lên đầu danh sách
    available_models = ["Auto (Smart Router)", "llama3.2:3b", "phi3:mini", "qwen2.5:3b"]
    if "base_model" not in st.session_state: 
        st.session_state.base_model = "Auto (Smart Router)" # Đặt mặc định là Auto
    selected_model = st.selectbox(
        "🧠 Base Model", 
        available_models, 
        index=available_models.index(st.session_state.base_model)
    )

    # NẾU PHÁT HIỆN ĐỔI MODEL -> GIẬT SẬP CACHE ĐỂ GIẢI PHÓNG VRAM
    if selected_model != st.session_state.base_model:
        st.session_state.base_model = selected_model
        st.cache_resource.clear() # Xóa sạch Cache VRAM
        st.rerun() # F5 tải lại trang để nạp model mới

    st.markdown("---") # Đường kẻ phân cách
    
    turbo = st.toggle("🚀 Turbo Mode", value=st.session_state.turbo_mode, help="Ép phản hồi nhanh nhất (Temp=0, Iter=3)")
    st.session_state.turbo_mode = turbo
    
    # Nếu bật Turbo Mode thì khóa slider
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
    if st.button("🔄 Refresh Monitor", use_container_width=True):
        render_telemetry(telemetry_container)
        
    if st.button("🗑️ Clear History", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# ==========================================
# MAIN UI
# ==========================================
st.title("🤖 THE IMMORTAL AI AGENT")
st.caption("Quadro T2000 Edition | Self-Healing Core v2.0")

# Hiển thị lịch sử chat
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Input với Safety Lock
user_input = st.chat_input("Hỏi tôi bất cứ điều gì...", disabled=st.session_state.is_running)

if user_input:
    # MOMENT 2 (Pre-run)
    render_telemetry(telemetry_container)
    
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    st.session_state.is_running = True
    
    with st.chat_message("assistant"):
        status_placeholder = st.status("🔮 Agent đang phân tích...", expanded=True)
        
        def on_agent_event(event_type, data):
            display_data = str(data)
            if len(display_data) > 300:
                display_data = display_data[:300] + "..."

            with status_placeholder:
                if event_type == "THINK":
                    st.markdown(f"**🤔 THINK:** _{display_data}_")
                    status_placeholder.update(label="🤔 Đang suy nghĩ...")
                elif event_type == "ACT":
                    st.markdown(f"🛠️ **ACT:** `{display_data}`")
                    status_placeholder.update(label="🛠️ Đang sử dụng công cụ...")
                elif event_type == "OBSERVE":
                    st.info(f"👁️ **OBSERVE:** {display_data}")
                    status_placeholder.update(label="👁️ Phân tích kết quả...")
                elif event_type == "REPAIR":
                    st.warning(f"⚠️ **SELF-REPAIR:** {display_data}")
                    status_placeholder.update(label="⚠️ Tự động sửa lỗi...")

        # Chạy Agent với thông số động
        final_temp = 0.0 if st.session_state.turbo_mode else st.session_state.temp_val
        final_iter = 3 if st.session_state.turbo_mode else st.session_state.iter_val
        
        response = AsyncBridge.run_agent(
            engine, 
            user_input, 
            max_iter=final_iter,
            temp=final_temp,
            event_callback=on_agent_event
        )
        
        status_placeholder.update(label="✅ Xử lý hoàn tất!", state="complete", expanded=False)
        st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})

    # MOMENT 3 (Post-run): Cập nhật VRAM sau khi xả cache
    st.session_state.is_running = False
    st.rerun()

# Raw Data Viewer nằm độc lập bên ngoài
st.markdown("---")
with st.expander("🔍 Raw Data Viewer (Context Research)"):
    st.json(st.session_state.messages)