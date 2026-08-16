import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import timedelta
import google.generativeai as genai

# ==========================================
# CẤU HÌNH TRANG & GIAO DIỆN (UI/UX)
# ==========================================
st.set_page_config(page_title="TRUNG TÂM VẬN HÀNH TOÀN CẢNH GHN", layout="wide", page_icon="🚀")

# Bảng màu chủ đạo: Xanh da trời, Cam, Trắng, Xanh lá, Đỏ
CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;700;900&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Montserrat', sans-serif !important;
    }
    h1, h2, h3 {
        font-weight: 900 !important;
        color: #0077B6 !important; /* Xanh da trời đậm */
        text-transform: uppercase;
    }
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
        font-weight: 700;
        font-size: 16px;
        color: #00B4D8;
    }
    .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {
        border-bottom-color: #FF8C00 !important; /* Cam */
    }
    .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] [data-testid="stMarkdownContainer"] p {
        color: #FF8C00 !important;
    }
    .metric-box {
        background-color: #FFFFFF;
        padding: 15px;
        border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        border-left: 5px solid #00B4D8;
    }
    .metric-title { font-size: 14px; font-weight: 700; color: #555; }
    .metric-value { font-size: 24px; font-weight: 900; color: #0077B6; }
    .metric-delta.up { color: #28A745; font-weight: 700;} /* Xanh lá */
    .metric-delta.down { color: #DC3545; font-weight: 700;} /* Đỏ */
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# Khởi tạo API Key AI (Thay thế bằng Key của bạn)
GEMINI_API_KEY = "YOUR_GEMINI_API_KEY"

# ==========================================
# 1. BẢO MẬT ĐĂNG NHẬP & PHÂN QUYỀN
# ==========================================
def check_login():
    st.markdown("<h1 style='text-align: center; color: #FF8C00;'>🔐 TRUNG TÂM VẬN HÀNH GHN</h1>", unsafe_allow_html=True)
    with st.form("login_form"):
        user_id = st.text_input("Mã Nhân Viên (ID)")
        password = st.text_input("Mật khẩu", type="password")
        submitted = st.form_submit_button("Đăng Nhập")
        
        if submitted:
            if user_id == "ADMIN" and password == "123": # Thay bằng tài khoản thật
                st.session_state.authenticated = True
                st.session_state.role = "Giám Đốc"
                st.rerun()
            elif user_id == "USER" and password == "123":
                st.session_state.authenticated = True
                st.session_state.role = "Nhân Viên"
                st.rerun()
            else:
                st.error("❌ Thông tin không chính xác!")

if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    check_login()
    st.stop()

# ==========================================
# 2. HỆ THỐNG TẢI DỮ LIỆU TỪ 12 LINKS GOOGLE SHEETS
# ==========================================
def make_csv_url(url):
    # Chuyển đổi link edit thành link export CSV
    if "/edit?gid=" in url:
        return url.replace("/edit?gid=", "/export?format=csv&gid=")
    return url

@st.cache_data(ttl=300)
def load_all_data():
    urls = {
        "vh_gtc": "https://docs.google.com/spreadsheets/d/1lJt4ZXVjIPoUYZF73nsPmVfziJSBXBISUWU1ldSxWH4/edit?gid=1806026577",
        "vh_ca": "https://docs.google.com/spreadsheets/d/1lJt4ZXVjIPoUYZF73nsPmVfziJSBXBISUWU1ldSxWH4/edit?gid=2040493559",
        "vh_tra": "https://docs.google.com/spreadsheets/d/1lJt4ZXVjIPoUYZF73nsPmVfziJSBXBISUWU1ldSxWH4/edit?gid=452321599",
        "vh_gtb": "https://docs.google.com/spreadsheets/d/1lJt4ZXVjIPoUYZF73nsPmVfziJSBXBISUWU1ldSxWH4/edit?gid=454179383",
        "vh_tts": "https://docs.google.com/spreadsheets/d/1lJt4ZXVjIPoUYZF73nsPmVfziJSBXBISUWU1ldSxWH4/edit?gid=1164899523",
        "vh_odr": "https://docs.google.com/spreadsheets/d/1lJt4ZXVjIPoUYZF73nsPmVfziJSBXBISUWU1ldSxWH4/edit?gid=1013193026",
        "kd_tong": "https://docs.google.com/spreadsheets/d/1dEC78RcXYcA7e2SVFmjhOfuP-DY57_FXkOCpRpln4vY/edit?gid=339323317",
        "kd_kh_moi": "https://docs.google.com/spreadsheets/d/1dEC78RcXYcA7e2SVFmjhOfuP-DY57_FXkOCpRpln4vY/edit?gid=949412123",
        "kd_pheu": "https://docs.google.com/spreadsheets/d/1dEC78RcXYcA7e2SVFmjhOfuP-DY57_FXkOCpRpln4vY/edit?gid=151781423",
        "ns_1": "https://docs.google.com/spreadsheets/d/1OemA7cIZM-5AAvsnQuQphNArKw43de27W75Z-Ri6BcQ/edit?gid=2000227799",
        "ns_2": "https://docs.google.com/spreadsheets/d/1OemA7cIZM-5AAvsnQuQphNArKw43de27W75Z-Ri6BcQ/edit?gid=1695228663",
        "kpi": "https://docs.google.com/spreadsheets/d/1lJt4ZXVjIPoUYZF73nsPmVfziJSBXBISUWU1ldSxWH4/edit?gid=1344197558"
    }
    
    data = {}
    for key, url in urls.items():
        try:
            df = pd.read_csv(make_csv_url(url))
            # Chuẩn hóa tên cột "ngày", "Thời Gian" thành "Ngày"
            for col in df.columns:
                if col.strip().lower() in ['ngày', 'thời gian', 'thời gian cập nhật']:
                    df.rename(columns={col: 'Ngày'}, inplace=True)
            
            if 'Ngày' in df.columns:
                df['Ngày'] = pd.to_datetime(df['Ngày'], errors='coerce', dayfirst=True)
            data[key] = df
        except:
            # Tạo DataFrame rỗng nếu link hỏng hoặc chưa có dữ liệu để tránh crash App
            data[key] = pd.DataFrame() 
            
    return data

with st.spinner("🔄 Đang đồng bộ hóa dữ liệu thời gian thực từ 12 Server..."):
    db = load_all_data()

# ==========================================
# HÀM HỖ TRỢ TÍNH TOÁN N-1, W-1, M-1
# ==========================================
def get_period_data(df, current_date, val_col):
    if df.empty or 'Ngày' not in df.columns or val_col not in df.columns:
        return 0, 0, 0, 0, 0, 0
        
    current_date = pd.to_datetime(current_date)
    
    # N vs N-1
    val_n = df[df['Ngày'] == current_date][val_col].sum()
    val_n1 = df[df['Ngày'] == (current_date - timedelta(days=1))][val_col].sum()
    
    # W vs W-1
    start_w = current_date - timedelta(days=current_date.weekday())
    val_w = df[(df['Ngày'] >= start_w) & (df['Ngày'] <= current_date)][val_col].sum()
    val_w1 = df[(df['Ngày'] >= start_w - timedelta(days=7)) & (df['Ngày'] < start_w)][val_col].sum()
    
    # M vs M-1
    start_m = current_date.replace(day=1)
    val_m = df[(df['Ngày'] >= start_m) & (df['Ngày'] <= current_date)][val_col].sum()
    start_m1 = (start_m - timedelta(days=1)).replace(day=1)
    val_m1 = df[(df['Ngày'] >= start_m1) & (df['Ngày'] < start_m)][val_col].sum()
    
    return val_n, val_n1, val_w, val_w1, val_m, val_m1

def render_metric_compare(title, curr, prev, is_percent=False):
    delta = curr - prev
    sign = "+" if delta > 0 else ""
    color_class = "up" if delta >= 0 else "down"
    val_format = f"{curr:.2f}%" if is_percent else f"{curr:,.0f}"
    delta_format = f"{sign}{delta:.2f}%" if is_percent else f"{sign}{delta:,.0f}"
    
    html = f"""
    <div class="metric-box">
        <div class="metric-title">{title}</div>
        <div class="metric-value">{val_format}</div>
        <div class="metric-delta {color_class}">{delta_format} so với kỳ trước</div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

# ==========================================
# THANH ĐIỀU HƯỚNG TABS
# ==========================================
st.sidebar.markdown(f"**👤 Xin chào, {st.session_state.role}**")
st.sidebar.button("Đăng xuất", on_click=lambda: st.session_state.clear())

st.sidebar.markdown("---")
st.sidebar.markdown("### 🔍 BỘ LỌC TOÀN CỤC")
global_date = st.sidebar.date_input("Chọn Ngày Phân Tích", pd.Timestamp.today())
global_bc = st.sidebar.text_input("Nhập Bưu Cục (Để trống = Tất cả)", "")

tabs = st.tabs([
    "🌍 TỔNG QUAN", 
    "🚚 VẬN HÀNH", 
    "💰 KINH DOANH", 
    "👥 NĂNG SUẤT & LƯƠNG", 
    "🎯 TIẾN ĐỘ KPI", 
    "🤖 TRỢ LÝ AI COMMANDER"
])

# ==========================================
# TAB 1: TỔNG QUAN CHIẾN LƯỢC
# ==========================================
with tabs[0]:
    st.markdown("## 🌍 TRUNG TÂM ĐIỀU HÀNH TỔNG QUAN")
    st.info("💡 Bảng tin tóm tắt các điểm nóng về Vận hành, Kinh doanh, Tác phong - Kỷ luật.")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 💬 Phân tích Group Chat & Dư luận")
        chat_input = st.text_area("Dán nội dung thảo luận trên nhóm Zalo/Telegram vào đây để AI đọc:", height=150)
        if st.button("Trích xuất thông tin nhóm"):
            if chat_input:
                try:
                    genai.configure(api_key=GEMINI_API_KEY)
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    prompt = f"Phân tích đoạn chat nội bộ sau. Tìm ra các vấn đề điểm nóng liên quan đến: Lương, Thu nhập, Tác phong, Bức xúc. Nêu rõ điểm ĐẠT và CHƯA ĐẠT. Nội dung: {chat_input}"
                    response = model.generate_content(prompt)
                    st.success(response.text)
                except Exception as e:
                    st.error("Lỗi AI. Vui lòng kiểm tra lại API Key.")
                    
    with col2:
        st.markdown("### 🚨 Các điểm Nóng cần chú ý hôm nay")
        st.warning("- **Vận Hành:** Tỷ lệ tồn kho khu vực 1 đang có dấu hiệu tăng 15% so với W-1.\n- **Nhân sự:** 3 nhân viên có Đơn giá trung bình giảm dưới mức tối thiểu.\n- **Kinh Doanh:** Phễu chuyển đổi KH mới đang hẹp ở bước Lên đơn.")

# ==========================================
# TAB 2: VẬN HÀNH
# ==========================================
with tabs[1]:
    st.markdown("## 🚚 CHỈ SỐ VẬN HÀNH")
    col_vh1, col_vh2, col_vh3 = st.columns(3)
    
    df_vh = db["vh_gtc"]
    if not df_vh.empty:
        n, n1, w, w1, m, m1 = get_period_data(df_vh, global_date, 'GTC')
        with col_vh1:
            st.markdown("#### BÁO CÁO GTC TỔNG")
            render_metric_compare("Ngày (N vs N-1)", n, n1)
            render_metric_compare("Tuần (W vs W-1)", w, w1)
            render_metric_compare("Tháng (M vs M-1)", m, m1)
    
    # Biểu đồ GTC
    if not df_vh.empty and 'Ngày' in df_vh.columns:
        fig_vh = px.bar(df_vh.tail(30), x='Ngày', y='Volume', color_discrete_sequence=['#00B4D8'], title="Sản lượng & Tỷ lệ GTC 30 ngày qua")
        st.plotly_chart(fig_vh, use_container_width=True)

# ==========================================
# TAB 3: KINH DOANH
# ==========================================
with tabs[2]:
    st.markdown("## 💰 KẾT QUẢ KINH DOANH")
    
    df_kd = db["kd_tong"]
    if not df_kd.empty and 'Doanh Thu' in df_kd.columns:
        n, n1, w, w1, m, m1 = get_period_data(df_kd, global_date, 'Doanh Thu')
        c1, c2, c3 = st.columns(3)
        with c1: render_metric_compare("Doanh thu Ngày", n, n1)
        with c2: render_metric_compare("Doanh thu Tuần", w, w1)
        with c3: render_metric_compare("Doanh thu Tháng", m, m1)
    
    st.markdown("---")
    col_kd1, col_kd2 = st.columns(2)
    with col_kd1:
        st.markdown("### Phễu Tiếp Xúc Khách Hàng Mới")
        df_pheu = db["kd_pheu"]
        if not df_pheu.empty and len(df_pheu.columns) >= 2:
            fig_funnel = go.Figure(go.Funnel(
                y=df_pheu.iloc[:, 0], # Bước phễu
                x=df_pheu.iloc[:, 1], # Số lượng
                marker={"color": ["#007BFF", "#FF8C00", "#28A745", "#DC3545"]}
            ))
            st.plotly_chart(fig_funnel, use_container_width=True)
            
    with col_kd2:
        st.markdown("### Danh Sách KH Tiềm Năng")
        df_kh = db["kd_kh_moi"]
        if not df_kh.empty and 'Trạng thái' in df_kh.columns:
            kh_tiem_nang = df_kh[df_kh['Trạng thái'].astype(str).str.contains("Tiềm năng", case=False, na=False)]
            st.dataframe(kh_tiem_nang, use_container_width=True)

# ==========================================
# TAB 4: NĂNG SUẤT VÀ LƯƠNG
# ==========================================
with tabs[3]:
    st.markdown("## 👥 NĂNG SUẤT & THU NHẬP NHÂN VIÊN")
    df_ns = db["ns_1"]
    
    if not df_ns.empty:
        # Lọc dữ liệu
        nv_chon = st.selectbox("Chọn Nhân Viên", ["Tất cả"] + list(df_ns['Nhân Viên'].dropna().unique()))
        
        # Logic tính Kỳ Lương GHN
        gd = pd.to_datetime(global_date)
        if gd.day <= 15:
            curr_start = gd.replace(day=1)
            curr_end = gd.replace(day=15)
            prev_end = curr_start - timedelta(days=1)
            prev_start = prev_end.replace(day=16)
            k_name = f"Kỳ 20 ({gd.month})"
            p_name = f"Kỳ 05 ({prev_start.month})"
        else:
            curr_start = gd.replace(day=16)
            curr_end = (gd.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
            prev_start = gd.replace(day=1)
            prev_end = gd.replace(day=15)
            k_name = f"Kỳ 05 ({gd.month})"
            p_name = f"Kỳ 20 ({gd.month})"
            
        st.info(f"📅 **Kỳ Lương Hiện Tại:** {k_name} (So với {p_name})")
        
        # Tổng lương = LHH LTC + LHH GTC + LHH GTBTT
        if all(c in df_ns.columns for c in ['LHH LTC', 'LHH GTC', 'LHH GTBTT']):
            df_ns['Tổng Lương'] = df_ns['LHH LTC'] + df_ns['LHH GTC'] + df_ns['LHH GTBTT']
            
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("### Biểu đồ Tổng Lương")
                fig_luong = px.line(df_ns.tail(15), x='Ngày', y='Tổng Lương', markers=True)
                fig_luong.update_traces(line_color='#28A745', line_width=4)
                st.plotly_chart(fig_luong, use_container_width=True)

# ==========================================
# TAB 5: TIẾN ĐỘ HOÀN THÀNH KPI
# ==========================================
with tabs[4]:
    st.markdown("## 🎯 BẢNG ĐIỀU KHIỂN KPI")
    df_kpi = db["kpi"]
    
    def create_gauge(title, value, kpi):
        fig = go.Figure(go.Indicator(
            mode = "gauge+number+delta",
            value = value,
            delta = {'reference': kpi},
            title = {'text': title},
            gauge = {'axis': {'range': [None, 100]},
                     'bar': {'color': "#007BFF"},
                     'steps': [
                         {'range': [0, kpi*0.8], 'color': "#FFCCCB"},
                         {'range': [kpi*0.8, kpi], 'color': "#FFE5B4"},
                         {'range': [kpi, 100], 'color': "#D4EDDA"}],
                     'threshold': {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': kpi}}))
        return fig

    c1, c2, c3 = st.columns(3)
    with c1: st.plotly_chart(create_gauge("GTC Tổng (%)", 85, 90), use_container_width=True) # Số giả lập
    with c2: st.plotly_chart(create_gauge("GTC TTS (%)", 92, 95), use_container_width=True)
    with c3: st.plotly_chart(create_gauge("Tỷ lệ Trả Hàng (%)", 5, 8), use_container_width=True)

# ==========================================
# TAB 6: HỎI ĐÁP AI (TRỢ LÝ ĐIỀU PHỐI)
# ==========================================
with tabs[5]:
    st.markdown("## 🤖 TRỢ LÝ ĐIỀU PHỐI AI")
    st.write("Hỏi bất kỳ câu hỏi nào về các số liệu trong 12 File Google Sheets đang liên kết.")
    
    user_q = st.chat_input("Nhập câu hỏi (Ví dụ: Doanh thu tuần này so với tuần trước thế nào?)")
    if user_q:
        st.chat_message("user").write(user_q)
        with st.spinner("AI đang truy xuất cơ sở dữ liệu..."):
            try:
                genai.configure(api_key=GEMINI_API_KEY)
                model = genai.GenerativeModel('gemini-1.5-flash')
                
                # Cấp Context cho AI
                context = f"Bạn là Trợ lý Vận Hành. Dữ liệu hiện tại đang có: {list(db.keys())}. "
                prompt = context + "\nCâu hỏi của Giám đốc: " + user_q
                
                res = model.generate_content(prompt)
                st.chat_message("assistant").write(res.text)
            except Exception as e:
                st.error("Chưa cấu hình API Key hoặc lỗi mạng.")
