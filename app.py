import os
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import google.generativeai as genai
import requests
from datetime import datetime

# ==========================================
# 0. CẤU HÌNH API KEY (BẢO MẬT QUA BIẾN MÔI TRƯỜNG - AN TOÀN CHO GITHUB)
# ==========================================
# Mã sẽ được lấy tự động từ cài đặt Environment Variables trên máy chủ Render.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "ĐIỀN_API_KEY_GEMINI_CỦA_BẠN_VÀO_ĐÂY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "ĐIỀN_TOKEN_BOT_TELEGRAM_VÀO_ĐÂY") 
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "ĐIỀN_CHAT_ID_NHÓM_VÀO_ĐÂY")

# ==========================================
# 1. CẤU HÌNH TRANG & GIAO DIỆN CHUNG (CSS)
# ==========================================
st.set_page_config(page_title="Dashboard Vận Hành & Năng Suất", layout="wide", page_icon="📈")

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
# 2. LẤY DỮ LIỆU TỪ GOOGLE SHEETS
# ==========================================
@st.cache_data(ttl=60) 
def get_real_data():
    url_vanhanh = "https://docs.google.com/spreadsheets/d/1lJt4ZXVjIPoUYZF73nsPmVfziJSBXBISUWU1ldSxWH4/export?format=csv&gid=501687087"
    url_nhansu = "https://docs.google.com/spreadsheets/d/1OemA7cIZM-5AAvsnQuQphNArKw43de27W75Z-Ri6BcQ/export?format=csv&gid=2000227799"
    
    try:
        df_vh = pd.read_csv(url_vanhanh)
        df_ns = pd.read_csv(url_nhansu)
        
        df_vh.columns = df_vh.columns.str.strip()
        df_ns.columns = df_ns.columns.str.strip()
        
        if 'Ngày' not in df_vh.columns:
            st.error("🚨 Không đọc được dữ liệu. Vui lòng kiểm tra quyền chia sẻ 'Bất kỳ ai có đường liên kết'!")
            st.stop()
            
        df_vh['Ngày'] = pd.to_datetime(df_vh['Ngày'])
        df_ns['Ngày'] = pd.to_datetime(df_ns['Ngày'])
        
        df_vh = df_vh.fillna(0)
        df_ns = df_ns.fillna(0)
        df_vh['Bưu Cục'] = df_vh['Bưu Cục'].astype(str)
        df_ns['Bưu Cục'] = df_ns['Bưu Cục'].astype(str)
        df_ns['Nhân Viên'] = df_ns['Nhân Viên'].astype(str)
        df_ns['Loại Hàng'] = df_ns['Loại Hàng'].astype(str)
        
        return df_vh, df_ns
        
    except Exception as e:
        st.error(f"🚨 Lỗi kết nối Google Sheets: {e}")
        st.stop()

df_vanhanh, df_nhansu = get_real_data()

# ==========================================
# 3. GIAO DIỆN CHÍNH & TRỢ LÝ AI
# ==========================================
st.markdown("""
    <div class="banner">
        <div>
            <h1 style="color: white; margin-bottom: 0;">DASHBOARD QUẢN LÝ VẬN HÀNH THÔNG MINH</h1>
            <p style="font-size: 16px; opacity: 0.9;">Tích hợp AI Gemini Pro phân tích - Dữ liệu thời gian thực</p>
        </div>
    </div>
""", unsafe_allow_html=True)

st.markdown("### 🤖 TRỢ LÝ AI PHÂN TÍCH RỦI RO & ĐỒNG BỘ DỮ LIỆU")
col_btn1, col_btn2, _ = st.columns([2, 2, 4])

with col_btn1:
    analyze_button = st.button("🔍 Nhờ AI Phân tích ngay", type="primary", use_container_width=True)

with col_btn2:
    if st.button("🔄 Làm mới dữ liệu ngay", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

ai_placeholder = st.empty()

if "ai_response" not in st.session_state:
    st.session_state.ai_response = "Bấm nút **'🔍 Nhờ AI Phân tích ngay'** để AI Gemini Pro bắt đầu quét dữ liệu vận hành..."

ai_placeholder.markdown(f'<div class="ai-warning">{st.session_state.ai_response}</div>', unsafe_allow_html=True)

# XỬ LÝ KHI BẤM NÚT PHÂN TÍCH AI (KHỞI TẠO AI TRỰC TIẾP TẠI ĐÂY)
if analyze_button:
    # Tối ưu logic: Kiểm tra nếu biến bị None, rỗng, hoặc là chuỗi mặc định
    if not GEMINI_API_KEY or GEMINI_API_KEY == "ĐIỀN_API_KEY_GEMINI_CỦA_BẠN_VÀO_ĐÂY":
        ai_placeholder.markdown("""
        <div class="ai-warning" style="color:#d9534f; background-color:#f2dede; border-left: 5px solid #d9534f;">
            <b>⚠️ CHƯA CẤU HÌNH API KEY:</b><br>
            Bạn chưa cấu hình GEMINI_API_KEY trên máy chủ Render.<br>
            <i>Vui lòng vào tab Environment Variables trên Render để điền mã của bạn!</i>
        </div>
        """, unsafe_allow_html=True)
    else:
        ai_placeholder.markdown('<div class="ai-warning">🔄 AI đang kết nối và đọc dữ liệu...</div>', unsafe_allow_html=True)
        try:
            # 1. CHỈ GỌI KẾT NỐI KHI BẤM NÚT -> CHỐNG LỖI NONETYPE
            genai.configure(api_key=GEMINI_API_KEY)
            
            # Bạn có thể dùng 'gemini-3.1-pro' hoặc 'gemini-3.6-flash' tùy nhu cầu tốc độ
            model = genai.GenerativeModel('gemini-3.6-flash') 
            
            # 2. Xử lý số liệu
            tong_don = df_vanhanh['Volume'].sum()
            gtc_tb = df_vanhanh['GTC'].mean()
            odr_tb = df_vanhanh['ODR'].mean()
            ns_hcm = df_nhansu.groupby('Bưu Cục')['Số Đơn'].sum().to_string()
            
            prompt = f"""
            Dữ liệu vận hành hôm nay: 
            - Tổng đơn: {tong_don}
            - Tỷ lệ GTC trung bình: {gtc_tb:.2f}%
            - Tỷ lệ Tồn kho (ODR): {odr_tb:.2f}%
            - Sản lượng theo Bưu cục: {ns_hcm}
            
            Nhiệm vụ: Đóng vai chuyên gia Logistics. Hãy đưa ra cảnh báo rủi ro vận hành và đề xuất giải pháp.
            Yêu cầu: Viết đúng 3 gạch đầu dòng ngắn gọn, súc tích. Dùng biểu tượng emoji phù hợp.
            """
            
            fast_config = genai.types.GenerationConfig(
                max_output_tokens=150,
                temperature=0.2,
            )
            
            # 3. Gửi yêu cầu lên Google
            response = model.generate_content(prompt, generation_config=fast_config, stream=True)
            
            full_response = ""
            for chunk in response:
                chunk_text = chunk.text if hasattr(chunk, 'text') else str(chunk)
                full_response += chunk_text
                ai_placeholder.markdown(f'<div class="ai-warning"><b>🤖 AI Gemini Pro đang phân tích:</b><br>{full_response} ▌</div>', unsafe_allow_html=True)
                
            ai_placeholder.markdown(f'<div class="ai-warning"><b>🤖 AI Gemini Pro Cảnh Báo:</b><br>{full_response}</div>', unsafe_allow_html=True)
            st.session_state.ai_response = f"<b>🤖 AI Gemini Pro Cảnh Báo:</b><br>{full_response}"
            
        except Exception as e:
            error_msg = f"❌ Lỗi kết nối Google AI: Vui lòng kiểm tra lại API Key hoặc đảm bảo máy tính có kết nối mạng ổn định. (Chi tiết: {e})"
            ai_placeholder.markdown(f'<div class="ai-warning" style="color:red;">{error_msg}</div>', unsafe_allow_html=True)

# NÚT BẮN TELEGRAM
if st.button("📤 Bắn báo cáo này lên nhóm Telegram"):
    if TELEGRAM_TOKEN == "ĐIỀN_TOKEN_BOT_TELEGRAM_VÀO_ĐÂY":
        st.warning("Bạn chưa cấu hình TELEGRAM_TOKEN trên máy chủ Render!")
    else:
        try:
            clean_text = st.session_state.ai_response.replace('<b>', '').replace('</b>', '').replace('<br>', '\n')
            message = f"🚨 BÁO CÁO VẬN HÀNH TỪ AI 🚨\n\n{clean_text}"
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
            req = requests.post(url, json=payload)
            if req.status_code == 200:
                st.success("✅ Đã bắn báo cáo thành công lên nhóm Telegram!")
            else:
                st.error("❌ Lỗi khi gửi Telegram: Vui lòng kiểm tra Token/Chat ID.")
        except Exception as e:
            st.error(f"Lỗi mạng khi kết nối Telegram: {e}")

st.divider()

# ==========================================
# 4. GIAO DIỆN CÁC TAB BIỂU ĐỒ
# ==========================================
tab1, tab2 = st.tabs(["🚚 VẬN HÀNH CHI TIẾT", "👥 NĂNG SUẤT & LƯƠNG"])

# ----------------- TAB 1: VẬN HÀNH -----------------
with tab1:
    col1, col2 = st.columns(2)
    with col1:
        date_range_vh = st.date_input("Khoảng thời gian (Vận hành)", [df_vanhanh['Ngày'].min(), df_vanhanh['Ngày'].max()], key="date_vh")
    with col2:
        buu_cuc_vh = st.selectbox("Chọn Bưu cục", ["Tất cả"] + list(df_vanhanh['Bưu Cục'].unique()), key="bc_vh")
        
    mask_vh = pd.Series(True, index=df_vanhanh.index)
    if len(date_range_vh) == 2:
        mask_vh &= (df_vanhanh['Ngày'].dt.date >= date_range_vh[0]) & (df_vanhanh['Ngày'].dt.date <= date_range_vh[1])
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
        mask_ns &= (df_nhansu['Ngày'].dt.date >= date_range_ns[0]) & (df_nhansu['Ngày'].dt.date <= date_range_ns[1])
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
