"""
DASHBOARD QUẢN LÝ VẬN HÀNH & KINH DOANH — GHN
Designed by AM Phan Van Chanh

Bản v3: giao diện mới theo nhận diện GHN, có logo, bỏ phụ thuộc matplotlib.

Biến môi trường cần cấu hình:
    GEMINI_API_KEY, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, APP_USER, APP_PASS
File kèm theo: đặt logo.png cùng thư mục với app.py.
"""

import base64
import os
from datetime import datetime, timedelta
from pathlib import Path

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

st.set_page_config(
    page_title="GHN · Dashboard Vận hành & Kinh doanh",
    layout="wide",
    page_icon="🚚",
    initial_sidebar_state="expanded",
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
CACHE_TTL = 300

# ==========================================
# 2. BỘ NHỚ PHIÊN
# ==========================================
_DEFAULT_STATE = {
    "authenticated": False,
    "kpi_gtc_dict": {"Tất cả": 70.0},
    "kpi_tts_dict": {"Tất cả": 80.0},
    "kpi_odr_dict": {"Tất cả": 98.0},
    "kpi_dt_dict": {"Tất cả": 71000000.0},
    "ai_vh_result": "",
    "ai_ns_result": "",
    "ai_kpi_result": "",
    "ai_kd_result": "",
    "ai_td_result": "",
    "chat_history": [],
}
for _k, _v in _DEFAULT_STATE.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ==========================================
# 3. HỆ MÀU THEO NHẬN DIỆN GHN
# ==========================================
BRAND_ORANGE = "#FF5200"      # lấy từ logo
BRAND_ORANGE_SOFT = "#FF8547"
BRAND_BLUE = "#0B74AF"        # lấy từ dòng slogan trong logo
BRAND_BLUE_DEEP = "#075A88"
INK = "#10202B"
MUTED = "#64748B"
BORDER = "#E3E8EF"
CANVAS = "#F4F6F9"
OK = "#0E9F6E"
WARN = "#F59E0B"
BAD = "#E02424"

pio.templates["ghn"] = go.layout.Template(
    layout=dict(
        font=dict(family="Inter, Segoe UI, sans-serif", size=12.5, color="#475569"),
        title=dict(font=dict(family="Inter", size=16, color=INK), x=0.005, xanchor="left", y=0.96),
        plot_bgcolor="#FFFFFF",
        paper_bgcolor="#FFFFFF",
        hovermode="x unified",
        hoverlabel=dict(bgcolor="#FFFFFF", bordercolor=BORDER, font=dict(color=INK, size=12)),
        colorway=[BRAND_BLUE, BRAND_ORANGE, OK, "#8B5CF6", WARN, MUTED],
        margin=dict(l=48, r=24, t=64, b=40),
        xaxis=dict(showgrid=False, linecolor=BORDER, ticks="outside", tickcolor=BORDER,
                   tickfont=dict(size=11.5), title=dict(font=dict(size=12, color=MUTED))),
        yaxis=dict(showgrid=True, gridcolor="#EEF1F5", zeroline=False,
                   tickfont=dict(size=11.5), title=dict(font=dict(size=12, color=MUTED))),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1,
                    font=dict(size=11.5), bgcolor="rgba(0,0,0,0)"),
        bargap=0.28,
    )
)
pio.templates.default = "ghn"


@st.cache_data(show_spinner=False)
def get_logo_uri():
    """Đọc logo.png cạnh app.py và nhúng thẳng vào HTML, không cần hosting ảnh."""
    for name in ("logo.png", "assets/logo.png", "static/logo.png"):
        path = Path(__file__).parent / name
        if path.exists():
            return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()
    return ""


LOGO_URI = get_logo_uri()


def logo_html(height=38):
    if LOGO_URI:
        return f'<img src="{LOGO_URI}" alt="GHN" style="height:{height}px;display:block;" />'
    return f'<div class="logo-fallback" style="font-size:{height * 0.55:.0f}px;">GHN</div>'


st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Barlow+Semi+Condensed:wght@600;700&family=Inter:wght@400;500;600;700&display=swap');

    :root {{
        --brand: {BRAND_ORANGE};
        --blue: {BRAND_BLUE};
        --blue-deep: {BRAND_BLUE_DEEP};
        --ink: {INK};
        --muted: {MUTED};
        --border: {BORDER};
        --canvas: {CANVAS};
        --ok: {OK};
        --bad: {BAD};
    }}

    html, body, [class*="css"], .stApp {{
        font-family: 'Inter', system-ui, sans-serif;
        font-feature-settings: "tnum" 1, "cv05" 1;
    }}
    .stApp {{ background: var(--canvas); }}
    .block-container {{ padding-top: 1.1rem; padding-bottom: 3rem; max-width: 1500px; }}

    /* ---------- Thanh tiêu đề ---------- */
    .app-bar {{
        background: #fff; border: 1px solid var(--border); border-radius: 14px;
        padding: 16px 22px; margin-bottom: 18px; position: relative; overflow: hidden;
        display: flex; align-items: center; justify-content: space-between; gap: 20px;
        box-shadow: 0 1px 2px rgba(16,32,43,.04), 0 8px 24px -18px rgba(16,32,43,.35);
    }}
    .app-bar::after {{
        content: ""; position: absolute; left: 0; right: 0; bottom: 0; height: 3px;
        background: linear-gradient(90deg, var(--brand) 0%, var(--brand) 34%, var(--blue) 34%, var(--blue) 100%);
    }}
    .brand {{ display: flex; align-items: center; gap: 18px; }}
    .brand-divider {{ width: 1px; height: 40px; background: var(--border); }}
    .brand-title {{
        font-family: 'Barlow Semi Condensed', 'Inter', sans-serif;
        font-size: 27px; font-weight: 700; color: var(--ink);
        letter-spacing: .3px; line-height: 1.1; text-transform: uppercase;
    }}
    .brand-sub {{ font-size: 12.5px; color: var(--muted); margin-top: 3px; letter-spacing: .2px; }}
    .brand-meta {{ text-align: right; font-size: 12px; color: var(--muted); line-height: 1.6; white-space: nowrap; }}
    .brand-meta b {{ color: var(--ink); font-weight: 600; }}
    .logo-fallback {{
        font-family: 'Barlow Semi Condensed', sans-serif; font-weight: 700;
        color: #fff; background: var(--brand); padding: 4px 10px; border-radius: 6px; letter-spacing: 1px;
    }}

    /* ---------- Tiêu đề mục ---------- */
    .sec {{ margin: 26px 0 14px; }}
    .sec-eyebrow {{
        display: inline-flex; align-items: center; gap: 8px;
        font-size: 11px; font-weight: 700; letter-spacing: 1.4px;
        text-transform: uppercase; color: var(--brand);
    }}
    .sec-eyebrow::before {{ content: ""; width: 18px; height: 2px; background: var(--brand); border-radius: 2px; }}
    .sec-title {{
        font-family: 'Barlow Semi Condensed', 'Inter', sans-serif;
        font-size: 22px; font-weight: 700; color: var(--ink); margin-top: 3px; letter-spacing: .2px;
    }}

    /* ---------- Metric ---------- */
    [data-testid="stMetric"] {{
        background: #fff; border: 1px solid var(--border); border-radius: 11px;
        padding: 14px 16px 12px; transition: border-color .15s ease;
    }}
    [data-testid="stMetric"]:hover {{ border-color: #C9D3E0; }}
    [data-testid="stMetricLabel"] p {{
        font-size: 11px !important; font-weight: 600 !important; letter-spacing: .7px;
        text-transform: uppercase; color: var(--muted) !important;
    }}
    [data-testid="stMetricValue"] {{
        font-size: 1.62rem !important; font-weight: 650 !important; color: var(--ink) !important;
        letter-spacing: -.4px;
    }}
    [data-testid="stMetricDelta"] {{ font-size: .8rem !important; font-weight: 500 !important; }}

    /* ---------- Tabs ---------- */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 4px; border-bottom: 1px solid var(--border); background: transparent; padding-bottom: 0;
    }}
    .stTabs [data-baseweb="tab"] {{
        background: transparent !important; border: none !important; border-radius: 8px 8px 0 0 !important;
        padding: 11px 18px !important; color: var(--muted) !important;
        font-size: 13px !important; font-weight: 600 !important; letter-spacing: .3px;
        text-transform: none !important; box-shadow: none !important;
    }}
    .stTabs [data-baseweb="tab"]:hover {{ background: #EDF1F6 !important; color: var(--ink) !important; }}
    .stTabs [aria-selected="true"] {{
        background: #fff !important; color: var(--ink) !important;
        border: 1px solid var(--border) !important; border-bottom: 1px solid #fff !important;
        margin-bottom: -1px; box-shadow: inset 0 3px 0 0 var(--brand) !important;
    }}
    .stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] {{ display: none; }}

    /* ---------- Khối AI ---------- */
    .ai-card {{
        background: #fff; border: 1px solid var(--border); border-left: 3px solid var(--brand);
        border-radius: 10px; padding: 18px 20px; margin: 6px 0 14px;
        font-size: 14.5px; line-height: 1.68; color: #334155;
    }}
    .ai-card-head {{
        display: flex; align-items: center; gap: 8px; margin-bottom: 10px;
        font-size: 11px; font-weight: 700; letter-spacing: 1.2px; text-transform: uppercase; color: var(--brand);
    }}
    .ai-empty {{ color: var(--muted); font-style: italic; }}

    /* ---------- Nút ---------- */
    .stButton > button {{
        border-radius: 8px; font-weight: 600; font-size: 13px; border: 1px solid var(--border);
        background: #fff; color: var(--ink); transition: all .15s ease;
    }}
    .stButton > button:hover {{ border-color: var(--brand); color: var(--brand); }}
    .stButton > button[kind="primary"] {{
        background: var(--brand); border-color: var(--brand); color: #fff;
    }}
    .stButton > button[kind="primary"]:hover {{ background: #E84A00; border-color: #E84A00; color: #fff; }}

    /* ---------- Input, expander, container ---------- */
    [data-testid="stExpander"] {{ border: 1px solid var(--border); border-radius: 11px; background: #fff; }}
    [data-testid="stVerticalBlockBorderWrapper"] > div > [data-testid="stVerticalBlock"] {{ gap: .6rem; }}
    label p {{ font-size: 12.5px !important; font-weight: 600 !important; color: #475569 !important; }}
    hr {{ border-color: var(--border); }}

    /* ---------- Sidebar ---------- */
    [data-testid="stSidebar"] {{ background: #fff; border-right: 1px solid var(--border); }}
    .side-brand {{ padding: 6px 0 14px; border-bottom: 1px solid var(--border); margin-bottom: 14px; }}
    .side-row {{ display: flex; justify-content: space-between; font-size: 12.5px; padding: 5px 0; color: var(--muted); }}
    .side-row b {{ color: var(--ink); font-weight: 600; }}

    /* ---------- Đăng nhập ---------- */
    .login-wrap {{
        max-width: 430px; margin: 5vh auto 0; background: #fff; border: 1px solid var(--border);
        border-radius: 16px; padding: 34px 34px 26px; text-align: center; position: relative; overflow: hidden;
        box-shadow: 0 20px 50px -32px rgba(16,32,43,.5);
    }}
    .login-wrap::before {{
        content: ""; position: absolute; top: 0; left: 0; right: 0; height: 3px; background: var(--brand);
    }}
    .login-title {{
        font-family: 'Barlow Semi Condensed', sans-serif; font-size: 22px; font-weight: 700;
        color: var(--ink); text-transform: uppercase; letter-spacing: .5px; margin: 16px 0 4px;
    }}
    .login-sub {{ font-size: 12.5px; color: var(--muted); margin-bottom: 18px; }}

    /* ---------- Chip ---------- */
    .chip {{
        display: inline-block; padding: 3px 10px; border-radius: 999px;
        font-size: 11px; font-weight: 600; letter-spacing: .3px;
    }}
    .chip-ok {{ background: #E7F7F0; color: #0E7A56; }}
    .chip-bad {{ background: #FDECEC; color: #B42318; }}
    .caption-note {{ font-size: 11.5px; color: var(--muted); margin-top: 6px; }}

    #MainMenu, footer {{ visibility: hidden; }}
    </style>
    """,
    unsafe_allow_html=True,
)

TABLE_STYLES = [
    dict(selector="th", props=[
        ("background-color", BRAND_BLUE_DEEP), ("color", "#ffffff"),
        ("font-weight", "600"), ("font-size", "12px"),
        ("letter-spacing", ".4px"), ("text-transform", "uppercase"),
        ("text-align", "center"), ("padding", "9px 10px"),
    ]),
    dict(selector="td", props=[("font-size", "13px"), ("padding", "7px 10px")]),
]


# ==========================================
# 4. ĐĂNG NHẬP
# ==========================================
def check_login():
    st.markdown(
        f"""
        <div class="login-wrap">
            {logo_html(40)}
            <div class="login-title">Hệ thống quản trị nội bộ</div>
            <div class="login-sub">Dashboard vận hành &amp; kinh doanh</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    _, mid, _ = st.columns([1, 1.6, 1])
    with mid:
        if not APP_USER or not APP_PASS:
            st.error("Chưa cấu hình tài khoản. Đặt biến môi trường APP_USER và APP_PASS trên máy chủ rồi khởi động lại app.")
            return
        with st.form("login_form"):
            user_id = st.text_input("ID đăng nhập", placeholder="Nhập ID")
            password = st.text_input("Mật khẩu", type="password", placeholder="Nhập mật khẩu")
            if st.form_submit_button("Đăng nhập", type="primary", use_container_width=True):
                if user_id == APP_USER and password == APP_PASS:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("ID hoặc mật khẩu không đúng.")


if not st.session_state.authenticated:
    check_login()
    st.stop()

with st.sidebar:
    st.markdown(f'<div class="side-brand">{logo_html(30)}</div>', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="side-row"><span>Tài khoản</span><b>{APP_USER or "Quản trị viên"}</b></div>
        <div class="side-row"><span>Vai trò</span><b>Quản lý khu vực</b></div>
        <div class="side-row"><span>Model AI</span><b>{GEMINI_MODEL}</b></div>
        """,
        unsafe_allow_html=True,
    )
    st.divider()
    if st.button("Làm mới dữ liệu", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    if st.button("Đăng xuất", use_container_width=True):
        st.session_state.authenticated = False
        st.rerun()


# ==========================================
# 5. TIỆN ÍCH DÙNG CHUNG
# ==========================================
def section(title, eyebrow=""):
    st.markdown(
        f"""<div class="sec">
              <div class="sec-eyebrow">{eyebrow or "Báo cáo"}</div>
              <div class="sec-title">{title}</div>
            </div>""",
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
    """Trung bình có trọng số — dùng cho %GTC, %ODR, %Trả hàng."""
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


def style_table(df, formats=None, cell_colors=None):
    """Styler dùng chung. cell_colors: {ten_cot: ham_to_mau} — thay cho background_gradient
    để không cần cài matplotlib."""
    sty = df.style
    if formats:
        sty = sty.format(formats)
    sty = (sty.set_properties(**{"background-color": "#FFFFFF", "color": "#334155",
                                 "border-color": BORDER})
              .set_table_styles(TABLE_STYLES))
    if cell_colors:
        for col, fn in cell_colors.items():
            if col in df.columns:
                sty = sty.map(fn, subset=[col])
    return sty


def color_delta(val):
    """Tô màu cột chênh lệch mà không cần matplotlib."""
    try:
        x = float(val)
    except (TypeError, ValueError):
        return ""
    if x >= 5:
        return f"background-color:#D8F3E6;color:#0A6B4A;font-weight:600"
    if x > 0:
        return f"background-color:#EEF9F4;color:{OK}"
    if x == 0:
        return "color:#94A3B8"
    if x > -5:
        return "background-color:#FEF1F1;color:#C2410C"
    return f"background-color:#FBDDDD;color:{BAD};font-weight:600"


def color_pass(val):
    s = str(val)
    if "✅" in s:
        return f"background-color:#EEF9F4;color:{OK};font-weight:600"
    if "❌" in s:
        return f"background-color:#FEF1F1;color:{BAD};font-weight:600"
    return ""


def empty_fig(title):
    fig = go.Figure()
    fig.update_layout(
        title=title,
        annotations=[dict(text="Không có dữ liệu trong bộ lọc hiện tại",
                          showarrow=False, font=dict(size=13, color=MUTED))],
        xaxis=dict(visible=False), yaxis=dict(visible=False), height=340,
    )
    return fig


def draw_combo_chart(df, x_col, bar_y, line_y, title, bar_name="Sản lượng", line_name="% GTC"):
    if df is None or df.empty:
        return empty_fig(title)
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Bar(x=df[x_col], y=df[bar_y], name=bar_name,
               marker=dict(color=BRAND_BLUE, line=dict(width=0)), opacity=0.9),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(x=df[x_col], y=df[line_y], name=line_name, mode="lines+markers",
                   line=dict(color=BRAND_ORANGE, width=2.6, shape="spline", smoothing=0.5),
                   marker=dict(size=7, color="#fff", line=dict(width=2.2, color=BRAND_ORANGE))),
        secondary_y=True,
    )
    fig.update_layout(title=title, height=380)
    fig.update_yaxes(title_text=bar_name, secondary_y=False)
    fig.update_yaxes(title_text=line_name, secondary_y=True, showgrid=False, range=[0, 100], ticksuffix="%")
    return fig


def draw_rate_line(df, x_col, y_col, title, color, target=None):
    if df is None or df.empty:
        return empty_fig(title)
    fig = px.line(df, x=x_col, y=y_col, markers=True, title=title)
    fig.update_traces(
        line=dict(color=color, width=2.6, shape="spline", smoothing=0.5),
        marker=dict(size=7, color="#fff", line=dict(width=2.2, color=color)),
        fill="tozeroy", fillcolor=color.replace("#", "rgba(").replace(
            "rgba(", "rgba(") if False else "rgba(0,0,0,0)",
    )
    if target is not None:
        fig.add_hline(y=target, line_dash="dot", line_color=MUTED, line_width=1.4,
                      annotation_text="Mục tiêu", annotation_font_size=11)
    fig.update_layout(height=380)
    fig.update_yaxes(ticksuffix="%")
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


def get_ai_analysis(prompt_text):
    if not GENAI_AVAILABLE:
        return "Thiếu thư viện. Cài đặt bằng lệnh: pip install google-genai"
    client = get_genai_client()
    if client is None:
        return "Chưa cấu hình GEMINI_API_KEY trên máy chủ."
    try:
        resp = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt_text,
            config=genai_types.GenerateContentConfig(max_output_tokens=8192),
        )
        if not getattr(resp, "candidates", None):
            return "AI không trả về nội dung, có thể bị bộ lọc an toàn chặn. Thử rút gọn câu hỏi."
        text = (resp.text or "").strip()
        return text if text else "AI trả về nội dung rỗng. Thử lại sau ít phút."
    except Exception as exc:
        return f"Lỗi máy chủ Google AI: {exc}"


def send_telegram(text):
    """Telegram giới hạn 4096 ký tự mỗi tin nhắn nên phải chia nhỏ."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return False, "Chưa cấu hình TELEGRAM_TOKEN hoặc TELEGRAM_CHAT_ID."
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
    return True, f"Đã gửi {len(chunks)} tin nhắn lên nhóm."


def render_ai_and_telegram(ai_result, tab_name, key_suffix):
    body = ai_result if ai_result else (
        '<span class="ai-empty">Bấm nút phân tích ở trên để nhận nhận định từ AI.</span>'
    )
    st.markdown(
        f'<div class="ai-card"><div class="ai-card-head">Cố vấn AI · {tab_name}</div>{body}</div>',
        unsafe_allow_html=True,
    )
    if not ai_result:
        return
    if st.button(f"Gửi báo cáo {tab_name} lên nhóm Telegram", key=f"btn_tele_{key_suffix}"):
        clean = ai_result.replace("**", "").replace("*", "")
        ok, msg = send_telegram(f"BÁO CÁO {tab_name.upper()}\n\n{clean}")
        (st.success if ok else st.error)(msg)


ROLE_OPTIONS = ["Giám đốc", "Quản lý khu vực (AM)", "Nhân viên xử lý & giao hàng"]
CLOSING_RULE = (
    "Yêu cầu bắt buộc: Viết súc tích, phân bổ ý rõ ràng. Tuyệt đối không bỏ dở câu. "
    "Kết thúc báo cáo bằng dòng chữ [HOÀN TẤT BÁO CÁO]."
)


# ==========================================
# 8. THANH TIÊU ĐỀ
# ==========================================
_last_day = df_vh_tongquan["Ngày"].max() if not df_vh_tongquan.empty else pd.NaT
_last_day_txt = f"{_last_day:%d/%m/%Y}" if pd.notna(_last_day) else "—"

st.markdown(
    f"""
    <div class="app-bar">
        <div class="brand">
            {logo_html(38)}
            <div class="brand-divider"></div>
            <div>
                <div class="brand-title">Dashboard Vận hành &amp; Kinh doanh</div>
                <div class="brand-sub">Hiệu suất thực · Quyết định nhanh · AI cố vấn — Designed by AM Phan Van Chanh</div>
            </div>
        </div>
        <div class="brand-meta">
            Dữ liệu mới nhất <b>{_last_day_txt}</b><br>
            Đọc lúc <b>{datetime.now():%H:%M %d/%m}</b> · tự làm mới {CACHE_TTL // 60} phút
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "Vận hành",
    "Năng suất & Lương",
    "KPI vận hành",
    "Kinh doanh",
    "Thi đua GTC",
    "Trợ lý AI",
])

# ==========================================
# TAB 1 — VẬN HÀNH
# ==========================================
with tab1:
    lo_vh, hi_vh = safe_range(df_vh_tongquan["Ngày"])
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([1.4, 1, 1.4, 1.1])
        with c1:
            picked_vh = st.date_input("Khoảng thời gian", [lo_vh, hi_vh], key="date_vh")
        with c2:
            bc_list_vh = ["Tất cả", "Grand Total"] + [
                x for x in df_vh_tongquan["Bưu Cục"].dropna().unique() if str(x) not in ("Tất cả", "Grand Total")
            ]
            buu_cuc_vh = st.selectbox("Bưu cục", bc_list_vh, key="bc_vh")
        with c3:
            lh_opts = sorted([x for x in df_vh_ca["Loại Hàng"].dropna().unique() if str(x) != "nan"])
            loai_hang_vh = st.multiselect("Loại hàng", lh_opts, default=lh_opts, key="lh_vh")
        with c4:
            view_mode_vh = st.selectbox("Chế độ xem", ["Theo Ngày", "Theo Tuần", "Theo Tháng"], key="view_mode_vh")

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

    df_period = df_vh_tq_f.copy()
    if not df_period.empty:
        df_period["Ngày"] = to_period(df_period["Ngày"], view_mode_vh)
    df_trend = agg_ops(df_period, ["Ngày"]).sort_values("Ngày") if not df_period.empty else pd.DataFrame()

    section("Tổng quan hiệu suất giao hàng", f"Kỳ gần nhất so với kỳ trước · {view_mode_vh.lower()}")

    if not df_trend.empty:
        last = df_trend.iloc[-1]
        prev = df_trend.iloc[-2] if len(df_trend) > 1 else last

        def _v(row, col):
            return float(row[col]) if pd.notna(row[col]) else 0.0

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Sản lượng", f"{_v(last, 'Volume'):,.0f}",
                  f"{_v(last, 'Volume') - _v(prev, 'Volume'):,.0f} đơn")
        k2.metric("Tỷ lệ GTC", f"{_v(last, 'GTC'):.2f}%",
                  f"{_v(last, 'GTC') - _v(prev, 'GTC'):+.2f} pp")
        k3.metric("Tỷ lệ trả hàng", f"{_v(last, 'Trả Hàng'):.2f}%",
                  f"{_v(last, 'Trả Hàng') - _v(prev, 'Trả Hàng'):+.2f} pp", delta_color="inverse")
        k4.metric("Ontime TTS (ODR)", f"{_v(last, 'ODR'):.2f}%",
                  f"{_v(last, 'ODR') - _v(prev, 'ODR'):+.2f} pp")
        st.markdown(
            '<div class="caption-note">Các tỷ lệ phần trăm tính theo trung bình có trọng số sản lượng, không phải trung bình cộng.</div>',
            unsafe_allow_html=True,
        )
    else:
        st.info("Không có dữ liệu vận hành trong bộ lọc hiện tại.")

    g1, g2 = st.columns(2)
    with g1:
        st.plotly_chart(draw_combo_chart(df_trend, "Ngày", "Volume", "GTC",
                                         "Sản lượng và tỷ lệ GTC"), use_container_width=True)
    with g2:
        st.plotly_chart(draw_rate_line(df_trend, "Ngày", "Trả Hàng",
                                       "Tỷ lệ trả hàng", BAD), use_container_width=True)

    section("TikTok Shop và cam kết ontime", "Sàn thương mại điện tử")
    g3, g4 = st.columns(2)
    with g3:
        st.plotly_chart(
            draw_combo_chart(df_trend, "Ngày", "Volume TTS", "GTC_TTS",
                             "Sản lượng và tỷ lệ GTC TikTok Shop",
                             bar_name="Sản lượng TTS", line_name="% GTC TTS"),
            use_container_width=True,
        )
    with g4:
        st.plotly_chart(draw_rate_line(df_trend, "Ngày", "ODR",
                                       "Ontime giao TTS (ODR)", OK), use_container_width=True)

    section("Năng suất theo ca làm việc", "Điều phối kho")
    df_ca_period = df_vh_ca_f.copy()
    if not df_ca_period.empty:
        df_ca_period["Ngày"] = to_period(df_ca_period["Ngày"], view_mode_vh)
        df_ca_g = agg_ops(df_ca_period, ["Ngày", "Ca"]).sort_values(["Ngày", "Ca"])
        fmt = "%m/%Y" if view_mode_vh == "Theo Tháng" else "%d/%m"
        df_ca_g["TrụcX"] = df_ca_g["Ngày"].dt.strftime(fmt) + " · " + df_ca_g["Ca"]

        fig_ca = make_subplots(specs=[[{"secondary_y": True}]])
        bars = [BRAND_BLUE, "#5BA3D0", "#A9CBE3"]
        lines = [BRAND_ORANGE, "#B45309", OK]
        for idx, ca_name in enumerate(df_ca_g["Ca"].unique()):
            sub = df_ca_g[df_ca_g["Ca"] == ca_name]
            fig_ca.add_trace(
                go.Bar(x=sub["TrụcX"], y=sub["Volume"], name=f"Sản lượng · {ca_name}",
                       marker=dict(color=bars[idx % len(bars)], line=dict(width=0)), opacity=0.92),
                secondary_y=False,
            )
            fig_ca.add_trace(
                go.Scatter(x=sub["TrụcX"], y=sub["GTC"], name=f"%GTC · {ca_name}", mode="lines+markers",
                           line=dict(color=lines[idx % len(lines)], width=2.2),
                           marker=dict(size=6, color="#fff", line=dict(width=2, color=lines[idx % len(lines)]))),
                secondary_y=True,
            )
        fig_ca.update_layout(title="Sản lượng và tỷ lệ GTC theo ca", barmode="group", height=420)
        fig_ca.update_yaxes(title_text="Sản lượng", secondary_y=False)
        fig_ca.update_yaxes(title_text="% GTC", secondary_y=True, showgrid=False, range=[0, 100], ticksuffix="%")
        st.plotly_chart(fig_ca, use_container_width=True)
    else:
        st.info("Không có dữ liệu theo ca trong bộ lọc hiện tại.")

    st.divider()
    section("Nhận định của AI", "Cố vấn")
    ai_role_vh = st.radio("Viết cho ai đọc", ROLE_OPTIONS, horizontal=True, key="role_vh")

    if st.button("Phân tích vận hành", type="primary", key="btn_ai_vh"):
        with st.spinner("AI đang phân tích dữ liệu vận hành..."):
            if ai_role_vh == ROLE_OPTIONS[0]:
                role_prompt = ("Nhiệm vụ: Đóng vai Giám đốc vận hành. Phân tích chuyên sâu theo 3 phần: "
                               "1. Đánh giá tổng thể hiệu suất, 2. Phân tích rủi ro vĩ mô, "
                               "3. Đề xuất hành động chiến lược. Viết chuyên nghiệp, uy quyền.")
            elif ai_role_vh == ROLE_OPTIONS[1]:
                role_prompt = ("Nhiệm vụ: Đóng vai Quản lý khu vực (AM). Phân tích 3 phần: "
                               "1. Đánh giá hiệu suất vận hành của khu vực, 2. Nhận diện điểm nóng và tuyến kéo tụt số liệu, "
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

LƯU Ý: ODR là tỷ lệ cam kết giao đúng hạn với sàn TikTok Shop. Chỉ số này càng cao càng tốt; thấp là rủi ro bị phạt.
{role_prompt}
{CLOSING_RULE}
"""
            st.session_state.ai_vh_result = get_ai_analysis(prompt_vh)
    render_ai_and_telegram(st.session_state.ai_vh_result, "Vận hành", "vh")


# ==========================================
# TAB 2 — NĂNG SUẤT & LƯƠNG
# ==========================================
with tab2:
    lo_ns, hi_ns = safe_range(df_nhansu["Ngày"])
    with st.container(border=True):
        f1, f2, f3, f4, f5 = st.columns(5)
        with f1:
            picked_ns = st.date_input("Khoảng thời gian", [lo_ns, hi_ns], key="date_ns")
        with f2:
            lh_set = set(df_nhansu["Loại Hàng"].dropna().astype(str).str.strip())
            if not df_ns_gtc_raw.empty:
                lh_set |= set(df_ns_gtc_raw["Loại Hàng"].dropna().astype(str).str.strip())
            lh_all = sorted([x for x in lh_set if x and x != "nan"])
            loai_hang_ns = st.multiselect("Loại hàng", lh_all, default=[], key="lh_filter")
        with f3:
            bc_set = set(df_nhansu["Bưu Cục"].dropna().astype(str).str.strip())
            if not df_ns_gtc_raw.empty:
                bc_set |= set(df_ns_gtc_raw["Bưu Cục"].dropna().astype(str).str.strip())
            bc_all = sorted([x for x in bc_set if x and x not in ("Chưa phân loại", "nan")])
            buu_cuc_ns = st.selectbox("Bưu cục", ["Tất cả"] + bc_all, key="bc_ns_tab2")
        with f4:
            def _staff(df):
                if df.empty:
                    return set()
                if buu_cuc_ns == "Tất cả":
                    sub = df
                else:
                    sub = df[df["Bưu Cục"].str.strip().str.lower() == buu_cuc_ns.strip().lower()]
                return set(sub["Nhân Viên"].dropna().astype(str).str.strip())

            nv_all = sorted([x for x in (_staff(df_nhansu) | _staff(df_ns_gtc_raw))
                             if x and x not in ("Chưa phân loại", "nan")])
            nhan_vien_ns = st.selectbox("Nhân viên", ["Tất cả"] + nv_all, key="nv_ns_tab2")
        with f5:
            loai_luong_ns = st.multiselect("Loại lương", SALARY_COMPONENTS,
                                           default=SALARY_COMPONENTS, key="ll_filter")

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
    df_ns_f = (df_ns_base[(df_ns_base["Ngày"] >= start_ns) & (df_ns_base["Ngày"] <= end_ns)].copy()
               if not df_ns_base.empty else df_ns_base)

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

    section(f"Kỳ lương hiện tại · {curr_name}", f"Mốc tính ngày {ref_date:%d/%m/%Y}, so với {prev_name}")
    a1, a2, a3, a4 = st.columns(4)
    a1.metric("Đơn giá trung bình", f"{price_curr:,.0f} đ", f"{price_curr - price_prev:+,.0f} đ")
    a2.metric("Đơn giá kỳ trước", f"{price_prev:,.0f} đ")
    a3.metric(f"Tổng lương ({', '.join(selected_ll)})", f"{salary_curr:,.0f} đ",
              f"{salary_curr - salary_prev:+,.0f} đ")
    a4.metric("Tổng lương kỳ trước", f"{salary_prev:,.0f} đ")

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

    section("Năng suất giao hàng", "Ngày · Tuần · Tháng và theo kỳ lương")
    e1, e2, e3, e4 = st.columns(4)
    e1.metric("%GTC ngày", f"{calc_gtc(d_n):.2f}%", f"{calc_gtc(d_n) - calc_gtc(d_n1):+.2f} pp so với N-1")
    e2.metric("%GTC tuần", f"{calc_gtc(d_w):.2f}%", f"{calc_gtc(d_w) - calc_gtc(d_w1):+.2f} pp so với W-1")
    e3.metric("%GTC tháng", f"{calc_gtc(d_m):.2f}%", f"{calc_gtc(d_m) - calc_gtc(d_m1):+.2f} pp so với M-1")
    e4.metric("Đơn GTC kỳ lương", f"{total_gtc(d_kl):,.0f}",
              f"{total_gtc(d_kl) - total_gtc(d_kl_prev):+,.0f} đơn")

    h1, h2, h3, h4 = st.columns(4)
    h1.metric("Đơn GTC ngày", f"{total_gtc(d_n):,.0f}", f"{total_gtc(d_n) - total_gtc(d_n1):+,.0f}")
    h2.metric("Đơn GTC tuần", f"{total_gtc(d_w):,.0f}", f"{total_gtc(d_w) - total_gtc(d_w1):+,.0f}")
    h3.metric("Đơn GTC tháng", f"{total_gtc(d_m):,.0f}", f"{total_gtc(d_m) - total_gtc(d_m1):+,.0f}")
    h4.metric("Đơn GTC kỳ trước", f"{total_gtc(d_kl_prev):,.0f}")

    df_gtc_f = slice_period(df_gtc_base, start_ns, end_ns)
    if df_gtc_f is not None and not df_gtc_f.empty:
        df_gtc_daily = df_gtc_f.groupby("Ngày", as_index=False).agg(
            {"Đơn giao tính lương": "sum", "Số đơn gán Giao": "sum"})
        df_gtc_daily["%GTC"] = np.where(
            df_gtc_daily["Số đơn gán Giao"] > 0,
            df_gtc_daily["Đơn giao tính lương"] / df_gtc_daily["Số đơn gán Giao"] * 100, 0.0)
    else:
        df_gtc_daily = pd.DataFrame(columns=["Ngày", "Đơn giao tính lương", "Số đơn gán Giao", "%GTC"])

    who = nhan_vien_ns if nhan_vien_ns != "Tất cả" else (buu_cuc_ns if buu_cuc_ns != "Tất cả" else "toàn hệ thống")

    p1, p2 = st.columns(2)
    with p1:
        if not df_ns_f.empty:
            df_dg = df_ns_f.groupby("Ngày", as_index=False)["Đơn Giá"].mean()
            fig_dg = px.line(df_dg, x="Ngày", y="Đơn Giá", markers=True,
                             title=f"Biến động đơn giá — {who}")
            fig_dg.update_traces(line=dict(color=BRAND_ORANGE, width=2.6, shape="spline", smoothing=0.5),
                                 marker=dict(size=7, color="#fff", line=dict(width=2.2, color=BRAND_ORANGE)))
            fig_dg.update_yaxes(title_text="VNĐ")
            fig_dg.update_layout(height=360)
            st.plotly_chart(fig_dg, use_container_width=True)
        else:
            st.info("Không có dữ liệu đơn giá trong bộ lọc.")
    with p2:
        if not df_gtc_daily.empty:
            fig_ns = make_subplots(specs=[[{"secondary_y": True}]])
            fig_ns.add_trace(go.Bar(x=df_gtc_daily["Ngày"], y=df_gtc_daily["Số đơn gán Giao"],
                                    name="Đơn gán", marker=dict(color="#C7DCEA", line=dict(width=0))),
                             secondary_y=False)
            fig_ns.add_trace(go.Bar(x=df_gtc_daily["Ngày"], y=df_gtc_daily["Đơn giao tính lương"],
                                    name="Đơn GTC", marker=dict(color=BRAND_BLUE, line=dict(width=0))),
                             secondary_y=False)
            fig_ns.add_trace(go.Scatter(x=df_gtc_daily["Ngày"], y=df_gtc_daily["%GTC"], name="% GTC",
                                        mode="lines+markers", line=dict(color=BRAND_ORANGE, width=2.6),
                                        marker=dict(size=7, color="#fff", line=dict(width=2.2, color=BRAND_ORANGE))),
                             secondary_y=True)
            fig_ns.update_layout(title=f"Đơn gán, đơn giao và %GTC — {who}", barmode="overlay", height=360)
            fig_ns.update_yaxes(title_text="Số lượng", secondary_y=False)
            fig_ns.update_yaxes(title_text="% GTC", secondary_y=True, showgrid=False, range=[0, 100], ticksuffix="%")
            fig_ns.update_xaxes(tickformat="%d/%m")
            st.plotly_chart(fig_ns, use_container_width=True)
        else:
            st.info("Không có dữ liệu năng suất GTC trong bộ lọc.")

    p3, p4 = st.columns(2)
    with p3:
        if not df_ns_f.empty:
            df_lg = df_ns_f.groupby("Ngày", as_index=False)["Tổng Lương"].sum()
            fig_lg = px.bar(df_lg, x="Ngày", y="Tổng Lương", title=f"Tổng lương theo ngày — {who}",
                            color_discrete_sequence=[OK])
            fig_lg.update_yaxes(title_text="VNĐ")
            fig_lg.update_layout(height=360)
            st.plotly_chart(fig_lg, use_container_width=True)
        else:
            st.info("Không có dữ liệu lương trong bộ lọc.")
    with p4:
        if not df_gtc_daily.empty:
            fig_don = go.Figure()
            fig_don.add_trace(go.Scatter(x=df_gtc_daily["Ngày"], y=df_gtc_daily["Số đơn gán Giao"],
                                         name="Đơn gán", mode="lines+markers",
                                         line=dict(color=BRAND_ORANGE, width=2.6),
                                         marker=dict(size=7, color="#fff", line=dict(width=2.2, color=BRAND_ORANGE))))
            fig_don.add_trace(go.Scatter(x=df_gtc_daily["Ngày"], y=df_gtc_daily["Đơn giao tính lương"],
                                         name="Đơn giao", mode="lines+markers",
                                         line=dict(color=BRAND_BLUE, width=2.6),
                                         marker=dict(size=7, color="#fff", line=dict(width=2.2, color=BRAND_BLUE))))
            fig_don.update_layout(title=f"Đơn gán và đơn giao — {who}", height=360)
            fig_don.update_yaxes(title_text="Số lượng đơn")
            fig_don.update_xaxes(tickformat="%d/%m")
            st.plotly_chart(fig_don, use_container_width=True)
        else:
            st.info("Không có dữ liệu số đơn gán và giao trong bộ lọc.")

    st.divider()
    section("Nhận định của AI", "Cố vấn")
    ai_role_ns = st.radio("Viết cho ai đọc", ROLE_OPTIONS, horizontal=True, key="role_ns")

    if st.button("Phân tích nhân sự và chi phí", type="primary", key="btn_ai_ns"):
        with st.spinner("AI đang phân tích dữ liệu năng suất..."):
            if ai_role_ns == ROLE_OPTIONS[0]:
                role_prompt = ("Nhiệm vụ: Đóng vai Giám đốc nhân sự. Đánh giá 3 phần: 1. Năng suất tổng thể, "
                               "2. Quỹ lương, chi phí và đơn giá, 3. Đề xuất chính sách nhân sự cấp quản lý.")
            elif ai_role_ns == ROLE_OPTIONS[1]:
                role_prompt = ("Nhiệm vụ: Đóng vai Quản lý khu vực (AM). Đánh giá 3 phần: 1. Năng suất giao hàng khu vực, "
                               "2. Cảnh báo rủi ro quỹ lương và đơn giá, 3. Chỉ đạo phân tuyến lại và ép năng suất. "
                               "Viết dứt khoát, thực tiễn.")
            else:
                role_prompt = ('Nhiệm vụ: Đóng vai Trợ lý nhân sự gửi thông báo cho nhóm nhân viên xử lý kho và giao hàng. '
                               'Xưng hô thân thiện (dùng "Mình" với "Anh em"). Chia 3 phần: 1. Ghi nhận công sức, '
                               '2. Tình hình thu nhập và đơn giá, 3. Bí kíp tăng thu nhập.')

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
    render_ai_and_telegram(st.session_state.ai_ns_result, "Năng suất & Nhân sự", "ns")


# ==========================================
# TAB 3 — KPI VẬN HÀNH
# ==========================================
with tab3:
    bc_list_kpi = ["Tất cả", "Grand Total"] + [
        x for x in df_vh_tongquan["Bưu Cục"].dropna().unique() if str(x) not in ("Tất cả", "Grand Total")
    ]

    with st.expander("Điều chỉnh mục tiêu KPI (lưu riêng theo từng khu vực)", expanded=False):
        target_bc = st.selectbox("Khu vực cần cài đặt", bc_list_kpi, key="set_bc_kpi_tab3")
        st.session_state.kpi_gtc_dict.setdefault(target_bc, 70.0)
        st.session_state.kpi_tts_dict.setdefault(target_bc, 80.0)
        st.session_state.kpi_odr_dict.setdefault(target_bc, 98.0)
        q1, q2, q3 = st.columns(3)
        with q1:
            st.session_state.kpi_gtc_dict[target_bc] = st.number_input(
                "KPI %GTC", 0.0, 100.0, float(st.session_state.kpi_gtc_dict[target_bc]), 0.5)
        with q2:
            st.session_state.kpi_tts_dict[target_bc] = st.number_input(
                "KPI %GTC TikTok Shop", 0.0, 100.0, float(st.session_state.kpi_tts_dict[target_bc]), 0.5)
        with q3:
            st.session_state.kpi_odr_dict[target_bc] = st.number_input(
                "KPI ontime giao TTS (ODR)", 0.0, 100.0, float(st.session_state.kpi_odr_dict[target_bc]), 0.5)

    lo_k, hi_k = safe_range(df_vh_tongquan["Ngày"])
    with st.container(border=True):
        r1, r2 = st.columns(2)
        with r1:
            picked_kpi = st.date_input("Khoảng thời gian", [lo_k, hi_k], key="date_kpi")
        with r2:
            buu_cuc_kpi = st.selectbox("Bưu cục", bc_list_kpi, key="bc_kpi")

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
        target = max(float(target), 0.5)  # tránh dải steps trùng nhau khi target bằng 0
        reached = float(value) >= target
        fig = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=float(value),
            domain={"x": [0, 1], "y": [0, 1]},
            title={"text": title, "font": {"size": 14, "color": MUTED}},
            number={"suffix": "%", "font": {"size": 34, "color": INK}, "valueformat": ".2f"},
            delta={"reference": target, "suffix": " pp",
                   "increasing": {"color": OK}, "decreasing": {"color": BAD},
                   "font": {"size": 13}},
            gauge={
                "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": BORDER,
                         "tickfont": {"size": 10, "color": MUTED}},
                "bar": {"color": OK if reached else BRAND_ORANGE, "thickness": 0.7},
                "bgcolor": "#F1F4F8",
                "steps": [{"range": [0, 100], "color": "#F1F4F8"}],
                "threshold": {"line": {"color": INK, "width": 2.5}, "thickness": 0.95, "value": target},
                "borderwidth": 0,
            },
        ))
        fig.update_layout(height=250, margin=dict(l=24, r=24, t=52, b=8))
        return fig

    section("Mức độ hoàn thành KPI", f"{buu_cuc_kpi} · {start_k:%d/%m} – {end_k:%d/%m/%Y}")
    s1, s2, s3 = st.columns(3)
    for col, (name, val, tgt) in zip(
        (s1, s2, s3),
        [("Tỷ lệ GTC chung", actual_gtc, kpi_gtc),
         ("Tỷ lệ GTC TikTok Shop", actual_tts, kpi_tts),
         ("Ontime giao TTS (ODR)", actual_odr, kpi_odr)],
    ):
        with col:
            with st.container(border=True):
                st.plotly_chart(create_gauge(name, val, tgt), use_container_width=True)
                chip = "chip-ok" if val >= tgt else "chip-bad"
                label = "Đạt KPI" if val >= tgt else "Chưa đạt KPI"
                st.markdown(
                    f'<div style="text-align:center;margin-top:-8px;">'
                    f'<span class="chip {chip}">{label}</span> '
                    f'<span class="caption-note">mục tiêu {tgt:.1f}%</span></div>',
                    unsafe_allow_html=True,
                )

    section("Theo dõi KPI theo ngày", "Bảng chi tiết")
    df_kpi_day = agg_ops(df_kpi_f, ["Ngày"]).sort_values("Ngày") if not df_kpi_f.empty else pd.DataFrame()
    if not df_kpi_day.empty:
        tbl = df_kpi_day[["Ngày", "Volume", "GTC", "GTC_TTS", "ODR"]].copy()
        tbl["% Đạt KPI GTC"] = (tbl["GTC"] / kpi_gtc * 100) if kpi_gtc > 0 else 0.0
        tbl["Kết quả"] = np.where(tbl["GTC"] >= kpi_gtc, "✅ Đạt", "❌ Chưa đạt")
        st.dataframe(
            tbl, use_container_width=True, hide_index=True, height=380,
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

    st.divider()
    section("Nhận định của AI", "Cố vấn")
    ai_role_kpi = st.radio("Viết cho ai đọc", ROLE_OPTIONS, horizontal=True, key="role_kpi")

    if st.button("Đánh giá mức độ đạt KPI", type="primary", key="btn_ai_kpi"):
        with st.spinner("AI đang đối chiếu số liệu với mục tiêu KPI..."):
            if ai_role_kpi == ROLE_OPTIONS[0]:
                role_prompt = ("Đóng vai Giám đốc kiểm soát. Nêu: 1. Tình hình đạt hoặc trượt KPI ở góc nhìn vĩ mô, "
                               "2. Cảnh báo rủi ro hệ thống, 3. Yêu cầu hành động khẩn cấp cho quản lý cấp trung.")
            elif ai_role_kpi == ROLE_OPTIONS[1]:
                role_prompt = ("Đóng vai Quản lý khu vực (AM). Nêu: 1. Mức độ hoàn thành KPI so với mục tiêu, "
                               "2. Các chỉ số đang báo động, đặc biệt là ODR, "
                               "3. Giao việc khẩn cho nhân viên kho và giao hàng.")
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

LƯU Ý: ODR là tỷ lệ cam kết giao đúng hạn với sàn TikTok Shop. ODR thực tế phải lớn hơn hoặc bằng mục tiêu mới là hoàn thành; thấp hơn là trượt KPI.

{role_prompt}
{CLOSING_RULE}
"""
            st.session_state.ai_kpi_result = get_ai_analysis(prompt_kpi)
    render_ai_and_telegram(st.session_state.ai_kpi_result, "KPI vận hành", "kpi")


# ==========================================
# TAB 4 — KINH DOANH
# ==========================================
with tab4:
    bc_list_kd = ["Tất cả", "Grand Total"] + [
        x for x in df_kinhdoanh["Bưu Cục"].dropna().unique() if str(x) not in ("Tất cả", "Grand Total")
    ]

    with st.expander("Điều chỉnh mục tiêu doanh thu (lưu riêng theo từng khu vực)", expanded=False):
        target_bc_kd = st.selectbox("Khu vực cần cài đặt", bc_list_kd, key="set_bc_kd_tab4")
        st.session_state.kpi_dt_dict.setdefault(target_bc_kd, 71000000.0)
        st.session_state.kpi_dt_dict[target_bc_kd] = st.number_input(
            "Mục tiêu doanh thu VNĐ mỗi tháng",
            min_value=0.0, value=float(st.session_state.kpi_dt_dict[target_bc_kd]), step=1000000.0)

    lo_kd, hi_kd = safe_range(df_kinhdoanh["Ngày"], days_back=7)
    with st.container(border=True):
        t1, t2, t3 = st.columns(3)
        with t1:
            picked_kd = st.date_input("Khoảng thời gian", [lo_kd, hi_kd], key="date_kd")
        with t2:
            buu_cuc_kd = st.selectbox("Bưu cục", bc_list_kd, key="bc_kd")
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
        label_prev = "Doanh thu hôm trước"
    elif view_type == "Theo Tuần":
        a_now = end_kd - timedelta(days=end_kd.weekday())
        b_now = a_now + timedelta(days=6)
        a_prev, b_prev = a_now - timedelta(days=7), a_now - timedelta(days=1)
        label_prev = "Doanh thu tuần trước"
    else:
        a_now = end_kd.replace(day=1)
        b_now = month_end(a_now)
        a_prev = (a_now - timedelta(days=1)).replace(day=1)
        b_prev = a_now - timedelta(days=1)
        label_prev = "Doanh thu tháng trước"

    rev_now = (float(df_kd_bc[(df_kd_bc["Ngày"] >= a_now) & (df_kd_bc["Ngày"] <= b_now)]["Doanh Thu"].sum())
               if not df_kd_bc.empty else 0.0)
    rev_prev = (float(df_kd_bc[(df_kd_bc["Ngày"] >= a_prev) & (df_kd_bc["Ngày"] <= b_prev)]["Doanh Thu"].sum())
                if not df_kd_bc.empty else 0.0)

    days_span = max((b_now - a_now).days + 1, 1)
    days_in_month = month_end(end_kd.replace(day=1)).day
    forecast_month = rev_now / days_span * days_in_month

    kpi_dt = float(st.session_state.kpi_dt_dict.get(buu_cuc_kd, 71000000.0))
    if view_type == "Theo Ngày":
        kpi_dt_view = kpi_dt / days_in_month
    elif view_type == "Theo Tuần":
        kpi_dt_view = kpi_dt / days_in_month * 7
    else:
        kpi_dt_view = kpi_dt

    section("Hiệu suất doanh thu", f"{buu_cuc_kd} · {view_type.lower()}")
    v1, v2, v3, v4 = st.columns(4)
    delta_kpi = (f"{(rev_now - kpi_dt_view) / kpi_dt_view * 100:+.1f}% so với KPI"
                 if kpi_dt_view > 0 else "Chưa đặt KPI")
    v1.metric("Doanh thu hiện tại", f"{rev_now:,.0f} đ", delta_kpi)
    v2.metric(label_prev, f"{rev_prev:,.0f} đ", f"{rev_now - rev_prev:+,.0f} đ")
    v3.metric("Mục tiêu KPI kỳ này", f"{kpi_dt_view:,.0f} đ")
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
            fig_rev = px.bar(plot, x="Ngày", y="Doanh Thu", title=f"Doanh thu so với KPI — {buu_cuc_kd}",
                             color_discrete_sequence=[BRAND_BLUE])
            fig_rev.add_hline(y=kpi_dt_view, line_dash="dot", line_color=BRAND_ORANGE, line_width=2,
                              annotation_text="KPI mục tiêu", annotation_font_size=11,
                              annotation_font_color=BRAND_ORANGE)
            fig_rev.update_layout(height=380)
            st.plotly_chart(fig_rev, use_container_width=True)
        else:
            st.info("Không có dữ liệu doanh thu trong bộ lọc.")
    with k2:
        if not df_kh_range.empty and "Trạng Thái" in df_kh_range.columns:
            funnel = (df_kh_range.groupby("Trạng Thái").size().reset_index(name="Số Lượng")
                      .sort_values("Số Lượng", ascending=False))
            fig_fn = go.Figure(go.Funnel(
                y=funnel["Trạng Thái"], x=funnel["Số Lượng"], textinfo="value+percent initial",
                textfont=dict(size=12),
                marker={"color": [BRAND_ORANGE, "#FF7A33", "#FFA070", BRAND_BLUE, "#7FB3D3"],
                        "line": {"width": 0}},
                connector={"line": {"color": BORDER, "width": 1}},
            ))
            fig_fn.update_layout(title="Phễu trạng thái khách hàng mới", hovermode="closest", height=380)
            st.plotly_chart(fig_fn, use_container_width=True)
        else:
            st.info("Không tìm thấy cột Trạng Thái trong dữ liệu khách hàng.")

    k3, k4 = st.columns(2)
    with k3:
        section("Doanh thu khách hàng mới", "Chi tiết")
        if not df_moi_range.empty:
            keys = [c for c in ["Mã KH", "Tên KH"] if c in df_moi_range.columns]
            if keys:
                tbl_new = (df_moi_range.groupby(keys, as_index=False)
                           .agg({"Doanh Thu": "sum", "Volume": "sum"})
                           .sort_values("Doanh Thu", ascending=False))
                st.dataframe(
                    tbl_new, use_container_width=True, height=330, hide_index=True,
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
        section("Doanh thu theo khách hàng", "Kỳ này so với kỳ trước")
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
            st.dataframe(
                cmp_df, use_container_width=True, height=300, hide_index=True,
                column_config={
                    "Kỳ Hiện Tại": st.column_config.NumberColumn("Kỳ hiện tại", format="%,d ₫"),
                    "Kỳ Trước": st.column_config.NumberColumn("Kỳ trước", format="%,d ₫"),
                    "Tăng Trưởng": st.column_config.NumberColumn("Tăng trưởng", format="%+,d ₫"),
                },
            )
            st.markdown(
                f'<div class="caption-note">Kỳ này {start_kd:%d/%m} – {end_kd:%d/%m} so với kỳ trước '
                f'{p_start:%d/%m} – {p_end:%d/%m}, cùng độ dài {span} ngày.</div>',
                unsafe_allow_html=True,
            )
        else:
            st.info("Chưa có dữ liệu doanh thu theo khách hàng.")

    section("Khách hàng tiềm năng chờ chốt deal", "Danh sách theo dõi")
    if not df_kh_range.empty:
        mask_tn = df_kh_range.apply(
            lambda row: row.astype(str).str.contains("tiềm năng", case=False, na=False).any(), axis=1)
        df_tn = df_kh_range[mask_tn]
    else:
        df_tn = pd.DataFrame()

    if not df_tn.empty:
        drop_cols = [c for c in ["Ngày", "Khách Liên Hệ", "Khách Lên Đơn"] if c in df_tn.columns]
        st.dataframe(style_table(df_tn.drop(columns=drop_cols)), use_container_width=True, hide_index=True)
    else:
        st.info("Không có khách hàng tiềm năng trong khoảng thời gian hoặc bưu cục này.")

    st.divider()
    section("Nhận định của AI", "Cố vấn")
    ai_role_kd = st.radio("Viết cho ai đọc", ROLE_OPTIONS, horizontal=True, key="role_kd")

    if st.button("Cố vấn kinh doanh và sales", type="primary", key="btn_ai_kd"):
        with st.spinner("AI đang phân tích hiệu suất kinh doanh..."):
            if ai_role_kd == ROLE_OPTIONS[0]:
                role_prompt = ("Nhiệm vụ: Đóng vai Giám đốc kinh doanh. Phân tích 3 phần: "
                               "1. Hiệu suất chạy số so với kỳ vọng, 2. Tỷ lệ chốt sale, "
                               "3. Chiến lược tăng trưởng doanh thu.")
            elif ai_role_kd == ROLE_OPTIONS[1]:
                role_prompt = ("Nhiệm vụ: Đóng vai Quản lý khu vực (AM). Phân tích 3 phần: "
                               "1. Tốc độ chạy doanh thu khu vực, 2. Cảnh báo rớt đơn ở phễu khách hàng tiềm năng, "
                               "3. Chỉ đạo đội sales chốt deal khẩn cấp.")
            else:
                role_prompt = ('Nhiệm vụ: Đóng vai Trợ lý kinh doanh gửi tin cho nhóm nhân viên sales. '
                               'Xưng hô thân thiện (dùng "Mình" với "Team Sales"). Phân tích 3 phần: '
                               '1. Tiến độ chạy số hôm nay, 2. Trạng thái phễu chốt sale, 3. Mẹo chốt deal khẩn cấp.')

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
    render_ai_and_telegram(st.session_state.ai_kd_result, "Kinh doanh", "kd")


# ==========================================
# TAB 5 — THI ĐUA GTC
# ==========================================
with tab5:
    if df_ns_gtc_raw.empty:
        st.warning("Chưa có dữ liệu năng suất GTC để xếp hạng thi đua.")
    else:
        lo_t5, hi_t5 = safe_range(df_ns_gtc_raw["Ngày"])
        with st.container(border=True):
            u1, u2 = st.columns(2)
            with u1:
                picked_t5 = st.date_input("Khoảng thời gian", [lo_t5, hi_t5], key="date_t5")
            with u2:
                bc_all_t5 = sorted([
                    x for x in df_ns_gtc_raw["Bưu Cục"].dropna().astype(str).str.strip().unique()
                    if x and x not in ("Chưa phân loại", "nan")
                ])
                buu_cuc_t5 = st.selectbox("Bưu cục", ["Tất cả"] + bc_all_t5, key="bc_t5")

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
        df_before = base_t5[(base_t5["Ngày"].dt.month == prev_ref.month) &
                            (base_t5["Ngày"].dt.year == prev_ref.year)]

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
            rank_df = rank_df.rename(columns={"Số đơn gán Giao": "Tổng Đơn Gán",
                                              "Đơn giao tính lương": "Tổng Đơn GTC"})

            rank_df["Hạng Gán"] = rank_df["Tổng Đơn Gán"].rank(method="min", ascending=False)
            rank_df["Hạng %GTC"] = rank_df[col_curr].rank(method="min", ascending=False)
            rank_df["Hạng Cải Thiện"] = rank_df["Cải Thiện (pp)"].rank(method="min", ascending=False)
            rank_df["Tổng Điểm"] = (rank_df["Hạng Gán"] + rank_df["Hạng %GTC"] + rank_df["Hạng Cải Thiện"]) / 3

            # Điểm thấp hơn thắng; hòa điểm thì %GTC cao hơn thắng.
            rank_df = rank_df.sort_values(["Tổng Điểm", col_curr], ascending=[True, False]).reset_index(drop=True)
            rank_df["Xếp Hạng Tổng"] = np.arange(1, len(rank_df) + 1)
            medals = {1: "🥇", 2: "🥈", 3: "🥉"}
            rank_df["Hạng"] = rank_df["Xếp Hạng Tổng"].map(lambda r: f"{medals.get(int(r), '')} {int(r)}".strip())
            rank_df["Đạt Thưởng (≥80%)"] = np.where(rank_df[col_curr] >= 80, "✅", "❌")

            n_pass = int((rank_df[col_curr] >= 80).sum())
            avg_gtc = float(np.average(rank_df[col_curr], weights=rank_df["Tổng Đơn Gán"].replace(0, np.nan).fillna(1)))
            section("Bảng xếp hạng thi đua GTC",
                    f"{buu_cuc_t5} · {start_t5:%d/%m} – {end_t5:%d/%m/%Y}")
            b1, b2, b3, b4 = st.columns(4)
            b1.metric("Số nhân viên tham gia", f"{len(rank_df):,d}")
            b2.metric("Đạt mốc thưởng 80%", f"{n_pass:,d}", f"{n_pass / max(len(rank_df), 1) * 100:.0f}% đội")
            b3.metric("%GTC bình quân", f"{avg_gtc:.2f}%")
            b4.metric("Tổng đơn GTC", f"{rank_df['Tổng Đơn GTC'].sum():,.0f}")

            show_cols = ["Hạng", "Nhân Viên", "Tổng Đơn Gán", "Tổng Đơn GTC", col_curr, col_prev,
                         "Cải Thiện (pp)", "Hạng Gán", "Hạng %GTC", "Hạng Cải Thiện", "Tổng Điểm",
                         "Đạt Thưởng (≥80%)"]
            view_df = rank_df[show_cols]

            styled_rank = style_table(
                view_df,
                formats={
                    "Tổng Đơn Gán": "{:,.0f}", "Tổng Đơn GTC": "{:,.0f}",
                    col_curr: "{:.2f}%", col_prev: "{:.2f}%", "Cải Thiện (pp)": "{:+.2f}",
                    "Hạng Gán": "{:.0f}", "Hạng %GTC": "{:.0f}", "Hạng Cải Thiện": "{:.0f}",
                    "Tổng Điểm": "{:.2f}",
                },
                cell_colors={"Cải Thiện (pp)": color_delta, "Đạt Thưởng (≥80%)": color_pass},
            )
            st.dataframe(styled_rank, use_container_width=True, hide_index=True)
            st.markdown(
                '<div class="caption-note">Cải Thiện (pp) là chênh lệch điểm phần trăm giữa hai tháng. '
                'Xếp hạng tổng lấy trung bình thứ hạng của ba tiêu chí, hạng càng nhỏ càng tốt.</div>',
                unsafe_allow_html=True,
            )

            section("Năng suất nhân viên hằng ngày", "Bảng chi tiết")
            daily = df_now.copy()
            daily["Ngày Str"] = daily["Ngày"].dt.strftime("%d/%m")
            g_daily = daily.groupby(["Nhân Viên", "Ngày", "Ngày Str"], as_index=False).agg(
                {"Số đơn gán Giao": "sum", "Đơn giao tính lương": "sum"})

            # pivot_table thay cho pivot: an toàn khi khoảng ngày vắt qua nhiều tháng hoặc nhiều năm.
            pivot = g_daily.pivot_table(
                index="Nhân Viên", columns="Ngày Str",
                values=["Số đơn gán Giao", "Đơn giao tính lương"],
                aggfunc="sum", fill_value=0)

            order, seen = [], set()
            for d in sorted(g_daily["Ngày"].unique()):
                s = pd.to_datetime(d).strftime("%d/%m")
                if s not in seen:
                    seen.add(s)
                    order.append(s)

            flat = pd.DataFrame(index=pivot.index)
            for d in order:
                gan_col, giao_col = ("Số đơn gán Giao", d), ("Đơn giao tính lương", d)
                if gan_col in pivot.columns and giao_col in pivot.columns:
                    gan, giao = pivot[gan_col], pivot[giao_col]
                    flat[f"Đơn gán ({d})"] = gan
                    flat[f"Đơn GTC ({d})"] = giao
                    flat[f"%GTC ({d})"] = np.where(gan > 0, giao / gan * 100, 0.0)
            flat = flat.reset_index()

            fmt_daily = {c: ("{:.2f}%" if c.startswith("%GTC") else "{:,.0f}")
                         for c in flat.columns if c != "Nhân Viên"}
            st.dataframe(style_table(flat, formats=fmt_daily), use_container_width=True, hide_index=True)

            st.divider()
            section("Nhận định của AI", "Cố vấn")
            ai_role_td = st.radio("Viết cho ai đọc", ROLE_OPTIONS, horizontal=True, key="role_td")

            if st.button("Đánh giá chương trình thi đua", type="primary", key="btn_ai_td"):
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
- Số nhân viên: {len(rank_df)}, trong đó {n_pass} người đạt mốc thưởng.

Top 3 xuất sắc: {top3}
Top 3 cần cố gắng: {bot3}

LƯU Ý: Điều kiện nhận thưởng là {col_curr} ≥ 80%. Mức cải thiện tính bằng {col_curr} trừ {col_prev}, đơn vị điểm phần trăm.
Xếp hạng tổng là trung bình thứ hạng của ba tiêu chí gồm số đơn gán, %GTC và mức cải thiện; hạng 1, 2, 3 là giỏi nhất.

{role_prompt}
{CLOSING_RULE}
"""
                    st.session_state.ai_td_result = get_ai_analysis(prompt_td)
            render_ai_and_telegram(st.session_state.ai_td_result, "Thi đua GTC", "td")


# ==========================================
# TAB 6 — TRỢ LÝ AI
# ==========================================
with tab6:
    section("Trợ lý AI đọc dữ liệu thời gian thực", "Hỏi đáp")
    st.markdown(
        '<div class="caption-note">Trợ lý chỉ đọc dữ liệu trong khoảng thời gian bạn chọn bên dưới, '
        'tổng hợp từ tất cả Google Sheet đã kết nối.</div>',
        unsafe_allow_html=True,
    )

    lo_ai, hi_ai = safe_range(df_vh_tongquan["Ngày"], days_back=7)
    with st.container(border=True):
        ca1, ca2 = st.columns([3, 1])
        with ca1:
            picked_ai = st.date_input("Khoảng thời gian AI đọc dữ liệu", [lo_ai, hi_ai], key="date_ai")
        with ca2:
            st.write("")
            if st.button("Xóa lịch sử trò chuyện", use_container_width=True):
                st.session_state.chat_history = []
                st.rerun()
    start_ai, end_ai = date_bounds(picked_ai, hi_ai)

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
                sub = df_khachhang[df_khachhang[col_tn[0]].astype(str)
                                   .str.contains("tiềm năng", case=False, na=False)]
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

Yêu cầu: Trả lời dựa đúng vào số liệu trên. Ngắn gọn, nêu đích danh tên nhân viên, bưu cục và số liệu cụ thể.
Nếu dữ liệu không đủ để trả lời, nói rõ là không có dữ liệu thay vì suy đoán. Trình bày bằng markdown, in đậm số liệu quan trọng."""
                answer = get_ai_analysis(full_prompt)
            st.markdown(answer)
            st.session_state.chat_history.append({"role": "assistant", "content": answer})
