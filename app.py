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
INK      = "#1B2534"   # chữ chính — xanh đen
INK_2    = "#54627A"   # chữ phụ
PAPER    = "#EEF1F7"   # nền trang — xám xanh rất nhạt như ảnh mẫu
CARD     = "#FFFFFF"   # nền thẻ trắng
RULE     = "#E4E8F0"   # viền mảnh
RULE_STR = "#CFD6E4"   # viền đậm hơn
BRASS    = "#F97316"   # CAM GHN — nhấn thương hiệu
BRASS_DP = "#C2540A"   # cam đậm cho chữ trên nền sáng
FOREST   = "#16A34A"   # xanh lá — số dương
BURGUNDY = "#DC2626"   # đỏ — số âm
SLATE    = "#8492A8"   # chữ mờ

# Màu phụ cho biểu đồ nhiều chuỗi (lấy tinh thần neon của ảnh mẫu)
CYAN     = "#0EA5E9"
BLUE     = "#2563EB"   # xanh da trời GHN
VIOLET   = "#7C3AED"
AMBER    = "#F59E0B"
PINK     = "#DB2777"

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

GROUPS: dict[str, list[str]] = {
    "Tổng quan": ["Tổng quan"],
    "Vận hành": ["GTC tổng", "Sản lượng theo ca", "Tỷ lệ trả hàng", "GTB thu tiền",
                 "GTC TikTok Shop", "ODR TikTok Shop", "Gán & Leadtime"],
    "Kinh doanh": ["Doanh thu & KPI", "Khách hàng mới", "Phễu tiếp xúc", "Khách hàng tiềm năng"],
    "Năng suất & Lương": ["Kỳ lương", "Đơn giá", "Sản lượng gán & GTC",
                          "Lương tổng", "Xếp hạng nhân viên"],
    "Tiến độ KPI": ["Tiến độ KPI"],
    "AI cố vấn": ["AI cố vấn"],
}
ROLE_GROUPS = {
    "admin": list(GROUPS),
    "manager": list(GROUPS),
    "staff": ["Tổng quan", "Vận hành", "Năng suất & Lương"],
}

# ════════════════════════════════════════════════════════════════════
# HỆ THIẾT KẾ
# ════════════════════════════════════════════════════════════════════
pio.templates["report"] = go.layout.Template(layout=dict(
    font=dict(family="Inter, sans-serif", size=12, color=SLATE),
    plot_bgcolor=CARD, paper_bgcolor=CARD, hovermode="x unified",
    colorway=[CYAN, BRASS, VIOLET, FOREST, AMBER, PINK, BLUE],
    margin=dict(l=46, r=16, t=16, b=36),
    xaxis=dict(showgrid=False, linecolor=RULE, linewidth=1, ticks="outside",
               tickcolor=RULE, ticklen=4, tickfont=dict(size=10.5, color=SLATE)),
    yaxis=dict(showgrid=True, gridcolor="#EEF1F6", gridwidth=1, zeroline=False,
               tickfont=dict(size=10.5, color=SLATE)),
    legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0,
                font=dict(size=10.5, color=INK_2)),
    hoverlabel=dict(bgcolor=CARD, bordercolor=RULE_STR,
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
  background:{PAPER};
  color:{INK};
}}
html, body, [class*="css"] {{ font-family:'Inter',sans-serif; color:{INK}; }}
.block-container {{ padding-top:1.1rem; padding-bottom:3rem; max-width:1560px; }}
/* Chỉ ẩn menu ba chấm và footer. KHÔNG ẩn cả header — nút mở/đóng thanh bên
   nằm trong header, ẩn đi là không còn cách nào mở lại thanh bên. */
#MainMenu {{ visibility:hidden; }}
footer {{ visibility:hidden; }}
header[data-testid="stHeader"] {{ background:transparent; height:0; }}
/* Giữ nút mở thanh bên luôn nhìn thấy và nổi lên trên */
[data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"] {{
  visibility:visible !important; display:flex !important; opacity:1 !important;
  top:12px !important; left:12px !important; z-index:999999 !important;
  background:{CARD}; border:1px solid {RULE_STR}; border-radius:8px;
  box-shadow:0 2px 6px rgba(27,37,52,.12);
}}
[data-testid="stSidebarCollapsedControl"] svg,
[data-testid="collapsedControl"] svg {{ color:{BLUE}; fill:{BLUE}; }}
/* Thanh bên luôn hiện, không bị thu bởi CSS khác */
section[data-testid="stSidebar"] {{ visibility:visible !important; }}
h1,h2,h3,h4 {{ font-family:'Inter',sans-serif; color:{INK}; }}

/* ── thanh trên cùng ─────────────────────────────────────────────── */
.topbar {{
  display:flex; justify-content:space-between; align-items:center; gap:14px;
  background:{CARD};
  border:1px solid {RULE}; border-radius:12px; padding:14px 20px; margin-bottom:14px;
  box-shadow:0 1px 3px rgba(27,37,52,.06);
}}
.topbar .tt {{ font-size:16px; font-weight:700; letter-spacing:.02em; color:{INK}; }}
.topbar .ts {{
  font-family:'JetBrains Mono',monospace; font-size:10.5px; letter-spacing:.12em;
  text-transform:uppercase; color:{SLATE}; margin-top:3px;
}}
.topbar .meta {{ text-align:right; font-family:'JetBrains Mono',monospace; font-size:10.5px;
  letter-spacing:.1em; text-transform:uppercase; color:{SLATE}; line-height:1.8; }}
.topbar .meta b {{ color:{INK}; font-weight:600; }}

/* ── thẻ số liệu lớn ─────────────────────────────────────────────── */
/* ── thẻ số nhỏ có biểu đồ bên trong (hàng đầu như ảnh mẫu) ────────── */
.tile-cap {{ font-size:11.5px; font-weight:600; color:{SLATE}; letter-spacing:.02em; }}
.tile-num {{ font-size:27px; font-weight:700; color:{INK}; line-height:1.15; margin-top:3px;
  font-variant-numeric:tabular-nums; letter-spacing:-.02em; }}
.tile-delta {{ font-size:11px; font-weight:500; margin-top:1px; font-variant-numeric:tabular-nums; }}

/* ── tiêu đề bên trong panel ───────────────────────────────────────── */
.panel-title {{ font-size:15px; font-weight:700; color:{INK}; letter-spacing:-.01em; }}
.panel-sub {{ font-size:11px; color:{SLATE}; margin-top:2px; margin-bottom:6px; }}

/* ── danh sách bưu cục (như Branches list) ─────────────────────────── */
.blist {{ margin-top:6px; }}
.brow {{ display:flex; justify-content:space-between; align-items:center;
  padding:11px 2px; border-bottom:1px solid {RULE}; }}
.brow:last-child {{ border-bottom:none; }}
.bname {{ font-size:13px; font-weight:600; color:{INK}; }}
.bsub {{ display:block; font-size:10.5px; font-weight:400; color:{SLATE};
  font-variant-numeric:tabular-nums; margin-top:1px; }}
.bdg {{ font-size:11px; font-weight:700; padding:3px 10px; border-radius:999px;
  font-variant-numeric:tabular-nums; white-space:nowrap; }}
.bdg-ok  {{ background:#DCFCE7; color:{FOREST}; }}
.bdg-mid {{ background:#FEF3C7; color:{BRASS_DP}; }}
.bdg-bad {{ background:#FEE2E2; color:{BURGUNDY}; }}

.hl-row {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(184px,1fr)); gap:12px; margin:14px 0; }}
.hl {{
  position:relative; background:{CARD};
  border:1px solid {RULE}; border-radius:12px; padding:16px 18px 15px; overflow:hidden;
  box-shadow:0 1px 3px rgba(27,37,52,.05);
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
}}
.hl .num small {{ font-size:13px; font-weight:500; color:{SLATE}; margin-left:2px; }}
.hl .delta {{
  font-family:'JetBrains Mono',monospace; font-size:11px; margin-top:9px;
  font-variant-numeric:tabular-nums; font-weight:500;
}}
.d-up {{ color:{FOREST}; }} .d-down {{ color:{BURGUNDY}; }} .d-flat {{ color:{SLATE}; }}

/* ── panel bọc biểu đồ ───────────────────────────────────────────── */
.panel {{
  background:{CARD};
  border:1px solid {RULE}; border-radius:12px; padding:14px 16px 6px; margin-bottom:12px;
  box-shadow:0 1px 3px rgba(27,37,52,.05);
}}

/* ── đầu mục ─────────────────────────────────────────────────────── */
.note-head {{ position:relative; margin:26px 0 14px; padding-bottom:11px;
  border-bottom:1px solid {RULE}; overflow:hidden; }}
.note-head .ghost {{
  position:absolute; right:0; top:-26px; font-size:96px; font-weight:800;
  color:{INK}; opacity:.05; line-height:1; user-select:none; pointer-events:none;
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
  background:{CARD};
  border:1px solid {RULE}; border-left:3px solid {BRASS};
  border-radius:12px; padding:20px 24px; margin:14px 0;
  box-shadow:0 1px 3px rgba(27,37,52,.05);
}}
.letter .kicker {{
  font-family:'JetBrains Mono',monospace; font-size:10px; letter-spacing:.16em;
  text-transform:uppercase; color:{BRASS_DP}; font-weight:600; margin-bottom:10px;
}}
.letter p {{ font-size:14.5px; line-height:1.8; color:{INK}; margin:0; }}
.letter .dropcap {{
  float:left; font-size:44px; font-weight:800; line-height:.85;
  padding:3px 10px 0 0; color:{BRASS};
}}
.letter .sign {{
  text-align:right; margin-top:12px; font-family:'JetBrains Mono',monospace;
  font-size:10px; letter-spacing:.1em; color:{SLATE}; text-transform:uppercase;
}}

/* ── điểm cần lưu ý ──────────────────────────────────────────────── */
.notice {{
  background:{CARD};
  border:1px solid {RULE}; border-radius:12px; padding:16px 20px; margin:14px 0;
  box-shadow:0 1px 3px rgba(27,37,52,.05);
}}
.notice .cap {{
  font-family:'JetBrains Mono',monospace; font-size:10px; letter-spacing:.16em;
  text-transform:uppercase; color:{BRASS_DP}; font-weight:600; margin-bottom:11px;
}}
.notice ol {{ margin:0; padding-left:19px; }}
.notice li {{ font-size:13px; line-height:1.8; color:{INK}; margin-bottom:8px; }}
.notice li:last-child {{ margin-bottom:0; }}
.notice li b {{ font-variant-numeric:tabular-nums; font-weight:700; color:{INK}; }}
.notice li .tag {{
  font-family:'JetBrains Mono',monospace; font-size:9px; letter-spacing:.1em;
  text-transform:uppercase; padding:2px 8px; border-radius:999px; margin-right:8px; font-weight:600;
}}
.tag-high {{ background:#FEF2F2; color:{BURGUNDY}; border:1px solid #FECACA; }}
.tag-mid  {{ background:#FFFBEB; color:{BRASS_DP};  border:1px solid #FDE68A; }}
.tag-ok   {{ background:#F0FDF4; color:{FOREST};   border:1px solid #BBF7D0; }}

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
  text-align:right; padding:9px 0; border-bottom:1px solid {RULE};
  font-variant-numeric:tabular-nums; color:{INK};
}}
table.ledger tr.total td {{
  border-top:1px solid {RULE_STR}; border-bottom:none;
  font-weight:700; color:{INK}; padding-top:11px;
}}
table.ledger td.up {{ color:{FOREST}; }} table.ledger td.down {{ color:{BURGUNDY}; }}
table.ledger td.name {{ font-variant-numeric:normal; color:{INK_2}; }}
table.ledger td span.up {{ color:{FOREST}; }} table.ledger td span.down {{ color:{BURGUNDY}; }}

.empty {{
  background:{CARD}; border:1px dashed {RULE_STR}; border-radius:12px;
  padding:22px; text-align:center; color:{SLATE}; font-size:12.5px; margin:12px 0; line-height:1.7;
}}

/* ── thanh bên ───────────────────────────────────────────────────── */
section[data-testid="stSidebar"] {{
  background:{CARD};
  border-right:1px solid {RULE};
}}
section[data-testid="stSidebar"] .block-container {{ padding-top:1.2rem; }}
.toc-sub {{
  font-family:'JetBrains Mono',monospace; font-size:9px; letter-spacing:.16em;
  text-transform:uppercase; color:{BRASS_DP}; font-weight:600; margin:14px 0 4px 4px;
}}
section[data-testid="stSidebar"] div[data-testid="stRadio"]:nth-of-type(2) [role="radiogroup"] label {{
  padding-left:20px; font-size:12px !important;
}}

.toc-label {{
  font-family:'JetBrains Mono',monospace; font-size:9.5px; letter-spacing:.18em;
  text-transform:uppercase; color:{SLATE}; font-weight:600; margin:4px 0 10px;
}}
section[data-testid="stSidebar"] [role="radiogroup"] label {{
  font-size:12.5px !important; padding:8px 10px; border-radius:9px;
  border:1px solid transparent; margin-bottom:2px; color:{INK_2} !important;
}}
section[data-testid="stSidebar"] [role="radiogroup"] label:hover {{ background:#F4F6FA; }}
section[data-testid="stSidebar"] [role="radiogroup"] label[data-checked="true"] {{
  color:{BLUE} !important; background:#EFF5FF;
  border-color:#BFDBFE; font-weight:600;
}}

/* ── điều khiển Streamlit ────────────────────────────────────────── */
.stButton>button {{
  border-radius:8px; border:1px solid {RULE_STR}; background:{CARD};
  color:{INK}; font-size:11.5px; letter-spacing:.05em; text-transform:uppercase;
  font-weight:600; padding:.52rem 1.05rem;
}}
.stButton>button:hover {{ border-color:{BLUE}; color:{BLUE}; background:#EFF5FF; }}
.stButton>button[kind="primary"] {{
  background:{BLUE}; color:#FFFFFF;
  border:none; font-weight:600;
}}
.stButton>button[kind="primary"]:hover {{ filter:brightness(1.08); color:#FFFFFF; }}

label, .stSelectbox label, .stRadio label, .stDateInput label,
.stMultiSelect label, .stNumberInput label, .stTextArea label {{
  font-family:'JetBrains Mono',monospace !important; font-size:9.5px !important;
  letter-spacing:.14em !important; text-transform:uppercase; color:{SLATE} !important;
}}
div[data-baseweb="select"]>div, div[data-baseweb="input"]>div, .stTextArea textarea {{
  border-radius:8px !important; border-color:{RULE_STR} !important;
  background:{CARD} !important; color:{INK} !important;
}}
div[data-testid="stDataFrame"] {{ border:1px solid {RULE}; border-radius:12px; overflow:hidden; }}
div[data-testid="stExpander"] {{ border:1px solid {RULE}; border-radius:12px; background:{CARD}; }}
[data-testid="stChatMessage"] {{ background:{CARD}; border:1px solid {RULE}; border-radius:12px; }}
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


def hex_fade(hex_color: str, alpha: float) -> str:
    """Chuyển #RRGGBB sang rgba() để tô nền biểu đồ nhạt."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def delta_line(delta: float, unit: str, higher_is_better=True, has_prev: bool = True) -> str:
    """Dòng chênh lệch dưới con số lớn trong thẻ.
    has_prev=False nghĩa là kỳ trước KHÔNG CÓ DỮ LIỆU — khác hẳn với kỳ trước bằng 0.
    Nếu không phân biệt, thẻ sẽ hiện '▲ 2.331 đơn so với hôm qua' trong khi thực tế
    hôm qua chưa có số liệu, gây hiểu nhầm là tăng vọt."""
    if not has_prev:
        return "<div class='tile-delta d-flat'>chưa có dữ liệu kỳ trước để so sánh</div>"
    good = (delta > 0) == higher_is_better
    cls = "d-flat" if abs(delta) < 1e-9 else ("d-up" if good else "d-down")
    arrow = "" if abs(delta) < 1e-9 else ("▲" if delta > 0 else "▼")
    if unit == "%":
        txt = f"{arrow} {abs(delta):,.2f} pp so với hôm qua"
    elif unit == "đ":
        txt = f"{arrow} {abs(delta)/1_000_000:,.1f} tr đ so với hôm qua"
    else:
        txt = f"{arrow} {abs(delta):,.0f} đơn so với hôm qua"
    return f"<div class='tile-delta {cls}'>{txt}</div>"


def raw_table(df: pd.DataFrame, value_label: str, key: str, unit: str = "%"):
    """Bảng dữ liệu thô để tra cứu từng dòng, kèm nút tải CSV."""
    if df is None or df.empty:
        empty("Không có dữ liệu chi tiết trong khoảng đã chọn.")
        return
    show = df[["Ngày", "Bưu Cục", "Trọng Số", "Giá Trị"]].rename(
        columns={"Trọng Số": "Sản lượng", "Giá Trị": value_label}).sort_values("Ngày", ascending=False)
    cfg = {"Ngày": st.column_config.DateColumn("Ngày", format="DD/MM/YYYY"),
           "Sản lượng": st.column_config.NumberColumn(format="%,d")}
    cfg[value_label] = st.column_config.NumberColumn(
        format="%.2f%%" if unit == "%" else ("%,.2f" if unit == "h" else "%,.0f"))
    st.dataframe(show, use_container_width=True, hide_index=True, height=280, column_config=cfg)
    st.download_button("Tải CSV dữ liệu chi tiết", show.to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"{key}.csv", mime="text/csv", key=f"dl_{key}")


def bc_compare_chart(df: pd.DataFrame, target: float | None, unit: str = "%",
                     higher_is_better: bool = True):
    """So sánh chỉ số giữa các bưu cục trong khoảng đã lọc — thanh ngang."""
    if df is None or df.empty:
        empty("Không có dữ liệu để so sánh giữa các bưu cục.")
        return
    d = df[~df["Bưu Cục"].map(is_total_row)]
    if d.empty:
        empty("Không có dữ liệu theo từng bưu cục (chỉ có dòng tổng).")
        return
    g = (d.assign(_p=d["Giá Trị"].fillna(0) * d["Trọng Số"])
          .groupby("Bưu Cục", as_index=False).agg(_p=("_p", "sum"), w=("Trọng Số", "sum")))
    g = g[g["w"] > 0]
    if g.empty:
        empty("Không đủ dữ liệu để so sánh.")
        return
    g["r"] = g["_p"] / g["w"]
    g = g.sort_values("r")
    if target:
        colors = [FOREST if (v >= target) == higher_is_better else BURGUNDY for v in g["r"]]
    else:
        colors = [BLUE] * len(g)
    fig = go.Figure(go.Bar(
        x=g["r"], y=g["Bưu Cục"], orientation="h", marker=dict(color=colors, line=dict(width=0)),
        text=[f"{v:,.2f}%" if unit == "%" else f"{v:,.1f}" for v in g["r"]],
        textposition="outside", textfont=dict(size=10.5, color=INK_2),
        customdata=g["w"], hovertemplate="%{y}<br>%{x:.2f}<br>Sản lượng %{customdata:,.0f}<extra></extra>"))
    if target:
        fig.add_vline(x=target, line_dash="dot", line_color=SLATE, line_width=1.5)
    fig.update_layout(height=max(160, 46 * len(g)), margin=dict(l=6, r=44, t=6, b=28))
    fig.update_xaxes(ticksuffix="%" if unit == "%" else "", showgrid=True, gridcolor="#EEF1F6")
    st.plotly_chart(fig, use_container_width=True)


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
        if LOGO.exists():
            st.image(str(LOGO), width=210)
        st.write("")
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


def is_total_row(name) -> bool:
    """Sheet của GHN có dòng tổng, đặt tên không thống nhất giữa các tab:
    'Grand Total' ở File1/File3/TTS, 'Tổng số' ở sheet Trả hàng."""
    return norm(name) in ("grand total", "tong so", "tong cong", "total", "tong")


def scope(df, bc):
    """Phạm vi 'Tất cả' lấy thẳng dòng tổng của sheet (theo yêu cầu), không tự cộng.
    Phạm vi một bưu cục thì lọc đúng bưu cục đó và loại dòng tổng ra."""
    if df is None or df.empty or "Bưu Cục" not in df.columns:
        return df if df is not None else pd.DataFrame()
    out = df
    if bc and bc != "Tất cả":
        return out[out["Bưu Cục"].map(norm) == norm(bc)]

    if not IS_ALL_BC:
        # Tài khoản bị giới hạn bưu cục: không được xem dòng tổng toàn khu vực,
        # nên gộp từ chính các bưu cục được phân quyền.
        allow = [norm(x) for x in ALLOWED_BC]
        return out[out["Bưu Cục"].map(lambda x: norm(x) in allow)]

    totals = out[out["Bưu Cục"].map(is_total_row)]
    # Nếu sheet nào không có dòng tổng thì mới tự gộp từ các bưu cục.
    return totals if not totals.empty else out[~out["Bưu Cục"].map(is_total_row)]


def bc_options(*frames):
    vals = set()
    for f in frames:
        if f is not None and not f.empty and "Bưu Cục" in f.columns:
            vals |= set(f["Bưu Cục"].dropna().astype(str).str.strip())
    vals = {v for v in vals
            if v and v.lower() not in ("nan", "chưa phân loại") and not is_total_row(v)}
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
    # Từ khóa dò cột đã đối chiếu với tên cột THẬT trong sheet (đọc ngày 16/08/2026):
    #   File1_BuuCuc / File2_TTS : Ngày | Cấp Quản Lý | Bưu cục | Volume | % Gán | % GTC | % Chuyển trả | Leadtime
    #   File3_TheoCa             : thêm cột "Loại Hàng (Ca)"
    #   Tỷ lệ Trả hàng           : Ngày | Cấp Quản Lý | Bưu cục | % Vol | % Return
    M_GTC = metric_frame("gtc_tong", [["% gtc"], ["gtc"], ["giao thanh cong"]])
    M_TRA = metric_frame("tra_hang", [["% return"], ["return"], ["chuyen tra"], ["tra hang"], ["tra"]])
    M_GTB = metric_frame("gtb_thu_tien", [["gtb"], ["thu tien"], ["% gtb"]])
    M_TTS = metric_frame("gtc_tts", [["% gtc"], ["gtc tts"], ["gtc"]])
    M_ODR = metric_frame("odr_tts", [["odr"], ["ontime"], ["dung han"], ["% odr"]])
    M_CA = metric_frame("sl_gtc_ca", [["% gtc"], ["gtc"]], extra_dim=[["loai hang"], ["ca"]])
    # Hai chỉ số có sẵn trong sheet nhưng chưa nằm trong yêu cầu ban đầu — đưa lên dashboard luôn.
    M_GAN = metric_frame("gtc_tong", [["% gan"], ["gan"]])
    M_LEAD = metric_frame("gtc_tong", [["leadtime"], ["lead time"]], is_pct=False)
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


def kpi_target(keys, fallback, exclude=(), bc="Tất cả", ref=None):
    """Đọc mốc KPI từ sheet KPI (cấu trúc thật: Tháng | Bưu cục | %GTC Tổng | %GTC TTS |
    %Trả hàng | Doanh thu). Lọc đúng tháng của kỳ báo cáo và đúng bưu cục.
    Sheet đang trống ở thời điểm dựng app — khi bạn điền số vào là dashboard tự nhận."""
    if DF_KPI.empty:
        return float(fallback)
    df = DF_KPI

    # Lọc theo tháng nếu sheet có cột Tháng
    mcol = pick_col(df, [["thang"]])
    if mcol is not None and ref is not None:
        want = pd.to_numeric(df[mcol], errors="coerce")
        same = df[want == ref.month]
        if not same.empty:
            df = same

    # Phạm vi "Tất cả" thì lấy dòng tổng, ngược lại lấy đúng bưu cục
    if "Bưu Cục" in df.columns:
        if bc and bc != "Tất cả":
            pick = df[df["Bưu Cục"].map(norm) == norm(bc)]
        else:
            pick = df[df["Bưu Cục"].map(is_total_row)]
        if not pick.empty:
            df = pick

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
        st.image(str(LOGO), width=150)
    st.markdown(f"<div style='font-size:11px;color:var(--slate);margin:10px 0 18px;line-height:1.6;'>"
                f"{esc(AUTH['ten'])} · {esc(AUTH['role'])}<br>{esc(' / '.join(ALLOWED_BC))}</div>",
                unsafe_allow_html=True)

    st.markdown("<div class='toc-label'>Mục lục</div>", unsafe_allow_html=True)
    role_groups = ROLE_GROUPS.get(AUTH["role"], ROLE_GROUPS["staff"])
    group = st.radio("Nhóm", role_groups, label_visibility="collapsed", key="nav_group")

    subitems = GROUPS[group]
    if len(subitems) > 1:
        st.markdown(f"<div class='toc-sub'>{esc(group)}</div>", unsafe_allow_html=True)
        # Mỗi nhóm giữ mục con đã chọn riêng, đổi nhóm không làm mất lựa chọn cũ.
        sub_key = f"nav_sub_{group}"
        sub = st.radio("Mục", subitems, label_visibility="collapsed", key=sub_key)
    else:
        sub = subitems[0]
    page = sub  # phần thân trang bên dưới dùng biến `page` để định tuyến

    # ── Bộ lọc toàn cục: chọn một lần, mọi trang cùng theo ────────────
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
if group == "Tổng quan":
    bc = page_scope("bc_home", "Phạm vi báo cáo")
    g_gtc, g_tra, g_tts, g_odr, g_gtb, g_dt = (scope(x, bc) for x in
                                               (M_GTC, M_TRA, M_TTS, M_ODR, M_GTB, M_DT))
    (dA, dB), (pA, pB) = period_pair(REF, "Ngày")
    (mA, mB), _ = period_pair(REF, "Tháng")

    t_gtc = kpi_target([["kpi", "gtc"], ["% gtc"], ["gtc"]], 70.0, exclude=["tts", "tiktok"], bc=bc, ref=REF)
    t_tts = kpi_target([["gtc tts"], ["tts"], ["tiktok"]], 80.0, bc=bc, ref=REF)
    t_tra = kpi_target([["tra hang"], ["tra"]], 5.0, bc=bc, ref=REF)
    t_odr = 98.0
    st.session_state.kpi_manual.setdefault(f"dt_{bc}", 71_000_000.0)
    t_dt = float(st.session_state.kpi_manual[f"dt_{bc}"])

    v_gtc, v_tts = val(g_gtc, dA, dB), val(g_tts, dA, dB)
    v_odr, v_tra = val(g_odr, dA, dB), val(g_tra, dA, dB)
    p_gtc, p_tts = val(g_gtc, pA, pB), val(g_tts, pA, pB)
    p_odr, p_tra = val(g_odr, pA, pB), val(g_tra, pA, pB)
    v_dt = val(g_dt, mA, mB, "sum")

    # ── Hàng thẻ số có biểu đồ nhỏ bên trong (như hàng Visits/Orders của mẫu) ──
    win_a = REF - timedelta(days=13)
    d_gtc = daily(sl(g_gtc, win_a, REF))
    d_tts = daily(sl(g_tts, win_a, REF))
    d_dt = daily(sl(g_dt, win_a, REF), "sum")

    def mini(kind, xs, ys, color):
        """Biểu đồ tí hon trong thẻ: đường cho tỷ lệ, cột cho sản lượng và tiền."""
        f = go.Figure()
        if kind == "line":
            f.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color=color, width=2),
                                   fill="tozeroy", fillcolor=hex_fade(color, .10),
                                   hovertemplate="%{y:.2f}%<extra></extra>"))
        else:
            f.add_trace(go.Bar(x=xs, y=ys, marker_color=color, marker_line_width=0,
                               hovertemplate="%{y:,.0f}<extra></extra>"))
        f.update_layout(height=64, margin=dict(l=0, r=0, t=4, b=0),
                        xaxis=dict(visible=False), yaxis=dict(visible=False),
                        showlegend=False, hovermode="x")
        return f

    vol_now = float(sl(g_gtc, dA, dB)["Trọng Số"].sum())
    vol_prev = float(sl(g_gtc, pA, pB)["Trọng Số"].sum())

    # Kỳ trước CÓ dữ liệu hay không — quyết định có hiện chênh lệch hay không.
    has_prev_gtc = not sl(g_gtc, pA, pB).empty
    has_prev_tts = not sl(g_tts, pA, pB).empty

    tiles = [
        ("Sản lượng hôm nay", f"{vol_now:,.0f}", vol_now - vol_prev, "đơn", True,
         "bar", d_gtc["Ngày"], d_gtc["Trọng Số"], BLUE, has_prev_gtc),
        ("%GTC tổng", f"{v_gtc:,.2f}%", v_gtc - p_gtc, "%", True,
         "line", d_gtc["Ngày"], d_gtc["Giá Trị"], CYAN, has_prev_gtc),
        ("%GTC TikTok", f"{v_tts:,.2f}%", v_tts - p_tts, "%", True,
         "line", d_tts["Ngày"], d_tts["Giá Trị"], VIOLET, has_prev_tts),
        ("Doanh thu tháng", f"{v_dt/1_000_000:,.1f} tr", None, "đ", True,
         "bar", d_dt["Ngày"], d_dt["Giá Trị"], BRASS, True),
    ]
    cols = st.columns(4)
    for col, (cap, valtxt, delta, unit, hib, kind, xs, ys, color, has_prev) in zip(cols, tiles):
        with col:
            with st.container(border=True):
                st.markdown(f"<div class='tile-cap'>{esc(cap)}</div>"
                            f"<div class='tile-num'>{valtxt}</div>"
                            + (delta_line(delta, unit, hib, has_prev) if delta is not None
                               else "<div class='tile-delta d-flat'>lũy kế tháng này</div>"),
                            unsafe_allow_html=True)
                if len(ys) > 1:
                    st.plotly_chart(mini(kind, xs, ys, color), use_container_width=True,
                                    config={"displayModeBar": False})

    # ── Biểu đồ nhiều đường + danh sách bưu cục (như Traffic Sources / Branches list) ──
    left, right = st.columns([1.75, 1])
    with left:
        with st.container(border=True):
            st.markdown("<div class='panel-title'>Diễn biến các chỉ số vận hành</div>"
                        "<div class='panel-sub'>30 ngày gần nhất · tất cả là tỷ lệ phần trăm</div>",
                        unsafe_allow_html=True)
            w30 = REF - timedelta(days=29)
            lines = [("%GTC tổng", daily(sl(g_gtc, w30, REF)), BLUE),
                     ("%GTC TikTok", daily(sl(g_tts, w30, REF)), CYAN),
                     ("ODR TikTok", daily(sl(g_odr, w30, REF)), VIOLET),
                     ("%Trả hàng", daily(sl(g_tra, w30, REF)), BRASS)]
            lines = [(n, d, c) for n, d, c in lines if not d.empty]
            if lines:
                fig = go.Figure()
                for name, d, color in lines:
                    fig.add_trace(go.Scatter(x=d["Ngày"], y=d["Giá Trị"], name=name,
                                             mode="lines+markers",
                                             line=dict(color=color, width=2.2, shape="spline"),
                                             marker=dict(size=5)))
                fig.add_hline(y=t_gtc, line_dash="dot", line_color=SLATE, line_width=1,
                              annotation_text="mốc GTC", annotation_position="top left",
                              annotation_font=dict(size=9, color=SLATE))
                fig.update_yaxes(ticksuffix="%")
                fig.update_layout(height=326, margin=dict(l=42, r=14, t=30, b=30))
                # Chỉ có 1 ngày thì Plotly chia trục theo mili giây — ép định dạng ngày.
                fig.update_xaxes(tickformat="%d/%m", dtick="D1" if len(lines[0][1]) <= 31 else None)
                st.plotly_chart(fig, use_container_width=True)
                n_days = max(len(d) for _, d, _ in lines)
                if n_days < 2:
                    st.markdown("<div class='fig-cap' style='color:#C2540A;'>Mới có 1 ngày dữ liệu "
                                "trong khoảng này nên chưa vẽ được đường xu hướng. Biểu đồ sẽ đầy đủ "
                                "khi sheet tích lũy thêm ngày.</div>", unsafe_allow_html=True)
            else:
                empty("Chưa có dữ liệu vận hành trong 30 ngày gần nhất.")

    with right:
        with st.container(border=True):
            st.markdown("<div class='panel-title'>Danh sách bưu cục</div>"
                        "<div class='panel-sub'>%GTC lũy kế tháng · so với mốc</div>",
                        unsafe_allow_html=True)
            src = sl(M_GTC, mA, mB)
            src = src[~src["Bưu Cục"].map(is_total_row)] if not src.empty else src
            if not IS_ALL_BC and not src.empty:
                allow = [norm(x) for x in ALLOWED_BC]
                src = src[src["Bưu Cục"].map(lambda x: norm(x) in allow)]
            if not src.empty:
                bl = (src.assign(_p=src["Giá Trị"].fillna(0) * src["Trọng Số"])
                      .groupby("Bưu Cục", as_index=False)
                      .agg(_p=("_p", "sum"), w=("Trọng Số", "sum")))
                bl = bl[bl["w"] > 0]
                bl["r"] = bl["_p"] / bl["w"]
                bl = bl.sort_values("r", ascending=False)
                rows = ""
                for _, r in bl.iterrows():
                    ok = r["r"] >= t_gtc
                    cls = "bdg-ok" if ok else ("bdg-mid" if r["r"] >= t_gtc * .95 else "bdg-bad")
                    rows += (f"<div class='brow'>"
                             f"<div class='bname'>{esc(r['Bưu Cục'])}"
                             f"<span class='bsub'>{r['w']:,.0f} đơn</span></div>"
                             f"<span class='bdg {cls}'>{r['r']:,.1f}%</span></div>")
                st.markdown(f"<div class='blist'>{rows}</div>", unsafe_allow_html=True)
            else:
                empty("Chưa có dữ liệu theo bưu cục trong tháng.")

    # ── Đồng hồ KPI + bảng theo dõi (như Website Traffic / Task manager) ──
    gcol, tcol = st.columns([1, 1.75])
    with gcol:
        with st.container(border=True):
            st.markdown("<div class='panel-title'>Tiến độ %GTC tháng</div>"
                        "<div class='panel-sub'>lũy kế so với mốc KPI</div>",
                        unsafe_allow_html=True)
            m_gtc = val(g_gtc, mA, mB)
            tgt = max(t_gtc, 0.5)
            gfig = go.Figure(go.Indicator(
                mode="gauge+number", value=m_gtc,
                number={"suffix": "%", "valueformat": ".2f", "font": {"size": 34, "color": INK}},
                gauge={"axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": RULE_STR,
                                "tickfont": {"size": 9, "color": SLATE}},
                       "bar": {"color": BLUE, "thickness": .30},
                       "bgcolor": PAPER, "borderwidth": 0,
                       "steps": [{"range": [0, tgt * .8], "color": "#FEE2E2"},
                                 {"range": [tgt * .8, tgt], "color": "#FEF3C7"},
                                 {"range": [tgt, 100], "color": "#DCFCE7"}],
                       "threshold": {"line": {"color": BURGUNDY, "width": 3},
                                     "thickness": .82, "value": tgt}}))
            gfig.update_layout(height=250, margin=dict(l=18, r=18, t=10, b=6))
            st.plotly_chart(gfig, use_container_width=True)
            gap = m_gtc - t_gtc
            st.markdown(f"<div class='fig-cap' style='text-align:center;'>"
                        f"Mốc {t_gtc:,.2f}% · {'vượt' if gap >= 0 else 'còn thiếu'} "
                        f"{abs(gap):,.2f} điểm phần trăm</div>", unsafe_allow_html=True)

    with tcol:
        with st.container(border=True):
            st.markdown("<div class='panel-title'>Theo dõi từng ngày</div>"
                        "<div class='panel-sub'>7 ngày gần nhất · đối chiếu với mốc KPI</div>",
                        unsafe_allow_html=True)
            d7 = daily(sl(g_gtc, REF - timedelta(days=6), REF))
            d7t = daily(sl(g_tra, REF - timedelta(days=6), REF))
            if not d7.empty:
                d7 = d7.merge(d7t[["Ngày", "Giá Trị"]].rename(columns={"Giá Trị": "tra"}),
                              on="Ngày", how="left")
                rows = ""
                for _, r in d7.sort_values("Ngày", ascending=False).iterrows():
                    ok = r["Giá Trị"] >= t_gtc
                    cls = "bdg-ok" if ok else ("bdg-mid" if r["Giá Trị"] >= t_gtc * .95 else "bdg-bad")
                    label = "Đạt" if ok else ("Sát mốc" if r["Giá Trị"] >= t_gtc * .95 else "Chưa đạt")
                    tra_txt = f"{r['tra']:,.2f}%" if pd.notna(r.get("tra")) else "—"
                    rows += (f"<tr><td class='name'>{r['Ngày']:%d/%m}</td>"
                             f"<td>{r['Trọng Số']:,.0f}</td>"
                             f"<td>{r['Giá Trị']:,.2f}%</td>"
                             f"<td>{tra_txt}</td>"
                             f"<td><span class='bdg {cls}'>{label}</span></td></tr>")
                st.markdown(
                    "<table class='ledger'><thead><tr><th>Ngày</th><th>Sản lượng</th>"
                    "<th>%GTC</th><th>%Trả hàng</th><th>Trạng thái</th></tr></thead>"
                    f"<tbody>{rows}</tbody></table>", unsafe_allow_html=True)
            else:
                empty("Chưa có dữ liệu 7 ngày gần nhất.")

    # ── Điểm cần lưu ý ────────────────────────────────────────────────
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
                       f"<b>{t/1_000_000:,.0f} tr đ</b> — thiếu <b>{abs(gap)/1_000_000:,.1f} tr đ</b>. "
                       f"{why.capitalize()}.")
            items += f"<li><span class='tag {tag}'>{label}</span>{txt}</li>"
    else:
        items = ("<li><span class='tag tag-ok'>Đạt mốc</span>Toàn bộ chỉ số đang bám sát hoặc "
                 "vượt mục tiêu đề ra.</li>")

    st.markdown(f"<div class='notice'><div class='cap'>Điểm cần lưu ý</div><ol>{items}</ol></div>",
                unsafe_allow_html=True)
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
elif group == "Vận hành":

    def quick_range(base_frame):
        c1, c2, c3 = st.columns([1.1, 1.6, 1.3])
        with c1:
            bc_ = page_scope(f"bc_vh_{sub}")
        with c2:
            quick = st.radio("Khung thời gian", ["Ngày", "Tuần", "Tháng", "Tự chọn"],
                             horizontal=True, key=f"q_vh_{sub}")
        lo = base_frame["Ngày"].min() if not base_frame.empty else REF - timedelta(days=60)
        if quick == "Ngày":
            a_, b_ = REF, REF
        elif quick == "Tuần":
            a_, b_ = REF - timedelta(days=REF.weekday()), REF
        elif quick == "Tháng":
            a_, b_ = REF.replace(day=1), REF
        else:
            a_, b_ = lo, REF
        with c3:
            a_, b_ = date_pick("Khoảng ngày", a_, b_, f"d_vh_{sub}")
        return bc_, a_, b_

    def metric_page(no, title, frame_full, unit, hib, color, target=None, value_label=None, note=""):
        """Khung dùng chung cho 5 chỉ số dạng %: ledger N/W/M, xu hướng, so sánh bưu cục, bảng thô."""
        bc_, a_, b_ = quick_range(frame_full)
        note_head(no, title, f"Phạm vi {bc_} · dữ liệu {a_:%d.%m.%Y} – {b_:%d.%m.%Y}")
        if note:
            st.markdown(f"<div class='fig-cap'>{note}</div>", unsafe_allow_html=True)

        f_scope = scope(frame_full, bc_)
        f_range = sl(f_scope, a_, b_)

        sub_head("Nhịp theo kỳ — so với kỳ liền trước")
        st.markdown(period_ledger(title, f_scope, REF, unit=unit, higher_is_better=hib),
                    unsafe_allow_html=True)

        cA, cB = st.columns([1.5, 1])
        with cA:
            sub_head("Xu hướng trong khoảng đã chọn")
            if not f_range.empty:
                g = daily(f_range)
                fig = px.area(g, x="Ngày", y="Giá Trị")
                fig.update_traces(line=dict(color=color, width=2), fillcolor=hex_fade(color, .08),
                                  mode="lines+markers", marker=dict(size=5, color=color))
                if target:
                    fig.add_hline(y=target, line_dash="dot", line_color=SLATE, line_width=1.3)
                fig.update_yaxes(ticksuffix="%" if unit == "%" else "")
                fig.update_xaxes(tickformat="%d/%m")
                st.plotly_chart(sized(fig, 260), use_container_width=True)
                if len(g) < 2:
                    st.markdown("<div class='fig-cap' style='color:#C2540A;'>Mới có 1 ngày dữ liệu — "
                                "đường xu hướng cần ít nhất 2 ngày.</div>", unsafe_allow_html=True)
            else:
                empty("Chưa có dữ liệu trong khoảng đã chọn.")
        with cB:
            sub_head("So sánh giữa bưu cục")
            bc_compare_chart(f_range, target, unit, hib)

        sub_head("Dữ liệu chi tiết")
        raw_table(f_range, value_label or title, f"vh_{no}", unit)

        def p(role):
            v = wavg(f_range["Giá Trị"], f_range["Trọng Số"]) if not f_range.empty else 0.0
            return f"""{title} — GHN, {a_:%d/%m/%Y} – {b_:%d/%m/%Y}, phạm vi {bc_}.
Giá trị bình quân có trọng số: {v:.2f}%. {'Mốc KPI: ' + f'{target:.2f}%.' if target else ''}
{'Chỉ số này càng cao càng tốt.' if hib else 'Chỉ số này càng thấp càng tốt.'}

{ROLE_STYLE[role]}
Ba phần: hiện trạng, điểm nóng theo bưu cục, việc cần làm ngay.
{CLOSE}"""

        sub_head("Nhận định")
        ai_panel(f"vh_{no}", f"Viết nhận định — {title}", p, title)
        return bc_, a_, b_

    if sub == "GTC tổng":
        t_gtc_p = kpi_target([["kpi", "gtc"], ["% gtc"], ["gtc"]], 70.0,
                             exclude=["tts", "tiktok"], bc=st.session_state.get("g_bc", "Tất cả"), ref=REF)
        metric_page("1.1", "GTC tổng", M_GTC, "%", True, BLUE, target=t_gtc_p, value_label="%GTC")

    elif sub == "Tỷ lệ trả hàng":
        t_tra_p = kpi_target([["tra hang"], ["tra"]], 5.0,
                             bc=st.session_state.get("g_bc", "Tất cả"), ref=REF)
        metric_page("1.2", "Tỷ lệ trả hàng", M_TRA, "%", False, BURGUNDY, target=t_tra_p,
                   value_label="%Trả hàng",
                   note="Chỉ số càng thấp càng tốt — thanh xanh nghĩa là dưới ngưỡng.")

    elif sub == "GTB thu tiền":
        metric_page("1.3", "Tỷ lệ GTB thu tiền", M_GTB, "%", True, FOREST, value_label="%GTB",
                   note="Giao thất bại nhưng vẫn thu được tiền — chưa có mốc KPI riêng cho chỉ số này.")

    elif sub == "GTC TikTok Shop":
        t_tts_p = kpi_target([["gtc tts"], ["tts"], ["tiktok"]], 80.0,
                             bc=st.session_state.get("g_bc", "Tất cả"), ref=REF)
        metric_page("1.4", "GTC TikTok Shop", M_TTS, "%", True, BRASS_DP, target=t_tts_p,
                   value_label="%GTC TTS")

    elif sub == "ODR TikTok Shop":
        metric_page("1.5", "ODR TikTok Shop", M_ODR, "%", True, VIOLET, target=98.0,
                   value_label="%ODR",
                   note="Cam kết giao đúng hạn với sàn TikTok Shop — thấp là bị phạt.")

    elif sub == "Sản lượng theo ca":
        bc_, a_, b_ = quick_range(M_CA)
        lh_all = (sorted({x for x in M_CA["Chiều"].dropna().astype(str).str.strip().unique()
                          if x and x.lower() != "nan"}) if "Chiều" in M_CA.columns else [])
        lh_pick = st.multiselect("Loại hàng / ca", lh_all, default=lh_all, key="lh_vh")
        note_head("1.6", "Sản lượng và GTC theo ca làm việc",
                  f"Phạm vi {bc_} · dữ liệu {a_:%d.%m.%Y} – {b_:%d.%m.%Y}")

        s_ca = sl(scope(M_CA, bc_), a_, b_)
        if lh_pick and "Chiều" in s_ca.columns:
            s_ca = s_ca[s_ca["Chiều"].isin(lh_pick)]

        if not s_ca.empty and "Chiều" in s_ca.columns:
            g = (s_ca.assign(_p=s_ca["Giá Trị"].fillna(0) * s_ca["Trọng Số"])
                     .groupby(["Ngày", "Chiều"], as_index=False)
                     .agg(_p=("_p", "sum"), w=("Trọng Số", "sum")))
            g["r"] = np.where(g["w"] > 0, g["_p"] / g["w"], np.nan)

            sub_head("Tổng theo ca trong kỳ")
            rows = []
            for ca in sorted(g["Chiều"].unique()):
                sub_g = g[g["Chiều"] == ca]
                rows.append([ca, f"{sub_g['w'].sum():,.0f} đơn",
                            f"{wavg(sub_g['r'], sub_g['w']):,.2f}%"])
            st.markdown(ledger_table("Tổng theo ca / loại hàng",
                                     ["Ca / loại hàng", "Sản lượng", "%GTC bình quân"], rows),
                        unsafe_allow_html=True)

            cA, cB = st.columns([1.4, 1])
            with cA:
                sub_head("Sản lượng theo ca theo ngày")
                fig = go.Figure()
                shades = [BLUE, BRASS, FOREST, VIOLET]
                for i, ca in enumerate(sorted(g["Chiều"].unique())):
                    sub_g = g[g["Chiều"] == ca]
                    fig.add_trace(go.Bar(x=sub_g["Ngày"], y=sub_g["w"], name=ca,
                                         marker_color=shades[i % 4], marker_line_width=0))
                fig.update_layout(barmode="stack", height=280)
                st.plotly_chart(fig, use_container_width=True)
            with cB:
                sub_head("%GTC theo ca theo ngày")
                fig2 = go.Figure()
                for i, ca in enumerate(sorted(g["Chiều"].unique())):
                    sub_g = g[g["Chiều"] == ca]
                    fig2.add_trace(go.Scatter(x=sub_g["Ngày"], y=sub_g["r"], name=ca, mode="lines",
                                              line=dict(width=2, color=shades[i % 4])))
                fig2.update_yaxes(ticksuffix="%", range=[0, 100])
                fig2.update_layout(height=280)
                st.plotly_chart(fig2, use_container_width=True)

            sub_head("Dữ liệu chi tiết")
            show = s_ca.rename(columns={"Trọng Số": "Sản lượng", "Giá Trị": "%GTC", "Chiều": "Ca/Loại hàng"})
            show = show[["Ngày", "Bưu Cục", "Ca/Loại hàng", "Sản lượng", "%GTC"]].sort_values(
                "Ngày", ascending=False)
            st.dataframe(show, use_container_width=True, hide_index=True, height=280,
                         column_config={"Ngày": st.column_config.DateColumn(format="DD/MM/YYYY"),
                                       "Sản lượng": st.column_config.NumberColumn(format="%,d"),
                                       "%GTC": st.column_config.NumberColumn(format="%.2f%%")})
            st.download_button("Tải CSV dữ liệu chi tiết", show.to_csv(index=False).encode("utf-8-sig"),
                               file_name="vh_1_6_theo_ca.csv", mime="text/csv", key="dl_vh_16")
        else:
            empty("Chưa đọc được cột ca hoặc loại hàng trong sheet theo ca.")

    else:  # "Gán & Leadtime"
        bc_, a_, b_ = quick_range(M_GAN)
        note_head("1.7", "Tỷ lệ gán và thời gian xử lý (Leadtime)",
                  f"Phạm vi {bc_} · dữ liệu {a_:%d.%m.%Y} – {b_:%d.%m.%Y}")
        st.markdown("<div class='fig-cap'>Hai chỉ số này có sẵn trong sheet GTC tổng nhưng chưa nằm "
                    "trong yêu cầu ban đầu — bổ sung theo góp ý.</div>", unsafe_allow_html=True)

        s_gan = sl(scope(M_GAN, bc_), a_, b_)
        s_lead = sl(scope(M_LEAD, bc_), a_, b_)

        cA, cB = st.columns(2)
        with cA:
            sub_head("Tỷ lệ gán — % đơn được gán so với tổng đơn")
            st.markdown(period_ledger("Tỷ lệ gán", scope(M_GAN, bc_), REF, unit="%"),
                        unsafe_allow_html=True)
            if not s_gan.empty:
                g = daily(s_gan)
                fig = px.area(g, x="Ngày", y="Giá Trị")
                fig.update_traces(line=dict(color=CYAN, width=2), fillcolor=hex_fade(CYAN, .08))
                fig.update_yaxes(ticksuffix="%")
                st.plotly_chart(sized(fig, 230), use_container_width=True)
            else:
                empty("Chưa có dữ liệu tỷ lệ gán.")
        with cB:
            sub_head("Leadtime — giờ trung bình xử lý đơn")
            if not s_lead.empty:
                avg_now = float(s_lead["Giá Trị"].mean())
                st.markdown(f"<div class='num tile-num'>{avg_now:,.1f} giờ</div>"
                            f"<div class='tile-delta d-flat'>bình quân {a_:%d/%m} – {b_:%d/%m}</div>",
                            unsafe_allow_html=True)
                g = daily(s_lead)
                fig = px.line(g, x="Ngày", y="Giá Trị", markers=True)
                fig.update_traces(line=dict(color=BRASS, width=2), marker=dict(size=5))
                fig.update_yaxes(title_text="giờ")
                st.plotly_chart(sized(fig, 200), use_container_width=True)
            else:
                empty("Chưa có dữ liệu Leadtime.")

        sub_head("Dữ liệu chi tiết")
        merged = s_gan.rename(columns={"Giá Trị": "%Gán"})[["Ngày", "Bưu Cục", "Trọng Số", "%Gán"]]
        if not s_lead.empty:
            merged = merged.merge(
                s_lead.rename(columns={"Giá Trị": "Leadtime (giờ)"})[["Ngày", "Bưu Cục", "Leadtime (giờ)"]],
                on=["Ngày", "Bưu Cục"], how="outer")
        merged = merged.rename(columns={"Trọng Số": "Sản lượng"}).sort_values("Ngày", ascending=False)
        st.dataframe(merged, use_container_width=True, hide_index=True, height=280,
                     column_config={"Ngày": st.column_config.DateColumn(format="DD/MM/YYYY"),
                                   "Sản lượng": st.column_config.NumberColumn(format="%,d"),
                                   "%Gán": st.column_config.NumberColumn(format="%.2f%%"),
                                   "Leadtime (giờ)": st.column_config.NumberColumn(format="%.2f")})
        st.download_button("Tải CSV dữ liệu chi tiết", merged.to_csv(index=False).encode("utf-8-sig"),
                           file_name="vh_1_7_gan_leadtime.csv", mime="text/csv", key="dl_vh_17")
elif group == "Kinh doanh":

    if sub == "Doanh thu & KPI":
        c1, c2, c3 = st.columns([1.1, 1.6, 1.3])
        with c1:
            bc = page_scope("bc_kd_dt")
        with c2:
            view = st.radio("Gộp theo", ["Ngày", "Tuần", "Tháng"], horizontal=True, key="v_kd")
        lo = M_DT["Ngày"].min() if not M_DT.empty else REF - timedelta(days=60)
        with c3:
            a0, b0 = date_pick("Khoảng ngày", max(lo, REF - timedelta(days=29)), REF, "d_kd")

        note_head("2.1", "Doanh thu và tiến độ KPI", f"Phạm vi {bc} · dữ liệu {a0:%d.%m.%Y} – {b0:%d.%m.%Y}")

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

        sub_head("Doanh thu so với mục tiêu tháng")
        rows_dt = [
            ["Lũy kế đến nay", f"{rev_m/1_000_000:,.1f} tr đ"],
            ["Mục tiêu tháng", f"{target/1_000_000:,.0f} tr đ"],
            ["Dự phóng cuối tháng", f"{forecast/1_000_000:,.1f} tr đ"],
            ["Tháng trước (cùng phạm vi)", f"{rev_pm/1_000_000:,.1f} tr đ"],
        ]
        st.markdown(ledger_table(f"Tháng {mA:%m/%Y} · đã qua {done_days}/{total_days} ngày",
                                 ["Chỉ tiêu", "Giá trị"], rows_dt,
                                 total_row=["Còn thiếu so với mục tiêu",
                                           f"{max(target-forecast,0)/1_000_000:,.1f} tr đ"]),
                    unsafe_allow_html=True)

        sub_head("Nhịp doanh thu theo kỳ — so với kỳ liền trước")
        st.markdown(period_ledger("Doanh thu", dt, REF, how="sum", unit="đ"), unsafe_allow_html=True)

        sub_head(f"Biểu đồ doanh thu — gộp theo {view.lower()}")
        d_range = sl(dt, a0, b0)
        if not d_range.empty:
            plot = d_range.copy()
            if view == "Tuần":
                plot["Ngày"] = plot["Ngày"].dt.to_period("W").apply(lambda r: r.start_time)
            elif view == "Tháng":
                plot["Ngày"] = plot["Ngày"].dt.to_period("M").apply(lambda r: r.start_time)
            plot = plot.groupby("Ngày", as_index=False)["Giá Trị"].sum()
            fig = px.bar(plot, x="Ngày", y="Giá Trị")
            fig.update_traces(marker_color=BLUE, marker_line_width=0, opacity=.9)
            if view == "Tháng":
                fig.add_hline(y=target, line_dash="dot", line_color=BRASS, line_width=1.5,
                              annotation_text="mục tiêu", annotation_position="top left")
            st.plotly_chart(sized(fig, 260), use_container_width=True)
        else:
            empty("Chưa có doanh thu trong khoảng đã chọn.")

        sub_head("Dữ liệu chi tiết")
        if not d_range.empty:
            show = d_range.rename(columns={"Giá Trị": "Doanh thu"})[["Ngày", "Bưu Cục", "Doanh thu"]] \
                .sort_values("Ngày", ascending=False)
            st.dataframe(show, use_container_width=True, hide_index=True, height=260,
                         column_config={"Ngày": st.column_config.DateColumn(format="DD/MM/YYYY"),
                                       "Doanh thu": st.column_config.NumberColumn(format="%,d ₫")})
            st.download_button("Tải CSV dữ liệu chi tiết", show.to_csv(index=False).encode("utf-8-sig"),
                               file_name="kd_2_1_doanh_thu.csv", mime="text/csv", key="dl_kd21")
        else:
            empty("Không có dữ liệu để xuất.")

        def p_kd(role):
            return f"""Kinh doanh GHN, phạm vi {bc}, tháng {mA:%m/%Y}.
Lũy kế {rev_m:,.0f} đ / mục tiêu {target:,.0f} đ. Dự phóng cuối tháng {forecast:,.0f} đ.
Đã qua {done_days}/{total_days} ngày. Tháng trước {rev_pm:,.0f} đ.

{ROLE_STYLE[role]}
Ba phần: tiến độ so với mục tiêu, rủi ro không đạt, việc cần làm ngay để về đích.
{CLOSE}"""

        sub_head("Nhận định")
        ai_panel("kd_dt", "Viết nhận định doanh thu", p_kd, "Doanh thu")

    elif sub == "Khách hàng mới":
        c1, c2 = st.columns([1.2, 2])
        with c1:
            bc = page_scope("bc_kd_khm")
        lo = DF_KHM["Ngày"].min() if not DF_KHM.empty and DF_KHM["Ngày"].notna().any() else REF - timedelta(days=29)
        with c2:
            a0, b0 = date_pick("Khoảng ngày", max(lo, REF - timedelta(days=29)), REF, "d_khm")

        note_head("2.2", "Khách hàng mới", f"Phạm vi {bc} · dữ liệu {a0:%d.%m.%Y} – {b0:%d.%m.%Y}")

        khm = sl(scope(DF_KHM, bc), a0, b0)
        if not khm.empty:
            ncol = pick_col(khm, [["ten kh"], ["ten khach"], ["khach hang"]])
            ccol = pick_col(khm, [["ma kh"], ["ma khach"]])
            rcol = pick_col(khm, [["doanh thu"]])
            vcol = pick_col(khm, VOL_K)
            keys = [c for c in (ccol, ncol) if c]

            if rcol:
                tong = float(khm[rcol].sum())
                sl_ = st.columns(3)
                sl_[0].markdown(f"<div class='eyebrow'>Số khách mới</div>"
                                f"<div class='num tile-num'>{len(khm):,}</div>", unsafe_allow_html=True)
                sl_[1].markdown(f"<div class='eyebrow'>Tổng doanh thu</div>"
                                f"<div class='num tile-num'>{tong/1_000_000:,.1f} tr đ</div>",
                                unsafe_allow_html=True)
                sl_[2].markdown(f"<div class='eyebrow'>Doanh thu bình quân/khách</div>"
                                f"<div class='num tile-num'>{tong/max(len(khm),1)/1_000_000:,.2f} tr đ</div>",
                                unsafe_allow_html=True)
                st.write("")

            if keys and rcol:
                sub_head("Xếp hạng theo doanh thu")
                agg = {rcol: "sum"}
                if vcol:
                    agg[vcol] = "sum"
                t = khm.groupby(keys, as_index=False).agg(agg).sort_values(rcol, ascending=False)
                st.dataframe(t, use_container_width=True, hide_index=True, height=340,
                             column_config={rcol: st.column_config.NumberColumn("Doanh thu", format="%,d ₫")})
                st.download_button("Tải CSV", t.to_csv(index=False).encode("utf-8-sig"),
                                   file_name="kd_2_2_khach_hang_moi.csv", mime="text/csv", key="dl_kd22")
            else:
                sub_head("Dữ liệu chi tiết")
                st.dataframe(khm, use_container_width=True, hide_index=True, height=340)
        else:
            empty("Chưa có khách hàng mới trong kỳ này.")

    elif sub == "Phễu tiếp xúc":
        bc = page_scope("bc_kd_pheu")
        note_head("2.3", "Phễu tiếp xúc khách hàng mới", f"Phạm vi {bc}")

        pheu = scope(DF_PHEU, bc)
        scol = pick_col(pheu, [["trang thai"]])
        cA, cB = st.columns([1, 1.3])
        with cA:
            sub_head("Sơ đồ phễu")
            if not pheu.empty and scol:
                cnt = pheu.groupby(scol).size().reset_index(name="n").sort_values("n", ascending=False)
                fig = go.Figure(go.Funnel(y=cnt[scol], x=cnt["n"], textinfo="value+percent initial",
                                          marker=dict(color=[BLUE, CYAN, VIOLET, SLATE, "#C6CBD2"]),
                                          connector=dict(line=dict(color=RULE, width=1))))
                fig.update_layout(hovermode="closest", margin=dict(l=6, r=6, t=6, b=6), height=340)
                st.plotly_chart(fig, use_container_width=True)
            else:
                empty("Chưa đọc được cột trạng thái trong sheet phễu.")
        with cB:
            sub_head("Số lượng theo trạng thái")
            if not pheu.empty and scol:
                cnt = pheu.groupby(scol).size().reset_index(name="Số lượng").sort_values(
                    "Số lượng", ascending=False)
                st.dataframe(cnt, use_container_width=True, hide_index=True, height=200)
                sub_head("Toàn bộ danh sách")
                st.dataframe(pheu, use_container_width=True, hide_index=True, height=260)
                st.download_button("Tải CSV", pheu.to_csv(index=False).encode("utf-8-sig"),
                                   file_name="kd_2_3_pheu.csv", mime="text/csv", key="dl_kd23")
            else:
                empty("Không có dữ liệu chi tiết.")

    else:  # "Khách hàng tiềm năng"
        bc = page_scope("bc_kd_tn")
        note_head("2.4", "Khách hàng tiềm năng chờ chốt", f"Phạm vi {bc}")

        pheu = scope(DF_PHEU, bc)
        scol = pick_col(pheu, [["trang thai"]])
        if not pheu.empty and scol:
            tn = pheu[pheu[scol].astype(str).map(lambda x: "tiem nang" in norm(x))]
            if not tn.empty:
                drop = [c for c in tn.columns if tn[c].isna().all()]
                tn = tn.drop(columns=drop)
                st.markdown(f"<div class='eyebrow'>Đang có {len(tn)} khách hàng tiềm năng</div>",
                            unsafe_allow_html=True)
                st.dataframe(tn, use_container_width=True, hide_index=True, height=420)
                st.download_button("Tải CSV danh sách", tn.to_csv(index=False).encode("utf-8-sig"),
                                   file_name="kd_2_4_khach_tiem_nang.csv", mime="text/csv", key="dl_kd24")
            else:
                empty("Không có khách nào ở trạng thái tiềm năng.")
        else:
            empty("Cần cột trạng thái để lọc khách tiềm năng.")
elif group == "Năng suất & Lương":
    c1, c2, c3 = st.columns([1.1, 1.3, 1.4])
    with c1:
        bc = page_scope(f"bc_ns_{sub}")
    nv_l, nv_g = pick_col(DF_LUONG, [["nhan vien"]]), pick_col(DF_NSGTC, [["nhan vien"]])
    staff = set()
    for df, col in ((DF_LUONG, nv_l), (DF_NSGTC, nv_g)):
        if col and not df.empty:
            staff |= set(scope(df, bc)[col].dropna().astype(str).str.strip())
    with c2:
        nv = st.selectbox("Nhân viên", ["Tất cả"] + sorted(x for x in staff if x and x != "nan"),
                          key=f"nv_ns_{sub}")
    base = DF_NSGTC if not DF_NSGTC.empty else DF_LUONG
    lo = base["Ngày"].min() if not base.empty and base["Ngày"].notna().any() else REF - timedelta(days=60)
    with c3:
        a0, b0 = date_pick("Khoảng ngày", max(lo, REF - timedelta(days=29)), REF, f"d_ns_{sub}")

    def only(df, col):
        out = scope(df, bc)
        if nv != "Tất cả" and col and not out.empty:
            out = out[out[col].astype(str).str.strip() == nv]
        return out

    L, G = only(DF_LUONG, nv_l), only(DF_NSGTC, nv_g)

    if REF.day <= 15:
        cA_, cB_ = REF.replace(day=1), REF.replace(day=15)
        pB_ = cA_ - timedelta(days=1)
        pA_ = pB_.replace(day=16)
        c_name, p_name = f"Kỳ 20 · {cA_:%m/%Y}", f"Kỳ 05 · {pA_:%m/%Y}"
    else:
        cA_ = REF.replace(day=16)
        cB_ = month_end(cA_)
        pA_, pB_ = REF.replace(day=1), REF.replace(day=15)
        c_name, p_name = f"Kỳ 05 · {cA_:%m/%Y}", f"Kỳ 20 · {pA_:%m/%Y}"

    price = pick_col(L, [["don gia"]])
    gan = pick_col(G, [["gan giao"], ["so don gan"], ["gan"]])
    gtc = pick_col(G, [["giao tinh luong"], ["don gtc"], ["giao thanh cong"], ["gtc"]], exclude=["%"])
    pay = {k: pick_col(L, [[k.lower()], [k.split()[-1].lower()]]) for k in SALARY_PARTS}
    pay = {k: v for k, v in pay.items() if v}

    def cut(df, a, b):
        return df[(df["Ngày"] >= a) & (df["Ngày"] <= b)] if df is not None and not df.empty else pd.DataFrame()

    Lc, Lp, Gc, Gp = cut(L, cA_, cB_), cut(L, pA_, pB_), cut(G, cA_, cB_), cut(G, pA_, pB_)
    Gr, Lr = cut(G, a0, b0), cut(L, a0, b0)

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

    def delta_span(delta: float, suffix: str, decimals: int = 0, hib: bool = True) -> str:
        good = (delta > 0) == hib
        cls = "" if abs(delta) < 1e-9 else ("up" if good else "down")
        arrow = "" if abs(delta) < 1e-9 else ("▲" if delta > 0 else "▼")
        return f"<span class='{cls}'>{arrow} {abs(delta):,.{decimals}f}{suffix}</span>"

    who = f"{bc}{'' if nv == 'Tất cả' else ' · ' + nv}"

    if sub == "Kỳ lương":
        note_head("3.1", "Kỳ lương", f"Phạm vi {who} · {c_name} so với {p_name}")
        st.markdown("<div class='fig-cap'>Kỳ 20 tính từ ngày 01 đến 15, chi lương ngày 20 · Kỳ 05 tính "
                    "từ ngày 16 đến hết tháng, chi lương ngày 05 tháng sau · "
                    "Lương tổng = LHH LTC + LHH GTC + LHH GTBTT</div>", unsafe_allow_html=True)

        rows_ns = [
            ["Đơn giá trung bình", f"{avg_price(Lc):,.0f} đ", f"{avg_price(Lp):,.0f} đ",
             delta_span(avg_price(Lc) - avg_price(Lp), " đ")],
            ["Sản lượng GTC", f"{sum_gtc(Gc):,.0f} đơn", f"{sum_gtc(Gp):,.0f} đơn",
             delta_span(sum_gtc(Gc) - sum_gtc(Gp), " đơn")],
            ["%GTC", f"{pct(Gc):,.2f}%", f"{pct(Gp):,.2f}%", delta_span(pct(Gc) - pct(Gp), " pp", 2)],
        ]
        st.markdown(ledger_table(f"{c_name} so với {p_name}",
                                 ["Chỉ tiêu", "Kỳ này", "Kỳ trước", "Chênh lệch"], rows_ns,
                                 total_row=["Lương tổng", f"{total_pay(Lc):,.0f} đ"]),
                    unsafe_allow_html=True)

        sub_head("Dữ liệu chi tiết kỳ hiện tại")
        if not Lc.empty:
            cols = [c for c in [nv_l, price, *pay.values()] if c]
            show = Lc[["Ngày", "Bưu Cục"] + cols].sort_values("Ngày", ascending=False) if cols else Lc
            st.dataframe(show, use_container_width=True, hide_index=True, height=280)
            st.download_button("Tải CSV", show.to_csv(index=False).encode("utf-8-sig"),
                               file_name="ns_3_1_ky_luong.csv", mime="text/csv", key="dl_ns31")
        else:
            empty("Không có dữ liệu lương trong kỳ hiện tại.")

        def p_ns(role):
            return f"""Kỳ lương GHN, phạm vi {who}. {c_name} so với {p_name}.
Đơn giá TB {avg_price(Lc):,.0f} đ (kỳ trước {avg_price(Lp):,.0f} đ).
Sản lượng GTC {sum_gtc(Gc):,.0f} đơn (kỳ trước {sum_gtc(Gp):,.0f} đơn).
%GTC {pct(Gc):.2f}% (kỳ trước {pct(Gp):.2f}%). Lương tổng {total_pay(Lc):,.0f} đ.

{ROLE_STYLE[role]}
Ba phần: thu nhập đang lên hay xuống, nguyên nhân nghi ngờ, việc cần làm.
{CLOSE}"""
        sub_head("Nhận định")
        ai_panel("ns_31", "Viết nhận định kỳ lương", p_ns, "Kỳ lương")

    elif sub == "Đơn giá":
        note_head("3.2", "Đơn giá", f"Phạm vi {who} · dữ liệu {a0:%d.%m.%Y} – {b0:%d.%m.%Y}")
        if price and not Lr.empty:
            avg_now = float(Lr[price].mean())
            st.markdown(f"<div class='eyebrow'>Đơn giá bình quân trong khoảng đã chọn</div>"
                        f"<div class='num tile-num'>{avg_now:,.0f} đ</div>", unsafe_allow_html=True)
            sub_head("Biến động theo ngày")
            g = Lr.groupby("Ngày", as_index=False)[price].mean()
            fig = px.line(g, x="Ngày", y=price, markers=True)
            fig.update_traces(line=dict(color=BLUE, width=2), marker=dict(size=5, color=BLUE))
            st.plotly_chart(sized(fig, 280), use_container_width=True)

            if nv_l and nv == "Tất cả":
                sub_head("So sánh đơn giá theo nhân viên")
                r = Lr.groupby(nv_l, as_index=False)[price].mean().sort_values(price)
                fig2 = go.Figure(go.Bar(x=r[price], y=r[nv_l], orientation="h", marker_color=BLUE,
                                        text=[f"{v:,.0f}" for v in r[price]], textposition="outside"))
                fig2.update_layout(height=max(160, 26 * len(r)), margin=dict(l=6, r=44, t=6, b=28))
                st.plotly_chart(fig2, use_container_width=True)

            sub_head("Dữ liệu chi tiết")
            cols = [c for c in [nv_l, price] if c]
            show = Lr[["Ngày", "Bưu Cục"] + cols].sort_values("Ngày", ascending=False)
            st.dataframe(show, use_container_width=True, hide_index=True, height=260)
            st.download_button("Tải CSV", show.to_csv(index=False).encode("utf-8-sig"),
                               file_name="ns_3_2_don_gia.csv", mime="text/csv", key="dl_ns32")
        else:
            empty("Chưa đọc được cột đơn giá.")

    elif sub == "Sản lượng gán & GTC":
        note_head("3.3", "Sản lượng gán và GTC", f"Phạm vi {who} · dữ liệu {a0:%d.%m.%Y} – {b0:%d.%m.%Y}")

        sub_head("Nhịp %GTC theo kỳ — so với kỳ liền trước")
        if gan and gtc and not G.empty:
            gm = pd.DataFrame({"Ngày": G["Ngày"],
                               "Giá Trị": np.where(G[gan] > 0, G[gtc] / G[gan] * 100, np.nan),
                               "Trọng Số": G[gan]})
            st.markdown(period_ledger("%GTC", gm, REF, unit="%"), unsafe_allow_html=True)
        else:
            empty("Chưa đọc được cột số đơn gán hoặc đơn giao tính lương.")

        sub_head("Sản lượng gán, GTC và tỷ lệ theo ngày")
        if gan and gtc and not Gr.empty:
            g = Gr.groupby("Ngày", as_index=False).agg({gan: "sum", gtc: "sum"})
            g["r"] = np.where(g[gan] > 0, g[gtc] / g[gan] * 100, 0.0)
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            fig.add_trace(go.Bar(x=g["Ngày"], y=g[gan], name="Gán", marker_color="#E5E6E0",
                                 marker_line_width=0), secondary_y=False)
            fig.add_trace(go.Bar(x=g["Ngày"], y=g[gtc], name="Giao thành công", marker_color=INK_2,
                                 marker_line_width=0, opacity=.85), secondary_y=False)
            fig.add_trace(go.Scatter(x=g["Ngày"], y=g["r"], name="%GTC", mode="lines+markers",
                                     line=dict(color=BRASS, width=2), marker=dict(size=5)), secondary_y=True)
            fig.update_layout(barmode="overlay")
            fig.update_yaxes(ticksuffix="%", secondary_y=True, showgrid=False, range=[0, 100])
            st.plotly_chart(sized(fig, 280), use_container_width=True)

            sub_head("Dữ liệu chi tiết")
            cols = [c for c in [nv_g, gan, gtc] if c]
            show = Gr[["Ngày", "Bưu Cục"] + cols].sort_values("Ngày", ascending=False)
            st.dataframe(show, use_container_width=True, hide_index=True, height=260)
            st.download_button("Tải CSV", show.to_csv(index=False).encode("utf-8-sig"),
                               file_name="ns_3_3_gan_gtc.csv", mime="text/csv", key="dl_ns33")
        else:
            empty("Chưa đủ dữ liệu gán và giao để vẽ.")

    elif sub == "Lương tổng":
        note_head("3.4", "Lương tổng", f"Phạm vi {who} · dữ liệu {a0:%d.%m.%Y} – {b0:%d.%m.%Y}")
        st.markdown("<div class='fig-cap'>Lương tổng = LHH LTC + LHH GTC + LHH GTBTT</div>",
                    unsafe_allow_html=True)
        if pay and not Lr.empty:
            tmp = Lr.copy()
            tmp["Lương tổng"] = tmp[list(pay.values())].sum(axis=1)
            tong = float(tmp["Lương tổng"].sum())
            st.markdown(f"<div class='eyebrow'>Tổng lương trong khoảng đã chọn</div>"
                        f"<div class='num tile-num'>{tong/1_000_000:,.1f} tr đ</div>", unsafe_allow_html=True)

            sub_head("Biến động theo ngày")
            g = tmp.groupby("Ngày", as_index=False)["Lương tổng"].sum()
            fig = px.area(g, x="Ngày", y="Lương tổng")
            fig.update_traces(line=dict(color=FOREST, width=2), fillcolor=hex_fade(FOREST, .08))
            st.plotly_chart(sized(fig, 260), use_container_width=True)

            sub_head("Cơ cấu 3 thành phần lương")
            parts = {k: float(tmp[v].sum()) for k, v in pay.items()}
            fig2 = go.Figure(go.Bar(x=list(parts.values()), y=list(parts.keys()), orientation="h",
                                    marker_color=[BLUE, BRASS, VIOLET][:len(parts)],
                                    text=[f"{v/1_000_000:,.1f} tr" for v in parts.values()],
                                    textposition="outside"))
            fig2.update_layout(height=160, margin=dict(l=6, r=60, t=6, b=28))
            st.plotly_chart(fig2, use_container_width=True)
            st.caption(" · ".join(f"**{k}**: {v}" for k, v in SALARY_PARTS.items()))

            sub_head("Dữ liệu chi tiết")
            cols = [c for c in [pick_col(L, [["nhan vien"]]), *pay.values()] if c]
            show = tmp[["Ngày", "Bưu Cục"] + cols + ["Lương tổng"]].sort_values("Ngày", ascending=False)
            st.dataframe(show, use_container_width=True, hide_index=True, height=260)
            st.download_button("Tải CSV", show.to_csv(index=False).encode("utf-8-sig"),
                               file_name="ns_3_4_luong_tong.csv", mime="text/csv", key="dl_ns34")
        else:
            empty("Chưa đọc được các cột LHH LTC, LHH GTC, LHH GTBTT.")

    else:  # "Xếp hạng nhân viên"
        note_head("3.5", "Xếp hạng nhân viên", f"Phạm vi {bc} · dữ liệu {a0:%d.%m.%Y} – {b0:%d.%m.%Y} · mốc thưởng 80%")
        if gan and gtc and nv_g and not Gr.empty:
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
            st.download_button("Tải CSV bảng xếp hạng", r.to_csv(index=False).encode("utf-8-sig"),
                               file_name="ns_3_5_xep_hang.csv", mime="text/csv", key="dl_ns35")

            sub_head("Phân bố %GTC toàn đội")
            fig = px.histogram(r, x="%GTC", nbins=12)
            fig.add_vline(x=80, line_dash="dot", line_color=BRASS, line_width=1.5,
                         annotation_text="mốc thưởng")
            fig.update_traces(marker_color=BLUE)
            st.plotly_chart(sized(fig, 220), use_container_width=True)
        else:
            empty("Chưa đủ dữ liệu để xếp hạng nhân viên.")
elif group == "Tiến độ KPI":
    c1, c2 = st.columns([1.1, 2])
    with c1:
        bc = page_scope("bc_kpi")
    with c2:
        a0, b0 = date_pick("Khoảng ngày", REF.replace(day=1), REF, "d_kpi")

    note_head("04", "Tiến độ hoàn thành KPI", f"Phạm vi {bc} · dữ liệu {a0:%d.%m.%Y} – {b0:%d.%m.%Y}")

    t_gtc = kpi_target([["kpi", "gtc"], ["% gtc"], ["gtc"]], 70.0, exclude=["tts", "tiktok"], bc=bc, ref=REF)
    t_tts = kpi_target([["gtc tts"], ["tts"], ["tiktok"]], 80.0, bc=bc, ref=REF)
    t_tra = kpi_target([["tra hang"], ["tra"]], 5.0, bc=bc, ref=REF)

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
        st.download_button("Tải CSV dữ liệu chi tiết", tbl.to_csv(index=False).encode("utf-8-sig"),
                           file_name="kpi_theo_ngay.csv", mime="text/csv", key="dl_kpi")
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
