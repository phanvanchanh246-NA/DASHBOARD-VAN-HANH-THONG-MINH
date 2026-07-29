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
if "kpi_odr_dict" not in st.session_state: st.session_state.kpi_odr_dict = {"Tất cả": 5.0} 
if "kpi_dt_dict" not in st.session_state: st.session_state.kpi_dt_dict = {"Tất cả": 71000000.0}

if "ai_vh_result" not in st.session_state: st.session_state.ai_vh_result = "Bấm nút '🔍 Nhờ AI Phân tích' để xem cố vấn chi tiết."
if "ai_ns_result" not in st.session_state: st.session_state.ai_ns_result = "Bấm nút '🔍 Nhờ AI Phân tích' để xem cố vấn chi tiết."
if "ai_kpi_result" not in st.session_state: st.session_state.ai_kpi_result = "Bấm nút '🔍 Nhờ AI Phân tích' để xem cố vấn chi tiết."
if "ai_kd_result" not in st.session_state: st.session_state.ai_kd_result = "Bấm nút '🔍 Nhờ AI Phân tích' để xem cố vấn chi tiết."

# Bộ nhớ cho Chatbot
if "chat_history" not in st.session_state: st.session_state.chat_history = []

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

# ==========================================
# BẢO MẬT ĐĂNG NHẬP
# ==========================================
def check_login():
    st.markdown("<h2 style='text-align: center; color: #007BFF;'>🔐 HỆ THỐNG QUẢN TRỊ NỘI BỘ GHN</h2>", unsafe_allow_html=True)
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
    st.stop() # Dừng hệ thống tại đây nếu chưa đăng nhập thành công

# Nút Đăng xuất ở thanh bên
with st.sidebar:
    if st.button("🚪 Đăng xuất", use_container_width=True):
        st.session_state.authenticated = False
        st.rerun()
        
    st.divider()
    # CHATBOT AI DẠY VIỆC
    st.markdown("### 🤖 Trợ lý AI Riêng")
    for chat in st.session_state.chat_history:
        with st.chat_message(chat["role"]):
            st.markdown(chat["content"])
            
    if prompt_chat := st.chat_input("Dạy AI hoặc đặt câu hỏi..."):
        st.session_state.chat_history.append({"role": "user", "content": prompt_chat})
        with st.chat_message("user"): st.markdown(prompt_chat)
        
        with st.chat_message("assistant"):
            if not GEMINI_API_KEY or GEMINI_API_KEY == "ĐIỀN_API_KEY_GEMINI_CỦA_BẠN_VÀO_ĐÂY":
                st.error("Chưa cấu hình API Key.")
            else:
                try:
                    genai.configure(api_key=GEMINI_API_KEY.strip())
                    model_chat = genai.GenerativeModel('gemini-3.6-flash')
                    response_chat = model_chat.generate_content(f"Người dùng nói: {prompt_chat}. Hãy trả lời ngắn gọn, tập trung vào logistics.")
                    st.markdown(response_chat.text)
                    st.session_state.chat_history.append({"role": "assistant", "content": response_chat.text})
                except Exception as e:
                    st.error(f"Lỗi AI: {e}")


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
    fig.update_yaxes(title_text="Sản lượng", secondary_y=False, showgrid=False)
    fig.update_yaxes(title_text="Tỷ lệ (%)", secondary_y=True, showgrid=True, gridcolor='rgba(0,0,0,0.05)', range=[0, 100])
    return fig

# ==========================================
# 2. LẤY DỮ LIỆU TỪ GOOGLE SHEETS (SIÊU BỘ LỌC CHỐNG LỖI V2)
# ==========================================
def parse_vn_num(val):
    val = str(val).replace('%', '').replace('đ', '').replace('VNĐ', '').replace(' ', '').strip()
    if val in ['nan', 'None', '', '0', '0.0']: 
        return 0.0
    if ',' in val and '.' in val:
        if val.rfind(',') > val.rfind('.'): 
            val = val.replace('.', '').replace(',', '.')
        else: 
            val = val.replace(',', '')
    elif ',' in val:
        val = val.replace(',', '.')
    elif '.' in val:
        parts = val.split('.')
        if len(parts) > 2: 
            val = val.replace('.', '')
        else:
            if len(parts[1]) == 3: 
                val = val.replace('.', '')
    try:
        return float(val)
    except:
        return 0.0

def clean_dataframe_numbers(df, text_cols):
    df.columns = df.columns.astype(str).str.strip().str.replace('\xa0', ' ')
    for col in df.columns:
        if col not in text_cols:
            df[col] = df[col].apply(parse_vn_num)
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
            <h1 style="color: white; margin-bottom: 0;">DASHBOARD QUẢN LÝ VẬN HÀNH KINH DOANH GHN</h1>
            <p style="font-size: 16px; opacity: 0.9;">Vận Hành - Năng Suất - KPI - Kinh Doanh</p>
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
        mask_vh &= (df_vanhanh['Ngày'] >= pd.to_datetime(date_range_vh[0])) & (df_vanhanh['Ngày'] <= pd.to_datetime(date_range_vh[1]))
    if buu_cuc_vh != "Tất cả":
        mask_vh &= (df_vanhanh['Bưu Cục'] == buu_cuc_vh)
    df_vh_filtered = df_vanhanh[mask_vh].copy()

    styled_header("1. TỔNG QUAN GTC VÀ TỶ LỆ TRẢ HÀNG", "🌍")
    
    view_mode_vh = st.radio("Chế độ xem Tổng quan:", ["Theo Ngày", "Theo Tuần", "Theo Tháng"], horizontal=True, key="view_mode_vh")
    
    df_trend_display = df_vh_filtered.copy()
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
        latest_vol = df_trend_display.iloc[-1]['Volume']
        latest_gtc = df_trend_display.iloc[-1]['GTC']
        
        prev_vol = 0
        prev_gtc = 0
        if len(df_trend_display) > 1:
            prev_vol = df_trend_display.iloc[-2]['Volume']
            prev_gtc = df_trend_display.iloc[-2]['GTC']
            
        st.markdown(f"**So sánh kỳ gần nhất so với kỳ trước ({view_mode_vh}):**")
        m_col1, m_col2 = st.columns(2)
        m_col1.metric("Tổng Sản Lượng", f"{latest_vol:,.0f} đơn", f"{latest_vol - prev_vol:,.0f} đơn")
        m_col2.metric("Tỷ lệ GTC", f"{latest_gtc:.2f}%", f"{latest_gtc - prev_gtc:.2f}%")

    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        fig_gtc = draw_combo_chart(df_trend_display, 'Ngày', 'Volume', 'GTC', f"Tỷ lệ GTC và Sản Lượng ({view_mode_vh})")
        st.plotly_chart(fig_gtc, use_container_width=True)
    with chart_col2:
        fig_return = px.line(df_trend_display, x='Ngày', y='Trả Hàng', markers=True, title=f"Tỷ lệ Trả Hàng ({view_mode_vh}) (%)")
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
        fig_odr = px.line(df_tts, x='Ngày', y='ODR', markers=True, title="Tỷ lệ Ontime TTS (ODR TikTokShop)")
        fig_odr.update_traces(line=dict(color='#007BFF', width=3), marker=dict(size=8, color='#FF8C00'))
        fig_odr.update_layout(plot_bgcolor='rgba(240, 248, 255, 0.5)', yaxis=dict(range=[70, 100]))
        st.plotly_chart(fig_odr, use_container_width=True)

    styled_header("3. NĂNG SUẤT GIAO THEO CA LÀM VIỆC", "🕒")
    df_ca = df_vh_filtered.groupby(['Ngày', 'Ca']).agg({'Volume': 'sum', 'GTC': 'mean'}).reset_index()
    
    df_ca['TrụcX'] = df_ca['Ngày'].dt.strftime('%d/%m') + " - " + df_ca['Ca']
    
    fig_ca = make_subplots(specs=[[{"secondary_y": True}]])
    for ca_name in df_ca['Ca'].unique():
        df_ca_sub = df_ca[df_ca['Ca'] == ca_name]
        fig_ca.add_trace(go.Bar(x=df_ca_sub['TrụcX'], y=df_ca_sub['Volume'], name=f"Volume {ca_name}", opacity=0.7), secondary_y=False)
        fig_ca.add_trace(go.Scatter(x=df_ca_sub['TrụcX'], y=df_ca_sub['GTC'], name=f"%GTC {ca_name}", mode='lines+markers', marker=dict(size=8)), secondary_y=True)

    fig_ca.update_layout(title="Sản Lượng và Tỷ Lệ GTC Theo Ca Làm Việc", plot_bgcolor='rgba(240, 248, 255, 0.5)', hovermode="x unified", barmode='group')
    fig_ca.update_yaxes(title_text="Sản lượng", secondary_y=False)
    fig_ca.update_yaxes(title_text="% GTC", secondary_y=True, range=[0, 100])
    st.plotly_chart(fig_ca, use_container_width=True)

    if st.button("🔍 Nhờ AI Phân tích Vận Hành", type="primary", key="btn_ai_vh"):
        with st.spinner("🔄 AI đang phân tích dữ liệu Vận Hành..."):
            prompt_vh = f"""
            Dữ liệu Vận Hành (Đã lọc theo bưu cục {buu_cuc_vh}): 
            - Tổng đơn: {df_vh_filtered['Volume'].sum()}
            - Tỷ lệ GTC: {df_vh_filtered['GTC'].mean():.2f}%
            - Tỷ lệ Tồn kho: {df_vh_filtered['ODR'].mean():.2f}%
            Nhiệm vụ: Đóng vai Giám đốc vận hành. Phân tích CHUYÊN SÂU theo 3 phần: 1. Đánh giá tổng quan, 2. Phân tích Rủi ro, 3. Đề xuất hành động. Viết tiếng Việt chuẩn, không bỏ dở câu.
            """
            st.session_state.ai_vh_result = get_ai_analysis(prompt_vh)
    render_ai_and_telegram(st.session_state.ai_vh_result, "Vận Hành", "vh")


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
        mask_ns &= (df_nhansu['Ngày'] >= pd.to_datetime(date_range_ns[0])) & (df_nhansu['Ngày'] <= pd.to_datetime(date_range_ns[1]))
    if loai_hang_filter:
        mask_ns &= df_nhansu['Loại Hàng'].isin(loai_hang_filter)
    if buu_cuc_ns != "Tất cả":
        mask_ns &= (df_nhansu['Bưu Cục'] == buu_cuc_ns)
    if nhan_vien_ns != "Tất cả":
        mask_ns &= (df_nhansu['Nhân Viên'] == nhan_vien_ns)
    df_ns_filtered = df_nhansu[mask_ns].copy()

    styled_header("PHÂN TÍCH ĐƠN GIÁ & NĂNG SUẤT GIAO", "📈")
    
    # === BỔ SUNG LOGIC SO SÁNH KỲ LƯƠNG ===
    mask_ns_no_date = pd.Series(True, index=df_nhansu.index)
    if loai_hang_filter: mask_ns_no_date &= df_nhansu['Loại Hàng'].isin(loai_hang_filter)
    if buu_cuc_ns != "Tất cả": mask_ns_no_date &= (df_nhansu['Bưu Cục'] == buu_cuc_ns)
    if nhan_vien_ns != "Tất cả": mask_ns_no_date &= (df_nhansu['Nhân Viên'] == nhan_vien_ns)
    df_ns_base = df_nhansu[mask_ns_no_date]
    
    max_date_ns = pd.to_datetime(date_range_ns[1]) if len(date_range_ns) == 2 else pd.to_datetime(date_range_ns[0])
    
    if max_date_ns.day <= 15:
        curr_start = max_date_ns.replace(day=1)
        curr_end = max_date_ns.replace(day=15)
        prev_end = curr_start - timedelta(days=1)
        prev_start = prev_end.replace(day=16)
        curr_name = f"Kỳ 20 ({curr_start.month}/{curr_start.year})"
        prev_name = f"Kỳ 05 ({prev_start.month}/{prev_start.year})"
    else:
        curr_start = max_date_ns.replace(day=16)
        next_m = (curr_start.replace(day=28) + timedelta(days=4)).replace(day=1)
        curr_end = next_m - timedelta(days=1)
        prev_start = max_date_ns.replace(day=1)
        prev_end = max_date_ns.replace(day=15)
        curr_name = f"Kỳ 05 ({curr_start.month}/{curr_start.year})"
        prev_name = f"Kỳ 20 ({prev_start.month}/{prev_start.year})"
        
    df_curr = df_ns_base[(df_ns_base['Ngày'] >= curr_start) & (df_ns_base['Ngày'] <= curr_end)]
    df_prev = df_ns_base[(df_ns_base['Ngày'] >= prev_start) & (df_ns_base['Ngày'] <= prev_end)]
    
    avg_price_curr = df_curr['Đơn Giá'].mean() if not df_curr.empty else 0
    avg_price_prev = df_prev['Đơn Giá'].mean() if not df_prev.empty else 0
    diff_price = avg_price_curr - avg_price_prev
    
    st.markdown(f"**So sánh Đơn Giá Trung Bình (Logic Kỳ Lương: Mốc ngày {max_date_ns.strftime('%d/%m/%Y')})**")
    m_ns1, m_ns2, m_ns3 = st.columns(3)
    m_ns1.metric(f"Hiện tại: {curr_name}", f"{avg_price_curr:,.0f} đ")
    m_ns2.metric(f"Kỳ trước: {prev_name}", f"{avg_price_prev:,.0f} đ")
    m_ns3.metric("Tăng/Giảm so với kỳ trước", f"{diff_price:,.0f} đ", f"{diff_price:,.0f} đ")
    
    # ==============================

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

    if st.button("🔍 Nhờ AI Phân tích Nhân sự & Chi phí", type="primary", key="btn_ai_ns"):
        with st.spinner("🔄 AI đang phân tích dữ liệu Năng Suất..."):
            prompt_ns = f"""
            Dữ liệu Năng suất Nhân sự (Đã lọc): 
            - Tổng đơn đã giao: {df_ns_filtered['Số Đơn'].sum()}
            - Đơn giá trung bình: {df_ns_filtered['Đơn Giá'].mean():,.0f} VNĐ
            - Kỳ lương: Hiện tại {curr_name} đang là {avg_price_curr:,.0f} đ (Tăng/giảm {diff_price:,.0f} so với kỳ trước).
            Nhiệm vụ: Đóng vai Quản lý nhân sự. Đánh giá chuyên sâu 3 phần: 1. Đánh giá năng suất, 2. Rủi ro chi phí, 3. Đề xuất nhân sự.
            """
            st.session_state.ai_ns_result = get_ai_analysis(prompt_ns)
    render_ai_and_telegram(st.session_state.ai_ns_result, "Năng Suất & Nhân Sự", "ns")


# ----------------- TAB 3: BÁO CÁO VẬN HÀNH THEO KPI -----------------
with tab3:
    styled_header("CÀI ĐẶT & THEO DÕI KPI VẬN HÀNH", "🎯")
    
    with st.expander("⚙️ ĐIỀU CHỈNH KPI (Sẽ tự động lưu lại theo từng Khu vực/Bưu cục)", expanded=True):
        target_bc_kpi = st.selectbox("✏️ Chọn khu vực muốn cài đặt KPI:", ["Tất cả"] + list(df_vanhanh['Bưu Cục'].unique()), key="set_bc_kpi_tab3")
        
        if target_bc_kpi not in st.session_state.kpi_gtc_dict: st.session_state.kpi_gtc_dict[target_bc_kpi] = 90.0
        if target_bc_kpi not in st.session_state.kpi_tts_dict: st.session_state.kpi_tts_dict[target_bc_kpi] = 85.0
        if target_bc_kpi not in st.session_state.kpi_odr_dict: st.session_state.kpi_odr_dict[target_bc_kpi] = 5.0

        kpi_col1, kpi_col2, kpi_col3 = st.columns(3)
        with kpi_col1:
            st.session_state.kpi_gtc_dict[target_bc_kpi] = st.number_input(f"Mục tiêu KPI %GTC ({target_bc_kpi})", min_value=0.0, max_value=100.0, value=float(st.session_state.kpi_gtc_dict[target_bc_kpi]), step=0.5)
        with kpi_col2:
            st.session_state.kpi_tts_dict[target_bc_kpi] = st.number_input(f"Mục tiêu KPI %GTC TikTokShop ({target_bc_kpi})", min_value=0.0, max_value=100.0, value=float(st.session_state.kpi_tts_dict[target_bc_kpi]), step=0.5)
        with kpi_col3:
            st.session_state.kpi_odr_dict[target_bc_kpi] = st.number_input(f"KPI Ontime Giao TTS (ODR) ({target_bc_kpi})", min_value=0.0, max_value=100.0, value=float(st.session_state.kpi_odr_dict[target_bc_kpi]), step=0.5)

    t3_col1, t3_col2 = st.columns(2)
    with t3_col1:
        date_range_kpi = st.date_input("Chọn thời gian", [df_vanhanh['Ngày'].min(), df_vanhanh['Ngày'].max()], key="date_kpi")
    with t3_col2:
        buu_cuc_kpi = st.selectbox("Chọn Bưu cục để XEM số liệu", ["Tất cả"] + list(df_vanhanh['Bưu Cục'].unique()), key="bc_kpi")

    mask_kpi = pd.Series(True, index=df_vanhanh.index)
    if len(date_range_kpi) == 2:
        mask_kpi &= (df_vanhanh['Ngày'] >= pd.to_datetime(date_range_kpi[0])) & (df_vanhanh['Ngày'] <= pd.to_datetime(date_range_kpi[1]))
    if buu_cuc_kpi != "Tất cả":
        mask_kpi &= (df_vanhanh['Bưu Cục'] == buu_cuc_kpi)
    df_kpi_filtered = df_vanhanh[mask_kpi].copy()

    actual_gtc = df_kpi_filtered['GTC'].mean() if not df_kpi_filtered.empty else 0
    actual_tts = df_kpi_filtered['GTC_TTS'].mean() if not df_kpi_filtered.empty else 0
    actual_odr = df_kpi_filtered['ODR'].mean() if not df_kpi_filtered.empty else 0
    
    current_kpi_gtc = st.session_state.kpi_gtc_dict.get(buu_cuc_kpi, 90.0)
    current_kpi_tts = st.session_state.kpi_tts_dict.get(buu_cuc_kpi, 85.0)
    current_kpi_odr = st.session_state.kpi_odr_dict.get(buu_cuc_kpi, 5.0)

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
        st.plotly_chart(create_gauge("Tỷ lệ GTC Chung (%)", actual_gtc, current_kpi_gtc), use_container_width=True)
    with gauge_col2:
        st.plotly_chart(create_gauge("Tỷ lệ GTC TikTokShop (%)", actual_tts, current_kpi_tts), use_container_width=True)
    with gauge_col3:
        st.plotly_chart(create_gauge("Ontime Giao TTS ODR (%)", actual_odr, current_kpi_odr, inverse_color=True), use_container_width=True)

    st.markdown("**BẢNG THEO DÕI HOÀN THÀNH KPI THEO NGÀY**")
    df_kpi_table = df_kpi_filtered.groupby('Ngày').agg({'GTC':'mean', 'GTC_TTS':'mean', 'ODR':'mean'}).reset_index()
    df_kpi_table['Ngày'] = df_kpi_table['Ngày'].dt.strftime('%d-%m-%Y')
    df_kpi_table['% Đạt KPI GTC'] = (df_kpi_table['GTC'] / current_kpi_gtc) * 100 if current_kpi_gtc > 0 else 0
    st.dataframe(df_kpi_table.style.format({"GTC": "{:.2f}%", "GTC_TTS": "{:.2f}%", "ODR": "{:.2f}%", "% Đạt KPI GTC": "{:.1f}%"}), use_container_width=True)

    if st.button("🔍 AI Đánh giá mức độ đạt KPI", type="primary", key="btn_ai_kpi"):
        with st.spinner("🔄 AI đang đối chiếu số liệu với mục tiêu KPI..."):
            prompt_kpi = f"""
            Khu vực ({buu_cuc_kpi}) - Mục tiêu: GTC > {current_kpi_gtc}%, GTC TikTok > {current_kpi_tts}%, Tồn kho < {current_kpi_odr}%.
            Thực tế: GTC: {actual_gtc:.2f}%, GTC TikTok: {actual_tts:.2f}%, Tồn kho: {actual_odr:.2f}%.
            Đóng vai Giám đốc kiểm soát. Đưa ra: 1. Đánh giá nhanh việc đạt/trượt KPI, 2. Cảnh báo nghiêm trọng nếu trượt, 3. Yêu cầu hành động khẩn.
            """
            st.session_state.ai_kpi_result = get_ai_analysis(prompt_kpi)
    render_ai_and_telegram(st.session_state.ai_kpi_result, "KPI Vận Hành", "kpi")


# ----------------- TAB 4: KINH DOANH -----------------
with tab4:
    styled_header("BÁO CÁO DOANH THU & KHÁCH HÀNG MỚI", "💰")
    
    with st.expander("⚙️ ĐIỀU CHỈNH KPI DOANH THU (Sẽ tự động lưu lại theo từng Khu vực/Bưu cục)", expanded=True):
        target_bc_kd = st.selectbox("✏️ Chọn khu vực muốn cài đặt KPI Doanh Thu:", ["Tất cả"] + list(df_kinhdoanh['Bưu Cục'].unique()), key="set_bc_kd_tab4")
        
        if target_bc_kd not in st.session_state.kpi_dt_dict: st.session_state.kpi_dt_dict[target_bc_kd] = 30000000.0
        
        st.session_state.kpi_dt_dict[target_bc_kd] = st.number_input(f"Mục tiêu Doanh thu VNĐ/Ngày ({target_bc_kd})", min_value=0.0, value=float(st.session_state.kpi_dt_dict[target_bc_kd]), step=1000000.0)
    
    t4_col1, t4_col2, t4_col3 = st.columns(3)
    with t4_col1:
        date_range_kd = st.date_input("Chọn thời gian", [df_kinhdoanh['Ngày'].max() - timedelta(days=7), df_kinhdoanh['Ngày'].max()], key="date_kd")
    with t4_col2:
        buu_cuc_kd = st.selectbox("Chọn Bưu cục để XEM số liệu", ["Tất cả"] + list(df_kinhdoanh['Bưu Cục'].unique()), key="bc_kd")
    with t4_col3:
        view_type = st.selectbox("Góc nhìn báo cáo", ["Theo Ngày", "Theo Tuần", "Theo Tháng"], key="view_kd")

    current_date = df_kinhdoanh['Ngày'].max()
    if len(date_range_kd) == 2:
        current_date = pd.to_datetime(date_range_kd[1])
        
    mask_kd = pd.Series(True, index=df_kinhdoanh.index)
    if buu_cuc_kd != "Tất cả":
        mask_kd &= (df_kinhdoanh['Bưu Cục'] == buu_cuc_kd)
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

    kpi_dt_val = st.session_state.kpi_dt_dict.get(buu_cuc_kd, 30000000.0)
    
    if view_type == "Theo Tuần": kpi_dt_val = kpi_dt_val * 7
    if view_type == "Theo Tháng": kpi_dt_val = kpi_dt_val * 30

    st.markdown(f"**Hiệu suất Doanh thu ({view_type})**")
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
        fig_rev = px.bar(df_plot_kd_grouped, x='Ngày', y='Doanh Thu', title=f"Biểu đồ Doanh Thu & KPI ({buu_cuc_kd})", color_discrete_sequence=['#28a745'])
        fig_rev.add_hline(y=kpi_dt_val, line_dash="dash", line_color="red", annotation_text="KPI Mục Tiêu")
        fig_rev.update_layout(plot_bgcolor='rgba(240, 248, 255, 0.5)')
        st.plotly_chart(fig_rev, use_container_width=True)

    with chart_kd2:
        total_lh = df_plot_kd_grouped['Khách Liên Hệ'].sum()
        total_ld = df_plot_kd_grouped['Khách Lên Đơn'].sum()
        total_rev_new = df_plot_kd_grouped['Doanh Thu KH Mới'].sum()
        fig_funnel = go.Figure(go.Funnel(
            y=["Khách Liên Hệ", "Khách Lên Đơn (Chuyển đổi)"],
            x=[total_lh, total_ld], textinfo="value+percent initial"
        ))
        fig_funnel.update_layout(title=f"Phễu chuyển đổi KH Mới ({view_type})")
        st.plotly_chart(fig_funnel, use_container_width=True)

    if st.button("🔍 AI Cố vấn Kinh Doanh & Sales", type="primary", key="btn_ai_kd"):
        with st.spinner("🔄 AI đang phân tích hiệu suất Kinh Doanh..."):
            prompt_kd = f"""
            Khu vực: {buu_cuc_kd}. Chế độ xem: {view_type}
            Phân tích Kinh doanh: KPI: {kpi_dt_val:,.0f}. Thực tế: {rev_n:,.0f}. So với kỳ trước: {rev_prev:,.0f}. Phễu KH: {total_lh} liên hệ -> {total_ld} lên đơn.
            Nhiệm vụ: Đóng vai Giám đốc Kinh doanh. Hãy phân tích 3 phần: 1. Lời khen/Cảnh báo việc chạy số, 2. Đánh giá tỷ lệ chốt sale, 3. Đề xuất chiến lược khẩn cấp.
            """
            st.session_state.ai_kd_result = get_ai_analysis(prompt_kd)
    render_ai_and_telegram(st.session_state.ai_kd_result, "Kinh Doanh", "kd")
