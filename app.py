"""
GHN · BẢNG ĐIỀU HÀNH KHU VỰC
Trung tâm vận hành: vận hành, kinh doanh, năng suất, KPI, hỏi AI.

Chạy local:  streamlit run app.py
Render:      streamlit run app.py --server.port $PORT --server.address 0.0.0.0

Hệ thiết kế: bảng điều độ ca của bưu cục — mỗi chỉ số một đèn, một mốc, một phán quyết.
Designed by AM Phan Van Chanh
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

# ════════════════════════════════════════════════════════════════════
# CẤU HÌNH
# ════════════════════════════════════════════════════════════════════
st.set_page_config(page_title="GHN · Bảng điều độ khu vực", page_icon="🚚",
                   layout="wide", initial_sidebar_state="expanded")

APP_DIR = Path(__file__).resolve().parent
LOGO = APP_DIR / "assets" / "logo_ghn.png"

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = "gemini-3.6-flash"
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
CHAT_LOG_CSV = os.environ.get("CHAT_LOG_CSV", "").strip()
CACHE_TTL = 300

INK      = "#0B1A2B"
INK_SOFT = "#16293D"
PAPER    = "#F4F6F8"
CARD     = "#FFFFFF"
RULE     = "#DDE3EA"
BLUE     = "#0057B8"
BLUE_DIM = "#5B8FD4"
ORANGE   = "#F26522"
GREEN    = "#0E9F6E"
AMBER    = "#D98A0B"
RED      = "#D92D20"
MUTE     = "#6B7A8C"

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

NAV = ["Trực ban", "Vận hành", "Kinh doanh", "Năng suất & Lương", "KPI", "Hỏi AI"]
ROLE_NAV = {"admin": NAV, "manager": NAV,
            "staff": ["Trực ban", "Vận hành", "Năng suất & Lương"]}

# ════════════════════════════════════════════════════════════════════
# HỆ THỐNG THIẾT KẾ
# ════════════════════════════════════════════════════════════════════
pio.templates["board"] = go.layout.Template(layout=dict(
    font=dict(family="Inter, sans-serif", size=12, color=MUTE),
    plot_bgcolor=CARD, paper_bgcolor=CARD, hovermode="x unified",
    colorway=[BLUE, ORANGE, GREEN, RED, INK, BLUE_DIM],
    margin=dict(l=48, r=18, t=18, b=38),
    xaxis=dict(showgrid=False, linecolor=RULE, linewidth=1, ticks="outside",
               tickcolor=RULE, ticklen=4,
               tickfont=dict(family="IBM Plex Mono, monospace", size=10, color=MUTE)),
    yaxis=dict(showgrid=True, gridcolor="#EEF1F4", gridwidth=1, zeroline=False,
               tickfont=dict(family="IBM Plex Mono, monospace", size=10, color=MUTE)),
    legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0,
                font=dict(family="IBM Plex Mono, monospace", size=10)),
    hoverlabel=dict(bgcolor=INK, bordercolor=INK,
                    font=dict(family="Inter", size=12, color="#fff")),
))
pio.templates.default = "board"

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700&family=IBM+Plex+Mono:wght@400;500;600&family=Inter:wght@400;500;600&display=swap');

:root {{
  --ink:{INK}; --paper:{PAPER}; --card:{CARD}; --rule:{RULE};
  --blue:{BLUE}; --orange:{ORANGE}; --green:{GREEN}; --amber:{AMBER}; --red:{RED}; --mute:{MUTE};
}}

.stApp {{ background:var(--paper); }}
html, body, [class*="css"] {{ font-family:'Inter',sans-serif; color:var(--ink); }}
.block-container {{ padding-top:1.6rem; padding-bottom:3rem; max-width:1480px; }}
#MainMenu, footer, header {{ visibility:hidden; }}

.eyebrow {{
  font-family:'IBM Plex Mono',monospace; font-size:10.5px; font-weight:500;
  letter-spacing:.14em; text-transform:uppercase; color:var(--mute); line-height:1.7;
}}
.num {{
  font-family:'Archivo',sans-serif; font-weight:600;
  font-variant-numeric:tabular-nums; letter-spacing:-.01em; color:var(--ink);
}}

.board {{ background:var(--ink); border-radius:4px; padding:20px 24px 18px; margin-bottom:18px; color:#fff; }}
.board-top {{
  display:flex; justify-content:space-between; align-items:baseline; flex-wrap:wrap; gap:8px;
  border-bottom:1px solid rgba(255,255,255,.12); padding-bottom:12px; margin-bottom:16px;
}}
.board-title {{
  font-family:'Archivo',sans-serif; font-weight:700; font-size:19px;
  letter-spacing:.02em; color:#fff; text-transform:uppercase;
}}
.board-meta {{
  font-family:'IBM Plex Mono',monospace; font-size:10.5px; letter-spacing:.1em;
  text-transform:uppercase; color:rgba(255,255,255,.55);
}}
.lamps {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(158px,1fr)); gap:22px; }}
.lamp-code {{
  font-family:'IBM Plex Mono',monospace; font-size:10px; letter-spacing:.14em;
  text-transform:uppercase; color:rgba(255,255,255,.5); margin-bottom:5px;
}}
.lamp-val {{
  font-family:'Archivo',sans-serif; font-weight:600; font-size:27px;
  font-variant-numeric:tabular-nums; color:#fff; line-height:1;
}}
.lamp-val small {{ font-size:13px; font-weight:500; opacity:.6; margin-left:2px; }}
.lamp-track {{ position:relative; height:5px; background:rgba(255,255,255,.13); border-radius:2px; margin-top:9px; }}
.lamp-fill {{ height:5px; border-radius:2px; }}
.lamp-tick {{ position:absolute; top:-3px; width:1.5px; height:11px; background:rgba(255,255,255,.85); }}
.lamp-note {{
  font-family:'IBM Plex Mono',monospace; font-size:10px; letter-spacing:.05em;
  color:rgba(255,255,255,.5); margin-top:7px;
}}

.exc {{
  background:var(--card); border:1px solid var(--rule); border-left:3px solid var(--rule);
  border-radius:3px; padding:12px 16px; margin-bottom:7px; display:flex; gap:14px; align-items:baseline;
}}
.exc-red {{ border-left-color:var(--red); }}
.exc-amber {{ border-left-color:var(--amber); }}
.exc-green {{ border-left-color:var(--green); }}
.exc-code {{
  font-family:'IBM Plex Mono',monospace; font-size:10.5px; font-weight:600; letter-spacing:.1em;
  text-transform:uppercase; color:var(--mute); min-width:104px; flex-shrink:0;
}}
.exc-text {{ font-size:14px; line-height:1.55; }}
.exc-text b {{ font-family:'Archivo',sans-serif; font-variant-numeric:tabular-nums; }}

.grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(228px,1fr)); gap:10px; }}
.card {{ background:var(--card); border:1px solid var(--rule); border-radius:3px; padding:14px 16px 12px; position:relative; }}
.card::before {{ content:''; position:absolute; left:0; top:0; bottom:0; width:3px; background:var(--rule); border-radius:3px 0 0 3px; }}
.card.up::before {{ background:var(--green); }}
.card.down::before {{ background:var(--red); }}
.card-val {{ font-size:30px; line-height:1.05; margin:6px 0 2px; }}
.card-val small {{ font-size:14px; opacity:.45; font-weight:500; }}
.card-delta {{ font-family:'IBM Plex Mono',monospace; font-size:11px; font-weight:500; letter-spacing:.03em; }}
.d-up {{ color:var(--green); }} .d-down {{ color:var(--red); }} .d-flat {{ color:var(--mute); }}
.card-spark {{ margin-top:8px; height:30px; }}

.head {{ display:flex; align-items:baseline; gap:12px; margin:30px 0 12px; }}
.head-t {{
  font-family:'Archivo',sans-serif; font-weight:600; font-size:15px; letter-spacing:.02em;
  text-transform:uppercase; color:var(--ink); white-space:nowrap;
}}
.head-r {{ flex:1; height:1px; background:var(--rule); }}
.head-n {{ font-family:'IBM Plex Mono',monospace; font-size:10px; letter-spacing:.1em; color:var(--mute); text-transform:uppercase; }}

.ai {{
  background:var(--card); border:1px solid var(--rule); border-top:3px solid var(--orange);
  border-radius:3px; padding:18px 20px; line-height:1.7; font-size:14.5px;
}}
.empty {{
  background:var(--card); border:1px dashed var(--rule); border-radius:3px;
  padding:26px; text-align:center; color:var(--mute); font-size:13.5px; line-height:1.6;
}}

section[data-testid="stSidebar"] {{ background:var(--card); border-right:1px solid var(--rule); }}
section[data-testid="stSidebar"] [role="radiogroup"] label {{
  font-family:'IBM Plex Mono',monospace !important; font-size:11.5px !important;
  letter-spacing:.09em; text-transform:uppercase; padding:5px 0;
}}

.stButton>button {{
  border-radius:3px; border:1px solid var(--rule); background:var(--card); color:var(--ink);
  font-family:'IBM Plex Mono',monospace; font-size:11.5px; letter-spacing:.07em;
  text-transform:uppercase; font-weight:500; padding:.5rem 1rem;
}}
.stButton>button:hover {{ border-color:var(--ink); }}
.stButton>button[kind="primary"] {{ background:var(--ink); color:#fff; border-color:var(--ink); }}
.stButton>button[kind="primary"]:hover {{ background:{INK_SOFT}; color:#fff; }}
div[data-testid="stDataFrame"] {{ border:1px solid var(--rule); border-radius:3px; }}
label, .stSelectbox label, .stRadio label, .stDateInput label, .stMultiSelect label, .stNumberInput label {{
  font-family:'IBM Plex Mono',monospace !important; font-size:10.5px !important;
  letter-spacing:.12em !important; text-transform:uppercase; color:var(--mute) !important;
}}
div[data-baseweb="select"]>div, div[data-baseweb="input"]>div {{ border-radius:3px; border-color:var(--rule); }}
hr {{ border-color:var(--rule); }}

@media (max-width:640px) {{
  .lamps {{ grid-template-columns:repeat(2,1fr); gap:16px; }}
  .board-title {{ font-size:16px; }}
  .card-val {{ font-size:25px; }}
  .exc {{ flex-direction:column; gap:4px; }}
}}
@media (prefers-reduced-motion:reduce) {{ * {{ animation:none !important; transition:none !important; }} }}
</style>
""", unsafe_allow_html=True)


def head(title: str, note: str = ""):
    st.markdown(f"<div class='head'><div class='head-t'>{title}</div>"
                f"<div class='head-r'></div><div class='head-n'>{note}</div></div>",
                unsafe_allow_html=True)


def empty(msg: str):
    st.markdown(f"<div class='empty'>{msg}</div>", unsafe_allow_html=True)


def sparkline(values, color=BLUE, w=190, h=30) -> str:
    v = [float(x) for x in values if pd.notna(x)]
    if len(v) < 2:
        return ""
    lo, hi = min(v), max(v)
    rng = (hi - lo) or 1.0
    step = w / (len(v) - 1)
    pts = [(i * step, h - 3 - (val - lo) / rng * (h - 8)) for i, val in enumerate(v)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    lx, ly = pts[-1]
    return (f"<svg width='100%' height='{h}' viewBox='0 0 {w} {h}' preserveAspectRatio='none'>"
            f"<polygon points='0,{h} {line} {w},{h}' fill='{color}' opacity='.07'/>"
            f"<polyline points='{line}' fill='none' stroke='{color}' stroke-width='1.6' "
            f"stroke-linejoin='round' stroke-linecap='round'/>"
            f"<circle cx='{lx:.1f}' cy='{ly:.1f}' r='2.4' fill='{color}'/></svg>")


def lamp(code: str, value: float, target: float | None, unit="%",
         higher_is_better=True, note="") -> str:
    if unit == "%":
        val_html = f"{value:,.2f}<small>%</small>"
    elif unit == "đ":
        val_html = f"{value/1_000_000:,.1f}<small>tr đ</small>"
    else:
        val_html = f"{value:,.0f}<small> {unit}</small>" if unit else f"{value:,.0f}"

    if target:
        ok = value >= target if higher_is_better else value <= target
        near = abs(value - target) / target <= .05
        col = GREEN if ok else (AMBER if near else RED)
        fill = max(min(value / target / 1.35 * 100, 100), 2)
        tick = 1 / 1.35 * 100
        bar = (f"<div class='lamp-track'><div class='lamp-fill' style='width:{fill:.0f}%;"
               f"background:{col};'></div><div class='lamp-tick' style='left:{tick:.0f}%;'></div></div>")
        note = note or f"mốc {target:,.1f}{'%' if unit == '%' else ''}"
    else:
        bar = "<div class='lamp-track'></div>"
    return (f"<div><div class='lamp-code'>{code}</div><div class='lamp-val'>{val_html}</div>"
            f"{bar}<div class='lamp-note'>{note}</div></div>")


def card(label: str, value: str, delta: float | None, series=None,
         unit="", higher_is_better=True, sub="") -> str:
    if delta is None:
        cls, dcls, dtxt = "", "d-flat", sub or "&nbsp;"
    else:
        good = (delta > 0) == higher_is_better
        cls = "" if abs(delta) < 1e-9 else ("up" if good else "down")
        dcls = "d-flat" if abs(delta) < 1e-9 else ("d-up" if good else "d-down")
        dtxt = f"{delta:+,.2f} pp" if unit == "%" else f"{delta:+,.0f}{' đ' if unit == 'đ' else ''}"
        if sub:
            dtxt += f" · {sub}"
    spark = ""
    if series is not None and len(list(series)) > 1:
        c = GREEN if cls == "up" else (RED if cls == "down" else BLUE_DIM)
        spark = f"<div class='card-spark'>{sparkline(series, c)}</div>"
    return (f"<div class='card {cls}'><div class='eyebrow'>{label}</div>"
            f"<div class='num card-val'>{value}</div>"
            f"<div class='card-delta {dcls}'>{dtxt}</div>{spark}</div>")


def grid(cards: list[str]):
    st.markdown(f"<div class='grid'>{''.join(cards)}</div>", unsafe_allow_html=True)


def sized(fig, height=290):
    fig.update_layout(height=height)
    return fig


# ════════════════════════════════════════════════════════════════════
# PHIÊN & ĐĂNG NHẬP
# ════════════════════════════════════════════════════════════════════
for k, v in {"auth": None, "ai": {}, "chat": [], "kpi_manual": {}}.items():
    st.session_state.setdefault(k, v)


def load_users() -> dict:
    raw = os.environ.get("APP_USERS", "").strip()
    if raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            st.error("APP_USERS chưa đúng định dạng JSON. Kiểm tra lại dấu ngoặc kép.")
    u, p = os.environ.get("APP_USER", "").strip(), os.environ.get("APP_PASS", "").strip()
    if u and p:
        return {u: {"password": p, "role": "admin", "ten": "Quản trị viên", "buu_cuc": ["Tất cả"]}}
    return {}


USERS = load_users()

if st.session_state.auth is None:
    _, mid, _ = st.columns([1, 1.1, 1])
    with mid:
        st.write("")
        if LOGO.exists():
            st.image(str(LOGO), width=230)
        st.markdown("<div class='eyebrow' style='margin:14px 0 4px;'>Trung tâm vận hành khu vực</div>"
                    "<div style='font-family:Archivo;font-weight:700;font-size:26px;"
                    "text-transform:uppercase;line-height:1.1;margin-bottom:18px;'>Bảng điều độ</div>",
                    unsafe_allow_html=True)
        if not USERS:
            st.error("Chưa có tài khoản nào. Đặt biến môi trường APP_USER và APP_PASS trên máy chủ, "
                     "rồi khởi động lại dịch vụ.")
            st.stop()
        with st.form("login"):
            uid = st.text_input("ID nhân viên")
            pwd = st.text_input("Mật khẩu", type="password")
            if st.form_submit_button("Vào ca", use_container_width=True, type="primary"):
                info = USERS.get(uid.strip())
                if info and str(info.get("password")) == pwd:
                    st.session_state.auth = {"id": uid.strip(), "ten": info.get("ten", uid.strip()),
                                             "role": info.get("role", "staff"),
                                             "buu_cuc": info.get("buu_cuc", ["Tất cả"])}
                    st.rerun()
                else:
                    st.error("ID hoặc mật khẩu không khớp. Kiểm tra lại hoặc hỏi quản trị viên khu vực.")
        st.markdown("<div class='eyebrow' style='margin-top:14px;'>Mỗi tài khoản chỉ thấy bưu cục được phân quyền</div>",
                    unsafe_allow_html=True)
    st.stop()

AUTH = st.session_state.auth
ALLOWED_BC = AUTH.get("buu_cuc", ["Tất cả"])
IS_ALL_BC = "Tất cả" in ALLOWED_BC

# ════════════════════════════════════════════════════════════════════
# LỚP DỮ LIỆU
# ════════════════════════════════════════════════════════════════════
def strip_accents(t: str) -> str:
    nfkd = unicodedata.normalize("NFD", str(t))
    return "".join(c for c in nfkd if unicodedata.category(c) != "Mn").replace("đ", "d").replace("Đ", "D")


def norm(t: str) -> str:
    s = strip_accents(t).lower().replace("\xa0", " ")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9% ]+", " ", s)).strip()


def parse_num(val):
    if pd.isna(val):
        return np.nan
    s = str(val)
    for j in ["%", "đ", "₫", "VNĐ", "vnd", " ", "\xa0"]:
        s = s.replace(j, "")
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
        p = s.split(".")
        if len(p) > 2:
            s = s.replace(".", "")
        elif len(p[1]) == 3 and p[0].lstrip("-") not in ("0", ""):
            s = s.replace(".", "")
    try:
        v = float(s)
        return -v if neg else v
    except ValueError:
        return np.nan


def pick_col(df, contains, exclude=()):
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
    df = pd.read_csv(f"https://docs.google.com/spreadsheets/d/{sid}/export?format=csv&gid={gid}")
    df.columns = df.columns.astype(str).str.strip().str.replace("\xa0", " ", regex=False)
    return df.loc[:, ~df.columns.str.match(r"^Unnamed")]


def safe_load(key: str) -> pd.DataFrame:
    try:
        return load_sheet(key)
    except Exception as exc:  # noqa: BLE001
        st.session_state.setdefault("errs", {})[key] = str(exc)
        return pd.DataFrame()


DATE_K = [["ngay"], ["thoi gian"], ["date"]]
BC_K = [["buu cuc"], ["buu"], ["khu vuc"], ["tram"], ["station"]]
VOL_K = [["san luong"], ["volume"], ["tong don"], ["so don"], ["don"]]


def base_frame(key: str) -> pd.DataFrame:
    raw = safe_load(key)
    if raw.empty:
        return pd.DataFrame(columns=["Ngày", "Bưu Cục"])
    df = raw.copy()
    dcol, bcol = pick_col(df, DATE_K), pick_col(df, BC_K)
    df["Ngày"] = pd.to_datetime(df[dcol], errors="coerce", dayfirst=True) if dcol else pd.NaT
    df["Bưu Cục"] = df[bcol].astype(str).str.strip() if bcol else "Chưa phân loại"
    keep_text = {pick_col(df, [[k]]) for k in
                 ("loai hang", "ca", "nhan vien", "trang thai", "ten", "ma", "tuyen")}
    for col in df.columns:
        if col in {dcol, bcol, "Ngày", "Bưu Cục"} or df[col].dtype.kind in "if":
            continue
        if col in keep_text:
            df[col] = df[col].astype(str).str.strip()
        else:
            df[col] = df[col].apply(parse_num)
    return df


def rescale_pct(s: pd.Series) -> pd.Series:
    s = pd.to_numeric(s, errors="coerce")
    v = s[s > 0].dropna()
    return s * 100 if (not v.empty and v.max() <= 1.2) else s


def metric_frame(key, value_keys, weight_keys=VOL_K, is_pct=True, extra_dim=None) -> pd.DataFrame:
    df = base_frame(key)
    cols = ["Ngày", "Bưu Cục", "Giá Trị", "Trọng Số"]
    if df.empty:
        return pd.DataFrame(columns=cols)
    vcol = pick_col(df, value_keys)
    if vcol is None:
        return pd.DataFrame(columns=cols)
    wcol = pick_col(df, weight_keys, exclude=[vcol]) if weight_keys else None
    out = pd.DataFrame({
        "Ngày": df["Ngày"], "Bưu Cục": df["Bưu Cục"],
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


def month_end(ts):
    n = ts.replace(day=28) + timedelta(days=4)
    return n - timedelta(days=n.day)


def period_pair(ref, mode):
    if mode == "Ngày":
        return (ref, ref), (ref - timedelta(days=1), ref - timedelta(days=1))
    if mode == "Tuần":
        a = ref - timedelta(days=ref.weekday())
        return (a, a + timedelta(days=6)), (a - timedelta(days=7), a - timedelta(days=1))
    a = ref.replace(day=1)
    pa = (a - timedelta(days=1)).replace(day=1)
    return (a, month_end(a)), (pa, a - timedelta(days=1))


def sl(df, a, b):
    if df is None or df.empty:
        return pd.DataFrame(columns=df.columns if df is not None else [])
    return df[(df["Ngày"] >= a) & (df["Ngày"] <= b)]


def val(df, a, b, how="wavg") -> float:
    s = sl(df, a, b)
    if s.empty:
        return 0.0
    return wavg(s["Giá Trị"], s["Trọng Số"]) if how == "wavg" else float(s["Giá Trị"].sum())


def daily(df, how="wavg") -> pd.DataFrame:
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


def scope(df, bc):
    if df is None or df.empty or "Bưu Cục" not in df.columns:
        return df if df is not None else pd.DataFrame()
    out = df
    if not IS_ALL_BC:
        allow = [norm(x) for x in ALLOWED_BC]
        out = out[out["Bưu Cục"].map(lambda x: norm(x) in allow)]
    if bc and bc != "Tất cả":
        out = out[out["Bưu Cục"].map(norm) == norm(bc)]
    return out


def bc_options(*frames):
    vals = set()
    for f in frames:
        if f is not None and not f.empty and "Bưu Cục" in f.columns:
            vals |= set(f["Bưu Cục"].dropna().astype(str).str.strip())
    vals = {v for v in vals if v and v.lower() not in ("nan", "chưa phân loại")}
    if not IS_ALL_BC:
        allow = [norm(x) for x in ALLOWED_BC]
        vals = {v for v in vals if norm(v) in allow}
    return ["Tất cả"] + sorted(vals)


# ════════════════════════════════════════════════════════════════════
# AI & TELEGRAM
# ════════════════════════════════════════════════════════════════════
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
        return "Thiếu thư viện google-genai. Chạy: pip install google-genai"
    c = genai_client()
    if c is None:
        return "Chưa có GEMINI_API_KEY. Thêm biến môi trường rồi khởi động lại dịch vụ."
    try:
        r = c.models.generate_content(
            model=GEMINI_MODEL, contents=prompt,
            config=genai_types.GenerateContentConfig(max_output_tokens=8192))
        if not getattr(r, "candidates", None):
            return "AI không trả về nội dung. Rút gọn câu hỏi rồi thử lại."
        return (r.text or "").strip() or "AI trả về nội dung rỗng."
    except Exception as exc:  # noqa: BLE001
        return f"Google AI báo lỗi: {exc}"


def send_telegram(text: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return False, "Chưa có TELEGRAM_TOKEN và TELEGRAM_CHAT_ID."
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    chunks = [text[i:i + 3800] for i in range(0, len(text), 3800)] or [""]
    for i, ch in enumerate(chunks):
        pre = "" if i == 0 else f"(phần {i+1}/{len(chunks)})\n"
        try:
            r = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": pre + ch}, timeout=20)
        except requests.RequestException as exc:
            return False, f"Không gửi được: {exc}"
        if r.status_code != 200:
            return False, f"Telegram từ chối, mã {r.status_code}."
    return True, f"Đã gửi {len(chunks)} tin."


ROLE_STYLE = {
    "Giám đốc": "Viết như giám đốc vận hành: đánh giá vĩ mô, nêu rủi ro hệ thống, đề xuất chiến lược. Chuyên nghiệp, quyết đoán.",
    "Quản lý khu vực": "Viết như AM khu vực: chỉ đích danh điểm nóng, giao việc cụ thể cho bưu cục và nhân viên. Dứt khoát, thực chiến.",
    "Nhân viên": 'Viết như trợ lý điều phối nhắn cho anh em. Xưng "Mình" với "Anh em", ngắn gọn, tạo động lực.',
}
CLOSE = "Viết súc tích, chia ý rõ ràng, không bỏ dở câu. Kết thúc bằng dòng [HẾT]."


def ai_panel(key: str, label: str, build_prompt, tab: str):
    c1, c2 = st.columns([1, 2.4])
    with c1:
        role = st.selectbox("Viết cho ai", list(ROLE_STYLE), key=f"r_{key}")
    with c2:
        st.markdown("<div style='height:26px'></div>", unsafe_allow_html=True)
        if st.button(label, type="primary", key=f"b_{key}", use_container_width=True):
            with st.spinner("Đang đọc số liệu..."):
                st.session_state.ai[key] = ask_ai(build_prompt(role))
    txt = st.session_state.ai.get(key)
    if txt:
        st.markdown(f"<div class='ai'>{txt}</div>", unsafe_allow_html=True)
        if st.button("Gửi lên nhóm Telegram", key=f"t_{key}"):
            ok, msg = send_telegram(f"[{tab.upper()}]\n\n" + txt.replace("*", ""))
            (st.success if ok else st.error)(msg)
    else:
        empty("Bấm nút phía trên để AI đọc đúng số liệu đang hiển thị và viết nhận định.")


# ════════════════════════════════════════════════════════════════════
# NẠP DỮ LIỆU
# ════════════════════════════════════════════════════════════════════
with st.spinner("Đang đồng bộ số liệu..."):
    M_GTC = metric_frame("gtc_tong", [["% gtc"], ["gtc"], ["giao thanh cong"]])
    M_TRA = metric_frame("tra_hang", [["tra hang"], ["tra"]])
    M_GTB = metric_frame("gtb_thu_tien", [["gtb"], ["thu tien"]])
    M_TTS = metric_frame("gtc_tts", [["gtc tts"], ["% gtc"], ["gtc"]])
    M_ODR = metric_frame("odr_tts", [["odr"], ["ontime"], ["dung han"]])
    M_CA = metric_frame("sl_gtc_ca", [["% gtc"], ["gtc"]], extra_dim=[["ca"], ["loai hang"]])
    M_DT = metric_frame("kd_doanh_thu", [["doanh thu"]], weight_keys=None, is_pct=False)
    DF_KPI = base_frame("kpi_vh")
    DF_KHM = base_frame("kd_kh_moi")
    DF_PHEU = base_frame("kd_pheu")
    DF_LUONG = base_frame("ns_luong")
    DF_NSGTC = base_frame("ns_gtc")

ALL_BC = bc_options(M_GTC, M_DT, DF_LUONG, DF_NSGTC)
REF = max([f["Ngày"].max() for f in (M_GTC, M_DT, DF_NSGTC)
           if f is not None and not f.empty and f["Ngày"].notna().any()]
          or [pd.Timestamp.today().normalize()])


def kpi_target(keys, fallback, exclude=(), bc="Tất cả"):
    if DF_KPI.empty:
        return float(fallback)
    df = scope(DF_KPI, bc)
    df = df if not df.empty else DF_KPI
    col = pick_col(df, keys, exclude=exclude)
    if col is None:
        return float(fallback)
    v = rescale_pct(df[col]).dropna()
    return float(v.iloc[-1]) if not v.empty else float(fallback)


def date_pick(label, default_a, default_b, key):
    p = st.date_input(label, [default_a, default_b], key=key)
    if isinstance(p, (list, tuple)) and len(p) >= 2:
        return pd.to_datetime(p[0]), pd.to_datetime(p[1])
    if isinstance(p, (list, tuple)) and len(p) == 1:
        return pd.to_datetime(p[0]), pd.to_datetime(p[0])
    return pd.to_datetime(default_a), pd.to_datetime(default_b)


# ════════════════════════════════════════════════════════════════════
# THANH BÊN
# ════════════════════════════════════════════════════════════════════
with st.sidebar:
    if LOGO.exists():
        st.image(str(LOGO), width=178)
    st.markdown(f"<div class='eyebrow' style='margin:10px 0 16px;'>{AUTH['ten']} · {AUTH['role']}<br>"
                f"{' / '.join(ALLOWED_BC)}</div>", unsafe_allow_html=True)
    pages = ROLE_NAV.get(AUTH["role"], ROLE_NAV["staff"])
    page = st.radio("Khu vực làm việc", pages, label_visibility="collapsed")
    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
    if st.button("Tải lại số liệu", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    if st.button("Kết ca", use_container_width=True):
        st.session_state.auth = None
        st.rerun()
    st.markdown(f"<div class='eyebrow' style='margin-top:16px;'>Số liệu đến {REF:%d.%m.%Y}<br>"
                f"Đồng bộ {datetime.now():%H:%M}</div>", unsafe_allow_html=True)
    errs = st.session_state.get("errs", {})
    if errs:
        st.markdown(f"<div class='eyebrow' style='color:{RED};margin-top:8px;'>"
                    f"{len(errs)} nguồn chưa đọc được: {', '.join(errs)}</div>", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════
# TRỰC BAN
# ════════════════════════════════════════════════════════════════════
if page == "Trực ban":
    bc = st.selectbox("Phạm vi", ALL_BC, key="bc_home")
    g_gtc, g_tra, g_tts, g_odr, g_gtb, g_dt = (scope(x, bc) for x in
                                               (M_GTC, M_TRA, M_TTS, M_ODR, M_GTB, M_DT))
    (dA, dB), (pA, pB) = period_pair(REF, "Ngày")
    (mA, mB), _ = period_pair(REF, "Tháng")

    t_gtc = kpi_target([["kpi", "gtc"], ["% gtc"], ["gtc"]], 70.0, exclude=["tts", "tiktok"], bc=bc)
    t_tts = kpi_target([["gtc tts"], ["tts"], ["tiktok"]], 80.0, bc=bc)
    t_tra = kpi_target([["tra hang"], ["tra"]], 5.0, bc=bc)
    t_odr = 98.0
    st.session_state.kpi_manual.setdefault(f"dt_{bc}", 71_000_000.0)
    t_dt = float(st.session_state.kpi_manual[f"dt_{bc}"])

    v_gtc, v_tts = val(g_gtc, dA, dB), val(g_tts, dA, dB)
    v_odr, v_tra = val(g_odr, dA, dB), val(g_tra, dA, dB)
    v_dt = val(g_dt, mA, mB, "sum")

    st.markdown(f"""<div class="board">
      <div class="board-top">
        <div class="board-title">Bảng điều độ · {bc}</div>
        <div class="board-meta">Ca ngày {REF:%d.%m.%Y} · vạch trắng là mốc</div>
      </div>
      <div class="lamps">
        {lamp("GTC tổng", v_gtc, t_gtc)}
        {lamp("GTC TikTok", v_tts, t_tts)}
        {lamp("ODR TikTok", v_odr, t_odr)}
        {lamp("Trả hàng", v_tra, t_tra, higher_is_better=False)}
        {lamp("Doanh thu tháng", v_dt, t_dt, unit="đ", note=f"mốc {t_dt/1_000_000:,.0f} tr đ")}
      </div></div>""", unsafe_allow_html=True)

    head("Cần xử lý ngay", "xếp theo mức lệch so với mốc")
    checks = [("GTC tổng", v_gtc, t_gtc, True, "%", "tỷ lệ giao thành công toàn khu vực"),
              ("GTC TikTok", v_tts, t_tts, True, "%", "đơn sàn TikTok Shop"),
              ("ODR TikTok", v_odr, t_odr, True, "%", "cam kết đúng hạn với sàn, thấp là bị phạt"),
              ("Trả hàng", v_tra, t_tra, False, "%", "đơn quay đầu về kho"),
              ("Doanh thu", v_dt, t_dt, True, "đ", "lũy kế tháng này")]
    issues = []
    for name, v, t, hib, unit, why in checks:
        if not t:
            continue
        gap = (v - t) if hib else (t - v)
        if gap < 0:
            issues.append((abs(gap) / t, name, v, t, unit, why, gap))
    issues.sort(reverse=True)

    if issues:
        rows = []
        for sev, name, v, t, unit, why, gap in issues:
            cls = "exc-red" if sev > .05 else "exc-amber"
            if unit == "%":
                txt = (f"<b>{v:,.2f}%</b> so với mốc <b>{t:,.2f}%</b>, thiếu "
                       f"<b>{abs(gap):,.2f}</b> điểm phần trăm — {why}.")
            else:
                txt = (f"<b>{v/1_000_000:,.1f} tr đ</b> so với mốc <b>{t/1_000_000:,.0f} tr đ</b>, thiếu "
                       f"<b>{abs(gap)/1_000_000:,.1f} tr đ</b> — {why}.")
            rows.append(f"<div class='exc {cls}'><div class='exc-code'>{name}</div>"
                        f"<div class='exc-text'>{txt}</div></div>")
        st.markdown("".join(rows), unsafe_allow_html=True)
    else:
        st.markdown("<div class='exc exc-green'><div class='exc-code'>Toàn khu vực</div>"
                    "<div class='exc-text'>Mọi chỉ số đang đạt mốc. Giữ nhịp và theo dõi tồn cuối ca.</div>"
                    "</div>", unsafe_allow_html=True)

    head("Nhịp trong ngày", "so với hôm trước · nét là 30 ngày gần nhất")
    cards = []
    for label, frame, hib, unit, how in [("GTC tổng", g_gtc, True, "%", "wavg"),
                                         ("Trả hàng", g_tra, False, "%", "wavg"),
                                         ("GTB thu tiền", g_gtb, True, "%", "wavg"),
                                         ("GTC TikTok", g_tts, True, "%", "wavg"),
                                         ("Doanh thu ngày", g_dt, True, "đ", "sum")]:
        now, prev = val(frame, dA, dB, how), val(frame, pA, pB, how)
        hist = daily(sl(frame, REF - timedelta(days=29), REF), how)["Giá Trị"].tolist()
        disp = f"{now:,.2f}%" if unit == "%" else f"{now/1_000_000:,.1f}<small> tr đ</small>"
        cards.append(card(label, disp, now - prev, hist, unit, hib))
    grid(cards)

    head("Tác phong & kỷ luật", "chưa nối nguồn")
    empty("Thêm một sheet chấm công hoặc vi phạm vào SOURCES, mục này sẽ tự hiện.")

    head("Tin nhắn nhóm", "AI đọc và tóm tắt")
    if CHAT_LOG_CSV:
        try:
            df_chat = pd.read_csv(CHAT_LOG_CSV).tail(300)
            st.markdown(f"<div class='eyebrow'>Đã nạp {len(df_chat)} tin gần nhất</div>",
                        unsafe_allow_html=True)
        except Exception as exc:  # noqa: BLE001
            df_chat = pd.DataFrame()
            empty(f"Không đọc được nguồn tin nhắn: {exc}")
    else:
        df_chat = pd.DataFrame()
        empty("Đặt biến CHAT_LOG_CSV trỏ tới sheet có các cột Ngày, Nhóm, Người gửi, Nội dung. "
              "AI sẽ tóm tắt chủ đề anh em đang bàn và cảnh báo khi có chuyện về lương hay quy trình.")

    def p_home(role):
        ctx = df_chat.to_csv(index=False)[:6000] if not df_chat.empty else "(chưa nối nguồn tin nhắn)"
        return f"""Bạn là trợ lý điều hành khu vực GHN. Ngày dữ liệu {REF:%d/%m/%Y}, phạm vi {bc}.
GTC tổng {v_gtc:.2f}% / mốc {t_gtc:.2f}%. GTC TikTok {v_tts:.2f}% / mốc {t_tts:.2f}%.
ODR TikTok {v_odr:.2f}% / mốc {t_odr:.2f}% (càng cao càng tốt, thấp là bị sàn phạt).
Trả hàng {v_tra:.2f}% / ngưỡng tối đa {t_tra:.2f}% (càng thấp càng tốt).
Doanh thu tháng {v_dt:,.0f} đ / mục tiêu {t_dt:,.0f} đ.

TIN NHẮN NHÓM:
{ctx}

{ROLE_STYLE[role]}
Ba phần: ĐANG TỐT, ĐANG HỎNG (nêu vì sao), LÀM NGAY (tối đa bốn việc, mỗi việc gắn một người chịu trách nhiệm).
Nếu có dữ liệu tin nhắn, thêm phần TÂM LÝ ĐỘI NGŨ.
{CLOSE}"""

    head("Nhận định", "AI đọc đúng số liệu đang hiển thị")
    ai_panel("home", "Viết nhận định trực ban", p_home, "Trực ban")

# ════════════════════════════════════════════════════════════════════
# VẬN HÀNH
# ════════════════════════════════════════════════════════════════════
elif page == "Vận hành":
    c1, c2, c3 = st.columns([1.1, 1.6, 1.3])
    with c1:
        bc = st.selectbox("Phạm vi", ALL_BC, key="bc_vh")
    with c2:
        quick = st.radio("Khung thời gian", ["Ngày", "Tuần", "Tháng", "Tự chọn"],
                         horizontal=True, key="q_vh")
    lo = M_GTC["Ngày"].min() if not M_GTC.empty else REF - timedelta(days=60)
    if quick == "Ngày":
        a0, b0 = REF, REF
    elif quick == "Tuần":
        a0, b0 = REF - timedelta(days=REF.weekday()), REF
    elif quick == "Tháng":
        a0, b0 = REF.replace(day=1), REF
    else:
        a0, b0 = lo, REF
    with c3:
        a0, b0 = date_pick("Khoảng ngày", a0, b0, "d_vh")

    span = (b0 - a0).days
    qa, qb = a0 - timedelta(days=span + 1), a0 - timedelta(days=1)

    def S(frame):
        return sl(scope(frame, bc), a0, b0)

    s_gtc, s_tra, s_gtb, s_tts, s_odr, s_ca = (S(x) for x in (M_GTC, M_TRA, M_GTB, M_TTS, M_ODR, M_CA))

    head("Chỉ số ca", f"{a0:%d.%m} – {b0:%d.%m} · {bc}")
    cards = []
    for label, cur, full, hib in [("GTC tổng", s_gtc, M_GTC, True),
                                  ("Trả hàng", s_tra, M_TRA, False),
                                  ("GTB thu tiền", s_gtb, M_GTB, True),
                                  ("GTC TikTok", s_tts, M_TTS, True),
                                  ("ODR TikTok", s_odr, M_ODR, True)]:
        now = wavg(cur["Giá Trị"], cur["Trọng Số"]) if not cur.empty else 0.0
        prv = sl(scope(full, bc), qa, qb)
        prev = wavg(prv["Giá Trị"], prv["Trọng Số"]) if not prv.empty else 0.0
        cards.append(card(label, f"{now:,.2f}%", now - prev,
                          daily(cur)["Giá Trị"].tolist(), "%", hib, sub="kỳ trước"))
    grid(cards)

    head("GTC tổng", "cột là sản lượng, đường là tỷ lệ")
    if not s_gtc.empty:
        g = daily(s_gtc)
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Bar(x=g["Ngày"], y=g["Trọng Số"], name="Sản lượng",
                             marker_color="#E8EEF6", marker_line_width=0), secondary_y=False)
        fig.add_trace(go.Scatter(x=g["Ngày"], y=g["Giá Trị"], name="%GTC", mode="lines+markers",
                                 line=dict(color=BLUE, width=2.2), marker=dict(size=5)),
                      secondary_y=True)
        fig.update_yaxes(ticksuffix="%", secondary_y=True, showgrid=False)
        st.plotly_chart(sized(fig, 300), use_container_width=True)
    else:
        empty("Chưa có dữ liệu GTC trong khoảng này.")

    head("Theo ca làm việc", "ca 1 · ca 2 · hàng tồn")
    if not s_ca.empty and "Chiều" in s_ca.columns:
        g = (s_ca.assign(_p=s_ca["Giá Trị"].fillna(0) * s_ca["Trọng Số"])
                 .groupby(["Ngày", "Chiều"], as_index=False)
                 .agg(_p=("_p", "sum"), w=("Trọng Số", "sum")))
        g["r"] = np.where(g["w"] > 0, g["_p"] / g["w"], np.nan)
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        shades = ["#C9D9EC", "#9DBBDF", "#6E99CE"]
        lines = [BLUE, ORANGE, GREEN]
        for i, name in enumerate(sorted(g["Chiều"].unique())):
            sub = g[g["Chiều"] == name]
            fig.add_trace(go.Bar(x=sub["Ngày"], y=sub["w"], name=name,
                                 marker_color=shades[i % 3], marker_line_width=0), secondary_y=False)
            fig.add_trace(go.Scatter(x=sub["Ngày"], y=sub["r"], name=f"%GTC {name}", mode="lines",
                                     line=dict(color=lines[i % 3], width=2)), secondary_y=True)
        fig.update_layout(barmode="stack")
        fig.update_yaxes(ticksuffix="%", secondary_y=True, showgrid=False, range=[0, 100])
        st.plotly_chart(sized(fig, 300), use_container_width=True)
    else:
        empty("Chưa đọc được cột ca hoặc loại hàng trong sheet theo ca.")

    cc1, cc2 = st.columns(2)
    with cc1:
        head("Trả hàng", "càng thấp càng tốt")
        if not s_tra.empty:
            fig = px.area(daily(s_tra), x="Ngày", y="Giá Trị")
            fig.update_traces(line=dict(color=RED, width=2), fillcolor="rgba(217,45,32,.07)")
            fig.update_yaxes(ticksuffix="%")
            st.plotly_chart(sized(fig, 250), use_container_width=True)
        else:
            empty("Chưa có dữ liệu trả hàng.")
    with cc2:
        head("GTB thu tiền", "giao thất bại nhưng thu được tiền")
        if not s_gtb.empty:
            fig = px.area(daily(s_gtb), x="Ngày", y="Giá Trị")
            fig.update_traces(line=dict(color=GREEN, width=2), fillcolor="rgba(14,159,110,.07)")
            fig.update_yaxes(ticksuffix="%")
            st.plotly_chart(sized(fig, 250), use_container_width=True)
        else:
            empty("Chưa có dữ liệu GTB thu tiền.")

    cc3, cc4 = st.columns(2)
    with cc3:
        head("GTC TikTok Shop", "")
        if not s_tts.empty:
            fig = px.line(daily(s_tts), x="Ngày", y="Giá Trị", markers=True)
            fig.update_traces(line=dict(color=BLUE, width=2.2), marker=dict(size=5))
            fig.update_yaxes(ticksuffix="%")
            st.plotly_chart(sized(fig, 250), use_container_width=True)
        else:
            empty("Chưa có dữ liệu GTC TikTok.")
    with cc4:
        head("ODR TikTok Shop", "cam kết đúng hạn với sàn")
        if not s_odr.empty:
            fig = px.line(daily(s_odr), x="Ngày", y="Giá Trị", markers=True)
            fig.update_traces(line=dict(color=ORANGE, width=2.2), marker=dict(size=5))
            fig.update_yaxes(ticksuffix="%")
            st.plotly_chart(sized(fig, 250), use_container_width=True)
        else:
            empty("Chưa có dữ liệu ODR.")

    def p_vh(role):
        def f(d):
            return wavg(d["Giá Trị"], d["Trọng Số"]) if not d.empty else 0.0
        return f"""Vận hành GHN {a0:%d/%m/%Y} – {b0:%d/%m/%Y}, phạm vi {bc}.
GTC tổng {f(s_gtc):.2f}%. Trả hàng {f(s_tra):.2f}% (thấp là tốt). GTB thu tiền {f(s_gtb):.2f}%.
GTC TikTok {f(s_tts):.2f}%. ODR TikTok {f(s_odr):.2f}% (cam kết đúng hạn với sàn, thấp là bị phạt).
Tổng sản lượng {s_gtc['Trọng Số'].sum() if not s_gtc.empty else 0:,.0f} đơn.

{ROLE_STYLE[role]}
Ba phần: hiệu suất, điểm nóng, việc làm ngay.
{CLOSE}"""

    head("Nhận định vận hành", "")
    ai_panel("vh", "Viết nhận định vận hành", p_vh, "Vận hành")

# ════════════════════════════════════════════════════════════════════
# KINH DOANH
# ════════════════════════════════════════════════════════════════════
elif page == "Kinh doanh":
    c1, c2, c3 = st.columns([1.1, 1.6, 1.3])
    with c1:
        bc = st.selectbox("Phạm vi", ALL_BC, key="bc_kd")
    with c2:
        view = st.radio("Gộp theo", ["Ngày", "Tuần", "Tháng"], horizontal=True, key="v_kd")
    lo = M_DT["Ngày"].min() if not M_DT.empty else REF - timedelta(days=60)
    with c3:
        a0, b0 = date_pick("Khoảng ngày", max(lo, REF - timedelta(days=29)), REF, "d_kd")

    dt = scope(M_DT, bc)
    (mA, mB), (pmA, pmB) = period_pair(REF, "Tháng")
    rev_m, rev_pm = val(dt, mA, mB, "sum"), val(dt, pmA, pmB, "sum")
    st.session_state.kpi_manual.setdefault(f"dt_{bc}", 71_000_000.0)

    k1, _ = st.columns([1, 2.4])
    with k1:
        st.session_state.kpi_manual[f"dt_{bc}"] = st.number_input(
            "Mục tiêu tháng (đ)", min_value=0.0,
            value=float(st.session_state.kpi_manual[f"dt_{bc}"]), step=1_000_000.0)
    target = float(st.session_state.kpi_manual[f"dt_{bc}"])
    done_days = max((REF - mA).days + 1, 1)
    total_days = month_end(mA).day
    forecast = rev_m / done_days * total_days
    pace = forecast / target * 100 if target else 0

    st.markdown(f"""<div class="board">
      <div class="board-top">
        <div class="board-title">Doanh thu tháng {mA:%m/%Y} · {bc}</div>
        <div class="board-meta">Đã qua {done_days}/{total_days} ngày</div>
      </div>
      <div class="lamps">
        {lamp("Lũy kế", rev_m, target, unit="đ", note=f"mốc {target/1_000_000:,.0f} tr đ")}
        {lamp("Dự phóng cuối tháng", forecast, target, unit="đ", note=f"đạt {pace:,.0f}% mục tiêu")}
        {lamp("Còn thiếu", max(target - forecast, 0), None, unit="đ", note="theo tốc độ hiện tại")}
        {lamp("Tháng trước", rev_pm, None, unit="đ", note="cùng phạm vi")}
      </div></div>""", unsafe_allow_html=True)

    head("Nhịp doanh thu", "so với kỳ liền trước")
    cards = []
    for mode in ["Ngày", "Tuần", "Tháng"]:
        (a, b), (za, zb) = period_pair(REF, mode)
        now, prev = val(dt, a, b, "sum"), val(dt, za, zb, "sum")
        hist = daily(sl(dt, REF - timedelta(days=29), REF), "sum")["Giá Trị"].tolist()
        cards.append(card(mode, f"{now/1_000_000:,.1f}<small> tr đ</small>", now - prev,
                          hist if mode == "Ngày" else None, "đ", True, sub="kỳ trước"))
    grid(cards)

    head("Biểu đồ doanh thu", f"gộp theo {view.lower()}")
    d_range = sl(dt, a0, b0)
    if not d_range.empty:
        plot = d_range.copy()
        if view == "Tuần":
            plot["Ngày"] = plot["Ngày"].dt.to_period("W").apply(lambda r: r.start_time)
        elif view == "Tháng":
            plot["Ngày"] = plot["Ngày"].dt.to_period("M").apply(lambda r: r.start_time)
        plot = plot.groupby("Ngày", as_index=False)["Giá Trị"].sum()
        fig = px.bar(plot, x="Ngày", y="Giá Trị")
        fig.update_traces(marker_color=BLUE, marker_line_width=0)
        if view == "Tháng":
            fig.add_hline(y=target, line_dash="dot", line_color=ORANGE, line_width=1.5,
                          annotation_text="mục tiêu", annotation_position="top left")
        st.plotly_chart(sized(fig, 300), use_container_width=True)
    else:
        empty("Chưa có doanh thu trong khoảng đã chọn.")

    e1, e2 = st.columns([1.15, 1])
    with e1:
        head("Khách hàng mới", "doanh thu trong kỳ")
        khm = sl(scope(DF_KHM, bc), a0, b0)
        if not khm.empty:
            ncol = pick_col(khm, [["ten kh"], ["ten khach"], ["khach hang"]])
            ccol = pick_col(khm, [["ma kh"], ["ma khach"]])
            rcol = pick_col(khm, [["doanh thu"]])
            vcol = pick_col(khm, VOL_K)
            keys = [c for c in (ccol, ncol) if c]
            if keys and rcol:
                agg = {rcol: "sum"}
                if vcol:
                    agg[vcol] = "sum"
                t = khm.groupby(keys, as_index=False).agg(agg).sort_values(rcol, ascending=False)
                st.dataframe(t, use_container_width=True, hide_index=True, height=300,
                             column_config={rcol: st.column_config.NumberColumn("Doanh thu",
                                                                                format="%,d ₫")})
            else:
                st.dataframe(khm, use_container_width=True, hide_index=True, height=300)
        else:
            empty("Chưa có khách hàng mới trong kỳ này.")
    with e2:
        head("Phễu tiếp xúc", "khách hàng mới")
        pheu = scope(DF_PHEU, bc)
        if "Ngày" in pheu.columns and pheu["Ngày"].notna().any():
            pheu = sl(pheu, a0, b0)
        scol = pick_col(pheu, [["trang thai"]])
        if not pheu.empty and scol:
            cnt = pheu.groupby(scol).size().reset_index(name="n").sort_values("n", ascending=False)
            fig = go.Figure(go.Funnel(y=cnt[scol], x=cnt["n"], textinfo="value+percent initial",
                                      marker=dict(color=[BLUE, "#3B78C4", BLUE_DIM, "#9DBBDF", "#C9D9EC"]),
                                      connector=dict(line=dict(color=RULE, width=1))))
            fig.update_layout(hovermode="closest", margin=dict(l=6, r=6, t=6, b=6))
            st.plotly_chart(sized(fig, 300), use_container_width=True)
        else:
            empty("Chưa đọc được cột trạng thái trong sheet phễu.")

    head("Khách hàng tiềm năng", "đang chờ chốt")
    if not pheu.empty and scol:
        tn = pheu[pheu[scol].astype(str).map(lambda x: "tiem nang" in norm(x))]
        if not tn.empty:
            drop = [c for c in tn.columns if tn[c].isna().all()]
            st.dataframe(tn.drop(columns=drop), use_container_width=True, hide_index=True)
        else:
            empty("Không có khách nào ở trạng thái tiềm năng. Cập nhật cột trạng thái trong sheet "
                  "để danh sách hiện ở đây.")
    else:
        empty("Cần cột trạng thái để lọc khách tiềm năng.")

    def p_kd(role):
        return f"""Kinh doanh GHN, phạm vi {bc}, tháng {mA:%m/%Y}.
Lũy kế {rev_m:,.0f} đ / mục tiêu {target:,.0f} đ. Dự phóng cuối tháng {forecast:,.0f} đ ({pace:.0f}% mục tiêu).
Đã qua {done_days}/{total_days} ngày. Tháng trước {rev_pm:,.0f} đ.

{ROLE_STYLE[role]}
Ba phần: tiến độ so với mục tiêu, phễu đang nghẽn ở đâu, việc chốt deal cần làm ngay.
{CLOSE}"""

    head("Nhận định kinh doanh", "")
    ai_panel("kd", "Viết nhận định kinh doanh", p_kd, "Kinh doanh")

# ════════════════════════════════════════════════════════════════════
# NĂNG SUẤT & LƯƠNG
# ════════════════════════════════════════════════════════════════════
elif page == "Năng suất & Lương":
    c1, c2, c3 = st.columns([1.1, 1.3, 1.4])
    with c1:
        bc = st.selectbox("Phạm vi", ALL_BC, key="bc_ns")
    nv_l, nv_g = pick_col(DF_LUONG, [["nhan vien"]]), pick_col(DF_NSGTC, [["nhan vien"]])
    staff = set()
    for df, col in ((DF_LUONG, nv_l), (DF_NSGTC, nv_g)):
        if col and not df.empty:
            staff |= set(scope(df, bc)[col].dropna().astype(str).str.strip())
    with c2:
        nv = st.selectbox("Nhân viên", ["Tất cả"] + sorted(x for x in staff if x and x != "nan"),
                          key="nv_ns")
    base = DF_NSGTC if not DF_NSGTC.empty else DF_LUONG
    lo = base["Ngày"].min() if not base.empty and base["Ngày"].notna().any() else REF - timedelta(days=60)
    with c3:
        a0, b0 = date_pick("Khoảng ngày", max(lo, REF - timedelta(days=29)), REF, "d_ns")

    def only(df, col):
        out = scope(df, bc)
        if nv != "Tất cả" and col and not out.empty:
            out = out[out[col].astype(str).str.strip() == nv]
        return out

    L, G = only(DF_LUONG, nv_l), only(DF_NSGTC, nv_g)

    if REF.day <= 15:
        cA, cB = REF.replace(day=1), REF.replace(day=15)
        pB_ = cA - timedelta(days=1)
        pA_ = pB_.replace(day=16)
        c_name, p_name = f"Kỳ 20 · {cA:%m/%Y}", f"Kỳ 05 · {pA_:%m/%Y}"
    else:
        cA = REF.replace(day=16)
        cB = month_end(cA)
        pA_, pB_ = REF.replace(day=1), REF.replace(day=15)
        c_name, p_name = f"Kỳ 05 · {cA:%m/%Y}", f"Kỳ 20 · {pA_:%m/%Y}"

    price = pick_col(L, [["don gia"]])
    gan = pick_col(G, [["gan giao"], ["so don gan"], ["gan"]])
    gtc = pick_col(G, [["giao tinh luong"], ["don gtc"], ["giao thanh cong"], ["gtc"]], exclude=["%"])
    pay = {k: pick_col(L, [[k.lower()], [k.split()[-1].lower()]]) for k in SALARY_PARTS}
    pay = {k: v for k, v in pay.items() if v}

    def cut(df, a, b):
        return df[(df["Ngày"] >= a) & (df["Ngày"] <= b)] if df is not None and not df.empty else pd.DataFrame()

    Lc, Lp, Gc, Gp = cut(L, cA, cB), cut(L, pA_, pB_), cut(G, cA, cB), cut(G, pA_, pB_)

    def avg_price(d):
        return float(d[price].mean()) if price and not d.empty and d[price].notna().any() else 0.0

    def sum_gtc(d):
        return float(d[gtc].sum()) if gtc and not d.empty else 0.0

    def pct(d):
        if d is None or d.empty or not gan or not gtc:
            return 0.0
        s = d[gan].sum()
        return float(d[gtc].sum() / s * 100) if s > 0 else 0.0

    def total_pay(d):
        return float(d[list(pay.values())].sum().sum()) if pay and not d.empty else 0.0

    st.markdown(f"""<div class="board">
      <div class="board-top">
        <div class="board-title">{c_name} · {bc}{'' if nv == 'Tất cả' else ' · ' + nv}</div>
        <div class="board-meta">{cA:%d.%m} – {cB:%d.%m} · so với {p_name}</div>
      </div>
      <div class="lamps">
        {lamp("Đơn giá TB", avg_price(Lc), None, unit="đ", note=f"kỳ trước {avg_price(Lp):,.0f} đ")}
        {lamp("Sản lượng GTC", sum_gtc(Gc), None, unit="đơn", note=f"kỳ trước {sum_gtc(Gp):,.0f} đơn")}
        {lamp("%GTC", pct(Gc), 80.0, note="mốc thưởng 80%")}
        {lamp("Lương tổng", total_pay(Lc), None, unit="đ", note=f"kỳ trước {total_pay(Lp)/1_000_000:,.1f} tr đ")}
      </div></div>""", unsafe_allow_html=True)

    st.markdown("<div class='eyebrow'>Kỳ 20 tính từ ngày 01 đến 15, chi lương ngày 20 &nbsp;·&nbsp; "
                "Kỳ 05 tính từ ngày 16 đến hết tháng, chi lương ngày 05 tháng sau &nbsp;·&nbsp; "
                "Lương tổng = LHH LTC + LHH GTC + LHH GTBTT</div>", unsafe_allow_html=True)

    head("Nhịp %GTC", "so với kỳ liền trước")
    if gan and gtc and not G.empty:
        gm = pd.DataFrame({"Ngày": G["Ngày"],
                           "Giá Trị": np.where(G[gan] > 0, G[gtc] / G[gan] * 100, np.nan),
                           "Trọng Số": G[gan]})
        cards = []
        for mode in ["Ngày", "Tuần", "Tháng"]:
            (a, b), (za, zb) = period_pair(REF, mode)
            now, prev = val(gm, a, b), val(gm, za, zb)
            hist = daily(sl(gm, REF - timedelta(days=29), REF))["Giá Trị"].tolist()
            cards.append(card(mode, f"{now:,.2f}%", now - prev,
                              hist if mode == "Ngày" else None, "%", True, sub="kỳ trước"))
        grid(cards)
    else:
        gm = pd.DataFrame(columns=["Ngày", "Giá Trị", "Trọng Số"])
        empty("Chưa đọc được cột số đơn gán hoặc đơn giao tính lương.")

    Gr, Lr = cut(G, a0, b0), cut(L, a0, b0)

    head("Sản lượng gán · GTC · tỷ lệ", f"{a0:%d.%m} – {b0:%d.%m}")
    if gan and gtc and not Gr.empty:
        g = Gr.groupby("Ngày", as_index=False).agg({gan: "sum", gtc: "sum"})
        g["r"] = np.where(g[gan] > 0, g[gtc] / g[gan] * 100, 0.0)
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Bar(x=g["Ngày"], y=g[gan], name="Gán",
                             marker_color="#E8EEF6", marker_line_width=0), secondary_y=False)
        fig.add_trace(go.Bar(x=g["Ngày"], y=g[gtc], name="Giao thành công",
                             marker_color=BLUE_DIM, marker_line_width=0), secondary_y=False)
        fig.add_trace(go.Scatter(x=g["Ngày"], y=g["r"], name="%GTC", mode="lines+markers",
                                 line=dict(color=ORANGE, width=2.2), marker=dict(size=5)),
                      secondary_y=True)
        fig.update_layout(barmode="overlay")
        fig.update_yaxes(ticksuffix="%", secondary_y=True, showgrid=False, range=[0, 100])
        st.plotly_chart(sized(fig, 300), use_container_width=True)
    else:
        empty("Chưa đủ dữ liệu gán và giao để vẽ.")

    f1, f2 = st.columns(2)
    with f1:
        head("Đơn giá theo ngày", "")
        if price and not Lr.empty:
            g = Lr.groupby("Ngày", as_index=False)[price].mean()
            fig = px.line(g, x="Ngày", y=price, markers=True)
            fig.update_traces(line=dict(color=INK, width=2), marker=dict(size=4, color=INK))
            st.plotly_chart(sized(fig, 250), use_container_width=True)
        else:
            empty("Chưa đọc được cột đơn giá.")
    with f2:
        head("Lương tổng theo ngày", " + ".join(pay) if pay else "")
        if pay and not Lr.empty:
            tmp = Lr.copy()
            tmp["T"] = tmp[list(pay.values())].sum(axis=1)
            g = tmp.groupby("Ngày", as_index=False)["T"].sum()
            fig = px.area(g, x="Ngày", y="T")
            fig.update_traces(line=dict(color=GREEN, width=2), fillcolor="rgba(14,159,110,.08)")
            st.plotly_chart(sized(fig, 250), use_container_width=True)
        else:
            empty("Chưa đọc được các cột LHH LTC, LHH GTC, LHH GTBTT.")

    if gan and gtc and nv_g and not Gr.empty:
        head("Xếp hạng nhân viên", f"{a0:%d.%m} – {b0:%d.%m} · mốc thưởng 80%")
        r = Gr.groupby(nv_g, as_index=False).agg({gan: "sum", gtc: "sum"})
        r["%GTC"] = np.where(r[gan] > 0, r[gtc] / r[gan] * 100, 0.0)
        r = r.sort_values("%GTC", ascending=False).reset_index(drop=True)
        medals = ["🥇", "🥈", "🥉"]
        r.insert(0, "Hạng", [f"{medals[i]} {i+1}" if i < 3 else str(i + 1) for i in range(len(r))])
        r["Thưởng"] = np.where(r["%GTC"] >= 80, "Đạt", "Chưa")
        st.dataframe(r, use_container_width=True, hide_index=True,
                     column_config={gan: st.column_config.NumberColumn("Đơn gán", format="%,d"),
                                    gtc: st.column_config.NumberColumn("Đơn GTC", format="%,d"),
                                    "%GTC": st.column_config.ProgressColumn("%GTC", format="%.2f%%",
                                                                            min_value=0, max_value=100)})

    def p_ns(role):
        return f"""Năng suất và lương GHN, phạm vi {bc}, nhân viên {nv}.
{c_name} ({cA:%d/%m}–{cB:%d/%m}) so với {p_name}.
Đơn giá TB {avg_price(Lc):,.0f} đ (kỳ trước {avg_price(Lp):,.0f} đ).
Sản lượng GTC {sum_gtc(Gc):,.0f} đơn (kỳ trước {sum_gtc(Gp):,.0f} đơn).
%GTC {pct(Gc):.2f}% (kỳ trước {pct(Gp):.2f}%), mốc thưởng 80%.
Lương tổng {total_pay(Lc):,.0f} đ (kỳ trước {total_pay(Lp):,.0f} đ).

{ROLE_STYLE[role]}
Ba phần: năng suất và thu nhập đang lên hay xuống, nguyên nhân nghi ngờ, việc cần làm để kéo %GTC.
{CLOSE}"""

    head("Nhận định năng suất", "")
    ai_panel("ns", "Viết nhận định năng suất", p_ns, "Năng suất")

# ════════════════════════════════════════════════════════════════════
# KPI
# ════════════════════════════════════════════════════════════════════
elif page == "KPI":
    c1, c2 = st.columns([1.1, 2])
    with c1:
        bc = st.selectbox("Phạm vi", ALL_BC, key="bc_kpi")
    with c2:
        a0, b0 = date_pick("Khoảng ngày", REF.replace(day=1), REF, "d_kpi")

    t_gtc = kpi_target([["kpi", "gtc"], ["% gtc"], ["gtc"]], 70.0, exclude=["tts", "tiktok"], bc=bc)
    t_tts = kpi_target([["gtc tts"], ["tts"], ["tiktok"]], 80.0, bc=bc)
    t_tra = kpi_target([["tra hang"], ["tra"]], 5.0, bc=bc)

    with st.expander("Chỉnh mốc KPI"):
        e1, e2, e3 = st.columns(3)
        with e1:
            t_gtc = st.number_input("GTC tổng tối thiểu (%)", 0.0, 100.0, float(t_gtc), .5)
        with e2:
            t_tts = st.number_input("GTC TikTok tối thiểu (%)", 0.0, 100.0, float(t_tts), .5)
        with e3:
            t_tra = st.number_input("Trả hàng tối đa (%)", 0.0, 100.0, float(t_tra), .5)

    a_gtc = val(scope(M_GTC, bc), a0, b0)
    a_tts = val(scope(M_TTS, bc), a0, b0)
    a_tra = val(scope(M_TRA, bc), a0, b0)

    st.markdown(f"""<div class="board">
      <div class="board-top">
        <div class="board-title">Tiến độ KPI · {bc}</div>
        <div class="board-meta">{a0:%d.%m.%Y} – {b0:%d.%m.%Y}</div>
      </div>
      <div class="lamps">
        {lamp("GTC tổng", a_gtc, t_gtc)}
        {lamp("GTC TikTok", a_tts, t_tts)}
        {lamp("Trả hàng", a_tra, t_tra, higher_is_better=False)}
      </div></div>""", unsafe_allow_html=True)

    head("Bám mốc theo ngày", "đường chấm là mốc KPI")
    series = []
    for frame, name, color, tgt in ((M_GTC, "GTC tổng", BLUE, t_gtc),
                                    (M_TTS, "GTC TikTok", GREEN, t_tts),
                                    (M_TRA, "Trả hàng", RED, t_tra)):
        g = daily(sl(scope(frame, bc), a0, b0))
        if not g.empty:
            series.append((g, name, color, tgt))
    if series:
        fig = go.Figure()
        for g, name, color, tgt in series:
            fig.add_trace(go.Scatter(x=g["Ngày"], y=g["Giá Trị"], name=name, mode="lines+markers",
                                     line=dict(color=color, width=2), marker=dict(size=4)))
            fig.add_hline(y=tgt, line_dash="dot", line_color=color, line_width=1, opacity=.45)
        fig.update_yaxes(ticksuffix="%")
        st.plotly_chart(sized(fig, 320), use_container_width=True)

        tbl = daily(sl(scope(M_GTC, bc), a0, b0)).rename(
            columns={"Giá Trị": "%GTC", "Trọng Số": "Sản lượng"})
        for frame, nm in ((M_TTS, "%GTC TTS"), (M_TRA, "%Trả hàng")):
            d = daily(sl(scope(frame, bc), a0, b0))[["Ngày", "Giá Trị"]].rename(columns={"Giá Trị": nm})
            tbl = tbl.merge(d, on="Ngày", how="outer")
        tbl = tbl.sort_values("Ngày")
        tbl["Đạt mốc GTC"] = np.where(tbl["%GTC"] >= t_gtc, "Đạt", "Chưa")
        st.dataframe(tbl, use_container_width=True, hide_index=True,
                     column_config={"Ngày": st.column_config.DateColumn(format="DD/MM/YYYY"),
                                    "Sản lượng": st.column_config.NumberColumn(format="%,d"),
                                    "%GTC": st.column_config.ProgressColumn(format="%.2f%%",
                                                                            min_value=0, max_value=100),
                                    "%GTC TTS": st.column_config.NumberColumn(format="%.2f%%"),
                                    "%Trả hàng": st.column_config.NumberColumn(format="%.2f%%")})
    else:
        empty("Chưa có dữ liệu KPI trong khoảng đã chọn.")

    def p_kpi(role):
        return f"""Tiến độ KPI GHN {a0:%d/%m/%Y} – {b0:%d/%m/%Y}, phạm vi {bc}.
GTC tổng {a_gtc:.2f}% / mốc tối thiểu {t_gtc:.2f}%.
GTC TikTok {a_tts:.2f}% / mốc tối thiểu {t_tts:.2f}%.
Trả hàng {a_tra:.2f}% / ngưỡng tối đa {t_tra:.2f}% (thấp hơn ngưỡng mới là đạt).

{ROLE_STYLE[role]}
Ba phần: chỉ số nào đạt và trượt, khoảng cách còn lại, hành động kéo số.
{CLOSE}"""

    head("Nhận định KPI", "")
    ai_panel("kpi", "Viết nhận định KPI", p_kpi, "KPI")

# ════════════════════════════════════════════════════════════════════
# HỎI AI
# ════════════════════════════════════════════════════════════════════
else:
    c1, c2 = st.columns([2, 1])
    with c1:
        aA, aB = date_pick("Khoảng ngày AI được đọc", REF - timedelta(days=7), REF, "d_ai")
    with c2:
        bc = st.selectbox("Phạm vi", ALL_BC, key="bc_ai")

    head("Hỏi AI", f"{aA:%d.%m} – {aB:%d.%m} · {bc}")
    if not st.session_state.chat:
        empty("Hỏi bằng tiếng Việt thường ngày. Ví dụ: bưu cục nào GTC thấp nhất tuần qua, "
              "ai giao nhiều đơn nhất, doanh thu tuần này so với tuần trước ra sao.")
    for m in st.session_state.chat:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
    if st.session_state.chat and st.button("Xóa hội thoại"):
        st.session_state.chat = []
        st.rerun()

    def build_ctx(a, b):
        parts = []
        for name, frame, how in [("GTC TONG", M_GTC, "wavg"), ("TRA HANG", M_TRA, "wavg"),
                                 ("GTB THU TIEN", M_GTB, "wavg"), ("GTC TIKTOK", M_TTS, "wavg"),
                                 ("ODR TIKTOK", M_ODR, "wavg"), ("DOANH THU", M_DT, "sum")]:
            s = sl(scope(frame, bc), a, b)
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
            s = sl(scope(df, bc), a, b)
            if not s.empty:
                cols = [c for c in s.columns if c != "Ngày"][:8]
                o = s[["Ngày"] + cols].copy()
                o["Ngày"] = o["Ngày"].dt.strftime("%d/%m/%Y")
                parts.append(f"\n--- {label} ---\n{o.head(400).to_csv(index=False)}")
        return "".join(parts) or "(Không có dữ liệu trong khoảng đã chọn.)"

    if q := st.chat_input("Hỏi về số liệu trong khoảng đã chọn"):
        st.session_state.chat.append({"role": "user", "content": q})
        with st.chat_message("user"):
            st.markdown(q)
        with st.chat_message("assistant"):
            with st.spinner("Đang đọc số liệu..."):
                ans = ask_ai(f"""Bạn là trợ lý phân tích của trung tâm vận hành GHN.
Số liệu thực tế {aA:%d/%m/%Y} – {aB:%d/%m/%Y}, phạm vi {bc}:
{build_ctx(aA, aB)}

Câu hỏi: {q}

Trả lời dựa đúng số liệu trên, gọi tên đích danh bưu cục hoặc nhân viên kèm con số.
Nếu số liệu không đủ để trả lời, nói rõ là không có, đừng suy đoán.
Trình bày bằng markdown, in đậm con số quan trọng.""")
            st.markdown(ans)
            st.session_state.chat.append({"role": "assistant", "content": ans})

st.markdown(f"<div style='margin-top:38px;padding-top:14px;border-top:1px solid {RULE};' "
            f"class='eyebrow'>GHN · Bảng điều độ khu vực · Designed by AM Phan Van Chanh</div>",
            unsafe_allow_html=True)
