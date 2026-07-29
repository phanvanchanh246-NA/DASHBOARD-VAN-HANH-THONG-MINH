import os
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import google.generativeai as genai
import requests
from datetime import datetime, timedelta

# ==========================================
# 0. CẤU HÌNH API KEY
# ==========================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "ĐIỀN_API_KEY_GEMINI_CỦA_BẠN_VÀO_ĐÂY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "ĐIỀN_TOKEN_BOT_TELEGRAM_VÀO_ĐÂY") 
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "ĐIỀN_CHAT_ID_NHÓM_VÀO_ĐÂY")

# ==========================================
# 1. CẤU HÌNH TRANG & GIAO DIỆN CHUNG (CSS)
# ==========================================
st.set_page_config(page_title="Dashboard Vận Hành & Kinh Doanh", layout="wide", page_icon="📈")

st.markdown("""
    <style>
    .banner {
        background: linear-gradient(135deg, #007BFF, #4facfe); 
        padding: 25px; border-radius: 12px; color: white;
        margin-bottom: 25px; display: flex; justify-content: space-between;
        align-items: center; border-bottom: 5px solid #FF8C00; 
    }
    .ai-warning {
        background-color: #fff4e5; border-left: 5px solid #FF8C00;
        padding: 15px; border-radius: 5px; margin-bottom: 20px;
        font-size: 15px; line-height: 1.6;
    }
    /* Giao diện Tab in đậm, đóng khung */
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] {
        font-weight: 800 !important; font-size: 16px !important; border: 2px solid #007BFF !important;
        border-radius: 8px 8px 0px 0px !important; padding: 10px 24px !important;
        background-color: #f0f8ff !important; color: #0056b3 !important;
    }
    .stTabs [aria-selected="true"] {
        background-color: #007BFF !important; color: white !important;
        border: 2px solid #007BFF !important; box-shadow: 0px 4px 6px rgba(0,0,0,0.1);
    }
    </style>
""", unsafe_allow_html=True)

def styled_header(text, icon=""):
    st.markdown(f"""
        <div style="background-color: #e6f2ff; color: #0056b3; padding: 12px 20px;
                    border-radius: 8px; border-left: 6px solid #007BFF;
                    font-size: 20px; font-weight: bold; margin-top: 20px; margin-bottom: 15px;">
            {icon} {text}
        </div>
    """, unsafe_allow_html=True)

def draw_combo_chart(df, x_col, bar_y, line_y, title, bar_name="Sản lượng", line_name="% GTC"):
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=df[x_col], y=df[bar_y], name=bar_name, marker_color='rgba(0, 123, 255, 0.4)'), secondary_y=False)
    fig.add_trace(go.Scatter(x=df[x_col], y=df[line_y], name=line_name, mode='lines+markers', line=dict(color='#FF8C00', width=3), marker=dict(size=6)), secondary_y=True)
    fig.update_layout(title=title, plot_bgcolor='rgba(240, 248, 255, 0.5)', hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    fig.update_yaxes(title_text="Sản lượng (Đơn)", secondary_y=False, showgrid=False)
    fig.update_yaxes(title_text="Tỷ lệ (%)", secondary_y=True, showgrid=True, gridcolor='rgba(0,0,0,0.05)', range=[0, 100])
    return fig

# ==========================================
# 2. LẤY DỮ LIỆU TỪ GOOGLE SHEETS (SIÊU BỘ LỌC CHỐNG LỖI)
# ==========================================
def clean_dataframe_numbers(df, text_cols):
    df.columns = df.columns.astype(str).str.strip().str.replace('\xa0', ' ')
    for col in df.columns:
        if col not in text_cols:
            s = df[col].astype(str).str.replace('%', '', regex=False).str.replace(',', '', regex=False).str.replace('đ', '', regex=False).str.replace('VNĐ', '', regex=False).str.strip()
            df[col] = pd.to_numeric(s, errors='coerce').fillna(0.0)
    return df

@st.cache_data(ttl=60)
def get_real_business_data():
    url_kinhdoanh = "https://docs.google.com/spreadsheets/d/1dEC78RcXYcA7e2SVFmjhOfuP-DY57_FXkOCpRpln4vY/export?format=csv&gid=1161540341"
    try:
        df_kd = pd.read_csv(url_kinhdoanh)
        kd_mapping = {
            'Doanh thu': 'Doanh Thu', 'Khách hàng liên hệ': 'Khách Liên Hệ',
            'Khách hàng lên đơn': 'Khách Lên Đơn', 'Doanh thu KH mới': 'Doanh Thu KH Mới'
        }
        df_kd = df_kd.rename(columns=kd_mapping)
        df_kd = clean_dataframe_numbers(df_kd, text_cols=['Ngày', 'Bưu Cục'])
        df_kd['Ngày'] = pd.to_datetime(df_kd['Ngày'], errors='coerce')
        df_kd['Bưu Cục'] = df_kd['Bưu Cục'].astype(str)
        for req in ['Doanh Thu', 'Khách Liên Hệ', 'Khách Lên Đơn', 'Doanh Thu KH Mới']:
            if req not in df_kd.columns: df_kd[req] = 0.0
        return df_kd.dropna(subset=['Ngày'])
    except Exception as e:
        st.error(f"🚨 Lỗi kết nối Google Sheets Kinh Doanh: {e}")
        st.stop()

df_kinhdoanh = get_real_business_data()

@st.cache_data(ttl=60) 
def get_real_data():
    url_vanhanh = "https://docs.google.com/spreadsheets/d/1lJt4ZXVjIPoUYZF73nsPmVfziJSBXBISUWU1ldSxWH4/export?format=csv&gid=501687087"
    url_nhansu = "https://docs.google.com/spreadsheets/d/1OemA7cIZM-5AAvsnQuQphNArKw43de27W75Z-Ri6BcQ/export?format=csv&gid=2000227799"
    try:
        df_vh = pd.read_csv(url_vanhanh)
        df_ns = pd.read_csv(url_nhansu)
        vh_mapping = {
            '%GTC': 'GTC', 'GTC (%)': 'GTC', 'Tỷ lệ GTC': 'GTC', '% GTC': 'GTC',
            'Trả hàng': 'Trả Hàng', 'Tỷ lệ trả hàng': 'Trả Hàng',
            'Volume_TTS': 'Volume TTS', 'GTC TTS': 'GTC_TTS', '%GTC_TTS': 'GTC_TTS',
            'Ontime Giao TTS': 'ODR', 'ODR (%)': 'ODR'
        }
        df_vh = df_vh.rename(columns=vh_mapping)
        ns_mapping = {
            'GTC': '%GTC', 'Tỷ lệ GTC': '%GTC', '% GTC': '%GTC',
            'Đơn giá': 'Đơn Giá', 'Số đơn': 'Số Đơn'
        }
        df_ns = df_ns.rename(columns=ns_mapping)
        df_vh = clean_dataframe_numbers(df_vh, text_cols=['Ngày', 'Bưu Cục', 'Ca'])
        df_ns = clean_dataframe_numbers(df_ns, text_cols=['Ngày', 'Bưu Cục', 'Nhân Viên', 'Loại Hàng'])
        df_vh['Ngày'] = pd.to_datetime(df_vh['Ngày'], errors='coerce')
        df_ns['Ngày'] = pd.to_datetime(df_ns['Ngày'], errors='coerce')
        df_vh['Bưu Cục'] = df_vh['Bưu Cục'].astype(str)
        df_ns['Bưu Cục'] = df_ns['Bưu Cục'].astype(str)
        df_ns['Nhân Viên'] = df_ns['Nhân Viên'].astype(str)
        df_ns['Loại Hàng'] = df_ns['Loại Hàng'].astype(str)
        for req in ['Volume', 'Volume TTS', 'GTC', 'GTC_TTS', 'Trả Hàng', 'ODR']:
            if req not in df_vh.columns: df_vh[req] = 0.0
        for req in ['Số Đơn', 'Đơn Giá', '%GTC']:
            if req not in df_ns.columns: df_ns[req] = 0.0
        return df_vh.dropna(subset=['Ngày']), df_ns.dropna(subset=['Ngày'])
    except Exception as e:
        st.error(f"🚨 Lỗi kết nối Google Sheets: {e}")
        st.stop()

df_vanhanh, df_nhansu = get_real_data()

# ==========================================
# 3. HÀM TRỢ LÝ AI
# ==========================================
st.markdown("""
    <div class="banner">
        <div>
            <h1 style="color: white; margin-bottom: 0;">DASHBOARD QUẢN LÝ TỔNG THỂ GHN</h1>
            <p style="font-size: 16px; opacity: 0.9;">Vận Hành - Năng Suất - KPI - Kinh Doanh | AI Tự động phân tích theo Tab</p>
        </div>
    </div>
""", unsafe_allow_html=True)

col_rf1, _ = st.columns([2, 8])
with col_rf1:
    if st.button("🔄 Làm mới dữ liệu thủ công", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

@st.cache_data(ttl=60, show_spinner=False)
def get_ai_analysis(prompt_text):
    if not GEMINI_API_KEY or GEMINI_API_KEY == "ĐIỀN_API_KEY_GEMINI_CỦA_BẠN_VÀO_ĐÂY":
        return "⚠️ **CHƯA CẤU HÌNH API KEY:** Vui lòng thêm biến môi trường GEMINI_API_KEY trên Render."
    try:
        genai.configure(api_key=GEMINI_API_KEY.strip())
        model = genai.GenerativeModel('gemini-1.5-flash') 
        detailed_config = genai.types.GenerationConfig(max_output_tokens=2048, temperature=0.4)
        response = model.generate_content(prompt_text, generation_config=detailed_config)
        return response.text
    except Exception as e:
        return f"❌ Lỗi từ máy chủ Google AI: {e}"

def render_ai_and_telegram(ai_result, tab_name, key_suffix):
    st.markdown(f'<div class="ai-warning"><b>🤖 Cố vấn AI ({tab_name}):</b><br><br>{ai_result}</div>', unsafe_allow_html=True)
    if st.button(f"📤 Bắn báo cáo {tab_name} lên nhóm Telegram", key=f"btn_tele_{key_suffix}"):
        if not TELEGRAM_TOKEN or TELEGRAM_TOKEN == "ĐIỀN_TOKEN_BOT_TELEGRAM_VÀO_ĐÂY":
            st.warning("Bạn chưa cấu hình TELEGRAM_TOKEN trên máy chủ Render!")
        else:
            try:
                clean_text = ai_result.replace('**', '').replace('*', '')
                message = f"🚨 BÁO CÁO {tab_name.upper()} 🚨\n\n{clean_text}"
                url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
                payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
                req = requests.post(url, json=payload)
                if req.status_code == 200:
                    st.success("✅ Đã bắn báo cáo thành công lên nhóm Telegram!")
                else:
                    st.error(f"❌ Lỗi khi gửi Telegram (Mã lỗi {req.status_code})")
            except Exception as e:
                st.error(f"Lỗi mạng: {e}")

st.divider()

# ==========================================
# 4. GIAO DIỆN CÁC TAB BIỂU ĐỒ 
# ==========================================
tab1, tab2, tab3, tab4 = st.tabs(["🚚 VẬN HÀNH CHI TIẾT", "👥 NĂNG SUẤT & LƯƠNG", "🎯 VẬN HÀNH THEO KPI", "💰 KINH DOANH"])

# ----------------- TAB 1: VẬN HÀNH -----------------
with tab1:
    col1, col2 = st.columns(2)
    with col1:
        date_range_vh = st.date_input("Khoảng thời gian (Vận hành)", [df_vanhanh['Ngày'].min(), df_vanhanh['Ngày'].max()], key="date_vh")
    with col2:
        buu_cuc_vh = st.selectbox("Chọn Bưu cục", ["Tất cả"] + list(df_vanhanh['Bưu Cục'].unique()), key="bc_vh")
        
    mask_vh = pd.Series(True, index=df_vanhanh.index)
    if len(date_range_vh) == 2:
        # Cập nhật code lọc ngày chuẩn xác (Sửa lỗi convert bool)
        mask_vh &= (df_vanhanh['Ngày'] >= pd.to_datetime(date_range_vh[0])) & (df_vanhanh['Ngày'] <= pd.to_datetime(date_range_vh[1]))
    if buu_cuc_vh != "Tất cả":
        mask_vh &= (df_vanhanh['Bưu Cục'] == buu_cuc_vh)
    df_vh_filtered = df_vanhanh[mask_vh].copy()

    styled_header("1. TỔNG QUAN GTC VÀ TỶ LỆ TRẢ HÀNG", "🌍")
    chart_col1, chart_col2 = st.columns(2)
    df_trend_daily = df_vh_filtered.groupby('Ngày').agg({'Volume': 'sum', 'GTC': 'mean', 'Trả Hàng': 'mean'}).reset_index()
    with chart_col1:
        fig_gtc = draw_combo_chart(df_trend_daily, 'Ngày', 'Volume', 'GTC', "Tỷ lệ Giao Thành Công (%GTC) và Sản Lượng")
        st.plotly_chart(fig_gtc, use_container_width=True)
    with chart_col2:
        fig_return = px.line(df_trend_daily, x='Ngày', y='Trả Hàng', markers=True, title="Tỷ lệ Trả Hàng Theo Ngày (%)")
        fig_return.update_traces(line=dict(color='#FF3333', width=3), marker=dict(size=8))
        fig_return.update_layout(plot_bgcolor='rgba(255, 240, 240, 0.5)')
        st.plotly_chart(fig_return, use_container_width=True)

    styled_header("2. PHÂN TÍCH TIKTOK SHOP & ONTIME GIAO TTS (ODR)", "🛒")
    chart_col3, chart_col4 = st.columns(2)
    df_tts = df_vh_filtered.groupby('Ngày').agg({'Volume TTS': 'sum', 'GTC_TTS': 'mean', 'ODR': 'mean'}).reset_index()
    with chart_col3:
        fig_tts = draw_combo_chart(df_tts, 'Ngày', 'Volume TTS', 'GTC_TTS', "Tỷ lệ GTC TiktokShop (TTS)", bar_name="Sản lượng TTS", line_name="% GTC TTS")
        st.plotly_chart(fig_tts, use_container_width=True)
    with chart_col4:
        fig_odr = px.line(df_tts, x='Ngày', y='ODR', markers=True, title="Tỷ lệ Đơn Hàng Tồn (ODR TikTokShop)")
        fig_odr.update_traces(line=dict(color='#007BFF', width=3), marker=dict(size=8, color='#FF8C00'))
        fig_odr.update_layout(plot_bgcolor='rgba(240, 248, 255, 0.5)', yaxis=dict(range=[70, 100]))
        st.plotly_chart(fig_odr, use_container_width=True)

    styled_header("3. NĂNG SUẤT GIAO THEO CA LÀM VIỆC", "🕒")
    df_ca = df_vh_filtered.groupby(['Ngày', 'Ca']).agg({'Volume': 'sum', 'GTC': 'mean'}).reset_index()
    fig_ca = px.bar(df_ca, x='Ngày', y='Volume', color='Ca', barmode='group', title="Sản lượng theo Ca làm việc")
    fig_ca.update_layout(plot_bgcolor='rgba(240, 248, 255, 0.5)')
    st.plotly_chart(fig_ca, use_container_width=True)

    with st.spinner("🔄 AI đang phân tích dữ liệu Vận Hành..."):
        prompt_vh = f"""
        Dữ liệu Vận Hành (Đã lọc theo bưu cục {buu_cuc_vh}): 
        - Tổng đơn: {df_vh_filtered['Volume'].sum()}
        - Tỷ lệ GTC: {df_vh_filtered['GTC'].mean():.2f}%
        - Tỷ lệ Tồn kho: {df_vh_filtered['ODR'].mean():.2f}%
        Nhiệm vụ: Đóng vai Giám đốc vận hành. Phân tích CHUYÊN SÂU theo 3 phần: 1. Đánh giá tổng quan, 2. Phân tích Rủi ro, 3. Đề xuất hành động. Viết tiếng Việt chuẩn, không bỏ dở câu.
        """
        ai_vh_result = get_ai_analysis(prompt_vh)
    render_ai_and_telegram(ai_vh_result, "Vận Hành", "vh")


# ----------------- TAB 2: NĂNG SUẤT & LƯƠNG -----------------
with tab2:
    f_col1, f_col2, f_col3, f_col4 = st.columns(4)
    with f_col1:
        date_range_ns = st.date_input("Khoảng thời gian (Nhân sự)", [df_nhansu['Ngày'].min(), df_nhansu['Ngày'].max()], key="date_ns")
    with f_col2:
        loai_hang_filter = st.multiselect("Lọc Loại Hàng", ["Hàng nhỏ", "Hàng cồng kềnh"], default=["Hàng nhỏ", "Hàng cồng kềnh"], key="lh_filter")
    with f_col3:
        bc_list = ["Tất cả"] + list(df_nhansu['Bưu Cục'].unique())
        buu_cuc_ns = st.selectbox("Lọc Bưu cục", bc_list, key="bc_ns_tab2")
    with f_col4:
        if buu_cuc_ns == "Tất cả":
            nv_list = ["Tất cả"] + list(df_nhansu['Nhân Viên'].unique())
        else:
            nv_list = ["Tất cả"] + list(df_nhansu[df_nhansu['Bưu Cục'] == buu_cuc_ns]['Nhân Viên'].unique())
        nhan_vien_ns = st.selectbox("Lọc Nhân viên", nv_list, key="nv_ns_tab2")

    mask_ns = pd.Series(True, index=df_nhansu.index)
    if len(date_range_ns) == 2:
        # Cập nhật code lọc ngày chuẩn xác
        mask_ns &= (df_nhansu['Ngày'] >= pd.to_datetime(date_range_ns[0])) & (df_nhansu['Ngày'] <= pd.to_datetime(date_range_ns[1]))
    if loai_hang_filter:
        mask_ns &= df_nhansu['Loại Hàng'].isin(loai_hang_filter)
    if buu_cuc_ns != "Tất cả":
        mask_ns &= (df_nhansu['Bưu Cục'] == buu_cuc_ns)
    if nhan_vien_ns != "Tất cả":
        mask_ns &= (df_nhansu['Nhân Viên'] == nhan_vien_ns)
    df_ns_filtered = df_nhansu[mask_ns].copy()

    styled_header("PHÂN TÍCH ĐƠN GIÁ & NĂNG SUẤT GIAO", "📈")
    chart_ns1, chart_ns2 = st.columns(2)
    with chart_ns1:
        if nhan_vien_ns != "Tất cả":
            df_dongia = df_ns_filtered.groupby('Ngày')['Đơn Giá'].mean().reset_index()
            title_dongia = f"Biến động Đơn Giá của {nhan_vien_ns}"
        elif buu_cuc_ns != "Tất cả":
            df_dongia = df_ns_filtered.groupby('Ngày')['Đơn Giá'].mean().reset_index()
            title_dongia = f"Đơn giá trung bình tại {buu_cuc_ns}"
        else:
            df_dongia = df_ns_filtered.groupby('Ngày')['Đơn Giá'].mean().reset_index()
            title_dongia = "Đơn giá trung bình toàn hệ thống"
        fig_dg = px.line(df_dongia, x='Ngày', y='Đơn Giá', markers=True, title=title_dongia)
        fig_dg.update_traces(line=dict(color='#FF8C00', width=3), marker=dict(size=8, color='#007BFF'))
        fig_dg.update_layout(plot_bgcolor='rgba(240, 248, 255, 0.5)', yaxis_title="VNĐ")
        st.plotly_chart(fig_dg, use_container_width=True)

    with chart_ns2:
        df_gtc_nv = df_ns_filtered.groupby('Ngày').agg({'Số Đơn': 'sum', '%GTC': 'mean'}).reset_index()
        title_gtc = f"Năng suất & %GTC của {nhan_vien_ns}" if nhan_vien_ns != "Tất cả" else "Năng suất & %GTC toàn hệ thống"
        fig_gtc_nv = draw_combo_chart(df_gtc_nv, 'Ngày', 'Số Đơn', '%GTC', title_gtc, bar_name="Số Đơn Đã Giao", line_name="% GTC")
        st.plotly_chart(fig_gtc_nv, use_container_width=True)

    with st.spinner("🔄 AI đang phân tích dữ liệu Năng Suất..."):
        prompt_ns = f"""
        Dữ liệu Năng suất Nhân sự (Đã lọc): 
        - Tổng đơn đã giao: {df_ns_filtered['Số Đơn'].sum()}
        - Đơn giá trung bình: {df_ns_filtered['Đơn Giá'].mean():,.0f} VNĐ
        Nhiệm vụ: Đóng vai Quản lý nhân sự. Đánh giá chuyên sâu 3 phần: 1. Đánh giá năng suất, 2. Rủi ro chi phí, 3. Đề xuất nhân sự.
        """
        ai_ns_result = get_ai_analysis(prompt_ns)
    render_ai_and_telegram(ai_ns_result, "Năng Suất & Nhân Sự", "ns")


# ----------------- TAB 3: BÁO CÁO VẬN HÀNH THEO KPI -----------------
with tab3:
    styled_header("CÀI ĐẶT & THEO DÕI KPI VẬN HÀNH", "🎯")
    with st.expander("⚙️ ĐIỀU CHỈNH KPI (Khu vực / Bưu cục)", expanded=True):
        kpi_col1, kpi_col2, kpi_col3 = st.columns(3)
        with kpi_col1:
            kpi_gtc_target = st.number_input("Mục tiêu KPI %GTC Chung", min_value=0.0, max_value=100.0, value=90.0, step=0.5, key="kpi_gtc")
        with kpi_col2:
            kpi_tts_target = st.number_input("Mục tiêu KPI %GTC TikTokShop", min_value=0.0, max_value=100.0, value=85.0, step=0.5, key="kpi_tts")
        with kpi_col3:
            kpi_odr_target = st.number_input("KPI Ontime Giao TTS (ODR) tối đa", min_value=0.0, max_value=100.0, value=5.0, step=0.5, key="kpi_odr")

    t3_col1, t3_col2 = st.columns(2)
    with t3_col1:
        date_range_kpi = st.date_input("Chọn thời gian", [df_vanhanh['Ngày'].min(), df_vanhanh['Ngày'].max()], key="date_kpi")
    with t3_col2:
        buu_cuc_kpi = st.selectbox("Chọn Bưu cục", ["Tất cả"] + list(df_vanhanh['Bưu Cục'].unique()), key="bc_kpi")

    mask_kpi = pd.Series(True, index=df_vanhanh.index)
    if len(date_range_kpi) == 2:
        # Cập nhật code lọc ngày chuẩn xác
        mask_kpi &= (df_vanhanh['Ngày'] >= pd.to_datetime(date_range_kpi[0])) & (df_vanhanh['Ngày'] <= pd.to_datetime(date_range_kpi[1]))
    if buu_cuc_kpi != "Tất cả":
        mask_kpi &= (df_vanhanh['Bưu Cục'] == buu_cuc_kpi)
    df_kpi_filtered = df_vanhanh[mask_kpi].copy()

    actual_gtc = df_kpi_filtered['GTC'].mean() if not df_kpi_filtered.empty else 0
    actual_tts = df_kpi_filtered['GTC_TTS'].mean() if not df_kpi_filtered.empty else 0
    actual_odr = df_kpi_filtered['ODR'].mean() if not df_kpi_filtered.empty else 0
    
    gauge_col1, gauge_col2, gauge_col3 = st.columns(3)
    def create_gauge(title, value, target, inverse_color=False):
        color = "green" if (value >= target and not inverse_color) or (value <= target and inverse_color) else "red"
        fig = go.Figure(go.Indicator(
            mode = "gauge+number+delta", value = value, domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': title, 'font': {'size': 20}},
            delta = {'reference': target, 'increasing': {'color': "red" if inverse_color else "green"}, 'decreasing': {'color': "green" if inverse_color else "red"}},
            gauge = {
                'axis': {'range': [None, 100], 'tickwidth': 1, 'tickcolor': "darkblue"},
                'bar': {'color': color},
                'steps': [
                    {'range': [0, target if not inverse_color else 100], 'color': "rgba(255,0,0,0.1)" if not inverse_color else "rgba(0,255,0,0.1)"},
                    {'range': [target if not inverse_color else 0, 100 if not inverse_color else target], 'color': "rgba(0,255,0,0.1)" if not inverse_color else "rgba(255,0,0,0.1)"}
                ],
            }
        ))
        fig.update_layout(height=300, margin=dict(l=10, r=10, t=40, b=10))
        return fig

    with gauge_col1:
        st.plotly_chart(create_gauge("Tỷ lệ GTC Chung (%)", actual_gtc, kpi_gtc_target), use_container_width=True)
    with gauge_col2:
        st.plotly_chart(create_gauge("Tỷ lệ GTC TikTokShop (%)", actual_tts, kpi_tts_target), use_container_width=True)
    with gauge_col3:
        st.plotly_chart(create_gauge("Ontime Giao TTS ODR (%)", actual_odr, kpi_odr_target, inverse_color=True), use_container_width=True)

    st.markdown("**BẢNG THEO DÕI HOÀN THÀNH KPI THEO NGÀY**")
    df_kpi_table = df_kpi_filtered.groupby('Ngày').agg({'GTC':'mean', 'GTC_TTS':'mean', 'ODR':'mean'}).reset_index()
    df_kpi_table['Ngày'] = df_kpi_table['Ngày'].dt.strftime('%d-%m-%Y')
    df_kpi_table['% Đạt KPI GTC'] = (df_kpi_table['GTC'] / kpi_gtc_target) * 100
    st.dataframe(df_kpi_table.style.format({"GTC": "{:.2f}%", "GTC_TTS": "{:.2f}%", "ODR": "{:.2f}%", "% Đạt KPI GTC": "{:.1f}%"}), use_container_width=True)

    with st.spinner("🔄 AI đang đánh giá mức độ đạt KPI..."):
        prompt_kpi = f"""
        Mục tiêu: GTC > {kpi_gtc_target}%, GTC TikTok > {kpi_tts_target}%, Tồn kho < {kpi_odr_target}%.
        Thực tế: GTC: {actual_gtc:.2f}%, GTC TikTok: {actual_tts:.2f}%, Tồn kho: {actual_odr:.2f}%.
        Đóng vai Giám đốc kiểm soát. Đưa ra: 1. Đánh giá nhanh việc đạt/trượt KPI, 2. Cảnh báo nghiêm trọng nếu trượt, 3. Yêu cầu hành động khẩn.
        """
        ai_kpi_result = get_ai_analysis(prompt_kpi)
    render_ai_and_telegram(ai_kpi_result, "KPI Vận Hành", "kpi")


# ----------------- TAB 4: KINH DOANH -----------------
with tab4:
    styled_header("BÁO CÁO DOANH THU & KHÁCH HÀNG MỚI", "💰")
    with st.expander("⚙️ ĐIỀU CHỈNH KPI DOANH THU", expanded=True):
        kpi_dt_target = st.number_input("Mục tiêu Doanh thu (VNĐ / Ngày)", min_value=0, value=30000000, step=1000000, key="kpi_dt")
    
    t4_col1, t4_col2, t4_col3 = st.columns(3)
    with t4_col1:
        date_range_kd = st.date_input("Chọn thời gian", [df_kinhdoanh['Ngày'].max() - timedelta(days=7), df_kinhdoanh['Ngày'].max()], key="date_kd")
    with t4_col2:
        buu_cuc_kd = st.selectbox("Chọn Bưu cục", ["Tất cả"] + list(df_kinhdoanh['Bưu Cục'].unique()), key="bc_kd")
    with t4_col3:
        view_type = st.selectbox("Góc nhìn báo cáo", ["Theo Ngày", "Theo Tuần", "Theo Tháng"], key="view_kd")

    current_date = df_kinhdoanh['Ngày'].max()
    if len(date_range_kd) == 2:
        current_date = pd.to_datetime(date_range_kd[1])
        
    mask_kd = pd.Series(True, index=df_kinhdoanh.index)
    if buu_cuc_kd != "Tất cả":
        mask_kd &= (df_kinhdoanh['Bưu Cục'] == buu_cuc_kd)
    df_filtered_kd = df_kinhdoanh[mask_kd]
    
    rev_n = df_filtered_kd[df_filtered_kd['Ngày'] == current_date]['Doanh Thu'].sum()
    rev_n1 = df_filtered_kd[df_filtered_kd['Ngày'] == (current_date - timedelta(days=1))]['Doanh Thu'].sum()
    rev_w1 = df_filtered_kd[df_filtered_kd['Ngày'] == (current_date - timedelta(days=7))]['Doanh Thu'].sum()
    rev_m1 = df_filtered_kd[df_filtered_kd['Ngày'] == (current_date - timedelta(days=30))]['Doanh Thu'].sum()

    st.markdown(f"**Hiệu suất Doanh thu ngày {current_date.strftime('%d-%m-%Y')}**")
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    m_col1.metric("Doanh Thu Hiện Tại (N)", f"{rev_n:,.0f} đ", f"{(rev_n - kpi_dt_target)/kpi_dt_target*100:.1f}% vs KPI")
    m_col2.metric("So với N-1 (Hôm qua)", f"{rev_n1:,.0f} đ", f"{rev_n - rev_n1:,.0f} đ")
    m_col3.metric("So với W-1 (Tuần trước)", f"{rev_w1:,.0f} đ", f"{rev_n - rev_w1:,.0f} đ")
    m_col4.metric("So với M-1 (Tháng trước)", f"{rev_m1:,.0f} đ", f"{rev_n - rev_m1:,.0f} đ")
    
    mask_kd_range = mask_kd.copy()
    if len(date_range_kd) == 2:
        # Cập nhật code lọc ngày chuẩn xác
        mask_kd_range &= (df_kinhdoanh['Ngày'] >= pd.to_datetime(date_range_kd[0])) & (df_kinhdoanh['Ngày'] <= pd.to_datetime(date_range_kd[1]))
    
    df_plot_kd = df_kinhdoanh[mask_kd_range].groupby('Ngày').agg({
        'Doanh Thu': 'sum', 'Khách Liên Hệ': 'sum', 'Khách Lên Đơn': 'sum', 'Doanh Thu KH Mới': 'sum'
    }).reset_index()

    chart_kd1, chart_kd2 = st.columns(2)
    with chart_kd1:
        fig_rev = px.bar(df_plot_kd, x='Ngày', y='Doanh Thu', title="Biểu đồ Doanh Thu & KPI", color_discrete_sequence=['#28a745'])
        fig_rev.add_hline(y=kpi_dt_target, line_dash="dash", line_color="red", annotation_text="KPI Mục Tiêu")
        fig_rev.update_layout(plot_bgcolor='rgba(240, 248, 255, 0.5)')
        st.plotly_chart(fig_rev, use_container_width=True)

    with chart_kd2:
        total_lh = df_plot_kd['Khách Liên Hệ'].sum()
        total_ld = df_plot_kd['Khách Lên Đơn'].sum()
        total_rev_new = df_plot_kd['Doanh Thu KH Mới'].sum()
        fig_funnel = go.Figure(go.Funnel(
            y=["Khách Liên Hệ", "Khách Lên Đơn (Chuyển đổi)"],
            x=[total_lh, total_ld], textinfo="value+percent initial"
        ))
        fig_funnel.update_layout(title=f"Phễu chuyển đổi KH Mới (Tổng DT: {total_rev_new:,.0f} đ)")
        st.plotly_chart(fig_funnel, use_container_width=True)

    with st.spinner("🔄 AI đang phân tích hiệu suất Kinh Doanh..."):
        prompt_kd = f"""
        Phân tích Kinh doanh: KPI ngày {kpi_dt_target:,.0f}. Thực tế (N): {rev_n:,.0f}. So với hôm qua (N-1): {rev_n1:,.0f}. Phễu KH: {total_lh} liên hệ -> {total_ld} lên đơn.
        Nhiệm vụ: Đóng vai Giám đốc Kinh doanh. Hãy phân tích 3 phần: 1. Lời khen/Cảnh báo việc chạy số, 2. Đánh giá tỷ lệ chốt sale, 3. Đề xuất chiến lược khẩn cấp.
        """
        ai_kd_result = get_ai_analysis(prompt_kd)
    render_ai_and_telegram(ai_kd_result, "Kinh Doanh", "kd")
