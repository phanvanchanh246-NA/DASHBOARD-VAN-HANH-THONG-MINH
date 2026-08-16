"""
GHN · BÁO CÁO VẬN HÀNH KHU VỰC
Hệ thiết kế: báo cáo thường niên doanh nghiệp — bìa, ghi chú, phụ lục.

Kiến trúc thông tin (khác hẳn bản "bảng điều độ" trước):
  Trang bìa      — thư điều hành + số nổi bật + điểm cần lưu ý
  Ghi chú 01     — Vận hành
  Ghi chú 02     — Kinh doanh
  Ghi chú 03     — Năng suất & Lương
  Ghi chú 04     — Chỉ tiêu KPI
  Phụ lục        — Hỏi đáp dữ liệu (AI)

Chạy local:  streamlit run app.py
Render:      streamlit run app.py --server.port $PORT --server.address 0.0.0.0

Designed by AM Phan Van Chanh
"""

from __future__ import annotations

import html as html_lib
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
st.set_page_config(page_title="GHN · Trung tâm vận hành chiến lược", page_icon="🚀",
                   layout="wide", initial_sidebar_state="expanded")

APP_DIR = Path(__file__).resolve().parent
LOGO = APP_DIR / "assets" / "logo_ghn.png"

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = "gemini-3.6-flash"
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
CHAT_LOG_CSV = os.environ.get("CHAT_LOG_CSV", "").strip()
CACHE_TTL = 300

# ── Bảng màu: báo cáo tài chính — mực xanh đen, giấy ngà, đồng trầm ──
# ── Hệ màu: dark analytics — nền tối, số liệu phát sáng ────────────
# Tên biến giữ nguyên để không phải sửa toàn bộ phần thân, chỉ đổi giá trị.
INK      = "#E8EDF7"   # CHỮ CHÍNH (sáng, trên nền tối)
INK_2    = "#8FA3C4"   # chữ phụ sáng vừa
PAPER    = "#080B14"   # NỀN TRANG — xanh đen sâu
CARD     = "#111726"   # nền thẻ / nền biểu đồ
RULE     = "#212B42"   # viền mảnh
RULE_STR = "#2E3B57"   # viền đậm hơn
BRASS    = "#F97C1B"   # CAM GHN phát sáng — nhấn thương hiệu
BRASS_DP = "#FFA24D"   # cam sáng hơn cho chữ trên nền tối
FOREST   = "#2DD48F"   # xanh lá neon — số dương
BURGUNDY = "#FF5470"   # đỏ hồng neon — số âm
SLATE    = "#7D8DAA"   # chữ mờ

# Màu phụ cho biểu đồ nhiều chuỗi (lấy tinh thần neon của ảnh mẫu)
CYAN     = "#22D3EE"
BLUE     = "#3B82F6"   # xanh da trời GHN
VIOLET   = "#A78BFA"
AMBER    = "#FBBF24"
PINK     = "#F472B6"

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

NOTES = ["Tổng quan", "Vận hành", "Kinh doanh",
         "Năng suất & Lương", "Tiến độ KPI", "AI cố vấn"]
ROLE_NOTES = {"admin": NOTES, "manager": NOTES,
              "staff": ["Tổng quan", "Vận hành", "Năng suất & Lương"]}

# ════════════════════════════════════════════════════════════════════
# HỆ THIẾT KẾ
# ════════════════════════════════════════════════════════════════════
pio.templates["report"] = go.layout.Template(layout=dict(
    font=dict(family="Inter, sans-serif", size=12, color=SLATE),
    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", hovermode="x unified",
    colorway=[CYAN, BRASS, VIOLET, FOREST, AMBER, PINK, BLUE],
    margin=dict(l=46, r=16, t=16, b=36),
    xaxis=dict(showgrid=False, linecolor=RULE, linewidth=1, ticks="outside",
               tickcolor=RULE, ticklen=4, tickfont=dict(size=10.5, color=SLATE)),
    yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,.06)", gridwidth=1, zeroline=False,
               tickfont=dict(size=10.5, color=SLATE)),
    legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0,
                font=dict(size=10.5, color=INK_2)),
    hoverlabel=dict(bgcolor="#1A2236", bordercolor=RULE_STR,
                    font=dict(family="Inter", size=12, color=INK)),
))
pio.templates.default = "report"

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

:root {{
  --ink:{INK}; --ink2:{INK_2}; --paper:{PAPER}; --card:{CARD};
  --rule:{RULE}; --rules:{RULE_STR}; --brass:{BRASS}; --brassd:{BRASS_DP};
  --forest:{FOREST}; --burg:{BURGUNDY}; --slate:{SLATE};
  --cyan:{CYAN}; --blue:{BLUE}; --violet:{VIOLET}; --amber:{AMBER}; --pink:{PINK};
}}

/* nền tối có quầng sáng nhẹ ở góc, như ảnh mẫu */
.stApp {{
  background:
    radial-gradient(1200px 620px at 12% -8%, rgba(59,130,246,.13), transparent 62%),
    radial-gradient(1000px 560px at 88% 4%, rgba(249,124,27,.10), transparent 60%),
    {PAPER};
  color:{INK};
}}
html, body, [class*="css"] {{ font-family:'Inter',sans-serif; color:{INK}; }}
.block-container {{ padding-top:1.1rem; padding-bottom:3rem; max-width:1560px; }}
#MainMenu, footer, header {{ visibility:hidden; }}
h1,h2,h3,h4 {{ font-family:'Inter',sans-serif; color:{INK}; }}

/* ── thanh trên cùng ─────────────────────────────────────────────── */
.topbar {{
  display:flex; justify-content:space-between; align-items:center; gap:14px;
  background:linear-gradient(180deg, rgba(28,38,60,.92), rgba(17,23,38,.92));
  border:1px solid {RULE}; border-radius:14px; padding:14px 20px; margin-bottom:14px;
  box-shadow:0 8px 30px rgba(0,0,0,.42);
}}
.topbar .tt {{ font-size:16px; font-weight:700; letter-spacing:.02em; color:{INK}; }}
.topbar .ts {{
  font-family:'JetBrains Mono',monospace; font-size:10.5px; letter-spacing:.12em;
  text-transform:uppercase; color:{SLATE}; margin-top:3px;
}}
.topbar .meta {{ text-align:right; font-family:'JetBrains Mono',monospace; font-size:10.5px;
  letter-spacing:.1em; text-transform:uppercase; color:{SLATE}; line-height:1.8; }}
.topbar .meta b {{ color:{CYAN}; font-weight:600; }}

/* ── thẻ số liệu lớn ─────────────────────────────────────────────── */
.hl-row {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(184px,1fr)); gap:12px; margin:14px 0; }}
.hl {{
  position:relative; background:linear-gradient(165deg, rgba(34,45,70,.72), rgba(17,23,38,.92));
  border:1px solid {RULE}; border-radius:14px; padding:16px 18px 15px; overflow:hidden;
}}
.hl::after {{
  content:''; position:absolute; left:0; right:0; top:0; height:2px;
  background:linear-gradient(90deg,{CYAN},{BLUE},transparent);
  opacity:.85;
}}
.hl .cap {{
  font-family:'JetBrains Mono',monospace; font-size:9.5px; letter-spacing:.14em;
  text-transform:uppercase; color:{SLATE}; margin-bottom:9px;
}}
.hl .num {{
  font-size:33px; font-weight:700; color:{INK}; line-height:1;
  font-variant-numeric:tabular-nums; letter-spacing:-.02em;
  text-shadow:0 0 22px rgba(34,211,238,.30);
}}
.hl .num small {{ font-size:13px; font-weight:500; color:{SLATE}; text-shadow:none; margin-left:2px; }}
.hl .delta {{
  font-family:'JetBrains Mono',monospace; font-size:11px; margin-top:9px;
  font-variant-numeric:tabular-nums; font-weight:500;
}}
.d-up {{ color:{FOREST}; }} .d-down {{ color:{BURGUNDY}; }} .d-flat {{ color:{SLATE}; }}

/* ── panel bọc biểu đồ ───────────────────────────────────────────── */
.panel {{
  background:linear-gradient(165deg, rgba(28,38,60,.55), rgba(17,23,38,.88));
  border:1px solid {RULE}; border-radius:14px; padding:14px 16px 6px; margin-bottom:12px;
}}

/* ── đầu mục ─────────────────────────────────────────────────────── */
.note-head {{ position:relative; margin:26px 0 14px; padding-bottom:11px;
  border-bottom:1px solid {RULE}; overflow:hidden; }}
.note-head .ghost {{
  position:absolute; right:0; top:-26px; font-size:96px; font-weight:800;
  color:{CYAN}; opacity:.055; line-height:1; user-select:none; pointer-events:none;
}}
.note-head .eyebrow {{
  font-family:'JetBrains Mono',monospace; font-size:10px; letter-spacing:.16em;
  text-transform:uppercase; color:{BRASS_DP}; font-weight:600; margin-bottom:4px;
}}
.note-head h2 {{ font-size:24px; font-weight:700; color:{INK}; margin:0; letter-spacing:-.01em; }}
.note-head .sub {{ font-size:12px; color:{SLATE}; margin-top:4px; }}

.sub-head {{
  font-size:13px; font-weight:600; color:{INK}; margin:22px 0 8px;
  padding-left:11px; border-left:3px solid {BRASS}; letter-spacing:.01em;
}}
.fig-cap {{
  font-family:'JetBrains Mono',monospace; font-size:9.5px; letter-spacing:.12em;
  text-transform:uppercase; color:{SLATE}; margin:12px 0 -4px;
}}

/* ── thư điều hành / khối AI ─────────────────────────────────────── */
.letter {{
  background:linear-gradient(165deg, rgba(28,38,60,.6), rgba(17,23,38,.9));
  border:1px solid {RULE}; border-left:3px solid {BRASS};
  border-radius:14px; padding:20px 24px; margin:14px 0;
}}
.letter .kicker {{
  font-family:'JetBrains Mono',monospace; font-size:10px; letter-spacing:.16em;
  text-transform:uppercase; color:{BRASS_DP}; font-weight:600; margin-bottom:10px;
}}
.letter p {{ font-size:14.5px; line-height:1.8; color:{INK}; margin:0; }}
.letter .dropcap {{
  float:left; font-size:44px; font-weight:800; line-height:.85;
  padding:3px 10px 0 0; color:{BRASS}; text-shadow:0 0 24px rgba(249,124,27,.4);
}}
.letter .sign {{
  text-align:right; margin-top:12px; font-family:'JetBrains Mono',monospace;
  font-size:10px; letter-spacing:.1em; color:{SLATE}; text-transform:uppercase;
}}

/* ── điểm cần lưu ý ──────────────────────────────────────────────── */
.notice {{
  background:linear-gradient(165deg, rgba(28,38,60,.6), rgba(17,23,38,.9));
  border:1px solid {RULE}; border-radius:14px; padding:16px 20px; margin:14px 0;
}}
.notice .cap {{
  font-family:'JetBrains Mono',monospace; font-size:10px; letter-spacing:.16em;
  text-transform:uppercase; color:{BRASS_DP}; font-weight:600; margin-bottom:11px;
}}
.notice ol {{ margin:0; padding-left:19px; }}
.notice li {{ font-size:13px; line-height:1.8; color:{INK}; margin-bottom:8px; }}
.notice li:last-child {{ margin-bottom:0; }}
.notice li b {{ font-variant-numeric:tabular-nums; font-weight:700; color:{CYAN}; }}
.notice li .tag {{
  font-family:'JetBrains Mono',monospace; font-size:9px; letter-spacing:.1em;
  text-transform:uppercase; padding:2px 8px; border-radius:999px; margin-right:8px; font-weight:600;
}}
.tag-high {{ background:rgba(255,84,112,.14); color:{BURGUNDY}; border:1px solid rgba(255,84,112,.32); }}
.tag-mid  {{ background:rgba(251,191,36,.13); color:{AMBER};    border:1px solid rgba(251,191,36,.3); }}
.tag-ok   {{ background:rgba(45,212,143,.13); color:{FOREST};   border:1px solid rgba(45,212,143,.3); }}

/* ── bảng ────────────────────────────────────────────────────────── */
table.ledger {{ width:100%; border-collapse:collapse; margin:10px 0 4px; font-size:12.5px; }}
table.ledger caption {{
  text-align:left; font-family:'JetBrains Mono',monospace; font-size:9.5px; letter-spacing:.12em;
  text-transform:uppercase; color:{SLATE}; padding-bottom:9px; caption-side:top;
}}
table.ledger th {{
  text-align:right; font-family:'JetBrains Mono',monospace; font-weight:500; font-size:9.5px;
  letter-spacing:.1em; text-transform:uppercase; color:{SLATE};
  padding:0 0 9px; border-bottom:1px solid {RULE_STR};
}}
table.ledger th:first-child, table.ledger td:first-child {{ text-align:left; }}
table.ledger td {{
  text-align:right; padding:9px 0; border-bottom:1px solid rgba(255,255,255,.045);
  font-variant-numeric:tabular-nums; color:{INK};
}}
table.ledger tr.total td {{
  border-top:1px solid {RULE_STR}; border-bottom:none;
  font-weight:700; color:{CYAN}; padding-top:11px;
}}
table.ledger td.up {{ color:{FOREST}; }} table.ledger td.down {{ color:{BURGUNDY}; }}
table.ledger td.name {{ font-variant-numeric:normal; color:{INK_2}; }}
table.ledger td span.up {{ color:{FOREST}; }} table.ledger td span.down {{ color:{BURGUNDY}; }}

.empty {{
  background:rgba(17,23,38,.6); border:1px dashed {RULE_STR}; border-radius:12px;
  padding:22px; text-align:center; color:{SLATE}; font-size:12.5px; margin:12px 0; line-height:1.7;
}}

/* ── thanh bên ───────────────────────────────────────────────────── */
section[data-testid="stSidebar"] {{
  background:linear-gradient(180deg, #0D1220, #0A0E1A);
  border-right:1px solid {RULE};
}}
section[data-testid="stSidebar"] .block-container {{ padding-top:1.2rem; }}
.toc-label {{
  font-family:'JetBrains Mono',monospace; font-size:9.5px; letter-spacing:.18em;
  text-transform:uppercase; color:{SLATE}; font-weight:600; margin:4px 0 10px;
}}
section[data-testid="stSidebar"] [role="radiogroup"] label {{
  font-size:12.5px !important; padding:8px 10px; border-radius:9px;
  border:1px solid transparent; margin-bottom:2px; color:{INK_2} !important;
}}
section[data-testid="stSidebar"] [role="radiogroup"] label:hover {{ background:rgba(255,255,255,.035); }}
section[data-testid="stSidebar"] [role="radiogroup"] label[data-checked="true"] {{
  color:{INK} !important; background:rgba(59,130,246,.14);
  border-color:rgba(59,130,246,.34); font-weight:600;
}}

/* ── điều khiển Streamlit ────────────────────────────────────────── */
.stButton>button {{
  border-radius:10px; border:1px solid {RULE_STR}; background:rgba(255,255,255,.035);
  color:{INK}; font-size:11.5px; letter-spacing:.05em; text-transform:uppercase;
  font-weight:600; padding:.52rem 1.05rem;
}}
.stButton>button:hover {{ border-color:{CYAN}; color:{CYAN}; background:rgba(34,211,238,.09); }}
.stButton>button[kind="primary"] {{
  background:linear-gradient(135deg,{BLUE},{CYAN}); color:#04121C;
  border:none; font-weight:700;
}}
.stButton>button[kind="primary"]:hover {{ filter:brightness(1.12); color:#04121C; }}

label, .stSelectbox label, .stRadio label, .stDateInput label,
.stMultiSelect label, .stNumberInput label, .stTextArea label {{
  font-family:'JetBrains Mono',monospace !important; font-size:9.5px !important;
  letter-spacing:.14em !important; text-transform:uppercase; color:{SLATE} !important;
}}
div[data-baseweb="select"]>div, div[data-baseweb="input"]>div, .stTextArea textarea {{
  border-radius:10px !important; border-color:{RULE} !important;
  background:rgba(255,255,255,.035) !important; color:{INK} !important;
}}
div[data-testid="stDataFrame"] {{ border:1px solid {RULE}; border-radius:12px; overflow:hidden; }}
div[data-testid="stExpander"] {{ border:1px solid {RULE}; border-radius:12px; background:rgba(17,23,38,.55); }}
[data-testid="stChatMessage"] {{ background:rgba(17,23,38,.7); border:1px solid {RULE}; border-radius:12px; }}
hr {{ border-color:{RULE}; }}
.stAlert {{ border-radius:12px; }}

@media (max-width:640px) {{
  .hl-row {{ grid-template-columns:repeat(2,1fr); }}
  .hl .num {{ font-size:26px; }}
  .note-head .ghost {{ font-size:62px; top:-12px; }}
  .topbar {{ flex-direction:column; align-items:flex-start; }}
  .topbar .meta {{ text-align:left; }}
}}
@media (prefers-reduced-motion:reduce) {{ * {{ animation:none !important; transition:none !important; }} }}
</style>
""", unsafe_allow_html=True)


def esc(x) -> str:
    return html_lib.escape(str(x))


def note_head(no: str, title: str, sub: str = ""):
    st.markdown(f"<div class='note-head'><div class='ghost'>{no}</div>"
                f"<div class='eyebrow'>Phần {no}</div><h2>{title}</h2>"
                f"<div class='sub'>{sub}</div></div>", unsafe_allow_html=True)


def sub_head(title: str):
    st.markdown(f"<div class='sub-head'>{title}</div>", unsafe_allow_html=True)


def fig_cap(text: str):
    st.markdown(f"<div class='fig-cap'>{text}</div>", unsafe_allow_html=True)


def empty(msg: str):
    st.markdown(f"<div class='empty'>{msg}</div>", unsafe_allow_html=True)


def fmt_num(v: float, unit: str) -> str:
    if unit == "%":
        return f"{v:,.2f}%"
    if unit == "đ":
        return f"{v/1_000_000:,.1f} tr đ"
    if unit == "đơn":
        return f"{v:,.0f} đơn"
    return f"{v:,.0f}"



def ledger_table(caption: str, headers: list[str], rows: list[list],
                 total_row: list | None = None, aligns: list[str] | None = None) -> str:
    """Bảng kiểu sổ cái: cột đầu căn trái, còn lại căn phải, dòng tổng gạch đôi."""
    th = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = ""
    for r in rows:
        cells = f"<td class='name'>{esc(r[0])}</td>" + "".join(f"<td>{c}</td>" for c in r[1:])
        body += f"<tr>{cells}</tr>"
    if total_row:
        cells = f"<td class='name'>{esc(total_row[0])}</td>" + "".join(f"<td>{c}</td>" for c in total_row[1:])
        body += f"<tr class='total'>{cells}</tr>"
    return (f"<table class='ledger'><caption>{esc(caption)}</caption>"
            f"<thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>")


def sized(fig, height=250):
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
    _, mid, _ = st.columns([1, 1.15, 1])
    with mid:
        st.write("")
        # Logo GHN gốc có nền trắng — đặt trên tấm trắng bo góc để giữ nguyên bản,
        # không bị lọt thỏm giữa nền tối.
        st.markdown("<div style='background:#fff;border-radius:12px;padding:14px 18px;"
                    "display:inline-block;margin-bottom:16px;'>", unsafe_allow_html=True)
        if LOGO.exists():
            st.image(str(LOGO), width=210)
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown(
            "<div style='font-family:JetBrains Mono,monospace;font-size:10px;letter-spacing:.18em;"
            "text-transform:uppercase;color:var(--brassd);font-weight:600;'>Trung tâm vận hành chiến lược</div>"
            "<h2 style='font-size:27px;font-weight:700;margin:6px 0 20px;letter-spacing:-.01em;'>"
            "Cổng truy cập báo cáo</h2>",
            unsafe_allow_html=True)
        if not USERS:
            st.error("Chưa có tài khoản nào. Đặt biến môi trường APP_USER và APP_PASS trên máy chủ, "
                     "rồi khởi động lại dịch vụ.")
            st.stop()
        with st.form("login"):
            uid = st.text_input("ID nhân viên")
            pwd = st.text_input("Mật khẩu", type="password")
            if st.form_submit_button("Vào báo cáo", use_container_width=True, type="primary"):
                info = USERS.get(uid.strip())
                if info and str(info.get("password")) == pwd:
                    st.session_state.auth = {"id": uid.strip(), "ten": info.get("ten", uid.strip()),
                                             "role": info.get("role", "staff"),
                                             "buu_cuc": info.get("buu_cuc", ["Tất cả"])}
                    st.rerun()
                else:
                    st.error("ID hoặc mật khẩu không khớp. Kiểm tra lại hoặc hỏi quản trị viên khu vực.")
        st.markdown("<div style='font-size:11px;color:var(--slate);margin-top:12px;'>"
                    "Mỗi tài khoản chỉ thấy bưu cục được phân quyền.</div>", unsafe_allow_html=True)
    st.stop()

AUTH = st.session_state.auth
ALLOWED_BC = AUTH.get("buu_cuc", ["Tất cả"])
IS_ALL_BC = "Tất cả" in ALLOWED_BC

# ════════════════════════════════════════════════════════════════════
# LỚP DỮ LIỆU (không đổi so với bản trước — đã kiểm chứng)
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


def date_pick(label, default_a, default_b, key):
    p = st.date_input(label, [default_a, default_b], key=key)
    if isinstance(p, (list, tuple)) and len(p) >= 2:
        return pd.to_datetime(p[0]), pd.to_datetime(p[1])
    if isinstance(p, (list, tuple)) and len(p) == 1:
        return pd.to_datetime(p[0]), pd.to_datetime(p[0])
    return pd.to_datetime(default_a), pd.to_datetime(default_b)


# ════════════════════════════════════════════════════════════════════
# BẢNG SỔ CÁI THEO KỲ (dùng chung cho mọi chỉ số vận hành)
# ════════════════════════════════════════════════════════════════════
def period_ledger(caption: str, frame: pd.DataFrame, ref: pd.Timestamp,
                  how="wavg", unit="%", higher_is_better=True) -> str:
    rows = []
    for mode in ["Ngày", "Tuần", "Tháng"]:
        (a, b), (pa, pb) = period_pair(ref, mode)
        now, prev = val(frame, a, b, how), val(frame, pa, pb, how)
        delta = now - prev
        good = (delta > 0) == higher_is_better
        cls = "" if abs(delta) < 1e-9 else ("up" if good else "down")
        arrow = "" if abs(delta) < 1e-9 else ("▲" if delta > 0 else "▼")
        d_txt = (f"{arrow} {abs(delta):,.2f} pp" if unit == "%" else
                 f"{arrow} {abs(delta)/1_000_000:,.1f} tr đ" if unit == "đ" else
                 f"{arrow} {abs(delta):,.0f}")
        rows.append([mode, fmt_num(now, unit), fmt_num(prev, unit), f"<span class='{cls}'>{d_txt}</span>"])
    return ledger_table(caption, ["Kỳ", "Kỳ này", "Kỳ trước", "Chênh lệch"], rows)


def highlight(cap: str, value: float, delta: float | None, unit="%", higher_is_better=True) -> str:
    if delta is None:
        d_html = "<div class='delta d-flat'>&nbsp;</div>"
    else:
        good = (delta > 0) == higher_is_better
        cls = "d-flat" if abs(delta) < 1e-9 else ("d-up" if good else "d-down")
        arrow = "" if abs(delta) < 1e-9 else ("▲" if delta > 0 else "▼")
        txt = (f"{arrow} {abs(delta):,.2f} pp" if unit == "%" else
               f"{arrow} {abs(delta)/1_000_000:,.1f} tr đ" if unit == "đ" else
               f"{arrow} {abs(delta):,.0f}")
        d_html = f"<div class='delta {cls}'>{txt}</div>"
    return f"<div class='hl'><div class='cap'>{esc(cap)}</div><div class='num'>{fmt_num(value, unit)}</div>{d_html}</div>"


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
    "Giám đốc": "Viết như giám đốc vận hành: đánh giá vĩ mô, nêu rủi ro hệ thống, đề xuất chiến lược. Giọng văn bản báo cáo chính thức, chuyên nghiệp.",
    "Quản lý khu vực": "Viết như AM khu vực: chỉ đích danh điểm nóng, giao việc cụ thể cho bưu cục và nhân viên. Dứt khoát, thực chiến.",
    "Nhân viên": 'Viết như trợ lý điều phối nhắn cho anh em. Xưng "Mình" với "Anh em", ngắn gọn, tạo động lực.',
}
CLOSE = "Viết súc tích, chia ý rõ ràng, không bỏ dở câu. Kết thúc bằng dòng [HẾT]."


ROLE_DEFAULT_VOICE = {"admin": "Giám đốc", "manager": "Quản lý khu vực", "staff": "Nhân viên"}


def ai_panel(key: str, label: str, build_prompt, tab: str):
    voices = list(ROLE_STYLE)
    default_voice = ROLE_DEFAULT_VOICE.get(AUTH.get("role", "staff"), "Quản lý khu vực")
    c1, c2 = st.columns([1, 2.4])
    with c1:
        role = st.selectbox("Viết cho ai", voices,
                            index=voices.index(default_voice) if default_voice in voices else 0,
                            key=f"r_{key}")
    with c2:
        st.markdown("<div style='height:26px'></div>", unsafe_allow_html=True)
        if st.button(label, type="primary", key=f"b_{key}", use_container_width=True):
            with st.spinner("Đang đọc số liệu..."):
                st.session_state.ai[key] = ask_ai(build_prompt(role))
    txt = st.session_state.ai.get(key)
    if txt:
        st.markdown(f"<div class='letter'><div class='kicker'>Nhận định — {esc(tab)}</div>"
                    f"<p style='font-style:normal;font-family:Public Sans;font-size:14px;"
                    f"line-height:1.75;'>{txt}</p></div>", unsafe_allow_html=True)
        if st.button("Gửi lên nhóm Telegram", key=f"t_{key}"):
            ok, msg = send_telegram(f"[{tab.upper()}]\n\n" + txt.replace("*", ""))
            (st.success if ok else st.error)(msg)
    else:
        empty("Bấm nút phía trên để AI đọc đúng số liệu đang hiển thị và viết nhận định.")


# ════════════════════════════════════════════════════════════════════
# NẠP DỮ LIỆU
# ════════════════════════════════════════════════════════════════════
with st.spinner("Đang tổng hợp số liệu cho báo cáo..."):
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

# Ngày mới nhất thực sự có trong dữ liệu — dùng làm mặc định cho bộ lọc toàn cục.
REF_DATA = max([f["Ngày"].max() for f in (M_GTC, M_DT, DF_NSGTC)
                if f is not None and not f.empty and f["Ngày"].notna().any()]
               or [pd.Timestamp.today().normalize()])
DATA_MIN = min([f["Ngày"].min() for f in (M_GTC, M_DT, DF_NSGTC)
                if f is not None and not f.empty and f["Ngày"].notna().any()]
               or [REF_DATA - timedelta(days=90)])


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


# ════════════════════════════════════════════════════════════════════
# THANH BÊN — MỤC LỤC
# ════════════════════════════════════════════════════════════════════
with st.sidebar:
    if LOGO.exists():
        st.markdown("<div style='background:#fff;border-radius:10px;padding:9px 12px;"
                    "margin-bottom:4px;'>", unsafe_allow_html=True)
        st.image(str(LOGO), width=150)
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown(f"<div style='font-size:11px;color:var(--slate);margin:10px 0 18px;line-height:1.6;'>"
                f"{esc(AUTH['ten'])} · {esc(AUTH['role'])}<br>{esc(' / '.join(ALLOWED_BC))}</div>",
                unsafe_allow_html=True)
    st.markdown("<div class='toc-label'>Mục lục</div>", unsafe_allow_html=True)
    notes = ROLE_NOTES.get(AUTH["role"], ROLE_NOTES["staff"])
    page = st.radio("Mục lục", notes, label_visibility="collapsed")

    # ── Bộ lọc toàn cục: chọn một lần, mọi ghi chú cùng theo ──────────
    st.markdown("<div class='toc-label' style='margin-top:18px;'>Bộ lọc toàn cục</div>",
                unsafe_allow_html=True)
    g_ref = st.date_input("Ngày phân tích", value=REF_DATA.date(),
                          min_value=DATA_MIN.date(), max_value=REF_DATA.date(), key="g_ref")
    REF = pd.to_datetime(g_ref)
    st.selectbox("Bưu cục", ALL_BC, key="g_bc")
    if REF != REF_DATA:
        st.markdown(f"<div style='font-size:10.5px;color:var(--brassd);margin-top:-6px;'>"
                    f"Đang xem lùi so với ngày mới nhất ({REF_DATA:%d.%m}).</div>",
                    unsafe_allow_html=True)

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    if st.button("Cập nhật số liệu", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    if st.button("Thoát", use_container_width=True):
        st.session_state.auth = None
        st.rerun()
    st.markdown(f"<div style='font-size:10.5px;color:var(--slate);margin-top:16px;line-height:1.6;'>"
                f"Số liệu đến {REF_DATA:%d.%m.%Y}<br>Tổng hợp lúc {datetime.now():%H:%M}</div>",
                unsafe_allow_html=True)
    errs = st.session_state.get("errs", {})
    if errs:
        st.markdown(f"<div style='font-size:10.5px;color:var(--burg);margin-top:8px;'>"
                    f"{len(errs)} nguồn chưa đọc được: {esc(', '.join(errs))}</div>", unsafe_allow_html=True)

def page_scope(key: str, label: str = "Phạm vi") -> str:
    """Ô chọn bưu cục của trang, mặc định lấy theo bộ lọc toàn cục ở sidebar.
    Người dùng vẫn đổi riêng cho trang này được mà không ảnh hưởng trang khác."""
    g = st.session_state.get("g_bc", "Tất cả")
    idx = ALL_BC.index(g) if g in ALL_BC else 0
    return st.selectbox(label, ALL_BC, index=idx, key=key)


# ── thanh trên cùng, hiện ở mọi trang ────────────────────────────────
_scope_txt = st.session_state.get("g_bc", "Tất cả")
st.markdown(f"""<div class="topbar">
  <div>
    <div class="tt">TRUNG TÂM VẬN HÀNH CHIẾN LƯỢC · GHN</div>
    <div class="ts">{esc(page)} &nbsp;·&nbsp; phạm vi {esc(_scope_txt)}</div>
  </div>
  <div class="meta">
    Ngày phân tích <b>{REF:%d.%m.%Y}</b><br>
    Dữ liệu đến <b>{REF_DATA:%d.%m.%Y}</b> &nbsp;·&nbsp; đồng bộ <b>{datetime.now():%H:%M}</b>
  </div>
</div>""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════
# TRANG BÌA
# ════════════════════════════════════════════════════════════════════
if page == "Tổng quan":
    bc = page_scope("bc_home", "Phạm vi báo cáo")
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
    p_gtc, p_tts = val(g_gtc, pA, pB), val(g_tts, pA, pB)
    p_odr, p_tra = val(g_odr, pA, pB), val(g_tra, pA, pB)
    v_dt = val(g_dt, mA, mB, "sum")

    st.markdown("<div class='letter'><div class='kicker'>Thư điều hành</div>"
                f"<p><span class='dropcap'>{'K' if v_gtc >= t_gtc else 'T'}</span>"
                f"{'ết quả vận hành khu vực ' + esc(bc) + ' đang bám sát mục tiêu đề ra' if v_gtc >= t_gtc else 'ỷ lệ giao thành công tại khu vực ' + esc(bc) + ' đang thấp hơn mục tiêu đề ra'}, "
                f"đạt {v_gtc:,.2f}% trên tổng sản lượng ngày {REF:%d/%m}, so với mốc {t_gtc:,.2f}%. "
                f"Doanh thu lũy kế tháng {mA:%m/%Y} ghi nhận {v_dt/1_000_000:,.1f} triệu đồng. "
                f"Báo cáo chi tiết theo từng mục được trình bày ở các ghi chú kèm theo.</p>"
                f"<div class='sign'>Tổng hợp tự động · {datetime.now():%d/%m/%Y %H:%M}</div></div>",
                unsafe_allow_html=True)

    highlights = "".join([
        highlight("GTC tổng", v_gtc, v_gtc - p_gtc, "%"),
        highlight("GTC TikTok", v_tts, v_tts - p_tts, "%"),
        highlight("ODR TikTok", v_odr, v_odr - p_odr, "%"),
        highlight("Trả hàng", v_tra, v_tra - p_tra, "%", higher_is_better=False),
        highlight("Doanh thu tháng", v_dt, None, "đ"),
    ])
    st.markdown(f"<div class='hl-row'>{highlights}</div>", unsafe_allow_html=True)

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

    items = ""
    if issues:
        for sev, name, v, t, unit, why, gap in issues:
            tag = "tag-high" if sev > .05 else "tag-mid"
            label = "Cần xử lý" if sev > .05 else "Theo dõi"
            if unit == "%":
                txt = (f"<b>{esc(name)}</b> đạt <b>{v:,.2f}%</b>, thấp hơn mốc <b>{t:,.2f}%</b> — "
                       f"thiếu <b>{abs(gap):,.2f}</b> điểm phần trăm. {why.capitalize()}.")
            else:
                txt = (f"<b>{esc(name)}</b> đạt <b>{v/1_000_000:,.1f} tr đ</b>, thấp hơn mốc "
                       f"<b>{t/1_000_000:,.0f} tr đ</b> — thiếu <b>{abs(gap)/1_000_000:,.1f} tr đ</b>. {why.capitalize()}.")
            items += f"<li><span class='tag {tag}'>{label}</span>{txt}</li>"
    else:
        items = "<li><span class='tag tag-ok'>Đạt mốc</span>Toàn bộ chỉ số đang bám sát hoặc vượt mục tiêu đề ra.</li>"

    st.markdown(f"<div class='notice'><div class='cap'>Điểm cần lưu ý</div><ol>{items}</ol></div>",
                unsafe_allow_html=True)

    # ── Xếp hạng bưu cục + xu hướng 30 ngày ──────────────────────────
    r1, r2 = st.columns([1, 1.25])
    with r1:
        sub_head("Xếp hạng bưu cục theo %GTC")
        rank_src = sl(scope(M_GTC, "Tất cả" if bc == "Tất cả" else bc), *period_pair(REF, "Tháng")[0])
        if not rank_src.empty:
            rk = (rank_src.assign(_p=rank_src["Giá Trị"].fillna(0) * rank_src["Trọng Số"])
                  .groupby("Bưu Cục", as_index=False)
                  .agg(_p=("_p", "sum"), w=("Trọng Số", "sum")))
            rk = rk[rk["w"] > 0]
            rk["%GTC"] = rk["_p"] / rk["w"]
            rk = rk.sort_values("%GTC").tail(12)
            colors = [BURGUNDY if v < t_gtc else (AMBER if v < t_gtc * 1.05 else FOREST)
                      for v in rk["%GTC"]]
            fig = go.Figure(go.Bar(
                x=rk["%GTC"], y=rk["Bưu Cục"], orientation="h",
                marker=dict(color=colors, line=dict(width=0)),
                text=[f"{v:,.1f}%" for v in rk["%GTC"]], textposition="outside",
                textfont=dict(size=10, color=INK_2),
                customdata=rk["w"],
                hovertemplate="%{y}<br>%GTC %{x:.2f}%<br>Sản lượng %{customdata:,.0f} đơn<extra></extra>"))
            fig.add_vline(x=t_gtc, line_dash="dot", line_color=CYAN, line_width=1.5)
            fig.update_layout(height=max(260, 26 * len(rk)), hovermode="closest",
                              margin=dict(l=6, r=44, t=8, b=28))
            fig.update_xaxes(ticksuffix="%", showgrid=True, gridcolor="rgba(255,255,255,.05)")
            fig.update_yaxes(showgrid=False, tickfont=dict(size=10.5))
            st.plotly_chart(fig, use_container_width=True)
            st.markdown(f"<div class='fig-cap'>Lũy kế tháng · đường xanh là mốc {t_gtc:,.1f}%</div>",
                        unsafe_allow_html=True)
        else:
            empty("Chưa có dữ liệu GTC theo bưu cục trong tháng này.")

    with r2:
        sub_head("Xu hướng 30 ngày")
        trend = daily(sl(g_gtc, REF - timedelta(days=29), REF))
        trend_tra = daily(sl(g_tra, REF - timedelta(days=29), REF))
        if not trend.empty:
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            fig.add_trace(go.Bar(x=trend["Ngày"], y=trend["Trọng Số"], name="Sản lượng",
                                 marker_color="rgba(59,130,246,.30)", marker_line_width=0),
                          secondary_y=False)
            fig.add_trace(go.Scatter(x=trend["Ngày"], y=trend["Giá Trị"], name="%GTC",
                                     mode="lines", line=dict(color=CYAN, width=2.4),
                                     fill="tozeroy", fillcolor="rgba(34,211,238,.08)"),
                          secondary_y=True)
            if not trend_tra.empty:
                fig.add_trace(go.Scatter(x=trend_tra["Ngày"], y=trend_tra["Giá Trị"],
                                         name="%Trả hàng", mode="lines",
                                         line=dict(color=BRASS, width=1.8, dash="dot")),
                              secondary_y=True)
            fig.add_hline(y=t_gtc, line_dash="dot", line_color="rgba(255,255,255,.28)",
                          line_width=1, secondary_y=True)
            fig.update_yaxes(showgrid=False, secondary_y=False)
            fig.update_yaxes(ticksuffix="%", secondary_y=True)
            fig.update_layout(height=340, margin=dict(l=44, r=44, t=26, b=30))
            st.plotly_chart(fig, use_container_width=True)
            st.markdown("<div class='fig-cap'>Cột là sản lượng · đường sáng là %GTC · "
                        "đường cam đứt là tỷ lệ trả hàng</div>", unsafe_allow_html=True)
        else:
            empty("Chưa có dữ liệu 30 ngày gần nhất.")

    sub_head("Tin nhắn nhóm và tác phong")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("<div style='font-size:11px;color:var(--slate);margin-bottom:6px;'>"
                    "Dán trực tiếp đoạn hội thoại Zalo hoặc Telegram vào đây. Nội dung chỉ dùng "
                    "cho lần phân tích này, không được lưu lại ở đâu.</div>", unsafe_allow_html=True)
        chat_paste = st.text_area("Nội dung nhóm cần AI đọc", height=150, key="chat_paste",
                                  placeholder="Dán đoạn chat vào đây...")
        if chat_paste.strip():
            st.markdown(f"<div style='font-size:11px;color:var(--forest);'>"
                        f"Đã nhận {len(chat_paste.strip().splitlines())} dòng — sẽ đưa vào phần "
                        f"nhận định bên dưới.</div>", unsafe_allow_html=True)
    with c2:
        if CHAT_LOG_CSV:
            try:
                df_chat = pd.read_csv(CHAT_LOG_CSV).tail(300)
                st.markdown(f"<div style='font-size:11px;color:var(--slate);'>"
                            f"Nguồn tự động: đã nạp {len(df_chat)} tin nhắn gần nhất.</div>",
                            unsafe_allow_html=True)
            except Exception as exc:  # noqa: BLE001
                df_chat = pd.DataFrame()
                empty(f"Không đọc được nguồn tin nhắn tự động: {exc}")
        else:
            df_chat = pd.DataFrame()
            empty("Chưa nối nguồn tin nhắn tự động. Đặt biến CHAT_LOG_CSV trỏ tới sheet có cột "
                  "Ngày, Nhóm, Người gửi, Nội dung nếu muốn AI đọc hằng ngày mà không phải dán tay.")
        empty("Tác phong & kỷ luật: thêm một sheet chấm công hoặc vi phạm vào SOURCES để mục này tự hiện.")

    def chat_context() -> str:
        parts = []
        if chat_paste.strip():
            parts.append("[Đoạn chat dán tay]\n" + chat_paste.strip()[:6000])
        if not df_chat.empty:
            parts.append("[Log tin nhắn tự động]\n" + df_chat.to_csv(index=False)[:6000])
        return "\n\n".join(parts) or "(chưa có dữ liệu tin nhắn)"

    def p_home(role):
        ctx = chat_context()
        return f"""Bạn là trợ lý điều hành khu vực GHN, viết cho một bản báo cáo chính thức. Ngày dữ liệu {REF:%d/%m/%Y}, phạm vi {bc}.
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

    sub_head("Nhận định điều hành")
    ai_panel("home", "Viết nhận định trang bìa", p_home, "Trang bìa")

# ════════════════════════════════════════════════════════════════════
# GHI CHÚ 01 · VẬN HÀNH
# ════════════════════════════════════════════════════════════════════
elif page == "Vận hành":
    c1, c2, c3, c4 = st.columns([1, 1.4, 1.15, 1.15])
    with c1:
        bc = page_scope("bc_vh")
    with c2:
        quick = st.radio("Khung thời gian", ["Ngày", "Tuần", "Tháng", "Tự chọn"], horizontal=True, key="q_vh")
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
    with c4:
        lh_all = (sorted({x for x in M_CA["Chiều"].dropna().astype(str).str.strip().unique()
                          if x and x.lower() != "nan"})
                  if "Chiều" in M_CA.columns else [])
        lh_pick = st.multiselect("Loại hàng / ca", lh_all, default=lh_all, key="lh_vh")

    note_head("01", "Vận hành", f"Phạm vi {bc} · dữ liệu {a0:%d.%m.%Y} – {b0:%d.%m.%Y}"
                                + (f" · {len(lh_pick)}/{len(lh_all)} loại hàng" if lh_all else ""))

    def S(frame):
        return sl(scope(frame, bc), a0, b0)

    s_gtc, s_tra, s_gtb, s_tts, s_odr, s_ca = (S(x) for x in (M_GTC, M_TRA, M_GTB, M_TTS, M_ODR, M_CA))

    # Chỉ sheet "sản lượng theo ca" mới có cột loại hàng, nên bộ lọc này áp cho khối 1.6.
    if lh_pick and "Chiều" in s_ca.columns:
        s_ca = s_ca[s_ca["Chiều"].isin(lh_pick)]
    if lh_all and len(lh_pick) < len(lh_all):
        st.markdown("<div class='fig-cap'>Bộ lọc loại hàng chỉ áp cho mục 1.6 — các sheet GTC, "
                    "trả hàng, GTB, TTS không có cột loại hàng</div>", unsafe_allow_html=True)

    for label, frame_full, frame_sc, unit, hib, color in [
        ("1.1 · GTC tổng", M_GTC, s_gtc, "%", True, INK),
        ("1.2 · Tỷ lệ trả hàng", M_TRA, s_tra, "%", False, BURGUNDY),
        ("1.3 · Tỷ lệ GTB thu tiền", M_GTB, s_gtb, "%", True, FOREST),
        ("1.4 · GTC TikTok Shop", M_TTS, s_tts, "%", True, BRASS_DP),
        ("1.5 · ODR TikTok Shop", M_ODR, s_odr, "%", True, INK_2),
    ]:
        sub_head(label)
        st.markdown(period_ledger(label, scope(frame_full, bc), REF, unit=unit, higher_is_better=hib),
                    unsafe_allow_html=True)
        if not frame_sc.empty:
            g = daily(frame_sc)
            fig = px.area(g, x="Ngày", y="Giá Trị")
            fig.update_traces(line=dict(color=color, width=1.8), fillcolor=f"rgba(0,0,0,0)")
            fig.update_yaxes(ticksuffix="%")
            st.plotly_chart(sized(fig, 210), use_container_width=True)
        else:
            empty(f"Chưa có dữ liệu cho {label.split('·')[1].strip()} trong khoảng đã chọn.")

    sub_head("1.6 · Sản lượng và GTC theo ca làm việc")
    if not s_ca.empty and "Chiều" in s_ca.columns:
        g = (s_ca.assign(_p=s_ca["Giá Trị"].fillna(0) * s_ca["Trọng Số"])
                 .groupby(["Ngày", "Chiều"], as_index=False)
                 .agg(_p=("_p", "sum"), w=("Trọng Số", "sum")))
        g["r"] = np.where(g["w"] > 0, g["_p"] / g["w"], np.nan)
        piv = g.pivot_table(index="Ngày", columns="Chiều", values="w", aggfunc="sum", fill_value=0)
        rows = []
        for ca in sorted(g["Chiều"].unique()):
            sub = g[g["Chiều"] == ca]
            total_sl = sub["w"].sum()
            avg_r = wavg(sub["r"], sub["w"])
            rows.append([ca, f"{total_sl:,.0f} đơn", f"{avg_r:,.2f}%"])
        st.markdown(ledger_table("Tổng theo ca trong kỳ", ["Ca / loại hàng", "Sản lượng", "%GTC bình quân"], rows),
                    unsafe_allow_html=True)
        fig = go.Figure()
        for i, ca in enumerate(sorted(g["Chiều"].unique())):
            sub = g[g["Chiều"] == ca]
            fig.add_trace(go.Scatter(x=sub["Ngày"], y=sub["r"], name=ca, mode="lines",
                                     line=dict(width=1.8, color=[INK, BRASS, FOREST][i % 3])))
        fig.update_yaxes(ticksuffix="%", range=[0, 100])
        st.plotly_chart(sized(fig, 220), use_container_width=True)
    else:
        empty("Chưa đọc được cột ca hoặc loại hàng trong sheet theo ca.")

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

    sub_head("Nhận định")
    ai_panel("vh", "Viết nhận định vận hành", p_vh, "Vận hành")

# ════════════════════════════════════════════════════════════════════
# GHI CHÚ 02 · KINH DOANH
# ════════════════════════════════════════════════════════════════════
elif page == "Kinh doanh":
    c1, c2, c3 = st.columns([1.1, 1.6, 1.3])
    with c1:
        bc = page_scope("bc_kd")
    with c2:
        view = st.radio("Gộp theo", ["Ngày", "Tuần", "Tháng"], horizontal=True, key="v_kd")
    lo = M_DT["Ngày"].min() if not M_DT.empty else REF - timedelta(days=60)
    with c3:
        a0, b0 = date_pick("Khoảng ngày", max(lo, REF - timedelta(days=29)), REF, "d_kd")

    note_head("02", "Kinh doanh", f"Phạm vi {bc} · dữ liệu {a0:%d.%m.%Y} – {b0:%d.%m.%Y}")

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

    sub_head("2.1 · Doanh thu so với mục tiêu tháng")
    rows_dt = [
        ["Lũy kế đến nay", f"{rev_m/1_000_000:,.1f} tr đ"],
        ["Mục tiêu tháng", f"{target/1_000_000:,.0f} tr đ"],
        ["Dự phóng cuối tháng", f"{forecast/1_000_000:,.1f} tr đ"],
        ["Tháng trước (cùng phạm vi)", f"{rev_pm/1_000_000:,.1f} tr đ"],
    ]
    st.markdown(ledger_table(f"Tháng {mA:%m/%Y} · đã qua {done_days}/{total_days} ngày",
                             ["Chỉ tiêu", "Giá trị"], rows_dt,
                             total_row=["Còn thiếu so với mục tiêu", f"{max(target-forecast,0)/1_000_000:,.1f} tr đ"]),
                unsafe_allow_html=True)

    sub_head("2.2 · Nhịp doanh thu theo kỳ")
    st.markdown(period_ledger("So với kỳ liền trước", dt, REF, how="sum", unit="đ"), unsafe_allow_html=True)

    sub_head(f"2.3 · Biểu đồ doanh thu — gộp theo {view.lower()}")
    d_range = sl(dt, a0, b0)
    if not d_range.empty:
        plot = d_range.copy()
        if view == "Tuần":
            plot["Ngày"] = plot["Ngày"].dt.to_period("W").apply(lambda r: r.start_time)
        elif view == "Tháng":
            plot["Ngày"] = plot["Ngày"].dt.to_period("M").apply(lambda r: r.start_time)
        plot = plot.groupby("Ngày", as_index=False)["Giá Trị"].sum()
        fig = px.bar(plot, x="Ngày", y="Giá Trị")
        fig.update_traces(marker_color=INK, marker_line_width=0, opacity=.85)
        if view == "Tháng":
            fig.add_hline(y=target, line_dash="dot", line_color=BRASS, line_width=1.5,
                          annotation_text="mục tiêu", annotation_position="top left")
        st.plotly_chart(sized(fig, 240), use_container_width=True)
    else:
        empty("Chưa có doanh thu trong khoảng đã chọn.")

    e1, e2 = st.columns([1.15, 1])
    with e1:
        sub_head("2.4 · Khách hàng mới trong kỳ")
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
                st.dataframe(t, use_container_width=True, hide_index=True, height=280,
                             column_config={rcol: st.column_config.NumberColumn("Doanh thu", format="%,d ₫")})
            else:
                st.dataframe(khm, use_container_width=True, hide_index=True, height=280)
        else:
            empty("Chưa có khách hàng mới trong kỳ này.")
    with e2:
        sub_head("2.5 · Phễu tiếp xúc khách hàng mới")
        pheu = scope(DF_PHEU, bc)
        if "Ngày" in pheu.columns and pheu["Ngày"].notna().any():
            pheu = sl(pheu, a0, b0)
        scol = pick_col(pheu, [["trang thai"]])
        if not pheu.empty and scol:
            cnt = pheu.groupby(scol).size().reset_index(name="n").sort_values("n", ascending=False)
            fig = go.Figure(go.Funnel(y=cnt[scol], x=cnt["n"], textinfo="value+percent initial",
                                      marker=dict(color=[INK, INK_2, SLATE, "#9AA2AE", "#C6CBD2"]),
                                      connector=dict(line=dict(color=RULE, width=1))))
            fig.update_layout(hovermode="closest", margin=dict(l=6, r=6, t=6, b=6))
            st.plotly_chart(sized(fig, 280), use_container_width=True)
        else:
            empty("Chưa đọc được cột trạng thái trong sheet phễu.")

    sub_head("2.6 · Khách hàng tiềm năng chờ chốt")
    if not pheu.empty and scol:
        tn = pheu[pheu[scol].astype(str).map(lambda x: "tiem nang" in norm(x))]
        if not tn.empty:
            drop = [c for c in tn.columns if tn[c].isna().all()]
            st.dataframe(tn.drop(columns=drop), use_container_width=True, hide_index=True)
        else:
            empty("Không có khách nào ở trạng thái tiềm năng.")
    else:
        empty("Cần cột trạng thái để lọc khách tiềm năng.")

    def p_kd(role):
        return f"""Kinh doanh GHN, phạm vi {bc}, tháng {mA:%m/%Y}.
Lũy kế {rev_m:,.0f} đ / mục tiêu {target:,.0f} đ. Dự phóng cuối tháng {forecast:,.0f} đ.
Đã qua {done_days}/{total_days} ngày. Tháng trước {rev_pm:,.0f} đ.

{ROLE_STYLE[role]}
Ba phần: tiến độ so với mục tiêu, phễu đang nghẽn ở đâu, việc chốt deal cần làm ngay.
{CLOSE}"""

    sub_head("Nhận định")
    ai_panel("kd", "Viết nhận định kinh doanh", p_kd, "Kinh doanh")

# ════════════════════════════════════════════════════════════════════
# GHI CHÚ 03 · NĂNG SUẤT & LƯƠNG
# ════════════════════════════════════════════════════════════════════
elif page == "Năng suất & Lương":
    c1, c2, c3 = st.columns([1.1, 1.3, 1.4])
    with c1:
        bc = page_scope("bc_ns")
    nv_l, nv_g = pick_col(DF_LUONG, [["nhan vien"]]), pick_col(DF_NSGTC, [["nhan vien"]])
    staff = set()
    for df, col in ((DF_LUONG, nv_l), (DF_NSGTC, nv_g)):
        if col and not df.empty:
            staff |= set(scope(df, bc)[col].dropna().astype(str).str.strip())
    with c2:
        nv = st.selectbox("Nhân viên", ["Tất cả"] + sorted(x for x in staff if x and x != "nan"), key="nv_ns")
    base = DF_NSGTC if not DF_NSGTC.empty else DF_LUONG
    lo = base["Ngày"].min() if not base.empty and base["Ngày"].notna().any() else REF - timedelta(days=60)
    with c3:
        a0, b0 = date_pick("Khoảng ngày", max(lo, REF - timedelta(days=29)), REF, "d_ns")

    note_head("03", "Năng suất & Lương",
              f"Phạm vi {bc}{'' if nv == 'Tất cả' else ' · ' + nv} · dữ liệu {a0:%d.%m.%Y} – {b0:%d.%m.%Y}")

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

    sub_head(f"3.1 · Kỳ lương — {c_name} so với {p_name}")
    st.markdown("<div style='font-size:11px;color:var(--slate);margin-bottom:8px;'>"
                "Kỳ 20 tính từ ngày 01 đến 15, chi lương ngày 20 · Kỳ 05 tính từ ngày 16 đến hết tháng, "
                "chi lương ngày 05 tháng sau · Lương tổng = LHH LTC + LHH GTC + LHH GTBTT</div>",
                unsafe_allow_html=True)
    def delta_span(delta: float, suffix: str, decimals: int = 0, hib: bool = True) -> str:
        good = (delta > 0) == hib
        cls = "" if abs(delta) < 1e-9 else ("up" if good else "down")
        arrow = "" if abs(delta) < 1e-9 else ("▲" if delta > 0 else "▼")
        return f"<span class='{cls}'>{arrow} {abs(delta):,.{decimals}f}{suffix}</span>"

    rows_ns = [
        ["Đơn giá trung bình", f"{avg_price(Lc):,.0f} đ", f"{avg_price(Lp):,.0f} đ",
         delta_span(avg_price(Lc) - avg_price(Lp), " đ")],
        ["Sản lượng GTC", f"{sum_gtc(Gc):,.0f} đơn", f"{sum_gtc(Gp):,.0f} đơn",
         delta_span(sum_gtc(Gc) - sum_gtc(Gp), " đơn")],
        ["%GTC", f"{pct(Gc):,.2f}%", f"{pct(Gp):,.2f}%", delta_span(pct(Gc) - pct(Gp), " pp", 2)],
    ]
    st.markdown(ledger_table(f"{c_name} so với {p_name}", ["Chỉ tiêu", "Kỳ này", "Kỳ trước", "Chênh lệch"], rows_ns,
                             total_row=["Lương tổng", f"{total_pay(Lc):,.0f} đ"]),
                unsafe_allow_html=True)

    sub_head("3.2 · Nhịp %GTC theo kỳ")
    if gan and gtc and not G.empty:
        gm = pd.DataFrame({"Ngày": G["Ngày"],
                           "Giá Trị": np.where(G[gan] > 0, G[gtc] / G[gan] * 100, np.nan),
                           "Trọng Số": G[gan]})
        st.markdown(period_ledger("So với kỳ liền trước", gm, REF, unit="%"), unsafe_allow_html=True)
    else:
        gm = pd.DataFrame(columns=["Ngày", "Giá Trị", "Trọng Số"])
        empty("Chưa đọc được cột số đơn gán hoặc đơn giao tính lương.")

    Gr, Lr = cut(G, a0, b0), cut(L, a0, b0)

    sub_head("3.3 · Sản lượng gán, GTC và tỷ lệ")
    if gan and gtc and not Gr.empty:
        g = Gr.groupby("Ngày", as_index=False).agg({gan: "sum", gtc: "sum"})
        g["r"] = np.where(g[gan] > 0, g[gtc] / g[gan] * 100, 0.0)
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Bar(x=g["Ngày"], y=g[gan], name="Gán", marker_color="#E5E6E0", marker_line_width=0),
                      secondary_y=False)
        fig.add_trace(go.Bar(x=g["Ngày"], y=g[gtc], name="Giao thành công", marker_color=INK_2,
                             marker_line_width=0, opacity=.85), secondary_y=False)
        fig.add_trace(go.Scatter(x=g["Ngày"], y=g["r"], name="%GTC", mode="lines+markers",
                                 line=dict(color=BRASS, width=1.8), marker=dict(size=4)), secondary_y=True)
        fig.update_layout(barmode="overlay")
        fig.update_yaxes(ticksuffix="%", secondary_y=True, showgrid=False, range=[0, 100])
        st.plotly_chart(sized(fig, 240), use_container_width=True)
    else:
        empty("Chưa đủ dữ liệu gán và giao để vẽ.")

    f1, f2 = st.columns(2)
    with f1:
        sub_head("3.4 · Đơn giá theo ngày")
        if price and not Lr.empty:
            g = Lr.groupby("Ngày", as_index=False)[price].mean()
            fig = px.line(g, x="Ngày", y=price, markers=True)
            fig.update_traces(line=dict(color=INK, width=1.8), marker=dict(size=4, color=INK))
            st.plotly_chart(sized(fig, 210), use_container_width=True)
        else:
            empty("Chưa đọc được cột đơn giá.")
    with f2:
        sub_head("3.5 · Lương tổng theo ngày")
        if pay and not Lr.empty:
            tmp = Lr.copy()
            tmp["T"] = tmp[list(pay.values())].sum(axis=1)
            g = tmp.groupby("Ngày", as_index=False)["T"].sum()
            fig = px.area(g, x="Ngày", y="T")
            fig.update_traces(line=dict(color=FOREST, width=1.8), fillcolor="rgba(31,110,74,.06)")
            st.plotly_chart(sized(fig, 210), use_container_width=True)
        else:
            empty("Chưa đọc được các cột LHH LTC, LHH GTC, LHH GTBTT.")

    if gan and gtc and nv_g and not Gr.empty:
        sub_head("3.6 · Xếp hạng nhân viên — mốc thưởng 80%")
        r = Gr.groupby(nv_g, as_index=False).agg({gan: "sum", gtc: "sum"})
        r["%GTC"] = np.where(r[gan] > 0, r[gtc] / r[gan] * 100, 0.0)
        r = r.sort_values("%GTC", ascending=False).reset_index(drop=True)
        r.insert(0, "Hạng", range(1, len(r) + 1))
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

    sub_head("Nhận định")
    ai_panel("ns", "Viết nhận định năng suất", p_ns, "Năng suất")

# ════════════════════════════════════════════════════════════════════
# GHI CHÚ 04 · KPI
# ════════════════════════════════════════════════════════════════════
elif page == "Tiến độ KPI":
    c1, c2 = st.columns([1.1, 2])
    with c1:
        bc = page_scope("bc_kpi")
    with c2:
        a0, b0 = date_pick("Khoảng ngày", REF.replace(day=1), REF, "d_kpi")

    note_head("04", "Tiến độ hoàn thành KPI", f"Phạm vi {bc} · dữ liệu {a0:%d.%m.%Y} – {b0:%d.%m.%Y}")

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

    sub_head("4.1 · Thực tế so với mục tiêu")
    def kpi_row(name, actual, target, hib):
        ok = actual >= target if hib else actual <= target
        gap = actual - target if hib else target - actual
        cls = "up" if gap >= 0 else "down"
        arrow = "▲" if gap >= 0 else "▼"
        status = "Đạt" if ok else "Chưa đạt"
        return [name, f"{actual:,.2f}%", f"{target:,.2f}%",
                f"<span class='{cls}'>{arrow} {abs(gap):,.2f} pp</span>", status]

    rows_kpi = [kpi_row("GTC tổng", a_gtc, t_gtc, True),
                kpi_row("GTC TikTok Shop", a_tts, t_tts, True),
                kpi_row("Trả hàng", a_tra, t_tra, False)]
    st.markdown(ledger_table("Đối chiếu chỉ tiêu trong kỳ", ["Chỉ tiêu", "Thực tế", "Mục tiêu", "Chênh lệch", "Trạng thái"],
                             rows_kpi), unsafe_allow_html=True)

    sub_head("4.2 · Bám mốc theo ngày")
    series = []
    for frame, name, color, tgt in ((M_GTC, "GTC tổng", INK, t_gtc),
                                    (M_TTS, "GTC TikTok", BRASS, t_tts),
                                    (M_TRA, "Trả hàng", BURGUNDY, t_tra)):
        g = daily(sl(scope(frame, bc), a0, b0))
        if not g.empty:
            series.append((g, name, color, tgt))
    if series:
        fig = go.Figure()
        for g, name, color, tgt in series:
            fig.add_trace(go.Scatter(x=g["Ngày"], y=g["Giá Trị"], name=name, mode="lines+markers",
                                     line=dict(color=color, width=1.8), marker=dict(size=4)))
            fig.add_hline(y=tgt, line_dash="dot", line_color=color, line_width=1, opacity=.4)
        fig.update_yaxes(ticksuffix="%")
        st.plotly_chart(sized(fig, 280), use_container_width=True)

        tbl = daily(sl(scope(M_GTC, bc), a0, b0)).rename(columns={"Giá Trị": "%GTC", "Trọng Số": "Sản lượng"})
        for frame, nm in ((M_TTS, "%GTC TTS"), (M_TRA, "%Trả hàng")):
            d = daily(sl(scope(frame, bc), a0, b0))[["Ngày", "Giá Trị"]].rename(columns={"Giá Trị": nm})
            tbl = tbl.merge(d, on="Ngày", how="outer")
        tbl = tbl.sort_values("Ngày")
        tbl["Đạt mốc GTC"] = np.where(tbl["%GTC"] >= t_gtc, "Đạt", "Chưa")
        st.dataframe(tbl, use_container_width=True, hide_index=True,
                     column_config={"Ngày": st.column_config.DateColumn(format="DD/MM/YYYY"),
                                    "Sản lượng": st.column_config.NumberColumn(format="%,d"),
                                    "%GTC": st.column_config.ProgressColumn(format="%.2f%%", min_value=0, max_value=100),
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

    sub_head("Nhận định")
    ai_panel("kpi", "Viết nhận định KPI", p_kpi, "KPI")

# ════════════════════════════════════════════════════════════════════
# PHỤ LỤC · HỎI AI
# ════════════════════════════════════════════════════════════════════
else:
    c1, c2 = st.columns([2, 1])
    with c1:
        aA, aB = date_pick("Khoảng ngày AI được đọc", REF - timedelta(days=7), REF, "d_ai")
    with c2:
        bc = page_scope("bc_ai")

    note_head("05", "AI cố vấn", f"Phạm vi {bc} · dữ liệu {aA:%d.%m.%Y} – {aB:%d.%m.%Y}")

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

st.markdown(f"<div style='margin-top:38px;padding-top:14px;border-top:3px double var(--rules);"
            f"font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--slate);'>"
            f"GHN · Báo cáo vận hành khu vực · Designed by AM Phan Van Chanh</div>", unsafe_allow_html=True)
