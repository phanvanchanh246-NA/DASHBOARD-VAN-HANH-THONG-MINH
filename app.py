"""
TRUNG TÂM VẬN HÀNH TOÀN CẢNH — GHN
Designed by AM Phan Van Chanh

Chạy local:   streamlit run main.py
Chạy Render:  streamlit run main.py --server.port $PORT --server.address 0.0.0.0

Biến môi trường:
    GEMINI_API_KEY   (bắt buộc nếu muốn dùng AI)
    TELEGRAM_TOKEN, TELEGRAM_CHAT_ID  (tùy chọn — gửi báo cáo)
    APP_USERS        (JSON phân quyền, xem mẫu trong README)
    APP_USER, APP_PASS  (dự phòng khi chưa cấu hình APP_USERS)
    CHAT_LOG_CSV     (tùy chọn — link CSV chứa log tin nhắn nhóm cho AI đọc)
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
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

# =============================================================================
# 1. CẤU HÌNH
# =============================================================================
st.set_page_config(
    page_title="Trung Tâm Vận Hành Toàn Cảnh — GHN",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="expanded",
)

APP_DIR = Path(__file__).resolve().parent
LOGO_PATH = APP_DIR / "assets" / "logo_ghn.png"

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = "gemini-3.6-flash"
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
CHAT_LOG_CSV = os.environ.get("CHAT_LOG_CSV", "").strip()
CACHE_TTL = 300

# --- Bảng màu chủ đạo: xanh da trời, cam, trắng, xanh lá, đỏ -----------------
BLUE = "#0067D6"
BLUE_DARK = "#00408A"
ORANGE = "#F26E21"
GREEN = "#17A55A"
RED = "#E03131"
INK = "#111827"
MUTED = "#6B7280"
LINE = "#E5E7EB"
CANVAS = "#FFFFFF"

# --- Nguồn dữ liệu ------------------------------------------------------------
SHEET_VH = "1lJt4ZXVjIPoUYZF73nsPmVfziJSBXBISUWU1ldSxWH4"
SHEET_KD = "1dEC78RcXYcA7e2SVFmjhOfuP-DY57_FXkOCpRpln4vY"
SHEET_NS = "1OemA7cIZM-5AAvsnQuQphNArKw43de27W75Z-Ri6BcQ"

SOURCES: dict[str, tuple[str, str]] = {
    "gtc_tong":     (SHEET_VH, "1806026577"),
    "sl_gtc_ca":    (SHEET_VH, "2040493559"),
    "tra_hang":     (SHEET_VH, "452321599"),
    "gtb_thu_tien": (SHEET_VH, "454179383"),
    "gtc_tts":      (SHEET_VH, "1164899523"),
    "odr_tts":      (SHEET_VH, "1013193026"),
    "kpi_vh":       (SHEET_VH, "1344197558"),
    "kd_doanh_thu": (SHEET_KD, "339323317"),
    "kd_kh_moi":    (SHEET_KD, "949412123"),
    "kd_pheu":      (SHEET_KD, "151781423"),
    "ns_luong":     (SHEET_NS, "2000227799"),
    "ns_gtc":       (SHEET_NS, "1695228663"),
}

SALARY_PARTS = {
    "LHH LTC": "Lương hoa hồng lấy thành công",
    "LHH GTC": "Lương hoa hồng giao thành công",
    "LHH GTBTT": "Lương hoa hồng giao thất bại thu tiền",
}

PAGES = [
    "🏠 Tổng quan toàn cảnh",
    "🚚 Vận hành",
    "💰 Kinh doanh",
    "👥 Năng suất & Lương",
    "🎯 Tiến độ KPI",
    "🤖 Hỏi đáp AI",
]

ROLE_PAGES = {
    "admin": PAGES,
    "manager": PAGES,
    "staff": ["🏠 Tổng quan toàn cảnh", "🚚 Vận hành", "👥 Năng suất & Lương"],
}

# =============================================================================
# 2. GIAO DIỆN — FONT & CSS
# =============================================================================
pio.templates["ghn"] = go.layout.Template(
    layout=dict(
        font=dict(family="Inter, Segoe UI, sans-serif", size=13, color="#374151"),
        title=dict(font=dict(family="Barlow Condensed, Inter", size=22, color=INK), x=0.01),
        plot_bgcolor=CANVAS,
        paper_bgcolor=CANVAS,
        hovermode="x unified",
        colorway=[BLUE, ORANGE, GREEN, RED, BLUE_DARK, MUTED],
        margin=dict(l=45, r=25, t=70, b=45),
        xaxis=dict(showgrid=False, linecolor=LINE, ticks="outside", tickcolor=LINE),
        yaxis=dict(showgrid=True, gridcolor="#F3F4F6", zerolinecolor=LINE),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
)
pio.templates.default = "ghn"

st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700;800&family=Inter:wght@400;500;600;800&display=swap');

    html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; }}
    h1, h2, h3, .hdr, [data-testid="stMetricLabel"] {{
        font-family: 'Barlow Condensed', 'Inter', sans-serif !important;
        letter-spacing: 0.4px;
    }}

    .cmd-bar {{
        background: linear-gradient(100deg, {BLUE_DARK} 0%, {BLUE} 55%, {ORANGE} 100%);
        border-radius: 14px; padding: 22px 26px; color: #fff;
        border-bottom: 6px solid {GREEN}; margin-bottom: 22px;
        box-shadow: 0 10px 26px rgba(0,64,138,.20);
    }}
    .cmd-bar h1 {{
        font-size: 34px; font-weight: 800; text-transform: uppercase;
        margin: 0 0 4px 0; color: #fff; line-height: 1.05;
    }}
    .cmd-bar p {{ margin: 0; font-size: 15px; font-weight: 500; opacity: .92; }}

    .sec {{
        font-family: 'Barlow Condensed', sans-serif; font-size: 26px; font-weight: 800;
        text-transform: uppercase; color: {BLUE_DARK}; letter-spacing: .6px;
        border-left: 8px solid {ORANGE}; padding: 8px 0 8px 14px;
        margin: 26px 0 14px 0;
    }}

    .pill {{
        display:inline-block; padding: 4px 12px; border-radius: 999px;
        font-size: 12px; font-weight: 800; text-transform: uppercase; letter-spacing:.5px;
    }}
    .pill-ok  {{ background:#E7F7EE; color:{GREEN}; border:1px solid #B7E7CC; }}
    .pill-bad {{ background:#FDECEC; color:{RED};   border:1px solid #F5C2C2; }}
    .pill-mid {{ background:#FFF2E6; color:{ORANGE};border:1px solid #FBD9BC; }}

    .note {{
        background:#fff; border-left: 6px solid {ORANGE}; border-radius: 10px;
        padding: 16px 18px; margin-bottom: 16px; line-height: 1.65; color:#333;
        box-shadow: 0 2px 10px rgba(0,0,0,.05);
    }}

    [data-testid="stMetricValue"] {{ font-weight: 800 !important; color: {BLUE} !important; font-size: 1.85rem !important; }}
    [data-testid="stMetricLabel"] {{ font-weight: 700 !important; font-size: 1rem !important; color: {MUTED} !important; text-transform: uppercase; }}

    section[data-testid="stSidebar"] {{ background: #FAFBFC; border-right: 1px solid {LINE}; }}
    div[data-testid="stDataFrame"] {{ border: 1px solid {LINE}; border-radius: 10px; }}
    </style>
    """,
    unsafe_allow_html=True,
)


def show_logo(width: int = 210):
    """Hiển thị logo GHN nguyên bản, không chỉnh sửa."""
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), width=width)
    else:
        st.markdown(
            f"<div style='font-family:Barlow Condensed;font-size:26px;font-weight:800;color:{ORANGE};'>"
            f"GIAO HÀNG NHANH</div>"
            "<div style='font-size:12px;color:#888;'>Đặt file logo tại assets/logo_ghn.png</div>",
            unsafe_allow_html=True,
        )


def sec(text: str):
    st.markdown(f"<div class='sec'>{text}</div>", unsafe_allow_html=True)


# =============================================================================
# 3. PHIÊN LÀM VIỆC
# =============================================================================
_DEFAULTS = {
    "auth": None,
    "ai_cache": {},
    "chat_history": [],
    "kpi_manual": {},
}
for _k, _v in _DEFAULTS.items():
    st.session_state.setdefault(_k, _v)


def load_users() -> dict:
    raw = os.environ.get("APP_USERS", "").strip()
    if raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            st.sidebar.error("APP_USERS không phải JSON hợp lệ.")
    u, p = os.environ.get("APP_USER", "").strip(), os.environ.get("APP_PASS", "").strip()
    if u and p:
        return {u: {"password": p, "role": "admin", "ten": "Quản trị viên", "buu_cuc": ["Tất cả"]}}
    return {}


USERS = load_users()


def login_screen():
    left, mid, right = st.columns([1, 1.25, 1])
    with mid:
        st.write("")
        show_logo(260)
        st.markdown(
            f"<h2 style='font-family:Barlow Condensed;font-weight:800;color:{BLUE_DARK};"
            "text-transform:uppercase;margin-top:10px;'>Trung tâm vận hành toàn cảnh</h2>",
            unsafe_allow_html=True,
        )
        if not USERS:
            st.error("Chưa cấu hình tài khoản. Đặt biến môi trường APP_USERS (hoặc APP_USER/APP_PASS) rồi khởi động lại.")
            return
        with st.form("login"):
            uid = st.text_input("ID nhân viên")
            pwd = st.text_input("Mật khẩu", type="password")
            if st.form_submit_button("ĐĂNG NHẬP", use_container_width=True, type="primary"):
                info = USERS.get(uid.strip())
                if info and str(info.get("password")) == pwd:
                    st.session_state.auth = {
                        "id": uid.strip(),
                        "ten": info.get("ten", uid.strip()),
                        "role": info.get("role", "staff"),
                        "buu_cuc": info.get("buu_cuc", ["Tất cả"]),
                    }
                    st.rerun()
                else:
                    st.error("ID hoặc mật khẩu không đúng.")
        st.caption("Tài khoản do quản trị viên khu vực cấp. Mỗi tài khoản chỉ thấy dữ liệu bưu cục được phân quyền.")


if st.session_state.auth is None:
    login_screen()
    st.stop()

AUTH = st.session_state.auth
ALLOWED_BC = AUTH.get("buu_cuc", ["Tất cả"])
IS_ALL_BC = "Tất cả" in ALLOWED_BC


# =============================================================================
# 4. ĐỌC & CHUẨN HÓA DỮ LIỆU
# =============================================================================
def strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFD", str(text))
    return "".join(ch for ch in nfkd if unicodedata.category(ch) != "Mn").replace("đ", "d").replace("Đ", "D")


def norm(text: str) -> str:
    s = strip_accents(text).lower().replace("\xa0", " ")
    s = re.sub(r"[^a-z0-9% ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def parse_vn_num(val):
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


def pick_col(df: pd.DataFrame, contains, exclude=()) -> str | None:
    """Dò cột theo từ khóa đã bỏ dấu. contains = list các nhóm từ khóa, ưu tiên nhóm đầu."""
    if df is None or df.empty:
        return None
    cols = {c: norm(c) for c in df.columns}
    for group in contains:
        keys = [norm(k) for k in ([group] if isinstance(group, str) else group)]
        for col, nc in cols.items():
            if all(k in nc for k in keys) and not any(norm(e) in nc for e in exclude):
                return col
    return None


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def load_sheet(key: str) -> pd.DataFrame:
    sid, gid = SOURCES[key]
    url = f"https://docs.google.com/spreadsheets/d/{sid}/export?format=csv&gid={gid}"
    df = pd.read_csv(url)
    df.columns = df.columns.astype(str).str.strip().str.replace("\xa0", " ", regex=False)
    df = df.loc[:, ~df.columns.str.match(r"^Unnamed")]
    return df


def safe_load(key: str) -> pd.DataFrame:
    try:
        return load_sheet(key)
    except Exception as exc:  # noqa: BLE001
        st.session_state.setdefault("load_errors", {})[key] = str(exc)
        return pd.DataFrame()


DATE_KEYS = [["ngay"], ["thoi gian"], ["date"]]
BC_KEYS = [["buu cuc"], ["buu"], ["khu vuc"], ["tram"], ["station"]]
VOL_KEYS = [["san luong"], ["volume"], ["tong don"], ["so don"], ["don"]]


def base_frame(key: str) -> pd.DataFrame:
    """Chuẩn hóa mọi sheet về khung chung: Ngày + Bưu Cục + các cột số."""
    raw = safe_load(key)
    if raw.empty:
        return pd.DataFrame(columns=["Ngày", "Bưu Cục"])
    df = raw.copy()
    dcol = pick_col(df, DATE_KEYS)
    bcol = pick_col(df, BC_KEYS)
    df["Ngày"] = pd.to_datetime(df[dcol], errors="coerce", dayfirst=True) if dcol else pd.NaT
    df["Bưu Cục"] = df[bcol].astype(str).str.strip() if bcol else "Chưa phân loại"
    skip = {dcol, bcol, "Ngày", "Bưu Cục"}
    for col in df.columns:
        if col in skip or df[col].dtype.kind in "if":
            continue
        if col in (pick_col(df, [["loai hang"]]), pick_col(df, [["ca"]]), pick_col(df, [["nhan vien"]]),
                   pick_col(df, [["trang thai"]]), pick_col(df, [["ten"]]), pick_col(df, [["ma"]])):
            df[col] = df[col].astype(str).str.strip()
            continue
        df[col] = df[col].apply(parse_vn_num)
    return df


def rescale_pct(series: pd.Series) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce")
    valid = s[s > 0].dropna()
    return s * 100 if (not valid.empty and valid.max() <= 1.2) else s


def metric_frame(key: str, value_keys, weight_keys=VOL_KEYS, is_pct=True, extra_dim=None) -> pd.DataFrame:
    """Trả về khung [Ngày, Bưu Cục, (Chiều phụ), Giá Trị, Trọng Số]."""
    df = base_frame(key)
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


def wavg(values, weights) -> float:
    v = pd.to_numeric(values, errors="coerce")
    w = pd.to_numeric(weights, errors="coerce").fillna(0)
    m = v.notna() & (w > 0)
    if w[m].sum() > 0:
        return float((v[m] * w[m]).sum() / w[m].sum())
    return float(v.mean()) if v.notna().any() else 0.0


def month_end(ts: pd.Timestamp) -> pd.Timestamp:
    nxt = ts.replace(day=28) + timedelta(days=4)
    return nxt - timedelta(days=nxt.day)


def period_pair(ref: pd.Timestamp, mode: str):
    """Trả về ((đầu kỳ này, cuối kỳ này), (đầu kỳ trước, cuối kỳ trước))."""
    if mode == "Ngày":
        return (ref, ref), (ref - timedelta(days=1), ref - timedelta(days=1))
    if mode == "Tuần":
        a = ref - timedelta(days=ref.weekday())
        return (a, a + timedelta(days=6)), (a - timedelta(days=7), a - timedelta(days=1))
    a = ref.replace(day=1)
    pa = (a - timedelta(days=1)).replace(day=1)
    return (a, month_end(a)), (pa, a - timedelta(days=1))


def slice_df(df: pd.DataFrame, a, b) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=df.columns if df is not None else [])
    return df[(df["Ngày"] >= a) & (df["Ngày"] <= b)]


def value_of(df: pd.DataFrame, a, b, how: str = "wavg") -> float:
    sub = slice_df(df, a, b)
    if sub.empty:
        return 0.0
    return wavg(sub["Giá Trị"], sub["Trọng Số"]) if how == "wavg" else float(sub["Giá Trị"].sum())


def filter_scope(df: pd.DataFrame, bc: str) -> pd.DataFrame:
    """Áp bộ lọc bưu cục + giới hạn phân quyền."""
    if df is None or df.empty or "Bưu Cục" not in df.columns:
        return df if df is not None else pd.DataFrame()
    out = df
    if not IS_ALL_BC:
        allow = [norm(x) for x in ALLOWED_BC]
        out = out[out["Bưu Cục"].map(lambda x: norm(x) in allow)]
    if bc and bc != "Tất cả":
        out = out[out["Bưu Cục"].map(norm) == norm(bc)]
    return out


def bc_options(*frames) -> list[str]:
    vals: set[str] = set()
    for f in frames:
        if f is not None and not f.empty and "Bưu Cục" in f.columns:
            vals |= set(f["Bưu Cục"].dropna().astype(str).str.strip())
    vals = {v for v in vals if v and v.lower() not in ("nan", "chưa phân loại")}
    if not IS_ALL_BC:
        allow = [norm(x) for x in ALLOWED_BC]
        vals = {v for v in vals if norm(v) in allow}
    return ["Tất cả"] + sorted(vals)


# =============================================================================
# 5. THÀNH PHẦN HIỂN THỊ
# =============================================================================
def quick_range(df_for_bounds: pd.DataFrame, key: str):
    """Bộ lọc ngày kèm nút chọn nhanh Ngày / Tuần / Tháng."""
    today = pd.Timestamp.today().normalize()
    if df_for_bounds is not None and not df_for_bounds.empty and df_for_bounds["Ngày"].notna().any():
        hi = df_for_bounds["Ngày"].max()
        lo = df_for_bounds["Ngày"].min()
    else:
        hi, lo = today, today - timedelta(days=30)

    c1, c2 = st.columns([1.4, 2])
    with c1:
        quick = st.radio("Chọn nhanh", ["Ngày", "Tuần", "Tháng", "Tùy chọn"],
                         horizontal=True, key=f"quick_{key}")
    if quick == "Ngày":
        start = end = hi
    elif quick == "Tuần":
        start, end = hi - timedelta(days=hi.weekday()), hi
    elif quick == "Tháng":
        start, end = hi.replace(day=1), hi
    else:
        start, end = lo, hi
    with c2:
        picked = st.date_input("Khoảng thời gian", [start, end],
                               min_value=lo, max_value=hi, key=f"date_{key}")
    if isinstance(picked, (list, tuple)) and len(picked) >= 2:
        start, end = pd.to_datetime(picked[0]), pd.to_datetime(picked[1])
    elif isinstance(picked, (list, tuple)) and len(picked) == 1:
        start = end = pd.to_datetime(picked[0])
    return start, end, hi


def trend_row(label: str, df: pd.DataFrame, ref: pd.Timestamp, how="wavg",
              unit="%", decimals=2, higher_is_better=True):
    """3 ô so sánh: Ngày/N-1, Tuần/W-1, Tháng/M-1."""
    cols = st.columns(3)
    for col, mode in zip(cols, ["Ngày", "Tuần", "Tháng"]):
        (a, b), (pa, pb) = period_pair(ref, mode)
        now, prev = value_of(df, a, b, how), value_of(df, pa, pb, how)
        diff = now - prev
        if unit == "%":
            val_txt, dlt_txt = f"{now:,.{decimals}f}%", f"{diff:+,.{decimals}f} pp"
        elif unit == "đ":
            val_txt, dlt_txt = f"{now:,.0f} đ", f"{diff:+,.0f} đ"
        else:
            val_txt, dlt_txt = f"{now:,.0f}", f"{diff:+,.0f}"
        col.metric(f"{label} · {mode}", val_txt, dlt_txt,
                   delta_color="normal" if higher_is_better else "inverse")


def line_chart(df: pd.DataFrame, title: str, color=BLUE, unit="%", how="wavg"):
    if df is None or df.empty:
        st.info(f"Chưa có dữ liệu cho: {title}")
        return
    if how == "wavg":
        g = (df.assign(_p=df["Giá Trị"].fillna(0) * df["Trọng Số"])
               .groupby("Ngày", as_index=False)
               .agg(_p=("_p", "sum"), _w=("Trọng Số", "sum")))
        g["Giá Trị"] = np.where(g["_w"] > 0, g["_p"] / g["_w"], np.nan)
    else:
        g = df.groupby("Ngày", as_index=False)["Giá Trị"].sum()
    fig = px.line(g.sort_values("Ngày"), x="Ngày", y="Giá Trị", markers=True, title=title)
    fig.update_traces(line=dict(color=color, width=4),
                      marker=dict(size=9, color=color, line=dict(width=2, color="#fff")))
    fig.update_yaxes(title_text="%" if unit == "%" else unit, ticksuffix="%" if unit == "%" else None)
    st.plotly_chart(fig, use_container_width=True)


def combo_chart(df: pd.DataFrame, title: str, bar_name="Sản lượng", line_name="% GTC"):
    if df is None or df.empty:
        st.info(f"Chưa có dữ liệu cho: {title}")
        return
    g = (df.assign(_p=df["Giá Trị"].fillna(0) * df["Trọng Số"])
           .groupby("Ngày", as_index=False)
           .agg(_p=("_p", "sum"), _w=("Trọng Số", "sum")))
    g["Tỷ lệ"] = np.where(g["_w"] > 0, g["_p"] / g["_w"], np.nan)
    g = g.sort_values("Ngày")
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=g["Ngày"], y=g["_w"], name=bar_name, marker_color=BLUE, opacity=.85),
                  secondary_y=False)
    fig.add_trace(go.Scatter(x=g["Ngày"], y=g["Tỷ lệ"], name=line_name, mode="lines+markers",
                             line=dict(color=ORANGE, width=4),
                             marker=dict(size=9, line=dict(width=2, color="#fff"))),
                  secondary_y=True)
    fig.update_layout(title=title)
    fig.update_yaxes(title_text=bar_name, secondary_y=False)
    fig.update_yaxes(title_text=line_name, secondary_y=True, showgrid=False, range=[0, 100], ticksuffix="%")
    st.plotly_chart(fig, use_container_width=True)


def status_pill(value: float, target: float, higher_is_better=True) -> str:
    ok = value >= target if higher_is_better else value <= target
    near = abs(value - target) / target <= 0.05 if target else False
    if ok:
        return "<span class='pill pill-ok'>Đạt</span>"
    return "<span class='pill pill-mid'>Sát mốc</span>" if near else "<span class='pill pill-bad'>Chưa đạt</span>"


# =============================================================================
# 6. AI & TELEGRAM
# =============================================================================
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
        return "⚠️ Thiếu thư viện. Chạy: `pip install google-genai`"
    client = genai_client()
    if client is None:
        return "⚠️ Chưa cấu hình GEMINI_API_KEY trên máy chủ."
    try:
        resp = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=genai_types.GenerateContentConfig(max_output_tokens=8192),
        )
        if not getattr(resp, "candidates", None):
            return "⚠️ AI không trả về nội dung. Thử rút gọn câu hỏi."
        return (resp.text or "").strip() or "⚠️ AI trả về nội dung rỗng."
    except Exception as exc:  # noqa: BLE001
        return f"❌ Lỗi Google AI: {exc}"


def send_telegram(text: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return False, "Chưa cấu hình TELEGRAM_TOKEN / TELEGRAM_CHAT_ID."
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    chunks = [text[i:i + 3800] for i in range(0, len(text), 3800)] or [""]
    for i, chunk in enumerate(chunks):
        head = "" if i == 0 else f"(phần {i + 1}/{len(chunks)})\n"
        try:
            r = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": head + chunk}, timeout=20)
        except requests.RequestException as exc:
            return False, f"Lỗi mạng: {exc}"
        if r.status_code != 200:
            return False, f"Telegram trả về {r.status_code}."
    return True, f"Đã gửi {len(chunks)} tin nhắn."


def ai_block(cache_key: str, button_label: str, prompt_builder, tab_name: str):
    """Nút gọi AI + hiển thị + nút gửi Telegram."""
    col_a, col_b = st.columns([1.2, 3])
    with col_a:
        role = st.selectbox("Góc nhìn báo cáo", ["Giám đốc", "Quản lý khu vực (AM)", "Nhân viên"],
                            key=f"role_{cache_key}")
    with col_b:
        st.write("")
        if st.button(button_label, type="primary", key=f"btn_{cache_key}", use_container_width=True):
            with st.spinner("AI đang phân tích..."):
                st.session_state.ai_cache[cache_key] = ask_ai(prompt_builder(role))
    result = st.session_state.ai_cache.get(cache_key, "Bấm nút phía trên để AI phân tích số liệu đang hiển thị.")
    st.markdown(f"<div class='note'><b>🤖 Cố vấn AI — {tab_name}</b><br><br>{result}</div>", unsafe_allow_html=True)
    if st.button(f"📤 Gửi báo cáo {tab_name} lên Telegram", key=f"tele_{cache_key}"):
        ok, msg = send_telegram(f"🚨 {tab_name.upper()} 🚨\n\n" + result.replace("*", ""))
        (st.success if ok else st.error)(msg)


ROLE_STYLE = {
    "Giám đốc": "Đóng vai Giám đốc: đánh giá vĩ mô, nêu rủi ro hệ thống, đề xuất chiến lược. Giọng chuyên nghiệp, quyết đoán.",
    "Quản lý khu vực (AM)": "Đóng vai Quản lý khu vực: chỉ ra điểm nóng, giao việc cụ thể cho bưu cục và nhân viên. Giọng dứt khoát, thực chiến.",
    "Nhân viên": 'Đóng vai trợ lý điều phối nhắn cho anh em nhân viên. Xưng "Mình" với "Anh em", ngắn gọn, tạo động lực.',
}
CLOSING = "Viết súc tích, chia ý rõ ràng, không bỏ dở câu. Kết thúc bằng dòng [HOÀN TẤT BÁO CÁO]."


# =============================================================================
# 7. NẠP DỮ LIỆU
# =============================================================================
with st.spinner("Đang đồng bộ dữ liệu từ Google Sheets..."):
    M_GTC = metric_frame("gtc_tong", [["% gtc"], ["gtc"], ["giao thanh cong"]])
    M_TRA = metric_frame("tra_hang", [["tra hang"], ["tra"]])
    M_GTB = metric_frame("gtb_thu_tien", [["gtb"], ["thu tien"]])
    M_TTS = metric_frame("gtc_tts", [["gtc tts"], ["% gtc"], ["gtc"]])
    M_ODR = metric_frame("odr_tts", [["odr"], ["ontime"], ["dung han"]])
    M_CA = metric_frame("sl_gtc_ca", [["% gtc"], ["gtc"]], extra_dim=[["ca"], ["loai hang"]])
    M_DT = metric_frame("kd_doanh_thu", [["doanh thu"]], weight_keys=None, is_pct=False)
    DF_KPI = base_frame("kpi_vh")
    DF_KH_MOI = base_frame("kd_kh_moi")
    DF_PHEU = base_frame("kd_pheu")
    DF_LUONG = base_frame("ns_luong")
    DF_NSGTC = base_frame("ns_gtc")

ALL_BC = bc_options(M_GTC, M_DT, DF_LUONG, DF_NSGTC)
REF_DATE = max([f["Ngày"].max() for f in (M_GTC, M_DT, DF_NSGTC)
                if f is not None and not f.empty and f["Ngày"].notna().any()] or [pd.Timestamp.today().normalize()])

# =============================================================================
# 8. THANH BÊN
# =============================================================================
with st.sidebar:
    show_logo(200)
    st.markdown(
        f"<div style='font-family:Barlow Condensed;font-size:19px;font-weight:800;color:{BLUE_DARK};"
        f"text-transform:uppercase;margin:6px 0 2px;'>Trung tâm vận hành</div>"
        f"<div style='font-size:13px;color:{MUTED};'>👤 {AUTH['ten']} · {AUTH['role'].upper()}</div>"
        f"<div style='font-size:13px;color:{MUTED};'>🏢 {', '.join(ALLOWED_BC)}</div>",
        unsafe_allow_html=True,
    )
    st.divider()
    allowed_pages = ROLE_PAGES.get(AUTH["role"], ROLE_PAGES["staff"])
    page = st.radio("Điều hướng", allowed_pages, label_visibility="collapsed")
    st.divider()
    if st.button("🔄 Làm mới dữ liệu", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    if st.button("🚪 Đăng xuất", use_container_width=True):
        st.session_state.auth = None
        st.rerun()
    st.caption(f"Số liệu mới nhất: {REF_DATE:%d/%m/%Y}")
    errs = st.session_state.get("load_errors", {})
    if errs:
        st.warning(f"{len(errs)} nguồn dữ liệu chưa đọc được: {', '.join(errs)}")

st.markdown(
    f"""
    <div class="cmd-bar">
        <h1>Trung tâm vận hành toàn cảnh</h1>
        <p>Hiệu suất thực · Quyết định nhanh · AI cố vấn — Designed by AM Phan Van Chanh</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# =============================================================================
# 9. TRANG 1 — TỔNG QUAN
# =============================================================================
if page == PAGES[0]:
    bc = st.selectbox("Bưu cục", ALL_BC, key="bc_home")
    g_gtc, g_tra, g_tts, g_odr, g_gtb = (filter_scope(x, bc) for x in (M_GTC, M_TRA, M_TTS, M_ODR, M_GTB))
    g_dt = filter_scope(M_DT, bc)

    (d_a, d_b), (d_pa, d_pb) = period_pair(REF_DATE, "Ngày")
    (m_a, m_b), _ = period_pair(REF_DATE, "Tháng")

    sec("Chỉ số nóng hôm nay")
    k = st.columns(5)
    snapshot = [
        ("%GTC tổng", value_of(g_gtc, d_a, d_b), value_of(g_gtc, d_pa, d_pb), "%", True),
        ("%GTC TikTok", value_of(g_tts, d_a, d_b), value_of(g_tts, d_pa, d_pb), "%", True),
        ("ODR TikTok", value_of(g_odr, d_a, d_b), value_of(g_odr, d_pa, d_pb), "%", True),
        ("Tỷ lệ trả hàng", value_of(g_tra, d_a, d_b), value_of(g_tra, d_pa, d_pb), "%", False),
        ("Doanh thu tháng", value_of(g_dt, m_a, m_b, "sum"), 0.0, "đ", True),
    ]
    for col, (name, now, prev, unit, hib) in zip(k, snapshot):
        if unit == "%":
            col.metric(name, f"{now:.2f}%", f"{now - prev:+.2f} pp",
                       delta_color="normal" if hib else "inverse")
        else:
            col.metric(name, f"{now:,.0f} đ")

    sec("Vận hành — nhịp ngày / tuần / tháng")
    trend_row("%GTC tổng", g_gtc, REF_DATE)
    st.write("")
    trend_row("Tỷ lệ trả hàng", g_tra, REF_DATE, higher_is_better=False)

    sec("Kinh doanh")
    trend_row("Doanh thu", g_dt, REF_DATE, how="sum", unit="đ")

    sec("Tác phong & kỷ luật")
    st.info(
        "Mục này cần một sheet nguồn về chấm công, đi muộn, vi phạm đồng phục hoặc quy trình. "
        "Bạn gửi link sheet, mình nối vào đúng chỗ này."
    )

    sec("AI đọc tin nhắn nhóm")
    if CHAT_LOG_CSV:
        try:
            df_chat = pd.read_csv(CHAT_LOG_CSV).tail(300)
            st.caption(f"Đã nạp {len(df_chat)} tin nhắn gần nhất.")
        except Exception as exc:  # noqa: BLE001
            df_chat = pd.DataFrame()
            st.warning(f"Không đọc được CHAT_LOG_CSV: {exc}")
    else:
        df_chat = pd.DataFrame()
        st.info(
            "Chưa cấu hình nguồn tin nhắn. Đặt biến môi trường CHAT_LOG_CSV trỏ tới một Google Sheet "
            "chứa các cột: Ngày, Nhóm, Người gửi, Nội dung. Sau đó AI sẽ tóm tắt chủ đề nóng "
            "(lương, thu nhập, quy trình, khiếu nại) ngay tại đây."
        )

    def prompt_home(role: str) -> str:
        chat_ctx = df_chat.to_csv(index=False)[:6000] if not df_chat.empty else "(chưa có dữ liệu tin nhắn)"
        return f"""Bạn là trợ lý điều hành trung tâm vận hành GHN. Ngày dữ liệu: {REF_DATE:%d/%m/%Y}. Bưu cục: {bc}.

CHỈ SỐ HÔM NAY:
- %GTC tổng: {value_of(g_gtc, d_a, d_b):.2f}% (hôm trước {value_of(g_gtc, d_pa, d_pb):.2f}%)
- %GTC TikTok: {value_of(g_tts, d_a, d_b):.2f}% | ODR TikTok: {value_of(g_odr, d_a, d_b):.2f}%
- Tỷ lệ trả hàng: {value_of(g_tra, d_a, d_b):.2f}% (thấp là tốt)
- Tỷ lệ GTB thu tiền: {value_of(g_gtb, d_a, d_b):.2f}%
- Doanh thu tháng này: {value_of(g_dt, m_a, m_b, 'sum'):,.0f} đ

TIN NHẮN NHÓM GẦN ĐÂY (nếu có):
{chat_ctx}

{ROLE_STYLE[role]}
Trình bày đúng 3 phần: 1) ĐẠT — điều gì đang tốt, 2) CHƯA ĐẠT — điều gì đang báo động và vì sao,
3) CẦN LÀM NGAY — tối đa 4 việc cụ thể, có người chịu trách nhiệm.
Nếu phần tin nhắn có dữ liệu, thêm mục 4) TÂM LÝ ĐỘI NGŨ nêu chủ đề anh em đang bàn (lương, thu nhập, quy trình) và mức độ cần lưu ý.
{CLOSING}"""

    sec("Cố vấn AI toàn cảnh")
    ai_block("home", "🔍 AI tổng hợp tình hình", prompt_home, "Tổng Quan")

# =============================================================================
# 10. TRANG 2 — VẬN HÀNH
# =============================================================================
elif page == PAGES[1]:
    sec("Bộ lọc vận hành")
    start, end, _ = quick_range(M_GTC, "vh")
    f1, f2 = st.columns(2)
    with f1:
        bc = st.selectbox("Bưu cục", ALL_BC, key="bc_vh")
    with f2:
        lh_vals = sorted({x for x in M_CA.get("Chiều", pd.Series(dtype=str)).dropna().unique() if str(x) != "nan"}) \
            if "Chiều" in M_CA.columns else []
        lh = st.multiselect("Loại hàng / Ca", lh_vals, default=lh_vals, key="lh_vh")

    def scoped(df):
        return slice_df(filter_scope(df, bc), start, end)

    s_gtc, s_tra, s_gtb, s_tts, s_odr = (scoped(x) for x in (M_GTC, M_TRA, M_GTB, M_TTS, M_ODR))
    s_ca = scoped(M_CA)
    if lh and "Chiều" in s_ca.columns:
        s_ca = s_ca[s_ca["Chiều"].isin(lh)]

    st.caption(f"Đang xem {start:%d/%m/%Y} – {end:%d/%m/%Y} · {bc}. "
               "Các tỷ lệ % tính trung bình có trọng số theo sản lượng.")

    sec("1. Báo cáo GTC tổng")
    trend_row("%GTC", filter_scope(M_GTC, bc), REF_DATE)
    combo_chart(s_gtc, "Sản lượng và %GTC tổng", bar_name="Sản lượng", line_name="% GTC")

    sec("2. Sản lượng & %GTC theo ca")
    if not s_ca.empty and "Chiều" in s_ca.columns:
        g = (s_ca.assign(_p=s_ca["Giá Trị"].fillna(0) * s_ca["Trọng Số"])
                  .groupby(["Ngày", "Chiều"], as_index=False)
                  .agg(_p=("_p", "sum"), _w=("Trọng Số", "sum")))
        g["Tỷ lệ"] = np.where(g["_w"] > 0, g["_p"] / g["_w"], np.nan)
        g["Trục"] = g["Ngày"].dt.strftime("%d/%m") + " · " + g["Chiều"]
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        palette_bar = [BLUE, BLUE_DARK, MUTED]
        palette_line = [ORANGE, RED, GREEN]
        for i, name in enumerate(g["Chiều"].unique()):
            sub = g[g["Chiều"] == name]
            fig.add_trace(go.Bar(x=sub["Trục"], y=sub["_w"], name=f"SL {name}",
                                 marker_color=palette_bar[i % 3], opacity=.85), secondary_y=False)
            fig.add_trace(go.Scatter(x=sub["Trục"], y=sub["Tỷ lệ"], name=f"%GTC {name}", mode="lines+markers",
                                     line=dict(color=palette_line[i % 3], width=3),
                                     marker=dict(size=8)), secondary_y=True)
        fig.update_layout(title="Sản lượng và %GTC theo ca làm việc", barmode="group")
        fig.update_yaxes(title_text="Sản lượng", secondary_y=False)
        fig.update_yaxes(title_text="% GTC", secondary_y=True, range=[0, 100], showgrid=False, ticksuffix="%")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Chưa đọc được dữ liệu theo ca. Kiểm tra sheet 'Sản lượng, %GTC theo ca'.")

    sec("3. Tỷ lệ trả hàng")
    trend_row("Trả hàng", filter_scope(M_TRA, bc), REF_DATE, higher_is_better=False)
    line_chart(s_tra, "Tỷ lệ trả hàng theo ngày", color=RED)

    sec("4. Tỷ lệ GTB — thu tiền")
    trend_row("GTB thu tiền", filter_scope(M_GTB, bc), REF_DATE)
    line_chart(s_gtb, "Tỷ lệ GTB thu tiền theo ngày", color=GREEN)

    sec("5. GTC TikTok Shop")
    trend_row("%GTC TTS", filter_scope(M_TTS, bc), REF_DATE)
    combo_chart(s_tts, "Sản lượng và %GTC TikTok Shop", bar_name="Sản lượng TTS", line_name="% GTC TTS")

    sec("6. ODR TikTok Shop")
    trend_row("ODR TTS", filter_scope(M_ODR, bc), REF_DATE)
    line_chart(s_odr, "Tỷ lệ ontime giao TikTok Shop (ODR)", color=BLUE)

    def prompt_vh(role: str) -> str:
        return f"""Dữ liệu vận hành GHN, {start:%d/%m/%Y} – {end:%d/%m/%Y}, bưu cục: {bc}.
- %GTC tổng: {wavg(s_gtc['Giá Trị'], s_gtc['Trọng Số']) if not s_gtc.empty else 0:.2f}%
- Tỷ lệ trả hàng: {wavg(s_tra['Giá Trị'], s_tra['Trọng Số']) if not s_tra.empty else 0:.2f}% (thấp là tốt)
- Tỷ lệ GTB thu tiền: {wavg(s_gtb['Giá Trị'], s_gtb['Trọng Số']) if not s_gtb.empty else 0:.2f}%
- %GTC TikTok: {wavg(s_tts['Giá Trị'], s_tts['Trọng Số']) if not s_tts.empty else 0:.2f}%
- ODR TikTok: {wavg(s_odr['Giá Trị'], s_odr['Trọng Số']) if not s_odr.empty else 0:.2f}% (cam kết đúng hạn với sàn, càng cao càng tốt, thấp là bị phạt)
- Tổng sản lượng: {s_gtc['Trọng Số'].sum() if not s_gtc.empty else 0:,.0f} đơn

{ROLE_STYLE[role]}
Chia 3 phần: 1) Đánh giá hiệu suất, 2) Điểm nóng và rủi ro, 3) Việc cần làm ngay.
{CLOSING}"""

    sec("Cố vấn AI vận hành")
    ai_block("vh", "🔍 AI phân tích vận hành", prompt_vh, "Vận Hành")

# =============================================================================
# 11. TRANG 3 — KINH DOANH
# =============================================================================
elif page == PAGES[2]:
    sec("Bộ lọc kinh doanh")
    start, end, _ = quick_range(M_DT, "kd")
    bc = st.selectbox("Bưu cục", ALL_BC, key="bc_kd")

    dt_bc = filter_scope(M_DT, bc)
    dt_range = slice_df(dt_bc, start, end)

    sec("1. Doanh thu — nhịp ngày / tuần / tháng")
    trend_row("Doanh thu", dt_bc, REF_DATE, how="sum", unit="đ")

    sec("2. Tiến độ doanh thu tháng so với KPI")
    kpi_key = f"kpi_dt_{bc}"
    st.session_state.kpi_manual.setdefault(kpi_key, 71_000_000.0)
    c1, c2 = st.columns([1, 2])
    with c1:
        st.session_state.kpi_manual[kpi_key] = st.number_input(
            f"KPI doanh thu tháng — {bc} (VNĐ)", min_value=0.0,
            value=float(st.session_state.kpi_manual[kpi_key]), step=1_000_000.0,
        )
    kpi_dt = float(st.session_state.kpi_manual[kpi_key])
    (m_a, m_b), _ = period_pair(REF_DATE, "Tháng")
    rev_month = value_of(dt_bc, m_a, m_b, "sum")
    days_done = max((REF_DATE - m_a).days + 1, 1)
    days_total = month_end(m_a).day
    forecast = rev_month / days_done * days_total
    with c2:
        m1, m2, m3 = st.columns(3)
        m1.metric("Doanh thu tháng này", f"{rev_month:,.0f} đ",
                  f"{rev_month / kpi_dt * 100:.1f}% KPI" if kpi_dt else "chưa đặt KPI")
        m2.metric("Dự kiến hết tháng", f"{forecast:,.0f} đ", "theo tốc độ hiện tại", delta_color="off")
        m3.metric("Còn thiếu so với KPI", f"{max(kpi_dt - forecast, 0):,.0f} đ")

    gauge = go.Figure(go.Indicator(
        mode="gauge+number",
        value=forecast,
        number={"valueformat": ",.0f", "suffix": " đ"},
        title={"text": "Dự phóng doanh thu tháng so với KPI"},
        gauge={
            "axis": {"range": [0, max(kpi_dt * 1.3, forecast * 1.1, 1)]},
            "bar": {"color": BLUE, "thickness": .3},
            "steps": [
                {"range": [0, kpi_dt * .8], "color": "#FDECEC"},
                {"range": [kpi_dt * .8, kpi_dt], "color": "#FFF2E6"},
                {"range": [kpi_dt, max(kpi_dt * 1.3, forecast * 1.1, 1)], "color": "#E7F7EE"},
            ],
            "threshold": {"line": {"color": RED, "width": 4}, "thickness": .85, "value": kpi_dt},
        },
    ))
    gauge.update_layout(height=280, margin=dict(l=20, r=20, t=60, b=10))
    st.plotly_chart(gauge, use_container_width=True)

    sec("3. Biểu đồ doanh thu")
    view = st.radio("Xem theo", ["Ngày", "Tuần", "Tháng"], horizontal=True, key="view_kd")
    if not dt_range.empty:
        plot = dt_range.copy()
        if view == "Tuần":
            plot["Ngày"] = plot["Ngày"].dt.to_period("W").apply(lambda r: r.start_time)
        elif view == "Tháng":
            plot["Ngày"] = plot["Ngày"].dt.to_period("M").apply(lambda r: r.start_time)
        plot = plot.groupby("Ngày", as_index=False)["Giá Trị"].sum()
        fig = px.bar(plot, x="Ngày", y="Giá Trị", title=f"Doanh thu theo {view.lower()}",
                     color_discrete_sequence=[BLUE])
        if view == "Tháng":
            fig.add_hline(y=kpi_dt, line_dash="dash", line_color=RED, annotation_text="KPI tháng")
        fig.update_yaxes(title_text="VNĐ")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Chưa có dữ liệu doanh thu trong khoảng đã chọn.")

    sec("4. Doanh thu khách hàng mới")
    kh_moi = slice_df(filter_scope(DF_KH_MOI, bc), start, end)
    if not kh_moi.empty:
        name_col = pick_col(kh_moi, [["ten kh"], ["ten khach"], ["khach hang"]])
        code_col = pick_col(kh_moi, [["ma kh"], ["ma khach"]])
        rev_col = pick_col(kh_moi, [["doanh thu"]])
        vol_col = pick_col(kh_moi, VOL_KEYS)
        keys = [c for c in (code_col, name_col) if c]
        if keys and rev_col:
            agg = {rev_col: "sum"}
            if vol_col:
                agg[vol_col] = "sum"
            tbl = kh_moi.groupby(keys, as_index=False).agg(agg).sort_values(rev_col, ascending=False)
            st.dataframe(
                tbl, use_container_width=True, hide_index=True, height=340,
                column_config={rev_col: st.column_config.NumberColumn("Doanh thu", format="%,d ₫")},
            )
            st.metric("Tổng doanh thu khách hàng mới", f"{tbl[rev_col].sum():,.0f} đ")
        else:
            st.dataframe(kh_moi, use_container_width=True, hide_index=True, height=340)
    else:
        st.info("Chưa có dữ liệu doanh thu khách hàng mới trong khoảng đã chọn.")

    sec("5. Phễu tiếp xúc khách hàng mới")
    pheu = filter_scope(DF_PHEU, bc)
    if "Ngày" in pheu.columns and pheu["Ngày"].notna().any():
        pheu = slice_df(pheu, start, end)
    status_col = pick_col(pheu, [["trang thai"]])
    if not pheu.empty and status_col:
        cnt = pheu.groupby(status_col).size().reset_index(name="Số lượng").sort_values("Số lượng", ascending=False)
        fig = go.Figure(go.Funnel(y=cnt[status_col], x=cnt["Số lượng"], textinfo="value+percent initial",
                                  marker={"color": [ORANGE, BLUE, GREEN, BLUE_DARK, MUTED]}))
        fig.update_layout(title="Phễu trạng thái khách hàng mới", hovermode="closest")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Chưa đọc được cột Trạng thái trong sheet phễu khách hàng.")

    sec("6. Danh sách khách hàng tiềm năng")
    if not pheu.empty and status_col:
        tn = pheu[pheu[status_col].astype(str).map(lambda x: "tiem nang" in norm(x))]
        if not tn.empty:
            drop = [c for c in tn.columns if c in ("Ngày",) and tn[c].isna().all()]
            st.dataframe(tn.drop(columns=drop), use_container_width=True, hide_index=True)
            st.caption(f"Có {len(tn)} khách hàng đang ở trạng thái tiềm năng, chờ chốt deal.")
        else:
            st.info("Không có khách hàng nào ở trạng thái 'Khách hàng tiềm năng'.")
    else:
        st.info("Cần cột Trạng thái để lọc khách hàng tiềm năng.")

    def prompt_kd(role: str) -> str:
        return f"""Dữ liệu kinh doanh GHN, {start:%d/%m/%Y} – {end:%d/%m/%Y}, bưu cục: {bc}.
- Doanh thu tháng này: {rev_month:,.0f} đ | KPI tháng: {kpi_dt:,.0f} đ
- Dự phóng hết tháng: {forecast:,.0f} đ ({forecast / kpi_dt * 100 if kpi_dt else 0:.1f}% KPI)
- Đã qua {days_done}/{days_total} ngày trong tháng.
- Doanh thu khách hàng mới trong kỳ: {kh_moi.select_dtypes('number').sum().max() if not kh_moi.empty else 0:,.0f}

{ROLE_STYLE[role]}
Chia 3 phần: 1) Tiến độ so với KPI, 2) Phễu khách hàng đang nghẽn ở đâu, 3) Việc chốt deal cần làm ngay.
{CLOSING}"""

    sec("Cố vấn AI kinh doanh")
    ai_block("kd", "🔍 AI cố vấn kinh doanh", prompt_kd, "Kinh Doanh")

# =============================================================================
# 12. TRANG 4 — NĂNG SUẤT & LƯƠNG
# =============================================================================
elif page == PAGES[3]:
    sec("Bộ lọc năng suất & lương")
    base_dates = DF_NSGTC if not DF_NSGTC.empty else DF_LUONG
    start, end, _ = quick_range(base_dates, "ns")
    c1, c2 = st.columns(2)
    with c1:
        bc = st.selectbox("Bưu cục", ALL_BC, key="bc_ns")
    nv_col_l = pick_col(DF_LUONG, [["nhan vien"]])
    nv_col_g = pick_col(DF_NSGTC, [["nhan vien"]])
    staff = set()
    for df, col in ((DF_LUONG, nv_col_l), (DF_NSGTC, nv_col_g)):
        if col and not df.empty:
            sub = filter_scope(df, bc)
            staff |= set(sub[col].dropna().astype(str).str.strip())
    with c2:
        nv = st.selectbox("Nhân viên", ["Tất cả"] + sorted(x for x in staff if x and x != "nan"), key="nv_ns")

    def scope_staff(df, nv_col):
        out = filter_scope(df, bc)
        if nv != "Tất cả" and nv_col and not out.empty:
            out = out[out[nv_col].astype(str).str.strip() == nv]
        return out

    L = scope_staff(DF_LUONG, nv_col_l)
    G = scope_staff(DF_NSGTC, nv_col_g)

    # --- Kỳ lương GHN: kỳ 20 (01–15), kỳ 05 (16–hết tháng) --------------------
    if REF_DATE.day <= 15:
        cur_a, cur_b = REF_DATE.replace(day=1), REF_DATE.replace(day=15)
        prev_b = cur_a - timedelta(days=1)
        prev_a = prev_b.replace(day=16)
        cur_name = f"Kỳ 20 · {cur_a:%m/%Y} (01–15, chi lương 20/{cur_a:%m})"
        prev_name = f"Kỳ 05 · {prev_a:%m/%Y} (16–hết tháng)"
    else:
        cur_a = REF_DATE.replace(day=16)
        cur_b = month_end(cur_a)
        prev_a, prev_b = REF_DATE.replace(day=1), REF_DATE.replace(day=15)
        nxt = cur_b + timedelta(days=1)
        cur_name = f"Kỳ 05 · {cur_a:%m/%Y} (16–hết tháng, chi lương 05/{nxt:%m})"
        prev_name = f"Kỳ 20 · {prev_a:%m/%Y} (01–15)"

    st.caption(f"Kỳ lương hiện tại: **{cur_name}** · Kỳ trước: **{prev_name}**")

    price_col = pick_col(L, [["don gia"]])
    gan_col = pick_col(G, [["gan giao"], ["so don gan"], ["gan"]])
    gtc_col = pick_col(G, [["giao tinh luong"], ["don gtc"], ["giao thanh cong"], ["gtc"]], exclude=["%"])

    def period_slice(df, a, b):
        return df[(df["Ngày"] >= a) & (df["Ngày"] <= b)] if df is not None and not df.empty else pd.DataFrame()

    L_cur, L_prev = period_slice(L, cur_a, cur_b), period_slice(L, prev_a, prev_b)
    G_cur, G_prev = period_slice(G, cur_a, cur_b), period_slice(G, prev_a, prev_b)

    sec("1. Đơn giá trung bình theo kỳ lương")
    p_cur = float(L_cur[price_col].mean()) if price_col and not L_cur.empty and L_cur[price_col].notna().any() else 0.0
    p_prev = float(L_prev[price_col].mean()) if price_col and not L_prev.empty and L_prev[price_col].notna().any() else 0.0
    a1, a2, a3 = st.columns(3)
    a1.metric("Kỳ hiện tại", f"{p_cur:,.0f} đ")
    a2.metric("Kỳ trước", f"{p_prev:,.0f} đ")
    a3.metric("Chênh lệch", f"{p_cur - p_prev:,.0f} đ", f"{p_cur - p_prev:,.0f} đ")

    sec("2. Sản lượng GTC theo kỳ lương")
    sl_cur = float(G_cur[gtc_col].sum()) if gtc_col and not G_cur.empty else 0.0
    sl_prev = float(G_prev[gtc_col].sum()) if gtc_col and not G_prev.empty else 0.0
    b1, b2, b3 = st.columns(3)
    b1.metric("Kỳ hiện tại", f"{sl_cur:,.0f} đơn")
    b2.metric("Kỳ trước", f"{sl_prev:,.0f} đơn")
    b3.metric("Chênh lệch", f"{sl_cur - sl_prev:,.0f} đơn", f"{sl_cur - sl_prev:,.0f} đơn")

    def pct_gtc(df):
        if df is None or df.empty or not gan_col or not gtc_col:
            return 0.0
        gan = df[gan_col].sum()
        return float(df[gtc_col].sum() / gan * 100) if gan > 0 else 0.0

    sec("3. %GTC theo kỳ lương")
    c1_, c2_, c3_ = st.columns(3)
    c1_.metric("Kỳ hiện tại", f"{pct_gtc(G_cur):.2f}%")
    c2_.metric("Kỳ trước", f"{pct_gtc(G_prev):.2f}%")
    c3_.metric("Chênh lệch", f"{pct_gtc(G_cur) - pct_gtc(G_prev):+.2f} pp")

    sec("4. %GTC theo ngày / tuần / tháng")
    if gan_col and gtc_col and not G.empty:
        gm = pd.DataFrame({"Ngày": G["Ngày"], "Giá Trị": np.where(
            G[gan_col] > 0, G[gtc_col] / G[gan_col] * 100, np.nan), "Trọng Số": G[gan_col]})
        trend_row("%GTC", gm, REF_DATE)
    else:
        st.info("Chưa đọc được cột 'Số đơn gán' hoặc 'Đơn giao tính lương' trong sheet năng suất.")

    G_range = period_slice(G, start, end)
    L_range = period_slice(L, start, end)

    sec("5. Biểu đồ đơn giá theo ngày")
    if price_col and not L_range.empty:
        g = L_range.groupby("Ngày", as_index=False)[price_col].mean()
        fig = px.line(g, x="Ngày", y=price_col, markers=True, title="Đơn giá trung bình theo ngày")
        fig.update_traces(line=dict(color=ORANGE, width=4),
                          marker=dict(size=9, color=BLUE, line=dict(width=2, color="#fff")))
        fig.update_yaxes(title_text="VNĐ")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Chưa đọc được cột Đơn giá.")

    sec("6. Sản lượng gán, sản lượng GTC và %GTC")
    if gan_col and gtc_col and not G_range.empty:
        g = G_range.groupby("Ngày", as_index=False).agg({gan_col: "sum", gtc_col: "sum"})
        g["%GTC"] = np.where(g[gan_col] > 0, g[gtc_col] / g[gan_col] * 100, 0.0)
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Bar(x=g["Ngày"], y=g[gan_col], name="Sản lượng gán",
                             marker_color=BLUE_DARK, opacity=.8), secondary_y=False)
        fig.add_trace(go.Bar(x=g["Ngày"], y=g[gtc_col], name="Sản lượng GTC",
                             marker_color=BLUE, opacity=.9), secondary_y=False)
        fig.add_trace(go.Scatter(x=g["Ngày"], y=g["%GTC"], name="% GTC", mode="lines+markers",
                                 line=dict(color=ORANGE, width=4), marker=dict(size=9)), secondary_y=True)
        fig.update_layout(title="Sản lượng gán · GTC · %GTC", barmode="group")
        fig.update_yaxes(title_text="Số đơn", secondary_y=False)
        fig.update_yaxes(title_text="% GTC", secondary_y=True, range=[0, 100], showgrid=False, ticksuffix="%")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Chưa đủ dữ liệu sản lượng gán / GTC để vẽ biểu đồ.")

    sec("7. Lương tổng")
    st.caption("Lương tổng = LHH LTC + LHH GTC + LHH GTBTT · "
               + " · ".join(f"**{k}**: {v}" for k, v in SALARY_PARTS.items()))
    pay_cols = {}
    for label in SALARY_PARTS:
        found = pick_col(L, [[label.lower()], [label.split()[-1].lower()]])
        if found:
            pay_cols[label] = found
    if pay_cols and not L_range.empty:
        chosen = st.multiselect("Thành phần lương", list(pay_cols), default=list(pay_cols), key="pay_parts")
        use = [pay_cols[c] for c in chosen] or list(pay_cols.values())
        tmp = L_range.copy()
        tmp["Tổng Lương"] = tmp[use].sum(axis=1)
        g = tmp.groupby("Ngày", as_index=False)["Tổng Lương"].sum()
        fig = px.area(g, x="Ngày", y="Tổng Lương", title="Lương tổng theo ngày")
        fig.update_traces(line=dict(color=GREEN, width=3), fillcolor="rgba(23,165,90,.15)")
        fig.update_yaxes(title_text="VNĐ")
        st.plotly_chart(fig, use_container_width=True)

        tot_cur = float(L_cur[use].sum().sum()) if not L_cur.empty else 0.0
        tot_prev = float(L_prev[use].sum().sum()) if not L_prev.empty else 0.0
        d1, d2, d3 = st.columns(3)
        d1.metric("Lương tổng kỳ này", f"{tot_cur:,.0f} đ")
        d2.metric("Lương tổng kỳ trước", f"{tot_prev:,.0f} đ")
        d3.metric("Chênh lệch", f"{tot_cur - tot_prev:,.0f} đ", f"{tot_cur - tot_prev:,.0f} đ")
    else:
        tot_cur = tot_prev = 0.0
        st.info("Chưa đọc được các cột LHH LTC / LHH GTC / LHH GTBTT trong sheet lương.")

    def prompt_ns(role: str) -> str:
        return f"""Dữ liệu năng suất & lương GHN, {start:%d/%m/%Y} – {end:%d/%m/%Y}, bưu cục: {bc}, nhân viên: {nv}.
Kỳ lương hiện tại: {cur_name}. Kỳ trước: {prev_name}.
- Đơn giá TB: {p_cur:,.0f} đ (kỳ trước {p_prev:,.0f} đ)
- Sản lượng GTC: {sl_cur:,.0f} đơn (kỳ trước {sl_prev:,.0f} đơn)
- %GTC: {pct_gtc(G_cur):.2f}% (kỳ trước {pct_gtc(G_prev):.2f}%)
- Lương tổng kỳ này: {tot_cur:,.0f} đ (kỳ trước {tot_prev:,.0f} đ)

{ROLE_STYLE[role]}
Chia 3 phần: 1) Năng suất và thu nhập đang đi lên hay xuống, 2) Nguyên nhân nghi ngờ, 3) Việc cần làm để tăng %GTC và thu nhập.
{CLOSING}"""

    sec("Cố vấn AI năng suất")
    ai_block("ns", "🔍 AI phân tích năng suất & lương", prompt_ns, "Năng Suất & Lương")

# =============================================================================
# 13. TRANG 5 — TIẾN ĐỘ KPI
# =============================================================================
elif page == PAGES[4]:
    sec("Bộ lọc KPI")
    start, end, _ = quick_range(M_GTC, "kpi")
    bc = st.selectbox("Bưu cục", ALL_BC, key="bc_kpi")

    def read_target(keys, fallback, exclude=()):
        """Đọc mục tiêu KPI từ sheet; nếu không có thì dùng giá trị mặc định."""
        if DF_KPI.empty:
            return fallback, False
        df = DF_KPI
        if not IS_ALL_BC or bc != "Tất cả":
            scoped = filter_scope(df, bc)
            df = scoped if not scoped.empty else df
        col = pick_col(df, keys, exclude=exclude)
        if col is None:
            return fallback, False
        vals = rescale_pct(df[col]).dropna()
        return (float(vals.iloc[-1]), True) if not vals.empty else (fallback, False)

    t_gtc, ok1 = read_target([["kpi", "gtc"], ["% gtc"], ["gtc"]], 70.0, exclude=["tts", "tiktok"])
    t_tts, ok2 = read_target([["gtc tts"], ["tts"], ["tiktok"]], 80.0)
    t_tra, ok3 = read_target([["tra hang"], ["tra"]], 5.0)

    if not (ok1 and ok2 and ok3):
        st.caption("Một số mục tiêu chưa đọc được từ sheet KPI — bạn có thể chỉnh tay bên dưới.")
        e1, e2, e3 = st.columns(3)
        with e1:
            t_gtc = st.number_input("Mục tiêu %GTC tổng", 0.0, 100.0, float(t_gtc), 0.5)
        with e2:
            t_tts = st.number_input("Mục tiêu %GTC TTS", 0.0, 100.0, float(t_tts), 0.5)
        with e3:
            t_tra = st.number_input("Ngưỡng %Trả hàng (tối đa)", 0.0, 100.0, float(t_tra), 0.5)

    a_gtc = value_of(filter_scope(M_GTC, bc), start, end)
    a_tts = value_of(filter_scope(M_TTS, bc), start, end)
    a_tra = value_of(filter_scope(M_TRA, bc), start, end)

    def gauge(title, value, target, higher_is_better=True):
        target = max(float(target), 0.5)
        if higher_is_better:
            steps = [
                {"range": [0, target * .8], "color": "#FDECEC"},
                {"range": [target * .8, target], "color": "#FFF2E6"},
                {"range": [target, 100], "color": "#E7F7EE"},
            ]
        else:
            steps = [
                {"range": [0, target], "color": "#E7F7EE"},
                {"range": [target, target * 1.5], "color": "#FFF2E6"},
                {"range": [min(target * 1.5, 100), 100], "color": "#FDECEC"},
            ]
        fig = go.Figure(go.Indicator(
            mode="gauge+number+delta", value=float(value),
            number={"suffix": "%", "valueformat": ".2f"},
            title={"text": title, "font": {"size": 17, "color": BLUE_DARK}},
            delta={"reference": target,
                   "increasing": {"color": GREEN if higher_is_better else RED},
                   "decreasing": {"color": RED if higher_is_better else GREEN}},
            gauge={
                "axis": {"range": [0, 100], "tickwidth": 2, "tickcolor": "#444"},
                "bar": {"color": INK, "thickness": .25},
                "steps": steps,
                "threshold": {"line": {"color": RED, "width": 4}, "thickness": .85, "value": target},
                "borderwidth": 2, "bordercolor": LINE,
            },
        ))
        fig.update_layout(height=300, margin=dict(l=20, r=20, t=60, b=15))
        return fig

    sec("Tiến độ hoàn thành KPI")
    g1, g2, g3 = st.columns(3)
    g1.plotly_chart(gauge("%GTC tổng", a_gtc, t_gtc), use_container_width=True)
    g2.plotly_chart(gauge("%GTC TikTok Shop", a_tts, t_tts), use_container_width=True)
    g3.plotly_chart(gauge("%Trả hàng (càng thấp càng tốt)", a_tra, t_tra, higher_is_better=False),
                    use_container_width=True)

    st.markdown(
        f"<div style='display:flex;gap:14px;flex-wrap:wrap;'>"
        f"<div>%GTC tổng {status_pill(a_gtc, t_gtc)}</div>"
        f"<div>%GTC TTS {status_pill(a_tts, t_tts)}</div>"
        f"<div>%Trả hàng {status_pill(a_tra, t_tra, higher_is_better=False)}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    sec("Bảng theo dõi KPI theo ngày")
    def daily_series(df, name):
        s = slice_df(filter_scope(df, bc), start, end)
        if s.empty:
            return pd.DataFrame(columns=["Ngày", name])
        g = (s.assign(_p=s["Giá Trị"].fillna(0) * s["Trọng Số"])
               .groupby("Ngày", as_index=False).agg(_p=("_p", "sum"), _w=("Trọng Số", "sum")))
        g[name] = np.where(g["_w"] > 0, g["_p"] / g["_w"], np.nan)
        return g[["Ngày", name]]

    tbl = daily_series(M_GTC, "%GTC")
    for src, nm in ((M_TTS, "%GTC TTS"), (M_TRA, "%Trả hàng")):
        tbl = tbl.merge(daily_series(src, nm), on="Ngày", how="outer")
    if not tbl.empty:
        tbl = tbl.sort_values("Ngày")
        tbl["% đạt KPI GTC"] = tbl["%GTC"] / t_gtc * 100 if t_gtc else 0
        tbl["Kết quả"] = np.where(tbl["%GTC"] >= t_gtc, "✅ Đạt", "❌ Chưa đạt")
        st.dataframe(
            tbl, use_container_width=True, hide_index=True,
            column_config={
                "Ngày": st.column_config.DateColumn("Ngày", format="DD/MM/YYYY"),
                "%GTC": st.column_config.NumberColumn(format="%.2f%%"),
                "%GTC TTS": st.column_config.NumberColumn(format="%.2f%%"),
                "%Trả hàng": st.column_config.NumberColumn(format="%.2f%%"),
                "% đạt KPI GTC": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=150),
            },
        )
    else:
        st.info("Chưa có dữ liệu KPI trong khoảng đã chọn.")

    def prompt_kpi(role: str) -> str:
        return f"""Tiến độ KPI GHN, {start:%d/%m/%Y} – {end:%d/%m/%Y}, bưu cục: {bc}.
- %GTC tổng: thực tế {a_gtc:.2f}% / mục tiêu {t_gtc:.2f}%
- %GTC TikTok Shop: thực tế {a_tts:.2f}% / mục tiêu {t_tts:.2f}%
- %Trả hàng: thực tế {a_tra:.2f}% / ngưỡng tối đa {t_tra:.2f}% (thấp hơn ngưỡng mới là đạt)

{ROLE_STYLE[role]}
Chia 3 phần: 1) Chỉ số nào đạt, chỉ số nào trượt, 2) Khoảng cách còn lại và thời gian còn bao nhiêu, 3) Hành động kéo số cụ thể.
{CLOSING}"""

    sec("Cố vấn AI KPI")
    ai_block("kpi", "🔍 AI đánh giá tiến độ KPI", prompt_kpi, "Tiến Độ KPI")

# =============================================================================
# 14. TRANG 6 — HỎI ĐÁP AI
# =============================================================================
else:
    sec("Hỏi đáp AI trên dữ liệu thực")
    st.caption("AI chỉ đọc dữ liệu trong khoảng thời gian bạn chọn và trong phạm vi bưu cục bạn được phân quyền.")

    c1, c2 = st.columns([2, 1])
    with c1:
        default_start = REF_DATE - timedelta(days=7)
        picked = st.date_input("Khoảng thời gian AI đọc", [default_start, REF_DATE], key="date_ai")
        if isinstance(picked, (list, tuple)) and len(picked) >= 2:
            ai_a, ai_b = pd.to_datetime(picked[0]), pd.to_datetime(picked[1])
        else:
            ai_a = ai_b = pd.to_datetime(picked[0]) if isinstance(picked, (list, tuple)) else pd.to_datetime(picked)
    with c2:
        bc = st.selectbox("Bưu cục", ALL_BC, key="bc_ai")

    if st.button("🧹 Xóa lịch sử hội thoại"):
        st.session_state.chat_history = []
        st.rerun()

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    def build_context(a, b) -> str:
        parts = []
        metric_map = [
            ("%GTC TỔNG", M_GTC, "wavg"), ("TỶ LỆ TRẢ HÀNG", M_TRA, "wavg"),
            ("GTB THU TIỀN", M_GTB, "wavg"), ("%GTC TIKTOK", M_TTS, "wavg"),
            ("ODR TIKTOK", M_ODR, "wavg"), ("DOANH THU", M_DT, "sum"),
        ]
        for name, frame, how in metric_map:
            s = slice_df(filter_scope(frame, bc), a, b)
            if s.empty:
                continue
            if how == "wavg":
                g = (s.assign(_p=s["Giá Trị"].fillna(0) * s["Trọng Số"])
                       .groupby(["Ngày", "Bưu Cục"], as_index=False)
                       .agg(_p=("_p", "sum"), _w=("Trọng Số", "sum")))
                g[name] = np.where(g["_w"] > 0, g["_p"] / g["_w"], np.nan)
                g = g.rename(columns={"_w": "Sản lượng"}).drop(columns=["_p"]).round(2)
            else:
                g = s.groupby(["Ngày", "Bưu Cục"], as_index=False)["Giá Trị"].sum().rename(
                    columns={"Giá Trị": name}).round(0)
            g["Ngày"] = g["Ngày"].dt.strftime("%d/%m/%Y")
            parts.append(f"\n--- {name} ---\n{g.to_csv(index=False)}")

        for label, df in (("NĂNG SUẤT NHÂN VIÊN", DF_NSGTC), ("LƯƠNG NHÂN VIÊN", DF_LUONG)):
            s = slice_df(filter_scope(df, bc), a, b)
            if not s.empty:
                cols = [c for c in s.columns if c != "Ngày"][:8]
                out = s[["Ngày"] + cols].copy()
                out["Ngày"] = out["Ngày"].dt.strftime("%d/%m/%Y")
                parts.append(f"\n--- {label} ---\n{out.head(400).to_csv(index=False)}")
        return "".join(parts) or "(Không có dữ liệu trong khoảng thời gian đã chọn.)"

    if question := st.chat_input("Ví dụ: bưu cục nào %GTC thấp nhất tuần qua?"):
        st.session_state.chat_history.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            with st.spinner("AI đang đọc dữ liệu..."):
                ctx = build_context(ai_a, ai_b)
                answer = ask_ai(f"""Bạn là trợ lý phân tích của trung tâm vận hành GHN.
Dữ liệu thực tế từ {ai_a:%d/%m/%Y} đến {ai_b:%d/%m/%Y}, phạm vi: {bc}.
{ctx}

Câu hỏi: {question}

Trả lời dựa ĐÚNG vào số liệu trên, nêu đích danh bưu cục/nhân viên và con số cụ thể.
Nếu dữ liệu không đủ, nói rõ là không có thay vì suy đoán. Trình bày markdown, in đậm số liệu quan trọng.""")
            st.markdown(answer)
            st.session_state.chat_history.append({"role": "assistant", "content": answer})

st.divider()
st.caption("Trung Tâm Vận Hành Toàn Cảnh · GHN · Designed by AM Phan Van Chanh")
