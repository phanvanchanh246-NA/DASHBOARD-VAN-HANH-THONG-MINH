"""
TRUNG TÂM VẬN HÀNH CHIẾN LƯỢC — GHN
Dashboard Streamlit: Vận hành · Kinh doanh · Năng suất & Lương · KPI · AI cố vấn

Chạy local:
    pip install -r requirements.txt
    streamlit run app.py

Chạy trên Render:
    streamlit run app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true

Biến môi trường (KHÔNG fix cứng key vào code):
    GEMINI_API_KEY      — khóa Google Gemini
    TELEGRAM_TOKEN      — token bot Telegram (tùy chọn)
    TELEGRAM_CHAT_ID    — id nhóm nhận báo cáo (tùy chọn)
    ADMIN_PASS          — mật khẩu tài khoản ADMIN (tùy chọn)
    USER_PASS           — mật khẩu tài khoản USER  (tùy chọn)
"""

from __future__ import annotations

import html as html_lib
import os
import re
import unicodedata
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


# ═══════════════════════════════════════════════════════════════════════
# 0. CẤU HÌNH TRANG
# ═══════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Trung Tâm Vận Hành Chiến Lược — GHN",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Bảng màu chuẩn theo yêu cầu ────────────────────────────────────────
PRIMARY = "#0077B6"   # Xanh da trời đậm — tiêu đề
ACCENT = "#FF8C00"    # Cam — nút bấm, số liệu nổi bật
SUCCESS = "#28A745"   # Xanh lá — tăng trưởng, vượt KPI
DANGER = "#DC3545"    # Đỏ — giảm, không đạt KPI
BG = "#FFFFFF"        # Trắng — nền
TEXT = "#212529"
MUTED = "#6C757D"
LINE = "#E9ECEF"
PRIMARY_SOFT = "#CFE8F5"

# ── Khóa API lấy từ biến môi trường ────────────────────────────────────
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
ADMIN_PASS = os.environ.get("ADMIN_PASS", "ghn@admin").strip()
USER_PASS = os.environ.get("USER_PASS", "ghn@user").strip()

GEMINI_MODEL = "gemini-3.6-flash"
CACHE_TTL = 300

# ── 12 nguồn dữ liệu Google Sheets ─────────────────────────────────────
SHEET_LINKS: dict[str, str] = {
    # Vận hành
    "gtc_tong": "https://docs.google.com/spreadsheets/d/1lJt4ZXVjIPoUYZF73nsPmVfziJSBXBISUWU1ldSxWH4/edit?gid=1806026577",
    "sl_theo_ca": "https://docs.google.com/spreadsheets/d/1lJt4ZXVjIPoUYZF73nsPmVfziJSBXBISUWU1ldSxWH4/edit?gid=2040493559",
    "tra_hang": "https://docs.google.com/spreadsheets/d/1lJt4ZXVjIPoUYZF73nsPmVfziJSBXBISUWU1ldSxWH4/edit?gid=452321599",
    "gtb_thu_tien": "https://docs.google.com/spreadsheets/d/1lJt4ZXVjIPoUYZF73nsPmVfziJSBXBISUWU1ldSxWH4/edit?gid=454179383",
    "gtc_tts": "https://docs.google.com/spreadsheets/d/1lJt4ZXVjIPoUYZF73nsPmVfziJSBXBISUWU1ldSxWH4/edit?gid=1164899523",
    "odr_tts": "https://docs.google.com/spreadsheets/d/1lJt4ZXVjIPoUYZF73nsPmVfziJSBXBISUWU1ldSxWH4/edit?gid=1013193026",
    # KPI
    "kpi": "https://docs.google.com/spreadsheets/d/1lJt4ZXVjIPoUYZF73nsPmVfziJSBXBISUWU1ldSxWH4/edit?gid=1344197558",
    # Kinh doanh
    "doanh_thu": "https://docs.google.com/spreadsheets/d/1dEC78RcXYcA7e2SVFmjhOfuP-DY57_FXkOCpRpln4vY/edit?gid=339323317",
    "kh_moi": "https://docs.google.com/spreadsheets/d/1dEC78RcXYcA7e2SVFmjhOfuP-DY57_FXkOCpRpln4vY/edit?gid=949412123",
    "pheu_kh": "https://docs.google.com/spreadsheets/d/1dEC78RcXYcA7e2SVFmjhOfuP-DY57_FXkOCpRpln4vY/edit?gid=151781423",
    # Năng suất & Lương
    "ns_luong": "https://docs.google.com/spreadsheets/d/1OemA7cIZM-5AAvsnQuQphNArKw43de27W75Z-Ri6BcQ/edit?gid=2000227799",
    "ns_gtc": "https://docs.google.com/spreadsheets/d/1OemA7cIZM-5AAvsnQuQphNArKw43de27W75Z-Ri6BcQ/edit?gid=1695228663",
}

SALARY_PARTS = {
    "LHH LTC": "Lương hoa hồng lấy thành công",
    "LHH GTC": "Lương hoa hồng giao thành công",
    "LHH GTBTT": "Lương hoa hồng giao thất bại thu tiền",
}


# ═══════════════════════════════════════════════════════════════════════
# 1. GIAO DIỆN — CSS TÙY CHỈNH
# ═══════════════════════════════════════════════════════════════════════
pio.templates["ghn"] = go.layout.Template(layout=dict(
    font=dict(family="Montserrat, sans-serif", size=18, color=TEXT),
    plot_bgcolor=BG, paper_bgcolor=BG, hovermode="x unified",
    colorway=[PRIMARY, ACCENT, SUCCESS, DANGER, "#00B4D8", "#6C757D"],
    # t=90 chừa chỗ cho tiêu đề; b=120 chừa chỗ cho legend nằm dưới.
    margin=dict(l=70, r=30, t=90, b=120),
    title=dict(x=0, xanchor="left", y=0.97, yanchor="top",
               font=dict(family="Montserrat", size=21, color=PRIMARY)),
    xaxis=dict(showgrid=False, linecolor=LINE, linewidth=1,
               ticks="outside", tickcolor=LINE, tickfont=dict(size=24),
               automargin=True),
    yaxis=dict(showgrid=True, gridcolor="#F1F3F5", zeroline=False, tickfont=dict(size=24),
               automargin=True),
    # Legend nằm DƯỚI biểu đồ. Trước đây đặt y=1.02 (phía trên) nên đè lên tiêu đề.
    # orientation="h" giúp legend tự xuống dòng khi màn hình hẹp, không tràn chữ.
    legend=dict(orientation="h", yanchor="top", y=-0.22, xanchor="left", x=0,
                font=dict(size=18), itemwidth=30),
    hoverlabel=dict(bgcolor=PRIMARY, bordercolor=PRIMARY,
                    font=dict(family="Montserrat", size=18, color="#FFFFFF")),
))
pio.templates.default = "ghn"

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700;800;900&display=swap');

/* ── PHÓNG CỠ CHỮ 1.5 LẦN ────────────────────────────────────────────
   Streamlit dùng rem cho phần lớn thành phần của nó (ô chọn, nút, bảng,
   chat...). Đổi cỡ chữ gốc từ 16px lên 24px là mọi thứ đó tự phóng theo.
   Các cỡ px trong CSS bên dưới đã được nhân sẵn 1.5. */
html {{ font-size: 24px; }}

html, body, [class*="css"], .stApp {{
    font-family: 'Montserrat', sans-serif !important;
    background-color: {BG};
    color: {TEXT};
}}
/* Trải rộng hết chiều ngang màn hình. Streamlit mặc định bó nội dung vào giữa;
   ghi đè max-width và thu hẹp lề hai bên. Không đụng tới cỡ chữ. */
.block-container {{
    padding-top: 1.2rem;
    padding-bottom: 3rem;
    padding-left: 1.6rem;
    padding-right: 1.6rem;
    max-width: 100% !important;
    width: 100% !important;
}}
[data-testid="stAppViewContainer"] > .main {{ max-width: 100% !important; }}
[data-testid="stMainBlockContainer"] {{ max-width: 100% !important; }}
#MainMenu {{ visibility: hidden; }}
footer {{ visibility: hidden; }}

h1, h2, h3, h4 {{
    font-family: 'Montserrat', sans-serif !important;
    font-weight: 900 !important;
    color: {PRIMARY} !important;
    letter-spacing: -0.01em;
}}

/* ── Banner đầu trang ───────────────────────────────────────────────── */
.ghn-banner {{
    background: linear-gradient(120deg, {PRIMARY} 0%, #00B4D8 65%, {ACCENT} 100%);
    border-radius: 10px; padding: 22px 28px; margin-bottom: 22px;
    box-shadow: 0 4px 14px rgba(0,119,182,0.25);
}}
.ghn-banner h1 {{
    color: #FFFFFF !important; font-size: 45px; font-weight: 900 !important;
    margin: 0 0 4px 0; text-transform: uppercase; letter-spacing: 0.5px;
}}
.ghn-banner p {{ color: rgba(255,255,255,0.92); font-size: 21px; font-weight: 600; margin: 0; }}

/* ── Metric Card: nền trắng, đổ bóng, bo góc, viền trái xanh ────────── */
.metric-card {{
    background: {BG};
    border-radius: 8px;
    border-left: 5px solid {PRIMARY};
    box-shadow: 0 2px 8px rgba(0,0,0,0.10);
    padding: 16px 18px;
    margin-bottom: 14px;
    height: 100%;
}}
.metric-card .m-title {{
    font-size: 18.75px; font-weight: 700; color: {MUTED};
    text-transform: uppercase; letter-spacing: 0.4px; margin-bottom: 6px;
}}
.metric-card .m-value {{
    font-size: 42px; font-weight: 900; color: {PRIMARY};
    line-height: 1.1; font-variant-numeric: tabular-nums;
}}
.metric-card .m-value.accent {{ color: {ACCENT}; }}
.metric-card .m-delta {{ font-size: 18.75px; font-weight: 700; margin-top: 6px; }}
.metric-card .m-delta.up {{ color: {SUCCESS}; }}
.metric-card .m-delta.down {{ color: {DANGER}; }}
.metric-card .m-delta.flat {{ color: {MUTED}; }}
.metric-card.ok {{ border-left-color: {SUCCESS}; }}
.metric-card.bad {{ border-left-color: {DANGER}; }}
.metric-card.accent {{ border-left-color: {ACCENT}; }}

/* ── Thanh Tabs: tab đang chọn viền dưới cam, chữ in đậm ───────────── */
.stTabs [data-baseweb="tab-list"] {{
    gap: 6px; border-bottom: 2px solid {LINE};
}}
.stTabs [data-baseweb="tab"] {{
    height: 52px; padding: 0 20px; background: transparent;
    border-radius: 6px 6px 0 0;
}}
.stTabs [data-baseweb="tab"] p {{
    font-family: 'Montserrat', sans-serif !important;
    font-size: 22.5px !important; font-weight: 700 !important; color: {MUTED} !important;
}}
.stTabs [aria-selected="true"] {{
    background: #FFF6EC !important;
    border-bottom: 4px solid {ACCENT} !important;
}}
.stTabs [aria-selected="true"] p {{
    color: {ACCENT} !important; font-weight: 900 !important;
}}

/* ── Dataframe: dòng tiêu đề nền xanh, chữ trắng in đậm ─────────────── */
div[data-testid="stDataFrame"] {{
    border: 1px solid {LINE}; border-radius: 8px; overflow: hidden;
    box-shadow: 0 2px 6px rgba(0,0,0,0.06);
}}
div[data-testid="stDataFrame"] thead tr th {{
    background-color: {PRIMARY} !important;
    color: #FFFFFF !important;
    font-weight: 800 !important;
    font-family: 'Montserrat', sans-serif !important;
    text-transform: uppercase; font-size: 18px !important;
}}
div[data-testid="stDataFrame"] [role="columnheader"] {{
    background-color: {PRIMARY} !important; color: #FFFFFF !important; font-weight: 800 !important;
}}

/* ── Bảng HTML tự dựng ──────────────────────────────────────────────── */
table.ghn-table {{ width: 100%; border-collapse: collapse; margin: 10px 0 16px; font-size: 20.25px; }}
table.ghn-table thead th {{
    background: {PRIMARY}; color: #FFFFFF; font-weight: 800; text-transform: uppercase;
    font-size: 18px; padding: 10px 12px; text-align: right; letter-spacing: 0.3px;
}}
table.ghn-table thead th:first-child, table.ghn-table td:first-child {{ text-align: left; }}
table.ghn-table td {{
    padding: 10px 12px; text-align: right; border-bottom: 1px solid {LINE};
    font-variant-numeric: tabular-nums; font-weight: 600;
}}
table.ghn-table tbody tr:nth-child(even) {{ background: #F8FBFD; }}
table.ghn-table td.up {{ color: {SUCCESS}; font-weight: 800; }}
table.ghn-table td.down {{ color: {DANGER}; font-weight: 800; }}
table.ghn-table td span.up {{ color: {SUCCESS}; font-weight: 800; }}
table.ghn-table td span.down {{ color: {DANGER}; font-weight: 800; }}

/* ── Nút bấm màu cam ────────────────────────────────────────────────── */
.stButton > button {{
    background: {ACCENT}; color: #FFFFFF; border: none; border-radius: 6px;
    font-family: 'Montserrat', sans-serif; font-weight: 800; font-size: 19.5px;
    text-transform: uppercase; letter-spacing: 0.4px; padding: 0.55rem 1.4rem;
    box-shadow: 0 2px 6px rgba(255,140,0,0.35);
}}
.stButton > button:hover {{ background: #E67E00; color: #FFFFFF; }}
.stDownloadButton > button {{
    background: {BG}; color: {PRIMARY}; border: 2px solid {PRIMARY}; border-radius: 6px;
    font-weight: 800; font-size: 18px; text-transform: uppercase;
}}
.stDownloadButton > button:hover {{ background: {PRIMARY}; color: #FFFFFF; }}

/* ── Nhãn ô nhập ────────────────────────────────────────────────────── */
label, .stSelectbox label, .stDateInput label, .stMultiSelect label, .stTextArea label {{
    font-family: 'Montserrat', sans-serif !important;
    font-weight: 700 !important; font-size: 18px !important;
    color: {PRIMARY} !important; text-transform: uppercase; letter-spacing: 0.3px;
}}

/* ── Khối cảnh báo / AI ─────────────────────────────────────────────── */
.ghn-alert {{
    background: #FFF; border-left: 5px solid {ACCENT}; border-radius: 8px;
    padding: 16px 20px; margin-bottom: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    font-size: 21px; line-height: 1.7;
}}
.ghn-alert.danger {{ border-left-color: {DANGER}; }}
.ghn-alert.ok {{ border-left-color: {SUCCESS}; }}
.ghn-alert .a-tag {{
    display: inline-block; font-size: 16.5px; font-weight: 800; text-transform: uppercase;
    padding: 2px 10px; border-radius: 12px; margin-right: 8px;
}}
.tag-danger {{ background: #FDECEE; color: {DANGER}; }}
.tag-warn {{ background: #FFF4E5; color: #B36200; }}
.tag-ok {{ background: #E8F6EC; color: {SUCCESS}; }}

.section-title {{
    font-size: 25.5px; font-weight: 900; color: {PRIMARY};
    text-transform: uppercase; letter-spacing: 0.3px;
    border-left: 5px solid {ACCENT}; padding-left: 12px; margin: 26px 0 12px;
}}
.note-box {{
    background: #F8FBFD; border: 1px dashed {PRIMARY_SOFT}; border-radius: 8px;
    padding: 18px; text-align: center; color: {MUTED}; font-size: 19.5px; font-weight: 600;
    margin: 10px 0;
}}
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════
# 2. TIỆN ÍCH CHUNG
# ═══════════════════════════════════════════════════════════════════════
def esc(x) -> str:
    return html_lib.escape(str(x))


def strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFD", str(text))
    out = "".join(c for c in nfkd if unicodedata.category(c) != "Mn")
    return out.replace("đ", "d").replace("Đ", "D")


def norm(text: str) -> str:
    s = strip_accents(text).lower().replace("\xa0", " ")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9% ]+", " ", s)).strip()


def make_csv_url(url: str) -> str:
    """Đổi link /edit?gid=... thành link /export?format=csv&gid=... để pandas đọc được."""
    clean = url.split("#")[0]
    if "/edit?gid=" in clean:
        return clean.replace("/edit?gid=", "/export?format=csv&gid=")
    if "/edit#gid=" in clean:
        return clean.replace("/edit#gid=", "/export?format=csv&gid=")
    if clean.endswith("/edit"):
        return clean.replace("/edit", "/export?format=csv")
    if "/export?format=csv" in clean:
        return clean
    return clean


def parse_num(val):
    """Đọc số kiểu Việt Nam: '83,61%' -> 83.61 ; '1.234.567' -> 1234567."""
    if pd.isna(val):
        return np.nan
    s = str(val)
    for junk in ["%", "đ", "₫", "VNĐ", "vnd", " ", "\xa0"]:
        s = s.replace(junk, "")
    s = s.strip()
    if s in ("", "-", "nan", "None", "null", "#N/A", "#DIV/0!", "#REF!"):
        return np.nan
    neg = s.startswith("(") and s.endswith(")")
    if neg:
        s = s[1:-1]
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    elif "." in s:
        parts = s.split(".")
        if len(parts) > 2:
            s = s.replace(".", "")
        elif len(parts[1]) == 3 and parts[0].lstrip("-") not in ("0", ""):
            s = s.replace(".", "")
    try:
        v = float(s)
        return -v if neg else v
    except ValueError:
        return np.nan


def pick_col(df: pd.DataFrame, groups, exclude=()):
    """Dò tên cột theo từ khóa đã bỏ dấu, không cần đặt tên cột cố định trong sheet.

    Sheet của GHN đặt tên cột không nhất quán: có chỗ ghi 'Bưu cục' (có dấu cách),
    có chỗ ghi 'BưuCục' và 'NhânViên' (viết liền). Vì vậy phải so khớp cả bản
    KHÔNG có dấu cách, nếu không cột tên nhân viên sẽ bị bỏ sót rồi bị ép thành số.
    """
    if df is None or df.empty:
        return None
    cols = {c: norm(c) for c in df.columns}
    for group in groups:
        keys = [norm(k) for k in ([group] if isinstance(group, str) else group)]
        for col, nc in cols.items():
            nc_tight = nc.replace(" ", "")
            hit = all((k in nc) or (k.replace(" ", "") in nc_tight) for k in keys)
            if not hit:
                continue
            skipped = any((norm(e) in nc) or (norm(e).replace(" ", "") in nc_tight)
                          for e in exclude)
            if not skipped:
                return col
    return None


def is_total_row(name) -> bool:
    """Sheet GHN có dòng tổng, tên không thống nhất giữa các tab:
    'Grand Total' ở File1/File3/TTS nhưng 'Tổng số' ở sheet Trả hàng."""
    return norm(name) in ("grand total", "tong so", "tong cong", "total", "tong")


def _as_series(x) -> pd.Series:
    """Nếu lỡ nhận vào DataFrame (do cột trùng tên) thì lấy cột đầu tiên."""
    if isinstance(x, pd.DataFrame):
        return x.iloc[:, 0]
    return x


def wavg(values, weights) -> float:
    """Trung bình CÓ TRỌNG SỐ. Bắt buộc dùng cho mọi tỷ lệ phần trăm.
    Cộng dồn hoặc lấy trung bình cộng các cột % đều cho kết quả sai."""
    v = pd.to_numeric(_as_series(values), errors="coerce")
    w = pd.to_numeric(_as_series(weights), errors="coerce").fillna(0)
    m = v.notna() & (w > 0)
    total_w = float(w[m].sum())
    if total_w > 0:
        return float((v[m] * w[m]).sum() / total_w)
    return float(v.mean()) if v.notna().any() else 0.0


def month_end(ts: pd.Timestamp) -> pd.Timestamp:
    nxt = ts.replace(day=28) + timedelta(days=4)
    return nxt - timedelta(days=nxt.day)


def fmt_money(v: float, full: bool = True) -> str:
    """Định dạng tiền. Mặc định hiển thị ĐẦY ĐỦ số đồng, không rút gọn về 'triệu'
    và không làm tròn — vì rút gọn 1.846.505 thành '1,8 tr đ' làm mất số liệu thật."""
    if full:
        return f"{v:,.0f} đ".replace(",", ".")
    if abs(v) >= 1_000_000:
        return f"{v/1_000_000:,.1f} tr đ"
    return f"{v:,.0f} đ"


# ═══════════════════════════════════════════════════════════════════════
# 3. TẢI DỮ LIỆU TỪ 12 GOOGLE SHEETS
# ═══════════════════════════════════════════════════════════════════════
DATE_KEYS = [["ngay"], ["thoi gian"], ["date"]]
# Sheet doanh thu dùng cột "Vùng" (giá trị TTB) thay vì "Bưu cục" — đã kiểm chứng
# trực tiếp trong sheet. Thiếu từ khóa này thì mọi dòng bị gán "Chưa phân loại"
# và lọc theo bưu cục sẽ luôn trả về 0.
BC_KEYS = [["buu cuc"], ["buu"], ["khu vuc"], ["vung"], ["tram"], ["station"], ["cum"]]
VOL_KEYS = [["san luong"], ["volume"], ["tong don"], ["so don"], ["don"]]
TEXT_HINTS = ("loai hang", "ca", "nhan vien", "trang thai", "ten", "ma", "tuyen", "cap quan ly")


def parse_dates(raw: pd.Series) -> pd.Series:
    """Đọc cột ngày mà KHÔNG cố định dayfirst.

    NGUYÊN NHÂN GỐC của lỗi 'dữ liệu dừng ở ngày 12': Google Sheets xuất CSV theo
    locale của bảng tính. Nếu bảng đang để locale Mỹ thì ngày ra dạng M/D/YYYY.
    Khi ép dayfirst=True, chuỗi '8/13/2026' trở thành 'ngày 8 tháng 13' — không hợp lệ
    nên pandas trả NaT, rồi dropna() xoá luôn dòng đó. Kết quả: mọi ngày có số > 12
    biến mất, dashboard trông như bị dừng ở ngày 12.

    Cách sửa: thử cả hai kiểu, chọn kiểu đọc được NHIỀU dòng hơn. Hoà thì ưu tiên
    dayfirst=False (khớp ISO yyyy-mm-dd và locale Mỹ).
    """
    s = raw.astype(str).str.strip().replace({"": None, "nan": None, "None": None})
    no_first = pd.to_datetime(s, errors="coerce", dayfirst=False)
    day_first = pd.to_datetime(s, errors="coerce", dayfirst=True)
    if day_first.notna().sum() > no_first.notna().sum():
        return day_first
    return no_first


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def load_sheet(key: str) -> pd.DataFrame:
    """Đọc 1 sheet, chuẩn hóa cột Ngày / Bưu Cục, ép kiểu số cho các cột còn lại.

    Đọc toàn bộ sheet qua export CSV — không giới hạn range hay số dòng, nên khi
    Google Sheet có thêm ngày mới là dashboard tự lấy được, không phải sửa code.
    """
    df = pd.read_csv(make_csv_url(SHEET_LINKS[key]))
    df.columns = df.columns.astype(str).str.strip().str.replace("\xa0", " ", regex=False)
    df = df.loc[:, ~df.columns.str.match(r"^Unnamed")]
    # Google Sheet có thể có hai cột cùng tên. Khi đó df["X"] trả về DataFrame chứ
    # không phải Series, làm mọi phép float()/sum() phía sau đổ vỡ. Giữ cột đầu tiên.
    df = df.loc[:, ~df.columns.duplicated(keep="first")]
    if df.empty:
        return df

    dcol = pick_col(df, DATE_KEYS)
    bcol = pick_col(df, BC_KEYS)
    df["Ngày"] = parse_dates(df[dcol]) if dcol else pd.NaT
    df["Bưu Cục"] = df[bcol].astype(str).str.strip() if bcol else "Chưa phân loại"

    keep_text = {pick_col(df, [[h]]) for h in TEXT_HINTS}
    for col in df.columns:
        if col in {dcol, bcol, "Ngày", "Bưu Cục"} or df[col].dtype.kind in "if":
            continue
        if col in keep_text:
            df[col] = df[col].astype(str).str.strip()
        else:
            df[col] = df[col].apply(parse_num)
    return df


def safe_load(key: str) -> pd.DataFrame:
    try:
        return load_sheet(key)
    except Exception as exc:  # noqa: BLE001
        st.session_state.setdefault("load_errors", {})[key] = str(exc)
        return pd.DataFrame()


def rescale_pct(s) -> pd.Series:
    """Nếu sheet lưu 0.85 thay vì 85 thì nhân 100."""
    s = pd.to_numeric(_as_series(s), errors="coerce")
    v = s[s > 0].dropna()
    return s * 100 if (not v.empty and v.max() <= 1.2) else s


def metric_frame(key: str, value_keys, weight_keys=VOL_KEYS,
                 is_pct=True, extra_dim=None) -> pd.DataFrame:
    """Chuẩn hóa 1 sheet về khung: Ngày | Bưu Cục | Giá Trị | Trọng Số | (Chiều)."""
    df = safe_load(key)
    cols = ["Ngày", "Bưu Cục", "Giá Trị", "Trọng Số"]
    if df.empty:
        return pd.DataFrame(columns=cols)
    vcol = pick_col(df, value_keys)
    if vcol is None:
        return pd.DataFrame(columns=cols)
    wcol = pick_col(df, weight_keys, exclude=[vcol]) if weight_keys else None
    out = pd.DataFrame({
        "Ngày": df["Ngày"],
        "Bưu Cục": df["Bưu Cục"],
        "Giá Trị": rescale_pct(df[vcol]) if is_pct else pd.to_numeric(df[vcol], errors="coerce"),
        "Trọng Số": pd.to_numeric(df[wcol], errors="coerce").fillna(0) if wcol else 1.0,
    })
    if extra_dim:
        ecol = pick_col(df, extra_dim)
        out["Chiều"] = df[ecol].astype(str).str.strip() if ecol else "Chung"
    return out.dropna(subset=["Ngày"])


# ═══════════════════════════════════════════════════════════════════════
# 4. LỌC PHẠM VI & SO SÁNH KỲ
# ═══════════════════════════════════════════════════════════════════════
def scope(df: pd.DataFrame, bc: str) -> pd.DataFrame:
    """Phạm vi 'Tất cả' lấy THẲNG dòng tổng của sheet, không tự cộng các bưu cục.
    Nếu cộng hết mọi dòng thì sản lượng bị đếm gấp đôi vì dòng tổng nằm lẫn trong dữ liệu."""
    if df is None or df.empty or "Bưu Cục" not in df.columns:
        return df if df is not None else pd.DataFrame()
    if bc and bc != "Tất cả":
        return df[df["Bưu Cục"].map(norm) == norm(bc)]
    totals = df[df["Bưu Cục"].map(is_total_row)]
    return totals if not totals.empty else df[~df["Bưu Cục"].map(is_total_row)]


def bc_options(*frames) -> list[str]:
    vals: set[str] = set()
    for f in frames:
        if f is not None and not f.empty and "Bưu Cục" in f.columns:
            vals |= set(f["Bưu Cục"].dropna().astype(str).str.strip())
    vals = {v for v in vals
            if v and v.lower() not in ("nan", "chưa phân loại") and not is_total_row(v)}
    return ["Tất cả"] + sorted(vals)


def sl(df: pd.DataFrame, a, b) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=df.columns if df is not None else [])
    return df[(df["Ngày"] >= a) & (df["Ngày"] <= b)]


def agg(df: pd.DataFrame, a, b, how: str = "wavg") -> float:
    s = sl(df, a, b)
    if s.empty:
        return 0.0
    if how == "wavg":
        return wavg(s["Giá Trị"], s["Trọng Số"])
    return float(pd.to_numeric(_as_series(s["Giá Trị"]), errors="coerce").sum())


def get_period_data(df: pd.DataFrame, ref_date, how: str = "wavg") -> dict:
    """So sánh N vs N-1, W vs W-1, M vs M-1.

    Lưu ý quan trọng: tuần này so với tuần trước dùng KHUNG BẰNG NHAU (7 ngày với 7 ngày).
    Nếu lấy tuần này từ thứ Hai đến hôm nay (ví dụ 3 ngày) rồi so với tuần trước đủ 7 ngày,
    kết quả luôn báo giảm mạnh dù thực tế không giảm.

    Trả về dict có các khóa: n, n1, w, w1, m, m1 kèm cờ has_* cho biết kỳ đó có dữ liệu hay không.
    """
    ref = pd.to_datetime(ref_date)
    empty_result = {k: 0.0 for k in ("n", "n1", "w", "w1", "m", "m1")}
    empty_result.update({"has_n1": False, "has_w1": False, "has_m1": False})
    if df is None or df.empty or "Ngày" not in df.columns:
        return empty_result

    # Ngày
    n_a = n_b = ref
    n1_a = n1_b = ref - timedelta(days=1)
    # Tuần (thứ Hai đầu tuần), 7 ngày so 7 ngày
    w_a = ref - timedelta(days=ref.weekday())
    w_b = w_a + timedelta(days=6)
    w1_a = w_a - timedelta(days=7)
    w1_b = w_a - timedelta(days=1)
    # Tháng
    m_a = ref.replace(day=1)
    m_b = month_end(m_a)
    m1_a = (m_a - timedelta(days=1)).replace(day=1)
    m1_b = m_a - timedelta(days=1)

    return {
        "n": agg(df, n_a, n_b, how), "n1": agg(df, n1_a, n1_b, how),
        "w": agg(df, w_a, w_b, how), "w1": agg(df, w1_a, w1_b, how),
        "m": agg(df, m_a, m_b, how), "m1": agg(df, m1_a, m1_b, how),
        "has_n1": not sl(df, n1_a, n1_b).empty,
        "has_w1": not sl(df, w1_a, w1_b).empty,
        "has_m1": not sl(df, m1_a, m1_b).empty,
    }


def daily(df: pd.DataFrame, how: str = "wavg") -> pd.DataFrame:
    """Gộp theo ngày. Tỷ lệ % gộp bằng trung bình có trọng số, số lượng thì cộng."""
    if df is None or df.empty:
        return pd.DataFrame(columns=["Ngày", "Giá Trị", "Trọng Số"])
    if how == "sum":
        g = df.groupby("Ngày", as_index=False)["Giá Trị"].sum()
        g["Trọng Số"] = g["Giá Trị"]
        return g.sort_values("Ngày")
    g = (df.assign(_p=df["Giá Trị"].fillna(0) * df["Trọng Số"])
           .groupby("Ngày", as_index=False).agg(_p=("_p", "sum"), _w=("Trọng Số", "sum")))
    g["Giá Trị"] = np.where(g["_w"] > 0, g["_p"] / g["_w"], np.nan)
    g["Trọng Số"] = g["_w"]
    return g[["Ngày", "Giá Trị", "Trọng Số"]].sort_values("Ngày")


# ═══════════════════════════════════════════════════════════════════════
# 5. THÀNH PHẦN GIAO DIỆN
# ═══════════════════════════════════════════════════════════════════════
def section(title: str):
    st.markdown(f"<div class='section-title'>{esc(title)}</div>", unsafe_allow_html=True)


def note(msg: str):
    st.markdown(f"<div class='note-box'>{esc(msg)}</div>", unsafe_allow_html=True)


def metric_card(title: str, value: str, delta: float | None = None, unit: str = "%",
                higher_is_better: bool = True, has_prev: bool = True,
                accent: bool = False, sub: str = "") -> str:
    """Ô số liệu: nền trắng, đổ bóng, bo góc 8px, viền trái màu."""
    cls, dhtml = "", ""
    if delta is None:
        dhtml = f"<div class='m-delta flat'>{esc(sub)}</div>" if sub else ""
    elif not has_prev:
        dhtml = "<div class='m-delta flat'>chưa có dữ liệu kỳ trước</div>"
    else:
        good = (delta > 0) == higher_is_better
        flat = abs(delta) < 1e-9
        dcls = "flat" if flat else ("up" if good else "down")
        cls = "" if flat else ("ok" if good else "bad")
        arrow = "" if flat else ("▲" if delta > 0 else "▼")
        if unit == "%":
            txt = f"{arrow} {abs(delta):,.2f} pp"
        elif unit == "đ":
            txt = f"{arrow} {fmt_money(abs(delta))}"
        else:
            txt = f"{arrow} {abs(delta):,.0f}"
        dhtml = f"<div class='m-delta {dcls}'>{txt} {esc(sub)}</div>"
    if accent:
        cls = "accent"
    vcls = "accent" if accent else ""
    return (f"<div class='metric-card {cls}'><div class='m-title'>{esc(title)}</div>"
            f"<div class='m-value {vcls}'>{value}</div>{dhtml}</div>")


def period_cards(df: pd.DataFrame, ref, unit="%", higher_is_better=True,
                 how="wavg", label=""):
    """3 ô: Ngày vs N-1, Tuần vs W-1, Tháng vs M-1."""
    p = get_period_data(df, ref, how)
    fmt = (lambda v: f"{v:,.2f}%") if unit == "%" else (
        fmt_money if unit == "đ" else (lambda v: f"{v:,.0f}"))
    cols = st.columns(3)
    specs = [("Ngày (N vs N-1)", p["n"], p["n"] - p["n1"], p["has_n1"]),
             ("Tuần (W vs W-1)", p["w"], p["w"] - p["w1"], p["has_w1"]),
             ("Tháng (M vs M-1)", p["m"], p["m"] - p["m1"], p["has_m1"])]
    for col, (t, v, d, hp) in zip(cols, specs):
        with col:
            st.markdown(metric_card(f"{label} {t}".strip(), fmt(v), d, unit,
                                    higher_is_better, hp), unsafe_allow_html=True)
    return p


def html_table(headers: list[str], rows: list[list[str]], caption: str = "") -> str:
    th = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = ""
    for r in rows:
        body += "<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>"
    cap = f"<div class='m-title' style='margin-bottom:6px;'>{esc(caption)}</div>" if caption else ""
    return f"{cap}<table class='ghn-table'><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>"


def arrow_span(delta: float, suffix: str, decimals: int = 2, higher_is_better=True) -> str:
    if abs(delta) < 1e-9:
        return f"0{suffix}"
    good = (delta > 0) == higher_is_better
    cls = "up" if good else "down"
    arrow = "▲" if delta > 0 else "▼"
    return f"<span class='{cls}'>{arrow} {abs(delta):,.{decimals}f}{suffix}</span>"


def synced_range_picker(label: str, default_a, default_b, key: str, sync_token=None):
    """Ô chọn khoảng ngày ĐỒNG BỘ với nút 'Chọn nhanh'.

    Streamlit giữ lại giá trị widget theo key, nên nếu chỉ truyền `value` thì đổi
    nút Chọn nhanh sẽ KHÔNG làm ô ngày đổi theo. Cách xử lý: theo dõi lựa chọn
    trước đó, khi người dùng bấm sang lựa chọn khác thì ghi đè thẳng vào
    session_state trước lúc vẽ widget. Nhờ vậy ô ngày luôn khớp nút Chọn nhanh,
    mà người dùng vẫn tự sửa ngày được sau đó.
    """
    da, db = clamp(default_a), clamp(default_b)
    if da > db:
        da = db

    token_key = f"__sync_{key}"
    changed = sync_token is not None and st.session_state.get(token_key) != sync_token
    if changed or key not in st.session_state:
        st.session_state[token_key] = sync_token
        st.session_state[key] = (da.date(), db.date())

    picked = st.date_input(label, min_value=DATA_MIN.date(), max_value=REF_DATE.date(), key=key)
    if isinstance(picked, (list, tuple)) and len(picked) >= 2:
        return pd.to_datetime(picked[0]), pd.to_datetime(picked[1])
    if isinstance(picked, (list, tuple)) and len(picked) == 1:
        return pd.to_datetime(picked[0]), pd.to_datetime(picked[0])
    return da, db


def date_range_picker(label: str, default_a, default_b, key: str):
    """Ô chọn khoảng ngày. default_a / default_b là giá trị điền sẵn khi mở trang.
    Giá trị luôn được kẹp trong khoảng ngày thực có của dữ liệu."""
    da, db = clamp(default_a), clamp(default_b)
    if da > db:
        da = db
    picked = st.date_input(label, [da.date(), db.date()],
                           min_value=DATA_MIN.date(), max_value=REF_DATE.date(), key=key)
    if isinstance(picked, (list, tuple)) and len(picked) >= 2:
        return pd.to_datetime(picked[0]), pd.to_datetime(picked[1])
    if isinstance(picked, (list, tuple)) and len(picked) == 1:
        return pd.to_datetime(picked[0]), pd.to_datetime(picked[0])
    return da, db


def pay_period(ref: pd.Timestamp):
    """Kỳ lương GHN. Kỳ được gọi tên theo THÁNG CHI LƯƠNG, không phải tháng phát sinh.

      Kỳ 20 tháng M : dữ liệu ngày 01–15 tháng M,        chi lương ngày 20 tháng M
      Kỳ 05 tháng M : dữ liệu ngày 16–hết tháng (M-1),   chi lương ngày 05 tháng M

    Ví dụ theo đúng yêu cầu: Kỳ 20 tháng 08 (dữ liệu 01–15/08) so với kỳ liền trước
    là Kỳ 05 tháng 08 — tức dữ liệu từ 16 đến hết tháng 07.
    """
    if ref.day <= 15:
        a = ref.replace(day=1)
        b = ref.replace(day=15)
        name = f"Kỳ 20 · tháng {a:%m/%Y}"          # chi lương 20 tháng này
        prev_b = a - timedelta(days=1)              # ngày cuối tháng trước
        prev_a = prev_b.replace(day=16)             # 16 tháng trước
        # Kỳ này chi lương ngày 05 của THÁNG NÀY, nên gọi theo tháng của `a`.
        prev_name = f"Kỳ 05 · tháng {a:%m/%Y}"
    else:
        a = ref.replace(day=16)
        b = month_end(a)
        pay_month = b + timedelta(days=1)           # chi lương ngày 05 tháng sau
        name = f"Kỳ 05 · tháng {pay_month:%m/%Y}"
        prev_a, prev_b = ref.replace(day=1), ref.replace(day=15)
        prev_name = f"Kỳ 20 · tháng {prev_a:%m/%Y}"
    return a, b, name, prev_a, prev_b, prev_name


def line_chart(df: pd.DataFrame, title: str, color: str, unit="%", target: float | None = None):
    if df is None or df.empty:
        note(f"Chưa có dữ liệu: {title}")
        return
    g = daily(df) if unit == "%" else daily(df, "sum")
    fig = px.line(g, x="Ngày", y="Giá Trị", markers=True, title=title)
    fig.update_traces(line=dict(color=color, width=3),
                      marker=dict(size=7, color=color, line=dict(width=2, color="#FFF")))
    if target:
        fig.add_hline(y=target, line_dash="dot", line_color=ACCENT, line_width=2,
                      annotation_text="Mốc KPI", annotation_position="top left")
    fig.update_yaxes(ticksuffix="%" if unit == "%" else "")
    fig.update_xaxes(tickformat="%d/%m")
    fig.update_layout(height=320, showlegend=False, margin=dict(t=90, b=70))
    st.plotly_chart(fig, use_container_width=True)
    if len(g) < 2:
        st.caption("Mới có 1 ngày dữ liệu nên chưa vẽ được đường xu hướng.")


def combo_chart(df: pd.DataFrame, title: str, bar_name="Sản lượng", line_name="% GTC",
                target: float | None = None):
    if df is None or df.empty:
        note(f"Chưa có dữ liệu: {title}")
        return
    g = daily(df)
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=g["Ngày"], y=g["Trọng Số"], name=bar_name,
                         marker_color=PRIMARY_SOFT, marker_line_width=0), secondary_y=False)
    fig.add_trace(go.Scatter(x=g["Ngày"], y=g["Giá Trị"], name=line_name, mode="lines+markers",
                             line=dict(color=ACCENT, width=3),
                             marker=dict(size=7, line=dict(width=2, color="#FFF"))),
                  secondary_y=True)
    if target:
        fig.add_hline(y=target, line_dash="dot", line_color=DANGER, line_width=2, secondary_y=True)
    fig.update_layout(title=title, height=450)
    fig.update_yaxes(title_text=bar_name, secondary_y=False)
    fig.update_yaxes(title_text=line_name, secondary_y=True, ticksuffix="%", showgrid=False)
    fig.update_xaxes(tickformat="%d/%m")
    st.plotly_chart(fig, use_container_width=True)


def bc_bar_chart(df: pd.DataFrame, target: float | None, higher_is_better=True, title=""):
    """So sánh chỉ số giữa các bưu cục — thanh ngang, tô xanh/đỏ theo mốc."""
    if df is None or df.empty:
        note("Chưa có dữ liệu để so sánh giữa các bưu cục.")
        return
    d = df[~df["Bưu Cục"].map(is_total_row)]
    if d.empty:
        note("Sheet chỉ có dòng tổng, không tách được theo bưu cục.")
        return
    g = (d.assign(_p=d["Giá Trị"].fillna(0) * d["Trọng Số"])
          .groupby("Bưu Cục", as_index=False).agg(_p=("_p", "sum"), w=("Trọng Số", "sum")))
    g = g[g["w"] > 0]
    if g.empty:
        note("Không đủ dữ liệu để so sánh.")
        return
    g["r"] = g["_p"] / g["w"]
    g = g.sort_values("r")
    if target:
        colors = [SUCCESS if (v >= target) == higher_is_better else DANGER for v in g["r"]]
    else:
        colors = [PRIMARY] * len(g)
    fig = go.Figure(go.Bar(x=g["r"], y=g["Bưu Cục"], orientation="h",
                           marker=dict(color=colors),
                           text=[f"{v:,.2f}%" for v in g["r"]], textposition="outside",
                           customdata=g["w"],
                           hovertemplate="%{y}<br>%{x:.2f}%<br>Sản lượng %{customdata:,.0f} đơn<extra></extra>"))
    if target:
        fig.add_vline(x=target, line_dash="dot", line_color=ACCENT, line_width=2)
    fig.update_layout(title=title, height=max(220, 60 * len(g)), margin=dict(l=10, r=60, t=50, b=30))
    fig.update_xaxes(ticksuffix="%")
    st.plotly_chart(fig, use_container_width=True)


def gauge_chart(title: str, value: float, target: float, higher_is_better=True):
    """Đồng hồ đo KPI. Kim xanh nếu đạt, đỏ nếu trượt."""
    target = max(float(target), 0.5)
    ok = value >= target if higher_is_better else value <= target
    needle = SUCCESS if ok else DANGER
    if higher_is_better:
        steps = [{"range": [0, target * 0.8], "color": "#FDECEE"},
                 {"range": [target * 0.8, target], "color": "#FFF4E5"},
                 {"range": [target, 100], "color": "#E8F6EC"}]
    else:
        steps = [{"range": [0, target], "color": "#E8F6EC"},
                 {"range": [target, min(target * 1.6, 100)], "color": "#FFF4E5"},
                 {"range": [min(target * 1.6, 100), 100], "color": "#FDECEE"}]
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=float(value),
        # domain rõ ràng để đồng hồ nằm giữa khung.
        domain={"x": [0, 1], "y": [0, 1]},
        number={"suffix": "%", "valueformat": ".2f",
                "font": {"size": 46, "color": needle, "family": "Montserrat"}},
        # "position": "bottom" xếp delta XUỐNG DƯỚI số chính. Mặc định Plotly đặt
        # delta nằm cạnh số, khiến cụm số bị đẩy lệch sang một bên tâm đồng hồ.
        delta={"reference": target, "suffix": " pp", "position": "bottom",
               "font": {"size": 20, "family": "Montserrat"},
               "increasing": {"color": SUCCESS if higher_is_better else DANGER},
               "decreasing": {"color": DANGER if higher_is_better else SUCCESS}},
        title={"text": f"<b>{esc(title)}</b>",
               "font": {"size": 22, "color": PRIMARY, "family": "Montserrat"},
               "align": "center"},
        gauge={"axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": MUTED},
               "bar": {"color": needle, "thickness": 0.3},
               "bgcolor": BG, "borderwidth": 1, "bordercolor": LINE,
               "steps": steps,
               "threshold": {"line": {"color": PRIMARY, "width": 4},
                             "thickness": 0.85, "value": target}}))
    fig.update_layout(height=360, margin=dict(l=40, r=40, t=90, b=30),
                      showlegend=False)
    st.plotly_chart(fig, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════
# 6. AI GEMINI & TELEGRAM
# ═══════════════════════════════════════════════════════════════════════
@st.cache_resource
def genai_client():
    if not GENAI_AVAILABLE or not GEMINI_API_KEY:
        return None
    try:
        return genai.Client(api_key=GEMINI_API_KEY)
    except Exception:  # noqa: BLE001
        return None


def ask_ai(prompt: str) -> str:
    if not GENAI_AVAILABLE:
        return "Thiếu thư viện. Chạy: pip install google-genai"
    client = genai_client()
    if client is None:
        return "Chưa cấu hình GEMINI_API_KEY. Thêm biến môi trường rồi khởi động lại dịch vụ."
    try:
        resp = client.models.generate_content(
            model=GEMINI_MODEL, contents=prompt,
            config=genai_types.GenerateContentConfig(max_output_tokens=8192))
        if not getattr(resp, "candidates", None):
            return "AI không trả về nội dung. Thử rút gọn câu hỏi."
        return (resp.text or "").strip() or "AI trả về nội dung rỗng."
    except Exception as exc:  # noqa: BLE001
        return f"Lỗi Google AI: {exc}"


def send_telegram(text: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return False, "Chưa cấu hình TELEGRAM_TOKEN / TELEGRAM_CHAT_ID."
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    chunks = [text[i:i + 3800] for i in range(0, len(text), 3800)] or [""]
    for i, chunk in enumerate(chunks):
        prefix = "" if i == 0 else f"(phần {i+1}/{len(chunks)})\n"
        try:
            r = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": prefix + chunk},
                              timeout=20)
        except requests.RequestException as exc:
            return False, f"Lỗi mạng: {exc}"
        if r.status_code != 200:
            return False, f"Telegram trả về mã {r.status_code}."
    return True, f"Đã gửi {len(chunks)} tin nhắn."


# ═══════════════════════════════════════════════════════════════════════
# 7. ĐĂNG NHẬP & PHÂN QUYỀN
# ═══════════════════════════════════════════════════════════════════════
for _k, _v in {"auth": None, "ai_cache": {}, "chat": [], "kpi_manual": {}}.items():
    st.session_state.setdefault(_k, _v)

ACCOUNTS = {
    "ADMIN": {"password": ADMIN_PASS, "role": "Giám Đốc"},
    "USER": {"password": USER_PASS, "role": "Nhân Viên"},
}


def login_screen():
    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        st.markdown(f"""
        <div class="ghn-banner" style="text-align:center;">
            <h1>Trung Tâm Vận Hành Chiến Lược</h1>
            <p>GIAO HÀNG NHANH — Hệ thống báo cáo nội bộ</p>
        </div>""", unsafe_allow_html=True)

        with st.form("login_form"):
            user_id = st.text_input("Mã nhân viên (ID)", placeholder="ADMIN hoặc USER")
            password = st.text_input("Mật khẩu", type="password")
            submitted = st.form_submit_button("ĐĂNG NHẬP", use_container_width=True)
            if submitted:
                info = ACCOUNTS.get(user_id.strip().upper())
                if info and password == info["password"]:
                    st.session_state.auth = {"id": user_id.strip().upper(), "role": info["role"]}
                    st.rerun()
                else:
                    st.error("ID hoặc mật khẩu không chính xác.")

        if ADMIN_PASS == "ghn@admin" or USER_PASS == "ghn@user":
            st.warning(
                "Đang dùng mật khẩu mặc định. Trước khi đưa lên máy chủ thật, hãy đặt biến "
                "môi trường ADMIN_PASS và USER_PASS để không ai đoán được mật khẩu.",
                icon="⚠️")


if st.session_state.auth is None:
    login_screen()
    st.stop()

AUTH = st.session_state.auth
IS_ADMIN = AUTH["role"] == "Giám Đốc"


# ═══════════════════════════════════════════════════════════════════════
# 8. NẠP TOÀN BỘ DỮ LIỆU
# ═══════════════════════════════════════════════════════════════════════
with st.spinner("Đang đồng bộ dữ liệu từ 12 Google Sheets..."):
    # Cột thật đã đối chiếu với sheet:
    #   File1_BuuCuc / File2_TTS: Ngày | Cấp Quản Lý | Bưu cục | Volume | % Gán | % GTC | % Chuyển trả | Leadtime
    #   File3_TheoCa            : thêm cột "Loại Hàng (Ca)"
    #   Tỷ lệ Trả hàng          : Ngày | Cấp Quản Lý | Bưu cục | % Vol | % Return
    M_GTC = metric_frame("gtc_tong", [["% gtc"], ["gtc"], ["giao thanh cong"]])
    M_GAN = metric_frame("gtc_tong", [["% gan"], ["gan"]])
    M_LEAD = metric_frame("gtc_tong", [["leadtime"], ["lead time"]], is_pct=False)
    M_CA = metric_frame("sl_theo_ca", [["% gtc"], ["gtc"]], extra_dim=[["loai hang"], ["ca"]])
    M_TRA = metric_frame("tra_hang", [["% return"], ["return"], ["chuyen tra"], ["tra hang"], ["tra"]])
    M_GTB = metric_frame("gtb_thu_tien",
                         [["da thu chuyen tra"], ["da thu"], ["gtb"], ["thu tien"]])
    M_TTS = metric_frame("gtc_tts", [["% gtc"], ["gtc tts"], ["gtc"]])
    M_ODR = metric_frame("odr_tts", [["odr"], ["ontime"], ["dung han"]])
    M_DT = metric_frame("doanh_thu", [["doanh thu"]], weight_keys=None, is_pct=False)

    DF_KPI = safe_load("kpi")
    DF_KHM = safe_load("kh_moi")
    DF_PHEU = safe_load("pheu_kh")
    DF_LUONG = safe_load("ns_luong")
    DF_NSGTC = safe_load("ns_gtc")

# Lưu vào session_state để tab AI cố vấn đọc được
st.session_state["dataframes"] = {
    "GTC tổng": M_GTC, "Tỷ lệ trả hàng": M_TRA, "GTB thu tiền": M_GTB,
    "GTC TikTok": M_TTS, "ODR TikTok": M_ODR, "Sản lượng theo ca": M_CA,
    "Doanh thu": M_DT, "Khách hàng mới": DF_KHM, "Phễu khách hàng": DF_PHEU,
    "Lương nhân viên": DF_LUONG, "Năng suất GTC": DF_NSGTC, "KPI": DF_KPI,
}

ALL_BC = bc_options(M_GTC, M_DT, DF_LUONG, DF_NSGTC)

def today_vn() -> pd.Timestamp:
    """Ngày hiện tại theo giờ Việt Nam (UTC+7), không phụ thuộc múi giờ máy chủ.
    Render chạy theo UTC nên nếu dùng datetime.now() thì từ 17h VN trở đi sẽ lệch 1 ngày."""
    return (pd.Timestamp.utcnow() + timedelta(hours=7)).normalize().tz_localize(None)


TODAY_VN = today_vn()
YESTERDAY_VN = TODAY_VN - timedelta(days=1)

# Ngày mới nhất có trong dữ liệu — quét TOÀN BỘ 12 sheet, không chỉ vài sheet.
# Trước đây chỉ quét 3 khung nên nếu một sheet đọc sai ngày là cả dashboard lệch theo.
_ALL_FRAMES = [M_GTC, M_CA, M_TRA, M_GTB, M_TTS, M_ODR, M_DT,
               DF_KHM, DF_PHEU, DF_LUONG, DF_NSGTC]
_dates = [f["Ngày"].max() for f in _ALL_FRAMES
          if f is not None and not f.empty and "Ngày" in f.columns and f["Ngày"].notna().any()]
REF_DATE = max(_dates) if _dates else TODAY_VN
_mins = [f["Ngày"].min() for f in _ALL_FRAMES
         if f is not None and not f.empty and "Ngày" in f.columns and f["Ngày"].notna().any()]
DATA_MIN = min(_mins) if _mins else REF_DATE - timedelta(days=90)

# Mốc mặc định cho bộ lọc: N-1 theo giờ Việt Nam, nhưng không vượt quá khoảng
# ngày thực có trong dữ liệu (nếu vượt thì st.date_input sẽ báo lỗi).
def clamp(d: pd.Timestamp) -> pd.Timestamp:
    return min(max(pd.to_datetime(d), DATA_MIN), REF_DATE)


DEFAULT_N1 = clamp(YESTERDAY_VN)

# Mặc định 7 ngày gần nhất theo giờ Việt Nam: từ N-7 đến N-1.
# Kẹp lại trong khoảng ngày thực có trong dữ liệu để st.date_input không báo lỗi.
DEFAULT_7D_END = clamp(YESTERDAY_VN)
DEFAULT_7D_START = clamp(YESTERDAY_VN - timedelta(days=6))
if DEFAULT_7D_START > DEFAULT_7D_END:
    DEFAULT_7D_START = DEFAULT_7D_END


SHEET_LABELS = {
    "gtc_tong": "GTC tổng", "sl_theo_ca": "Sản lượng theo ca", "tra_hang": "Tỷ lệ trả hàng",
    "gtb_thu_tien": "GTB thu tiền", "gtc_tts": "GTC TikTok", "odr_tts": "ODR TikTok",
    "kpi": "Mốc KPI", "doanh_thu": "Doanh thu", "kh_moi": "Khách hàng mới",
    "pheu_kh": "Phễu khách hàng", "ns_luong": "Lương nhân viên", "ns_gtc": "Năng suất GTC",
}


def sheet_diagnostics() -> pd.DataFrame:
    """Soi từng sheet: đọc được bao nhiêu dòng, khoảng ngày nào, nhận ra cột nào.
    Đây là cách nhanh nhất để phát hiện vì sao một con số hiện ra sai hoặc bằng 0."""
    rows = []
    for key, label in SHEET_LABELS.items():
        raw = safe_load(key)
        if raw.empty:
            rows.append({
                "Sheet": label, "Số dòng": 0, "Từ ngày": "—", "Đến ngày": "—",
                "Cột đơn vị": "—", "Giá trị đơn vị": "—",
                "Tình trạng": "Không đọc được / rỗng",
                "Các cột trong sheet": "—"})
            continue

        has_date = "Ngày" in raw.columns and raw["Ngày"].notna().any()
        d_min = raw["Ngày"].min() if has_date else None
        d_max = raw["Ngày"].max() if has_date else None
        units = ([u for u in raw["Bưu Cục"].dropna().astype(str).unique()][:4]
                 if "Bưu Cục" in raw.columns else [])
        original_cols = [c for c in raw.columns if c not in ("Ngày", "Bưu Cục")]

        if not has_date:
            status = "Thiếu cột Ngày"
        elif units and all(u == "Chưa phân loại" for u in units):
            status = "Không nhận ra cột đơn vị"
        elif d_max is not None and (REF_DATE - d_max).days > 3:
            status = f"Cũ hơn {(REF_DATE - d_max).days} ngày so với ngày mới nhất"
        else:
            status = "Bình thường"

        rows.append({
            "Sheet": label,
            "Số dòng": len(raw),
            "Từ ngày": f"{d_min:%d/%m/%Y}" if d_min is not None and pd.notna(d_min) else "—",
            "Đến ngày": f"{d_max:%d/%m/%Y}" if d_max is not None and pd.notna(d_max) else "—",
            "Cột đơn vị": "Bưu Cục" if units and units[0] != "Chưa phân loại" else "không nhận ra",
            "Giá trị đơn vị": ", ".join(units) if units else "—",
            "Tình trạng": status,
            "Các cột trong sheet": " | ".join(str(c) for c in original_cols),
        })
    return pd.DataFrame(rows)


def kpi_target(keys, fallback: float, exclude=(), bc="Tất cả") -> float:
    """Đọc mốc KPI từ sheet KPI (Tháng | Bưu cục | %GTC Tổng | %GTC TTS | %Trả hàng | Doanh thu).
    Sheet có thể còn trống — khi bạn điền số vào là dashboard tự nhận, không phải sửa code."""
    if DF_KPI.empty:
        return float(fallback)
    df = DF_KPI
    mcol = pick_col(df, [["thang"]])
    if mcol is not None:
        months = pd.to_numeric(df[mcol], errors="coerce")
        same = df[months == REF_DATE.month]
        if not same.empty:
            df = same
    if "Bưu Cục" in df.columns:
        pick = (df[df["Bưu Cục"].map(norm) == norm(bc)] if bc != "Tất cả"
                else df[df["Bưu Cục"].map(is_total_row)])
        if not pick.empty:
            df = pick
    col = pick_col(df, keys, exclude=exclude)
    if col is None:
        return float(fallback)
    vals = rescale_pct(_as_series(df[col])).dropna()
    return float(vals.iloc[-1]) if not vals.empty else float(fallback)


# ═══════════════════════════════════════════════════════════════════════
# 9. BANNER & THANH BÊN
# ═══════════════════════════════════════════════════════════════════════
st.markdown(f"""
<div class="ghn-banner">
    <h1>Trung Tâm Vận Hành Chiến Lược — GHN</h1>
    <p>Hiệu suất thực · Quyết định nhanh · AI cố vấn &nbsp;|&nbsp;
       {esc(AUTH['id'])} · {esc(AUTH['role'])} &nbsp;|&nbsp;
       Dữ liệu đến {REF_DATE:%d/%m/%Y} · Đồng bộ {datetime.now():%H:%M}</p>
</div>""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown(f"### {AUTH['id']}")
    st.caption(f"Vai trò: {AUTH['role']}")
    st.divider()
    if st.button("Làm mới dữ liệu", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    if st.button("Đăng xuất", use_container_width=True):
        st.session_state.auth = None
        st.rerun()
    errs = st.session_state.get("load_errors", {})
    if errs:
        st.divider()
        st.error(f"{len(errs)} nguồn chưa đọc được:\n\n" + "\n".join(f"- {k}" for k in errs))

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "TỔNG QUAN", "VẬN HÀNH", "KINH DOANH",
    "NĂNG SUẤT & LƯƠNG", "TIẾN ĐỘ KPI", "AI CỐ VẤN",
])


# ═══════════════════════════════════════════════════════════════════════
# TAB 1 — TỔNG QUAN
# ═══════════════════════════════════════════════════════════════════════
with tab1:
    bc_ov = st.selectbox("Phạm vi báo cáo", ALL_BC, key="bc_ov")

    g_gtc = scope(M_GTC, bc_ov)
    g_tra = scope(M_TRA, bc_ov)
    g_tts = scope(M_TTS, bc_ov)
    g_odr = scope(M_ODR, bc_ov)
    g_dt = scope(M_DT, bc_ov)

    t_gtc_ov = kpi_target([["kpi", "gtc"], ["% gtc"], ["gtc"]], 70.0,
                          exclude=["tts", "tiktok"], bc=bc_ov)
    t_tts_ov = kpi_target([["gtc tts"], ["tts"], ["tiktok"]], 80.0, bc=bc_ov)
    t_tra_ov = kpi_target([["tra hang"], ["tra"]], 5.0, bc=bc_ov)
    t_odr_ov = 98.0

    p_gtc = get_period_data(g_gtc, REF_DATE)
    p_tra = get_period_data(g_tra, REF_DATE)
    p_tts = get_period_data(g_tts, REF_DATE)
    p_odr = get_period_data(g_odr, REF_DATE)
    p_dt = get_period_data(g_dt, REF_DATE, "sum")
    # Khung sản lượng: lấy chính cột Trọng Số làm giá trị để cộng dồn.
    # LƯU Ý: phải GHI ĐÈ đúng cột "Giá Trị" sẵn có. Nếu tạo cột tạm rồi rename,
    # khung sẽ có HAI cột cùng tên "Giá Trị", khiến df["Giá Trị"] trả về DataFrame
    # và float() báo lỗi "must be a real number, not 'Series'".
    if g_gtc.empty:
        vol_frame = g_gtc
    else:
        vol_frame = g_gtc.copy()
        vol_frame["Giá Trị"] = vol_frame["Trọng Số"]
    p_vol = get_period_data(vol_frame, REF_DATE, "sum")

    section("Chỉ số nổi bật hôm nay")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(metric_card("Sản lượng hôm nay", f"{p_vol['n']:,.0f}",
                                p_vol["n"] - p_vol["n1"], "đơn", True, p_vol["has_n1"],
                                accent=True), unsafe_allow_html=True)
    with c2:
        st.markdown(metric_card("%GTC tổng", f"{p_gtc['n']:,.2f}%",
                                p_gtc["n"] - p_gtc["n1"], "%", True, p_gtc["has_n1"]),
                    unsafe_allow_html=True)
    with c3:
        st.markdown(metric_card("%GTC TikTok", f"{p_tts['n']:,.2f}%",
                                p_tts["n"] - p_tts["n1"], "%", True, p_tts["has_n1"]),
                    unsafe_allow_html=True)
    with c4:
        st.markdown(metric_card("Doanh thu tháng", fmt_money(p_dt["m"]),
                                p_dt["m"] - p_dt["m1"], "đ", True, p_dt["has_m1"]),
                    unsafe_allow_html=True)

    section("Cảnh báo — chỉ số chưa đạt mốc")
    checks = [
        ("GTC tổng", p_gtc["n"], t_gtc_ov, True, "tỷ lệ giao thành công toàn khu vực"),
        ("GTC TikTok", p_tts["n"], t_tts_ov, True, "đơn sàn TikTok Shop"),
        ("ODR TikTok", p_odr["n"], t_odr_ov, True, "cam kết đúng hạn với sàn, thấp là bị phạt"),
        ("Tỷ lệ trả hàng", p_tra["n"], t_tra_ov, False, "đơn quay đầu về kho"),
    ]
    issues = []
    for name, actual, target, hib, why in checks:
        if not target:
            continue
        gap = (actual - target) if hib else (target - actual)
        if gap < 0:
            issues.append((abs(gap) / target, name, actual, target, gap, why))
    issues.sort(reverse=True)

    if issues:
        for sev, name, actual, target, gap, why in issues:
            tag = "tag-danger" if sev > 0.05 else "tag-warn"
            label = "CẦN XỬ LÝ" if sev > 0.05 else "THEO DÕI"
            cls = "danger" if sev > 0.05 else ""
            st.markdown(
                f"<div class='ghn-alert {cls}'><span class='a-tag {tag}'>{label}</span>"
                f"<b>{esc(name)}</b> đang ở <b>{actual:,.2f}%</b>, mốc là <b>{target:,.2f}%</b> — "
                f"lệch <b>{abs(gap):,.2f}</b> điểm phần trăm. {esc(why.capitalize())}.</div>",
                unsafe_allow_html=True)
    else:
        st.markdown(
            "<div class='ghn-alert ok'><span class='a-tag tag-ok'>ĐẠT MỐC</span>"
            "Toàn bộ chỉ số đang bám sát hoặc vượt mục tiêu đề ra.</div>",
            unsafe_allow_html=True)

    section("Diễn biến các chỉ số vận hành — 30 ngày gần nhất")
    w30 = REF_DATE - timedelta(days=29)
    series = [("%GTC tổng", daily(sl(g_gtc, w30, REF_DATE)), PRIMARY),
              ("%GTC TikTok", daily(sl(g_tts, w30, REF_DATE)), "#00B4D8"),
              ("ODR TikTok", daily(sl(g_odr, w30, REF_DATE)), SUCCESS),
              ("%Trả hàng", daily(sl(g_tra, w30, REF_DATE)), DANGER)]
    series = [(n, d, c) for n, d, c in series if not d.empty]
    if series:
        fig_ov = go.Figure()
        for name, d, color in series:
            fig_ov.add_trace(go.Scatter(x=d["Ngày"], y=d["Giá Trị"], name=name,
                                        mode="lines+markers",
                                        line=dict(color=color, width=3), marker=dict(size=6)))
        fig_ov.add_hline(y=t_gtc_ov, line_dash="dot", line_color=ACCENT, line_width=2,
                         annotation_text="Mốc GTC", annotation_position="top left")
        fig_ov.update_yaxes(ticksuffix="%")
        fig_ov.update_xaxes(tickformat="%d/%m")
        fig_ov.update_layout(height=480)
        st.plotly_chart(fig_ov, use_container_width=True)
        if max(len(d) for _, d, _ in series) < 2:
            st.caption("Mới có 1 ngày dữ liệu — biểu đồ sẽ đầy đủ khi sheet tích lũy thêm ngày.")
    else:
        note("Chưa có dữ liệu vận hành trong 30 ngày gần nhất.")

    section("Chẩn đoán nguồn dữ liệu")
    st.caption("Mở bảng này khi thấy một con số bị sai hoặc bằng 0. Nó cho biết từng sheet "
               "đọc được bao nhiêu dòng, dữ liệu đến ngày nào, và có nhận ra cột đơn vị không.")
    with st.expander("Xem tình trạng 12 nguồn dữ liệu", expanded=False):
        diag = sheet_diagnostics()
        bad = diag[diag["Tình trạng"] != "Bình thường"]
        if not bad.empty:
            st.warning(
                f"{len(bad)}/{len(diag)} nguồn đang có vấn đề: "
                + ", ".join(f"**{r['Sheet']}** ({r['Tình trạng']})" for _, r in bad.iterrows()),
                icon="⚠️")
        st.dataframe(diag, use_container_width=True, hide_index=True, height=460)
        st.download_button("TẢI CSV CHẨN ĐOÁN",
                           diag.to_csv(index=False).encode("utf-8-sig"),
                           "chan_doan_du_lieu.csv", "text/csv", key="dl_diag")
        st.markdown(
            "**Cách đọc bảng này**\n\n"
            "- *Không nhận ra cột đơn vị*: sheet đặt tên cột khác thường. Khi đó mọi dòng bị gán "
            "\"Chưa phân loại\" và bộ lọc bưu cục sẽ trả về 0.\n"
            "- *Cũ hơn N ngày*: sheet chưa được cập nhật cùng nhịp với các sheet khác. Chỉ số "
            "theo tháng của sheet đó sẽ bằng 0 nếu tháng hiện tại chưa có dòng nào.\n"
            "- *Thiếu cột Ngày*: không so sánh được theo thời gian.")

    section("Phân tích Group Chat — điểm nóng về lương và tác phong")
    chat_input = st.text_area(
        "Dán nội dung thảo luận trên nhóm Zalo hoặc Telegram vào đây",
        height=160, key="chat_extract",
        placeholder="Dán đoạn hội thoại... Nội dung chỉ dùng cho lần phân tích này, không lưu lại.")

    if st.button("TRÍCH XUẤT ĐIỂM NÓNG", key="btn_chat"):
        if not chat_input.strip():
            st.warning("Bạn chưa dán nội dung nhóm vào ô phía trên.")
        else:
            with st.spinner("AI đang đọc nội dung nhóm..."):
                prompt_chat = f"""Bạn là trợ lý nhân sự của GHN. Dưới đây là đoạn hội thoại nội bộ
của nhân viên giao hàng. Hãy phân tích và chỉ ra các điểm nóng.

NỘI DUNG NHÓM:
{chat_input.strip()[:8000]}

Trình bày đúng 4 mục:
1. LƯƠNG & THU NHẬP — anh em đang bàn gì, có bức xúc gì không
2. TÁC PHONG & KỶ LUẬT — dấu hiệu vi phạm, đi muộn, thái độ
3. ĐIỂM ĐẠT — điều gì tích cực đáng ghi nhận
4. ĐIỂM CHƯA ĐẠT & CẦN XỬ LÝ — tối đa 4 việc, mỗi việc gắn người chịu trách nhiệm

Nếu không có dữ liệu cho mục nào thì ghi rõ "không có thông tin", đừng suy đoán.
Kết thúc bằng dòng [HẾT]."""
                st.session_state.ai_cache["chat"] = ask_ai(prompt_chat)

    if st.session_state.ai_cache.get("chat"):
        st.markdown(f"<div class='ghn-alert'>{st.session_state.ai_cache['chat']}</div>",
                    unsafe_allow_html=True)
        if st.button("GỬI LÊN NHÓM TELEGRAM", key="tele_chat"):
            ok, msg = send_telegram("[PHÂN TÍCH NHÓM]\n\n"
                                    + st.session_state.ai_cache["chat"].replace("*", ""))
            (st.success if ok else st.error)(msg)


# ═══════════════════════════════════════════════════════════════════════
# TAB 2 — VẬN HÀNH
# ═══════════════════════════════════════════════════════════════════════
with tab2:
    f1, f2, f3 = st.columns([1.1, 1.5, 1.2])
    with f1:
        bc_vh = st.selectbox("Bưu cục", ALL_BC, key="bc_vh")
    with f2:
        quick_vh = st.radio("Chọn nhanh", ["7 ngày gần nhất", "Ngày", "Tuần", "Tháng", "Tùy chọn"],
                            horizontal=True, key="quick_vh")
    if quick_vh == "7 ngày gần nhất":
        # Mặc định khi mở trang: 7 ngày gần nhất theo giờ Việt Nam (N-7 đến N-1).
        a_vh, b_vh = DEFAULT_7D_START, DEFAULT_7D_END
    elif quick_vh == "Ngày":
        a_vh, b_vh = DEFAULT_N1, DEFAULT_N1
    elif quick_vh == "Tuần":
        a_vh, b_vh = REF_DATE - timedelta(days=REF_DATE.weekday()), REF_DATE
    elif quick_vh == "Tháng":
        a_vh, b_vh = REF_DATE.replace(day=1), REF_DATE
    else:
        a_vh, b_vh = DATA_MIN, REF_DATE
    with f3:
        # sync_token = lựa chọn Chọn nhanh -> đổi nút là ô ngày tự cập nhật theo.
        a_vh, b_vh = synced_range_picker("Khoảng ngày", a_vh, b_vh, "date_vh",
                                         sync_token=quick_vh)

    lh_options = (sorted({x for x in M_CA["Chiều"].dropna().astype(str).str.strip().unique()
                          if x and x.lower() != "nan"})
                  if "Chiều" in M_CA.columns else [])
    lh_pick = st.multiselect("Loại hàng / ca làm việc", lh_options, default=lh_options, key="lh_vh")

    st.caption(f"Đang xem {a_vh:%d/%m/%Y} – {b_vh:%d/%m/%Y} · Bưu cục: {bc_vh}. "
               "Mọi tỷ lệ % tính bằng trung bình có trọng số theo sản lượng.")

    t_gtc_vh = kpi_target([["kpi", "gtc"], ["% gtc"], ["gtc"]], 70.0,
                          exclude=["tts", "tiktok"], bc=bc_vh)
    t_tts_vh = kpi_target([["gtc tts"], ["tts"], ["tiktok"]], 80.0, bc=bc_vh)
    t_tra_vh = kpi_target([["tra hang"], ["tra"]], 5.0, bc=bc_vh)

    s_gtc = sl(scope(M_GTC, bc_vh), a_vh, b_vh)
    s_tra = sl(scope(M_TRA, bc_vh), a_vh, b_vh)
    s_gtb = sl(scope(M_GTB, bc_vh), a_vh, b_vh)
    s_tts = sl(scope(M_TTS, bc_vh), a_vh, b_vh)
    s_odr = sl(scope(M_ODR, bc_vh), a_vh, b_vh)
    s_gan = sl(scope(M_GAN, bc_vh), a_vh, b_vh)
    s_lead = sl(scope(M_LEAD, bc_vh), a_vh, b_vh)
    s_ca = sl(scope(M_CA, bc_vh), a_vh, b_vh)
    if lh_pick and "Chiều" in s_ca.columns:
        s_ca = s_ca[s_ca["Chiều"].isin(lh_pick)]

    # 2.1 GTC tổng
    section("1. Báo cáo GTC tổng")
    period_cards(scope(M_GTC, bc_vh), REF_DATE, "%", True, "wavg", "%GTC")
    cA, cB = st.columns([1.6, 1])
    with cA:
        combo_chart(s_gtc, "Sản lượng và %GTC theo ngày", "Sản lượng", "% GTC", t_gtc_vh)
    with cB:
        bc_bar_chart(sl(M_GTC, a_vh, b_vh), t_gtc_vh, True, "So sánh giữa bưu cục")

    # 2.2 Sản lượng và %GTC theo ca
    section("2. Sản lượng và %GTC theo ca làm việc")
    if not s_ca.empty and "Chiều" in s_ca.columns:
        g_ca = (s_ca.assign(_p=s_ca["Giá Trị"].fillna(0) * s_ca["Trọng Số"])
                    .groupby(["Ngày", "Chiều"], as_index=False)
                    .agg(_p=("_p", "sum"), w=("Trọng Số", "sum")))
        g_ca["r"] = np.where(g_ca["w"] > 0, g_ca["_p"] / g_ca["w"], np.nan)

        rows_ca = []
        for ca in sorted(g_ca["Chiều"].unique()):
            sub_ca = g_ca[g_ca["Chiều"] == ca]
            rows_ca.append([esc(ca), f"{sub_ca['w'].sum():,.0f} đơn",
                            f"{wavg(sub_ca['r'], sub_ca['w']):,.2f}%"])
        st.markdown(html_table(["Ca / loại hàng", "Sản lượng", "%GTC bình quân"], rows_ca),
                    unsafe_allow_html=True)

        cC, cD = st.columns(2)
        palette = [PRIMARY, ACCENT, SUCCESS, "#00B4D8"]
        with cC:
            fig_ca1 = go.Figure()
            for i, ca in enumerate(sorted(g_ca["Chiều"].unique())):
                sub_ca = g_ca[g_ca["Chiều"] == ca]
                fig_ca1.add_trace(go.Bar(x=sub_ca["Ngày"], y=sub_ca["w"], name=ca,
                                         marker_color=palette[i % len(palette)],
                                         marker_line_width=0))
            fig_ca1.update_layout(barmode="stack", title="Sản lượng theo ca", height=430)
            fig_ca1.update_xaxes(tickformat="%d/%m")
            st.plotly_chart(fig_ca1, use_container_width=True)
        with cD:
            fig_ca2 = go.Figure()
            for i, ca in enumerate(sorted(g_ca["Chiều"].unique())):
                sub_ca = g_ca[g_ca["Chiều"] == ca]
                fig_ca2.add_trace(go.Scatter(x=sub_ca["Ngày"], y=sub_ca["r"], name=ca,
                                             mode="lines+markers",
                                             line=dict(color=palette[i % len(palette)], width=3),
                                             marker=dict(size=6)))
            fig_ca2.update_layout(title="%GTC theo ca", height=430)
            fig_ca2.update_yaxes(ticksuffix="%", range=[0, 100])
            fig_ca2.update_xaxes(tickformat="%d/%m")
            st.plotly_chart(fig_ca2, use_container_width=True)
    else:
        note("Chưa đọc được cột ca hoặc loại hàng trong sheet Sản lượng theo ca.")

    # 2.3 Trả hàng
    section("3. Tỷ lệ trả hàng (càng thấp càng tốt)")
    period_cards(scope(M_TRA, bc_vh), REF_DATE, "%", False, "wavg", "%Trả hàng")
    cE, cF = st.columns([1.6, 1])
    with cE:
        line_chart(s_tra, "Tỷ lệ trả hàng theo ngày", DANGER, "%", t_tra_vh)
    with cF:
        bc_bar_chart(sl(M_TRA, a_vh, b_vh), t_tra_vh, False, "So sánh giữa bưu cục")

    # 2.4 GTB thu tiền
    section("4. Tỷ lệ GTB — giao thất bại nhưng thu được tiền")
    period_cards(scope(M_GTB, bc_vh), REF_DATE, "%", True, "wavg", "%GTB")
    line_chart(s_gtb, "Tỷ lệ GTB thu tiền theo ngày", SUCCESS, "%")

    # 2.5 GTC TTS
    section("5. GTC TikTok Shop")
    period_cards(scope(M_TTS, bc_vh), REF_DATE, "%", True, "wavg", "%GTC TTS")
    cG, cH = st.columns([1.6, 1])
    with cG:
        combo_chart(s_tts, "Sản lượng và %GTC TikTok Shop", "Sản lượng TTS", "% GTC TTS", t_tts_vh)
    with cH:
        bc_bar_chart(sl(M_TTS, a_vh, b_vh), t_tts_vh, True, "So sánh giữa bưu cục")

    # 2.6 ODR TTS
    section("6. ODR TikTok Shop — cam kết giao đúng hạn với sàn")
    period_cards(scope(M_ODR, bc_vh), REF_DATE, "%", True, "wavg", "ODR")
    line_chart(s_odr, "Tỷ lệ ODR theo ngày", ACCENT, "%", 98.0)

    # 2.7 Gán & Leadtime (chỉ số có sẵn trong sheet)
    section("7. Tỷ lệ gán và Leadtime")
    cI, cJ = st.columns(2)
    with cI:
        if not s_gan.empty:
            st.markdown(metric_card("Tỷ lệ gán bình quân",
                                    f"{wavg(s_gan['Giá Trị'], s_gan['Trọng Số']):,.2f}%",
                                    None, sub="trong khoảng đã chọn"), unsafe_allow_html=True)
            line_chart(s_gan, "Tỷ lệ gán theo ngày", "#00B4D8", "%")
        else:
            note("Chưa đọc được cột % Gán.")
    with cJ:
        if not s_lead.empty:
            st.markdown(metric_card("Leadtime bình quân",
                                    f"{s_lead['Giá Trị'].mean():,.1f} giờ",
                                    None, sub="thời gian xử lý đơn"), unsafe_allow_html=True)
            g_lead = s_lead.groupby("Ngày", as_index=False)["Giá Trị"].mean()
            fig_lead = px.line(g_lead, x="Ngày", y="Giá Trị", markers=True,
                               title="Leadtime theo ngày (giờ)")
            fig_lead.update_traces(line=dict(color=PRIMARY, width=3), marker=dict(size=7))
            fig_lead.update_xaxes(tickformat="%d/%m")
            fig_lead.update_layout(height=320, showlegend=False, margin=dict(t=90, b=70))
            st.plotly_chart(fig_lead, use_container_width=True)
        else:
            note("Chưa đọc được cột Leadtime.")

    section("Dữ liệu chi tiết vận hành")
    if not s_gtc.empty:
        detail_vh = s_gtc.rename(columns={"Trọng Số": "Sản lượng", "Giá Trị": "%GTC"})[
            ["Ngày", "Bưu Cục", "Sản lượng", "%GTC"]].sort_values("Ngày", ascending=False)
        st.dataframe(detail_vh, use_container_width=True, hide_index=True, height=300,
                     column_config={
                         "Ngày": st.column_config.DateColumn(format="DD/MM/YYYY"),
                         "Sản lượng": st.column_config.NumberColumn(format="%,d"),
                         "%GTC": st.column_config.NumberColumn(format="%.2f%%")})
        st.download_button("TẢI CSV", detail_vh.to_csv(index=False).encode("utf-8-sig"),
                           "van_hanh_chi_tiet.csv", "text/csv", key="dl_vh")
    else:
        note("Không có dữ liệu chi tiết trong khoảng đã chọn.")


# ═══════════════════════════════════════════════════════════════════════
# TAB 3 — KINH DOANH
# ═══════════════════════════════════════════════════════════════════════
with tab3:
    k1, k2, k3, k4 = st.columns([1, 1.1, 1.5, 1.2])
    with k1:
        bc_kd = st.selectbox("Bưu cục", ALL_BC, key="bc_kd")
    with k2:
        view_kd = st.radio("Gộp theo", ["Ngày", "Tuần", "Tháng"], horizontal=True, key="view_kd")
    with k3:
        quick_kd = st.radio("Chọn nhanh", ["7 ngày gần nhất", "Ngày", "Tuần", "Tháng", "Tùy chọn"],
                            horizontal=True, key="quick_kd")
    if quick_kd == "7 ngày gần nhất":
        a_kd, b_kd = DEFAULT_7D_START, DEFAULT_7D_END
    elif quick_kd == "Ngày":
        a_kd, b_kd = DEFAULT_N1, DEFAULT_N1
    elif quick_kd == "Tuần":
        a_kd, b_kd = REF_DATE - timedelta(days=REF_DATE.weekday()), REF_DATE
    elif quick_kd == "Tháng":
        a_kd, b_kd = REF_DATE.replace(day=1), REF_DATE
    else:
        a_kd, b_kd = DATA_MIN, REF_DATE
    with k4:
        a_kd, b_kd = synced_range_picker("Khoảng ngày", a_kd, b_kd, "date_kd",
                                         sync_token=quick_kd)

    dt_scope = scope(M_DT, bc_kd)

    # Sheet doanh thu dùng cột "Vùng" (ví dụ TTB) chứ không phải bưu cục, nên khi
    # lọc theo một bưu cục cụ thể sẽ không khớp dòng nào. Nói rõ thay vì hiện số 0.
    if not M_DT.empty and dt_scope.empty:
        don_vi = ", ".join(M_DT["Bưu Cục"].dropna().astype(str).unique()[:5])
        st.warning(
            f"Sheet doanh thu không có dòng nào thuộc **{bc_kd}**. Sheet này ghi theo đơn vị: "
            f"**{don_vi}** — đây là cấp vùng, không phải cấp bưu cục. "
            "Chọn phạm vi *Tất cả* để xem đúng số, hoặc bổ sung cột Bưu cục vào sheet.",
            icon="⚠️")
    elif M_DT.empty:
        st.warning("Chưa đọc được sheet doanh thu. Mở mục Chẩn đoán nguồn dữ liệu ở tab "
                   "Tổng quan để xem lý do.", icon="⚠️")
    else:
        dt_max = dt_scope["Ngày"].max()
        if pd.notna(dt_max) and dt_max.to_period("M") != REF_DATE.to_period("M"):
            st.warning(
                f"Sheet doanh thu mới có dữ liệu đến **{dt_max:%d/%m/%Y}**, trong khi ngày phân "
                f"tích là **{REF_DATE:%d/%m/%Y}**. Vì vậy con số 'lũy kế tháng này' đang bằng 0. "
                "Cập nhật sheet doanh thu là hết.", icon="⚠️")

    section("1. Doanh thu — so sánh N-1, W-1, M-1")
    p_kd = period_cards(dt_scope, REF_DATE, "đ", True, "sum", "Doanh thu")

    section("2. Tiến độ doanh thu tháng so với KPI")
    kpi_dt_sheet = kpi_target([["doanh thu"]], 0.0, bc=bc_kd)
    default_dt = kpi_dt_sheet if kpi_dt_sheet > 0 else 71_000_000.0
    st.session_state.kpi_manual.setdefault(f"dt_{bc_kd}", float(default_dt))

    d1, d2 = st.columns([1, 2.2])
    with d1:
        st.session_state.kpi_manual[f"dt_{bc_kd}"] = st.number_input(
            "Mục tiêu doanh thu tháng (đ)", min_value=0.0,
            value=float(st.session_state.kpi_manual[f"dt_{bc_kd}"]), step=1_000_000.0,
            key=f"num_dt_{bc_kd}")
    target_dt = float(st.session_state.kpi_manual[f"dt_{bc_kd}"])
    if kpi_dt_sheet > 0:
        st.caption(f"Mốc lấy từ sheet KPI: {fmt_money(kpi_dt_sheet)}. Có thể chỉnh tay ở trên.")
    else:
        st.caption("Sheet KPI chưa có số doanh thu — đang dùng mốc nhập tay. "
                   "Điền vào sheet là dashboard tự nhận.")

    m_start = REF_DATE.replace(day=1)
    days_done = max((REF_DATE - m_start).days + 1, 1)
    days_total = month_end(m_start).day
    forecast_dt = p_kd["m"] / days_done * days_total

    with d2:
        e1, e2, e3 = st.columns(3)
        with e1:
            st.markdown(metric_card("Lũy kế tháng này", fmt_money(p_kd["m"]), None,
                                    sub=f"đã qua {days_done}/{days_total} ngày"),
                        unsafe_allow_html=True)
        with e2:
            st.markdown(metric_card("Dự phóng cuối tháng", fmt_money(forecast_dt), None,
                                    sub="theo tốc độ hiện tại", accent=True),
                        unsafe_allow_html=True)
        with e3:
            thieu = max(target_dt - forecast_dt, 0)
            st.markdown(metric_card("Còn thiếu so với mục tiêu", fmt_money(thieu), None,
                                    sub="nếu giữ nguyên tốc độ"), unsafe_allow_html=True)

    section(f"3. Biểu đồ doanh thu — gộp theo {view_kd.lower()}")
    d_kd_range = sl(dt_scope, a_kd, b_kd)
    if not d_kd_range.empty:
        plot_kd = d_kd_range.copy()
        if view_kd == "Tuần":
            plot_kd["Ngày"] = plot_kd["Ngày"].dt.to_period("W").apply(lambda r: r.start_time)
        elif view_kd == "Tháng":
            plot_kd["Ngày"] = plot_kd["Ngày"].dt.to_period("M").apply(lambda r: r.start_time)
        plot_kd = plot_kd.groupby("Ngày", as_index=False)["Giá Trị"].sum()
        fig_kd = px.bar(plot_kd, x="Ngày", y="Giá Trị", title="Doanh thu")
        fig_kd.update_traces(marker_color=PRIMARY, marker_line_width=0)
        if view_kd == "Tháng":
            fig_kd.add_hline(y=target_dt, line_dash="dot", line_color=ACCENT, line_width=2,
                             annotation_text="Mục tiêu", annotation_position="top left")
        fig_kd.update_xaxes(tickformat="%d/%m" if view_kd == "Ngày" else "%m/%Y")
        fig_kd.update_layout(height=340, showlegend=False, margin=dict(t=90, b=70))
        st.plotly_chart(fig_kd, use_container_width=True)
    else:
        note("Chưa có doanh thu trong khoảng đã chọn.")

    section("4. Phễu tiếp xúc khách hàng mới")
    pheu_df = DF_PHEU.copy()
    if not pheu_df.empty and "Bưu Cục" in pheu_df.columns and bc_kd != "Tất cả":
        pheu_df = pheu_df[pheu_df["Bưu Cục"].map(norm) == norm(bc_kd)]
    status_col = pick_col(pheu_df, [["trang thai"]])

    fA, fB = st.columns([1, 1.2])
    with fA:
        if not pheu_df.empty and status_col:
            cnt = (pheu_df.groupby(status_col).size().reset_index(name="Số lượng")
                   .sort_values("Số lượng", ascending=False))
            fig_funnel = go.Figure(go.Funnel(
                y=cnt[status_col], x=cnt["Số lượng"], textinfo="value+percent initial",
                marker=dict(color=[PRIMARY, "#00B4D8", ACCENT, SUCCESS, MUTED]),
                connector=dict(line=dict(color=LINE, width=1))))
            fig_funnel.update_layout(title="Phễu trạng thái khách hàng", height=380,
                                     showlegend=False,
                                     hovermode="closest")
            st.plotly_chart(fig_funnel, use_container_width=True)
        else:
            note("Chưa đọc được cột Trạng thái trong sheet phễu khách hàng.")
    with fB:
        if not pheu_df.empty and status_col:
            cnt = (pheu_df.groupby(status_col).size().reset_index(name="Số lượng")
                   .sort_values("Số lượng", ascending=False))
            st.dataframe(cnt, use_container_width=True, hide_index=True, height=200)
            st.markdown(metric_card("Tổng khách trong phễu", f"{len(pheu_df):,}", None,
                                    sub="tất cả trạng thái"), unsafe_allow_html=True)
        else:
            note("Không có dữ liệu phễu.")

    section("5. Danh sách khách hàng tiềm năng")
    st.caption("Chỉ hiển thị các dòng có cột trạng thái ghi 'Khách hàng tiềm năng'.")
    kh_src = DF_KHM if not DF_KHM.empty else pheu_df
    kh_status = pick_col(kh_src, [["trang thai"]])
    if not kh_src.empty and kh_status:
        tn = kh_src[kh_src[kh_status].astype(str).map(lambda x: "tiem nang" in norm(x))]
        if not tn.empty:
            drop_cols = [c for c in tn.columns if tn[c].isna().all()]
            tn_show = tn.drop(columns=drop_cols)
            st.markdown(metric_card("Khách hàng tiềm năng chờ chốt", f"{len(tn_show):,}",
                                    None, accent=True, sub="đang trong danh sách"),
                        unsafe_allow_html=True)
            st.dataframe(tn_show, use_container_width=True, hide_index=True, height=340)
            st.download_button("TẢI CSV DANH SÁCH",
                               tn_show.to_csv(index=False).encode("utf-8-sig"),
                               "khach_hang_tiem_nang.csv", "text/csv", key="dl_tn")
        else:
            note("Không có dòng nào ở trạng thái 'Khách hàng tiềm năng'.")
    else:
        note("Cần cột Trạng thái trong sheet Khách hàng mới để lọc danh sách tiềm năng.")


# ═══════════════════════════════════════════════════════════════════════
# TAB 4 — NĂNG SUẤT VÀ LƯƠNG
# ═══════════════════════════════════════════════════════════════════════
with tab4:
    nv_col_luong = pick_col(DF_LUONG, [["nhan vien"]])
    nv_col_gtc = pick_col(DF_NSGTC, [["nhan vien"]])

    def staff_id(name) -> str:
        """Khóa gộp nhân viên.

        Hai sheet ghi TÊN KHÁC NHAU cho cùng một người:
          sheet lương    : '3029537-Lê Thị Thúy Kiều'
          sheet năng suất: '3029537_Lê Thị Kiều'
        Khác cả dấu phân cách lẫn cách viết tên. Vì vậy gộp theo MÃ NHÂN VIÊN
        (cụm số ở đầu). Nếu không có mã thì rơi về so tên đã bỏ dấu và bỏ '_', '-'.
        """
        s = str(name).strip()
        m = re.match(r"^\s*(\d{4,})", s)
        if m:
            return m.group(1)
        return norm(s).replace("_", "").replace("-", "").replace(" ", "")

    def staff_label(name) -> str:
        """Tên hiển thị: thống nhất dùng dấu gạch dưới cho dễ đọc."""
        return re.sub(r"[_\-]+", " · ", str(name).strip(), count=1)

    n1, n2, n3 = st.columns([1.1, 1.3, 1.3])
    with n1:
        bc_ns = st.selectbox("Bưu cục", ALL_BC, key="bc_ns")

    # Gom danh sách nhân viên từ CẢ HAI sheet, gộp theo mã để không bị trùng dòng.
    staff_map: dict[str, str] = {}
    for _df, _col in ((DF_LUONG, nv_col_luong), (DF_NSGTC, nv_col_gtc)):
        if _col and not _df.empty:
            _scoped = _df if bc_ns == "Tất cả" else _df[_df["Bưu Cục"].map(norm) == norm(bc_ns)]
            for raw in _scoped[_col].dropna().astype(str).str.strip().unique():
                if not raw or raw == "nan":
                    continue
                key_id = staff_id(raw)
                # Giữ bản tên dài hơn (thường đầy đủ hơn) làm nhãn hiển thị
                if key_id not in staff_map or len(raw) > len(staff_map[key_id]):
                    staff_map[key_id] = raw

    staff_display = {staff_label(v): k for k, v in staff_map.items()}
    with n2:
        nv_ns = st.selectbox("Nhân viên", ["Tất cả"] + sorted(staff_display), key="nv_ns")
    nv_id = staff_display.get(nv_ns)
    with n3:
        ns_pa, ns_pb, _, _, _, _ = pay_period(REF_DATE)
        a_ns, b_ns = date_range_picker("Khoảng ngày (theo kỳ lương)", ns_pa, ns_pb, "date_ns")

    if nv_ns != "Tất cả":
        st.caption(f"Đang lọc theo mã nhân viên **{nv_id}** — gộp mọi cách ghi tên của người này "
                   "ở cả sheet lương và sheet năng suất.")

    def filter_staff(df, col):
        if df is None or df.empty:
            return pd.DataFrame()
        out = df if bc_ns == "Tất cả" else df[df["Bưu Cục"].map(norm) == norm(bc_ns)]
        if nv_ns != "Tất cả" and col and nv_id:
            out = out[out[col].map(staff_id) == nv_id]
        return out

    L = filter_staff(DF_LUONG, nv_col_luong)
    G = filter_staff(DF_NSGTC, nv_col_gtc)

    # ── Logic kỳ lương GHN ─────────────────────────────────────────────
    # Ngày 01–15  -> Kỳ 20 (chi lương ngày 20 cùng tháng)
    # Ngày 16–cuối -> Kỳ 05 (chi lương ngày 05 tháng sau)
    if REF_DATE.day <= 15:
        cur_a, cur_b = REF_DATE.replace(day=1), REF_DATE.replace(day=15)
        prev_b = cur_a - timedelta(days=1)
        prev_a = prev_b.replace(day=16)
        cur_name = f"Kỳ 20 · tháng {cur_a:%m/%Y}"
        prev_name = f"Kỳ 05 · tháng {prev_a:%m/%Y}"
    else:
        cur_a = REF_DATE.replace(day=16)
        cur_b = month_end(cur_a)
        prev_a, prev_b = REF_DATE.replace(day=1), REF_DATE.replace(day=15)
        cur_name = f"Kỳ 05 · tháng {cur_a:%m/%Y}"
        prev_name = f"Kỳ 20 · tháng {prev_a:%m/%Y}"

    st.info(f"**Kỳ lương hiện tại:** {cur_name} ({cur_a:%d/%m} – {cur_b:%d/%m}) "
            f"— so với {prev_name}. "
            f"Kỳ 20 tính từ ngày 01 đến 15 chi lương ngày 20; "
            f"Kỳ 05 tính từ ngày 16 đến hết tháng chi lương ngày 05 tháng sau.")

    col_price = pick_col(L, [["don gia"]])
    col_gan = pick_col(G, [["gan giao"], ["so don gan"], ["gan"]])
    col_gtc = pick_col(G, [["giao tinh luong"], ["don gtc"], ["giao thanh cong"], ["gtc"]],
                       exclude=["%"])
    # %GTC lấy thẳng cột "%GTC" của sheet Năng suất nhân viên (gid 1695228663)
    col_pct = pick_col(G, [["% gtc"], ["%gtc"]])
    # Sản lượng GTC = Đơn GTC + Đơn GTBTT, lấy ở sheet Đơn Giá - Lương (gid 2000227799)
    col_don_gtc = pick_col(L, [["don gtc"]], exclude=["lhh", "%"])
    col_don_gtbtt = pick_col(L, [["don gtbtt"], ["gtbtt"]], exclude=["lhh", "%"])
    pay_cols = {k: pick_col(L, [[k.lower()], [k.split()[-1].lower()]]) for k in SALARY_PARTS}
    pay_cols = {k: v for k, v in pay_cols.items() if v}

    def cut(df, a, b):
        if df is None or df.empty or "Ngày" not in df.columns:
            return pd.DataFrame()
        return df[(df["Ngày"] >= a) & (df["Ngày"] <= b)]

    L_cur, L_prev = cut(L, cur_a, cur_b), cut(L, prev_a, prev_b)
    G_cur, G_prev = cut(G, cur_a, cur_b), cut(G, prev_a, prev_b)
    L_range, G_range = cut(L, a_ns, b_ns), cut(G, a_ns, b_ns)

    def avg_price(d):
        """Đơn giá trung bình — giữ nguyên độ chính xác, không làm tròn."""
        if not col_price or d is None or d.empty:
            return 0.0
        s = pd.to_numeric(_as_series(d[col_price]), errors="coerce")
        return float(s.mean()) if s.notna().any() else 0.0

    def sum_gtc(d):
        """Sản lượng GTC = Đơn GTC + Đơn GTBTT (theo sheet Đơn Giá - Lương)."""
        if d is None or d.empty:
            return 0.0
        total = 0.0
        for c in (col_don_gtc, col_don_gtbtt):
            if c and c in d.columns:
                total += float(pd.to_numeric(_as_series(d[c]), errors="coerce").sum())
        return total

    def pct_gtc(d):
        """%GTC: bình quân có trọng số của cột %GTC, trọng số là sản lượng gán.
        Không lấy trung bình cộng vì người giao 1 đơn đạt 100% sẽ kéo lệch kết quả."""
        if d is None or d.empty:
            return 0.0
        if col_pct and col_gan:
            return wavg(rescale_pct(d[col_pct]), d[col_gan])
        if col_gan and col_gtc:
            total_gan = float(pd.to_numeric(_as_series(d[col_gan]), errors="coerce").sum())
            total_gtc = float(pd.to_numeric(_as_series(d[col_gtc]), errors="coerce").sum())
            return (total_gtc / total_gan * 100) if total_gan > 0 else 0.0
        return 0.0

    def total_salary(d):
        if not pay_cols or d is None or d.empty:
            return 0.0
        cols = [c for c in pay_cols.values() if c in d.columns]
        if not cols:
            return 0.0
        return float(d[cols].apply(pd.to_numeric, errors="coerce").sum().sum())

    section("1. So sánh kỳ lương hiện tại với kỳ trước")
    rows_ky = [
        # Đơn giá: giữ 3 chữ số thập phân, không làm tròn về số nguyên.
        ["Đơn giá trung bình", f"{avg_price(L_cur):,.3f} đ", f"{avg_price(L_prev):,.3f} đ",
         arrow_span(avg_price(L_cur) - avg_price(L_prev), " đ", 3)],
        # Sản lượng GTC = Đơn GTC + Đơn GTBTT, lấy từ sheet Đơn Giá - Lương.
        ["Sản lượng GTC", f"{sum_gtc(L_cur):,.0f} đơn", f"{sum_gtc(L_prev):,.0f} đơn",
         arrow_span(sum_gtc(L_cur) - sum_gtc(L_prev), " đơn", 0)],
        ["%GTC", f"{pct_gtc(G_cur):,.2f}%", f"{pct_gtc(G_prev):,.2f}%",
         arrow_span(pct_gtc(G_cur) - pct_gtc(G_prev), " pp", 2)],
        ["Tổng lương", fmt_money(total_salary(L_cur)), fmt_money(total_salary(L_prev)),
         arrow_span(total_salary(L_cur) - total_salary(L_prev), " đ", 0)],
    ]
    st.markdown(html_table(["Chỉ tiêu", cur_name, prev_name, "Chênh lệch"], rows_ky),
                unsafe_allow_html=True)
    st.caption("Sản lượng GTC = Đơn GTC + Đơn GTBTT (sheet Đơn Giá - Lương) · "
               "%GTC lấy từ cột %GTC của sheet Năng suất nhân viên, bình quân có trọng số "
               "theo sản lượng gán.")
    st.caption("Tổng lương = LHH LTC + LHH GTC + LHH GTBTT · "
               + " · ".join(f"**{k}**: {v}" for k, v in SALARY_PARTS.items()))

    section("2. %GTC theo Ngày, Tuần, Tháng")
    if col_gan and col_gtc and not G.empty:
        gm = pd.DataFrame({
            "Ngày": G["Ngày"],
            "Giá Trị": np.where(G[col_gan] > 0, G[col_gtc] / G[col_gan] * 100, np.nan),
            "Trọng Số": G[col_gan],
        }).dropna(subset=["Ngày"])
        period_cards(gm, REF_DATE, "%", True, "wavg", "%GTC")
    else:
        gm = pd.DataFrame(columns=["Ngày", "Giá Trị", "Trọng Số"])
        note("Chưa đọc được cột 'Số đơn gán' hoặc 'Đơn giao tính lương' trong sheet năng suất.")

    section("3. Biểu đồ sản lượng gán, sản lượng GTC và %GTC")
    if col_gan and col_gtc and not G_range.empty:
        g_ns = G_range.groupby("Ngày", as_index=False).agg({col_gan: "sum", col_gtc: "sum"})
        g_ns["r"] = np.where(g_ns[col_gan] > 0, g_ns[col_gtc] / g_ns[col_gan] * 100, 0.0)
        fig_ns = make_subplots(specs=[[{"secondary_y": True}]])
        fig_ns.add_trace(go.Bar(x=g_ns["Ngày"], y=g_ns[col_gan], name="Sản lượng gán",
                                marker_color=PRIMARY_SOFT, marker_line_width=0), secondary_y=False)
        fig_ns.add_trace(go.Bar(x=g_ns["Ngày"], y=g_ns[col_gtc], name="Sản lượng GTC",
                                marker_color=PRIMARY, marker_line_width=0), secondary_y=False)
        fig_ns.add_trace(go.Scatter(x=g_ns["Ngày"], y=g_ns["r"], name="% GTC",
                                    mode="lines+markers", line=dict(color=ACCENT, width=3),
                                    marker=dict(size=7)), secondary_y=True)
        fig_ns.update_layout(barmode="overlay", height=470,
                             title="Sản lượng gán · GTC · tỷ lệ")
        fig_ns.update_yaxes(title_text="Số đơn", secondary_y=False)
        fig_ns.update_yaxes(title_text="% GTC", secondary_y=True, ticksuffix="%",
                            showgrid=False, range=[0, 100])
        fig_ns.update_xaxes(tickformat="%d/%m")
        st.plotly_chart(fig_ns, use_container_width=True)
    else:
        note("Chưa đủ dữ liệu gán và giao để vẽ biểu đồ.")

    section("4. Biểu đồ đơn giá và tổng lương theo ngày")
    cK, cL = st.columns(2)
    with cK:
        if col_price and not L_range.empty:
            g_price = L_range.groupby("Ngày", as_index=False)[col_price].mean()
            fig_price = px.line(g_price, x="Ngày", y=col_price, markers=True,
                                title="Đơn giá trung bình theo ngày")
            fig_price.update_traces(line=dict(color=PRIMARY, width=3),
                                    marker=dict(size=7, color=PRIMARY))
            fig_price.update_yaxes(title_text="VNĐ")
            fig_price.update_xaxes(tickformat="%d/%m")
            fig_price.update_layout(height=330, showlegend=False, margin=dict(t=90, b=70))
            st.plotly_chart(fig_price, use_container_width=True)
        else:
            note("Chưa đọc được cột Đơn giá.")
    with cL:
        if pay_cols and not L_range.empty:
            tmp = L_range.copy()
            tmp["Tổng Lương"] = tmp[list(pay_cols.values())].sum(axis=1)
            g_pay = tmp.groupby("Ngày", as_index=False)["Tổng Lương"].sum()
            fig_pay = px.line(g_pay, x="Ngày", y="Tổng Lương", markers=True,
                              title="Tổng lương theo ngày")
            fig_pay.update_traces(line=dict(color=SUCCESS, width=3),
                                  marker=dict(size=7, color=SUCCESS))
            fig_pay.update_yaxes(title_text="VNĐ")
            fig_pay.update_xaxes(tickformat="%d/%m")
            fig_pay.update_layout(height=330, showlegend=False, margin=dict(t=90, b=70))
            st.plotly_chart(fig_pay, use_container_width=True)
        else:
            note("Chưa đọc được các cột LHH LTC, LHH GTC, LHH GTBTT.")

    if col_gan and col_gtc and nv_col_gtc and not G_range.empty:
        section("5. Xếp hạng nhân viên theo %GTC")
        rank = G_range.groupby(nv_col_gtc, as_index=False).agg({col_gan: "sum", col_gtc: "sum"})
        rank["%GTC"] = np.where(rank[col_gan] > 0, rank[col_gtc] / rank[col_gan] * 100, 0.0)
        rank = rank.sort_values("%GTC", ascending=False).reset_index(drop=True)
        medals = ["🥇", "🥈", "🥉"]
        rank.insert(0, "Hạng", [f"{medals[i]} {i+1}" if i < 3 else str(i + 1)
                                for i in range(len(rank))])
        rank["Thưởng (≥80%)"] = np.where(rank["%GTC"] >= 80, "Đạt", "Chưa")
        st.dataframe(rank, use_container_width=True, hide_index=True,
                     column_config={
                         col_gan: st.column_config.NumberColumn("Đơn gán", format="%,d"),
                         col_gtc: st.column_config.NumberColumn("Đơn GTC", format="%,d"),
                         "%GTC": st.column_config.ProgressColumn("%GTC", format="%.2f%%",
                                                                 min_value=0, max_value=100)})
        st.download_button("TẢI CSV XẾP HẠNG", rank.to_csv(index=False).encode("utf-8-sig"),
                           "xep_hang_nhan_vien.csv", "text/csv", key="dl_rank")


# ═══════════════════════════════════════════════════════════════════════
# TAB 5 — TIẾN ĐỘ HOÀN THÀNH KPI
# ═══════════════════════════════════════════════════════════════════════
with tab5:
    q1, q2 = st.columns([1.1, 2])
    with q1:
        bc_kpi = st.selectbox("Bưu cục", ALL_BC, key="bc_kpi")
    with q2:
        # Mặc định: từ ngày đầu tháng hiện tại đến ngày hiện tại (giờ Việt Nam)
        a_kpi, b_kpi = date_range_picker(
            "Khoảng ngày (tháng này)", TODAY_VN.replace(day=1), TODAY_VN, "date_kpi")

    t_gtc = kpi_target([["kpi", "gtc"], ["% gtc"], ["gtc"]], 70.0,
                       exclude=["tts", "tiktok"], bc=bc_kpi)
    t_tts = kpi_target([["gtc tts"], ["tts"], ["tiktok"]], 80.0, bc=bc_kpi)
    t_tra = kpi_target([["tra hang"], ["tra"]], 5.0, bc=bc_kpi)

    if DF_KPI.empty or DF_KPI.select_dtypes("number").notna().sum().sum() == 0:
        st.warning("Sheet KPI chưa có số liệu. Đang dùng mốc tạm — bạn chỉnh ở dưới, "
                   "hoặc điền vào sheet KPI là dashboard tự nhận.", icon="⚠️")

    with st.expander("Chỉnh mốc KPI thủ công"):
        x1, x2, x3 = st.columns(3)
        with x1:
            t_gtc = st.number_input("%GTC tổng tối thiểu", 0.0, 100.0, float(t_gtc), 0.5)
        with x2:
            t_tts = st.number_input("%GTC TTS tối thiểu", 0.0, 100.0, float(t_tts), 0.5)
        with x3:
            t_tra = st.number_input("%Trả hàng tối đa", 0.0, 100.0, float(t_tra), 0.5)

    a_gtc = agg(scope(M_GTC, bc_kpi), a_kpi, b_kpi)
    a_tts = agg(scope(M_TTS, bc_kpi), a_kpi, b_kpi)
    a_tra = agg(scope(M_TRA, bc_kpi), a_kpi, b_kpi)

    section("Đồng hồ đo tiến độ KPI")
    gc1, gc2, gc3 = st.columns(3)
    with gc1:
        gauge_chart("%GTC Tổng", a_gtc, t_gtc, True)
    with gc2:
        gauge_chart("%GTC TikTok Shop", a_tts, t_tts, True)
    with gc3:
        gauge_chart("%Trả hàng (thấp là tốt)", a_tra, t_tra, False)

    section("Đối chiếu chi tiết")
    def kpi_row(name, actual, target, hib):
        ok = actual >= target if hib else actual <= target
        gap = (actual - target) if hib else (target - actual)
        status = ("<span class='up'>ĐẠT</span>" if ok else "<span class='down'>CHƯA ĐẠT</span>")
        return [esc(name), f"{actual:,.2f}%", f"{target:,.2f}%",
                arrow_span(gap, " pp", 2, True), status]

    st.markdown(html_table(
        ["Chỉ tiêu", "Thực tế", "Mục tiêu", "Chênh lệch", "Trạng thái"],
        [kpi_row("%GTC Tổng", a_gtc, t_gtc, True),
         kpi_row("%GTC TikTok Shop", a_tts, t_tts, True),
         kpi_row("%Trả hàng", a_tra, t_tra, False)]), unsafe_allow_html=True)

    section("Bám mốc theo ngày")
    kpi_series = []
    for frame, name, color, tgt in ((M_GTC, "%GTC Tổng", PRIMARY, t_gtc),
                                    (M_TTS, "%GTC TTS", SUCCESS, t_tts),
                                    (M_TRA, "%Trả hàng", DANGER, t_tra)):
        g = daily(sl(scope(frame, bc_kpi), a_kpi, b_kpi))
        if not g.empty:
            kpi_series.append((g, name, color, tgt))
    if kpi_series:
        fig_kpi = go.Figure()
        for g, name, color, tgt in kpi_series:
            fig_kpi.add_trace(go.Scatter(x=g["Ngày"], y=g["Giá Trị"], name=name,
                                         mode="lines+markers",
                                         line=dict(color=color, width=3), marker=dict(size=6)))
            fig_kpi.add_hline(y=tgt, line_dash="dot", line_color=color, line_width=1.5, opacity=0.5)
        fig_kpi.update_yaxes(ticksuffix="%")
        fig_kpi.update_xaxes(tickformat="%d/%m")
        fig_kpi.update_layout(height=470)
        st.plotly_chart(fig_kpi, use_container_width=True)

        tbl_kpi = daily(sl(scope(M_GTC, bc_kpi), a_kpi, b_kpi)).rename(
            columns={"Giá Trị": "%GTC", "Trọng Số": "Sản lượng"})
        for frame, nm in ((M_TTS, "%GTC TTS"), (M_TRA, "%Trả hàng")):
            d = daily(sl(scope(frame, bc_kpi), a_kpi, b_kpi))[["Ngày", "Giá Trị"]].rename(
                columns={"Giá Trị": nm})
            tbl_kpi = tbl_kpi.merge(d, on="Ngày", how="outer")
        tbl_kpi = tbl_kpi.sort_values("Ngày", ascending=False)
        tbl_kpi["Đạt mốc GTC"] = np.where(tbl_kpi["%GTC"] >= t_gtc, "Đạt", "Chưa")
        st.dataframe(tbl_kpi, use_container_width=True, hide_index=True, height=320,
                     column_config={
                         "Ngày": st.column_config.DateColumn(format="DD/MM/YYYY"),
                         "Sản lượng": st.column_config.NumberColumn(format="%,d"),
                         "%GTC": st.column_config.ProgressColumn(format="%.2f%%",
                                                                 min_value=0, max_value=100),
                         "%GTC TTS": st.column_config.NumberColumn(format="%.2f%%"),
                         "%Trả hàng": st.column_config.NumberColumn(format="%.2f%%")})
        st.download_button("TẢI CSV", tbl_kpi.to_csv(index=False).encode("utf-8-sig"),
                           "kpi_theo_ngay.csv", "text/csv", key="dl_kpi")
    else:
        note("Chưa có dữ liệu KPI trong khoảng đã chọn.")


# ═══════════════════════════════════════════════════════════════════════
# TAB 6 — AI CỐ VẤN
# ═══════════════════════════════════════════════════════════════════════
with tab6:
    st.markdown("Hỏi bằng tiếng Việt thường ngày. AI đọc trực tiếp các bảng dữ liệu "
                "đã tải trong phiên làm việc này.")

    z1, z2 = st.columns([2, 1])
    with z1:
        # Mặc định: N-1 theo giờ Việt Nam
        a_ai, b_ai = date_range_picker("Khoảng ngày AI được đọc",
                                       DEFAULT_7D_START, DEFAULT_7D_END, "date_ai")
    with z2:
        bc_ai = st.selectbox("Bưu cục", ALL_BC, key="bc_ai")

    if st.session_state.chat and st.button("XÓA HỘI THOẠI", key="clear_chat"):
        st.session_state.chat = []
        st.rerun()

    for msg in st.session_state.chat:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if not st.session_state.chat:
        note("Ví dụ: bưu cục nào %GTC thấp nhất tuần qua? "
             "Ai giao nhiều đơn nhất? Doanh thu tuần này so với tuần trước ra sao?")

    def build_context(a, b) -> str:
        """Ghép dữ liệu thật từ st.session_state['dataframes'] thành ngữ cảnh cho AI."""
        parts = []
        metric_specs = [
            ("GTC TONG", M_GTC, "wavg"), ("TRA HANG", M_TRA, "wavg"),
            ("GTB THU TIEN", M_GTB, "wavg"), ("GTC TIKTOK", M_TTS, "wavg"),
            ("ODR TIKTOK", M_ODR, "wavg"), ("DOANH THU", M_DT, "sum"),
        ]
        for name, frame, how in metric_specs:
            s = sl(scope(frame, bc_ai), a, b)
            if s.empty:
                continue
            if how == "wavg":
                g = (s.assign(_p=s["Giá Trị"].fillna(0) * s["Trọng Số"])
                      .groupby(["Ngày", "Bưu Cục"], as_index=False)
                      .agg(_p=("_p", "sum"), SanLuong=("Trọng Số", "sum")))
                g[name] = np.where(g["SanLuong"] > 0, g["_p"] / g["SanLuong"], np.nan)
                g = g.drop(columns=["_p"]).round(2)
            else:
                g = (s.groupby(["Ngày", "Bưu Cục"], as_index=False)["Giá Trị"].sum()
                      .rename(columns={"Giá Trị": name}).round(0))
            g["Ngày"] = g["Ngày"].dt.strftime("%d/%m/%Y")
            parts.append(f"\n--- {name} ---\n{g.to_csv(index=False)}")

        for label, df in (("NANG SUAT NHAN VIEN", DF_NSGTC), ("LUONG NHAN VIEN", DF_LUONG)):
            if df is None or df.empty or "Ngày" not in df.columns:
                continue
            s = df[(df["Ngày"] >= a) & (df["Ngày"] <= b)]
            if bc_ai != "Tất cả" and "Bưu Cục" in s.columns:
                s = s[s["Bưu Cục"].map(norm) == norm(bc_ai)]
            if not s.empty:
                keep = [c for c in s.columns if c != "Ngày"][:8]
                o = s[["Ngày"] + keep].copy()
                o["Ngày"] = o["Ngày"].dt.strftime("%d/%m/%Y")
                parts.append(f"\n--- {label} ---\n{o.head(400).to_csv(index=False)}")

        return "".join(parts) or "(Không có dữ liệu trong khoảng thời gian đã chọn.)"

    if question := st.chat_input("Nhập câu hỏi về số liệu..."):
        st.session_state.chat.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            with st.spinner("AI đang đọc dữ liệu..."):
                context = build_context(a_ai, b_ai)
                answer = ask_ai(f"""Bạn là trợ lý phân tích của Trung tâm vận hành GHN.

Dữ liệu thực tế từ {a_ai:%d/%m/%Y} đến {b_ai:%d/%m/%Y}, phạm vi {bc_ai}:
{context}

GHI CHÚ VỀ CHỈ SỐ:
- %GTC là tỷ lệ giao thành công, càng cao càng tốt.
- ODR là cam kết giao đúng hạn với sàn TikTok Shop, càng cao càng tốt, thấp là bị phạt.
- %Trả hàng là đơn quay đầu về kho, càng thấp càng tốt.
- Mọi tỷ lệ đã được tính trung bình có trọng số theo sản lượng.

Câu hỏi của người quản lý: {question}

Trả lời dựa ĐÚNG vào số liệu trên, gọi tên đích danh bưu cục hoặc nhân viên kèm con số cụ thể.
Nếu dữ liệu không đủ để trả lời, nói rõ là không có, tuyệt đối không suy đoán.
Trình bày bằng markdown, in đậm các con số quan trọng.""")
            st.markdown(answer)
            st.session_state.chat.append({"role": "assistant", "content": answer})


st.markdown(
    f"<div style='margin-top:36px;padding-top:16px;border-top:2px solid {LINE};"
    f"text-align:center;color:{MUTED};font-size: 18px;font-weight:600;'>"
    f"TRUNG TÂM VẬN HÀNH CHIẾN LƯỢC — GHN &nbsp;·&nbsp; Designed by AM Phan Van Chanh</div>",
    unsafe_allow_html=True)
