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
import dateutil.relativedelta

# ==========================================
# 0. CẤU HÌNH API KEY
# ==========================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "ĐIỀN_API_KEY_GEMINI_CỦA_BẠN_VÀO_ĐÂY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "ĐIỀN_TOKEN_BOT_TELEGRAM_VÀO_ĐÂY") 
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "ĐIỀN_CHAT_ID_NHÓM_VÀO_ĐÂY")

# ==========================================
# KHỞI TẠO BỘ NHỚ LƯU TRỮ (SESSION STATE)
# ==========================================
if "authenticated" not in st.session_state: st.session_state.authenticated = False
if "kpi_gtc_dict" not in st.session_state: st.session_state.kpi_gtc_dict = {"Tất cả": 70.0}
if "kpi_tts_dict" not in st.session_state: st.session_state.kpi_tts_dict = {"Tất cả": 80.0}
if "kpi_odr_dict" not in st.session_state: st.session_state.kpi_odr_dict = {"Tất cả": 98.0} 
if "kpi_dt_dict" not in st.session_state: st.session_state.kpi_dt_dict = {"Tất cả": 71000000.0}

if "ai_vh_result" not in st.session_state: st.session_state.ai_vh_result = "Bấm nút '🔍 Nhờ AI Phân tích' để xem cố vấn chi tiết."
if "ai_ns_result" not in st.session_state: st.session_state.ai_ns_result = "Bấm nút '🔍 Nhờ AI Phân tích' để xem cố vấn chi tiết."
if "ai_kpi_result" not in st.session_state: st.session_state.ai_kpi_result = "Bấm nút '🔍 Nhờ AI Phân tích' để xem cố vấn chi tiết."
if "ai_kd_result" not in st.session_state: st.session_state.ai_kd_result = "Bấm nút '🔍 Nhờ AI Phân tích' để xem cố vấn chi tiết."
if "ai_td_result" not in st.session_state: st.session_state.ai_td_result = "Bấm nút '🔍 AI Đánh giá Chương trình Thi đua' để xem cố vấn chi tiết."

# Bộ nhớ cho Chatbot
if "chat_history" not in st.session_state: st.session_state.chat_history = []

# ==========================================
# 1. CẤU HÌNH TRANG & GIAO DIỆN CHUNG (CSS)
# ==========================================
st.set_page_config(page_title="Dashboard Vận Hành & Kinh Doanh", layout="wide", page_icon="📈")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800;900&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif !important;
    }
    
    .banner {
        background: linear-gradient(135deg, #007BFF, #FF8C00); 
        padding: 25px; border-radius: 12px; color: white;
        margin-bottom: 25px; display: flex; justify-content: space-between;
        align-items: center; border-bottom: 6px solid #28a745; 
        box-shadow: 0px 4px 15px rgba(0,0,0,0.1);
    }
    .banner h1 {
        font-weight: 900 !important;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    .ai-warning {
        background-color: #ffffff; border-left: 6px solid #FF8C00;
        padding: 18px; border-radius: 8px; margin-bottom: 20px;
        font-size: 16px; line-height: 1.6;
        box-shadow: 0px 2px 8px rgba(0,0,0,0.05);
        color: #333333;
    }
    
    /* Làm nổi bật các con số Metric */
    [data-testid="stMetricValue"] {
        font-weight: 900 !important;
        color: #007BFF !important;
        font-size: 2.2rem !important;
    }
    [data-testid="stMetricLabel"] {
        font-weight: 800 !important;
        font-size: 1rem !important;
        color: #555555 !important;
    }
    
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] {
        font-weight: 900 !important; font-size: 18px !important; border: 2px solid #007BFF !important;
        border-radius: 8px 8px 0px 0px !important; padding: 14px 26px !important;
        background-color: #ffffff !important; color: #0056b3 !important;
        text-transform: uppercase; letter-spacing: 0.5px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #007BFF !important; color: white !important;
        border: 2px solid #007BFF !important; box-shadow: 0px -4px 10px rgba(0,123,255,0.3);
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# BẢO MẬT ĐĂNG NHẬP
# ==========================================
def check_login():
    st.markdown("<h2 style='text-align: center; color: #007BFF; font-weight: 900;'>🔐 HỆ THỐNG QUẢN TRỊ NỘI BỘ GHN</h2>", unsafe_allow_html=True)
    with st.form("login_form"):
        st.write("Vui lòng đăng nhập để xem báo cáo")
        user_id = st.text_input("ID Đăng nhập")
        password = st.text_input("Mật khẩu", type="password")
        submitted = st.form_submit_button("Đăng Nhập")
        
        if submitted:
            if user_id == "GHNQB" and password == "999":
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("❌ ID hoặc Mật khẩu không chính xác!")

if not st.session_state.authenticated:
    check_login()
    st.stop()

# Nút Đăng xuất ở thanh bên
with st.sidebar:
    if st.button("🚪 Đăng xuất", use_container_width=True):
        st.session_state.authenticated = False
        st.rerun()
        
    st.divider()
    st.markdown("👨‍💻 **Tài khoản:** Quản trị viên")

def styled_header(text, icon=""):
    st.markdown(f"""
        <div style="background-color: #ffffff; color: #0056b3; padding: 15px 20px;
                    border-radius: 8px; border-left: 8px solid #007BFF;
                    font-size: 22px; font-weight: 900; margin-top: 25px; margin-bottom: 20px;
                    box-shadow: 0px 2px 5px rgba(0,0,0,0.05); text-transform: uppercase;">
            {icon} {text}
        </div>
    """, unsafe_allow_html=True)

def draw_combo_chart(df, x_col, bar_y, line_y, title, bar_name="Sản lượng", line_name="% GTC"):
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=df[x_col], y=df[bar_y], name=bar_name, marker_color='#007BFF', opacity=0.85), secondary_y=False)
    fig.add_trace(go.Scatter(x=df[x_col], y=df[line_y], name=line_name, mode='lines+markers', line=dict(color='#FF8C00', width=4), marker=dict(size=10, color='#FF8C00', line=dict(width=2, color='white'))), secondary_y=True)
    fig.update_layout(title=dict(text=title, font=dict(size=18, family="Inter", color="#333")), plot_bgcolor='#ffffff', paper_bgcolor='#ffffff', hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(weight="bold")))
    fig.update_yaxes(title_text=bar_name, secondary_y=False, showgrid=True, gridcolor='#f0f0f0', title_font=dict(weight="bold"))
    fig.update_yaxes(title_text=line_name, secondary_y=True, showgrid=False, range=[0, 100], title_font=dict(weight="bold"))
    fig.update_xaxes(title_font=dict(weight="bold"), tickfont=dict(weight="bold"))
    return fig

# ==========================================
# 2. LẤY DỮ LIỆU TỪ GOOGLE SHEETS
# ==========================================
def parse_vn_num(val):
    if pd.isna(val): return np.nan
    val_str = str(val).replace('%', '').replace('đ', '').replace('VNĐ', '').replace(' ', '').strip()
    if val_str in ['nan', 'None', '', '-', 'null']: 
        return np.nan
    if ',' in val_str and '.' in val_str:
        if val_str.rfind(',') > val_str.rfind('.'): 
            val_str = val_str.replace('.', '').replace(',', '.')
        else: 
            val_str = val_str.replace(',', '')
    elif ',' in val_str:
        val_str = val_str.replace(',', '.')
    elif '.' in val_str:
        parts = val_str.split('.')
        if len(parts) > 2: 
            val_str = val_str.replace('.', '')
        else:
            if len(parts[1]) == 3 and parts[0] != '0': 
                val_str = val_str.replace('.', '')
    try:
        return float(val_str)
    except:
        return np.nan

def clean_dataframe_numbers(df, text_cols):
    for col in df.columns:
        if col not in text_cols:
            df[col] = df[col].apply(parse_vn_num)
    return df

@st.cache_data(ttl=60)
def get_real_business_data():
    url_kinhdoanh = "https://docs.google.com/spreadsheets/d/1dEC78RcXYcA7e2SVFmjhOfuP-DY57_FXkOCpRpln4vY/export?format=csv&gid=1161540341"
    try:
        df_kd = pd.read_csv(url_kinhdoanh)
        df_kd.columns = df_kd.columns.astype(str).str.strip().str.replace('\xa0', ' ')
        kd_mapping = {
            'Thời Gian': 'Ngày', 'Thời gian': 'Ngày', 'ngày': 'Ngày',
            'Bưu cục': 'Bưu Cục', 'bưu cục': 'Bưu Cục', 'Khu vực': 'Bưu Cục', 'Trạm': 'Bưu Cục', 'Cửa hàng': 'Bưu Cục',
            'Doanh thu': 'Doanh Thu', 'Khách hàng liên hệ': 'Khách Liên Hệ',
            'Khách hàng lên đơn': 'Khách Lên Đơn', 'Doanh thu KH mới': 'Doanh Thu KH Mới'
        }
        df_kd = df_kd.rename(columns=kd_mapping)
        if 'Bưu Cục' not in df_kd.columns: df_kd['Bưu Cục'] = "Chưa phân loại"
        
        df_kd = clean_dataframe_numbers(df_kd, text_cols=['Ngày', 'Bưu Cục'])
        df_kd['Ngày'] = pd.to_datetime(df_kd['Ngày'], errors='coerce')
        df_kd['Bưu Cục'] = df_kd['Bưu Cục'].astype(str).str.strip()
        for req in ['Doanh Thu', 'Khách Liên Hệ', 'Khách Lên Đơn', 'Doanh Thu KH Mới']:
            if req not in df_kd.columns: df_kd[req] = 0.0
        return df_kd.dropna(subset=['Ngày'])
    except Exception as e:
        st.error(f"🚨 Lỗi kết nối Google Sheets Kinh Doanh: {e}")
        st.stop()

df_kinhdoanh = get_real_business_data()

@st.cache_data(ttl=60) 
def get_real_data():
    url_vh_tongquan = "https://docs.google.com/spreadsheets/d/1lJt4ZXVjIPoUYZF73nsPmVfziJSBXBISUWU1ldSxWH4/export?format=csv&gid=1548015845"
    url_vh_ca = "https://docs.google.com/spreadsheets/d/1lJt4ZXVjIPoUYZF73nsPmVfziJSBXBISUWU1ldSxWH4/export?format=csv&gid=501687087"
    url_nhansu = "https://docs.google.com/spreadsheets/d/1OemA7cIZM-5AAvsnQuQphNArKw43de27W75Z-Ri6BcQ/export?format=csv&gid=2000227799"
    
    try:
        df_vh_tq = pd.read_csv(url_vh_tongquan)
        df_vh_c = pd.read_csv(url_vh_ca)
        df_ns = pd.read_csv(url_nhansu)
        
        df_vh_tq.columns = df_vh_tq.columns.astype(str).str.strip().str.replace('\xa0', ' ')
        df_vh_c.columns = df_vh_c.columns.astype(str).str.strip().str.replace('\xa0', ' ')
        df_ns.columns = df_ns.columns.astype(str).str.strip().str.replace('\xa0', ' ')
        
        vh_mapping = {
            'Thời Gian': 'Ngày', 'Thời gian': 'Ngày', 'ngày': 'Ngày', 'Ngày tạo': 'Ngày', 'Ngày': 'Ngày',
            'Bưu cục': 'Bưu Cục', 'bưu cục': 'Bưu Cục', 'Khu vực': 'Bưu Cục', 'Trạm': 'Bưu Cục',
            '%GTC': 'GTC', 'GTC (%)': 'GTC', 'Tỷ lệ GTC': 'GTC', '% GTC': 'GTC',
            'Trả hàng': 'Trả Hàng', 'Tỷ lệ trả hàng': 'Trả Hàng', '% Trả hàng': 'Trả Hàng',
            'Volume_TTS': 'Volume TTS', 'GTC TTS': 'GTC_TTS', '%GTC_TTS': 'GTC_TTS', 'Tỷ lệ GTC TTS': 'GTC_TTS', '% GTC TTS': 'GTC_TTS',
            'Ontime Giao TTS': 'ODR', 'ODR (%)': 'ODR', 'Tỷ lệ ODR': 'ODR', '% ODR': 'ODR', 'Ontime': 'ODR', 'Tỷ lệ Ontime': 'ODR', 'Tỉ lệ Ontime': 'ODR',
            'Sản lượng': 'Volume', 'Sản Lượng': 'Volume', 'Tổng đơn': 'Volume', 'Tổng Đơn': 'Volume', 'Volume': 'Volume',
            'Loại hàng': 'Loại Hàng', 'loại hàng': 'Loại Hàng', 'Phân loại': 'Loại Hàng', 'Ca làm việc': 'Loại Hàng', 'Ca': 'Loại Hàng'
        }
        df_vh_tq = df_vh_tq.rename(columns=vh_mapping)
        df_vh_c = df_vh_c.rename(columns=vh_mapping)
        
        ns_mapping = {
            'Thời Gian': 'Ngày', 'Thời gian': 'Ngày', 'ngày': 'Ngày', 'Ngày': 'Ngày',
            'Bưu cục': 'Bưu Cục', 'bưu cục': 'Bưu Cục', 'Khu vực': 'Bưu Cục', 'Trạm': 'Bưu Cục',
            'Nhân viên': 'Nhân Viên', 'nhân viên': 'Nhân Viên', 'Tên nhân viên': 'Nhân Viên', 'Nhân Viên': 'Nhân Viên', 'Tên Nhân Viên': 'Nhân Viên',
            'Loại hàng': 'Loại Hàng', 'loại hàng': 'Loại Hàng', 'Loại Hàng': 'Loại Hàng',
            'GTC': '%GTC', 'Tỷ lệ GTC': '%GTC', '% GTC': '%GTC',
            'Đơn giá': 'Đơn Giá', 'Số đơn': 'Số Đơn'
        }
        df_ns = df_ns.rename(columns=ns_mapping)
        
        if 'Bưu Cục' not in df_vh_tq.columns: df_vh_tq['Bưu Cục'] = "Chưa phân loại"
        if 'Bưu Cục' not in df_vh_c.columns: df_vh_c['Bưu Cục'] = "Chưa phân loại"
        if 'Bưu Cục' not in df_ns.columns: df_ns['Bưu Cục'] = "Chưa phân loại"
        
        text_cols_vh = ['Ngày', 'Bưu Cục', 'Ca', 'Loại Hàng']
        df_vh_tq = clean_dataframe_numbers(df_vh_tq, text_cols_vh)
        df_vh_c = clean_dataframe_numbers(df_vh_c, text_cols_vh)
        df_ns = clean_dataframe_numbers(df_ns, ['Ngày', 'Bưu Cục', 'Nhân Viên', 'Loại Hàng'])
        
        for df_target in [df_vh_tq, df_vh_c]:
            for col in ['GTC', 'GTC_TTS', 'Trả Hàng', 'ODR']:
                if col in df_target.columns:
                    valid_vals = df_target[df_target[col] > 0][col].dropna()
                    if not valid_vals.empty and valid_vals.max() <= 1.2:
                        df_target[col] = df_target[col] * 100
                        
        if '%GTC' in df_ns.columns:
            valid_vals = df_ns[df_ns['%GTC'] > 0]['%GTC'].dropna()
            if not valid_vals.empty and valid_vals.max() <= 1.2:
                df_ns['%GTC'] = df_ns['%GTC'] * 100
        
        df_vh_tq['Ngày'] = pd.to_datetime(df_vh_tq['Ngày'], errors='coerce')
        df_vh_c['Ngày'] = pd.to_datetime(df_vh_c['Ngày'], errors='coerce')
        df_ns['Ngày'] = pd.to_datetime(df_ns['Ngày'], errors='coerce')
        
        for df in [df_vh_tq, df_vh_c]:
            df['Bưu Cục'] = df['Bưu Cục'].astype(str).str.strip()
            if 'Loại Hàng' not in df.columns: df['Loại Hàng'] = "Hàng Mới Ca 1"
            df['Loại Hàng'] = df['Loại Hàng'].astype(str).str.strip()
            df['Ca'] = df['Loại Hàng']
            
        df_ns['Bưu Cục'] = df_ns['Bưu Cục'].astype(str).str.strip()
        if 'Nhân Viên' in df_ns.columns:
            df_ns['Nhân Viên'] = df_ns['Nhân Viên'].astype(str).str.strip()
        else:
            df_ns['Nhân Viên'] = "Chưa phân loại"
            
        if 'Loại Hàng' not in df_ns.columns: df_ns['Loại Hàng'] = "FULL"
        df_ns['Loại Hàng'] = df_ns['Loại Hàng'].astype(str).str.strip()
        
        for req in ['Volume', 'Volume TTS']:
            if req not in df_vh_tq.columns: df_vh_tq[req] = 0.0
            if req not in df_vh_c.columns: df_vh_c[req] = 0.0
        for req in ['GTC', 'GTC_TTS', 'Trả Hàng', 'ODR']:
            if req not in df_vh_tq.columns: df_vh_tq[req] = np.nan
            if req not in df_vh_c.columns: df_vh_c[req] = np.nan
            
        for req in ['Số Đơn', 'LHH LTC', 'LHH GTC', 'LHH GTBTT']:
            if req not in df_ns.columns: df_ns[req] = 0.0
        if 'Đơn Giá' not in df_ns.columns: df_ns['Đơn Giá'] = np.nan
        if '%GTC' not in df_ns.columns: df_ns['%GTC'] = np.nan
            
        df_ns['Tổng Lương'] = df_ns['LHH LTC'] + df_ns['LHH GTC'] + df_ns['LHH GTBTT']
            
        return df_vh_tq.dropna(subset=['Ngày']), df_vh_c.dropna(subset=['Ngày']), df_ns.dropna(subset=['Ngày'])
    except Exception as e:
        st.error(f"🚨 Lỗi kết nối Google Sheets: {e}")
        st.stop()

df_vh_tongquan, df_vh_ca, df_nhansu = get_real_data()

# LẤY DỮ LIỆU ĐẶC BIỆT: DATA BIỂU ĐỒ %GTC CHO TAB NĂNG SUẤT (THÁNG HIỆN TẠI)
@st.cache_data(ttl=60)
def get_ns_gtc_data():
    url_ns_gtc = "https://docs.google.com/spreadsheets/d/1OemA7cIZM-5AAvsnQuQphNArKw43de27W75Z-Ri6BcQ/export?format=csv&gid=1862143946"
    try:
        df = pd.read_csv(url_ns_gtc)
        df.columns = df.columns.astype(str).str.strip().str.replace('\xa0', ' ')
        mapping = {
            'Thời Gian': 'Ngày', 'Thời gian': 'Ngày', 'ngày': 'Ngày', 'Ngày': 'Ngày',
            'Bưu cục': 'Bưu Cục', 'bưu cục': 'Bưu Cục', 'Khu vực': 'Bưu Cục', 'Trạm': 'Bưu Cục', 'Bưu Cục': 'Bưu Cục',
            'Nhân viên': 'Nhân Viên', 'nhân viên': 'Nhân Viên', 'Tên nhân viên': 'Nhân Viên', 'Nhân Viên': 'Nhân Viên', 'Tên Nhân Viên': 'Nhân Viên',
            'Loại hàng': 'Loại Hàng', 'loại hàng': 'Loại Hàng', 'Phân loại': 'Loại Hàng', 'Loại Hàng': 'Loại Hàng',
            'Đơn giao tính lương': 'Đơn giao tính lương', 'Số đơn giao tính lương': 'Đơn giao tính lương', 'Đơn Giao Tính Lương': 'Đơn giao tính lương', 'Đơn giao': 'Đơn giao tính lương', 'Số đơn GTC': 'Đơn giao tính lương', 'Đơn GTC': 'Đơn giao tính lương',
            'Số đơn gán Giao': 'Số đơn gán Giao', 'Số đơn gán giao': 'Số đơn gán Giao', 'Số đơn gán': 'Số đơn gán Giao', 'Số Đơn Gán Giao': 'Số đơn gán Giao', 'Đơn gán': 'Số đơn gán Giao', 'Số Đơn Gán': 'Số đơn gán Giao'
        }
        df = df.rename(columns=mapping)
        if 'Bưu Cục' not in df.columns: df['Bưu Cục'] = "Chưa phân loại"
        if 'Nhân Viên' not in df.columns: df['Nhân Viên'] = "Chưa phân loại"
        
        df = clean_dataframe_numbers(df, ['Ngày', 'Bưu Cục', 'Nhân Viên', 'Loại Hàng'])
        df['Ngày'] = pd.to_datetime(df['Ngày'], errors='coerce')
        
        df['Bưu Cục'] = df['Bưu Cục'].astype(str).str.strip()
        
        if 'Nhân Viên' in df.columns:
            df['Nhân Viên'] = df['Nhân Viên'].astype(str).str.strip()
        else:
            df['Nhân Viên'] = "Chưa phân loại"
            
        if 'Loại Hàng' in df.columns:
            df['Loại Hàng'] = df['Loại Hàng'].astype(str).str.strip()
            
        for req in ['Đơn giao tính lương', 'Số đơn gán Giao']:
            if req not in df.columns: df[req] = 0.0
            
        return df.dropna(subset=['Ngày'])
    except Exception as e:
        return pd.DataFrame()

df_ns_gtc_raw = get_ns_gtc_data()

# LẤY DỮ LIỆU ĐẶC BIỆT: DATA %GTC CHO THÁNG TRƯỚC (THÁNG 06) BẢO VỆ CHỐNG LỖI MẤT DỮ LIỆU
@st.cache_data(ttl=60)
def get_prev_month_gtc_data():
    url_ns_gtc_prev = "https://docs.google.com/spreadsheets/d/1OemA7cIZM-5AAvsnQuQphNArKw43de27W75Z-Ri6BcQ/export?format=csv&gid=1862143946"
    try:
        df = pd.read_csv(url_ns_gtc_prev)
        df.columns = df.columns.astype(str).str.strip().str.replace('\xa0', ' ')
        mapping = {
            'Thời Gian': 'Ngày', 'Thời gian': 'Ngày', 'ngày': 'Ngày', 'Ngày': 'Ngày',
            'Bưu cục': 'Bưu Cục', 'bưu cục': 'Bưu Cục', 'Khu vực': 'Bưu Cục', 'Trạm': 'Bưu Cục', 'Bưu Cục': 'Bưu Cục',
            'Nhân viên': 'Nhân Viên', 'nhân viên': 'Nhân Viên', 'Tên nhân viên': 'Nhân Viên', 'Nhân Viên': 'Nhân Viên', 'Tên Nhân Viên': 'Nhân Viên',
            'Loại hàng': 'Loại Hàng', 'loại hàng': 'Loại Hàng', 'Phân loại': 'Loại Hàng', 'Loại Hàng': 'Loại Hàng',
            'Đơn giao tính lương': 'Đơn giao tính lương', 'Số đơn giao tính lương': 'Đơn giao tính lương', 'Đơn Giao Tính Lương': 'Đơn giao tính lương', 'Đơn giao': 'Đơn giao tính lương', 'Số đơn GTC': 'Đơn giao tính lương', 'Đơn GTC': 'Đơn giao tính lương',
            'Số đơn gán Giao': 'Số đơn gán Giao', 'Số đơn gán giao': 'Số đơn gán Giao', 'Số đơn gán': 'Số đơn gán Giao', 'Số Đơn Gán Giao': 'Số đơn gán Giao', 'Đơn gán': 'Số đơn gán Giao', 'Số Đơn Gán': 'Số đơn gán Giao'
        }
        df = df.rename(columns=mapping)
        if 'Bưu Cục' not in df.columns: df['Bưu Cục'] = "Chưa phân loại"
        if 'Nhân Viên' not in df.columns: df['Nhân Viên'] = "Chưa phân loại"
        
        df = clean_dataframe_numbers(df, ['Ngày', 'Bưu Cục', 'Nhân Viên', 'Loại Hàng'])
        
        if 'Ngày' in df.columns:
            df['Ngày'] = pd.to_datetime(df['Ngày'], errors='coerce')
        
        df['Bưu Cục'] = df['Bưu Cục'].astype(str).str.strip()
        
        if 'Nhân Viên' in df.columns:
            df['Nhân Viên'] = df['Nhân Viên'].astype(str).str.strip()
        else:
            df['Nhân Viên'] = "Chưa phân loại"
            
        if 'Loại Hàng' in df.columns:
            df['Loại Hàng'] = df['Loại Hàng'].astype(str).str.strip()
            
        for req in ['Đơn giao tính lương', 'Số đơn gán Giao']:
            if req not in df.columns: df[req] = 0.0
            
        # KHÔNG SỬ DỤNG LỆNH df.dropna(subset=['Ngày']) ĐỂ TRÁNH LỖI XÓA DỮ LIỆU BẢNG TỔNG
        return df
    except Exception as e:
        return pd.DataFrame(columns=['Ngày', 'Bưu Cục', 'Nhân Viên', 'Loại Hàng', 'Đơn giao tính lương', 'Số đơn gán Giao'])

df_ns_prev_raw = get_prev_month_gtc_data()

@st.cache_data(ttl=60)
def get_customer_data():
    url_kh = "https://docs.google.com/spreadsheets/d/16ywqMY_QxFcRvOXEFsZGAxz0PGRiB1OPELzaUq-Whq8/export?format=csv&gid=942640433"
    try:
        df_kh = pd.read_csv(url_kh)
        return df_kh
    except Exception as e:
        return pd.DataFrame()

df_khachhang = get_customer_data()


# ==========================================
# 3. HÀM TRỢ LÝ AI & CSS ĐỊNH DẠNG BẢNG
# ==========================================
st.markdown("""
    <div class="banner">
        <div>
            <h1 style="color: white; margin-bottom: 5px;">DASHBOARD QUẢN LÝ VẬN HÀNH & KINH DOANH GHN</h1>
            <p style="font-size: 18px; font-weight: 600; opacity: 0.95; margin-bottom: 0;">Hiệu Suất Thực - Quyết Định Nhanh - AI Cố Vấn</p>
            <p style="font-size: 14px; font-style: italic; opacity: 0.8; margin-top: 5px; margin-bottom: 0;">Designed by AM Phan Van Chanh</p>
        </div>
    </div>
""", unsafe_allow_html=True)

col_rf1, _ = st.columns([2, 8])
with col_rf1:
    if st.button("🔄 Làm mới dữ liệu thủ công", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

def get_ai_analysis(prompt_text):
    if not GEMINI_API_KEY or GEMINI_API_KEY == "ĐIỀN_API_KEY_GEMINI_CỦA_BẠN_VÀO_ĐÂY":
        return "⚠️ **CHƯA CẤU HÌNH API KEY:** Vui lòng thêm biến môi trường GEMINI_API_KEY trên Render."
    try:
        genai.configure(api_key=GEMINI_API_KEY.strip())
        model = genai.GenerativeModel('gemini-3.6-flash') 
        detailed_config = genai.types.GenerationConfig(max_output_tokens=8192, temperature=0.4)
        response = model.generate_content(prompt_text, generation_config=detailed_config)
        return response.text
    except Exception as e:
        return f"❌ Lỗi từ máy chủ Google AI: {e}"

def render_ai_and_telegram(ai_result, tab_name, key_suffix):
    st.markdown(f'<div class="ai-warning"><b>🤖 Cố vấn AI ({tab_name}):</b><br><br>{ai_result}</div>', unsafe_allow_html=True)
    if st.button(f"📤 Bắn báo cáo {tab_name} lên nhóm Telegram", type="primary", key=f"btn_tele_{key_suffix}"):
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

# ĐỊNH DẠNG CHUNG CHO DÒNG TIÊU ĐỀ BẢNG (HEADER)
th_props = [
    ('background-color', '#FF6600'), # Cam an toàn
    ('color', '#ffffff'),            # Chữ trắng tương phản
    ('font-weight', '900'),          # In đậm mạnh
    ('font-size', '15px'),           # Kích thước chữ
    ('text-align', 'center'),        # Căn giữa
    ('text-transform', 'uppercase')  # In hoa
]
header_styles = [dict(selector="th", props=th_props)]


# ==========================================
# 4. GIAO DIỆN CÁC TAB BIỂU ĐỒ 
# ==========================================
# ĐÃ BỔ SUNG TAB 6 DÀNH RIÊNG CHO TRỢ LÝ AI
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["🚚 VẬN HÀNH CHI TIẾT", "👥 NĂNG SUẤT & LƯƠNG", "🎯 VẬN HÀNH THEO KPI", "💰 KINH DOANH", "🏆 THI ĐUA GTC", "🤖 TRỢ LÝ AI"])

# ----------------- TAB 1: VẬN HÀNH -----------------
with tab1:
    col1, col2, col3 = st.columns(3)
    with col1:
        date_range_vh = st.date_input("Khoảng thời gian (Vận hành)", [df_vh_tongquan['Ngày'].min(), df_vh_tongquan['Ngày'].max()], key="date_vh")
    with col2:
        bc_list_vh = ["Tất cả", "Grand Total"] + [x for x in df_vh_tongquan['Bưu Cục'].unique() if str(x) not in ["Tất cả", "Grand Total"]]
        buu_cuc_vh = st.selectbox("Chọn Bưu cục", bc_list_vh, key="bc_vh")
    with col3:
        loai_hang_vh = st.multiselect("Lọc Loại Hàng", ["Hàng Mới Ca 1", "Hàng Mới Ca 2", "Hàng Tồn"], default=["Hàng Mới Ca 1", "Hàng Mới Ca 2", "Hàng Tồn"], key="lh_vh")

    mask_vh_tq = pd.Series(True, index=df_vh_tongquan.index)
    if len(date_range_vh) == 2:
        mask_vh_tq &= (df_vh_tongquan['Ngày'] >= pd.to_datetime(date_range_vh[0])) & (df_vh_tongquan['Ngày'] <= pd.to_datetime(date_range_vh[1]))
    if buu_cuc_vh != "Tất cả":
        mask_vh_tq &= (df_vh_tongquan['Bưu Cục'].str.lower() == str(buu_cuc_vh).lower())
    df_vh_tq_filtered = df_vh_tongquan[mask_vh_tq].copy()
    
    mask_vh_ca = pd.Series(True, index=df_vh_ca.index)
    if len(date_range_vh) == 2:
        mask_vh_ca &= (df_vh_ca['Ngày'] >= pd.to_datetime(date_range_vh[0])) & (df_vh_ca['Ngày'] <= pd.to_datetime(date_range_vh[1]))
    if buu_cuc_vh != "Tất cả":
        mask_vh_ca &= (df_vh_ca['Bưu Cục'].str.lower() == str(buu_cuc_vh).lower())
    if loai_hang_vh:
        mask_vh_ca &= df_vh_ca['Loại Hàng'].isin(loai_hang_vh)
    df_vh_ca_filtered = df_vh_ca[mask_vh_ca].copy()

    styled_header("1. TỔNG QUAN GTC VÀ TỶ LỆ TRẢ HÀNG", "🌍")
    
    view_mode_vh = st.radio("Chế độ xem (Áp dụng toàn Tab):", ["Theo Ngày", "Theo Tuần", "Theo Tháng"], horizontal=True, key="view_mode_vh")
    
    df_trend_display = df_vh_tq_filtered.copy()
    if view_mode_vh == "Theo Tuần":
        df_trend_display['Period'] = df_trend_display['Ngày'].dt.to_period('W').apply(lambda r: r.start_time)
        df_trend_display = df_trend_display.groupby('Period').agg({'Volume': 'sum', 'GTC': 'mean', 'Trả Hàng': 'mean'}).reset_index()
        df_trend_display = df_trend_display.rename(columns={'Period': 'Ngày'})
    elif view_mode_vh == "Theo Tháng":
        df_trend_display['Period'] = df_trend_display['Ngày'].dt.to_period('M').apply(lambda r: r.start_time)
        df_trend_display = df_trend_display.groupby('Period').agg({'Volume': 'sum', 'GTC': 'mean', 'Trả Hàng': 'mean'}).reset_index()
        df_trend_display = df_trend_display.rename(columns={'Period': 'Ngày'})
    else:
        df_trend_display = df_trend_display.groupby('Ngày').agg({'Volume': 'sum', 'GTC': 'mean', 'Trả Hàng': 'mean'}).reset_index()

    if not df_trend_display.empty:
        df_trend_display = df_trend_display.sort_values('Ngày')
        latest_vol = df_trend_display.iloc[-1]['Volume'] if not df_trend_display.empty else 0.0
        latest_gtc = df_trend_display.iloc[-1]['GTC'] if not df_trend_display.empty else 0.0
        
        latest_vol = latest_vol if pd.notna(latest_vol) else 0.0
        latest_gtc = latest_gtc if pd.notna(latest_gtc) else 0.0
        
        prev_vol = df_trend_display.iloc[-2]['Volume'] if len(df_trend_display) > 1 else 0.0
        prev_gtc = df_trend_display.iloc[-2]['GTC'] if len(df_trend_display) > 1 else 0.0
        
        prev_vol = prev_vol if pd.notna(prev_vol) else 0.0
        prev_gtc = prev_gtc if pd.notna(prev_gtc) else 0.0
            
        st.markdown(f"<div style='font-weight: 800; font-size: 16px; color: #333;'>So sánh kỳ gần nhất so với kỳ trước ({view_mode_vh}):</div>", unsafe_allow_html=True)
        m_col1, m_col2 = st.columns(2)
        m_col1.metric("Tổng Sản Lượng", f"{latest_vol:,.0f} đơn", f"{latest_vol - prev_vol:,.0f} đơn")
        m_col2.metric("Tỷ lệ GTC", f"{latest_gtc:.2f}%", f"{latest_gtc - prev_gtc:.2f}%")

    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        fig_gtc = draw_combo_chart(df_trend_display, 'Ngày', 'Volume', 'GTC', f"Tỷ lệ GTC và Sản Lượng ({view_mode_vh})")
        st.plotly_chart(fig_gtc, use_container_width=True)
    with chart_col2:
        fig_return = px.line(df_trend_display, x='Ngày', y='Trả Hàng', markers=True, title=f"Tỷ lệ Trả Hàng ({view_mode_vh}) (%)")
        fig_return.update_traces(line=dict(color='#FF3333', width=4), marker=dict(size=10, color='#FF3333', line=dict(width=2, color='white')))
        fig_return.update_layout(title=dict(font=dict(size=18, family="Inter", color="#333")), plot_bgcolor='#ffffff', paper_bgcolor='#ffffff', hovermode="x unified")
        fig_return.update_yaxes(showgrid=True, gridcolor='#f0f0f0', title_font=dict(weight="bold"))
        fig_return.update_xaxes(title_font=dict(weight="bold"), tickfont=dict(weight="bold"))
        st.plotly_chart(fig_return, use_container_width=True)

    styled_header("2. PHÂN TÍCH TIKTOK SHOP & ONTIME GIAO TTS (ODR)", "🛒")
    chart_col3, chart_col4 = st.columns(2)
    
    df_tts_base = df_vh_tq_filtered.copy()
    if view_mode_vh == "Theo Tuần":
        df_tts_base['Ngày'] = df_tts_base['Ngày'].dt.to_period('W').apply(lambda r: r.start_time)
    elif view_mode_vh == "Theo Tháng":
        df_tts_base['Ngày'] = df_tts_base['Ngày'].dt.to_period('M').apply(lambda r: r.start_time)
    df_tts = df_tts_base.groupby('Ngày').agg({'Volume TTS': 'sum', 'GTC_TTS': 'mean', 'ODR': 'mean'}).reset_index()
    
    with chart_col3:
        fig_tts = draw_combo_chart(df_tts, 'Ngày', 'Volume TTS', 'GTC_TTS', f"Tỷ lệ GTC TiktokShop ({view_mode_vh})", bar_name="Sản lượng TTS", line_name="% GTC TTS")
        st.plotly_chart(fig_tts, use_container_width=True)
    with chart_col4:
        fig_odr = px.line(df_tts, x='Ngày', y='ODR', markers=True, title=f"Tỷ lệ Ontime TTS (ODR TikTokShop) ({view_mode_vh})")
        fig_odr.update_traces(line=dict(color='#28a745', width=4), marker=dict(size=10, color='#28a745', line=dict(width=2, color='white')))
        fig_odr.update_layout(title=dict(font=dict(size=18, family="Inter", color="#333")), plot_bgcolor='#ffffff', paper_bgcolor='#ffffff', hovermode="x unified")
        fig_odr.update_yaxes(showgrid=True, gridcolor='#f0f0f0', title_font=dict(weight="bold"))
        fig_odr.update_xaxes(title_font=dict(weight="bold"), tickfont=dict(weight="bold"))
        st.plotly_chart(fig_odr, use_container_width=True)

    styled_header("3. NĂNG SUẤT GIAO THEO CA LÀM VIỆC", "🕒")
    
    df_ca_base = df_vh_ca_filtered.copy()
    if view_mode_vh == "Theo Tuần":
        df_ca_base['Ngày'] = df_ca_base['Ngày'].dt.to_period('W').apply(lambda r: r.start_time)
    elif view_mode_vh == "Theo Tháng":
        df_ca_base['Ngày'] = df_ca_base['Ngày'].dt.to_period('M').apply(lambda r: r.start_time)
    df_ca = df_ca_base.groupby(['Ngày', 'Ca']).agg({'Volume': 'sum', 'GTC': 'mean'}).reset_index()
    
    fmt = '%m/%Y' if view_mode_vh == "Theo Tháng" else '%d/%m'
    df_ca['TrụcX'] = df_ca['Ngày'].dt.strftime(fmt) + " - " + df_ca['Ca']
    
    fig_ca = make_subplots(specs=[[{"secondary_y": True}]])
    colors_bar = ['#007BFF', '#17a2b8', '#6c757d']
    colors_line = ['#FF8C00', '#FF3333', '#28a745']
    for idx, ca_name in enumerate(df_ca['Ca'].unique()):
        df_ca_sub = df_ca[df_ca['Ca'] == ca_name]
        c_bar = colors_bar[idx % len(colors_bar)]
        c_line = colors_line[idx % len(colors_line)]
        fig_ca.add_trace(go.Bar(x=df_ca_sub['TrụcX'], y=df_ca_sub['Volume'], name=f"Volume {ca_name}", marker_color=c_bar, opacity=0.85), secondary_y=False)
        fig_ca.add_trace(go.Scatter(x=df_ca_sub['TrụcX'], y=df_ca_sub['GTC'], name=f"%GTC {ca_name}", mode='lines+markers', line=dict(color=c_line, width=3), marker=dict(size=8, color=c_line, line=dict(width=1, color='white'))), secondary_y=True)

    fig_ca.update_layout(title=dict(text=f"Sản Lượng và Tỷ Lệ GTC Theo Ca Làm Việc ({view_mode_vh})", font=dict(size=18, family="Inter", color="#333")), plot_bgcolor='#ffffff', paper_bgcolor='#ffffff', hovermode="x unified", barmode='group', legend=dict(font=dict(weight="bold")))
    fig_ca.update_yaxes(title_text="Sản lượng", secondary_y=False, showgrid=True, gridcolor='#f0f0f0', title_font=dict(weight="bold"))
    fig_ca.update_yaxes(title_text="% GTC", secondary_y=True, showgrid=False, range=[0, 100], title_font=dict(weight="bold"))
    fig_ca.update_xaxes(title_font=dict(weight="bold"), tickfont=dict(weight="bold"))
    st.plotly_chart(fig_ca, use_container_width=True)

    st.markdown("---")
    ai_role_vh = st.radio("🤖 Chọn đối tượng nhận báo cáo AI (Vận Hành):", ["Góc nhìn Giám Đốc", "Góc nhìn Quản lý khu vực (AM)", "Góc nhìn Nhân viên xử lý"], horizontal=True, key="role_vh")
    
    if st.button("🔍 Nhờ AI Phân tích Vận Hành", type="primary", key="btn_ai_vh"):
        with st.spinner("🔄 AI đang phân tích dữ liệu Vận Hành..."):
            
            if ai_role_vh == "Góc nhìn Giám Đốc":
                role_prompt = "Nhiệm vụ: Đóng vai Giám đốc vận hành. Phân tích CHUYÊN SÂU theo 3 phần: 1. Đánh giá tổng thể hiệu suất, 2. Phân tích Rủi ro vĩ mô, 3. Đề xuất hành động chiến lược. Viết chuyên nghiệp, uy quyền."
            elif ai_role_vh == "Góc nhìn Quản lý khu vực (AM)":
                role_prompt = "Nhiệm vụ: Đóng vai Quản lý khu vực (AM). Phân tích 3 phần: 1. Đánh giá hiệu suất vận hành của khu vực, 2. Nhận diện các điểm nóng/tuyến kéo tụt số liệu, 3. Đưa ra chỉ đạo điều phối trực tiếp cho Nhân viên xử lý (điều hành kho) và Nhân viên giao hàng. Viết dứt khoát, mang tính quản trị và đốc thúc."
            else:
                role_prompt = 'Nhiệm vụ: Đóng vai Trợ lý Điều phối Vận hành gửi thông báo trực tiếp cho NHÓM NHÂN VIÊN XỬ LÝ (Điều hành kho) & GIAO HÀNG. Xưng hô thân thiện, tạo động lực (dùng từ "Mình" với "Mọi người" hoặc "Team"). Hãy chia làm 3 ý rõ ràng: 1. Đánh giá nhanh tình hình ca làm việc, 2. Ghi chú các điểm nóng cần anh em chú ý gấp, 3. Kêu gọi hành động ưu tiên cho hôm nay.'
                
            mean_gtc = df_vh_tq_filtered['GTC'].mean()
            mean_gtc = mean_gtc if pd.notna(mean_gtc) else 0.0
            mean_odr = df_vh_tq_filtered['ODR'].mean()
            mean_odr = mean_odr if pd.notna(mean_odr) else 0.0
            
            d_start_vh = date_range_vh[0].strftime('%d/%m/%Y')
            d_end_vh = date_range_vh[1].strftime('%d/%m/%Y') if len(date_range_vh) > 1 else d_start_vh
            lh_str_vh = ", ".join(loai_hang_vh) if loai_hang_vh else "Tất cả"
            
            prompt_vh = f"""
            Dữ liệu Vận Hành Đã Lọc:
            - Thời gian: {d_start_vh} đến {d_end_vh}
            - Bưu cục/Khu vực: {buu_cuc_vh}
            - Loại hàng: {lh_str_vh}
            - Tổng đơn: {df_vh_tq_filtered['Volume'].sum():,.0f}
            - Tỷ lệ GTC: {mean_gtc:.2f}%
            - Tỷ lệ Ontime Giao TTS (ODR): {mean_odr:.2f}%
            
            (LƯU Ý QUAN TRỌNG CHO AI: ODR là tỷ lệ cam kết giao hàng đúng hạn với sàn Tiktokshop. Tỷ lệ này CÀNG CAO CÀNG TỐT. Thấp là tệ, rủi ro bị phạt.)
            {role_prompt}
            Yêu cầu BẮT BUỘC: Viết súc tích, phân bổ ý rõ ràng. Tuyệt đối không được bỏ dở câu. Kết thúc báo cáo bằng dòng chữ [HOÀN TẤT BÁO CÁO].
            """
            st.session_state.ai_vh_result = get_ai_analysis(prompt_vh)
    render_ai_and_telegram(st.session_state.ai_vh_result, "Vận Hành", "vh")


# ----------------- TAB 2: NĂNG SUẤT & LƯƠNG -----------------
with tab2:
    f_col1, f_col2, f_col3, f_col4, f_col5 = st.columns(5)
    with f_col1:
        date_range_ns = st.date_input("Khoảng thời gian (Nhân sự)", [df_nhansu['Ngày'].min(), df_nhansu['Ngày'].max()], key="date_ns")
    with f_col2:
        lh_set1 = set(df_nhansu['Loại Hàng'].dropna().astype(str).str.strip().unique())
        lh_set2 = set(df_ns_gtc_raw['Loại Hàng'].dropna().astype(str).str.strip().unique()) if not df_ns_gtc_raw.empty and 'Loại Hàng' in df_ns_gtc_raw.columns else set()
        lh_all = sorted([x for x in lh_set1.union(lh_set2) if x and x != "nan"])
        loai_hang_filter = st.multiselect("Lọc Loại Hàng", lh_all, default=[], key="lh_filter")
    with f_col3:
        bc_set1 = set(df_nhansu['Bưu Cục'].dropna().astype(str).str.strip().unique())
        bc_set2 = set(df_ns_gtc_raw['Bưu Cục'].dropna().astype(str).str.strip().unique()) if not df_ns_gtc_raw.empty else set()
        bc_all = sorted([x for x in bc_set1.union(bc_set2) if x and x != "Chưa phân loại" and x != "nan"])
        bc_list = ["Tất cả"] + bc_all
        buu_cuc_ns = st.selectbox("Lọc Bưu cục", bc_list, key="bc_ns_tab2")
    with f_col4:
        if buu_cuc_ns == "Tất cả":
            nv_set1 = set(df_nhansu['Nhân Viên'].dropna().astype(str).str.strip().unique())
            nv_set2 = set(df_ns_gtc_raw['Nhân Viên'].dropna().astype(str).str.strip().unique()) if not df_ns_gtc_raw.empty else set()
        else:
            nv_set1 = set(df_nhansu[df_nhansu['Bưu Cục'].astype(str).str.strip().str.lower() == str(buu_cuc_ns).strip().lower()]['Nhân Viên'].dropna().astype(str).str.strip().unique())
            nv_set2 = set(df_ns_gtc_raw[df_ns_gtc_raw['Bưu Cục'].astype(str).str.strip().str.lower() == str(buu_cuc_ns).strip().lower()]['Nhân Viên'].dropna().astype(str).str.strip().unique()) if not df_ns_gtc_raw.empty else set()
        nv_all = sorted([x for x in nv_set1.union(nv_set2) if x and x != "Chưa phân loại" and x != "nan"])
        nv_list = ["Tất cả"] + nv_all
        nhan_vien_ns = st.selectbox("Lọc Nhân viên", nv_list, key="nv_ns_tab2")
    with f_col5:
        loai_luong_list = ['LHH LTC', 'LHH GTC', 'LHH GTBTT']
        loai_luong_filter = st.multiselect("Lọc Loại Lương", loai_luong_list, default=loai_luong_list, key="ll_filter")

    mask_ns = pd.Series(True, index=df_nhansu.index)
    if len(date_range_ns) == 2:
        mask_ns &= (df_nhansu['Ngày'] >= pd.to_datetime(date_range_ns[0])) & (df_nhansu['Ngày'] <= pd.to_datetime(date_range_ns[1]))
    if buu_cuc_ns != "Tất cả":
        mask_ns &= (df_nhansu['Bưu Cục'].astype(str).str.strip().str.lower() == str(buu_cuc_ns).strip().lower())
    if nhan_vien_ns != "Tất cả":
        mask_ns &= (df_nhansu['Nhân Viên'].astype(str).str.strip().str.lower() == str(nhan_vien_ns).strip().lower())
    if loai_hang_filter:
        mask_ns &= (df_nhansu['Loại Hàng'].astype(str).str.strip().isin(loai_hang_filter))
        
    df_ns_filtered = df_nhansu[mask_ns].copy()
    
    mask_ns_no_date = pd.Series(True, index=df_nhansu.index)
    if buu_cuc_ns != "Tất cả": mask_ns_no_date &= (df_nhansu['Bưu Cục'].astype(str).str.strip().str.lower() == str(buu_cuc_ns).strip().lower())
    if nhan_vien_ns != "Tất cả": mask_ns_no_date &= (df_nhansu['Nhân Viên'].astype(str).str.strip().str.lower() == str(nhan_vien_ns).strip().lower())
    if loai_hang_filter: mask_ns_no_date &= (df_nhansu['Loại Hàng'].astype(str).str.strip().isin(loai_hang_filter))
    
    df_ns_base = df_nhansu[mask_ns_no_date].copy()
    
    selected_ll = loai_luong_filter if loai_luong_filter else loai_luong_list
    df_ns_filtered['Tổng Lương'] = df_ns_filtered[selected_ll].sum(axis=1)
    df_ns_base['Tổng Lương'] = df_ns_base[selected_ll].sum(axis=1)

    styled_header("PHÂN TÍCH ĐƠN GIÁ, NĂNG SUẤT & TỔNG LƯƠNG", "📈")
    
    max_date_ns = pd.to_datetime(date_range_ns[1]) if len(date_range_ns) == 2 else pd.to_datetime(date_range_ns[0])
    
    if max_date_ns.day <= 15:
        curr_start = max_date_ns.replace(day=1)
        curr_end = max_date_ns.replace(day=15)
        prev_end = curr_start - timedelta(days=1)
        prev_start = prev_end.replace(day=16)
        curr_name = f"Kỳ 20 ({curr_start.month:02d}/{curr_start.year})"
        prev_name = f"Kỳ 05 ({curr_start.month:02d}/{curr_start.year})"
    else:
        curr_start = max_date_ns.replace(day=16)
        next_m = (curr_start.replace(day=28) + timedelta(days=4)).replace(day=1)
        curr_end = next_m - timedelta(days=1)
        prev_start = max_date_ns.replace(day=1)
        prev_end = max_date_ns.replace(day=15)
        curr_name = f"Kỳ 05 ({next_m.month:02d}/{next_m.year})"
        prev_name = f"Kỳ 20 ({curr_start.month:02d}/{curr_start.year})"
        
    df_curr = df_ns_base[(df_ns_base['Ngày'] >= curr_start) & (df_ns_base['Ngày'] <= curr_end)]
    df_prev = df_ns_base[(df_ns_base['Ngày'] >= prev_start) & (df_ns_base['Ngày'] <= prev_end)]
    
    avg_price_curr = df_curr['Đơn Giá'].mean()
    avg_price_curr = avg_price_curr if pd.notna(avg_price_curr) else 0.0
    avg_price_prev = df_prev['Đơn Giá'].mean()
    avg_price_prev = avg_price_prev if pd.notna(avg_price_prev) else 0.0
    diff_price = avg_price_curr - avg_price_prev
    
    total_salary_curr = df_curr['Tổng Lương'].sum() if not df_curr.empty else 0
    total_salary_prev = df_prev['Tổng Lương'].sum() if not df_prev.empty else 0
    diff_salary = total_salary_curr - total_salary_prev
    
    st.markdown(f"<div style='font-weight: 800; font-size: 16px; color: #333;'>So sánh Đơn Giá Trung Bình (Logic Kỳ Lương: Mốc ngày {max_date_ns.strftime('%d/%m/%Y')})</div>", unsafe_allow_html=True)
    m_ns1, m_ns2, m_ns3 = st.columns(3)
    m_ns1.metric(f"Hiện tại: {curr_name}", f"{avg_price_curr:,.0f} đ")
    m_ns2.metric(f"Kỳ trước: {prev_name}", f"{avg_price_prev:,.0f} đ")
    m_ns3.metric("Tăng/Giảm so với kỳ trước", f"{diff_price:,.0f} đ", f"{diff_price:,.0f} đ")
    
    st.markdown(f"<div style='font-weight: 800; font-size: 16px; color: #333; margin-top: 15px;'>So sánh Tổng Lương theo Loại: {', '.join(selected_ll)}</div>", unsafe_allow_html=True)
    m_sal1, m_sal2, m_sal3 = st.columns(3)
    m_sal1.metric(f"Tổng Lương Hiện Tại", f"{total_salary_curr:,.0f} đ")
    m_sal2.metric(f"Tổng Lương Kỳ Trước", f"{total_salary_prev:,.0f} đ")
    m_sal3.metric("Mức Tăng/Giảm Thu Nhập", f"{diff_salary:,.0f} đ", f"{diff_salary:,.0f} đ")
    
    if not df_ns_gtc_raw.empty:
        mask_gtc = pd.Series(True, index=df_ns_gtc_raw.index)
        if buu_cuc_ns != "Tất cả": 
            mask_gtc &= (df_ns_gtc_raw['Bưu Cục'].astype(str).str.strip().str.lower() == str(buu_cuc_ns).strip().lower())
        if nhan_vien_ns != "Tất cả": 
            mask_gtc &= (df_ns_gtc_raw['Nhân Viên'].astype(str).str.strip().str.lower() == str(nhan_vien_ns).strip().lower())
        if loai_hang_filter and 'Loại Hàng' in df_ns_gtc_raw.columns:
            mask_gtc &= (df_ns_gtc_raw['Loại Hàng'].astype(str).str.strip().isin(loai_hang_filter))
            
        df_ns_gtc_base = df_ns_gtc_raw[mask_gtc]
        
        df_n = df_ns_gtc_base[df_ns_gtc_base['Ngày'] == max_date_ns]
        df_n_prev = df_ns_gtc_base[df_ns_gtc_base['Ngày'] == (max_date_ns - timedelta(days=1))]
        
        def calc_gtc(df_sub):
            t_giao = df_sub['Đơn giao tính lương'].sum()
            t_gan = df_sub['Số đơn gán Giao'].sum()
            return (t_giao / t_gan * 100) if t_gan > 0 else 0.0

        gtc_n = calc_gtc(df_n)
        gtc_n_prev = calc_gtc(df_n_prev)

        start_w_ns = max_date_ns - timedelta(days=max_date_ns.weekday())
        end_w_ns = start_w_ns + timedelta(days=6)
        df_w = df_ns_gtc_base[(df_ns_gtc_base['Ngày'] >= start_w_ns) & (df_ns_gtc_base['Ngày'] <= end_w_ns)]
        
        start_w_prev_ns = start_w_ns - timedelta(days=7)
        end_w_prev_ns = start_w_prev_ns + timedelta(days=6)
        df_w_prev = df_ns_gtc_base[(df_ns_gtc_base['Ngày'] >= start_w_prev_ns) & (df_ns_gtc_base['Ngày'] <= end_w_prev_ns)]
        
        gtc_w = calc_gtc(df_w)
        gtc_w_prev = calc_gtc(df_w_prev)

        start_m_ns = max_date_ns.replace(day=1)
        next_m_ns = start_m_ns.replace(day=28) + timedelta(days=4)
        end_m_ns = next_m_ns - timedelta(days=next_m_ns.day)
        df_m = df_ns_gtc_base[(df_ns_gtc_base['Ngày'] >= start_m_ns) & (df_ns_gtc_base['Ngày'] <= end_m_ns)]
        
        start_m_prev_ns = (start_m_ns - timedelta(days=1)).replace(day=1)
        end_m_prev_ns = start_m_ns - timedelta(days=1)
        df_m_prev = df_ns_gtc_base[(df_ns_gtc_base['Ngày'] >= start_m_prev_ns) & (df_ns_gtc_base['Ngày'] <= end_m_prev_ns)]
        
        gtc_m = calc_gtc(df_m)
        gtc_m_prev = calc_gtc(df_m_prev)
        
        df_gtc_curr_kl = df_ns_gtc_base[(df_ns_gtc_base['Ngày'] >= curr_start) & (df_ns_gtc_base['Ngày'] <= curr_end)]
        df_gtc_prev_kl = df_ns_gtc_base[(df_ns_gtc_base['Ngày'] >= prev_start) & (df_ns_gtc_base['Ngày'] <= prev_end)]
        
        sl_gtc_curr_kl = df_gtc_curr_kl['Đơn giao tính lương'].sum()
        sl_gtc_prev_kl = df_gtc_prev_kl['Đơn giao tính lương'].sum()
        diff_sl_gtc_kl = sl_gtc_curr_kl - sl_gtc_prev_kl
        
        sl_n = df_n['Đơn giao tính lương'].sum()
        sl_n_prev = df_n_prev['Đơn giao tính lương'].sum()
        sl_w = df_w['Đơn giao tính lương'].sum()
        sl_w_prev = df_w_prev['Đơn giao tính lương'].sum()
        sl_m = df_m['Đơn giao tính lương'].sum()
        sl_m_prev = df_m_prev['Đơn giao tính lương'].sum()
        
    else:
        sl_gtc_curr_kl = sl_gtc_prev_kl = diff_sl_gtc_kl = 0
        gtc_n = gtc_n_prev = gtc_w = gtc_w_prev = gtc_m = gtc_m_prev = 0.0
        sl_n = sl_n_prev = sl_w = sl_w_prev = sl_m = sl_m_prev = 0

    st.markdown(f"<div style='font-weight: 800; font-size: 16px; color: #333; margin-top: 15px;'>So sánh Sản Lượng GTC (Logic Kỳ Lương)</div>", unsafe_allow_html=True)
    m_slkl1, m_slkl2, m_slkl3 = st.columns(3)
    m_slkl1.metric(f"SL GTC Hiện Tại ({curr_name})", f"{sl_gtc_curr_kl:,.0f} đơn")
    m_slkl2.metric(f"SL GTC Kỳ Trước ({prev_name})", f"{sl_gtc_prev_kl:,.0f} đơn")
    m_slkl3.metric("Tăng/Giảm so với kỳ trước", f"{diff_sl_gtc_kl:,.0f} đơn", f"{diff_sl_gtc_kl:,.0f} đơn")

    st.markdown(f"<div style='font-weight: 800; font-size: 16px; color: #333; margin-top: 25px;'>So sánh Năng suất %GTC (Mốc ngày {max_date_ns.strftime('%d/%m/%Y')})</div>", unsafe_allow_html=True)
    m_gtc1, m_gtc2, m_gtc3 = st.columns(3)
    m_gtc1.metric("Ngày (N vs N-1)", f"{gtc_n:.2f}%", f"{gtc_n - gtc_n_prev:.2f}% so với N-1")
    m_gtc2.metric("Tuần (W vs W-1)", f"{gtc_w:.2f}%", f"{gtc_w - gtc_w_prev:.2f}% so với W-1")
    m_gtc3.metric("Tháng (M vs M-1)", f"{gtc_m:.2f}%", f"{gtc_m - gtc_m_prev:.2f}% so với M-1")
    
    st.markdown(f"<div style='font-weight: 800; font-size: 16px; color: #333; margin-top: 25px;'>So sánh Sản Lượng GTC (Mốc ngày {max_date_ns.strftime('%d/%m/%Y')})</div>", unsafe_allow_html=True)
    m_sl1, m_sl2, m_sl3 = st.columns(3)
    m_sl1.metric("Ngày (N vs N-1)", f"{sl_n:,.0f} đơn", f"{sl_n - sl_n_prev:,.0f} đơn so với N-1")
    m_sl2.metric("Tuần (W vs W-1)", f"{sl_w:,.0f} đơn", f"{sl_w - sl_w_prev:,.0f} đơn so với W-1")
    m_sl3.metric("Tháng (M vs M-1)", f"{sl_m:,.0f} đơn", f"{sl_m - sl_m_prev:,.0f} đơn so với M-1")

    if not df_ns_gtc_raw.empty:
        mask_gtc_chart = pd.Series(True, index=df_ns_gtc_raw.index)
        if len(date_range_ns) == 2:
            mask_gtc_chart &= (df_ns_gtc_raw['Ngày'] >= pd.to_datetime(date_range_ns[0])) & (df_ns_gtc_raw['Ngày'] <= pd.to_datetime(date_range_ns[1]))
        if buu_cuc_ns != "Tất cả": 
            mask_gtc_chart &= (df_ns_gtc_raw['Bưu Cục'].astype(str).str.strip().str.lower() == str(buu_cuc_ns).strip().lower())
        if nhan_vien_ns != "Tất cả": 
            mask_gtc_chart &= (df_ns_gtc_raw['Nhân Viên'].astype(str).str.strip().str.lower() == str(nhan_vien_ns).strip().lower())
        if loai_hang_filter and 'Loại Hàng' in df_ns_gtc_raw.columns:
            mask_gtc_chart &= (df_ns_gtc_raw['Loại Hàng'].astype(str).str.strip().isin(loai_hang_filter))
        
        df_gtc_filtered = df_ns_gtc_raw[mask_gtc_chart].copy()
        if not df_gtc_filtered.empty:
            df_gtc_nv = df_gtc_filtered.groupby('Ngày').agg({'Đơn giao tính lương': 'sum', 'Số đơn gán Giao': 'sum'}).reset_index()
            df_gtc_nv['%GTC'] = (df_gtc_nv['Đơn giao tính lương'] / df_gtc_nv['Số đơn gán Giao'].replace({0.0: np.nan, 0: np.nan}) * 100).fillna(0.0)
        else:
            df_gtc_nv = pd.DataFrame(columns=['Ngày', 'Đơn giao tính lương', 'Số đơn gán Giao', '%GTC'])
    else:
        df_gtc_nv = pd.DataFrame(columns=['Ngày', 'Đơn giao tính lương', 'Số đơn gán Giao', '%GTC'])
        df_gtc_filtered = pd.DataFrame()

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
        fig_dg.update_traces(line=dict(color='#FF8C00', width=4), marker=dict(size=10, color='#007BFF', line=dict(width=2, color='white')))
        fig_dg.update_layout(title=dict(font=dict(size=18, family="Inter", color="#333")), plot_bgcolor='#ffffff', paper_bgcolor='#ffffff', hovermode="x unified", yaxis_title="VNĐ")
        fig_dg.update_yaxes(showgrid=True, gridcolor='#f0f0f0', title_font=dict(weight="bold"))
        fig_dg.update_xaxes(title_font=dict(weight="bold"), tickfont=dict(weight="bold"))
        st.plotly_chart(fig_dg, use_container_width=True)

    with chart_ns2:
        title_gtc = f"Năng suất & %GTC của {nhan_vien_ns}" if nhan_vien_ns != "Tất cả" else "Năng suất & %GTC toàn hệ thống"
        
        if not df_gtc_nv.empty:
            fig_gtc_nv = make_subplots(specs=[[{"secondary_y": True}]])
            fig_gtc_nv.add_trace(go.Bar(x=df_gtc_nv['Ngày'], y=df_gtc_nv['Số đơn gán Giao'], name="Số đơn gán", marker_color='#17a2b8', opacity=0.85), secondary_y=False)
            fig_gtc_nv.add_trace(go.Bar(x=df_gtc_nv['Ngày'], y=df_gtc_nv['Đơn giao tính lương'], name="Số đơn GTC", marker_color='#007BFF', opacity=0.85), secondary_y=False)
            fig_gtc_nv.add_trace(go.Scatter(x=df_gtc_nv['Ngày'], y=df_gtc_nv['%GTC'], name="% GTC", mode='lines+markers', line=dict(color='#FF8C00', width=4), marker=dict(size=10, color='#FF8C00', line=dict(width=2, color='white'))), secondary_y=True)

            fig_gtc_nv.update_layout(title=dict(text=title_gtc, font=dict(size=18, family="Inter", color="#333")), plot_bgcolor='#ffffff', paper_bgcolor='#ffffff', hovermode="x unified", barmode='group', legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(weight="bold")))
            fig_gtc_nv.update_yaxes(title_text="Số lượng", secondary_y=False, showgrid=True, gridcolor='#f0f0f0', title_font=dict(weight="bold"))
            fig_gtc_nv.update_yaxes(title_text="% GTC", secondary_y=True, showgrid=False, range=[0, 100], title_font=dict(weight="bold"))
            fig_gtc_nv.update_xaxes(title_font=dict(weight="bold"), tickfont=dict(weight="bold"), dtick="D1", tickformat="%d/%m")
            st.plotly_chart(fig_gtc_nv, use_container_width=True)
        else:
            st.warning("⚠️ Không tìm thấy dữ liệu Năng suất & %GTC phù hợp với bộ lọc.")

    st.markdown("---")
    chart_ns3, chart_ns4 = st.columns(2)
    with chart_ns3:
        df_luong = df_ns_filtered.groupby('Ngày')['Tổng Lương'].sum().reset_index()
        title_luong = f"Biến động Tổng Lương của {nhan_vien_ns}" if nhan_vien_ns != "Tất cả" else f"Biến động Tổng Lương tại {buu_cuc_ns}"
        fig_luong = px.line(df_luong, x='Ngày', y='Tổng Lương', markers=True, title=title_luong)
        fig_luong.update_traces(line=dict(color='#28a745', width=4), marker=dict(size=10, color='#007BFF', line=dict(width=2, color='white')))
        fig_luong.update_layout(title=dict(font=dict(size=18, family="Inter", color="#333")), plot_bgcolor='#ffffff', paper_bgcolor='#ffffff', hovermode="x unified", yaxis_title="VNĐ")
        fig_luong.update_yaxes(showgrid=True, gridcolor='#f0f0f0', title_font=dict(weight="bold"))
        fig_luong.update_xaxes(title_font=dict(weight="bold"), tickfont=dict(weight="bold"))
        st.plotly_chart(fig_luong, use_container_width=True)

    with chart_ns4:
        title_line_don = f"Số đơn Gán vs Giao của {nhan_vien_ns}" if nhan_vien_ns != "Tất cả" else f"Số đơn Gán vs Giao tại {buu_cuc_ns}"
        
        if not df_gtc_nv.empty:
            fig_line_don = go.Figure()
            fig_line_don.add_trace(go.Scatter(x=df_gtc_nv['Ngày'], y=df_gtc_nv['Số đơn gán Giao'], name="Số đơn gán", mode='lines+markers', line=dict(color='#FF8C00', width=4), marker=dict(size=10, line=dict(width=2, color='white'))))
            fig_line_don.add_trace(go.Scatter(x=df_gtc_nv['Ngày'], y=df_gtc_nv['Đơn giao tính lương'], name="Số đơn giao", mode='lines+markers', line=dict(color='#007BFF', width=4), marker=dict(size=10, line=dict(width=2, color='white'))))
        
            fig_line_don.update_layout(title=dict(text=title_line_don, font=dict(size=18, family="Inter", color="#333")), plot_bgcolor='#ffffff', paper_bgcolor='#ffffff', hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(weight="bold")))
            fig_line_don.update_yaxes(title_text="Số lượng đơn", showgrid=True, gridcolor='#f0f0f0', title_font=dict(weight="bold"))
            fig_line_don.update_xaxes(title_font=dict(weight="bold"), tickfont=dict(weight="bold"), dtick="D1", tickformat="%d/%m")
            st.plotly_chart(fig_line_don, use_container_width=True)
        else:
            st.warning("⚠️ Không tìm thấy dữ liệu Số đơn Gán vs Giao phù hợp với bộ lọc.")

    st.markdown("---")
    ai_role_ns = st.radio("🤖 Chọn đối tượng nhận báo cáo AI (Năng Suất):", ["Góc nhìn Giám Đốc", "Góc nhìn Quản lý khu vực (AM)", "Góc nhìn Nhân viên xử lý"], horizontal=True, key="role_ns")

    if st.button("🔍 Nhờ AI Phân tích Nhân sự & Chi phí", type="primary", key="btn_ai_ns"):
        with st.spinner("🔄 AI đang phân tích dữ liệu Năng Suất..."):
            if ai_role_ns == "Góc nhìn Giám Đốc":
                role_prompt = "Nhiệm vụ: Đóng vai Giám đốc Nhân sự. Đánh giá chuyên sâu 3 phần: 1. Đánh giá năng suất tổng thể, 2. Phân tích Quỹ lương/Chi phí/Đơn giá, 3. Đề xuất chính sách nhân sự cấp quản lý. Viết chuyên nghiệp."
            elif ai_role_ns == "Góc nhìn Quản lý khu vực (AM)":
                role_prompt = "Nhiệm vụ: Đóng vai Quản lý khu vực (AM). Đánh giá 3 phần: 1. Tổng quan năng suất giao hàng của khu vực, 2. Cảnh báo rủi ro về quỹ lương/đơn giá, 3. Chỉ đạo Nhân viên xử lý (điều hành kho) phân tuyến lại, ép năng suất giao hàng. Viết dứt khoát, thực tiễn và thúc đẩy."
            else:
                role_prompt = 'Nhiệm vụ: Đóng vai Trợ lý Nhân sự gửi thông báo cho NHÓM NHÂN VIÊN XỬ LÝ (Điều hành kho) & GIAO HÀNG. Xưng hô thân thiện, tạo động lực (dùng "Mình" với "Mọi người" hoặc "Anh em"). Hãy chia 3 phần: 1. Ghi nhận công sức/năng suất của team, 2. Thông báo nhanh tình hình tổng thu nhập/đơn giá, 3. Chia sẻ bí kíp/lời khuyên để anh em tăng thu nhập.'
                
            tong_don_gan = df_gtc_filtered['Số đơn gán Giao'].sum() if not df_gtc_filtered.empty else 0
            tong_don_giao = df_gtc_filtered['Đơn giao tính lương'].sum() if not df_gtc_filtered.empty else 0
            
            d_start_ns = date_range_ns[0].strftime('%d/%m/%Y')
            d_end_ns = date_range_ns[1].strftime('%d/%m/%Y') if len(date_range_ns) > 1 else d_start_ns
            lh_str_ns = ", ".join(loai_hang_filter) if loai_hang_filter else "Tất cả"
            ll_str_ns = ", ".join(selected_ll)

            prompt_ns = f"""
            Dữ liệu Năng suất & Nhân Sự Đã Lọc:
            - Thời gian: {d_start_ns} đến {d_end_ns}
            - Bưu cục/Khu vực: {buu_cuc_ns}
            - Nhân viên: {nhan_vien_ns}
            - Loại hàng: {lh_str_ns}
            - Loại lương áp dụng: {ll_str_ns}
            
            Kết quả thực tế:
            - Tổng số đơn gán (LTC): {tong_don_gan:,.0f} đơn
            - Tổng đơn giao thành công (GTC): {tong_don_giao:,.0f} đơn
            - Đơn giá trung bình: {avg_price_curr:,.0f} VNĐ
            - Tổng lương kỳ hiện tại ({curr_name}): {total_salary_curr:,.0f} đ (Tăng/giảm {diff_salary:,.0f} đ so với kỳ trước).
            
            {role_prompt}
            Yêu cầu BẮT BUỘC: Viết súc tích, phân bổ ý rõ ràng. Tuyệt đối không được bỏ dở câu. Kết thúc báo cáo bằng dòng chữ [HOÀN TẤT BÁO CÁO].
            """
            st.session_state.ai_ns_result = get_ai_analysis(prompt_ns)
    render_ai_and_telegram(st.session_state.ai_ns_result, "Năng Suất & Nhân Sự", "ns")


# ----------------- TAB 3: BÁO CÁO VẬN HÀNH THEO KPI -----------------
with tab3:
    styled_header("CÀI ĐẶT & THEO DÕI KPI VẬN HÀNH", "🎯")
    
    with st.expander("⚙️ ĐIỀU CHỈNH KPI (Sẽ tự động lưu lại theo từng Khu vực/Bưu cục)", expanded=True):
        bc_list_kpi = ["Tất cả", "Grand Total"] + [x for x in df_vh_tongquan['Bưu Cục'].unique() if str(x) not in ["Tất cả", "Grand Total"]]
        target_bc_kpi = st.selectbox("✏️ Chọn khu vực muốn cài đặt KPI:", bc_list_kpi, key="set_bc_kpi_tab3")
        
        if target_bc_kpi not in st.session_state.kpi_gtc_dict: st.session_state.kpi_gtc_dict[target_bc_kpi] = 70.0
        if target_bc_kpi not in st.session_state.kpi_tts_dict: st.session_state.kpi_tts_dict[target_bc_kpi] = 80.0
        if target_bc_kpi not in st.session_state.kpi_odr_dict: st.session_state.kpi_odr_dict[target_bc_kpi] = 98.0

        kpi_col1, kpi_col2, kpi_col3 = st.columns(3)
        with kpi_col1:
            st.session_state.kpi_gtc_dict[target_bc_kpi] = st.number_input(f"Mục tiêu KPI %GTC ({target_bc_kpi})", min_value=0.0, max_value=100.0, value=float(st.session_state.kpi_gtc_dict[target_bc_kpi]), step=0.5)
        with kpi_col2:
            st.session_state.kpi_tts_dict[target_bc_kpi] = st.number_input(f"Mục tiêu KPI %GTC TikTokShop ({target_bc_kpi})", min_value=0.0, max_value=100.0, value=float(st.session_state.kpi_tts_dict[target_bc_kpi]), step=0.5)
        with kpi_col3:
            st.session_state.kpi_odr_dict[target_bc_kpi] = st.number_input(f"KPI Ontime Giao TTS (ODR) ({target_bc_kpi})", min_value=0.0, max_value=100.0, value=float(st.session_state.kpi_odr_dict[target_bc_kpi]), step=0.5)

    t3_col1, t3_col2 = st.columns(2)
    with t3_col1:
        date_range_kpi = st.date_input("Chọn thời gian", [df_vh_tongquan['Ngày'].min(), df_vh_tongquan['Ngày'].max()], key="date_kpi")
    with t3_col2:
        buu_cuc_kpi = st.selectbox("Chọn Bưu cục để XEM số liệu", bc_list_kpi, key="bc_kpi")

    mask_kpi = pd.Series(True, index=df_vh_tongquan.index)
    if len(date_range_kpi) == 2:
        mask_kpi &= (df_vh_tongquan['Ngày'] >= pd.to_datetime(date_range_kpi[0])) & (df_vh_tongquan['Ngày'] <= pd.to_datetime(date_range_kpi[1]))
    if buu_cuc_kpi != "Tất cả":
        mask_kpi &= (df_vh_tongquan['Bưu Cục'].str.lower() == str(buu_cuc_kpi).lower())
    df_kpi_filtered = df_vh_tongquan[mask_kpi].copy()

    actual_gtc = df_kpi_filtered['GTC'].mean() if not df_kpi_filtered.empty else np.nan
    actual_tts = df_kpi_filtered['GTC_TTS'].mean() if not df_kpi_filtered.empty else np.nan
    actual_odr = df_kpi_filtered['ODR'].mean() if not df_kpi_filtered.empty else np.nan
    
    actual_gtc = actual_gtc if pd.notna(actual_gtc) else 0.0
    actual_tts = actual_tts if pd.notna(actual_tts) else 0.0
    actual_odr = actual_odr if pd.notna(actual_odr) else 0.0
    
    current_kpi_gtc = st.session_state.kpi_gtc_dict.get(buu_cuc_kpi, 70.0)
    current_kpi_tts = st.session_state.kpi_tts_dict.get(buu_cuc_kpi, 80.0)
    current_kpi_odr = st.session_state.kpi_odr_dict.get(buu_cuc_kpi, 98.0)

    gauge_col1, gauge_col2, gauge_col3 = st.columns(3)
    def create_gauge(title, value, target):
        steps = [
            {'range': [0, target * 0.8], 'color': "#FF7F50"},   # Fail: Cam san hô (Coral)
            {'range': [target * 0.8, target], 'color': "#48CAE4"}, # Warn: Xanh lam sáng (Light blue)
            {'range': [target, 100], 'color': "#00F2FE"}        # Success: Xanh ngọc lấp lánh
        ]
        delta_inc = "#00F2FE"
        delta_dec = "#FF7F50"
            
        fig = go.Figure(go.Indicator(
            mode = "gauge+number+delta", value = value, domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': title, 'font': {'size': 18, 'family': "Inter", 'color': '#0056b3', 'weight': 'bold'}},
            delta = {'reference': target, 'increasing': {'color': delta_inc}, 'decreasing': {'color': delta_dec}},
            gauge = {
                'axis': {'range': [0, 100], 'tickwidth': 2, 'tickcolor': "#333", 'tickfont': dict(weight="bold")},
                'bar': {'color': "#2C3E50", 'thickness': 0.25}, # Kim đo đổi thành Xanh Navy Đậm cho nổi bật
                'steps': steps,
                'borderwidth': 2,
                'bordercolor': "#e2e2e2",
            }
        ))
        fig.update_layout(height=320, margin=dict(l=20, r=20, t=50, b=20), font=dict(family="Inter"))
        return fig

    with gauge_col1:
        st.plotly_chart(create_gauge("Tỷ lệ GTC Chung (%)", actual_gtc, current_kpi_gtc), use_container_width=True)
    with gauge_col2:
        st.plotly_chart(create_gauge("Tỷ lệ GTC TikTok (%)", actual_tts, current_kpi_tts), use_container_width=True)
    with gauge_col3:
        st.plotly_chart(create_gauge("Ontime Giao TTS ODR (%)", actual_odr, current_kpi_odr), use_container_width=True)

    st.markdown("---")
    st.markdown("""
        <div style="background: linear-gradient(135deg, #00B4D8, #0077B6); padding: 15px 20px; border-radius: 8px; margin-bottom: 15px; box-shadow: 0 4px 10px rgba(0,0,0,0.15);">
            <h3 style="color: white; margin: 0; font-weight: 900; text-transform: uppercase;">📊 BẢNG THEO DÕI HOÀN THÀNH KPI THEO NGÀY</h3>
        </div>
    """, unsafe_allow_html=True)
    
    df_kpi_table = df_kpi_filtered.groupby('Ngày').agg({'GTC':'mean', 'GTC_TTS':'mean', 'ODR':'mean'}).reset_index()
    df_kpi_table['Ngày'] = df_kpi_table['Ngày'].dt.strftime('%d-%m-%Y')
    df_kpi_table['% Đạt KPI GTC'] = (df_kpi_table['GTC'] / current_kpi_gtc) * 100 if current_kpi_gtc > 0 else 0
    
    styled_kpi_table = df_kpi_table.style.set_properties(**{
        'background-color': '#f8fdff', 
        'color': '#003f5c', 
        'border-color': '#90e0ef'
    }).format({"GTC": "{:.2f}%", "GTC_TTS": "{:.2f}%", "ODR": "{:.2f}%", "% Đạt KPI GTC": "{:.1f}%"}).set_table_styles(header_styles)
    
    st.dataframe(styled_kpi_table, use_container_width=True)

    st.markdown("---")
    ai_role_kpi = st.radio("🤖 Chọn đối tượng nhận báo cáo AI (KPI):", ["Góc nhìn Giám Đốc", "Góc nhìn Quản lý khu vực (AM)", "Góc nhìn Nhân viên xử lý"], horizontal=True, key="role_kpi")

    if st.button("🔍 AI Đánh giá mức độ đạt KPI", type="primary", key="btn_ai_kpi"):
        with st.spinner("🔄 AI đang đối chiếu số liệu với mục tiêu KPI..."):
            if ai_role_kpi == "Góc nhìn Giám Đốc":
                role_prompt = "Đóng vai Giám đốc kiểm soát. Đưa ra: 1. Đánh giá tình hình đạt/trượt KPI vĩ mô, 2. Cảnh báo rủi ro hệ thống nếu trượt, 3. Yêu cầu hành động khẩn cấp cho Quản lý cấp trung."
            elif ai_role_kpi == "Góc nhìn Quản lý khu vực (AM)":
                role_prompt = "Nhiệm vụ: Đóng vai Quản lý khu vực (AM). Đánh giá 3 phần: 1. Phân tích mức độ hoàn thành KPI của khu vực so với mục tiêu, 2. Điểm danh các chỉ số đang báo động (đặc biệt ODR), 3. Giao task khẩn cho Nhân viên xử lý (điều hành kho) và Nhân viên giao hàng để kéo số. Viết dứt khoát, ép số."
            else:
                role_prompt = 'Nhiệm vụ: Đóng vai Trợ lý Báo cáo gửi tin nhắn cho NHÓM NHÂN VIÊN XỬ LÝ (Điều hành kho) & GIAO HÀNG. Xưng hô thân thiện, cổ vũ (dùng "Mình" với "Mọi người" hoặc "Team"). Hãy chia 3 phần: 1. Tuyên dương team nếu đạt KPI hoặc Động viên nếu trượt, 2. Chỉ ra điểm nghẽn hiện tại, 3. Phân công mục tiêu chạy gấp hôm nay để giữ vững phong độ/kéo lại số.'
                
            d_start_kpi = date_range_kpi[0].strftime('%d/%m/%Y')
            d_end_kpi = date_range_kpi[1].strftime('%d/%m/%Y') if len(date_range_kpi) > 1 else d_start_kpi
            
            prompt_kpi = f"""
            Dữ liệu KPI Đã Lọc:
            - Thời gian: {d_start_kpi} đến {d_end_kpi}
            - Bưu cục/Khu vực: {buu_cuc_kpi}
            
            Mục tiêu KPI: 
            - GTC > {current_kpi_gtc}% 
            - GTC TikTok > {current_kpi_tts}%
            - Ontime Giao TTS (ODR) > {current_kpi_odr}% (Càng cao càng tốt)
            
            Thực tế đạt được: 
            - GTC: {actual_gtc:.2f}% 
            - GTC TikTok: {actual_tts:.2f}%
            - Ontime Giao TTS (ODR): {actual_odr:.2f}%
            
            (LƯU Ý DÀNH CHO AI: ODR là tỷ lệ cam kết giao hàng đúng hạn với sàn Tiktokshop. Chỉ số ODR Thực tế phải LỚN HƠN HOẶC BẰNG Mục tiêu KPI thì mới được coi là hoàn thành xuất sắc. Nếu thấp hơn là trượt KPI, đang làm tệ).
            
            {role_prompt}
            Yêu cầu BẮT BUỘC: Viết súc tích, phân bổ ý rõ ràng. Tuyệt đối không được bỏ dở câu. Kết thúc báo cáo bằng dòng chữ [HOÀN TẤT BÁO CÁO].
            """
            st.session_state.ai_kpi_result = get_ai_analysis(prompt_kpi)
    render_ai_and_telegram(st.session_state.ai_kpi_result, "KPI Vận Hành", "kpi")


# ----------------- TAB 4: KINH DOANH -----------------
with tab4:
    styled_header("BÁO CÁO DOANH THU & KHÁCH HÀNG MỚI", "💰")
    
    with st.expander("⚙️ ĐIỀU CHỈNH KPI DOANH THU (Sẽ tự động lưu lại theo từng Khu vực/Bưu cục)", expanded=True):
        bc_list_kd = ["Tất cả", "Grand Total"] + [x for x in df_kinhdoanh['Bưu Cục'].unique() if str(x) not in ["Tất cả", "Grand Total"]]
        target_bc_kd = st.selectbox("✏️ Chọn khu vực muốn cài đặt KPI Doanh Thu:", bc_list_kd, key="set_bc_kd_tab4")
        
        if target_bc_kd not in st.session_state.kpi_dt_dict: st.session_state.kpi_dt_dict[target_bc_kd] = 710000000.0
        
        st.session_state.kpi_dt_dict[target_bc_kd] = st.number_input(f"Mục tiêu Doanh thu VNĐ/Tháng ({target_bc_kd})", min_value=0.0, value=float(st.session_state.kpi_dt_dict[target_bc_kd]), step=10000000.0)
    
    t4_col1, t4_col2, t4_col3 = st.columns(3)
    with t4_col1:
        date_range_kd = st.date_input("Chọn thời gian", [df_kinhdoanh['Ngày'].max() - timedelta(days=7), df_kinhdoanh['Ngày'].max()], key="date_kd")
    with t4_col2:
        buu_cuc_kd = st.selectbox("Chọn Bưu cục để XEM số liệu", bc_list_kd, key="bc_kd")
    with t4_col3:
        view_type = st.selectbox("Góc nhìn báo cáo", ["Theo Ngày", "Theo Tuần", "Theo Tháng"], key="view_kd")

    current_date = df_kinhdoanh['Ngày'].max()
    if len(date_range_kd) == 2:
        current_date = pd.to_datetime(date_range_kd[1])
        
    mask_kd = pd.Series(True, index=df_kinhdoanh.index)
    if buu_cuc_kd != "Tất cả":
        mask_kd &= (df_kinhdoanh['Bưu Cục'].str.lower() == str(buu_cuc_kd).lower())
    df_filtered_kd = df_kinhdoanh[mask_kd]
    
    if view_type == "Theo Ngày":
        rev_n = df_filtered_kd[df_filtered_kd['Ngày'] == current_date]['Doanh Thu'].sum()
        rev_prev = df_filtered_kd[df_filtered_kd['Ngày'] == (current_date - timedelta(days=1))]['Doanh Thu'].sum()
        label_prev = "So với N-1 (Hôm qua)"
    elif view_type == "Theo Tuần":
        start_w = current_date - timedelta(days=current_date.weekday())
        end_w = start_w + timedelta(days=6)
        rev_n = df_filtered_kd[(df_filtered_kd['Ngày'] >= start_w) & (df_filtered_kd['Ngày'] <= end_w)]['Doanh Thu'].sum()
        
        start_w_prev = start_w - timedelta(days=7)
        end_w_prev = start_w_prev + timedelta(days=6)
        rev_prev = df_filtered_kd[(df_filtered_kd['Ngày'] >= start_w_prev) & (df_filtered_kd['Ngày'] <= end_w_prev)]['Doanh Thu'].sum()
        label_prev = "So với W-1 (Tuần trước)"
    else: # Theo Tháng
        start_m = current_date.replace(day=1)
        next_month = start_m.replace(day=28) + timedelta(days=4)
        end_m = next_month - timedelta(days=next_month.day)
        rev_n = df_filtered_kd[(df_filtered_kd['Ngày'] >= start_m) & (df_filtered_kd['Ngày'] <= end_m)]['Doanh Thu'].sum()
        
        start_m_prev = (start_m - timedelta(days=1)).replace(day=1)
        end_m_prev = start_m - timedelta(days=1)
        rev_prev = df_filtered_kd[(df_filtered_kd['Ngày'] >= start_m_prev) & (df_filtered_kd['Ngày'] <= end_m_prev)]['Doanh Thu'].sum()
        label_prev = "So với M-1 (Tháng trước)"

    kpi_dt_val = st.session_state.kpi_dt_dict.get(buu_cuc_kd, 710000000.0)
    
    if view_type == "Theo Ngày": kpi_dt_val = kpi_dt_val / 30
    elif view_type == "Theo Tuần": kpi_dt_val = (kpi_dt_val / 30) * 7

    st.markdown(f"<div style='font-weight: 800; font-size: 16px; color: #333;'>Hiệu suất Doanh thu ({view_type})</div>", unsafe_allow_html=True)
    m_col1, m_col2, m_col3 = st.columns(3)
    m_col1.metric("Doanh Thu Hiện Tại", f"{rev_n:,.0f} đ", f"{(rev_n - kpi_dt_val)/kpi_dt_val*100:.1f}% vs KPI" if kpi_dt_val > 0 else "0%")
    m_col2.metric(label_prev, f"{rev_prev:,.0f} đ", f"{rev_n - rev_prev:,.0f} đ so với kỳ trước")
    
    mask_kd_range = mask_kd.copy()
    if len(date_range_kd) == 2:
        mask_kd_range &= (df_kinhdoanh['Ngày'] >= pd.to_datetime(date_range_kd[0])) & (df_kinhdoanh['Ngày'] <= pd.to_datetime(date_range_kd[1]))
    
    df_plot_kd_display = df_kinhdoanh[mask_kd_range].copy()
    if view_type == "Theo Tuần":
        df_plot_kd_display['Ngày'] = df_plot_kd_display['Ngày'].dt.to_period('W').apply(lambda r: r.start_time)
    elif view_type == "Theo Tháng":
        df_plot_kd_display['Ngày'] = df_plot_kd_display['Ngày'].dt.to_period('M').apply(lambda r: r.start_time)
        
    df_plot_kd_grouped = df_plot_kd_display.groupby('Ngày').agg({
        'Doanh Thu': 'sum', 'Khách Liên Hệ': 'sum', 'Khách Lên Đơn': 'sum', 'Doanh Thu KH Mới': 'sum'
    }).reset_index()

    chart_kd1, chart_kd2 = st.columns(2)
    with chart_kd1:
        fig_rev = px.bar(df_plot_kd_grouped, x='Ngày', y='Doanh Thu', title=f"Biểu đồ Doanh Thu & KPI ({buu_cuc_kd})", color_discrete_sequence=['#007BFF'])
        fig_rev.add_hline(y=kpi_dt_val, line_dash="dash", line_color="#FF3333", annotation_text="KPI Mục Tiêu")
        fig_rev.update_layout(title=dict(font=dict(size=18, family="Inter", color="#333", weight="bold")), plot_bgcolor='#ffffff', paper_bgcolor='#ffffff')
        fig_rev.update_yaxes(showgrid=True, gridcolor='#f0f0f0', title_font=dict(weight="bold"))
        fig_rev.update_xaxes(title_font=dict(weight="bold"), tickfont=dict(weight="bold"))
        st.plotly_chart(fig_rev, use_container_width=True)

    with chart_kd2:
        total_lh = df_plot_kd_grouped['Khách Liên Hệ'].sum()
        total_ld = df_plot_kd_grouped['Khách Lên Đơn'].sum()
        total_rev_new = df_plot_kd_grouped['Doanh Thu KH Mới'].sum()
        fig_funnel = go.Figure(go.Funnel(
            y=["Khách Liên Hệ", "Khách Lên Đơn (Chuyển đổi)"],
            x=[total_lh, total_ld], textinfo="value+percent initial",
            marker={"color": ["#FF8C00", "#28a745"]} 
        ))
        fig_funnel.update_layout(title=dict(text=f"Phễu chuyển đổi KH Mới ({view_type})", font=dict(size=18, family="Inter", color="#333", weight="bold")), plot_bgcolor='#ffffff', paper_bgcolor='#ffffff')
        st.plotly_chart(fig_funnel, use_container_width=True)

    st.markdown("---")
    st.markdown("""
        <div style="background: linear-gradient(135deg, #FF8C00, #ff5722); padding: 15px 20px; border-radius: 8px; margin-bottom: 15px; box-shadow: 0 4px 10px rgba(0,0,0,0.15);">
            <h3 style="color: white; margin: 0; font-weight: 900; text-transform: uppercase;">📋 Danh Sách Khách Hàng Tiềm Năng Chờ Chốt Deal</h3>
            <p style="color: #fff3cd; font-size: 14px; margin: 5px 0 0 0; font-style: italic;">(Chỉ hiển thị các khách hàng được đánh dấu phân loại "Khách hàng tiềm năng")</p>
        </div>
    """, unsafe_allow_html=True)
    
    if not df_khachhang.empty:
        target_col = [c for c in df_khachhang.columns if 'loại khách hàng' in str(c).lower()]
        if target_col:
            df_kh_filtered = df_khachhang[df_khachhang[target_col[0]].astype(str).str.contains('tiềm năng', case=False, na=False)]
        else:
            df_kh_filtered = df_khachhang
    else:
        df_kh_filtered = df_khachhang
        
    styled_df = df_kh_filtered.style.set_properties(**{
        'background-color': '#fff9f0', 
        'color': '#333333', 
        'border-color': '#ffcc80'
    }).set_table_styles(header_styles)
    
    st.dataframe(styled_df, use_container_width=True)

    st.markdown("---")
    ai_role_kd = st.radio("🤖 Chọn đối tượng nhận báo cáo AI (Kinh Doanh):", ["Góc nhìn Giám Đốc", "Góc nhìn Quản lý khu vực (AM)", "Góc nhìn Nhân viên xử lý"], horizontal=True, key="role_kd")

    if st.button("🔍 AI Cố vấn Kinh Doanh & Sales", type="primary", key="btn_ai_kd"):
        with st.spinner("🔄 AI đang phân tích hiệu suất Kinh Doanh..."):
            if ai_role_kd == "Góc nhìn Giám Đốc":
                role_prompt = "Nhiệm vụ: Đóng vai Giám đốc Kinh doanh. Hãy phân tích 3 phần: 1. Đánh giá hiệu suất chạy số tổng thể, 2. Phân tích tỷ lệ chốt sale, 3. Đề xuất chiến lược định hướng để tăng trưởng doanh thu."
            elif ai_role_kd == "Góc nhìn Quản lý khu vực (AM)":
                role_prompt = "Nhiệm vụ: Đóng vai Quản lý khu vực (AM). Phân tích 3 phần: 1. Đánh giá tốc độ chạy doanh thu của khu vực, 2. Cảnh báo tỷ lệ rớt đơn ở phễu khách hàng tiềm năng, 3. Đưa ra chỉ đạo thúc đẩy đội ngũ Nhân viên xử lý/Sales khu vực chốt deal khẩn cấp. Viết dứt khoát, máu lửa."
            else:
                role_prompt = 'Nhiệm vụ: Đóng vai Trợ lý Kinh doanh gửi tin báo cho NHÓM NHÂN VIÊN SALES/XỬ LÝ ĐƠN. Xưng hô thân thiện, máu lửa (dùng "Mình" với "Mọi người" hoặc "Team Sales"). Phân tích 3 phần: 1. Khen ngợi/Nhắc nhở tiến độ chạy số hôm nay, 2. Nhận xét tỷ lệ chốt sale thực tế, 3. Đưa ra mẹo nhỏ hoặc chiến lược để anh em chốt deal khẩn cấp.'
                
            d_start_kd = date_range_kd[0].strftime('%d/%m/%Y')
            d_end_kd = date_range_kd[1].strftime('%d/%m/%Y') if len(date_range_kd) > 1 else d_start_kd
            
            prompt_kd = f"""
            Dữ liệu Kinh Doanh Đã Lọc:
            - Thời gian: {d_start_kd} đến {d_end_kd}
            - Bưu cục/Khu vực: {buu_cuc_kd}
            - Góc nhìn báo cáo: {view_type}
            
            Thực tế đạt được:
            - KPI Doanh thu: {kpi_dt_val:,.0f} đ
            - Doanh thu thực tế: {rev_n:,.0f} đ (Tăng/giảm so với kỳ trước: {rev_prev:,.0f} đ)
            - Phễu Khách hàng tiềm năng: {total_lh} liên hệ -> {total_ld} lên đơn (chuyển đổi).
            
            {role_prompt}
            Yêu cầu BẮT BUỘC: Viết súc tích, phân bổ ý rõ ràng. Tuyệt đối không được bỏ dở câu. Kết thúc báo cáo bằng dòng chữ [HOÀN TẤT BÁO CÁO].
            """
            st.session_state.ai_kd_result = get_ai_analysis(prompt_kd)
    render_ai_and_telegram(st.session_state.ai_kd_result, "Kinh Doanh", "kd")

# ----------------- TAB 5: THI ĐUA GTC -----------------
with tab5:
    styled_header("BẢNG XẾP HẠNG CHƯƠNG TRÌNH THI ĐUA GTC", "🏆")
    
    col_t5_1, col_t5_2 = st.columns(2)
    with col_t5_1:
        min_date = df_ns_gtc_raw['Ngày'].min() if not df_ns_gtc_raw.empty and 'Ngày' in df_ns_gtc_raw.columns else datetime.today()
        max_date = df_ns_gtc_raw['Ngày'].max() if not df_ns_gtc_raw.empty and 'Ngày' in df_ns_gtc_raw.columns else datetime.today()
        if pd.isna(min_date): min_date = datetime.today()
        if pd.isna(max_date): max_date = datetime.today()
        
        date_range_t5 = st.date_input("Khoảng thời gian (Thi Đua):", [min_date, max_date], key="date_t5")
        
    with col_t5_2:
        bc_set_t5 = set(df_ns_gtc_raw['Bưu Cục'].dropna().astype(str).str.strip().unique()) if not df_ns_gtc_raw.empty and 'Bưu Cục' in df_ns_gtc_raw.columns else set()
        bc_all_t5 = sorted([x for x in bc_set_t5 if x and x != "Chưa phân loại" and x != "nan"])
        bc_list_t5 = ["Tất cả"] + bc_all_t5
        buu_cuc_t5 = st.selectbox("Lọc Bưu cục (Thi Đua):", bc_list_t5, key="bc_t5")
    
    df_t5_base = df_ns_gtc_raw.copy()
    
    if len(date_range_t5) == 2:
        curr_start = pd.to_datetime(date_range_t5[0])
        curr_end = pd.to_datetime(date_range_t5[1])
        
        # Tự động nhận diện Tháng Hiện Tại (Theo ngày kết thúc lọc) và Tháng Trước
        curr_m = curr_end.month
        curr_y = curr_end.year
        
        prev_d = curr_end.replace(day=1) - timedelta(days=1)
        prev_m = prev_d.month
        prev_y = prev_d.year
        
        col_curr = f"%GTC Tháng {curr_m:02d}"
        col_prev = f"%GTC Tháng {prev_m:02d}"
        
        if not df_t5_base.empty and 'Ngày' in df_t5_base.columns:
            # Dữ liệu Tháng Hiện Tại (Theo bộ lọc của người dùng)
            df_t7 = df_t5_base[(df_t5_base['Ngày'] >= curr_start) & (df_t5_base['Ngày'] <= curr_end)].copy()
            # Dữ liệu Tháng Trước (Lấy từ cơ sở dữ liệu tổng để không bị cắt xén)
            df_t6 = df_t5_base[(df_t5_base['Ngày'].dt.month == prev_m) & (df_t5_base['Ngày'].dt.year == prev_y)].copy()
        else:
            df_t7 = pd.DataFrame()
            df_t6 = pd.DataFrame()
    else:
        df_t7 = df_t5_base.copy()
        df_t6 = pd.DataFrame()
        col_curr = "%GTC Tháng Hiện Tại"
        col_prev = "%GTC Tháng Trước"
        
    if buu_cuc_t5 != "Tất cả":
        if not df_t7.empty and 'Bưu Cục' in df_t7.columns:
            df_t7 = df_t7[df_t7['Bưu Cục'].astype(str).str.strip().str.lower() == str(buu_cuc_t5).strip().lower()]
        if not df_t6.empty and 'Bưu Cục' in df_t6.columns:
            df_t6 = df_t6[df_t6['Bưu Cục'].astype(str).str.strip().str.lower() == str(buu_cuc_t5).strip().lower()]
        
    if not df_t7.empty:
        grp_t7 = df_t7.groupby('Nhân Viên').agg({'Số đơn gán Giao': 'sum', 'Đơn giao tính lương': 'sum'}).reset_index()
        # BẢO VỆ CHIA KHÔNG
        grp_t7[col_curr] = (grp_t7['Đơn giao tính lương'] / grp_t7['Số đơn gán Giao'].replace({0.0: np.nan, 0: np.nan}) * 100).fillna(0.0)
        
        if not df_t6.empty:
            grp_t6 = df_t6.groupby('Nhân Viên').agg({'Số đơn gán Giao': 'sum', 'Đơn giao tính lương': 'sum'}).reset_index()
            # BẢO VỆ CHIA KHÔNG
            grp_t6[col_prev] = (grp_t6['Đơn giao tính lương'] / grp_t6['Số đơn gán Giao'].replace({0.0: np.nan, 0: np.nan}) * 100).fillna(0.0)
        else:
            grp_t6 = pd.DataFrame(columns=['Nhân Viên', col_prev])
            
        df_thi_dua = pd.merge(grp_t7, grp_t6[['Nhân Viên', col_prev]], on='Nhân Viên', how='left')
        df_thi_dua[col_prev] = df_thi_dua[col_prev].fillna(0.0)
        
        # TỶ LỆ CẢI THIỆN = PHÉP TRỪ
        df_thi_dua['Tỷ Lệ Cải Thiện'] = df_thi_dua[col_curr] - df_thi_dua[col_prev]
        
        df_thi_dua.rename(columns={'Số đơn gán Giao': 'Tổng Đơn Gán', 'Đơn giao tính lương': 'Tổng Đơn GTC'}, inplace=True)
        
        # XẾP HẠNG
        df_thi_dua['Xếp Hạng Gán'] = df_thi_dua['Tổng Đơn Gán'].rank(method='min', ascending=False)
        df_thi_dua['Xếp Hạng %GTC'] = df_thi_dua[col_curr].rank(method='min', ascending=False)
        df_thi_dua['Xếp Hạng Cải Thiện'] = df_thi_dua['Tỷ Lệ Cải Thiện'].rank(method='min', ascending=False)
        
        df_thi_dua['Tổng Điểm'] = (df_thi_dua['Xếp Hạng Gán'] + df_thi_dua['Xếp Hạng %GTC'] + df_thi_dua['Xếp Hạng Cải Thiện']) / 3
        
        # BỔ SUNG LOGIC TIE-BREAKER: Ưu tiên %GTC tháng hiện tại nếu bằng điểm
        df_thi_dua['Tie_Breaker'] = -df_thi_dua[col_curr]
        df_thi_dua['Xếp Hạng Tổng'] = df_thi_dua[['Tổng Điểm', 'Tie_Breaker']].apply(tuple, axis=1).rank(method='min')
        df_thi_dua = df_thi_dua.drop(columns=['Tie_Breaker'])
        
        df_thi_dua['Đạt Điều Kiện Thưởng (>=80%)'] = np.where(df_thi_dua[col_curr] >= 80, '✅', '❌')
        
        df_thi_dua = df_thi_dua.sort_values('Xếp Hạng Tổng')
        
        cols_order_td = ['Nhân Viên', 'Tổng Đơn Gán', 'Tổng Đơn GTC', col_curr, col_prev, 'Tỷ Lệ Cải Thiện', 'Xếp Hạng Gán', 'Xếp Hạng %GTC', 'Xếp Hạng Cải Thiện', 'Tổng Điểm', 'Xếp Hạng Tổng', 'Đạt Điều Kiện Thưởng (>=80%)']
        df_thi_dua = df_thi_dua[cols_order_td]
        
        styled_thi_dua = df_thi_dua.style.format({
            'Tổng Đơn Gán': "{:,.0f}",
            'Tổng Đơn GTC': "{:,.0f}",
            col_curr: "{:.2f}%",
            col_prev: "{:.2f}%",
            'Tỷ Lệ Cải Thiện': "{:+.2f}%",
            'Xếp Hạng Gán': "{:.0f}",
            'Xếp Hạng %GTC': "{:.0f}",
            'Xếp Hạng Cải Thiện': "{:.0f}",
            'Tổng Điểm': "{:.2f}",
            'Xếp Hạng Tổng': "{:.0f}"
        }).set_properties(**{
            'background-color': '#FFF4E6',  # Vàng cam nhạt (Năng động)
            'color': '#D35400',             # Cam đậm cháy
            'border-color': '#FF9F43',      # Viền cam sáng
            'font-weight': '600'            # Làm đậm các con số thi đua
        }).set_table_styles(header_styles)
        
        st.dataframe(styled_thi_dua, use_container_width=True)
        
        st.markdown("---")
        styled_header("BẢNG NĂNG SUẤT NHÂN VIÊN HẰNG NGÀY", "📅")
        
        df_daily = df_t7.copy()
        if 'Ngày' in df_daily.columns:
            df_daily['Ngày Str'] = df_daily['Ngày'].dt.strftime('%d/%m')
            
            grp_daily = df_daily.groupby(['Nhân Viên', 'Ngày', 'Ngày Str']).agg({'Số đơn gán Giao': 'sum', 'Đơn giao tính lương': 'sum'}).reset_index()
            # BẢO VỆ CHIA KHÔNG
            grp_daily['%GTC'] = (grp_daily['Đơn giao tính lương'] / grp_daily['Số đơn gán Giao'].replace({0.0: np.nan, 0: np.nan}) * 100).fillna(0.0)
            
            pivot_daily = grp_daily.pivot(index='Nhân Viên', columns='Ngày Str', values=['Số đơn gán Giao', 'Đơn giao tính lương', '%GTC'])
            
            dates_sorted = sorted(grp_daily['Ngày'].unique())
            dates_sorted_str = [pd.to_datetime(d).strftime('%d/%m') for d in dates_sorted]
            
            cols_order_daily = []
            new_cols_names = []
            for d_str in dates_sorted_str:
                cols_order_daily.extend([('Số đơn gán Giao', d_str), ('Đơn giao tính lương', d_str), ('%GTC', d_str)])
                new_cols_names.extend([f"Tổng Đơn Gán ({d_str})", f"Tổng Đơn GTC ({d_str})", f"%GTC ({d_str})"])
                
            valid_cols = [c for c in cols_order_daily if c in pivot_daily.columns]
            pivot_daily = pivot_daily[valid_cols]
            
            final_names = []
            for c in valid_cols:
                if c[0] == 'Số đơn gán Giao': final_names.append(f"Tổng Đơn Gán ({c[1]})")
                elif c[0] == 'Đơn giao tính lương': final_names.append(f"Tổng Đơn GTC ({c[1]})")
                else: final_names.append(f"%GTC ({c[1]})")
                
            pivot_daily.columns = final_names
            pivot_daily = pivot_daily.reset_index().fillna(0)
            
            format_dict_daily = {}
            for col in pivot_daily.columns:
                if col != 'Nhân Viên':
                    if '%GTC' in col:
                        format_dict_daily[col] = "{:.2f}%"
                    else:
                        format_dict_daily[col] = "{:,.0f}"
                        
            styled_daily = pivot_daily.style.format(format_dict_daily).set_properties(**{
                'background-color': '#E1F5FE',  # Xanh dương nhạt (Tươi sáng)
                'color': '#0277BD',             # Xanh lam đậm
                'border-color': '#29B6F6',      # Viền xanh da trời
                'font-weight': '500'            # Làm rõ số liệu
            }).set_table_styles(header_styles)
            
            st.dataframe(styled_daily, use_container_width=True)
            
            st.markdown("---")
            ai_role_td = st.radio("🤖 Chọn đối tượng nhận báo cáo AI (Thi Đua GTC):", ["Góc nhìn Giám Đốc", "Góc nhìn Quản lý khu vực (AM)", "Góc nhìn Nhân viên xử lý"], horizontal=True, key="role_td")

            if st.button("🔍 AI Đánh giá Chương trình Thi đua", type="primary", key="btn_ai_td"):
                with st.spinner("🔄 AI đang phân tích dữ liệu Thi đua GTC..."):
                    if ai_role_td == "Góc nhìn Giám Đốc":
                        role_prompt = "Đóng vai Giám đốc vận hành. Đánh giá tổng quan hiệu suất thi đua của các bưu cục, vinh danh những nhân sự xuất sắc và chỉ ra các rủi ro năng suất từ nhóm xếp cuối."
                    elif ai_role_td == "Góc nhìn Quản lý khu vực (AM)":
                        role_prompt = "Đóng vai Quản lý khu vực (AM). Nhận xét trực diện bảng xếp hạng thi đua, đốc thúc các cá nhân đang ở thứ hạng thấp và có phương án điều phối ngay lập tức."
                    else:
                        role_prompt = 'Đóng vai Trợ lý Điều phối gửi thông báo cho đội Shipper/Nhân viên. Dùng xưng hô thân thiện ("Mình" với "Mọi người/Anh em"). Vinh danh top đầu, động viên top cuối cố gắng để đạt mốc thưởng >=80%.'
                    
                    top_3 = df_thi_dua.head(3)[['Nhân Viên', col_curr, 'Tổng Điểm']].to_dict('records') if not df_thi_dua.empty else []
                    bottom_3 = df_thi_dua.tail(3)[['Nhân Viên', col_curr]].to_dict('records') if not df_thi_dua.empty else []
                    
                    d_start_td = date_range_t5[0].strftime('%d/%m/%Y') if len(date_range_t5) > 0 else ""
                    d_end_td = date_range_t5[1].strftime('%d/%m/%Y') if len(date_range_t5) > 1 else d_start_td

                    prompt_td = f"""
                    Dữ liệu Thi đua GTC Đã Lọc:
                    - Thời gian: {d_start_td} đến {d_end_td}
                    - Bưu cục/Khu vực: {buu_cuc_t5}
                    
                    Top 3 Xuất sắc nhất: {top_3}
                    Top 3 Cần cố gắng: {bottom_3}
                    
                    (LƯU Ý DÀNH CHO AI: Điều kiện nhận thưởng là %GTC của {col_curr} phải >= 80%. Mức độ cải thiện tính bằng {col_curr} trừ đi {col_prev} (điểm % phần trăm). Xếp hạng tổng dựa trên trung bình thứ hạng của 3 tiêu chí: Số lượng gán, %GTC, %Cải thiện. Xếp hạng càng thấp (1,2,3) thì càng giỏi).
                    
                    {role_prompt}
                    Yêu cầu BẮT BUỘC: Viết súc tích, phân bổ ý rõ ràng. Tuyệt đối không được bỏ dở câu. Kết thúc báo cáo bằng dòng chữ [HOÀN TẤT BÁO CÁO].
                    """
                    st.session_state.ai_td_result = get_ai_analysis(prompt_td)
            render_ai_and_telegram(st.session_state.ai_td_result, "Thi Đua GTC", "td")
            
        else:
            st.warning("⚠️ Dữ liệu không có cột Ngày để hiển thị bảng hằng ngày.")
    else:
        st.warning("⚠️ Không có dữ liệu Thi đua & Năng suất cho Bưu Cục này.")

# ----------------- TAB 6: TRỢ LÝ AI -----------------
with tab6:
    styled_header("TRỢ LÝ AI PHÂN TÍCH & GIẢI ĐÁP", "🤖")
    st.markdown("Tại đây bạn có thể yêu cầu AI phân tích dữ liệu chung, đưa ra lời khuyên hoặc đặt các câu hỏi về nghiệp vụ Logistics.")
    
    chat_container = st.container()
    with chat_container:
        for chat in st.session_state.chat_history:
            with st.chat_message(chat["role"]):
                st.markdown(chat["content"])
                
    if prompt_chat := st.chat_input("Nhập câu hỏi hoặc yêu cầu cho AI..."):
        st.session_state.chat_history.append({"role": "user", "content": prompt_chat})
        with st.chat_message("user"): st.markdown(prompt_chat)
        
        with st.chat_message("assistant"):
            if not GEMINI_API_KEY or GEMINI_API_KEY == "ĐIỀN_API_KEY_GEMINI_CỦA_BẠN_VÀO_ĐÂY":
                st.error("Chưa cấu hình API Key. Vui lòng thiết lập biến môi trường GEMINI_API_KEY.")
            else:
                try:
                    genai.configure(api_key=GEMINI_API_KEY.strip())
                    model_chat = genai.GenerativeModel('gemini-3.6-flash')
                    response_chat = model_chat.generate_content(f"Người dùng nói: {prompt_chat}. Hãy trả lời ngắn gọn, tập trung vào logistics và phân tích số liệu.")
                    st.markdown(response_chat.text)
                    st.session_state.chat_history.append({"role": "assistant", "content": response_chat.text})
                except Exception as e:
                    st.error(f"Lỗi AI: {e}")
