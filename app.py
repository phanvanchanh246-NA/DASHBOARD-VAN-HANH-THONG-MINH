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
# 0. CẤU HÌNH API KEY (BẢO MẬT QUA BIẾN MÔI TRƯỜNG - AN TOÀN CHO GITHUB)
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
# DỮ LIỆU GIẢ LẬP CHO TAB KINH DOANH (BỔ SUNG THÊM)
# ==========================================
@st.cache_data
def get_mock_business_data():
    dates = pd.date_range(start=datetime.now() - timedelta(days=60), end=datetime.now())
    hubs = ["BC Quận 1", "BC Quận 3", "BC Tân Bình", "BC Gò Vấp", "BC Thủ Đức"]
    data = []
    for d in dates:
        for h in hubs:
            kh_lien_he = np.random.randint(10, 50)
            kh_len_don = int(kh_lien_he * np.random.uniform(0.3, 0.8))
            data.append({
                "Ngày": d,
                "Bưu Cục": h,
                "Doanh Thu": np.random.randint(10000000, 50000000), # 10M - 50M
                "Khách Liên Hệ": kh_lien_he,
                "Khách Lên Đơn": kh_len_don,
                "Doanh Thu KH Mới": kh_len_don * np.random.randint(50000, 200000)
            })
    return pd.DataFrame(data)

df_kinhdoanh = get_mock_business_data()

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
# 3. GIAO DIỆN CHÍNH & TRỢ LÝ AI (TỰ ĐỘNG 100%)
# ==========================================
st.markdown("""
    <div class="banner">
        <div>
            <h1 style="color: white; margin-bottom: 0;">DASHBOARD QUẢN LÝ TỔNG THỂ GHN</h1>
            <p style="font-size: 16px; opacity: 0.9;">Vận Hành - Năng Suất - KPI - Kinh Doanh | AI Tự động phân tích</p>
        </div>
    </div>
""", unsafe_allow_html=True)

st.markdown("### 🤖 TRỢ LÝ AI PHÂN TÍCH RỦI RO CHUNG")

if st.button("🔄 Làm mới dữ liệu thủ công", use_container_width=False):
    st.cache_data.clear()
    st.rerun()

# HÀM TỰ ĐỘNG GỌI AI VÀ LƯU BỘ NHỚ ĐỆM 60 GIÂY
@st.cache_data(ttl=60, show_spinner=False)
def auto_run_ai_analysis(tong_don_val, gtc_tb_val, odr_tb_val, ns_hcm_val):
    if not GEMINI_API_KEY or GEMINI_API_KEY == "ĐIỀN_API_KEY_GEMINI_CỦA_BẠN_VÀO_ĐÂY":
        return "⚠️ **CHƯA CẤU HÌNH API KEY:** Vui lòng thêm biến môi trường GEMINI_API_KEY trên Render."
    
    try:
        genai.configure(api_key=GEMINI_API_KEY.strip())
        model = genai.GenerativeModel('gemini-3.6-flash') 
        
        prompt = f"""
        Dữ liệu vận hành hôm nay: 
        - Tổng đơn: {tong_don_val}
        - Tỷ lệ GTC: {gtc_tb_val:.2f}%
        - Ontime Giao TTS: {odr_tb_val:.2f}%
        - Sản lượng bưu cục: \n{ns_hcm_val}
        
        Nhiệm vụ: Đóng vai Giám đốc vận hành. Hãy phân tích CHUYÊN SÂU.
        Yêu cầu BẮT BUỘC: 
        - Viết 100% bằng Tiếng Việt chuẩn, có dấu đầy đủ, câu văn mạch lạc.
        - Tuyệt đối không được bỏ dở câu.
        - Bố cục 3 phần rõ ràng:
        1. 📊 Đánh giá tổng quan
        2. ⚠️ Phân tích Rủi ro 
        3. 💡 Đề xuất hành động
        """
        
        detailed_config = genai.types.GenerationConfig(max_output_tokens=2048, temperature=0.4)
        response = model.generate_content(prompt, generation_config=detailed_config)
        return response.text
    except Exception as e:
        return f"❌ Lỗi từ máy chủ Google AI: {e}"

tong_don = df_vanhanh['Volume'].sum()
gtc_tb = df_vanhanh['GTC'].mean()
odr_tb = df_vanhanh['ODR'].mean()
ns_hcm = df_nhansu.groupby('Bưu Cục')['Số Đơn'].sum().to_string()

with st.spinner("🔄 AI đang tự động phân tích dữ liệu mới nhất..."):
    ai_result = auto_run_ai_analysis(tong_don, gtc_tb, odr_tb, ns_hcm)

st.session_state.ai_response = ai_result
st.markdown(f'<div class="ai-warning"><b>🤖 Báo cáo tự động từ AI:</b><br><br>{ai_result}</div>', unsafe_allow_html=True)

if st.button("📤 Bắn báo cáo này lên nhóm Telegram", key="btn_tele_main"):
    if not TELEGRAM_TOKEN or TELEGRAM_TOKEN == "ĐIỀN_TOKEN_BOT_TELEGRAM_VÀO_ĐÂY":
        st.warning("Bạn chưa cấu hình TELEGRAM_TOKEN trên máy chủ Render!")
    else:
        try:
            clean_text = st.session_state.ai_response.replace('**', '').replace('*', '')
            message = f"🚨 BÁO CÁO VẬN HÀNH TỪ AI 🚨\n\n{clean_text}"
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
            req = requests.post(url, json=payload)
            if req.status_code == 200:
                st.success("✅ Đã bắn báo cáo thành công lên nhóm Telegram!")
            else:
                st.error(f"❌ Lỗi khi gửi Telegram (Mã lỗi {req.status_code})")
        except Exception as e:
            st.error(f"Lỗi mạng khi kết nối Telegram: {e}")
st.divider()

# ==========================================
# 4. GIAO DIỆN CÁC TAB BIỂU ĐỒ (ĐÃ BỔ SUNG TAB 3 VÀ TAB 4)
# ==========================================
tab1, tab2, tab3, tab4 = st.tabs(["🚚 VẬN HÀNH CHI TIẾT", "👥 NĂNG SUẤT & LƯƠNG", "🎯 VẬN HÀNH THEO KPI", "💰 KINH DOANH"])

# ----------------- TAB 1: VẬN HÀNH (GIỮ NGUYÊN) -----------------
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


# ----------------- TAB 2: NĂNG SUẤT & LƯƠNG (GIỮ NGUYÊN) -----------------
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


# ----------------- TAB 3: BÁO CÁO VẬN HÀNH THEO KPI (MỚI BỔ SUNG) -----------------
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

    # Bộ lọc Tab 3
    t3_col1, t3_col2 = st.columns(2)
    with t3_col1:
        date_range_kpi = st.date_input("Chọn thời gian", [df_vanhanh['Ngày'].min(), df_vanhanh['Ngày'].max()], key="date_kpi")
    with t3_col2:
        buu_cuc_kpi = st.selectbox("Chọn Bưu cục", ["Tất cả"] + list(df_vanhanh['Bưu Cục'].unique()), key="bc_kpi")

    # Lọc dữ liệu
    mask_kpi = pd.Series(True, index=df_vanhanh.index)
    if len(date_range_kpi) == 2:
        mask_kpi &= (df_vanhanh['Ngày'].dt.date >= date_range_kpi[0]) & (df_vanhanh['Ngày'].dt.date <= date_range_kpi[1])
    if buu_cuc_kpi != "Tất cả":
        mask_kpi &= (df_vanhanh['Bưu Cục'] == buu_cuc_kpi)
    df_kpi_filtered = df_vanhanh[mask_kpi].copy()

    # Tính toán thực tế
    actual_gtc = df_kpi_filtered['GTC'].mean() if not df_kpi_filtered.empty else 0
    actual_tts = df_kpi_filtered['GTC_TTS'].mean() if not df_kpi_filtered.empty else 0
    actual_odr = df_kpi_filtered['ODR'].mean() if not df_kpi_filtered.empty else 0
    
    # Vẽ đồng hồ Gauge
    gauge_col1, gauge_col2, gauge_col3 = st.columns(3)
    
    def create_gauge(title, value, target, inverse_color=False):
        # Inverse_color = True dùng cho ODR (Càng thấp càng tốt)
        color = "green" if (value >= target and not inverse_color) or (value <= target and inverse_color) else "red"
        fig = go.Figure(go.Indicator(
            mode = "gauge+number+delta",
            value = value,
            domain = {'x': [0, 1], 'y': [0, 1]},
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

    # Bảng số liệu chi tiết
    st.markdown("**BẢNG THEO DÕI HOÀN THÀNH KPI THEO NGÀY**")
    df_kpi_table = df_kpi_filtered.groupby('Ngày').agg({'GTC':'mean', 'GTC_TTS':'mean', 'ODR':'mean'}).reset_index()
    df_kpi_table['Ngày'] = df_kpi_table['Ngày'].dt.strftime('%d-%m-%Y')
    df_kpi_table['% Đạt KPI GTC'] = (df_kpi_table['GTC'] / kpi_gtc_target) * 100
    st.dataframe(df_kpi_table.style.format({"GTC": "{:.2f}%", "GTC_TTS": "{:.2f}%", "ODR": "{:.2f}%", "% Đạt KPI GTC": "{:.1f}%"}), use_container_width=True)

    # AI Cảnh báo riêng cho KPI
    if st.button("🔍 AI Đánh giá mức độ đạt KPI", key="ai_btn_kpi"):
        with st.spinner("AI đang đối chiếu số liệu với mục tiêu KPI..."):
            prompt_kpi = f"""
            Đóng vai trò Giám đốc kiểm soát vận hành. 
            Mục tiêu đề ra: GTC > {kpi_gtc_target}%, GTC TikTok > {kpi_tts_target}%, Tồn kho < {kpi_odr_target}%.
            Thực tế đạt được: GTC: {actual_gtc:.2f}%, GTC TikTok: {actual_tts:.2f}%, Tồn kho: {actual_odr:.2f}%.
            Khu vực đang xem: {buu_cuc_kpi}.
            
            Hãy đưa ra: 
            1. Đánh giá nhanh việc đạt/trượt KPI.
            2. Cảnh báo mức độ nghiêm trọng nếu trượt.
            3. Yêu cầu hành động khẩn cấp cho Quản lý bưu cục.
            Viết bằng tiếng Việt chuyên nghiệp, súc tích, dùng emoji.
            """
            try:
                model = genai.GenerativeModel('gemini-3.6-flash')
                response_kpi = model.generate_content(prompt_kpi)
                st.markdown(f'<div class="ai-warning">{response_kpi.text}</div>', unsafe_allow_html=True)
            except Exception as e:
                st.error(f"Lỗi AI: {e}")


# ----------------- TAB 4: KINH DOANH (MỚI BỔ SUNG) -----------------
with tab4:
    styled_header("BÁO CÁO DOANH THU & KHÁCH HÀNG MỚI", "💰")
    
    with st.expander("⚙️ ĐIỀU CHỈNH KPI DOANH THU", expanded=True):
        kpi_dt_target = st.number_input("Mục tiêu Doanh thu (VNĐ / Ngày)", min_value=0, value=30000000, step=1000000, key="kpi_dt")
    
    # Bộ lọc Tab 4
    t4_col1, t4_col2, t4_col3 = st.columns(3)
    with t4_col1:
        date_range_kd = st.date_input("Chọn thời gian", [df_kinhdoanh['Ngày'].max() - timedelta(days=7), df_kinhdoanh['Ngày'].max()], key="date_kd")
    with t4_col2:
        buu_cuc_kd = st.selectbox("Chọn Bưu cục", ["Tất cả"] + list(df_kinhdoanh['Bưu Cục'].unique()), key="bc_kd")
    with t4_col3:
        view_type = st.selectbox("Góc nhìn báo cáo", ["Theo Ngày", "Theo Tuần", "Theo Tháng"], key="view_kd")

    # Xử lý ngày hiện tại để so sánh N-1, W-1
    current_date = df_kinhdoanh['Ngày'].max()
    if len(date_range_kd) == 2:
        current_date = pd.to_datetime(date_range_kd[1])
        
    mask_kd = pd.Series(True, index=df_kinhdoanh.index)
    if buu_cuc_kd != "Tất cả":
        mask_kd &= (df_kinhdoanh['Bưu Cục'] == buu_cuc_kd)
    
    # Tính toán so sánh (Metric)
    df_filtered_kd = df_kinhdoanh[mask_kd]
    
    # Số liệu Hôm nay (N)
    rev_n = df_filtered_kd[df_filtered_kd['Ngày'] == current_date]['Doanh Thu'].sum()
    # Số liệu N-1
    rev_n1 = df_filtered_kd[df_filtered_kd['Ngày'] == (current_date - timedelta(days=1))]['Doanh Thu'].sum()
    # Số liệu W-1
    rev_w1 = df_filtered_kd[df_filtered_kd['Ngày'] == (current_date - timedelta(days=7))]['Doanh Thu'].sum()
    # Số liệu M-1
    rev_m1 = df_filtered_kd[df_filtered_kd['Ngày'] == (current_date - timedelta(days=30))]['Doanh Thu'].sum()

    st.markdown(f"**Hiệu suất Doanh thu ngày {current_date.strftime('%d-%m-%Y')}**")
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    m_col1.metric("Doanh Thu Hiện Tại (N)", f"{rev_n:,.0f} đ", f"{(rev_n - kpi_dt_target)/kpi_dt_target*100:.1f}% vs KPI")
    m_col2.metric("So với N-1 (Hôm qua)", f"{rev_n1:,.0f} đ", f"{rev_n - rev_n1:,.0f} đ")
    m_col3.metric("So với W-1 (Tuần trước)", f"{rev_w1:,.0f} đ", f"{rev_n - rev_w1:,.0f} đ")
    m_col4.metric("So với M-1 (Tháng trước)", f"{rev_m1:,.0f} đ", f"{rev_n - rev_m1:,.0f} đ")
    
    # Lọc data theo Range cho biểu đồ
    mask_kd_range = mask_kd.copy()
    if len(date_range_kd) == 2:
        mask_kd_range &= (df_kinhdoanh['Ngày'].dt.date >= date_range_kd[0]) & (df_kinhdoanh['Ngày'].dt.date <= date_range_kd[1])
    
    df_plot_kd = df_kinhdoanh[mask_kd_range].groupby('Ngày').agg({
        'Doanh Thu': 'sum', 'Khách Liên Hệ': 'sum', 'Khách Lên Đơn': 'sum', 'Doanh Thu KH Mới': 'sum'
    }).reset_index()

    chart_kd1, chart_kd2 = st.columns(2)
    
    with chart_kd1:
        # Biểu đồ Doanh thu kết hợp đường KPI
        fig_rev = px.bar(df_plot_kd, x='Ngày', y='Doanh Thu', title="Biểu đồ Doanh Thu & KPI", color_discrete_sequence=['#28a745'])
        fig_rev.add_hline(y=kpi_dt_target, line_dash="dash", line_color="red", annotation_text="KPI Mục Tiêu")
        fig_rev.update_layout(plot_bgcolor='rgba(240, 248, 255, 0.5)')
        st.plotly_chart(fig_rev, use_container_width=True)

    with chart_kd2:
        # Biểu đồ phễu Khách hàng mới
        total_lh = df_plot_kd['Khách Liên Hệ'].sum()
        total_ld = df_plot_kd['Khách Lên Đơn'].sum()
        total_rev_new = df_plot_kd['Doanh Thu KH Mới'].sum()
        
        fig_funnel = go.Figure(go.Funnel(
            y=["Khách Liên Hệ", "Khách Lên Đơn (Chuyển đổi)"],
            x=[total_lh, total_ld],
            textinfo="value+percent initial"
        ))
        fig_funnel.update_layout(title=f"Phễu chuyển đổi KH Mới (Tổng DT: {total_rev_new:,.0f} đ)")
        st.plotly_chart(fig_funnel, use_container_width=True)

    # AI Cảnh báo Kinh doanh
    if st.button("🔍 AI Cố vấn Kinh Doanh & Sales", key="ai_btn_kd"):
        with st.spinner("AI đang phân tích hiệu suất Sales..."):
            prompt_kd = f"""
            Đóng vai trò Giám đốc Kinh Doanh. 
            Phân tích số liệu ngày {current_date.strftime('%d-%m-%Y')}:
            - KPI Doanh thu ngày: {kpi_dt_target:,.0f}
            - Thực tế đạt (N): {rev_n:,.0f}
            - So với hôm qua (N-1): {rev_n1:,.0f}
            - Phễu Khách Mới (trong giai đoạn lọc): {total_lh} liên hệ -> {total_ld} lên đơn. Mang về {total_rev_new:,.0f} đ.
            
            Hãy đưa ra:
            1. Lời khen hoặc Cảnh báo đanh thép về việc chạy số doanh thu so với KPI.
            2. Nhận xét tỷ lệ chốt sale khách hàng mới.
            3. Đề xuất chiến lược Sales (gọi điện, chăm sóc lại khách cũ, đẩy mạnh sale khách mới) ngay lập tức.
            Viết ngắn gọn, có gạch đầu dòng, dùng emoji.
            """
            try:
                model = genai.GenerativeModel('gemini-3.6-flash')
                response_kd = model.generate_content(prompt_kd)
                st.markdown(f'<div class="ai-warning">{response_kd.text}</div>', unsafe_allow_html=True)
            except Exception as e:
                st.error(f"Lỗi AI: {e}")
