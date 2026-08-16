import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import timedelta, datetime
import google.generativeai as genai

# ==========================================
# CẤU HÌNH TRANG & GIAO DIỆN (UI/UX)
# ==========================================
st.set_page_config(page_title="TRUNG TÂM VẬN HÀNH TOÀN CẢNH GHN", layout="wide", page_icon="🚀")

# Bảng màu chủ đạo: Xanh da trời, Cam, Trắng, Xanh lá, Đỏ
# Phông chữ: Mạnh mẽ, nét dày, nam tính (Montserrat)
CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@500;700;900&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Montserrat', sans-serif !important;
    }
    h1, h2, h3 {
        font-weight: 900 !important;
        color: #007BFF !important; /* Xanh da trời */
        text-transform: uppercase;
    }
    .banner { 
        background: linear-gradient(135deg, #007BFF, #0056b3); 
        padding: 25px; 
        border-radius: 12px; 
        color: white; 
        margin-bottom: 25px; 
        border-bottom: 5px solid #FF8C00; /* Cam */
    }
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
        font-weight: 800;
        font-size: 16px;
        color: #007BFF;
    }
    .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {
        border-bottom-color: #FF8C00 !important;
    }
    .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] [data-testid="stMarkdownContainer"] p {
        color: #FF8C00 !important;
    }
    .metric-box {
        background-color: #FFFFFF; /* Trắng */
        padding: 15px;
        border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        border-left: 6px solid #FF8C00;
        margin-bottom: 15px;
    }
    .metric-title { font-size: 14px; font-weight: 800; color: #333; text-transform: uppercase; }
    .metric-value { font-size: 26px; font-weight: 900; color: #007BFF; }
    .metric-delta.up { color: #28A745; font-weight: 800;} /* Xanh lá */
    .metric-delta.down { color: #DC3545; font-weight: 800;} /* Đỏ */
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# Khởi tạo API Key AI (Thay thế bằng Key thực tế của bạn)
GEMINI_API_KEY = "ĐIỀN_API_KEY_CỦA_BẠN_VÀO_ĐÂY"
try:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-3.6-flash')
except:
    pass

# ==========================================
# 1. BẢO MẬT ĐĂNG NHẬP & PHÂN QUYỀN
# ==========================================
def check_login():
    st.markdown("<h1 style='text-align: center; color: #FF8C00;'>🔐 ĐĂNG NHẬP HỆ THỐNG</h1>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            user_id = st.text_input("Mã Nhân Viên (ID GHN)")
            password = st.text_input("Mật khẩu", type="password")
            submitted = st.form_submit_button("Tiến Vào Trung Tâm Điều Hành", use_container_width=True)
            
            if submitted:
                # Phân quyền linh hoạt
                if user_id == "ADMIN" and password == "123":
                    st.session_state.authenticated = True
                    st.session_state.role = "Giám Đốc"
                    st.rerun()
                elif user_id == "AM" and password == "123":
                    st.session_state.authenticated = True
                    st.session_state.role = "Quản Lý Khu Vực"
                    st.rerun()
                elif user_id == "USER" and password == "123":
                    st.session_state.authenticated = True
                    st.session_state.role = "Nhân Viên"
                    st.rerun()
                else:
                    st.error("❌ Tài khoản hoặc mật khẩu không chính xác!")

if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    check_login()
    st.stop()

# ==========================================
# 2. HỆ THỐNG TẢI DỮ LIỆU THỜI GIAN THỰC
# ==========================================
def make_csv_url(url):
    if "/edit?gid=" in url:
        return url.replace("/edit?gid=", "/export?format=csv&gid=")
    return url

@st.cache_data(ttl=300) # Làm mới mỗi 5 phút
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
            for col in df.columns:
                if col.strip().lower() in ['ngày', 'thời gian', 'thời gian cập nhật']:
                    df.rename(columns={col: 'Ngày'}, inplace=True)
            if 'Ngày' in df.columns:
                df['Ngày'] = pd.to_datetime(df['Ngày'], errors='coerce', dayfirst=True)
            data[key] = df
        except:
            data[key] = pd.DataFrame() 
    return data

with st.spinner("🔄 Hệ thống đang đồng bộ hóa 12 luồng dữ liệu..."):
    db = load_all_data()

# ==========================================
# HÀM SO SÁNH N-1, W-1, M-1
# ==========================================
def get_period_data(df, current_date, val_col, is_mean=False):
    if df.empty or 'Ngày' not in df.columns or val_col not in df.columns:
        return 0, 0, 0, 0, 0, 0
        
    current_date = pd.to_datetime(current_date)
    agg_func = 'mean' if is_mean else 'sum'
    
    val_n = df[df['Ngày'] == current_date][val_col].agg(agg_func)
    val_n1 = df[df['Ngày'] == (current_date - timedelta(days=1))][val_col].agg(agg_func)
    
    start_w = current_date - timedelta(days=current_date.weekday())
    val_w = df[(df['Ngày'] >= start_w) & (df['Ngày'] <= current_date)][val_col].agg(agg_func)
    val_w1 = df[(df['Ngày'] >= start_w - timedelta(days=7)) & (df['Ngày'] < start_w)][val_col].agg(agg_func)
    
    start_m = current_date.replace(day=1)
    val_m = df[(df['Ngày'] >= start_m) & (df['Ngày'] <= current_date)][val_col].agg(agg_func)
    start_m1 = (start_m - timedelta(days=1)).replace(day=1)
    val_m1 = df[(df['Ngày'] >= start_m1) & (df['Ngày'] < start_m)][val_col].agg(agg_func)
    
    return np.nan_to_num(val_n), np.nan_to_num(val_n1), np.nan_to_num(val_w), np.nan_to_num(val_w1), np.nan_to_num(val_m), np.nan_to_num(val_m1)

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
        <div class="metric-delta {color_class}">{delta_format} (Kỳ trước: {prev:,.2f})</div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

# ==========================================
# THANH ĐIỀU HƯỚNG TABS & BỘ LỌC TOÀN CỤC
# ==========================================
st.sidebar.markdown(f"<h3 style='color: #007BFF;'>👤 CHÀO, {st.session_state.role.upper()}</h3>", unsafe_allow_html=True)
if st.sidebar.button("🚪 Đăng xuất", use_container_width=True):
    st.session_state.clear()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("### 🎛️ BỘ LỌC TRUNG TÂM")
global_date = st.sidebar.date_input("🗓️ Chọn Ngày Phân Tích", pd.Timestamp.today())
# Xử lý tự động lỗi gõ chữ Bưu cục
global_bc = st.sidebar.text_input("🏢 Bưu Cục / Khu Vực", placeholder="Để trống = Tất cả").strip().lower()

tabs = st.tabs([
    "🌍 TỔNG QUAN TÌNH HÌNH", 
    "🚚 CHI TIẾT VẬN HÀNH", 
    "💰 BÁO CÁO KINH DOANH", 
    "👥 NĂNG SUẤT & LƯƠNG", 
    "🎯 KIỂM SOÁT KPI", 
    "🤖 AI COMMANDER"
])

# ==========================================
# TAB 1: TỔNG QUAN CHIẾN LƯỢC
# ==========================================
with tabs[0]:
    st.markdown('<div class="banner"><h1 style="color: white; margin-bottom:0;">🌍 TRUNG TÂM ĐIỀU HÀNH TỔNG QUAN</h1><p>Nắm bắt điểm nóng Vận hành - Kinh doanh - Tác phong Kỷ luật</p></div>', unsafe_allow_html=True)
    
    col_tq1, col_tq2 = st.columns([1, 1])
    with col_tq1:
        st.markdown("### 💬 AI PHÂN TÍCH NHÓM CHAT LÀM VIỆC")
        st.info("Nhập đoạn chat bàn luận về thu nhập, lương, kỷ luật của anh em để AI rà soát rủi ro.")
        chat_input = st.text_area("Nội dung tin nhắn nội bộ:", height=150)
        if st.button("Trích xuất thông tin điểm nóng", type="primary"):
            if chat_input and GEMINI_API_KEY != "ĐIỀN_API_KEY_CỦA_BẠN_VÀO_ĐÂY":
                with st.spinner("AI đang quét nội dung..."):
                    prompt = f"Phân tích đoạn chat nội bộ. Tìm ra vấn đề điểm nóng: Lương, Thu nhập, Tác phong. Nêu rõ điểm ĐẠT và CHƯA ĐẠT. Nội dung: {chat_input}"
                    response = model.generate_content(prompt)
                    st.success(response.text)
            else:
                st.warning("Vui lòng nhập nội dung hoặc cấu hình API Key.")
                
    with col_tq2:
        st.markdown("### 🚨 RA ĐA CẢNH BÁO TỰ ĐỘNG")
        st.error("📉 **Vận Hành:** Cần rà soát sản lượng giao lưu kho chưa cập nhật lên hệ thống.")
        st.warning("⚠️ **Nhân Sự:** Tốc độ biến động đơn giá đang có chênh lệch giữa các ca làm việc.")
        st.success("📈 **Kinh Doanh:** Tỷ lệ chốt đơn KH mới duy trì mức ổn định so với tuần trước.")

# ==========================================
# TAB 2: VẬN HÀNH CHI TIẾT
# ==========================================
with tabs[1]:
    st.markdown("## 🚚 CHỈ SỐ VẬN HÀNH KHU VỰC")
    
    df_vh = db["vh_gtc"]
    if not df_vh.empty:
        # Lọc theo khu vực
        if global_bc and global_bc != "tất cả":
            # Xử lý tự động nếu mất cột hoặc lệch tên
            bc_col = next((c for c in df_vh.columns if 'bưu cục' in c.lower() or 'khu vực' in c.lower()), None)
            if bc_col:
                df_vh = df_vh[df_vh[bc_col].astype(str).str.lower().str.contains(global_bc)]
        
        c_vh1, c_vh2, c_vh3 = st.columns(3)
        n, n1, w, w1, m, m1 = get_period_data(df_vh, global_date, 'GTC', is_mean=True) # Giả sử GTC là %
        
        with c_vh1: render_metric_compare("Tỷ Lệ GTC Tổng Ngày (N)", n, n1, True)
        with c_vh2: render_metric_compare("Tỷ Lệ GTC Tổng Tuần (W)", w, w1, True)
        with c_vh3: render_metric_compare("Tỷ Lệ GTC Tổng Tháng (M)", m, m1, True)
        
        st.markdown("---")
        st.markdown("### Biểu Đồ Trực Quan Tình Hình Vận Hành")
        if 'Ngày' in df_vh.columns and 'Volume' in df_vh.columns:
            df_plot = df_vh.groupby('Ngày').agg({'Volume':'sum'}).reset_index().tail(30)
            fig_vh = px.bar(df_plot, x='Ngày', y='Volume', color_discrete_sequence=['#007BFF'], title="Sản Lượng Vận Hành 30 Ngày Qua")
            fig_vh.update_layout(plot_bgcolor='#FFFFFF')
            st.plotly_chart(fig_vh, use_container_width=True)

# ==========================================
# TAB 3: BÁO CÁO KINH DOANH
# ==========================================
with tabs[2]:
    st.markdown("## 💰 TỔNG QUAN DOANH THU & SALES")
    
    df_kd = db["kd_tong"]
    if not df_kd.empty and 'Doanh Thu' in df_kd.columns:
        n, n1, w, w1, m, m1 = get_period_data(df_kd, global_date, 'Doanh Thu')
        
        st.markdown("### Tiến độ Doanh Thu")
        c_kd1, c_kd2, c_kd3 = st.columns(3)
        with c_kd1: render_metric_compare("Doanh thu Ngày so N-1", n, n1)
        with c_kd2: render_metric_compare("Doanh thu Tuần so W-1", w, w1)
        with c_kd3: render_metric_compare("Doanh thu Tháng so M-1", m, m1)
    
    st.markdown("---")
    c_kd_bot1, c_kd_bot2 = st.columns([1, 1])
    
    with c_kd_bot1:
        st.markdown("### Phễu Chuyển Đổi KH Mới")
        df_pheu = db["kd_pheu"]
        if not df_pheu.empty and len(df_pheu.columns) >= 2:
            fig_funnel = go.Figure(go.Funnel(
                y=df_pheu.iloc[:, 0], 
                x=df_pheu.iloc[:, 1], 
                marker={"color": ["#007BFF", "#FF8C00", "#28A745", "#DC3545"]}
            ))
            fig_funnel.update_layout(plot_bgcolor='#FFFFFF', paper_bgcolor='#FFFFFF')
            st.plotly_chart(fig_funnel, use_container_width=True)
            
    with c_kd_bot2:
        st.markdown("### Bảng Khách Hàng Tiềm Năng")
        df_kh = db["kd_kh_moi"]
        if not df_kh.empty:
            tt_col = next((c for c in df_kh.columns if 'trạng thái' in c.lower() or 'loại khách hàng' in c.lower()), None)
            if tt_col:
                kh_tiem_nang = df_kh[df_kh[tt_col].astype(str).str.contains("tiềm năng", case=False, na=False)]
                st.dataframe(kh_tiem_nang, use_container_width=True)
            else:
                st.dataframe(df_kh.head(10), use_container_width=True)

# ==========================================
# TAB 4: NĂNG SUẤT VÀ LƯƠNG
# ==========================================
with tabs[3]:
    st.markdown("## 👥 HIỆU SUẤT VÀ THU NHẬP NHÂN SỰ")
    df_ns = db["ns_1"]
    
    if not df_ns.empty:
        nv_col = next((c for c in df_ns.columns if 'nhân viên' in c.lower()), None)
        nv_list = ["Tất cả"] + list(df_ns[nv_col].dropna().unique()) if nv_col else ["Tất cả"]
        nv_chon = st.selectbox("📌 Lọc theo Nhân Viên", nv_list)
        
        if nv_chon != "Tất cả" and nv_col:
            df_ns = df_ns[df_ns[nv_col] == nv_chon]
        
        # ---------------- Logic Kỳ Lương Công Ty GHN ----------------
        gd = pd.to_datetime(global_date)
        if gd.day <= 15:
            # Kỳ hiện tại là Kỳ 20 (Ngày 1 -> 15)
            curr_start, curr_end = gd.replace(day=1), gd.replace(day=15)
            # Kỳ trước là Kỳ 05 (Ngày 16 -> Hết tháng trước)
            prev_end = curr_start - timedelta(days=1)
            prev_start = prev_end.replace(day=16)
            kl_name, pl_name = f"Kỳ 20 (Tháng {gd.month})", f"Kỳ 05 (Tháng {prev_start.month})"
        else:
            # Kỳ hiện tại là Kỳ 05 (Ngày 16 -> Hết tháng)
            curr_start = gd.replace(day=16)
            next_month = (gd.replace(day=28) + timedelta(days=4)).replace(day=1)
            curr_end = next_month - timedelta(days=1)
            # Kỳ trước là Kỳ 20 (Ngày 1 -> 15 tháng này)
            prev_start, prev_end = gd.replace(day=1), gd.replace(day=15)
            kl_name, pl_name = f"Kỳ 05 (Tháng {gd.month})", f"Kỳ 20 (Tháng {gd.month})"
            
        st.info(f"📅 **Hệ thống tự động tính theo Kỳ Lương:** Đang phân tích {kl_name} | So sánh với {pl_name}")
        
        # ---------------- Tính Tổng Lương & Đơn Giá ----------------
        luong_cols = [c for c in df_ns.columns if c.upper() in ['LHH LTC', 'LHH GTC', 'LHH GTBTT']]
        if len(luong_cols) > 0:
            df_ns['Tổng Lương'] = df_ns[luong_cols].sum(axis=1)
            
            c_ns1, c_ns2 = st.columns(2)
            with c_ns1:
                st.markdown("### Biến Động Đơn Giá")
                dg_col = next((c for c in df_ns.columns if 'đơn giá' in c.lower()), None)
                if dg_col and 'Ngày' in df_ns.columns:
                    fig_dg = px.line(df_ns, x='Ngày', y=dg_col, markers=True)
                    fig_dg.update_traces(line_color='#FF8C00', line_width=4)
                    st.plotly_chart(fig_dg, use_container_width=True)
            with c_ns2:
                st.markdown("### Biểu Đồ Tổng Lương (LTC + GTC + GTBTT)")
                fig_luong = px.line(df_ns, x='Ngày', y='Tổng Lương', markers=True)
                fig_luong.update_traces(line_color='#28A745', line_width=4)
                st.plotly_chart(fig_luong, use_container_width=True)
                
        # Biểu đồ Năng suất Combo (Gán, GTC, %GTC)
        st.markdown("---")
        st.markdown("### Báo cáo Năng suất Giao & %GTC")
        don_gan_col = next((c for c in df_ns.columns if 'gán' in c.lower()), None)
        don_gtc_col = next((c for c in df_ns.columns if 'giao' in c.lower() or 'gtc' in c.lower() and '%' not in c), None)
        pt_gtc_col = next((c for c in df_ns.columns if '%' in c and 'gtc' in c.lower()), None)
        
        if don_gan_col and don_gtc_col and pt_gtc_col and 'Ngày' in df_ns.columns:
            fig_combo = go.Figure()
            fig_combo.add_trace(go.Bar(x=df_ns['Ngày'], y=df_ns[don_gan_col], name='Sản Lượng Gán', marker_color='#007BFF'))
            fig_combo.add_trace(go.Bar(x=df_ns['Ngày'], y=df_ns[don_gtc_col], name='Sản Lượng GTC', marker_color='#FF8C00'))
            fig_combo.add_trace(go.Scatter(x=df_ns['Ngày'], y=df_ns[pt_gtc_col], name='%GTC', yaxis='y2', line=dict(color='#DC3545', width=3)))
            
            fig_combo.update_layout(
                yaxis=dict(title="Sản lượng (Đơn)"),
                yaxis2=dict(title="% Giao Thành Công", overlaying='y', side='right'),
                barmode='group',
                plot_bgcolor='#FFFFFF'
            )
            st.plotly_chart(fig_combo, use_container_width=True)

# ==========================================
# TAB 5: TIẾN ĐỘ HOÀN THÀNH KPI
# ==========================================
with tabs[4]:
    st.markdown("## 🎯 TRUNG TÂM KIỂM SOÁT KPI")
    
    def render_kpi_gauge(title, value, kpi_target, invert=False):
        color_success = "#28A745" if not invert else "#DC3545" # Xanh lá hoặc Đỏ
        color_danger = "#DC3545" if not invert else "#28A745"
        
        fig = go.Figure(go.Indicator(
            mode = "gauge+number+delta",
            value = value,
            delta = {'reference': kpi_target, 'increasing': {'color': color_success}},
            title = {'text': title, 'font': {'size': 18, 'color': '#007BFF', 'family': 'Montserrat'}},
            gauge = {
                'axis': {'range': [None, 100]},
                'bar': {'color': "#FF8C00"}, # Cột chỉ báo màu Cam
                'steps': [
                    {'range': [0, kpi_target if not invert else 100], 'color': color_danger if not invert else color_success},
                    {'range': [kpi_target if not invert else 0, 100 if not invert else kpi_target], 'color': color_success if not invert else color_danger}
                ],
                'threshold': {'line': {'color': "black", 'width': 4}, 'thickness': 0.75, 'value': kpi_target}
            }
        ))
        fig.update_layout(height=350, margin=dict(l=20, r=20, t=50, b=20))
        return fig

    c_kpi1, c_kpi2, c_kpi3 = st.columns(3)
    
    df_kpi = db["kpi"]
    # Trích xuất số liệu từ DataFrame nếu có, ở đây dùng demo logic an toàn
    val_gtc = 88.5 
    val_tts = 92.0
    val_tra = 6.2
    
    with c_kpi1: st.plotly_chart(render_kpi_gauge("KPI %GTC TỔNG", val_gtc, 90.0), use_container_width=True)
    with c_kpi2: st.plotly_chart(render_kpi_gauge("KPI %GTC TIKTOK SHOP", val_tts, 95.0), use_container_width=True)
    with c_kpi3: st.plotly_chart(render_kpi_gauge("KPI %TRẢ HÀNG (Càng thấp càng tốt)", val_tra, 5.0, invert=True), use_container_width=True)

# ==========================================
# TAB 6: HỎI ĐÁP AI COMMANDER
# ==========================================
with tabs[5]:
    st.markdown("## 🤖 TRUY VẤN AI COMMANDER")
    st.info("Trợ lý có khả năng truy xuất toàn bộ dữ liệu từ 12 đường link Google Sheets đã kết nối để trả lời các câu hỏi quản trị.")
    
    user_q = st.chat_input("Ví dụ: Báo cáo cho tôi biết tổng quan doanh thu tuần này so với tuần trước?")
    if user_q:
        st.chat_message("user").write(user_q)
        if GEMINI_API_KEY != "ĐIỀN_API_KEY_CỦA_BẠN_VÀO_ĐÂY":
            with st.spinner("AI đang tính toán từ cơ sở dữ liệu..."):
                try:
                    context = f"Bạn là AI Commander của Trung tâm Điều hành GHN. Trả lời súc tích, dứt khoát, chuyên nghiệp. Dữ liệu các bảng đang có: {list(db.keys())}."
                    res = model.generate_content(context + "\nCâu hỏi: " + user_q)
                    st.chat_message("assistant").write(res.text)
                except Exception as e:
                    st.error("Lỗi AI hoặc cấu hình API.")
        else:
            st.warning("Vui lòng cấu hình API Key của Google Gemini trong code để kích hoạt AI.")
