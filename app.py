"""
DASHBOARD QUẢN LÝ VẬN HÀNH & KINH DOANH GHN
Designed by AM Phan Van Chanh
Bản đã tối ưu: SDK Gemini mới, trung bình có trọng số, template Plotly dùng chung.

Biến môi trường cần cấu hình trên Render:
    GEMINI_API_KEY, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, APP_USER, APP_PASS
"""

import os
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import requests
import streamlit as st
from plotly.subplots import make_subplots

try:
    from google import genai
    from google.genai import types as genai_types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

# ==========================================
# 0. CẤU HÌNH TRANG (phải là lệnh Streamlit đầu tiên)
# ==========================================
st.set_page_config(
    page_title="Dashboard Vận Hành & Kinh Doanh",
    layout="wide",
    page_icon="📈",
)

# ==========================================
# 1. BIẾN MÔI TRƯỜNG
# ==========================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
APP_USER = os.environ.get("APP_USER", "").strip()
APP_PASS = os.environ.get("APP_PASS", "").strip()

GEMINI_MODEL = "gemini-3.6-flash"
CACHE_TTL = 300  # 5 phút — đã có nút làm mới thủ công

# ==========================================
# 2. BỘ NHỚ PHIÊN
# ==========================================
_DEFAULT_STATE = {
    "authenticated": False,
    "kpi_gtc_dict": {"Tất cả": 70.0},
    "kpi_tts_dict": {"Tất cả": 80.0},
    "kpi_odr_dict": {"Tất cả": 98.0},
    "kpi_dt_dict": {"Tất cả": 71000000.0},
    "ai_vh_result": "Bấm nút '🔍 Nhờ AI Phân tích' để xem cố vấn chi tiết.",
    "ai_ns_result": "Bấm nút '🔍 Nhờ AI Phân tích' để xem cố vấn chi tiết.",
    "ai_kpi_result": "Bấm nút '🔍 Nhờ AI Phân tích' để xem cố vấn chi tiết.",
    "ai_kd_result": "Bấm nút '🔍 Cố vấn AI Kinh Doanh' để xem cố vấn chi tiết.",
    "ai_td_result": "Bấm nút '🔍 AI Đánh giá Chương trình Thi đua' để xem cố vấn chi tiết.",
    "chat_history": [],
}
for _k, _v in _DEFAULT_STATE.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ==========================================
# 3. BẢNG MÀU & TEMPLATE PLOTLY DÙNG CHUNG
# ==========================================
C_BLUE = "#007BFF"
C_ORANGE = "#FF8C00"
C_GREEN = "#28A745"
C_RED = "#FF3333"
C_TEAL = "#17A2B8"
C_GREY = "#6C757D"
C_INK = "#1F2937"

pio.templates["ghn"] = go.layout.Template(
    layout=dict(
        font=dict(family="Inter, Segoe UI, sans-serif", size=13, color="#374151"),
        title=dict(font=dict(family="Inter", size=18, color=C_INK), x=0.01),
        plot_bgcolor="#FFFFFF",
        paper_bgcolor="#FFFFFF",
        hovermode="x unified",
        colorway=[C_BLUE, C_ORANGE, C_GREEN, C_TEAL, C_RED, C_GREY],
        margin=dict(l=45, r=30, t=70, b=45),
        xaxis=dict(showgrid=False, linecolor="#E5E7EB", ticks="outside", tickcolor="#E5E7EB"),
        yaxis=dict(showgrid=True, gridcolor="#F1F3F5", zerolinecolor="#E5E7EB"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
)
pio.templates.default = "ghn"

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800;900&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }

    .banner {
        background: linear-gradient(135deg, #007BFF, #FF8C00);
        padding: 25px; border-radius: 12px; color: white;
        margin-bottom: 25px; display: flex; justify-content: space-between;
        align-items: center; border-bottom: 6px solid #28a745;
        box-shadow: 0px 4px 15px rgba(0,0,0,0.1);
    }
    .banner h1 { font-weight: 900 !important; text-transform: uppercase; letter-spacing: 1px; }

    .ai-warning {
        background-color: #ffffff; border-left: 6px solid #FF8C00;
        padding: 18px; border-radius: 8px; margin-bottom: 20px;
        font-size: 16px; line-height: 1.6;
        box-shadow: 0px 2px 8px rgba(0,0,0,0.05); color: #333333;
    }

    [data-testid="stMetricValue"] { font-weight: 900 !important; color: #007BFF !important; font-size: 2.0rem !important; }
    [data-testid="stMetricLabel"] { font-weight: 800 !important; font-size: 0.95rem !important; color: #555555 !important; }

    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] {
        font-weight: 900 !important; font-size: 17px !important; border: 2px solid #007BFF !important;
        border-radius: 8px 8px 0px 0px !important; padding: 13px 24px !important;
        background-color: #ffffff !important; color: #0056b3 !important;
        text-transform: uppercase; letter-spacing: 0.5px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #007BFF !important; color: white !important;
        border: 2px solid #007BFF !important; box-shadow: 0px -4px 10px rgba(0,123,255,0.3);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

TH_PROPS = [
    ("background-color", "#29B6F6"),
    ("color", "#ffffff"),
    ("font-weight", "900"),
    ("font-size", "15px"),
    ("text-align", "center"),
    ("text-transform", "uppercase"),
]
HEADER_STYLES = [dict(selector="th", props=TH_PROPS)]


# ==========================================
# 4. ĐĂNG NHẬP
# ==========================================
def check_login():
    st.markdown(
        "<h2 style='text-align:center;color:#007BFF;font-weight:900;'>🔐 HỆ THỐNG QUẢN TRỊ NỘI BỘ GHN</h2>",
        unsafe_allow_html=True,
    )
    if not APP_USER or not APP_PASS:
        st.error(
            "Chưa cấu hình tài khoản. Đặt biến môi trường APP_USER và APP_PASS trên máy chủ rồi khởi động lại app."
        )
        return
    with st.form("login_form"):
        st.write("Đăng nhập để xem báo cáo.")
        user_id = st.text_input("ID đăng nhập")
        password = st.text_input("Mật khẩu", type="password")
        if st.form_submit_button("Đăng nhập"):
            if user_id == APP_USER and password == APP_PASS:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("ID hoặc mật khẩu không đúng.")


if not st.session_state.authenticated:
    check_login()
    st.stop()

with st.sidebar:
    if st.button("🚪 Đăng xuất", use_container_width=True):
        st.session_state.authenticated = False
        st.rerun()
    st.divider()
    st.markdown("👨‍💻 **Tài khoản:** Quản trị viên GHN")
    st.markdown("🌐 **Khu vực:** Toàn quốc")
    st.caption(f"Model AI: `{GEMINI_MODEL}`")


# ==========================================
# 5. TIỆN ÍCH DÙNG CHUNG
# ==========================================
def styled_header(text, icon=""):
    st.markdown(
        f"""
        <div style="background:#ffffff;color:#0056b3;padding:15px 20px;border-radius:8px;
                    border-left:8px solid #007BFF;font-size:22px;font-weight:900;
                    margin-top:25px;margin-bottom:20px;box-shadow:0px 2px 5px rgba(0,0,0,0.05);
                    text-transform:uppercase;">
            {icon} {text}
        </div>
        """,
        unsafe_allow_html=True,
    )


def date_bounds(picked, fallback=None):
    """st.date_input trả về 1 phần tử khi người dùng mới chọn ngày đầu → luôn trả (start, end)."""
    fb = pd.to_datetime(fallback) if fallback is not None else pd.Timestamp.today().normalize()
    if picked is None:
        return fb, fb
    if isinstance(picked, (list, tuple)):
        if len(picked) >= 2:
            return pd.to_datetime(picked[0]), pd.to_datetime(picked[1])
        if len(picked) == 1:
            return pd.to_datetime(picked[0]), pd.to_datetime(picked[0])
        return fb, fb
    return pd.to_datetime(picked), pd.to_datetime(picked)


def safe_range(series, days_back=None):
    """Giá trị mặc định an toàn cho st.date_input kể cả khi dữ liệu rỗng."""
    today = pd.Timestamp.today().normalize()
    if series is None or len(series) == 0 or series.dropna().empty:
        return today - timedelta(days=7), today
    lo, hi = series.min(), series.max()
    if pd.isna(lo) or pd.isna(hi):
        return today - timedelta(days=7), today
    if days_back is not None:
        lo = max(lo, hi - timedelta(days=days_back))
    return lo, hi


def wavg(values, weights):
    """Trung bình có trọng số — dùng cho %GTC, %ODR, %Trả hàng (KHÔNG dùng mean thường)."""
    v = pd.to_numeric(values, errors="coerce")
    w = pd.to_numeric(weights, errors="coerce").fillna(0)
    m = v.notna() & (w > 0)
    total = w[m].sum()
    if total <= 0:
        return float(v.mean()) if v.notna().any() else 0.0
    return float((v[m] * w[m]).sum() / total)


OPS_RATE_COLS = [
    ("GTC", "Volume"),
    ("Trả Hàng", "Volume"),
    ("GTC_TTS", "Volume TTS"),
    ("ODR", "Volume TTS"),
]


def agg_ops(df, group_cols):
    """Gộp dữ liệu vận hành: sản lượng cộng dồn, tỷ lệ % lấy trung bình CÓ TRỌNG SỐ."""
    cols_out = list(group_cols) + ["Volume", "Volume TTS"] + [c for c, _ in OPS_RATE_COLS]
    if df is None or df.empty:
        return pd.DataFrame(columns=cols_out)

    d = df.copy()
    for col, wcol in OPS_RATE_COLS:
        if col not in d.columns:
            d[col] = np.nan
        if wcol not in d.columns:
            d[wcol] = 0.0
        v = pd.to_numeric(d[col], errors="coerce")
        w = pd.to_numeric(d[wcol], errors="coerce").fillna(0)
        d[f"_w_{col}"] = np.where(v.notna(), w, 0.0)
        d[f"_p_{col}"] = v.fillna(0) * d[f"_w_{col}"]

    agg_map = {"Volume": "sum", "Volume TTS": "sum"}
    for col, _ in OPS_RATE_COLS:
        agg_map[f"_p_{col}"] = "sum"
        agg_map[f"_w_{col}"] = "sum"

    g = d.groupby(group_cols, as_index=False).agg(agg_map)
    for col, _ in OPS_RATE_COLS:
        g[col] = np.where(g[f"_w_{col}"] > 0, g[f"_p_{col}"] / g[f"_w_{col}"], np.nan)
    drop = [c for c in g.columns if c.startswith("_p_") or c.startswith("_w_")]
    return g.drop(columns=drop)


def to_period(series, mode):
    if mode == "Theo Tuần":
        return series.dt.to_period("W").apply(lambda r: r.start_time)
    if mode == "Theo Tháng":
        return series.dt.to_period("M").apply(lambda r: r.start_time)
    return series


def month_end(ts):
    nxt = ts.replace(day=28) + timedelta(days=4)
    return nxt - timedelta(days=nxt.day)


def draw_combo_chart(df, x_col, bar_y, line_y, title, bar_name="Sản lượng", line_name="% GTC"):
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    if df is None or df.empty:
        fig.update_layout(title=f"<b>{title}</b>", annotations=[
            dict(text="Không có dữ liệu trong bộ lọc hiện tại", showarrow=False, font=dict(size=15, color=C_GREY))
        ])
        return fig
    fig.add_trace(
        go.Bar(x=df[x_col], y=df[bar_y], name=bar_name, marker_color=C_BLUE, opacity=0.85),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=df[x_col], y=df[line_y], name=line_name, mode="lines+markers",
            line=dict(color=C_ORANGE, width=4),
            marker=dict(size=10, color=C_ORANGE, line=dict(width=2, color="white")),
        ),
        secondary_y=True,
    )
    fig.update_layout(title=f"<b>{title}</b>")
    fig.update_yaxes(title_text=f"<b>{bar_name}</b>", secondary_y=False)
    fig.update_yaxes(title_text=f"<b>{line_name}</b>", secondary_y=True, showgrid=False, range=[0, 100])
    return fig


def draw_rate_line(df, x_col, y_col, title, color):
    if df is None or df.empty:
        fig = go.Figure()
        fig.update_layout(title=f"<b>{title}</b>", annotations=[
            dict(text="Không có dữ liệu trong bộ lọc hiện tại", showarrow=False, font=dict(size=15, color=C_GREY))
        ])
        return fig
    fig = px.line(df, x=x_col, y=y_col, markers=True, title=f"<b>{title}</b>")
    fig.update_traces(
        line=dict(color=color, width=4),
        marker=dict(size=10, color=color, line=dict(width=2, color="white")),
    )
    return fig


# ==========================================
# 6. ĐỌC DỮ LIỆU TỪ GOOGLE SHEETS
# ==========================================
def parse_vn_num(val):
    if pd.isna(val):
        return np.nan
    s = str(val).replace("%", "").replace("đ", "").replace("VNĐ", "").replace("₫", "").replace(" ", "").strip()
    if s in ["nan", "None", "", "-", "null", "#N/A", "#DIV/0!"]:
        return np.nan
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    elif "." in s:
        parts = s.split(".")
        if len(parts) > 2:
            s = s.replace(".", "")
        elif len(parts[1]) == 3 and parts[0] not in ("0", "-0", ""):
            s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return np.nan


def clean_dataframe_numbers(df, text_cols):
    for col in df.columns:
        if col not in text_cols:
            df[col] = df[col].apply(parse_vn_num)
    return df


def normalize_headers(df):
    df.columns = df.columns.astype(str).str.strip().str.replace("\xa0", " ")
    return df


def rescale_percent(df, cols):
    """Nếu sheet lưu 0.85 thay vì 85 thì nhân 100."""
    for col in cols:
        if col in df.columns:
            valid = df.loc[df[col] > 0, col].dropna()
            if not valid.empty and valid.max() <= 1.2:
                df[col] = df[col] * 100
    return df


VH_MAPPING = {
    "Thời Gian": "Ngày", "Thời gian": "Ngày", "ngày": "Ngày", "Ngày tạo": "Ngày",
    "Bưu cục": "Bưu Cục", "bưu cục": "Bưu Cục", "Khu vực": "Bưu Cục", "Trạm": "Bưu Cục",
    "%GTC": "GTC", "GTC (%)": "GTC", "Tỷ lệ GTC": "GTC", "% GTC": "GTC",
    "Trả hàng": "Trả Hàng", "Tỷ lệ trả hàng": "Trả Hàng", "% Trả hàng": "Trả Hàng",
    "Volume_TTS": "Volume TTS", "GTC TTS": "GTC_TTS", "%GTC_TTS": "GTC_TTS",
    "Tỷ lệ GTC TTS": "GTC_TTS", "% GTC TTS": "GTC_TTS",
    "Ontime Giao TTS": "ODR", "ODR (%)": "ODR", "Tỷ lệ ODR": "ODR", "% ODR": "ODR",
    "Ontime": "ODR", "Tỷ lệ Ontime": "ODR", "Tỉ lệ Ontime": "ODR",
    "Sản lượng": "Volume", "Sản Lượng": "Volume", "Tổng đơn": "Volume", "Tổng Đơn": "Volume",
    "Loại hàng": "Loại Hàng", "loại hàng": "Loại Hàng", "Phân loại": "Loại Hàng",
    "Ca làm việc": "Loại Hàng", "Ca": "Loại Hàng",
}

NS_MAPPING = {
    "Thời Gian": "Ngày", "Thời gian": "Ngày", "ngày": "Ngày",
    "Bưu cục": "Bưu Cục", "bưu cục": "Bưu Cục", "Khu vực": "Bưu Cục", "Trạm": "Bưu Cục",
    "Nhân viên": "Nhân Viên", "nhân viên": "Nhân Viên", "Tên nhân viên": "Nhân Viên",
    "Tên Nhân Viên": "Nhân Viên",
    "Loại hàng": "Loại Hàng", "loại hàng": "Loại Hàng",
    "GTC": "%GTC", "Tỷ lệ GTC": "%GTC", "% GTC": "%GTC",
    "Đơn giá": "Đơn Giá", "Số đơn": "Số Đơn",
}

GTC_MAPPING = {
    "Thời Gian": "Ngày", "Thời gian": "Ngày", "ngày": "Ngày",
    "Bưu cục": "Bưu Cục", "bưu cục": "Bưu Cục", "Khu vực": "Bưu Cục", "Trạm": "Bưu Cục",
    "Nhân viên": "Nhân Viên", "nhân viên": "Nhân Viên", "Tên nhân viên": "Nhân Viên",
    "Tên Nhân Viên": "Nhân Viên",
    "Loại hàng": "Loại Hàng", "loại hàng": "Loại Hàng", "Phân loại": "Loại Hàng",
    "Số đơn giao tính lương": "Đơn giao tính lương", "Đơn Giao Tính Lương": "Đơn giao tính lương",
    "Đơn giao": "Đơn giao tính lương", "Số đơn GTC": "Đơn giao tính lương", "Đơn GTC": "Đơn giao tính lương",
    "Số đơn gán giao": "Số đơn gán Giao", "Số đơn gán": "Số đơn gán Giao",
    "Số Đơn Gán Giao": "Số đơn gán Giao", "Đơn gán": "Số đơn gán Giao", "Số Đơn Gán": "Số đơn gán Giao",
}

URL_VH_TONGQUAN = "https://docs.google.com/spreadsheets/d/1lJt4ZXVjIPoUYZF73nsPmVfziJSBXBISUWU1ldSxWH4/export?format=csv&gid=1548015845"
URL_VH_CA = "https://docs.google.com/spreadsheets/d/1lJt4ZXVjIPoUYZF73nsPmVfziJSBXBISUWU1ldSxWH4/export?format=csv&gid=501687087"
URL_NHANSU = "https://docs.google.com/spreadsheets/d/1OemA7cIZM-5AAvsnQuQphNArKw43de27W75Z-Ri6BcQ/export?format=csv&gid=2000227799"
URL_NS_GTC = "https://docs.google.com/spreadsheets/d/1OemA7cIZM-5AAvsnQuQphNArKw43de27W75Z-Ri6BcQ/export?format=csv&gid=1862143946"
URL_KINHDOANH = "https://docs.google.com/spreadsheets/d/1dEC78RcXYcA7e2SVFmjhOfuP-DY57_FXkOCpRpln4vY/export?format=csv&gid=1161540341"
URL_DT_KH_MOI = "https://docs.google.com/spreadsheets/d/1dEC78RcXYcA7e2SVFmjhOfuP-DY57_FXkOCpRpln4vY/export?format=csv&gid=1798669626"
URL_DT_THEO_KH = "https://docs.google.com/spreadsheets/d/1dEC78RcXYcA7e2SVFmjhOfuP-DY57_FXkOCpRpln4vY/export?format=csv&gid=944526772"
URL_KHACHHANG = "https://docs.google.com/spreadsheets/d/16ywqMY_QxFcRvOXEFsZGAxz0PGRiB1OPELzaUq-Whq8/export?format=csv&gid=942640433"


@st.cache_data(ttl=CACHE_TTL, show_spinner="Đang tải dữ liệu vận hành...")
def get_ops_data():
    df_tq = normalize_headers(pd.read_csv(URL_VH_TONGQUAN)).rename(columns=VH_MAPPING)
    df_ca = normalize_headers(pd.read_csv(URL_VH_CA)).rename(columns=VH_MAPPING)

    out = []
    for df in (df_tq, df_ca):
        if "Bưu Cục" not in df.columns:
            df["Bưu Cục"] = "Chưa phân loại"
        if "Loại Hàng" not in df.columns:
            df["Loại Hàng"] = "Hàng Mới Ca 1"
        df = clean_dataframe_numbers(df, ["Ngày", "Bưu Cục", "Ca", "Loại Hàng"])
        df = rescale_percent(df, ["GTC", "GTC_TTS", "Trả Hàng", "ODR"])
        df["Ngày"] = pd.to_datetime(df["Ngày"], errors="coerce")
        df["Bưu Cục"] = df["Bưu Cục"].astype(str).str.strip()
        df["Loại Hàng"] = df["Loại Hàng"].astype(str).str.strip()
        df["Ca"] = df["Loại Hàng"]
        for c in ["Volume", "Volume TTS"]:
            if c not in df.columns:
                df[c] = 0.0
        for c in ["GTC", "GTC_TTS", "Trả Hàng", "ODR"]:
            if c not in df.columns:
                df[c] = np.nan
        out.append(df.dropna(subset=["Ngày"]))
    return out[0], out[1]


@st.cache_data(ttl=CACHE_TTL, show_spinner="Đang tải dữ liệu lương...")
def get_salary_data():
    df = normalize_headers(pd.read_csv(URL_NHANSU)).rename(columns=NS_MAPPING)
    for c, default in [("Bưu Cục", "Chưa phân loại"), ("Nhân Viên", "Chưa phân loại"), ("Loại Hàng", "FULL")]:
        if c not in df.columns:
            df[c] = default
    df = clean_dataframe_numbers(df, ["Ngày", "Bưu Cục", "Nhân Viên", "Loại Hàng"])
    df = rescale_percent(df, ["%GTC"])
    df["Ngày"] = pd.to_datetime(df["Ngày"], errors="coerce")
    for c in ["Bưu Cục", "Nhân Viên", "Loại Hàng"]:
        df[c] = df[c].astype(str).str.strip()
    for c in ["Số Đơn", "LHH LTC", "LHH GTC", "LHH GTBTT"]:
        if c not in df.columns:
            df[c] = 0.0
    for c in ["Đơn Giá", "%GTC"]:
        if c not in df.columns:
            df[c] = np.nan
    return df.dropna(subset=["Ngày"])


@st.cache_data(ttl=CACHE_TTL, show_spinner="Đang tải dữ liệu năng suất GTC...")
def get_gtc_data():
    cols = ["Ngày", "Bưu Cục", "Nhân Viên", "Loại Hàng", "Đơn giao tính lương", "Số đơn gán Giao"]
    try:
        df = normalize_headers(pd.read_csv(URL_NS_GTC)).rename(columns=GTC_MAPPING)
    except Exception:
        return pd.DataFrame(columns=cols)
    for c, default in [("Bưu Cục", "Chưa phân loại"), ("Nhân Viên", "Chưa phân loại"), ("Loại Hàng", "FULL")]:
        if c not in df.columns:
            df[c] = default
    for c in ["Đơn giao tính lương", "Số đơn gán Giao"]:
        if c not in df.columns:
            df[c] = 0.0
    df = clean_dataframe_numbers(df, ["Ngày", "Bưu Cục", "Nhân Viên", "Loại Hàng"])
    df["Ngày"] = pd.to_datetime(df["Ngày"], errors="coerce")
    for c in ["Bưu Cục", "Nhân Viên", "Loại Hàng"]:
        df[c] = df[c].astype(str).str.strip()
    return df.dropna(subset=["Ngày"])


@st.cache_data(ttl=CACHE_TTL, show_spinner="Đang tải dữ liệu kinh doanh...")
def get_business_data():
    df = normalize_headers(pd.read_csv(URL_KINHDOANH)).rename(columns={
        "Thời Gian": "Ngày", "Thời gian": "Ngày", "ngày": "Ngày",
        "Bưu cục": "Bưu Cục", "bưu cục": "Bưu Cục", "Khu vực": "Bưu Cục",
        "Trạm": "Bưu Cục", "Cửa hàng": "Bưu Cục",
        "Doanh thu": "Doanh Thu", "Khách hàng liên hệ": "Khách Liên Hệ",
        "Khách hàng lên đơn": "Khách Lên Đơn", "Doanh thu KH mới": "Doanh Thu KH Mới",
    })
    if "Bưu Cục" not in df.columns:
        df["Bưu Cục"] = "Chưa phân loại"
    df = clean_dataframe_numbers(df, ["Ngày", "Bưu Cục"])
    df["Ngày"] = pd.to_datetime(df["Ngày"], errors="coerce")
    df["Bưu Cục"] = df["Bưu Cục"].astype(str).str.strip()
    for c in ["Doanh Thu", "Khách Liên Hệ", "Khách Lên Đơn", "Doanh Thu KH Mới"]:
        if c not in df.columns:
            df[c] = 0.0
    return df.dropna(subset=["Ngày"])


@st.cache_data(ttl=CACHE_TTL, show_spinner="Đang tải dữ liệu khách hàng...")
def get_customer_data():
    try:
        df = normalize_headers(pd.read_csv(URL_KHACHHANG)).rename(columns={
            "Thời Gian": "Ngày", "Thời gian": "Ngày", "ngày": "Ngày",
            "Bưu cục": "Bưu Cục", "bưu cục": "Bưu Cục", "Khu vực": "Bưu Cục",
            "Khách hàng liên hệ": "Khách Liên Hệ", "Khách liên hệ": "Khách Liên Hệ",
            "Khách hàng lên đơn": "Khách Lên Đơn", "Khách lên đơn": "Khách Lên Đơn",
            "loại khách hàng": "Loại Khách Hàng", "Loại khách hàng": "Loại Khách Hàng",
            "Trạng thái": "Trạng Thái", "trạng thái": "Trạng Thái",
        })
    except Exception:
        return pd.DataFrame()
    if "Bưu Cục" not in df.columns:
        df["Bưu Cục"] = "Chưa phân loại"
    num_cols = ["Khách Liên Hệ", "Khách Lên Đơn", "Doanh Thu", "Volume", "Số đơn"]
    df = clean_dataframe_numbers(df, [c for c in df.columns if c not in num_cols])
    if "Ngày" in df.columns:
        df["Ngày"] = pd.to_datetime(df["Ngày"], errors="coerce")
    df["Bưu Cục"] = df["Bưu Cục"].astype(str).str.strip()
    return df


@st.cache_data(ttl=CACHE_TTL, show_spinner="Đang tải doanh thu khách hàng mới...")
def get_new_customer_revenue():
    try:
        df = normalize_headers(pd.read_csv(URL_DT_KH_MOI)).rename(columns={
            "Thời Gian": "Ngày", "Thời gian": "Ngày", "ngày": "Ngày",
            "Bưu cục": "Bưu Cục", "bưu cục": "Bưu Cục", "Khu vực": "Bưu Cục",
            "Doanh thu": "Doanh Thu", "Doanh thu KH mới": "Doanh Thu", "Doanh Thu KH mới": "Doanh Thu",
            "Mã Khách Hàng": "Mã KH", "Mã khách hàng": "Mã KH",
            "Tên khách hàng": "Tên KH", "Tên Khách Hàng": "Tên KH", "Khách hàng": "Tên KH",
            "Sản lượng": "Volume", "Số đơn": "Volume",
        })
    except Exception:
        return pd.DataFrame()
    for c in ["Bưu Cục", "Mã KH", "Tên KH"]:
        if c not in df.columns:
            df[c] = "Chưa xác định"
    for c in ["Doanh Thu", "Volume"]:
        if c not in df.columns:
            df[c] = 0.0
    df = clean_dataframe_numbers(df, ["Ngày", "Bưu Cục", "Mã KH", "Tên KH"])
    if "Ngày" in df.columns:
        df["Ngày"] = pd.to_datetime(df["Ngày"], errors="coerce")
    df["Bưu Cục"] = df["Bưu Cục"].astype(str).str.strip()
    return df


@st.cache_data(ttl=CACHE_TTL, show_spinner="Đang tải doanh thu theo khách hàng...")
def get_revenue_by_customer():
    try:
        df = normalize_headers(pd.read_csv(URL_DT_THEO_KH)).rename(columns={
            "Thời Gian": "Ngày", "Thời gian": "Ngày", "ngày": "Ngày",
            "Bưu cục": "Bưu Cục", "bưu cục": "Bưu Cục", "Khu vực": "Bưu Cục",
            "Doanh thu": "Doanh Thu",
            "Khách hàng": "Tên Khách Hàng", "Tên khách hàng": "Tên Khách Hàng",
        })
    except Exception:
        return pd.DataFrame()
    if "Bưu Cục" not in df.columns:
        df["Bưu Cục"] = "Chưa phân loại"
    if "Tên Khách Hàng" not in df.columns:
        df["Tên Khách Hàng"] = "Khách lẻ"
    if "Doanh Thu" not in df.columns:
        df["Doanh Thu"] = 0.0
    df = clean_dataframe_numbers(df, ["Ngày", "Bưu Cục", "Tên Khách Hàng", "Mã Khách Hàng"])
    if "Ngày" in df.columns:
        df["Ngày"] = pd.to_datetime(df["Ngày"], errors="coerce")
    df["Bưu Cục"] = df["Bưu Cục"].astype(str).str.strip()
    df["Tên Khách Hàng"] = df["Tên Khách Hàng"].astype(str).str.strip()
    return df


try:
    df_vh_tongquan, df_vh_ca = get_ops_data()
    df_nhansu = get_salary_data()
    df_ns_gtc_raw = get_gtc_data()
    df_kinhdoanh = get_business_data()
except Exception as exc:
    st.error(f"Không đọc được Google Sheets: {exc}")
    st.info("Kiểm tra quyền chia sẻ của sheet (Anyone with the link → Viewer) rồi bấm làm mới.")
    st.stop()

df_khachhang = get_customer_data()
df_dt_kh_moi = get_new_customer_revenue()
df_dt_theo_kh = get_revenue_by_customer()

SALARY_COMPONENTS = ["LHH LTC", "LHH GTC", "LHH GTBTT"]


# ==========================================
# 7. AI & TELEGRAM
# ==========================================
@st.cache_resource
def get_genai_client():
    if not GENAI_AVAILABLE or not GEMINI_API_KEY:
        return None
    try:
        return genai.Client(api_key=GEMINI_API_KEY)
    except Exception:
        return None


def get_ai_analysis(prompt_text, temperature_hint=None):
    if not GENAI_AVAILABLE:
        return "⚠️ Thiếu thư viện. Cài đặt: `pip install google-genai`"
    client = get_genai_client()
    if client is None:
        return "⚠️ Chưa cấu hình GEMINI_API_KEY trên máy chủ."
    try:
        resp = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt_text,
            config=genai_types.GenerateContentConfig(max_output_tokens=8192),
        )
        if not getattr(resp, "candidates", None):
            return "⚠️ AI không trả về nội dung (có thể bị bộ lọc an toàn chặn). Thử rút gọn câu hỏi."
        text = (resp.text or "").strip()
        return text if text else "⚠️ AI trả về nội dung rỗng. Thử lại sau ít phút."
    except Exception as exc:
        return f"❌ Lỗi máy chủ Google AI: {exc}"


def send_telegram(text):
    """Telegram giới hạn 4096 ký tự/tin nhắn → chia nhỏ."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return False, "Chưa cấu hình TELEGRAM_TOKEN / TELEGRAM_CHAT_ID."
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    chunks = [text[i:i + 3800] for i in range(0, len(text), 3800)] or [""]
    for idx, chunk in enumerate(chunks):
        prefix = "" if idx == 0 else f"(phần {idx + 1}/{len(chunks)})\n"
        try:
            r = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": prefix + chunk}, timeout=20)
        except requests.RequestException as exc:
            return False, f"Lỗi mạng: {exc}"
        if r.status_code != 200:
            return False, f"Telegram trả về mã {r.status_code}: {r.text[:200]}"
    return True, f"Đã gửi {len(chunks)} tin nhắn."


def render_ai_and_telegram(ai_result, tab_name, key_suffix):
    st.markdown(
        f'<div class="ai-warning"><b>🤖 Cố vấn AI ({tab_name}):</b><br><br>{ai_result}</div>',
        unsafe_allow_html=True,
    )
    if st.button(f"📤 Gửi báo cáo {tab_name} lên nhóm Telegram", type="primary", key=f"btn_tele_{key_suffix}"):
        clean = ai_result.replace("**", "").replace("*", "")
        ok, msg = send_telegram(f"🚨 BÁO CÁO {tab_name.upper()} 🚨\n\n{clean}")
        if ok:
            st.success(f"✅ {msg}")
        else:
            st.error(f"❌ {msg}")


ROLE_OPTIONS = ["Góc nhìn Giám Đốc", "Góc nhìn Quản lý khu vực (AM)", "Góc nhìn Nhân viên xử lý"]
CLOSING_RULE = (
    "Yêu cầu BẮT BUỘC: Viết súc tích, phân bổ ý rõ ràng. Tuyệt đối không bỏ dở câu. "
    "Kết thúc báo cáo bằng dòng chữ [HOÀN TẤT BÁO CÁO]."
)


# ==========================================
# 8. BANNER
# ==========================================
st.markdown(
    """
    <div class="banner">
        <div>
            <h1 style="color:white;margin-bottom:5px;">DASHBOARD QUẢN LÝ VẬN HÀNH &amp; KINH DOANH GHN</h1>
            <p style="font-size:18px;font-weight:600;opacity:0.95;margin-bottom:0;">Hiệu Suất Thực - Quyết Định Nhanh - AI Cố Vấn</p>
            <p style="font-size:14px;font-style:italic;opacity:0.8;margin-top:5px;margin-bottom:0;">Designed by AM Phan Van Chanh</p>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

col_rf, col_info = st.columns([2, 8])
with col_rf:
    if st.button("🔄 Làm mới dữ liệu", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
with col_info:
    st.caption(f"Dữ liệu tự làm mới mỗi {CACHE_TTL // 60} phút. Lần đọc gần nhất: {datetime.now():%H:%M:%S %d/%m/%Y}")

st.divider()

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🚚 VẬN HÀNH CHI TIẾT",
    "👥 NĂNG SUẤT & LƯƠNG",
    "🎯 VẬN HÀNH THEO KPI",
    "💰 KINH DOANH",
    "🏆 THI ĐUA GTC",
    "🤖 TRỢ LÝ AI",
])

# ==========================================
# TAB 1 — VẬN HÀNH
# ==========================================
with tab1:
    lo_vh, hi_vh = safe_range(df_vh_tongquan["Ngày"])
    c1, c2, c3 = st.columns(3)
    with c1:
        picked_vh = st.date_input("Khoảng thời gian (Vận hành)", [lo_vh, hi_vh], key="date_vh")
    with c2:
        bc_list_vh = ["Tất cả", "Grand Total"] + [
            x for x in df_vh_tongquan["Bưu Cục"].dropna().unique() if str(x) not in ("Tất cả", "Grand Total")
        ]
        buu_cuc_vh = st.selectbox("Chọn bưu cục", bc_list_vh, key="bc_vh")
    with c3:
        lh_opts = sorted([x for x in df_vh_ca["Loại Hàng"].dropna().unique() if str(x) != "nan"])
        loai_hang_vh = st.multiselect("Lọc loại hàng", lh_opts, default=lh_opts, key="lh_vh")

    start_vh, end_vh = date_bounds(picked_vh, hi_vh)

    m_tq = (df_vh_tongquan["Ngày"] >= start_vh) & (df_vh_tongquan["Ngày"] <= end_vh)
    if buu_cuc_vh != "Tất cả":
        m_tq &= df_vh_tongquan["Bưu Cục"].str.lower() == str(buu_cuc_vh).lower()
    df_vh_tq_f = df_vh_tongquan[m_tq].copy()

    m_ca = (df_vh_ca["Ngày"] >= start_vh) & (df_vh_ca["Ngày"] <= end_vh)
    if buu_cuc_vh != "Tất cả":
        m_ca &= df_vh_ca["Bưu Cục"].str.lower() == str(buu_cuc_vh).lower()
    if loai_hang_vh:
        m_ca &= df_vh_ca["Loại Hàng"].isin(loai_hang_vh)
    df_vh_ca_f = df_vh_ca[m_ca].copy()

    styled_header("1. Tổng quan GTC và tỷ lệ trả hàng", "🌍")
    view_mode_vh = st.radio(
        "Chế độ xem (áp dụng toàn tab):", ["Theo Ngày", "Theo Tuần", "Theo Tháng"],
        horizontal=True, key="view_mode_vh",
    )

    df_period = df_vh_tq_f.copy()
    if not df_period.empty:
        df_period["Ngày"] = to_period(df_period["Ngày"], view_mode_vh)
    df_trend = agg_ops(df_period, ["Ngày"]).sort_values("Ngày") if not df_period.empty else pd.DataFrame()

    if not df_trend.empty:
        last = df_trend.iloc[-1]
        prev = df_trend.iloc[-2] if len(df_trend) > 1 else last
        vol_now, vol_prev = float(last["Volume"] or 0), float(prev["Volume"] or 0)
        gtc_now = float(last["GTC"]) if pd.notna(last["GTC"]) else 0.0
        gtc_prev = float(prev["GTC"]) if pd.notna(prev["GTC"]) else 0.0

        with st.container(border=True):
            st.markdown(
                f"<div style='font-weight:800;font-size:16px;color:#333;'>So sánh kỳ gần nhất với kỳ trước ({view_mode_vh})</div>",
                unsafe_allow_html=True,
            )
            k1, k2 = st.columns(2)
            k1.metric("Tổng sản lượng", f"{vol_now:,.0f} đơn", f"{vol_now - vol_prev:,.0f} đơn")
            k2.metric("Tỷ lệ GTC", f"{gtc_now:.2f}%", f"{gtc_now - gtc_prev:.2f}%")
        st.caption("Các tỷ lệ % được tính trung bình có trọng số theo sản lượng, không phải trung bình cộng.")
    else:
        st.info("Không có dữ liệu vận hành trong bộ lọc hiện tại.")

    g1, g2 = st.columns(2)
    with g1:
        st.plotly_chart(
            draw_combo_chart(df_trend, "Ngày", "Volume", "GTC", f"Tỷ lệ GTC và sản lượng ({view_mode_vh})"),
            use_container_width=True,
        )
    with g2:
        st.plotly_chart(
            draw_rate_line(df_trend, "Ngày", "Trả Hàng", f"Tỷ lệ trả hàng ({view_mode_vh}) — %", C_RED),
            use_container_width=True,
        )

    styled_header("2. TikTok Shop & ontime giao TTS (ODR)", "🛒")
    g3, g4 = st.columns(2)
    with g3:
        st.plotly_chart(
            draw_combo_chart(
                df_trend, "Ngày", "Volume TTS", "GTC_TTS", f"Tỷ lệ GTC TikTok Shop ({view_mode_vh})",
                bar_name="Sản lượng TTS", line_name="% GTC TTS",
            ),
            use_container_width=True,
        )
    with g4:
        st.plotly_chart(
            draw_rate_line(df_trend, "Ngày", "ODR", f"Ontime giao TTS — ODR ({view_mode_vh})", C_GREEN),
            use_container_width=True,
        )

    styled_header("3. Năng suất giao theo ca làm việc", "🕒")
    df_ca_period = df_vh_ca_f.copy()
    if not df_ca_period.empty:
        df_ca_period["Ngày"] = to_period(df_ca_period["Ngày"], view_mode_vh)
        df_ca_g = agg_ops(df_ca_period, ["Ngày", "Ca"]).sort_values(["Ngày", "Ca"])
        fmt = "%m/%Y" if view_mode_vh == "Theo Tháng" else "%d/%m"
        df_ca_g["TrụcX"] = df_ca_g["Ngày"].dt.strftime(fmt) + " · " + df_ca_g["Ca"]

        fig_ca = make_subplots(specs=[[{"secondary_y": True}]])
        bars = [C_BLUE, C_TEAL, C_GREY]
        lines = [C_ORANGE, C_RED, C_GREEN]
        for idx, ca_name in enumerate(df_ca_g["Ca"].unique()):
            sub = df_ca_g[df_ca_g["Ca"] == ca_name]
            fig_ca.add_trace(
                go.Bar(x=sub["TrụcX"], y=sub["Volume"], name=f"Volume {ca_name}",
                       marker_color=bars[idx % len(bars)], opacity=0.85),
                secondary_y=False,
            )
            fig_ca.add_trace(
                go.Scatter(x=sub["TrụcX"], y=sub["GTC"], name=f"%GTC {ca_name}", mode="lines+markers",
                           line=dict(color=lines[idx % len(lines)], width=3),
                           marker=dict(size=8, line=dict(width=1, color="white"))),
                secondary_y=True,
            )
        fig_ca.update_layout(title=f"<b>Sản lượng và tỷ lệ GTC theo ca ({view_mode_vh})</b>", barmode="group")
        fig_ca.update_yaxes(title_text="<b>Sản lượng</b>", secondary_y=False)
        fig_ca.update_yaxes(title_text="<b>% GTC</b>", secondary_y=True, showgrid=False, range=[0, 100])
        st.plotly_chart(fig_ca, use_container_width=True)
    else:
        st.info("Không có dữ liệu theo ca trong bộ lọc hiện tại.")

    st.markdown("---")
    ai_role_vh = st.radio("🤖 Đối tượng nhận báo cáo AI (vận hành):", ROLE_OPTIONS, horizontal=True, key="role_vh")

    if st.button("🔍 Nhờ AI phân tích vận hành", type="primary", key="btn_ai_vh"):
        with st.spinner("AI đang phân tích dữ liệu vận hành..."):
            if ai_role_vh == ROLE_OPTIONS[0]:
                role_prompt = ("Nhiệm vụ: Đóng vai Giám đốc vận hành. Phân tích chuyên sâu theo 3 phần: "
                               "1. Đánh giá tổng thể hiệu suất, 2. Phân tích rủi ro vĩ mô, "
                               "3. Đề xuất hành động chiến lược. Viết chuyên nghiệp, uy quyền.")
            elif ai_role_vh == ROLE_OPTIONS[1]:
                role_prompt = ("Nhiệm vụ: Đóng vai Quản lý khu vực (AM). Phân tích 3 phần: "
                               "1. Đánh giá hiệu suất vận hành của khu vực, 2. Nhận diện điểm nóng/tuyến kéo tụt số liệu, "
                               "3. Chỉ đạo điều phối trực tiếp cho nhân viên xử lý kho và nhân viên giao hàng. "
                               "Viết dứt khoát, mang tính quản trị và đốc thúc.")
            else:
                role_prompt = ('Nhiệm vụ: Đóng vai Trợ lý điều phối vận hành gửi thông báo cho nhóm nhân viên xử lý kho '
                               'và giao hàng. Xưng hô thân thiện, tạo động lực (dùng "Mình" với "Mọi người"). '
                               'Chia 3 ý: 1. Đánh giá nhanh tình hình ca làm việc, 2. Điểm nóng cần chú ý gấp, '
                               '3. Kêu gọi hành động ưu tiên hôm nay.')

            mean_gtc = wavg(df_vh_tq_f.get("GTC"), df_vh_tq_f.get("Volume")) if not df_vh_tq_f.empty else 0.0
            mean_odr = wavg(df_vh_tq_f.get("ODR"), df_vh_tq_f.get("Volume TTS")) if not df_vh_tq_f.empty else 0.0
            mean_tra = wavg(df_vh_tq_f.get("Trả Hàng"), df_vh_tq_f.get("Volume")) if not df_vh_tq_f.empty else 0.0

            prompt_vh = f"""
Dữ liệu vận hành đã lọc:
- Thời gian: {start_vh:%d/%m/%Y} đến {end_vh:%d/%m/%Y}
- Bưu cục/Khu vực: {buu_cuc_vh}
- Loại hàng: {", ".join(loai_hang_vh) if loai_hang_vh else "Tất cả"}
- Tổng đơn: {df_vh_tq_f['Volume'].sum():,.0f}
- Tỷ lệ GTC (trung bình có trọng số): {mean_gtc:.2f}%
- Tỷ lệ trả hàng: {mean_tra:.2f}%
- Ontime giao TTS (ODR): {mean_odr:.2f}%

LƯU Ý: ODR là tỷ lệ cam kết giao đúng hạn với sàn TikTok Shop. Chỉ số này CÀNG CAO CÀNG TỐT; thấp là rủi ro bị phạt.
{role_prompt}
{CLOSING_RULE}
"""
            st.session_state.ai_vh_result = get_ai_analysis(prompt_vh)
    render_ai_and_telegram(st.session_state.ai_vh_result, "Vận Hành", "vh")


# ==========================================
# TAB 2 — NĂNG SUẤT & LƯƠNG
# ==========================================
with tab2:
    lo_ns, hi_ns = safe_range(df_nhansu["Ngày"])
    f1, f2, f3, f4, f5 = st.columns(5)
    with f1:
        picked_ns = st.date_input("Khoảng thời gian (nhân sự)", [lo_ns, hi_ns], key="date_ns")
    with f2:
        lh_set = set(df_nhansu["Loại Hàng"].dropna().astype(str).str.strip())
        if not df_ns_gtc_raw.empty:
            lh_set |= set(df_ns_gtc_raw["Loại Hàng"].dropna().astype(str).str.strip())
        lh_all = sorted([x for x in lh_set if x and x != "nan"])
        loai_hang_ns = st.multiselect("Lọc loại hàng", lh_all, default=[], key="lh_filter")
    with f3:
        bc_set = set(df_nhansu["Bưu Cục"].dropna().astype(str).str.strip())
        if not df_ns_gtc_raw.empty:
            bc_set |= set(df_ns_gtc_raw["Bưu Cục"].dropna().astype(str).str.strip())
        bc_all = sorted([x for x in bc_set if x and x not in ("Chưa phân loại", "nan")])
        buu_cuc_ns = st.selectbox("Lọc bưu cục", ["Tất cả"] + bc_all, key="bc_ns_tab2")
    with f4:
        def _staff(df):
            if df.empty:
                return set()
            if buu_cuc_ns == "Tất cả":
                sub = df
            else:
                sub = df[df["Bưu Cục"].str.strip().str.lower() == buu_cuc_ns.strip().lower()]
            return set(sub["Nhân Viên"].dropna().astype(str).str.strip())

        nv_all = sorted([x for x in (_staff(df_nhansu) | _staff(df_ns_gtc_raw)) if x and x not in ("Chưa phân loại", "nan")])
        nhan_vien_ns = st.selectbox("Lọc nhân viên", ["Tất cả"] + nv_all, key="nv_ns_tab2")
    with f5:
        loai_luong_ns = st.multiselect("Lọc loại lương", SALARY_COMPONENTS, default=SALARY_COMPONENTS, key="ll_filter")

    start_ns, end_ns = date_bounds(picked_ns, hi_ns)
    selected_ll = loai_luong_ns or SALARY_COMPONENTS

    def apply_staff_filters(df):
        if df.empty:
            return df
        m = pd.Series(True, index=df.index)
        if buu_cuc_ns != "Tất cả":
            m &= df["Bưu Cục"].str.strip().str.lower() == buu_cuc_ns.strip().lower()
        if nhan_vien_ns != "Tất cả":
            m &= df["Nhân Viên"].str.strip().str.lower() == nhan_vien_ns.strip().lower()
        if loai_hang_ns and "Loại Hàng" in df.columns:
            m &= df["Loại Hàng"].str.strip().isin(loai_hang_ns)
        return df[m].copy()

    df_ns_base = apply_staff_filters(df_nhansu)
    if not df_ns_base.empty:
        df_ns_base["Tổng Lương"] = df_ns_base[selected_ll].sum(axis=1)
    df_ns_f = df_ns_base[(df_ns_base["Ngày"] >= start_ns) & (df_ns_base["Ngày"] <= end_ns)].copy() \
        if not df_ns_base.empty else df_ns_base

    styled_header("Đơn giá, năng suất và tổng lương", "📈")

    ref_date = end_ns
    if ref_date.day <= 15:
        curr_start = ref_date.replace(day=1)
        curr_end = ref_date.replace(day=15)
        prev_end = curr_start - timedelta(days=1)
        prev_start = prev_end.replace(day=16)
        curr_name = f"Kỳ 20 ({curr_start.month:02d}/{curr_start.year})"
        prev_name = f"Kỳ 05 ({curr_start.month:02d}/{curr_start.year})"
    else:
        curr_start = ref_date.replace(day=16)
        curr_end = month_end(curr_start)
        prev_start = ref_date.replace(day=1)
        prev_end = ref_date.replace(day=15)
        nxt = curr_end + timedelta(days=1)
        curr_name = f"Kỳ 05 ({nxt.month:02d}/{nxt.year})"
        prev_name = f"Kỳ 20 ({curr_start.month:02d}/{curr_start.year})"

    def slice_period(df, a, b):
        if df is None or df.empty:
            return df if df is not None else pd.DataFrame()
        return df[(df["Ngày"] >= a) & (df["Ngày"] <= b)]

    df_curr = slice_period(df_ns_base, curr_start, curr_end)
    df_prev = slice_period(df_ns_base, prev_start, prev_end)

    price_curr = float(df_curr["Đơn Giá"].mean()) if not df_curr.empty and df_curr["Đơn Giá"].notna().any() else 0.0
    price_prev = float(df_prev["Đơn Giá"].mean()) if not df_prev.empty and df_prev["Đơn Giá"].notna().any() else 0.0
    salary_curr = float(df_curr["Tổng Lương"].sum()) if not df_curr.empty else 0.0
    salary_prev = float(df_prev["Tổng Lương"].sum()) if not df_prev.empty else 0.0

    with st.container(border=True):
        st.markdown(
            f"<div style='font-weight:800;font-size:16px;color:#333;'>Đơn giá trung bình theo kỳ lương (mốc {ref_date:%d/%m/%Y})</div>",
            unsafe_allow_html=True,
        )
        a1, a2, a3 = st.columns(3)
        a1.metric(f"Hiện tại — {curr_name}", f"{price_curr:,.0f} đ")
        a2.metric(f"Kỳ trước — {prev_name}", f"{price_prev:,.0f} đ")
        a3.metric("Chênh lệch", f"{price_curr - price_prev:,.0f} đ", f"{price_curr - price_prev:,.0f} đ")

        st.markdown(
            f"<div style='font-weight:800;font-size:16px;color:#333;margin-top:12px;'>Tổng lương theo loại: {', '.join(selected_ll)}</div>",
            unsafe_allow_html=True,
        )
        b1, b2, b3 = st.columns(3)
        b1.metric("Tổng lương hiện tại", f"{salary_curr:,.0f} đ")
        b2.metric("Tổng lương kỳ trước", f"{salary_prev:,.0f} đ")
        b3.metric("Mức tăng/giảm", f"{salary_curr - salary_prev:,.0f} đ", f"{salary_curr - salary_prev:,.0f} đ")

    df_gtc_base = apply_staff_filters(df_ns_gtc_raw)

    def calc_gtc(df_sub):
        if df_sub is None or df_sub.empty:
            return 0.0
        gan = df_sub["Số đơn gán Giao"].sum()
        giao = df_sub["Đơn giao tính lương"].sum()
        return float(giao / gan * 100) if gan > 0 else 0.0

    if not df_gtc_base.empty:
        d_n = df_gtc_base[df_gtc_base["Ngày"] == ref_date]
        d_n1 = df_gtc_base[df_gtc_base["Ngày"] == ref_date - timedelta(days=1)]

        w_start = ref_date - timedelta(days=ref_date.weekday())
        d_w = slice_period(df_gtc_base, w_start, w_start + timedelta(days=6))
        d_w1 = slice_period(df_gtc_base, w_start - timedelta(days=7), w_start - timedelta(days=1))

        m_start = ref_date.replace(day=1)
        d_m = slice_period(df_gtc_base, m_start, month_end(m_start))
        d_m1 = slice_period(df_gtc_base, (m_start - timedelta(days=1)).replace(day=1), m_start - timedelta(days=1))

        d_kl = slice_period(df_gtc_base, curr_start, curr_end)
        d_kl_prev = slice_period(df_gtc_base, prev_start, prev_end)
    else:
        empty = pd.DataFrame(columns=["Đơn giao tính lương", "Số đơn gán Giao"])
        d_n = d_n1 = d_w = d_w1 = d_m = d_m1 = d_kl = d_kl_prev = empty

    def total_gtc(df_sub):
        return float(df_sub["Đơn giao tính lương"].sum()) if not df_sub.empty else 0.0

    with st.container(border=True):
        st.markdown(
            "<div style='font-weight:800;font-size:16px;color:#333;'>Sản lượng GTC theo kỳ lương</div>",
            unsafe_allow_html=True,
        )
        c1_, c2_, c3_ = st.columns(3)
        sl_kl, sl_kl_prev = total_gtc(d_kl), total_gtc(d_kl_prev)
        c1_.metric(f"Hiện tại — {curr_name}", f"{sl_kl:,.0f} đơn")
        c2_.metric(f"Kỳ trước — {prev_name}", f"{sl_kl_prev:,.0f} đơn")
        c3_.metric("Chênh lệch", f"{sl_kl - sl_kl_prev:,.0f} đơn", f"{sl_kl - sl_kl_prev:,.0f} đơn")

    with st.container(border=True):
        st.markdown(
            f"<div style='font-weight:800;font-size:16px;color:#333;'>Năng suất %GTC (mốc {ref_date:%d/%m/%Y})</div>",
            unsafe_allow_html=True,
        )
        e1, e2, e3 = st.columns(3)
        e1.metric("Ngày (N vs N-1)", f"{calc_gtc(d_n):.2f}%", f"{calc_gtc(d_n) - calc_gtc(d_n1):.2f}%")
        e2.metric("Tuần (W vs W-1)", f"{calc_gtc(d_w):.2f}%", f"{calc_gtc(d_w) - calc_gtc(d_w1):.2f}%")
        e3.metric("Tháng (M vs M-1)", f"{calc_gtc(d_m):.2f}%", f"{calc_gtc(d_m) - calc_gtc(d_m1):.2f}%")

        st.markdown(
            "<div style='font-weight:800;font-size:16px;color:#333;margin-top:12px;'>Sản lượng GTC</div>",
            unsafe_allow_html=True,
        )
        h1, h2, h3 = st.columns(3)
        h1.metric("Ngày (N vs N-1)", f"{total_gtc(d_n):,.0f} đơn", f"{total_gtc(d_n) - total_gtc(d_n1):,.0f} đơn")
        h2.metric("Tuần (W vs W-1)", f"{total_gtc(d_w):,.0f} đơn", f"{total_gtc(d_w) - total_gtc(d_w1):,.0f} đơn")
        h3.metric("Tháng (M vs M-1)", f"{total_gtc(d_m):,.0f} đơn", f"{total_gtc(d_m) - total_gtc(d_m1):,.0f} đơn")

    df_gtc_f = slice_period(df_gtc_base, start_ns, end_ns)
    if df_gtc_f is not None and not df_gtc_f.empty:
        df_gtc_daily = df_gtc_f.groupby("Ngày", as_index=False).agg(
            {"Đơn giao tính lương": "sum", "Số đơn gán Giao": "sum"}
        )
        df_gtc_daily["%GTC"] = np.where(
            df_gtc_daily["Số đơn gán Giao"] > 0,
            df_gtc_daily["Đơn giao tính lương"] / df_gtc_daily["Số đơn gán Giao"] * 100,
            0.0,
        )
    else:
        df_gtc_daily = pd.DataFrame(columns=["Ngày", "Đơn giao tính lương", "Số đơn gán Giao", "%GTC"])

    who = nhan_vien_ns if nhan_vien_ns != "Tất cả" else (buu_cuc_ns if buu_cuc_ns != "Tất cả" else "toàn hệ thống")

    p1, p2 = st.columns(2)
    with p1:
        if not df_ns_f.empty:
            df_dg = df_ns_f.groupby("Ngày", as_index=False)["Đơn Giá"].mean()
            fig_dg = px.line(df_dg, x="Ngày", y="Đơn Giá", markers=True, title=f"<b>Biến động đơn giá — {who}</b>")
            fig_dg.update_traces(line=dict(color=C_ORANGE, width=4),
                                 marker=dict(size=9, color=C_BLUE, line=dict(width=2, color="white")))
            fig_dg.update_yaxes(title_text="<b>VNĐ</b>")
            st.plotly_chart(fig_dg, use_container_width=True)
        else:
            st.info("Không có dữ liệu đơn giá trong bộ lọc.")
    with p2:
        if not df_gtc_daily.empty:
            fig_ns = make_subplots(specs=[[{"secondary_y": True}]])
            fig_ns.add_trace(go.Bar(x=df_gtc_daily["Ngày"], y=df_gtc_daily["Số đơn gán Giao"],
                                    name="Số đơn gán", marker_color=C_TEAL, opacity=0.85), secondary_y=False)
            fig_ns.add_trace(go.Bar(x=df_gtc_daily["Ngày"], y=df_gtc_daily["Đơn giao tính lương"],
                                    name="Số đơn GTC", marker_color=C_BLUE, opacity=0.85), secondary_y=False)
            fig_ns.add_trace(go.Scatter(x=df_gtc_daily["Ngày"], y=df_gtc_daily["%GTC"], name="% GTC",
                                        mode="lines+markers", line=dict(color=C_ORANGE, width=4),
                                        marker=dict(size=9, line=dict(width=2, color="white"))), secondary_y=True)
            fig_ns.update_layout(title=f"<b>Năng suất và %GTC — {who}</b>", barmode="group")
            fig_ns.update_yaxes(title_text="<b>Số lượng</b>", secondary_y=False)
            fig_ns.update_yaxes(title_text="<b>% GTC</b>", secondary_y=True, showgrid=False, range=[0, 100])
            fig_ns.update_xaxes(tickformat="%d/%m")
            st.plotly_chart(fig_ns, use_container_width=True)
        else:
            st.info("Không có dữ liệu năng suất GTC trong bộ lọc.")

    p3, p4 = st.columns(2)
    with p3:
        if not df_ns_f.empty:
            df_lg = df_ns_f.groupby("Ngày", as_index=False)["Tổng Lương"].sum()
            fig_lg = px.line(df_lg, x="Ngày", y="Tổng Lương", markers=True, title=f"<b>Biến động tổng lương — {who}</b>")
            fig_lg.update_traces(line=dict(color=C_GREEN, width=4),
                                 marker=dict(size=9, color=C_BLUE, line=dict(width=2, color="white")))
            fig_lg.update_yaxes(title_text="<b>VNĐ</b>")
            st.plotly_chart(fig_lg, use_container_width=True)
        else:
            st.info("Không có dữ liệu lương trong bộ lọc.")
    with p4:
        if not df_gtc_daily.empty:
            fig_don = go.Figure()
            fig_don.add_trace(go.Scatter(x=df_gtc_daily["Ngày"], y=df_gtc_daily["Số đơn gán Giao"], name="Số đơn gán",
                                         mode="lines+markers", line=dict(color=C_ORANGE, width=4),
                                         marker=dict(size=9, line=dict(width=2, color="white"))))
            fig_don.add_trace(go.Scatter(x=df_gtc_daily["Ngày"], y=df_gtc_daily["Đơn giao tính lương"], name="Số đơn giao",
                                         mode="lines+markers", line=dict(color=C_BLUE, width=4),
                                         marker=dict(size=9, line=dict(width=2, color="white"))))
            fig_don.update_layout(title=f"<b>Số đơn gán và số đơn giao — {who}</b>")
            fig_don.update_yaxes(title_text="<b>Số lượng đơn</b>")
            fig_don.update_xaxes(tickformat="%d/%m")
            st.plotly_chart(fig_don, use_container_width=True)
        else:
            st.info("Không có dữ liệu số đơn gán/giao trong bộ lọc.")

    st.markdown("---")
    ai_role_ns = st.radio("🤖 Đối tượng nhận báo cáo AI (năng suất):", ROLE_OPTIONS, horizontal=True, key="role_ns")

    if st.button("🔍 Nhờ AI phân tích nhân sự và chi phí", type="primary", key="btn_ai_ns"):
        with st.spinner("AI đang phân tích dữ liệu năng suất..."):
            if ai_role_ns == ROLE_OPTIONS[0]:
                role_prompt = ("Nhiệm vụ: Đóng vai Giám đốc nhân sự. Đánh giá 3 phần: 1. Năng suất tổng thể, "
                               "2. Quỹ lương/chi phí/đơn giá, 3. Đề xuất chính sách nhân sự cấp quản lý.")
            elif ai_role_ns == ROLE_OPTIONS[1]:
                role_prompt = ("Nhiệm vụ: Đóng vai Quản lý khu vực (AM). Đánh giá 3 phần: 1. Năng suất giao hàng khu vực, "
                               "2. Cảnh báo rủi ro quỹ lương/đơn giá, 3. Chỉ đạo phân tuyến lại và ép năng suất. "
                               "Viết dứt khoát, thực tiễn.")
            else:
                role_prompt = ('Nhiệm vụ: Đóng vai Trợ lý nhân sự gửi thông báo cho nhóm nhân viên xử lý kho và giao hàng. '
                               'Xưng hô thân thiện (dùng "Mình" với "Anh em"). Chia 3 phần: 1. Ghi nhận công sức, '
                               '2. Tình hình thu nhập/đơn giá, 3. Bí kíp tăng thu nhập.')

            tong_gan = df_gtc_f["Số đơn gán Giao"].sum() if df_gtc_f is not None and not df_gtc_f.empty else 0
            tong_giao = df_gtc_f["Đơn giao tính lương"].sum() if df_gtc_f is not None and not df_gtc_f.empty else 0

            prompt_ns = f"""
Dữ liệu năng suất và nhân sự đã lọc:
- Thời gian: {start_ns:%d/%m/%Y} đến {end_ns:%d/%m/%Y}
- Bưu cục: {buu_cuc_ns} | Nhân viên: {nhan_vien_ns}
- Loại hàng: {", ".join(loai_hang_ns) if loai_hang_ns else "Tất cả"}
- Loại lương áp dụng: {", ".join(selected_ll)}

Kết quả thực tế:
- Tổng số đơn gán: {tong_gan:,.0f} đơn
- Tổng đơn giao thành công: {tong_giao:,.0f} đơn
- Đơn giá trung bình kỳ hiện tại: {price_curr:,.0f} VNĐ
- Tổng lương kỳ hiện tại ({curr_name}): {salary_curr:,.0f} đ (chênh lệch {salary_curr - salary_prev:,.0f} đ so với kỳ trước)

{role_prompt}
{CLOSING_RULE}
"""
            st.session_state.ai_ns_result = get_ai_analysis(prompt_ns)
    render_ai_and_telegram(st.session_state.ai_ns_result, "Năng Suất & Nhân Sự", "ns")


# ==========================================
# TAB 3 — KPI VẬN HÀNH
# ==========================================
with tab3:
    styled_header("Cài đặt và theo dõi KPI vận hành", "🎯")

    bc_list_kpi = ["Tất cả", "Grand Total"] + [
        x for x in df_vh_tongquan["Bưu Cục"].dropna().unique() if str(x) not in ("Tất cả", "Grand Total")
    ]

    with st.expander("⚙️ Điều chỉnh KPI (lưu riêng theo từng khu vực)", expanded=True):
        target_bc = st.selectbox("Khu vực cần cài đặt KPI:", bc_list_kpi, key="set_bc_kpi_tab3")
        st.session_state.kpi_gtc_dict.setdefault(target_bc, 70.0)
        st.session_state.kpi_tts_dict.setdefault(target_bc, 80.0)
        st.session_state.kpi_odr_dict.setdefault(target_bc, 98.0)

        q1, q2, q3 = st.columns(3)
        with q1:
            st.session_state.kpi_gtc_dict[target_bc] = st.number_input(
                f"KPI %GTC — {target_bc}", 0.0, 100.0, float(st.session_state.kpi_gtc_dict[target_bc]), 0.5)
        with q2:
            st.session_state.kpi_tts_dict[target_bc] = st.number_input(
                f"KPI %GTC TikTok Shop — {target_bc}", 0.0, 100.0, float(st.session_state.kpi_tts_dict[target_bc]), 0.5)
        with q3:
            st.session_state.kpi_odr_dict[target_bc] = st.number_input(
                f"KPI ontime giao TTS (ODR) — {target_bc}", 0.0, 100.0, float(st.session_state.kpi_odr_dict[target_bc]), 0.5)

    lo_k, hi_k = safe_range(df_vh_tongquan["Ngày"])
    r1, r2 = st.columns(2)
    with r1:
        picked_kpi = st.date_input("Chọn thời gian", [lo_k, hi_k], key="date_kpi")
    with r2:
        buu_cuc_kpi = st.selectbox("Bưu cục xem số liệu", bc_list_kpi, key="bc_kpi")

    start_k, end_k = date_bounds(picked_kpi, hi_k)
    m_kpi = (df_vh_tongquan["Ngày"] >= start_k) & (df_vh_tongquan["Ngày"] <= end_k)
    if buu_cuc_kpi != "Tất cả":
        m_kpi &= df_vh_tongquan["Bưu Cục"].str.lower() == str(buu_cuc_kpi).lower()
    df_kpi_f = df_vh_tongquan[m_kpi].copy()

    actual_gtc = wavg(df_kpi_f.get("GTC"), df_kpi_f.get("Volume")) if not df_kpi_f.empty else 0.0
    actual_tts = wavg(df_kpi_f.get("GTC_TTS"), df_kpi_f.get("Volume TTS")) if not df_kpi_f.empty else 0.0
    actual_odr = wavg(df_kpi_f.get("ODR"), df_kpi_f.get("Volume TTS")) if not df_kpi_f.empty else 0.0

    kpi_gtc = float(st.session_state.kpi_gtc_dict.get(buu_cuc_kpi, 70.0))
    kpi_tts = float(st.session_state.kpi_tts_dict.get(buu_cuc_kpi, 80.0))
    kpi_odr = float(st.session_state.kpi_odr_dict.get(buu_cuc_kpi, 98.0))

    def create_gauge(title, value, target):
        target = max(float(target), 0.5)  # tránh các dải steps trùng nhau khi target = 0
        fig = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=float(value),
            domain={"x": [0, 1], "y": [0, 1]},
            title={"text": f"<b>{title}</b>", "font": {"size": 17, "color": "#0056b3"}},
            number={"suffix": "%"},
            delta={"reference": target, "increasing": {"color": "#00B4D8"}, "decreasing": {"color": "#FF7F50"}},
            gauge={
                "axis": {"range": [0, 100], "tickwidth": 2, "tickcolor": "#333"},
                "bar": {"color": "#2C3E50", "thickness": 0.25},
                "steps": [
                    {"range": [0, target * 0.8], "color": "#FFD9CC"},
                    {"range": [target * 0.8, target], "color": "#BDE6F5"},
                    {"range": [target, 100], "color": "#B8F2E6"},
                ],
                "threshold": {"line": {"color": C_RED, "width": 4}, "thickness": 0.85, "value": target},
                "borderwidth": 2,
                "bordercolor": "#E5E7EB",
            },
        ))
        fig.update_layout(height=310, margin=dict(l=20, r=20, t=60, b=20))
        return fig

    s1, s2, s3 = st.columns(3)
    s1.plotly_chart(create_gauge("Tỷ lệ GTC chung", actual_gtc, kpi_gtc), use_container_width=True)
    s2.plotly_chart(create_gauge("Tỷ lệ GTC TikTok", actual_tts, kpi_tts), use_container_width=True)
    s3.plotly_chart(create_gauge("Ontime giao TTS (ODR)", actual_odr, kpi_odr), use_container_width=True)
    st.caption("Vạch đỏ trên đồng hồ là mốc KPI. Các tỷ lệ tính trung bình có trọng số theo sản lượng.")

    st.markdown("---")
    st.markdown(
        """
        <div style="background:linear-gradient(135deg,#00B4D8,#0077B6);padding:15px 20px;border-radius:8px;
                    margin-bottom:15px;box-shadow:0 4px 10px rgba(0,0,0,0.15);">
            <h3 style="color:white;margin:0;font-weight:900;text-transform:uppercase;">📊 Theo dõi hoàn thành KPI theo ngày</h3>
        </div>
        """,
        unsafe_allow_html=True,
    )

    df_kpi_day = agg_ops(df_kpi_f, ["Ngày"]).sort_values("Ngày") if not df_kpi_f.empty else pd.DataFrame()
    if not df_kpi_day.empty:
        tbl = df_kpi_day[["Ngày", "Volume", "GTC", "GTC_TTS", "ODR"]].copy()
        tbl["% Đạt KPI GTC"] = (tbl["GTC"] / kpi_gtc * 100) if kpi_gtc > 0 else 0.0
        tbl["Kết quả"] = np.where(tbl["GTC"] >= kpi_gtc, "✅ Đạt", "❌ Chưa đạt")
        st.dataframe(
            tbl,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Ngày": st.column_config.DateColumn("Ngày", format="DD/MM/YYYY"),
                "Volume": st.column_config.NumberColumn("Sản lượng", format="%,d"),
                "GTC": st.column_config.NumberColumn("%GTC", format="%.2f%%"),
                "GTC_TTS": st.column_config.NumberColumn("%GTC TTS", format="%.2f%%"),
                "ODR": st.column_config.NumberColumn("ODR", format="%.2f%%"),
                "% Đạt KPI GTC": st.column_config.ProgressColumn(
                    "% đạt KPI GTC", format="%.1f%%", min_value=0, max_value=150),
            },
        )
    else:
        st.info("Không có dữ liệu KPI trong bộ lọc hiện tại.")

    st.markdown("---")
    ai_role_kpi = st.radio("🤖 Đối tượng nhận báo cáo AI (KPI):", ROLE_OPTIONS, horizontal=True, key="role_kpi")

    if st.button("🔍 AI đánh giá mức độ đạt KPI", type="primary", key="btn_ai_kpi"):
        with st.spinner("AI đang đối chiếu số liệu với mục tiêu KPI..."):
            if ai_role_kpi == ROLE_OPTIONS[0]:
                role_prompt = ("Đóng vai Giám đốc kiểm soát. Nêu: 1. Tình hình đạt/trượt KPI vĩ mô, "
                               "2. Cảnh báo rủi ro hệ thống, 3. Yêu cầu hành động khẩn cấp cho quản lý cấp trung.")
            elif ai_role_kpi == ROLE_OPTIONS[1]:
                role_prompt = ("Đóng vai Quản lý khu vực (AM). Nêu: 1. Mức độ hoàn thành KPI so với mục tiêu, "
                               "2. Các chỉ số đang báo động (đặc biệt ODR), 3. Giao việc khẩn cho nhân viên kho và giao hàng.")
            else:
                role_prompt = ('Đóng vai Trợ lý báo cáo gửi tin cho nhóm nhân viên xử lý kho và giao hàng. '
                               'Xưng hô thân thiện (dùng "Mình" với "Team"). Nêu: 1. Tuyên dương hoặc động viên, '
                               '2. Điểm nghẽn hiện tại, 3. Mục tiêu cần chạy gấp hôm nay.')

            prompt_kpi = f"""
Dữ liệu KPI đã lọc:
- Thời gian: {start_k:%d/%m/%Y} đến {end_k:%d/%m/%Y}
- Bưu cục/Khu vực: {buu_cuc_kpi}

Mục tiêu KPI: GTC ≥ {kpi_gtc}% | GTC TikTok ≥ {kpi_tts}% | ODR ≥ {kpi_odr}%
Thực tế đạt: GTC {actual_gtc:.2f}% | GTC TikTok {actual_tts:.2f}% | ODR {actual_odr:.2f}%

LƯU Ý: ODR là tỷ lệ cam kết giao đúng hạn với sàn TikTok Shop. ODR thực tế phải LỚN HƠN HOẶC BẰNG mục tiêu mới là hoàn thành; thấp hơn là trượt KPI.

{role_prompt}
{CLOSING_RULE}
"""
            st.session_state.ai_kpi_result = get_ai_analysis(prompt_kpi)
    render_ai_and_telegram(st.session_state.ai_kpi_result, "KPI Vận Hành", "kpi")


# ==========================================
# TAB 4 — KINH DOANH
# ==========================================
with tab4:
    styled_header("Doanh thu và phát triển khách hàng", "💰")

    bc_list_kd = ["Tất cả", "Grand Total"] + [
        x for x in df_kinhdoanh["Bưu Cục"].dropna().unique() if str(x) not in ("Tất cả", "Grand Total")
    ]

    with st.expander("⚙️ Điều chỉnh KPI doanh thu (lưu riêng theo từng khu vực)", expanded=True):
        target_bc_kd = st.selectbox("Khu vực cần cài đặt KPI doanh thu:", bc_list_kd, key="set_bc_kd_tab4")
        st.session_state.kpi_dt_dict.setdefault(target_bc_kd, 71000000.0)
        st.session_state.kpi_dt_dict[target_bc_kd] = st.number_input(
            f"Mục tiêu doanh thu VNĐ/tháng — {target_bc_kd}",
            min_value=0.0, value=float(st.session_state.kpi_dt_dict[target_bc_kd]), step=1000000.0,
        )

    lo_kd, hi_kd = safe_range(df_kinhdoanh["Ngày"], days_back=7)
    t1, t2, t3 = st.columns(3)
    with t1:
        picked_kd = st.date_input("Chọn thời gian", [lo_kd, hi_kd], key="date_kd")
    with t2:
        buu_cuc_kd = st.selectbox("Bưu cục xem số liệu", bc_list_kd, key="bc_kd")
    with t3:
        view_type = st.selectbox("Góc nhìn báo cáo", ["Theo Ngày", "Theo Tuần", "Theo Tháng"], key="view_kd")

    start_kd, end_kd = date_bounds(picked_kd, hi_kd)

    def filter_bc(df):
        if df is None or df.empty or "Bưu Cục" not in df.columns:
            return df if df is not None else pd.DataFrame()
        if buu_cuc_kd == "Tất cả":
            return df
        return df[df["Bưu Cục"].str.lower() == str(buu_cuc_kd).lower()]

    def filter_date(df, a, b):
        if df is None or df.empty or "Ngày" not in df.columns:
            return df if df is not None else pd.DataFrame()
        return df[df["Ngày"].isna() | ((df["Ngày"] >= a) & (df["Ngày"] <= b))]

    df_kd_bc = filter_bc(df_kinhdoanh)

    if view_type == "Theo Ngày":
        a_now, b_now = end_kd, end_kd
        a_prev, b_prev = end_kd - timedelta(days=1), end_kd - timedelta(days=1)
        label_prev = "Kỳ trước (hôm qua)"
    elif view_type == "Theo Tuần":
        a_now = end_kd - timedelta(days=end_kd.weekday())
        b_now = a_now + timedelta(days=6)
        a_prev, b_prev = a_now - timedelta(days=7), a_now - timedelta(days=1)
        label_prev = "Kỳ trước (tuần trước)"
    else:
        a_now = end_kd.replace(day=1)
        b_now = month_end(a_now)
        a_prev = (a_now - timedelta(days=1)).replace(day=1)
        b_prev = a_now - timedelta(days=1)
        label_prev = "Kỳ trước (tháng trước)"

    rev_now = float(df_kd_bc[(df_kd_bc["Ngày"] >= a_now) & (df_kd_bc["Ngày"] <= b_now)]["Doanh Thu"].sum()) if not df_kd_bc.empty else 0.0
    rev_prev = float(df_kd_bc[(df_kd_bc["Ngày"] >= a_prev) & (df_kd_bc["Ngày"] <= b_prev)]["Doanh Thu"].sum()) if not df_kd_bc.empty else 0.0

    days_span = max((b_now - a_now).days + 1, 1)
    days_in_month = month_end(end_kd.replace(day=1)).day
    daily_avg = rev_now / days_span
    forecast_month = daily_avg * days_in_month

    kpi_dt = float(st.session_state.kpi_dt_dict.get(buu_cuc_kd, 71000000.0))
    if view_type == "Theo Ngày":
        kpi_dt_view = kpi_dt / days_in_month
    elif view_type == "Theo Tuần":
        kpi_dt_view = kpi_dt / days_in_month * 7
    else:
        kpi_dt_view = kpi_dt

    with st.container(border=True):
        st.markdown(
            f"<div style='font-weight:800;font-size:16px;color:#333;'>Hiệu suất doanh thu ({view_type})</div>",
            unsafe_allow_html=True,
        )
        v1, v2, v3, v4 = st.columns(4)
        delta_kpi = f"{(rev_now - kpi_dt_view) / kpi_dt_view * 100:.1f}% so với KPI" if kpi_dt_view > 0 else "Chưa đặt KPI"
        v1.metric("Doanh thu hiện tại", f"{rev_now:,.0f} đ", delta_kpi)
        v2.metric(label_prev, f"{rev_prev:,.0f} đ", f"{rev_now - rev_prev:,.0f} đ")
        v3.metric("Mục tiêu KPI", f"{kpi_dt_view:,.0f} đ")
        v4.metric("Dự kiến hết tháng", f"{forecast_month:,.0f} đ", "theo tốc độ hiện tại", delta_color="off")

    df_kd_range = filter_date(df_kd_bc, start_kd, end_kd)
    df_kh_range = filter_date(filter_bc(df_khachhang), start_kd, end_kd)
    df_moi_range = filter_date(filter_bc(df_dt_kh_moi), start_kd, end_kd)

    k1, k2 = st.columns(2)
    with k1:
        if not df_kd_range.empty:
            plot = df_kd_range.copy()
            plot["Ngày"] = to_period(plot["Ngày"], view_type)
            plot = plot.groupby("Ngày", as_index=False)["Doanh Thu"].sum()
            fig_rev = px.bar(plot, x="Ngày", y="Doanh Thu", title=f"<b>Doanh thu và KPI — {buu_cuc_kd}</b>",
                             color_discrete_sequence=[C_BLUE])
            fig_rev.add_hline(y=kpi_dt_view, line_dash="dash", line_color=C_RED, annotation_text="KPI mục tiêu")
            st.plotly_chart(fig_rev, use_container_width=True)
        else:
            st.info("Không có dữ liệu doanh thu trong bộ lọc.")
    with k2:
        if not df_kh_range.empty and "Trạng Thái" in df_kh_range.columns:
            funnel = df_kh_range.groupby("Trạng Thái").size().reset_index(name="Số Lượng").sort_values("Số Lượng", ascending=False)
            fig_fn = go.Figure(go.Funnel(
                y=funnel["Trạng Thái"], x=funnel["Số Lượng"], textinfo="value+percent initial",
                marker={"color": [C_ORANGE, C_GREEN, C_BLUE, C_TEAL, C_GREY]},
            ))
            fig_fn.update_layout(title=f"<b>Phễu trạng thái khách hàng mới ({view_type})</b>", hovermode="closest")
            st.plotly_chart(fig_fn, use_container_width=True)
        else:
            st.info("Không tìm thấy cột Trạng Thái trong dữ liệu khách hàng.")

    k3, k4 = st.columns(2)
    with k3:
        st.markdown("<div style='font-weight:800;font-size:18px;color:#333;margin-bottom:12px;'>Doanh thu khách hàng mới</div>",
                    unsafe_allow_html=True)
        if not df_moi_range.empty:
            keys = [c for c in ["Mã KH", "Tên KH"] if c in df_moi_range.columns]
            if keys:
                tbl_new = (df_moi_range.groupby(keys, as_index=False)
                           .agg({"Doanh Thu": "sum", "Volume": "sum"})
                           .sort_values("Doanh Thu", ascending=False))
                st.dataframe(
                    tbl_new, use_container_width=True, height=350, hide_index=True,
                    column_config={
                        "Doanh Thu": st.column_config.NumberColumn("Doanh thu", format="%,d ₫"),
                        "Volume": st.column_config.NumberColumn("Sản lượng", format="%,d"),
                    },
                )
            else:
                st.info("Thiếu cột Mã KH hoặc Tên KH trong dữ liệu gốc.")
        else:
            st.info("Chưa có dữ liệu doanh thu khách hàng mới trong khoảng này.")

    with k4:
        st.markdown("<div style='font-weight:800;font-size:18px;color:#333;margin-bottom:12px;'>Doanh thu theo khách hàng — kỳ này so với kỳ trước</div>",
                    unsafe_allow_html=True)
        df_kh_rev = filter_bc(df_dt_theo_kh)
        if df_kh_rev is not None and not df_kh_rev.empty:
            span = (end_kd - start_kd).days + 1
            p_end = start_kd - timedelta(days=1)
            p_start = p_end - timedelta(days=span - 1)
            g_now = (df_kh_rev[(df_kh_rev["Ngày"] >= start_kd) & (df_kh_rev["Ngày"] <= end_kd)]
                     .groupby("Tên Khách Hàng", as_index=False)["Doanh Thu"].sum()
                     .rename(columns={"Doanh Thu": "Kỳ Hiện Tại"}))
            g_prev = (df_kh_rev[(df_kh_rev["Ngày"] >= p_start) & (df_kh_rev["Ngày"] <= p_end)]
                      .groupby("Tên Khách Hàng", as_index=False)["Doanh Thu"].sum()
                      .rename(columns={"Doanh Thu": "Kỳ Trước"}))
            cmp_df = pd.merge(g_now, g_prev, on="Tên Khách Hàng", how="outer").fillna(0)
            cmp_df["Tăng Trưởng"] = cmp_df["Kỳ Hiện Tại"] - cmp_df["Kỳ Trước"]
            cmp_df = cmp_df.sort_values("Kỳ Hiện Tại", ascending=False)
            st.caption(f"Kỳ này {start_kd:%d/%m} – {end_kd:%d/%m} so với kỳ trước {p_start:%d/%m} – {p_end:%d/%m} (cùng độ dài {span} ngày).")
            st.dataframe(
                cmp_df, use_container_width=True, height=320, hide_index=True,
                column_config={
                    "Kỳ Hiện Tại": st.column_config.NumberColumn("Kỳ hiện tại", format="%,d ₫"),
                    "Kỳ Trước": st.column_config.NumberColumn("Kỳ trước", format="%,d ₫"),
                    "Tăng Trưởng": st.column_config.NumberColumn("Tăng trưởng", format="%+,d ₫"),
                },
            )
        else:
            st.info("Chưa có dữ liệu doanh thu theo khách hàng.")

    st.markdown("---")
    st.markdown(
        """
        <div style="background:linear-gradient(135deg,#FF8C00,#FF5722);padding:15px 20px;border-radius:8px;
                    margin-bottom:15px;box-shadow:0 4px 10px rgba(0,0,0,0.15);">
            <h3 style="color:white;margin:0;font-weight:900;text-transform:uppercase;">📋 Khách hàng tiềm năng chờ chốt deal</h3>
            <p style="color:#FFF3CD;font-size:14px;margin:5px 0 0 0;font-style:italic;">Lọc theo các dòng có đánh dấu "tiềm năng".</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not df_kh_range.empty:
        mask_tn = df_kh_range.apply(
            lambda row: row.astype(str).str.contains("tiềm năng", case=False, na=False).any(), axis=1
        )
        df_tn = df_kh_range[mask_tn]
    else:
        df_tn = pd.DataFrame()

    if not df_tn.empty:
        drop_cols = [c for c in ["Ngày", "Khách Liên Hệ", "Khách Lên Đơn"] if c in df_tn.columns]
        styled_tn = (df_tn.drop(columns=drop_cols).style
                     .set_properties(**{"background-color": "#FFF9F0", "color": "#333333", "border-color": "#FFCC80"})
                     .set_table_styles(HEADER_STYLES))
        st.dataframe(styled_tn, use_container_width=True)
    else:
        st.info("Không có khách hàng tiềm năng trong khoảng thời gian hoặc bưu cục này.")

    st.markdown("---")
    ai_role_kd = st.radio("🤖 Đối tượng nhận báo cáo AI (kinh doanh):", ROLE_OPTIONS, horizontal=True, key="role_kd")

    if st.button("🔍 AI cố vấn kinh doanh và sales", type="primary", key="btn_ai_kd"):
        with st.spinner("AI đang phân tích hiệu suất kinh doanh..."):
            if ai_role_kd == ROLE_OPTIONS[0]:
                role_prompt = ("Nhiệm vụ: Đóng vai Giám đốc kinh doanh. Phân tích 3 phần: 1. Hiệu suất chạy số so với kỳ vọng, "
                               "2. Tỷ lệ chốt sale, 3. Chiến lược tăng trưởng doanh thu.")
            elif ai_role_kd == ROLE_OPTIONS[1]:
                role_prompt = ("Nhiệm vụ: Đóng vai Quản lý khu vực (AM). Phân tích 3 phần: 1. Tốc độ chạy doanh thu khu vực, "
                               "2. Cảnh báo rớt đơn ở phễu khách hàng tiềm năng, 3. Chỉ đạo đội sales chốt deal khẩn cấp.")
            else:
                role_prompt = ('Nhiệm vụ: Đóng vai Trợ lý kinh doanh gửi tin cho nhóm nhân viên sales. '
                               'Xưng hô thân thiện (dùng "Mình" với "Team Sales"). Phân tích 3 phần: 1. Tiến độ chạy số hôm nay, '
                               '2. Trạng thái phễu chốt sale, 3. Mẹo chốt deal khẩn cấp.')

            funnel_summary = "không có dữ liệu"
            if not df_kh_range.empty and "Trạng Thái" in df_kh_range.columns:
                fc = df_kh_range.groupby("Trạng Thái").size()
                funnel_summary = ", ".join(f"{k}: {v}" for k, v in fc.items())

            prompt_kd = f"""
Dữ liệu kinh doanh đã lọc:
- Thời gian: {start_kd:%d/%m/%Y} đến {end_kd:%d/%m/%Y}
- Bưu cục/Khu vực: {buu_cuc_kd}
- Góc nhìn báo cáo: {view_type}

Thực tế đạt được:
- KPI doanh thu kỳ này: {kpi_dt_view:,.0f} đ
- Doanh thu thực tế: {rev_now:,.0f} đ (kỳ trước: {rev_prev:,.0f} đ)
- Doanh thu dự kiến hết tháng: {forecast_month:,.0f} đ
- Phễu khách hàng mới theo trạng thái: {funnel_summary}

{role_prompt}
{CLOSING_RULE}
"""
            st.session_state.ai_kd_result = get_ai_analysis(prompt_kd)
    render_ai_and_telegram(st.session_state.ai_kd_result, "Kinh Doanh", "kd")


# ==========================================
# TAB 5 — THI ĐUA GTC
# ==========================================
with tab5:
    styled_header("Bảng xếp hạng chương trình thi đua GTC", "🏆")

    if df_ns_gtc_raw.empty:
        st.warning("Chưa có dữ liệu năng suất GTC để xếp hạng thi đua.")
    else:
        lo_t5, hi_t5 = safe_range(df_ns_gtc_raw["Ngày"])
        u1, u2 = st.columns(2)
        with u1:
            picked_t5 = st.date_input("Khoảng thời gian (thi đua):", [lo_t5, hi_t5], key="date_t5")
        with u2:
            bc_all_t5 = sorted([
                x for x in df_ns_gtc_raw["Bưu Cục"].dropna().astype(str).str.strip().unique()
                if x and x not in ("Chưa phân loại", "nan")
            ])
            buu_cuc_t5 = st.selectbox("Lọc bưu cục (thi đua):", ["Tất cả"] + bc_all_t5, key="bc_t5")

        start_t5, end_t5 = date_bounds(picked_t5, hi_t5)
        prev_ref = end_t5.replace(day=1) - timedelta(days=1)
        col_curr = f"%GTC Tháng {end_t5.month:02d}"
        col_prev = f"%GTC Tháng {prev_ref.month:02d}"
        if col_curr == col_prev:
            col_prev += " (trước)"

        base_t5 = df_ns_gtc_raw
        if buu_cuc_t5 != "Tất cả":
            base_t5 = base_t5[base_t5["Bưu Cục"].str.strip().str.lower() == buu_cuc_t5.strip().lower()]

        df_now = base_t5[(base_t5["Ngày"] >= start_t5) & (base_t5["Ngày"] <= end_t5)]
        df_before = base_t5[(base_t5["Ngày"].dt.month == prev_ref.month) & (base_t5["Ngày"].dt.year == prev_ref.year)]

        if df_now.empty:
            st.warning("Không có dữ liệu thi đua cho bưu cục hoặc khoảng thời gian này.")
        else:
            g_now = df_now.groupby("Nhân Viên", as_index=False).agg(
                {"Số đơn gán Giao": "sum", "Đơn giao tính lương": "sum"})
            g_now[col_curr] = np.where(
                g_now["Số đơn gán Giao"] > 0,
                g_now["Đơn giao tính lương"] / g_now["Số đơn gán Giao"] * 100, 0.0)

            if not df_before.empty:
                g_before = df_before.groupby("Nhân Viên", as_index=False).agg(
                    {"Số đơn gán Giao": "sum", "Đơn giao tính lương": "sum"})
                g_before[col_prev] = np.where(
                    g_before["Số đơn gán Giao"] > 0,
                    g_before["Đơn giao tính lương"] / g_before["Số đơn gán Giao"] * 100, 0.0)
                g_before = g_before[["Nhân Viên", col_prev]]
            else:
                g_before = pd.DataFrame({"Nhân Viên": [], col_prev: []})

            rank_df = pd.merge(g_now, g_before, on="Nhân Viên", how="left")
            rank_df[col_prev] = rank_df[col_prev].fillna(0.0)
            rank_df["Cải Thiện (pp)"] = rank_df[col_curr] - rank_df[col_prev]
            rank_df = rank_df.rename(columns={"Số đơn gán Giao": "Tổng Đơn Gán", "Đơn giao tính lương": "Tổng Đơn GTC"})

            rank_df["Hạng Gán"] = rank_df["Tổng Đơn Gán"].rank(method="min", ascending=False)
            rank_df["Hạng %GTC"] = rank_df[col_curr].rank(method="min", ascending=False)
            rank_df["Hạng Cải Thiện"] = rank_df["Cải Thiện (pp)"].rank(method="min", ascending=False)
            rank_df["Tổng Điểm"] = (rank_df["Hạng Gán"] + rank_df["Hạng %GTC"] + rank_df["Hạng Cải Thiện"]) / 3

            # Xếp hạng tổng: điểm thấp hơn thắng, hòa thì %GTC cao hơn thắng.
            rank_df = rank_df.sort_values(["Tổng Điểm", col_curr], ascending=[True, False]).reset_index(drop=True)
            rank_df["Xếp Hạng Tổng"] = np.arange(1, len(rank_df) + 1)
            medals = {1: "🥇", 2: "🥈", 3: "🥉"}
            rank_df["Hạng"] = rank_df["Xếp Hạng Tổng"].map(lambda r: f"{medals.get(int(r), '')} {int(r)}".strip())
            rank_df["Đạt Thưởng (≥80%)"] = np.where(rank_df[col_curr] >= 80, "✅", "❌")

            show_cols = ["Hạng", "Nhân Viên", "Tổng Đơn Gán", "Tổng Đơn GTC", col_curr, col_prev,
                         "Cải Thiện (pp)", "Hạng Gán", "Hạng %GTC", "Hạng Cải Thiện", "Tổng Điểm",
                         "Đạt Thưởng (≥80%)"]
            view_df = rank_df[show_cols]

            styled_rank = (
                view_df.style
                .format({
                    "Tổng Đơn Gán": "{:,.0f}", "Tổng Đơn GTC": "{:,.0f}",
                    col_curr: "{:.2f}%", col_prev: "{:.2f}%", "Cải Thiện (pp)": "{:+.2f}",
                    "Hạng Gán": "{:.0f}", "Hạng %GTC": "{:.0f}", "Hạng Cải Thiện": "{:.0f}",
                    "Tổng Điểm": "{:.2f}",
                })
                .background_gradient(cmap="RdYlGn", subset=["Cải Thiện (pp)"])
                .set_properties(**{"background-color": "#FFF9F2", "color": "#8A4B08", "border-color": "#FFD8A8"})
                .set_table_styles(HEADER_STYLES)
            )
            st.dataframe(styled_rank, use_container_width=True, hide_index=True)
            st.caption("Cải Thiện (pp) là chênh lệch điểm phần trăm giữa hai tháng. Xếp hạng tổng = trung bình thứ hạng của 3 tiêu chí; hạng càng nhỏ càng tốt.")

            st.markdown("---")
            styled_header("Năng suất nhân viên hằng ngày", "📅")

            daily = df_now.copy()
            daily["Ngày Str"] = daily["Ngày"].dt.strftime("%d/%m")
            g_daily = daily.groupby(["Nhân Viên", "Ngày", "Ngày Str"], as_index=False).agg(
                {"Số đơn gán Giao": "sum", "Đơn giao tính lương": "sum"})

            # pivot_table thay cho pivot: an toàn khi khoảng ngày vắt qua nhiều tháng/năm.
            pivot = g_daily.pivot_table(
                index="Nhân Viên", columns="Ngày Str",
                values=["Số đơn gán Giao", "Đơn giao tính lương"],
                aggfunc="sum", fill_value=0,
            )
            order = [pd.to_datetime(d).strftime("%d/%m") for d in sorted(g_daily["Ngày"].unique())]
            seen, order_unique = set(), []
            for d in order:
                if d not in seen:
                    seen.add(d)
                    order_unique.append(d)

            flat = pd.DataFrame(index=pivot.index)
            for d in order_unique:
                gan_col = ("Số đơn gán Giao", d)
                giao_col = ("Đơn giao tính lương", d)
                if gan_col in pivot.columns and giao_col in pivot.columns:
                    gan = pivot[gan_col]
                    giao = pivot[giao_col]
                    flat[f"Đơn gán ({d})"] = gan
                    flat[f"Đơn GTC ({d})"] = giao
                    flat[f"%GTC ({d})"] = np.where(gan > 0, giao / gan * 100, 0.0)
            flat = flat.reset_index()

            fmt_daily = {c: ("{:.2f}%" if c.startswith("%GTC") else "{:,.0f}") for c in flat.columns if c != "Nhân Viên"}
            styled_daily = (flat.style.format(fmt_daily)
                            .set_properties(**{"background-color": "#E9F6FE", "color": "#0277BD",
                                               "border-color": "#29B6F6", "font-weight": "500"})
                            .set_table_styles(HEADER_STYLES))
            st.dataframe(styled_daily, use_container_width=True, hide_index=True)

            st.markdown("---")
            ai_role_td = st.radio("🤖 Đối tượng nhận báo cáo AI (thi đua GTC):", ROLE_OPTIONS, horizontal=True, key="role_td")

            if st.button("🔍 AI đánh giá chương trình thi đua", type="primary", key="btn_ai_td"):
                with st.spinner("AI đang phân tích dữ liệu thi đua GTC..."):
                    if ai_role_td == ROLE_OPTIONS[0]:
                        role_prompt = ("Đóng vai Giám đốc vận hành. Đánh giá tổng quan hiệu suất thi đua, "
                                       "vinh danh nhân sự xuất sắc và chỉ ra rủi ro năng suất từ nhóm xếp cuối.")
                    elif ai_role_td == ROLE_OPTIONS[1]:
                        role_prompt = ("Đóng vai Quản lý khu vực (AM). Nhận xét trực diện bảng xếp hạng, "
                                       "đốc thúc cá nhân thứ hạng thấp và nêu phương án điều phối ngay.")
                    else:
                        role_prompt = ('Đóng vai Trợ lý điều phối gửi thông báo cho đội giao hàng. '
                                       'Xưng hô thân thiện (dùng "Mình" với "Anh em"). Vinh danh top đầu, '
                                       'động viên nhóm cuối đạt mốc thưởng 80%.')

                    top3 = rank_df.head(3)[["Nhân Viên", col_curr, "Tổng Điểm"]].to_dict("records")
                    bot3 = rank_df.tail(3)[["Nhân Viên", col_curr]].to_dict("records")

                    prompt_td = f"""
Dữ liệu thi đua GTC đã lọc:
- Thời gian: {start_t5:%d/%m/%Y} đến {end_t5:%d/%m/%Y}
- Bưu cục/Khu vực: {buu_cuc_t5}

Top 3 xuất sắc: {top3}
Top 3 cần cố gắng: {bot3}

LƯU Ý: Điều kiện nhận thưởng là {col_curr} ≥ 80%. Mức cải thiện tính bằng {col_curr} trừ {col_prev}, đơn vị điểm phần trăm.
Xếp hạng tổng là trung bình thứ hạng của 3 tiêu chí (số đơn gán, %GTC, mức cải thiện); hạng 1, 2, 3 là giỏi nhất.

{role_prompt}
{CLOSING_RULE}
"""
                    st.session_state.ai_td_result = get_ai_analysis(prompt_td)
            render_ai_and_telegram(st.session_state.ai_td_result, "Thi Đua GTC", "td")


# ==========================================
# TAB 6 — TRỢ LÝ AI
# ==========================================
with tab6:
    styled_header("Trợ lý AI đọc dữ liệu thời gian thực", "🤖")
    st.markdown("Hỏi bất cứ điều gì về dữ liệu tổng hợp từ các Google Sheet đã kết nối. Trợ lý chỉ đọc đúng khoảng thời gian bạn chọn bên dưới.")

    lo_ai, hi_ai = safe_range(df_vh_tongquan["Ngày"], days_back=7)
    picked_ai = st.date_input("🗓️ Khoảng thời gian AI đọc dữ liệu:", [lo_ai, hi_ai], key="date_ai")
    start_ai, end_ai = date_bounds(picked_ai, hi_ai)

    col_clear, _ = st.columns([2, 8])
    with col_clear:
        if st.button("🧹 Xóa lịch sử trò chuyện", use_container_width=True):
            st.session_state.chat_history = []
            st.rerun()

    for chat in st.session_state.chat_history:
        with st.chat_message(chat["role"]):
            st.markdown(chat["content"])

    def build_context(a, b):
        parts = []

        def add(title, df, group_cols, agg, extra=None):
            if df is None or df.empty or "Ngày" not in df.columns:
                return
            sub = df[(df["Ngày"] >= a) & (df["Ngày"] <= b)]
            if sub.empty:
                return
            g = sub.groupby(group_cols, as_index=False).agg(agg)
            if extra is not None:
                g = extra(g)
            g = g.copy()
            g["Ngày"] = pd.to_datetime(g["Ngày"]).dt.strftime("%d/%m/%Y")
            parts.append(f"\n--- {title} ---\n{g.to_csv(index=False)}")

        ops = df_vh_tongquan[(df_vh_tongquan["Ngày"] >= a) & (df_vh_tongquan["Ngày"] <= b)]
        if not ops.empty:
            g = agg_ops(ops, ["Ngày", "Bưu Cục"]).round(2)
            g["Ngày"] = g["Ngày"].dt.strftime("%d/%m/%Y")
            parts.append(f"\n--- 1. VẬN HÀNH TỔNG QUAN ---\n{g.to_csv(index=False)}")

        ops_ca = df_vh_ca[(df_vh_ca["Ngày"] >= a) & (df_vh_ca["Ngày"] <= b)]
        if not ops_ca.empty:
            g = agg_ops(ops_ca, ["Ngày", "Bưu Cục", "Ca"])[["Ngày", "Bưu Cục", "Ca", "Volume", "GTC"]].round(2)
            g["Ngày"] = g["Ngày"].dt.strftime("%d/%m/%Y")
            parts.append(f"\n--- 2. VẬN HÀNH THEO CA ---\n{g.to_csv(index=False)}")

        salary = df_nhansu.copy()
        salary["Tổng Lương"] = salary[SALARY_COMPONENTS].sum(axis=1)
        add("3. LƯƠNG VÀ ĐƠN GIÁ NHÂN SỰ", salary, ["Ngày", "Bưu Cục", "Nhân Viên"],
            {"Số Đơn": "sum", "Tổng Lương": "sum", "Đơn Giá": "mean"})

        add("4. NĂNG SUẤT GTC", df_ns_gtc_raw, ["Ngày", "Bưu Cục", "Nhân Viên"],
            {"Số đơn gán Giao": "sum", "Đơn giao tính lương": "sum"},
            extra=lambda g: g.assign(**{"%GTC": np.where(
                g["Số đơn gán Giao"] > 0, g["Đơn giao tính lương"] / g["Số đơn gán Giao"] * 100, 0).round(2)}))

        add("5. DOANH THU KINH DOANH", df_kinhdoanh, ["Ngày", "Bưu Cục"],
            {"Doanh Thu": "sum", "Khách Liên Hệ": "sum", "Khách Lên Đơn": "sum", "Doanh Thu KH Mới": "sum"})

        if not df_khachhang.empty:
            col_tn = [c for c in df_khachhang.columns if "loại khách hàng" in str(c).lower()]
            if col_tn:
                sub = df_khachhang[df_khachhang[col_tn[0]].astype(str).str.contains("tiềm năng", case=False, na=False)]
            else:
                sub = df_khachhang
            parts.append(f"\n--- 6. KHÁCH HÀNG TIỀM NĂNG (tối đa 30 dòng) ---\n{sub.head(30).to_csv(index=False)}")

        return "".join(parts) if parts else "(Không có dữ liệu trong khoảng thời gian đã chọn.)"

    if prompt_chat := st.chat_input("Hỏi AI: doanh thu tuần qua? Ai có %GTC cao nhất?"):
        st.session_state.chat_history.append({"role": "user", "content": prompt_chat})
        with st.chat_message("user"):
            st.markdown(prompt_chat)

        with st.chat_message("assistant"):
            with st.spinner("AI đang đọc dữ liệu từ các Google Sheet..."):
                context = build_context(start_ai, end_ai)
                full_prompt = f"""Bạn là Trợ lý Giám đốc vận hành logistics của GHN.
Hệ thống đã trích xuất dữ liệu thực tế từ các Google Sheet trong khoảng {start_ai:%d/%m/%Y} đến {end_ai:%d/%m/%Y}:
{context}

Câu hỏi của người quản lý: {prompt_chat}

Yêu cầu: Trả lời dựa ĐÚNG vào số liệu trên. Ngắn gọn, nêu đích danh tên nhân viên, bưu cục và số liệu cụ thể.
Nếu dữ liệu không đủ để trả lời, nói rõ là không có dữ liệu thay vì suy đoán. Trình bày bằng markdown, in đậm số liệu quan trọng."""
                answer = get_ai_analysis(full_prompt)
            st.markdown(answer)
            st.session_state.chat_history.append({"role": "assistant", "content": answer})
