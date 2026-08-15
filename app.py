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


# Logo GHN gốc đã nhúng sẵn dạng base64 — app chạy được kể cả khi chỉ upload mỗi app.py.
LOGO_EMBEDDED_B64 = "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"


@st.cache_data(show_spinner=False)
def get_logo_uri():
    """Ưu tiên file logo.png cạnh app.py; nếu không có thì dùng bản nhúng sẵn."""
    for name in ("logo.png", "assets/logo.png", "static/logo.png"):
        try:
            path = Path(__file__).parent / name
            if path.exists():
                return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()
        except Exception:
            continue
    return "data:image/png;base64," + LOGO_EMBEDDED_B64


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
