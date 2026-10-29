"""
TRUNG TÂM VẬN HÀNH — GHN
Dashboard Streamlit: Vận hành · Kinh doanh · Năng suất & Lương · KPI · AI cố vấn

Chạy local:
    pip install -r requirements.txt
    streamlit run app.py

Chạy trên Render:
    streamlit run app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true

Biến môi trường (KHÔNG fix cứng key vào code):
    ANTHROPIC_API_KEY   — khóa Claude (Anthropic). Có khóa này thì app ưu tiên dùng Claude
    ANTHROPIC_MODEL     — mô hình Claude (mặc định claude-opus-5-5; đổi sang claude-sonnet-5-5 để rẻ hơn)
    AI_PROVIDER         — auto (mặc định) | claude | gemini: AI nào được ưu tiên; lỗi thì tự chuyển sang AI còn lại
    GEMINI_API_KEY      — khóa Google Gemini (dự phòng hoặc dùng riêng)
    TELEGRAM_TOKEN      — token bot Telegram (tùy chọn)
    TELEGRAM_CHAT_ID    — id nhóm nhận báo cáo (tùy chọn)
    TELEGRAM_API_BASE   — máy chủ Telegram API (mặc định https://api.telegram.org; chỉ đổi khi test)
    GTALK_OA_TOKEN      — "username:password" của OA GTalk (tùy chọn)
    GTALK_CHANNELS      — các nhóm GTalk nhận tin, JSON {"Tên nhóm": "channelId"} hoặc "Tên=channelId;Tên2=id2"
    GTALK_API_BASE      — mặc định https://mbff.ghn.vn (thật); thử trước ở https://test-api.mbff.ghn.tech
    ADMIN_ID            — tên đăng nhập tài khoản quản trị (mặc định: 3032156)
    ADMIN_PASS          — mật khẩu tài khoản quản trị (mặc định: ghn@admin)
    USER_PASS           — mật khẩu tài khoản USER  (mặc định: ghn@user)
"""

from __future__ import annotations

import base64
import hashlib
import html as html_lib
import io
import json
import os
import re
import threading
import time
import unicodedata
from collections import Counter
import warnings
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from functools import lru_cache

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import requests
from PIL import Image, ImageDraw, ImageFont
from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx
import streamlit as st
from plotly.subplots import make_subplots

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    from google import genai
    from google.genai import types as genai_types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False


# ═══════════════════════════════════════════════════════════════════════
# 0. CẤU HÌNH TRANG
# ═══════════════════════════════════════════════════════════════════════
_APP_ICON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "icon-192.png")
st.set_page_config(
    page_title="Trung Tâm Vận Hành — GHN",
    page_icon=_APP_ICON if os.path.exists(_APP_ICON) else "🚀",
    layout="wide",
    initial_sidebar_state="auto",   # máy tính: mở menu bên trái; điện thoại: thu gọn
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
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
CLAUDE_MODEL = os.environ.get("ANTHROPIC_MODEL", "").strip() or "claude-opus-5-5"
CLAUDE_EFFORT = (os.environ.get("ANTHROPIC_EFFORT", "").strip().lower()
                 if os.environ.get("ANTHROPIC_EFFORT", "").strip().lower() in ("low", "medium", "high", "xhigh", "max")
                 else "medium")
AI_PROVIDER = os.environ.get("AI_PROVIDER", "auto").strip().lower()
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
TELEGRAM_API_BASE = os.environ.get("TELEGRAM_API_BASE", "https://api.telegram.org").strip().rstrip("/")
GTALK_OA_TOKEN = os.environ.get("GTALK_OA_TOKEN", "").strip()
GTALK_API_BASE = os.environ.get("GTALK_API_BASE", "https://mbff.ghn.vn").strip().rstrip("/")
GTALK_CHANNELS_RAW = os.environ.get("GTALK_CHANNELS", "").strip()
ADMIN_ID = os.environ.get("ADMIN_ID", "3032156").strip().upper()
ADMIN_PASS = os.environ.get("ADMIN_PASS", "ghn@admin").strip()
USER_PASS = os.environ.get("USER_PASS", "ghn@user").strip()

GEMINI_MODEL = "gemini-3.6-flash"
# Mô hình dự phòng khi mô hình chính quá tải/hết quota (để trống để tắt). Có thể đổi bằng biến môi trường.
GEMINI_FALLBACK_MODEL = os.environ.get("GEMINI_FALLBACK_MODEL", "gemini-2.5-flash").strip()
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
    "opr_tts": "https://docs.google.com/spreadsheets/d/1lJt4ZXVjIPoUYZF73nsPmVfziJSBXBISUWU1ldSxWH4/edit?gid=505537577",
    # KPI
    "kpi": "https://docs.google.com/spreadsheets/d/1lJt4ZXVjIPoUYZF73nsPmVfziJSBXBISUWU1ldSxWH4/edit?gid=1344197558",
    # Kinh doanh
    "doanh_thu": "https://docs.google.com/spreadsheets/d/1dEC78RcXYcA7e2SVFmjhOfuP-DY57_FXkOCpRpln4vY/edit?gid=339323317",
    "kh_moi": "https://docs.google.com/spreadsheets/d/1dEC78RcXYcA7e2SVFmjhOfuP-DY57_FXkOCpRpln4vY/edit?gid=949412123",
    "pheu_kh": "https://docs.google.com/spreadsheets/d/1dEC78RcXYcA7e2SVFmjhOfuP-DY57_FXkOCpRpln4vY/edit?gid=151781423",
    # Năng suất & Lương
    "ns_luong": "https://docs.google.com/spreadsheets/d/1OemA7cIZM-5AAvsnQuQphNArKw43de27W75Z-Ri6BcQ/edit?gid=2000227799",
    "ns_gtc": "https://docs.google.com/spreadsheets/d/1OemA7cIZM-5AAvsnQuQphNArKw43de27W75Z-Ri6BcQ/edit?gid=1695228663",
    # Năng suất tháng trước (tab "Năng Suất Tháng 07") — dùng cho tab Thi đua
    "ns_thang_truoc": "https://docs.google.com/spreadsheets/d/1OemA7cIZM-5AAvsnQuQphNArKw43de27W75Z-Ri6BcQ/edit?gid=1826894473",
}

# Chốt chặn: mọi nguồn có nhãn thì phải có link, và ngược lại.
# Lần trước thêm nguồn "ns_thang_truoc" mà lệnh chèn link thất bại, chỉ có nhãn được thêm,
# nên app âm thầm trả bảng rỗng và tab Thi đua hiện 0.00% suốt nhiều lượt sửa.
def _kiem_tra_nguon() -> list[str]:
    thieu_link = [k for k in SHEET_LABELS if k not in SHEET_LINKS]
    thieu_nhan = [k for k in SHEET_LINKS if k not in SHEET_LABELS]
    loi = []
    if thieu_link:
        loi.append(f"Thiếu link trong SHEET_LINKS cho: {', '.join(thieu_link)}")
    if thieu_nhan:
        loi.append(f"Thiếu nhãn trong SHEET_LABELS cho: {', '.join(thieu_nhan)}")
    for k, v in SHEET_LINKS.items():
        if "/edit?gid=" not in v and "/export?format=csv" not in v:
            loi.append(f"Link nguồn '{k}' không đúng mẫu, không đổi sang CSV được")
    return loi


SALARY_PARTS = {
    "LHH LTC": "Lương hoa hồng lấy thành công",
    "LHH GTC": "Lương hoa hồng giao thành công",
    "LHH GTBTT": "Lương hoa hồng giao thất bại thu tiền",
}


# ═══════════════════════════════════════════════════════════════════════
# 1. GIAO DIỆN — CSS TÙY CHỈNH
# ═══════════════════════════════════════════════════════════════════════
pio.templates["ghn"] = go.layout.Template(layout=dict(
    font=dict(family="Montserrat, sans-serif", size=15, color=TEXT),
    plot_bgcolor=BG, paper_bgcolor=BG, hovermode="x unified",
    colorway=[PRIMARY, ACCENT, SUCCESS, DANGER, "#00B4D8", "#6C757D"],
    # t=90 chừa chỗ cho tiêu đề; b=120 chừa chỗ cho legend nằm dưới.
    margin=dict(l=70, r=30, t=90, b=120),
    title=dict(x=0, xanchor="left", y=0.97, yanchor="top",
               font=dict(family="Montserrat, sans-serif", size=18, color=PRIMARY)),
    xaxis=dict(showgrid=False, linecolor=LINE, linewidth=1,
               ticks="outside", tickcolor=LINE, tickfont=dict(size=17),
               automargin=True),
    yaxis=dict(showgrid=True, gridcolor="#F1F3F5", zeroline=False, tickfont=dict(size=17),
               automargin=True),
    # Legend nằm DƯỚI biểu đồ. Trước đây đặt y=1.02 (phía trên) nên đè lên tiêu đề.
    # orientation="h" giúp legend tự xuống dòng khi màn hình hẹp, không tràn chữ.
    legend=dict(orientation="h", yanchor="top", y=-0.22, xanchor="left", x=0,
                font=dict(size=15), itemwidth=30),
    hoverlabel=dict(bgcolor=PRIMARY, bordercolor=PRIMARY,
                    font=dict(family="Montserrat, sans-serif", size=15, color="#FFFFFF")),
))
pio.templates.default = "ghn"

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700;800;900&display=swap');

/* ── PHÓNG CỠ CHỮ 1.5 LẦN ────────────────────────────────────────────
   Streamlit dùng rem cho phần lớn thành phần của nó (ô chọn, nút, bảng,
   chat...). Đổi cỡ chữ gốc từ 16px lên 24px là mọi thứ đó tự phóng theo.
   Các cỡ px trong CSS bên dưới đã được nhân sẵn 1.5. */
html {{ font-size: 20px; }}
/* Hệ số cỡ chữ cho các khối tự dựng; đổi theo độ rộng màn hình ở cuối khối CSS. */
:root {{ --fs: 1; }}

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
    color: #FFFFFF !important; font-size: calc(38.25px * var(--fs)); font-weight: 900 !important;
    margin: 0 0 4px 0; text-transform: uppercase; letter-spacing: 0.5px;
}}
.ghn-banner p {{ color: rgba(255,255,255,0.92); font-size: calc(17.75px * var(--fs)); font-weight: 600; margin: 0; }}
.ghn-banner-row {{ display: flex; align-items: center; gap: 24px; flex-wrap: wrap; }}
.ghn-banner-text {{ flex: 1 1 320px; min-width: 0; }}
.ghn-logo-plate {{
    background: #FFFFFF; border-radius: 12px; padding: 10px 18px; flex: 0 0 auto;
    box-shadow: 0 2px 10px rgba(0,0,0,0.18);
}}
.ghn-logo-plate {{ max-width: 100%; box-sizing: border-box; }}
.ghn-logo-plate img {{ height: 50px; width: auto; max-width: 100%; object-fit: contain; display: block; }}
.ghn-banner-row h1 {{ font-size: calc(30.5px * var(--fs)); }}
.ghn-login-logo {{ text-align: center; margin: 40px 0 20px 0; }}
.ghn-login-logo img {{ width: min(360px, 85%); height: auto; }}
@media (max-width: 640px) {{
    .block-container {{ padding-top: 3.2rem; }}
    .ghn-banner {{ padding: 16px 16px; }}
    .ghn-banner-row {{ gap: 14px; }}
    .ghn-banner-row h1 {{ font-size: calc(22px * var(--fs)); }}
    .ghn-banner p {{ font-size: calc(13.5px * var(--fs)); }}
    .ghn-logo-plate {{ width: 100%; padding: 8px 12px; }}
    .ghn-logo-plate img {{ height: auto; width: 100%; max-width: 260px; margin: 0 auto; }}
}}

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
    font-size: calc(16px * var(--fs)); font-weight: 700; color: {MUTED};
    text-transform: uppercase; letter-spacing: 0.4px; margin-bottom: 6px;
}}
.metric-card .m-value {{
    font-size: calc(35.75px * var(--fs)); font-weight: 900; color: {PRIMARY};
    line-height: 1.1; font-variant-numeric: tabular-nums;
}}
.metric-card .m-value.accent {{ color: {ACCENT}; }}
.metric-card .m-delta {{ font-size: calc(16px * var(--fs)); font-weight: 700; margin-top: 6px; }}
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
    font-size: calc(19px * var(--fs)) !important; font-weight: 700 !important; color: {MUTED} !important;
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
    text-transform: uppercase; font-size: calc(15.25px * var(--fs)) !important;
}}
div[data-testid="stDataFrame"] [role="columnheader"] {{
    background-color: {PRIMARY} !important; color: #FFFFFF !important; font-weight: 800 !important;
}}

/* ── Bảng HTML tự dựng ──────────────────────────────────────────────── */
table.ghn-table {{ width: 100%; border-collapse: collapse; margin: 10px 0 16px; font-size: calc(17.25px * var(--fs)); }}
table.ghn-table thead th {{
    background: {PRIMARY}; color: #FFFFFF; font-weight: 800; text-transform: uppercase;
    font-size: calc(15.25px * var(--fs)); padding: 10px 12px; text-align: right; letter-spacing: 0.3px;
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
    font-family: 'Montserrat', sans-serif; font-weight: 800; font-size: calc(16.5px * var(--fs));
    text-transform: uppercase; letter-spacing: 0.4px; padding: 0.4rem 1.4rem;
    min-height: 48px;   /* bằng chiều cao ô chọn/ô nhập để đứng cạnh nhau thì thẳng hàng */
    box-shadow: 0 2px 6px rgba(255,140,0,0.35);
}}
.stButton > button:hover {{ background: #E67E00; color: #FFFFFF; }}
.stDownloadButton > button {{
    background: {BG}; color: {PRIMARY}; border: 2px solid {PRIMARY}; border-radius: 6px;
    font-weight: 800; font-size: calc(15.25px * var(--fs)); text-transform: uppercase;
    padding: 0.4rem 1.4rem; min-height: 48px;
}}
.stDownloadButton > button:hover {{ background: {PRIMARY}; color: #FFFFFF; }}

/* ── Nhãn ô nhập ────────────────────────────────────────────────────── */
label, .stSelectbox label, .stDateInput label, .stMultiSelect label, .stTextArea label {{
    font-family: 'Montserrat', sans-serif !important;
    font-weight: 700 !important; font-size: calc(15.25px * var(--fs)) !important;
    color: {PRIMARY} !important; text-transform: uppercase; letter-spacing: 0.3px;
}}

/* ── Khối cảnh báo / AI ─────────────────────────────────────────────── */
.ghn-alert {{
    background: #FFF; border-left: 5px solid {ACCENT}; border-radius: 8px;
    padding: 16px 20px; margin-bottom: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    font-size: calc(17.75px * var(--fs)); line-height: 1.7;
}}
.ghn-alert.danger {{ border-left-color: {DANGER}; }}
.ghn-alert.ok {{ border-left-color: {SUCCESS}; }}
.ghn-alert .a-tag {{
    display: inline-block; font-size: calc(14px * var(--fs)); font-weight: 800; text-transform: uppercase;
    padding: 2px 10px; border-radius: 12px; margin-right: 8px;
}}
.tag-danger {{ background: #FDECEE; color: {DANGER}; }}
.tag-warn {{ background: #FFF4E5; color: #B36200; }}
.tag-ok {{ background: #E8F6EC; color: {SUCCESS}; }}

/* ── Trạng thái đang xử lý ──────────────────────────────────────────── */
[data-testid="stStatusWidget"] {{
    position: fixed !important;
    top: 12px !important;
    right: 18px !important;
    z-index: 999999 !important;

    /* Ép thành hình chữ nhật, chữ căn giữa cả ngang lẫn dọc */
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    width: 130px !important;
    height: 38px !important;
    min-height: 0 !important;
    padding: 0 !important;
    overflow: hidden !important;
    line-height: 1 !important;

    background: #FFF4E5 !important;
    border: 1px solid {ACCENT} !important;
    border-radius: 8px !important;
    box-shadow: none !important;
}}

/* Ẩn TẤT CẢ phần tử con. Trước đây chỉ ẩn button/svg/label nên các thẻ bọc
   vẫn chiếm chiều cao, làm khung bị cao và chữ bị đẩy xuống đáy. */
[data-testid="stStatusWidget"] * {{
    display: none !important;
}}

[data-testid="stStatusWidget"]::after {{
    content: "Loading…";
    display: block !important;
    font-family: 'Montserrat', sans-serif;
    font-weight: 700;
    font-size: calc(11px * var(--fs));
    color: #B36200;
    letter-spacing: 0.3px;
    line-height: 1;
    white-space: nowrap;
}}

.section-title {{
    font-size: calc(21.75px * var(--fs)); font-weight: 900; color: {PRIMARY};
    text-transform: uppercase; letter-spacing: 0.3px;
    border-left: 5px solid {ACCENT}; padding-left: 12px; margin: 26px 0 12px;
}}
.note-box {{
    background: #F8FBFD; border: 1px dashed {PRIMARY_SOFT}; border-radius: 8px;
    padding: 18px; text-align: center; color: {MUTED}; font-size: calc(16.5px * var(--fs)); font-weight: 600;
    margin: 10px 0;
}}
/* ── Menu bên trái (radio trong sidebar trình bày như menu) ─────────── */
section[data-testid="stSidebar"] {{ background: #FAFBFC; border-right: 1px solid {LINE}; }}
.nav-head {{ font-size: calc(12px * var(--fs)); font-weight: 800; color: {MUTED}; letter-spacing: 1px;
             margin: 4px 0 6px 6px; }}
section[data-testid="stSidebar"] [data-testid="stRadioGroup"] {{ gap: 2px; width: 100%; }}
section[data-testid="stSidebar"] [data-testid="stRadioGroup"] > div {{ width: 100%; }}
section[data-testid="stSidebar"] [data-testid="stRadioOption"] {{
    display: flex !important; width: 100%; box-sizing: border-box; margin: 0; padding: 10px 12px;
    border-radius: 10px; cursor: pointer; transition: background .15s; text-transform: none !important;
}}
section[data-testid="stSidebar"] [data-testid="stRadioOption"]:hover {{ background: #EEF4F8; }}
/* ẩn nút tròn của radio, chỉ giữ chữ + biểu tượng */
section[data-testid="stSidebar"] [data-testid="stRadioOption"] > div > div:first-child {{ display: none; }}
section[data-testid="stSidebar"] [data-testid="stRadioOption"] p {{
    font-size: calc(17px * var(--fs)) !important; font-weight: 700; color: {TEXT} !important;
    text-transform: none !important; letter-spacing: 0;
}}
section[data-testid="stSidebar"] [data-testid="stRadioOption"] p span[role="img"] {{
    margin-right: 8px; color: {MUTED};
}}
section[data-testid="stSidebar"] [data-testid="stRadioOption"][data-selected="true"] {{ background: #FFF1E3; }}
section[data-testid="stSidebar"] [data-testid="stRadioOption"][data-selected="true"] p,
section[data-testid="stSidebar"] [data-testid="stRadioOption"][data-selected="true"] p span[role="img"] {{
    color: {ACCENT} !important; font-weight: 800;
}}
.ghn-hero-title {{
    color: #FFFFFF; margin: 0; font-size: calc(28px * var(--fs)); font-weight: 900; line-height: 1.2;
    text-transform: uppercase; letter-spacing: 0.5px; text-shadow: 0 1px 3px rgba(0,0,0,0.28);
    font-family: 'Montserrat', sans-serif;
}}

/* ── TỰ CO GIÃN THEO MÀN HÌNH ──────────────────────────────────────────
   Màn lớn (≥1800px): phóng chữ và ô nhập cho dễ đọc từ xa.
   Máy tính bảng / laptop nhỏ (≤1100px): thanh tab xuống dòng để thấy đủ các tab,
   các cột hẹp tự xuống hàng thay vì bị bóp.
   Điện thoại (≤640px): thu gọn banner, lề, cỡ chữ. Streamlit tự xếp cột thành một cột. */
@media (min-width: 1800px) {{
    html {{ font-size: 22px; }}
    :root {{ --fs: 1.12; }}
    .ghn-logo-plate img {{ height: 58px; }}
}}
@media (min-width: 2400px) {{
    html {{ font-size: 24px; }}
    :root {{ --fs: 1.25; }}
    .block-container {{ padding-left: 2.4rem; padding-right: 2.4rem; }}
    .ghn-logo-plate img {{ height: 66px; }}
}}
@media (max-width: 1100px) {{
    :root {{ --fs: 0.94; }}
    .stTabs [role="tablist"] {{ flex-wrap: wrap; row-gap: 4px; }}
    .stTabs [role="tab"] {{ padding: 0 12px; }}
    [data-testid="stHorizontalBlock"] {{ flex-wrap: wrap; }}
    [data-testid="stColumn"] {{ min-width: min(230px, 100%); }}
    .ghn-logo-plate img {{ height: 40px; }}
    .ghn-banner h1, .ghn-banner-row h1 {{ font-size: calc(26px * var(--fs)); }}
}}
@media (max-width: 640px) {{
    html {{ font-size: 18px; }}
    :root {{ --fs: 0.86; }}
    .block-container {{ padding-left: 0.8rem; padding-right: 0.8rem; }}
    .stTabs [role="tab"] {{ padding: 0 7px; height: 36px; min-height: 0; }}
    .stTabs [role="tab"] p {{ font-size: 13.5px !important; }}
    .ghn-banner {{ margin-bottom: 14px; }}
    .ghn-banner-row h1 {{ font-size: calc(22px * var(--fs)); }}
    .ghn-alert {{ padding: 12px 14px; line-height: 1.55; }}
    .metric-card {{ padding: 12px 14px; }}
    .section-title {{ margin: 20px 0 10px; }}
    table.ghn-table th, table.ghn-table td {{ padding: 8px 6px; }}
    .ghn-hero {{ padding: 14px 16px !important; }}
    /* Nút mở menu bên trái: hiện rõ thành nút "Menu" màu cam */
    [data-testid="stExpandSidebarButton"] {{
        background: {ACCENT} !important; color: #FFFFFF !important; border-radius: 18px !important;
        padding: 4px 14px 4px 10px !important; width: auto !important; gap: 4px;
    }}
    [data-testid="stExpandSidebarButton"] svg, [data-testid="stExpandSidebarButton"] span {{ color: #FFFFFF !important; }}
    [data-testid="stExpandSidebarButton"]::after {{
        content: "Menu"; font-weight: 800; font-size: 15px; color: #FFFFFF;
    }}
    /* Nhãn dữ liệu trên biểu đồ: màn hẹp chỉ hiện cách một nhãn cho khỏi chồng chữ */
    .stPlotlyChart g.textpoint:nth-child(even),
    .stPlotlyChart g.point:nth-child(even) text.bartext {{ display: none; }}
}}
</style>
""", unsafe_allow_html=True)


# ── Cài dashboard thành app trên điện thoại (PWA) ───────────────────────
# Gắn manifest + biểu tượng vào <head> để "Thêm vào màn hình chính" ra app có logo GHN, mở toàn màn hình.
# File nằm trong static/, được phục vụ tại /app/static/ (bật enableStaticServing ở .streamlit/config.toml).
st.html("""<script>
(function () {
  var h = document.head;
  if (h.querySelector('link[rel="manifest"]')) return;
  function add(tag, attrs) {
    var e = document.createElement(tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    h.appendChild(e);
  }
  add('link', {rel: 'manifest', href: '/app/static/manifest.json'});
  add('link', {rel: 'apple-touch-icon', href: '/app/static/apple-touch-icon.png'});
  add('meta', {name: 'apple-mobile-web-app-capable', content: 'yes'});
  add('meta', {name: 'mobile-web-app-capable', content: 'yes'});
  add('meta', {name: 'apple-mobile-web-app-title', content: 'GHN Dashboard'});
  add('meta', {name: 'apple-mobile-web-app-status-bar-style', content: 'default'});
  add('meta', {name: 'theme-color', content: '#0077B6'});
})();
</script>""", unsafe_allow_javascript=True)

APP_INSTALL_GUIDE = """
**iPhone (Safari)**
1. Mở dashboard bằng **Safari**.
2. Bấm nút **Chia sẻ** (ô vuông có mũi tên lên) ở thanh dưới.
3. Chọn **Thêm vào MH chính** → **Thêm**.

**Android (Chrome)**
1. Mở dashboard bằng **Chrome**.
2. Bấm **⋮** góc trên bên phải.
3. Chọn **Cài đặt ứng dụng** hoặc **Thêm vào màn hình chính** → **Cài đặt**.

Biểu tượng **GHN Dashboard** sẽ nằm trên màn hình chính, mở ra toàn màn hình như một ứng dụng.
Dashboard tự cập nhật khi có bản mới, không cần cài lại.
"""


# ═══════════════════════════════════════════════════════════════════════
# 2. TIỆN ÍCH CHUNG
# ═══════════════════════════════════════════════════════════════════════
def esc(x) -> str:
    return html_lib.escape(str(x))


@lru_cache(maxsize=8192)
def strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFD", str(text))
    out = "".join(c for c in nfkd if unicodedata.category(c) != "Mn")
    return out.replace("đ", "d").replace("Đ", "D")


@lru_cache(maxsize=8192)
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
# Các cột CÓ chữ "ngày" nhưng KHÔNG phải ngày phát sinh dữ liệu.
# Sheet năng suất có cả "Ngày vào làm" đứng TRƯỚC cột "Thời gian"; nếu không loại trừ,
# app sẽ lấy ngày vào làm (2018, 2020, 2022...) làm mốc thời gian và mọi so sánh
# theo tháng đều sai.
DATE_EXCLUDE = ["vao lam", "sinh", "nghi viec", "thu viec", "ky hop dong",
                "bat dau", "ket thuc", "cap nhat", "tao"]
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

    Cách sửa: thử nhiều kiểu, chọn kiểu đọc được NHIỀU dòng hơn.

    Bổ sung: sheet "Năng Suất Tháng 07" ghi ngày dạng '26-07-03' (YY-MM-DD, năm 2 chữ số).
    Kiểu này nếu đọc thường sẽ thành ngày 26 tháng 7 hoặc năm 2003, nên phải thử riêng
    format %y-%m-%d trước.
    """
    s = raw.astype(str).str.strip().replace({"": None, "nan": None, "None": None})

    target = int(s.notna().sum())
    # Kiểu nào đọc được TOÀN BỘ dòng có giá trị thì dừng ngay (kết quả y hệt việc
    # thử hết rồi chọn kiểu tốt nhất), tránh đường đọc từng ô chậm của dateutil.
    attempts = (
        lambda: pd.to_datetime(s, format="%y-%m-%d", errors="coerce"),   # 26-07-03 = 03/07/2026
        lambda: pd.to_datetime(s, format="%Y-%m-%d", errors="coerce"),   # ISO chuẩn
        lambda: pd.to_datetime(s, errors="coerce", dayfirst=False),
        lambda: pd.to_datetime(s, errors="coerce", dayfirst=True),
    )
    best = None
    for attempt in attempts:
        try:
            with warnings.catch_warnings():
                # Cảnh báo "Could not infer format" là bình thường với sheet ghi ngày lẫn kiểu.
                warnings.simplefilter("ignore", UserWarning)
                c = attempt()
        except Exception:  # noqa: BLE001
            continue
        if best is None or c.notna().sum() > best.notna().sum():
            best = c
        if best.notna().sum() >= target:
            break
    return best if best is not None else pd.Series(pd.NaT, index=raw.index)


def _parse_num_col(col: pd.Series) -> pd.Series:
    """parse_num cho cả cột, chỉ parse mỗi giá trị khác nhau một lần."""
    lookup = {u: parse_num(u) for u in col.dropna().unique()}
    return col.map(lookup).astype(float)


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def load_sheet(key: str) -> pd.DataFrame:
    """Đọc 1 sheet, chuẩn hóa cột Ngày / Bưu Cục, ép kiểu số cho các cột còn lại.

    Đọc toàn bộ sheet qua export CSV — không giới hạn range hay số dòng, nên khi
    Google Sheet có thêm ngày mới là dashboard tự lấy được, không phải sửa code.
    """
    resp = requests.get(make_csv_url(SHEET_LINKS[key]), timeout=30)
    resp.raise_for_status()
    df = pd.read_csv(io.BytesIO(resp.content))
    df.columns = df.columns.astype(str).str.strip().str.replace("\xa0", " ", regex=False)
    df = df.loc[:, ~df.columns.str.match(r"^Unnamed")]
    # Google Sheet có thể có hai cột cùng tên. Khi đó df["X"] trả về DataFrame chứ
    # không phải Series, làm mọi phép float()/sum() phía sau đổ vỡ. Giữ cột đầu tiên.
    df = df.loc[:, ~df.columns.duplicated(keep="first")]
    if df.empty:
        return df

    dcol = pick_col(df, DATE_KEYS, exclude=DATE_EXCLUDE)
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
            df[col] = _parse_num_col(df[col])
    return df


def safe_load(key: str) -> pd.DataFrame:
    """Đọc sheet, nuốt lỗi thành bảng rỗng nhưng GHI LẠI lý do thật.

    Trước đây lỗi bị nuốt hoàn toàn nên một nguồn khai báo thiếu link vẫn chỉ hiện
    'không đọc được', rất khó tìm ra. Nay lý do được lưu để hiển thị ở thanh bên.
    """
    errors = st.session_state.setdefault("load_errors", {})
    if key not in SHEET_LINKS:
        errors[key] = f"Chưa khai báo link cho nguồn '{key}' trong SHEET_LINKS."
        return pd.DataFrame()
    if key in errors:          # prefetch_sheets đã thử và thất bại ở lượt chạy này
        return pd.DataFrame()
    try:
        df = load_sheet(key)
    except Exception as exc:  # noqa: BLE001
        errors[key] = f"{type(exc).__name__}: {exc}"
        return pd.DataFrame()
    if _BC_CANON and not df.empty and "Bưu Cục" in df.columns:
        df = df.assign(**{"Bưu Cục": df["Bưu Cục"].map(lambda v: _BC_CANON.get(norm(v), v))})
    return df


# Tên bưu cục chuẩn: norm(tên) -> cách viết xuất hiện nhiều nhất trên mọi sheet.
# Sheet hay gõ lệch ('(QBI) Đông Thuận' thiếu dấu, '( QBI ) Đồng Thuận' thừa dấu cách),
# nếu không gộp thì bộ lọc hiện hai mục cho cùng một bưu cục.
_BC_CANON: dict[str, str] = {}


def build_bc_canon() -> None:
    counts: dict[str, Counter] = {}
    for key in SHEET_LINKS:
        try:
            df = load_sheet(key)
        except Exception:  # noqa: BLE001  (lỗi đã ghi ở prefetch_sheets)
            continue
        if df.empty or "Bưu Cục" not in df.columns:
            continue
        for name, n in df["Bưu Cục"].astype(str).str.strip().value_counts().items():
            if name and name.lower() != "nan":
                counts.setdefault(norm(name), Counter())[name] += n
    _BC_CANON.clear()
    _BC_CANON.update({k: c.most_common(1)[0][0] for k, c in counts.items() if k})


def prefetch_sheets() -> None:
    """Tải song song mọi sheet chưa có trong cache (trước đây tải lần lượt từng cái).
    Sheet đã cache thì trả về gần như tức thì; sheet lỗi được ghi vào load_errors."""
    st.session_state["load_errors"] = {}
    keys = [k for k in SHEET_LINKS]
    ctx = get_script_run_ctx()

    def _work(key: str):
        if ctx is not None:
            add_script_run_ctx(threading.current_thread(), ctx)
        try:
            load_sheet(key)
            return key, None
        except Exception as exc:  # noqa: BLE001
            return key, f"{type(exc).__name__}: {exc}"

    with ThreadPoolExecutor(max_workers=min(8, len(keys))) as pool:
        for key, err in pool.map(_work, keys):
            if err:
                st.session_state["load_errors"][key] = err
    build_bc_canon()


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
    # Gộp các cách viết khác nhau của cùng một bưu cục (khác dấu, khác khoảng trắng).
    by_key: dict[str, str] = {}
    for v in sorted(vals):
        by_key.setdefault(norm(v), _BC_CANON.get(norm(v), v))
    return ["Tất cả"] + sorted(by_key.values())


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


LABEL_FONT = dict(size=12)


def point_labels(values, fmt, max_labels: int = 16, offset: int = 0) -> list[str]:
    """Nhãn dữ liệu cho từng điểm. Nhiều điểm quá thì cách vài điểm ghi một nhãn (luôn ghi điểm cuối)
    để nhãn không đè lên nhau; di chuột vẫn xem được số của mọi điểm.
    `offset` lệch vị trí ghi nhãn giữa các đường trên cùng biểu đồ để nhãn so le nhau."""
    vals = list(values)
    n = len(vals)
    step = max(1, -(-n // max_labels))
    out = []
    for i, v in enumerate(vals):
        keep = i == n - 1 or ((i + offset) % step == 0 and n - 1 - i >= max(1, step // 2))
        out.append(fmt(v) if keep and v is not None and pd.notna(v) else "")
    return out


def label_layout(series_values: list, gap: float = 12.0) -> list[tuple[str, int]]:
    """Vị trí nhãn cho biểu đồ nhiều đường: đường nằm sát ngay dưới một đường khác thì ghi nhãn
    phía dưới và so le điểm ghi nhãn, tránh hai hàng nhãn chồng lên nhau. Trả (textposition, offset)."""
    means = [float(pd.to_numeric(pd.Series(v), errors="coerce").mean()) for v in series_values]
    out = []
    for i, m in enumerate(means):
        sat_tren = any(j != i and 0 <= mj - m < gap and (mj > m or j < i) for j, mj in enumerate(means))
        out.append(("bottom center", 1) if sat_tren else ("top center", 0))
    return out


def band_axes(fig, bar_max: float, roomy: bool = False) -> None:
    """Biểu đồ cột + đường % (hai trục): dồn cột xuống ~60% chiều cao dưới, đường % lên dải trên,
    để nhãn số của cột và nhãn % của đường không đè lên nhau. `roomy`: dải % rộng hơn khi có 2 đường %."""
    fig.update_yaxes(range=[0, max(float(bar_max), 1.0) * (1.9 if roomy else 1.6)], secondary_y=False)
    fig.update_yaxes(range=[-105, 108] if roomy else [-140, 108], tickvals=[0, 50, 100],
                     ticktext=["0%", "50%", "100%"], secondary_y=True)


def pct_label(v) -> str:
    return f"{v:.1f}%"


def num_label(v) -> str:
    return f"{v:,.0f}"


def money_label(v) -> str:
    return fmt_money(v, full=False)


def line_chart(df: pd.DataFrame, title: str, color: str, unit="%", target: float | None = None,
               y_title: str | None = None):
    if df is None or df.empty:
        note(f"Chưa có dữ liệu: {title}")
        return
    g = daily(df) if unit == "%" else daily(df, "sum")
    fig = px.line(g, x="Ngày", y="Giá Trị", markers=True, title=title)
    fig.update_traces(line=dict(color=color, width=3),
                      marker=dict(size=7, color=color, line=dict(width=2, color="#FFF")),
                      mode="lines+markers+text",
                      text=point_labels(g["Giá Trị"], pct_label if unit == "%" else num_label),
                      textposition="top center", textfont=dict(color=color, **LABEL_FONT),
                      cliponaxis=False)
    if target:
        fig.add_hline(y=target, line_dash="dot", line_color=ACCENT, line_width=2,
                      annotation_text="Mốc KPI", annotation_position="top left")
    fig.update_yaxes(ticksuffix="%" if unit == "%" else "",
                     title_text=y_title or ("Tỷ lệ (%)" if unit == "%" else "Giá trị"))
    fig.update_xaxes(tickformat="%d/%m", title_text=None)
    fig.update_layout(height=320, showlegend=False, margin=dict(t=90, b=70))
    st.plotly_chart(fig, width="stretch")
    if len(g) < 2:
        st.caption("Mới có 1 ngày dữ liệu nên chưa vẽ được đường diễn biến.")


def combo_chart(df: pd.DataFrame, title: str, bar_name="Sản lượng", line_name="% GTC",
                target: float | None = None, gan_df: pd.DataFrame | None = None, max_labels: int = 16):
    """Cột sản lượng + đường %GTC (+ đường % gán đơn nếu có `gan_df`) theo ngày, hai trục."""
    if df is None or df.empty:
        note(f"Chưa có dữ liệu: {title}")
        return
    g = daily(df)
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=g["Ngày"], y=g["Trọng Số"], name=bar_name,
                         marker_color=PRIMARY, marker_line_width=0,
                         hoverinfo="x+y+name", text=point_labels(g["Trọng Số"], num_label), textposition="inside",
                         insidetextanchor="end", textangle=-90 if len(g) > 10 else 0,
                         textfont=dict(color="#FFFFFF", **LABEL_FONT)), secondary_y=False)
    lines = [(g, line_name, ACCENT, "circle")]
    if gan_df is not None and not gan_df.empty:
        lines.append((daily(gan_df), "% Gán đơn", "#00B4D8", "diamond"))
    # gap=40: đường %GTC nằm dưới đường % gán thì ghi nhãn phía dưới, tránh đè lên đường mốc KPI.
    pos = label_layout([d["Giá Trị"] for d, *_ in lines], gap=40)
    for (d, name, color, sym), (tpos, off) in zip(lines, pos):
        fig.add_trace(go.Scatter(x=d["Ngày"], y=d["Giá Trị"], name=name, mode="lines+markers+text",
                                 line=dict(color=color, width=3),
                                 marker=dict(size=8, symbol=sym, line=dict(width=2, color="#FFF")),
                                 hoverinfo="x+y+name", text=point_labels(d["Giá Trị"], pct_label, max_labels, off),
                                 textposition=tpos, textfont=dict(color=color, **LABEL_FONT), cliponaxis=False),
                      secondary_y=True)
    if target:
        # Mốc vẽ thành đường có tên trong chú thích (add_hline kèm chữ bị lệch chỗ khi có hai trục).
        fig.add_trace(go.Scatter(x=[g["Ngày"].iloc[0], g["Ngày"].iloc[-1]], y=[target, target], mode="lines",
                                 name=f"Mốc KPI {target:g}%", hoverinfo="skip",
                                 line=dict(color=DANGER, width=2, dash="dot")), secondary_y=True)
    fig.update_layout(title=title, height=490)
    fig.update_yaxes(title_text=bar_name, secondary_y=False)
    fig.update_yaxes(title_text="Tỷ lệ (%)", secondary_y=True, ticksuffix="%", showgrid=False)
    band_axes(fig, g["Trọng Số"].max(), roomy=len(lines) > 1)
    fig.update_xaxes(tickformat="%d/%m")
    st.plotly_chart(fig, width="stretch")


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
                           textfont=dict(size=17), cliponaxis=False,
                           customdata=g["w"],
                           hovertemplate="%{y}<br>%{x:.2f}%<br>Sản lượng %{customdata:,.0f} đơn<extra></extra>"))
    if target:
        fig.add_vline(x=target, line_dash="dot", line_color=ACCENT, line_width=2)
    # Nới trục ngang thêm 22% so với giá trị lớn nhất để nhãn số đặt ngoài đầu cột
    # không bị cắt. Cỡ chữ đã phóng 1.5 lần nên nhãn chiếm nhiều chỗ hơn trước.
    x_max = float(max(g["r"].max(), target or 0))
    fig.update_xaxes(range=[0, x_max * 1.22], ticksuffix="%", automargin=True)
    fig.update_yaxes(automargin=True, tickfont=dict(size=17))
    fig.update_layout(title=title,
                      height=max(300, 110 * len(g) + 130),
                      margin=dict(l=20, r=120, t=90, b=60),
                      showlegend=False, bargap=0.45)
    st.plotly_chart(fig, width="stretch")


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
                "font": {"size": 39, "color": needle, "family": "Montserrat, sans-serif"}},
        # "position": "bottom" xếp delta XUỐNG DƯỚI số chính. Mặc định Plotly đặt
        # delta nằm cạnh số, khiến cụm số bị đẩy lệch sang một bên tâm đồng hồ.
        delta={"reference": target, "suffix": " pp", "position": "bottom",
               "font": {"size": 17, "family": "Montserrat, sans-serif"},
               "increasing": {"color": SUCCESS if higher_is_better else DANGER},
               "decreasing": {"color": DANGER if higher_is_better else SUCCESS}},
        title={"text": f"<b>{esc(title)}</b>",
               "font": {"size": 19, "color": PRIMARY, "family": "Montserrat, sans-serif"},
               "align": "center"},
        gauge={"axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": MUTED},
               "bar": {"color": needle, "thickness": 0.3},
               "bgcolor": BG, "borderwidth": 1, "bordercolor": LINE,
               "steps": steps,
               "threshold": {"line": {"color": PRIMARY, "width": 4},
                             "thickness": 0.85, "value": target}}))
    fig.update_layout(height=360, margin=dict(l=40, r=40, t=90, b=30),
                      showlegend=False)
    st.plotly_chart(fig, width="stretch")


# ═══════════════════════════════════════════════════════════════════════
# 5b. XUẤT ẢNH BẢNG XẾP HẠNG (gửi nhân viên mỗi ngày)
# ═══════════════════════════════════════════════════════════════════════
_ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")


def _rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _font(bold: bool, size: int):
    """Phông Liberation Sans đi kèm trong assets/fonts (có đủ dấu tiếng Việt)."""
    name = "LiberationSans-Bold.ttf" if bold else "LiberationSans-Regular.ttf"
    try:
        return ImageFont.truetype(os.path.join(_ASSETS, "fonts", name), size)
    except OSError:
        return ImageFont.load_default()


_IMG_CACHE: dict[str, bytes] = {}


def img_cache(fn):
    """Nhớ ảnh PNG đã vẽ theo nội dung tham số (tối đa 12 ảnh). Dùng cho các hàm vẽ ảnh vì chúng được gọi
    theo yêu cầu (bấm tải/xem trước/gửi), kể cả từ luồng riêng của nút tải mà st.cache_data không hợp."""
    def wrapper(*args, **kw):
        h = hashlib.sha1(fn.__name__.encode())
        for a in list(args) + [kw[k] for k in sorted(kw)]:
            if isinstance(a, pd.DataFrame):
                h.update(pd.util.hash_pandas_object(a, index=True).values.tobytes())
                h.update("|".join(map(str, a.columns)).encode())
            else:
                h.update(repr(a).encode())
        key = h.hexdigest()
        if key not in _IMG_CACHE:
            if len(_IMG_CACHE) >= 12:
                _IMG_CACHE.pop(next(iter(_IMG_CACHE)))
            _IMG_CACHE[key] = fn(*args, **kw)
        return _IMG_CACHE[key]
    wrapper.__name__ = fn.__name__
    return wrapper


MEDAL_RGB = {1: (255, 193, 7), 2: (173, 181, 189), 3: (205, 127, 50)}
MEDAL_BG = {1: (255, 248, 225), 2: (245, 246, 247), 3: (252, 240, 230)}


def _fit_text(d, text: str, font, max_w: float) -> str:
    """Cắt bớt chữ và thêm '…' nếu dài hơn max_w."""
    if d.textlength(text, font=font) <= max_w:
        return text
    while text and d.textlength(text + "…", font=font) > max_w:
        text = text[:-1]
    return text + "…"


def _draw_header(img, d, W: int, title: str, subtitle: str, S: int, head_h: int) -> None:
    """Đầu ảnh dùng chung: nền xanh, logo trên tấm trắng, tiêu đề, dải cam dưới cùng."""
    PAD = 40 * S
    d.rectangle([0, 0, W, head_h], fill=_rgb(PRIMARY))
    d.rectangle([0, head_h - 8 * S, W, head_h], fill=_rgb(ACCENT))
    x_text = PAD
    try:
        logo = Image.open(os.path.join(_ASSETS, "logo.png")).convert("RGBA")
        lh = 72 * S
        logo = logo.resize((round(logo.width * lh / logo.height), lh), Image.LANCZOS)
        px, py = 18 * S, 14 * S
        plate_w, plate_h = logo.width + 2 * px, lh + 2 * py
        y0 = (head_h - 8 * S - plate_h) // 2
        d.rounded_rectangle([PAD, y0, PAD + plate_w, y0 + plate_h], radius=14 * S, fill=(255, 255, 255))
        img.paste(logo, (PAD + px, y0 + py), logo)
        x_text = PAD + plate_w + 36 * S
    except OSError:
        pass
    max_w = W - x_text - PAD
    size = 40
    f_title = _font(True, size * S)
    while size > 26 and d.textlength(title, font=f_title) > max_w:   # tiêu đề dài thì thu nhỏ
        size -= 2
        f_title = _font(True, size * S)
    f_sub = _font(False, 25 * S)
    d.text((x_text, 38 * S), _fit_text(d, title, f_title, max_w), font=f_title, fill=(255, 255, 255))
    d.text((x_text, 38 * S + 62 * S), _fit_text(d, subtitle, f_sub, max_w), font=f_sub,
           fill=(225, 240, 250))


def _png_bytes(img) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG", compress_level=6)   # optimize=True chậm gấp ~3 lần mà chỉ nhẹ hơn ~2%
    return buf.getvalue()


@img_cache
def render_rank_image(rows: pd.DataFrame, title: str, subtitle: str, footer: str,
                      threshold: float = 80.0) -> bytes:
    """Vẽ bảng xếp hạng thành ảnh PNG để gửi nhân viên.
    `rows` gồm các cột: Hạng (int), Nhân viên, Đơn gán, Đơn GTC, %GTC."""
    S = 2                                   # vẽ gấp đôi rồi giữ nguyên độ phân giải cho nét
    W, PAD = 1400 * S, 40 * S
    HEAD_H, TH_H, ROW_H, FOOT_H = 170 * S, 66 * S, 62 * S, 70 * S
    n = len(rows)
    H = HEAD_H + 24 * S + TH_H + ROW_H * n + FOOT_H

    c_primary, c_accent = _rgb(PRIMARY), _rgb(ACCENT)
    c_text, c_muted, c_line = _rgb(TEXT), _rgb(MUTED), _rgb(LINE)
    c_ok, c_zebra = _rgb(SUCCESS), (247, 250, 252)
    medal, medal_bg = MEDAL_RGB, MEDAL_BG

    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    f_th, f_td, f_tdb = _font(True, 22 * S), _font(False, 26 * S), _font(True, 26 * S)
    f_small = _font(False, 21 * S)

    def text_w(t, f):
        return d.textlength(t, font=f)

    def fit(t, f, max_w):
        if text_w(t, f) <= max_w:
            return t
        while t and text_w(t + "…", f) > max_w:
            t = t[:-1]
        return t + "…"

    _draw_header(img, d, W, title, subtitle, S, HEAD_H)

    # ── Cột ──
    x_rank, x_name = PAD + 14 * S, PAD + 130 * S
    r_gan, r_gtc = 790 * S, 945 * S
    x_bar, bar_w = 975 * S, 140 * S
    x_pct_r = 1245 * S

    y = HEAD_H + 24 * S
    d.rectangle([PAD, y, W - PAD, y + TH_H], fill=(232, 243, 250))
    mid = y + TH_H // 2
    d.text((x_rank, mid), "HẠNG", font=f_th, fill=c_primary, anchor="lm")
    d.text((x_name, mid), "NHÂN VIÊN", font=f_th, fill=c_primary, anchor="lm")
    d.text((r_gan, mid), "ĐƠN GÁN", font=f_th, fill=c_primary, anchor="rm")
    d.text((r_gtc, mid), "ĐƠN GTC", font=f_th, fill=c_primary, anchor="rm")
    d.text((x_bar, mid), "%GTC", font=f_th, fill=c_primary, anchor="lm")
    d.text((W - PAD - 14 * S, mid), "MỤC TIÊU ≥ 80%", font=f_th, fill=c_primary, anchor="rm")
    y += TH_H

    # ── Dòng dữ liệu ──
    for i, r in enumerate(rows.itertuples(index=False)):
        rank_no = int(r[0])
        top = rank_no in medal
        bg = medal_bg[rank_no] if top else (c_zebra if i % 2 else (255, 255, 255))
        d.rectangle([PAD, y, W - PAD, y + ROW_H], fill=bg)
        d.line([PAD, y + ROW_H, W - PAD, y + ROW_H], fill=c_line, width=S)
        cy = y + ROW_H // 2
        if top:
            rad = 21 * S
            cx = x_rank + rad
            d.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], fill=medal[rank_no])
            d.text((cx, cy), str(rank_no), font=f_tdb, fill=(255, 255, 255), anchor="mm")
        else:
            d.text((x_rank + 21 * S, cy), str(rank_no), font=f_td, fill=c_muted, anchor="mm")
        name = fit(str(r[1]), f_tdb if top else f_td, r_gan - x_name - 150 * S)
        d.text((x_name, cy), name, font=f_tdb if top else f_td, fill=c_text, anchor="lm")
        d.text((r_gan, cy), f"{int(r[2]):,}", font=f_td, fill=c_text, anchor="rm")
        d.text((r_gtc, cy), f"{int(r[3]):,}", font=f_td, fill=c_text, anchor="rm")
        pct = float(r[4])
        passed = pct >= threshold
        bh = 16 * S
        d.rounded_rectangle([x_bar, cy - bh // 2, x_bar + bar_w, cy + bh // 2], radius=bh // 2,
                            fill=(233, 236, 239))
        fill_w = max(bh, round(bar_w * min(max(pct, 0.0), 100.0) / 100.0))
        d.rounded_rectangle([x_bar, cy - bh // 2, x_bar + fill_w, cy + bh // 2], radius=bh // 2,
                            fill=c_ok if passed else c_accent)
        d.text((x_pct_r, cy), f"{pct:.2f}%", font=f_tdb, fill=c_ok if passed else c_text, anchor="rm")
        label = "Đạt" if passed else "Chưa"
        pw, ph = 84 * S, 38 * S
        px1 = W - PAD - 14 * S
        d.rounded_rectangle([px1 - pw, cy - ph // 2, px1, cy + ph // 2], radius=ph // 2,
                            fill=c_ok if passed else (233, 236, 239))
        d.text((px1 - pw // 2, cy), label, font=_font(True, 22 * S),
               fill=(255, 255, 255) if passed else c_muted, anchor="mm")
        y += ROW_H

    d.text((PAD, y + FOOT_H // 2), footer, font=f_small, fill=c_muted, anchor="lm")
    d.rectangle([PAD, y + FOOT_H - 4 * S, W - PAD, y + FOOT_H - 1 * S], fill=c_primary)

    buf = io.BytesIO()
    img.save(buf, format="PNG", compress_level=6)   # optimize=True chậm gấp ~3 lần mà chỉ nhẹ hơn ~2%
    return buf.getvalue()



@img_cache
def render_podium_image(cards: list, title: str, subtitle: str, footer: str) -> bytes:
    """Ảnh vinh danh top 3. Mỗi phần tử `cards`: dict(rank, name, pct, prize, detail)."""
    S = 2
    W, PAD = 1400 * S, 40 * S
    HEAD_H, CARD_H, FOOT_H = 170 * S, 372 * S, 70 * S
    H = HEAD_H + 40 * S + CARD_H + FOOT_H + 10 * S
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    _draw_header(img, d, W, title, subtitle, S, HEAD_H)

    gap = 30 * S
    card_w = (W - 2 * PAD - 2 * gap) // 3
    y0 = HEAD_H + 40 * S
    f_name, f_pct = _font(True, 27 * S), _font(True, 54 * S)
    f_prize, f_det, f_rank = _font(True, 28 * S), _font(False, 20 * S), _font(True, 40 * S)
    c_ok, c_muted, c_text = _rgb(SUCCESS), _rgb(MUTED), _rgb(TEXT)

    # Bục: hạng 1 ở giữa, hạng 2 bên trái, hạng 3 bên phải.
    slot = {2: 0, 1: 1, 3: 2}
    for c in cards:
        rank = int(c["rank"])
        x0 = PAD + slot.get(rank, 0) * (card_w + gap)
        x1 = x0 + card_w
        lift = 0 if rank == 1 else 24 * S
        top = y0 + lift
        d.rounded_rectangle([x0, top, x1, y0 + CARD_H], radius=18 * S,
                            fill=MEDAL_BG.get(rank, (247, 250, 252)),
                            outline=MEDAL_RGB.get(rank, _rgb(LINE)), width=3 * S)
        cx = (x0 + x1) // 2
        rad = 38 * S
        cy = top + 30 * S + rad
        d.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], fill=MEDAL_RGB.get(rank, c_muted))
        d.text((cx, cy), str(rank), font=f_rank, fill=(255, 255, 255), anchor="mm")
        y = cy + rad + 34 * S
        d.text((cx, y), _fit_text(d, str(c["name"]), f_name, card_w - 40 * S), font=f_name,
               fill=c_text, anchor="mm")
        y += 64 * S
        d.text((cx, y), f"{float(c['pct']):.2f}%", font=f_pct, fill=_rgb(PRIMARY), anchor="mm")
        y += 60 * S
        d.text((cx, y), str(c["prize"]), font=f_prize, fill=c_ok, anchor="mm")
        y += 42 * S
        d.text((cx, y), _fit_text(d, str(c["detail"]), f_det, card_w - 30 * S), font=f_det,
               fill=c_muted, anchor="mm")

    yf = y0 + CARD_H
    d.text((PAD, yf + FOOT_H // 2), footer, font=_font(False, 21 * S), fill=c_muted, anchor="lm")
    d.rectangle([PAD, yf + FOOT_H - 4 * S, W - PAD, yf + FOOT_H - 1 * S], fill=_rgb(PRIMARY))
    return _png_bytes(img)


@img_cache
def render_td_table_image(rows: pd.DataFrame, title: str, subtitle: str, footer: str,
                          now_label: str, prev_label: str, prize_header: str = "THƯỞNG") -> bytes:
    """Ảnh bảng xếp hạng thi đua chi tiết.
    `rows` gồm cột: Hạng, Nhân viên, Bưu cục, Gán, GTC, Now, Prev, Cải thiện, Điểm, ĐK, Thưởng, Hạng thưởng."""
    S = 2
    W, PAD = 1900 * S, 36 * S
    HEAD_H, TH_H, ROW_H, FOOT_H = 170 * S, 78 * S, 58 * S, 70 * S
    n = len(rows)
    H = HEAD_H + 24 * S + TH_H + ROW_H * n + FOOT_H
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    _draw_header(img, d, W, title, subtitle, S, HEAD_H)

    c_primary, c_text, c_muted = _rgb(PRIMARY), _rgb(TEXT), _rgb(MUTED)
    c_ok, c_bad, c_line = _rgb(SUCCESS), _rgb(DANGER), _rgb(LINE)
    f_th, f_td, f_tdb = _font(True, 19 * S), _font(False, 23 * S), _font(True, 23 * S)

    # (tiêu đề, mép phải/trái theo đơn vị 1x, căn lề)
    cols = [("HẠNG", 76, "c"), ("NHÂN VIÊN", 126, "l"), ("BƯU CỤC", 520, "l"),
            ("GÁN", 820, "r"), ("GTC", 940, "r"), (now_label, 1110, "r"), (prev_label, 1280, "r"),
            ("CẢI THIỆN", 1430, "r"), ("ĐIỂM", 1530, "r"), ("ĐK ≥80%", 1650, "c"),
            (prize_header, 1846, "r")]
    y = HEAD_H + 24 * S
    d.rectangle([PAD, y, W - PAD, y + TH_H], fill=(232, 243, 250))
    for label, x, al in cols:
        xx = x * S
        # tiêu đề cột %GTC dài: tách 2 dòng
        parts = label.split(" ", 1) if label in (now_label, prev_label) else [label]
        for j, part in enumerate(parts):
            yy = y + TH_H // 2 + (0 if len(parts) == 1 else (-13 if j == 0 else 13) * S)
            anchor = {"l": "lm", "r": "rm", "c": "mm"}[al]
            d.text((xx, yy), part.upper(), font=f_th, fill=c_primary, anchor=anchor)
    y += TH_H

    for i, r in enumerate(rows.itertuples(index=False)):
        (hang, ten, bc, gan, gtc, now, prev, ct, diem, dk, thuong, hang_th) = r
        prized = pd.notna(hang_th)
        bg = MEDAL_BG.get(int(hang_th), (255, 255, 255)) if prized else (
            (247, 250, 252) if i % 2 else (255, 255, 255))
        d.rectangle([PAD, y, W - PAD, y + ROW_H], fill=bg)
        d.line([PAD, y + ROW_H, W - PAD, y + ROW_H], fill=c_line, width=S)
        cy = y + ROW_H // 2
        if prized:
            rad = 19 * S
            d.ellipse([76 * S - rad, cy - rad, 76 * S + rad, cy + rad], fill=MEDAL_RGB[int(hang_th)])
            d.text((76 * S, cy), str(int(hang)), font=f_tdb, fill=(255, 255, 255), anchor="mm")
        else:
            d.text((76 * S, cy), str(int(hang)), font=f_td, fill=c_muted, anchor="mm")
        fn = f_tdb if prized else f_td
        d.text((126 * S, cy), _fit_text(d, str(ten), fn, 384 * S), font=fn, fill=c_text, anchor="lm")
        d.text((520 * S, cy), _fit_text(d, str(bc), f_td, 210 * S), font=f_td, fill=c_muted, anchor="lm")
        d.text((820 * S, cy), f"{int(gan):,}", font=f_td, fill=c_text, anchor="rm")
        d.text((940 * S, cy), f"{int(gtc):,}", font=f_td, fill=c_text, anchor="rm")
        d.text((1110 * S, cy), f"{float(now):.2f}%", font=f_tdb,
               fill=c_ok if float(now) >= 80 else c_text, anchor="rm")
        d.text((1280 * S, cy), f"{float(prev):.2f}%", font=f_td, fill=c_muted, anchor="rm")
        d.text((1430 * S, cy), f"{float(ct):+.2f}", font=f_td,
               fill=c_ok if float(ct) >= 0 else c_bad, anchor="rm")
        d.text((1530 * S, cy), f"{float(diem):.2f}", font=f_td, fill=c_text, anchor="rm")
        ok = dk == "Đạt"
        pw, ph = 84 * S, 34 * S
        d.rounded_rectangle([1650 * S - pw // 2, cy - ph // 2, 1650 * S + pw // 2, cy + ph // 2],
                            radius=ph // 2, fill=c_ok if ok else (233, 236, 239))
        d.text((1650 * S, cy), "Đạt" if ok else "Chưa", font=_font(True, 19 * S),
               fill=(255, 255, 255) if ok else c_muted, anchor="mm")
        thuong = str(thuong).replace("Vinh danh hạng", "Hạng")   # cột hẹp
        d.text((1846 * S, cy), _fit_text(d, thuong, f_tdb if prized else f_td, 150 * S),
               font=f_tdb if prized else f_td,
               fill=c_ok if prized else c_muted, anchor="rm")
        y += ROW_H

    d.text((PAD, y + FOOT_H // 2), footer, font=_font(False, 20 * S), fill=c_muted, anchor="lm")
    d.rectangle([PAD, y + FOOT_H - 4 * S, W - PAD, y + FOOT_H - 1 * S], fill=c_primary)
    return _png_bytes(img)


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


_AI_RETRY_CODES = {429, 500, 502, 503, 504}      # lỗi tạm thời: đáng thử lại
_AI_NEXT_MODEL_CODES = _AI_RETRY_CODES | {404}     # thử mô hình dự phòng nếu vẫn lỗi


def _ai_err_code(exc: Exception) -> int | None:
    code = getattr(exc, "code", None)
    if isinstance(code, int):
        return code
    m = re.match(r"\s*(\d{3})\b", str(exc))        # lỗi google-genai có dạng "503 UNAVAILABLE. {...}"
    return int(m.group(1)) if m else None


def _ai_err_text(code: int | None, exc: Exception, model: str) -> str:
    if code in (500, 502, 503, 504):
        return (f"Máy chủ Google AI đang quá tải hoặc tạm gián đoạn (mã {code}). "
                "Đây là lỗi tạm thời từ phía Google, bạn thử lại sau ít phút.")
    if code == 429:
        return "Đã vượt giới hạn lượt dùng Google AI (gọi quá nhanh hoặc hết hạn mức). Đợi một lúc rồi thử lại."
    if code in (401, 403):
        return f"Google AI từ chối khóa GEMINI_API_KEY (mã {code}): sai, hết hạn hoặc chưa được cấp quyền."
    if code == 404:
        return f"Không tìm thấy mô hình AI '{model}'. Kiểm tra lại tên mô hình."
    return "Lỗi Google AI" + (f" (mã {code})" if code else "") + f": {str(exc)[:200]}"


def _ask_gemini(prompt: str) -> tuple[bool, str]:
    """Gọi Gemini. Trả (True, nội dung) nếu thành công, (False, lý do lỗi) nếu không.

    Lỗi tạm thời của Google (503 quá tải, 429, 5xx) được thử lại tự động với thời gian chờ tăng dần,
    sau đó chuyển sang mô hình dự phòng. Lỗi khóa API (400/401/403) thì dừng ngay, không thử lại."""
    if not GENAI_AVAILABLE:
        return False, "Thiếu thư viện. Chạy: pip install google-genai"
    client = genai_client()
    if client is None:
        return False, "Chưa cấu hình GEMINI_API_KEY."
    plan = [(GEMINI_MODEL, 3)]
    if GEMINI_FALLBACK_MODEL and GEMINI_FALLBACK_MODEL != GEMINI_MODEL:
        plan.append((GEMINI_FALLBACK_MODEL, 2))
    first_err = ""
    for model, tries in plan:
        for attempt in range(tries):
            try:
                resp = client.models.generate_content(
                    model=model, contents=prompt,
                    config=genai_types.GenerateContentConfig(max_output_tokens=8192))
            except Exception as exc:  # noqa: BLE001
                code = _ai_err_code(exc)
                first_err = first_err or _ai_err_text(code, exc, model)
                if code in _AI_RETRY_CODES and attempt < tries - 1:
                    time.sleep(2 * (attempt + 1))          # chờ 2s, 4s rồi thử lại
                    continue
                if code in _AI_NEXT_MODEL_CODES:
                    break                                   # sang mô hình dự phòng
                return False, first_err                     # lỗi khóa/yêu cầu: thử lại cũng vô ích
            if not getattr(resp, "candidates", None):
                return False, "AI không trả về nội dung. Thử lại."
            text = (resp.text or "").strip()
            return (True, text) if text else (False, "AI trả về nội dung rỗng.")
    return False, first_err + " Hệ thống đã tự thử lại nhưng chưa được."


@st.cache_resource
def claude_client():
    if not ANTHROPIC_AVAILABLE or not ANTHROPIC_API_KEY:
        return None
    try:
        # SDK tự thử lại 3 lần với lỗi tạm thời (429, 5xx, mất kết nối) nên không cần vòng thử lại riêng.
        return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, max_retries=3, timeout=180.0)
    except Exception:  # noqa: BLE001
        return None


def _ask_claude(prompt: str) -> tuple[bool, str]:
    """Gọi Claude (Anthropic). Trả (True, nội dung) hoặc (False, lý do lỗi bằng tiếng Việt)."""
    if not ANTHROPIC_AVAILABLE:
        return False, "Thiếu thư viện. Chạy: pip install anthropic"
    client = claude_client()
    if client is None:
        return False, "Chưa cấu hình ANTHROPIC_API_KEY."
    # Không gửi `thinking`: các mô hình Claude mới tự suy luận; độ sâu điều khiển bằng effort.
    kwargs = dict(model=CLAUDE_MODEL, max_tokens=16000, output_config={"effort": CLAUDE_EFFORT},
                  messages=[{"role": "user", "content": prompt}])
    try:
        if CLAUDE_MODEL.startswith(("claude-opus-5", "claude-sonnet-5-5", "claude-fable")):
            # Nếu bộ lọc an toàn từ chối nhầm, máy chủ tự chạy lại trên mô hình dự phòng.
            try:
                resp = client.beta.messages.create(
                    betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs)
            except anthropic.BadRequestError as exc:
                if "fallback" not in str(exc).lower() and "beta" not in str(exc).lower():
                    raise
                resp = client.messages.create(**kwargs)       # tài khoản/nền tảng chưa hỗ trợ fallbacks
        else:
            resp = client.messages.create(**kwargs)
    except anthropic.AuthenticationError:
        return False, "Anthropic từ chối khóa ANTHROPIC_API_KEY (sai hoặc đã bị thu hồi)."
    except anthropic.PermissionDeniedError:
        return False, f"Khóa ANTHROPIC_API_KEY không có quyền dùng mô hình {CLAUDE_MODEL}."
    except anthropic.NotFoundError:
        return False, f"Không tìm thấy mô hình Claude '{CLAUDE_MODEL}'. Kiểm tra biến ANTHROPIC_MODEL."
    except anthropic.RateLimitError:
        return False, "Đã vượt giới hạn lượt dùng Claude (mã 429). Thử lại sau ít phút."
    except anthropic.APIConnectionError:
        return False, "Không kết nối được tới máy chủ Claude. Kiểm tra mạng rồi thử lại."
    except anthropic.APIStatusError as exc:
        if exc.status_code >= 500:
            return False, (f"Máy chủ Claude đang quá tải hoặc tạm gián đoạn (mã {exc.status_code}). "
                           "Thử lại sau ít phút.")
        body = exc.body if isinstance(exc.body, dict) else {}
        detail = str((body.get("error") or {}).get("message") or exc.message)[:200]
        if "credit balance" in detail.lower():
            return False, ("Tài khoản Anthropic đã hết tín dụng. Nạp thêm tại console.anthropic.com "
                           "(mục Plans & Billing) rồi thử lại.")
        return False, f"Claude từ chối yêu cầu (mã {exc.status_code}): {detail}"
    except Exception as exc:  # noqa: BLE001
        return False, f"Lỗi Claude: {str(exc)[:200]}"
    if resp.stop_reason == "refusal":
        return False, "Claude từ chối trả lời yêu cầu này (bộ lọc an toàn)."
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    return (True, text) if text else (False, "AI trả về nội dung rỗng.")


def ask_ai_checked(prompt: str) -> tuple[bool, str]:
    """Hỏi AI. Trả (True, nội dung) nếu thành công, (False, lý do lỗi) nếu không — để chỗ nào cần gửi
    ra ngoài (Telegram, GTalk) không nhầm câu báo lỗi với nội dung AI viết.

    Dùng AI nào có khóa: Claude được ưu tiên (đổi bằng AI_PROVIDER). Nếu AI ưu tiên lỗi thì tự thử AI còn lại."""
    available = {"claude": (ANTHROPIC_API_KEY, _ask_claude, "Claude"),
                 "gemini": (GEMINI_API_KEY, _ask_gemini, "Gemini")}
    prefer = AI_PROVIDER if AI_PROVIDER in available else "claude"
    order = [prefer] + [k for k in available if k != prefer]
    order = [k for k in order if available[k][0]]
    if not order:
        return False, ("Chưa cấu hình AI. Thêm ANTHROPIC_API_KEY (Claude) hoặc GEMINI_API_KEY (Gemini) "
                       "trên máy chủ rồi khởi động lại dịch vụ.")
    errors: list[str] = []
    for k in order:
        ok, out = available[k][1](prompt)
        if ok:
            return True, out
        errors.append(f"{available[k][2]}: {out}")
    return False, " | ".join(errors) if len(errors) > 1 else errors[0].split(": ", 1)[1]


def ask_ai(prompt: str) -> str:
    return ask_ai_checked(prompt)[1]


def staff_id(name) -> str:
    """Khóa gộp nhân viên, dùng chung cho mọi tab.

    Các sheet ghi TÊN KHÁC NHAU cho cùng một người:
      sheet lương        : '3029537-Lê Thị Thúy Kiều'
      sheet năng suất    : '3029537_Lê Thị Kiều'
      sheet tháng trước  : '1704766-Lê Minh Tài'
    Khác cả dấu phân cách lẫn cách viết tên, nên gộp theo MÃ NHÂN VIÊN (cụm số ở đầu).
    Nếu không có mã thì rơi về so tên đã bỏ dấu, bỏ '_' và '-'.
    """
    txt = str(name).strip()
    m = re.match(r"^\s*(\d{4,})", txt)
    if m:
        return m.group(1)
    return norm(txt).replace("_", "").replace("-", "").replace(" ", "")


def staff_label(name) -> str:
    """Tên hiển thị: tách mã và tên bằng dấu chấm giữa cho dễ đọc."""
    return re.sub(r"[_\-]+", " · ", str(name).strip(), count=1)


ADVISOR_ROLES = {
    "Giám đốc": (
        "Bạn là Giám đốc vùng. Nhìn ở tầm quản trị: đánh giá bức tranh tổng thể, "
        "nêu rủi ro hệ thống và tác động tới chi phí, cam kết với sàn và uy tín khu vực. "
        "Đề xuất mang tính chiến lược, phân bổ nguồn lực. Giọng chuyên nghiệp, quyết đoán."
    ),
    "Quản lý khu vực": (
        "Bạn là Quản lý khu vực (AM) phụ trách trực tiếp các bưu cục. Nhìn ở tầm điều hành: "
        "chỉ đích danh bưu cục và nhân viên đang có vấn đề, nêu việc phải làm trong 24-48 giờ tới, "
        "gắn người chịu trách nhiệm. Giọng dứt khoát, thực chiến, sát mặt đất."
    ),
}


def ai_advisor(key: str, tab_label: str, data_text: str, extra_note: str = ""):
    """Khối cố vấn AI đặt ở cuối mỗi tab: đọc đúng số liệu đang hiển thị trên tab đó
    rồi đưa ra nhận định và đề xuất hành động theo góc nhìn Giám đốc hoặc AM."""
    section("Cố vấn AI — nhận định và đề xuất hành động")
    c1, c2 = st.columns([1.2, 2.4], vertical_alignment="bottom")
    with c1:
        role = st.selectbox("Góc nhìn", list(ADVISOR_ROLES), key=f"role_{key}")
    with c2:
        run = st.button(f"PHÂN TÍCH {tab_label.upper()}", key=f"btn_adv_{key}",
                        width="stretch")

    if run:
        with st.spinner("AI đang đọc số liệu và soạn nhận định..."):
            prompt = f"""{ADVISOR_ROLES[role]}

Dưới đây là số liệu THỰC TẾ đang hiển thị trên tab "{tab_label}" của dashboard
Trung tâm vận hành GHN:

{data_text}

{extra_note}

QUY ƯỚC CHỈ SỐ:
- %GTC là tỷ lệ giao thành công, càng cao càng tốt.
- ODR là cam kết giao đúng hạn với sàn TikTok Shop, càng cao càng tốt, thấp là bị sàn phạt.
- %Trả hàng là đơn quay đầu về kho, càng thấp càng tốt.
- Mọi tỷ lệ đã tính trung bình có trọng số theo sản lượng.

Trình bày đúng 3 phần, mỗi phần có tiêu đề in đậm:
1. **ĐÁNH GIÁ** — bức tranh hiện tại, nêu con số cụ thể để chứng minh.
2. **VẤN ĐỀ & RỦI RO** — chỉ rõ chỉ số nào đang hỏng, hỏng ở đâu, hệ quả nếu để tiếp.
3. **ĐỀ XUẤT HÀNH ĐỘNG** — tối đa 4 việc, mỗi việc một dòng, ghi rõ làm gì và ai chịu trách nhiệm.

Chỉ dùng số liệu được cung cấp. Nếu thiếu dữ liệu cho phần nào thì ghi rõ "chưa đủ dữ liệu",
tuyệt đối không suy đoán hay bịa số. Viết ngắn gọn. Kết thúc bằng dòng [HẾT]."""
            ok_ai, ai_out = ask_ai_checked(prompt)
            if ok_ai:
                st.session_state.ai_cache[key] = ai_out
            else:
                # Không lưu câu báo lỗi như thể là nhận định (sẽ hiện kèm nút gửi Telegram).
                st.error(ai_out)

    result = st.session_state.ai_cache.get(key)
    if result:
        st.markdown(f"<div class='ghn-alert'>{result}</div>", unsafe_allow_html=True)
        if st.button("GỬI LÊN NHÓM TELEGRAM", key=f"tele_adv_{key}"):
            ok, msg = send_telegram(f"[{tab_label.upper()}]\n\n" + result.replace("*", ""))
            (st.success if ok else st.error)(msg)
    else:
        note("Chọn góc nhìn rồi bấm nút phía trên để AI đọc số liệu đang hiển thị "
             "và đưa ra nhận định kèm đề xuất hành động.")


def _tele_enabled() -> bool:
    return bool(TELEGRAM_TOKEN and TELEGRAM_CHAT_ID)


def _tele_safe(msg) -> str:
    """Che token bot khỏi thông báo lỗi (lỗi của requests thường kèm nguyên URL có token)."""
    out = str(msg)
    return out.replace(TELEGRAM_TOKEN, "***") if TELEGRAM_TOKEN else out


def _tele_call(method: str, data: dict, files: dict | None = None) -> tuple[bool, str]:
    """Gọi 1 phương thức Telegram Bot API. Trả (thành công, mô tả lỗi nếu có)."""
    url = f"{TELEGRAM_API_BASE}/bot{TELEGRAM_TOKEN}/{method}"
    try:
        r = requests.post(url, data=data, files=files, timeout=60)
    except requests.RequestException as exc:
        return False, f"Lỗi mạng: {_tele_safe(exc)}"
    if r.status_code == 200:
        return True, ""
    try:
        desc = r.json().get("description", "")
    except ValueError:
        desc = ""
    return False, f"Telegram trả về mã {r.status_code}" + (f": {_tele_safe(desc)}" if desc else ".")


def send_telegram(text: str):
    if not _tele_enabled():
        return False, "Chưa cấu hình TELEGRAM_TOKEN / TELEGRAM_CHAT_ID."
    chunks = [text[i:i + 3800] for i in range(0, len(text), 3800)] or [""]
    for i, chunk in enumerate(chunks):
        prefix = "" if i == 0 else f"(phần {i+1}/{len(chunks)})\n"
        ok, err = _tele_call("sendMessage", {"chat_id": TELEGRAM_CHAT_ID, "text": prefix + chunk})
        if not ok:
            return False, err
    return True, f"Đã gửi {len(chunks)} tin nhắn."


TELE_CAPTION_MAX = 1024     # giới hạn lời chú thích của ảnh trên Telegram


def clean_tele_text(text: str) -> str:
    """Telegram gửi văn bản thuần nên bỏ ký hiệu markdown AI hay thêm vào."""
    lines = []
    for ln in str(text).replace("**", "").replace("__", "").splitlines():
        ln = ln.rstrip()
        if ln.lstrip().startswith(("* ", "- ")):
            ln = "• " + ln.lstrip()[2:]
        lines.append(ln.lstrip("#").strip() if ln.lstrip().startswith("#") else ln)
    return "\n".join(lines).strip()


def send_telegram_photo(png: bytes, text: str, filename: str = "xep_hang.png") -> tuple[bool, str]:
    """Gửi ảnh kèm thông báo.
    - Thông báo <= 1024 ký tự: làm chú thích của ảnh (một tin duy nhất).
    - Dài hơn: gửi ảnh trước rồi gửi thông báo thành tin nhắn riêng.
    - Telegram từ chối ảnh (quá cao/rộng): tự gửi lại dạng file đính kèm."""
    if not _tele_enabled():
        return False, "Chưa cấu hình TELEGRAM_TOKEN / TELEGRAM_CHAT_ID."
    text = clean_tele_text(text)
    caption = text if len(text) <= TELE_CAPTION_MAX else ""
    data = {"chat_id": TELEGRAM_CHAT_ID}
    if caption:
        data["caption"] = caption
    as_file = False
    ok, err = _tele_call("sendPhoto", data, {"photo": (filename, png, "image/png")})
    if not ok:
        ok2, err2 = _tele_call("sendDocument", data, {"document": (filename, png, "image/png")})
        if not ok2:
            return False, f"Không gửi được ảnh. {err}"
        ok, as_file = True, True
    note_ = " (Telegram không nhận ảnh này ở dạng ảnh nên đã gửi dạng file)" if as_file else ""
    if text and not caption:
        ok3, err3 = send_telegram(text)
        if not ok3:
            return False, f"Đã gửi ảnh{note_} nhưng chưa gửi được thông báo: {err3}"
        return True, f"Đã gửi ảnh{note_} và thông báo (thông báo dài hơn {TELE_CAPTION_MAX} ký tự nên gửi thành tin riêng)."
    return True, f"Đã gửi ảnh kèm thông báo{note_}."


# ── GTalk (nhắn tin nội bộ GHN) ────────────────────────────────────────
def parse_gtalk_channels(raw: str) -> tuple[dict, str | None]:
    """Đọc danh sách nhóm nhận tin từ biến môi trường GTALK_CHANNELS.
    Chấp nhận JSON {"Tên nhóm": "channelId"} hoặc dạng "Tên nhóm=channelId" cách nhau bằng ; hoặc xuống dòng.
    Trả (từ điển tên -> channelId, thông báo lỗi nếu cấu hình sai)."""
    if not raw:
        return {}, None
    try:
        obj = json.loads(raw)
        if not isinstance(obj, dict):
            return {}, 'GTALK_CHANNELS phải là JSON dạng {"Tên nhóm": "channelId"}.'
        items = list(obj.items())
    except ValueError:
        items = []
        for part in re.split(r"[;\n]+", raw):
            if not part.strip():
                continue
            if "=" not in part:
                return {}, f"GTALK_CHANNELS: mục '{part.strip()[:30]}' thiếu dấu '='."
            k, v = part.split("=", 1)
            items.append((k.strip(), v.strip()))
    out: dict[str, str] = {}
    for k, v in items:
        name, cid = str(k).strip(), str(v).strip()
        if not name or not cid.isdigit():
            return {}, f"GTALK_CHANNELS: nhóm '{name}' có channelId không phải dãy số."
        out[name] = cid
    return out, None


GTALK_CHANNELS, GTALK_CFG_ERR = parse_gtalk_channels(GTALK_CHANNELS_RAW)
GTALK_CAPTION_MAX = 1024   # tài liệu GTalk không nêu giới hạn chú thích; dùng mức an toàn như Telegram


def _gtalk_enabled() -> bool:
    return bool(GTALK_OA_TOKEN and GTALK_CHANNELS)


def _gt_safe(msg) -> str:
    """Che token OA và chữ ký trong link S3 khỏi thông báo lỗi hiển thị lên giao diện."""
    out = str(msg)
    if GTALK_OA_TOKEN:
        out = out.replace(GTALK_OA_TOKEN, "***")
    return re.sub(r"\?[^\s'\")]*", "?…", out)


_gt_lock = threading.Lock()
_gt_last_id = [0]


def _gt_msg_id() -> str:
    """clientMsgId duy nhất cho mỗi tin: mili giây hiện tại, tăng dần nếu trùng."""
    with _gt_lock:
        t = time.time_ns() // 1_000_000
        if t <= _gt_last_id[0]:
            t = _gt_last_id[0] + 1
        _gt_last_id[0] = t
        return str(t)


def _gt_post(path: str, body: dict) -> tuple[bool, dict | str]:
    """Gọi API GTalk. Thành công khi HTTP 200 VÀ errorCode == 'success' (GTalk báo lỗi trong thân)."""
    try:
        r = requests.post(f"{GTALK_API_BASE}{path}", json={**body, "oaToken": GTALK_OA_TOKEN}, timeout=30)
    except requests.RequestException as exc:
        return False, f"Lỗi mạng: {_gt_safe(exc)}"
    try:
        js = r.json()
    except ValueError:
        return False, f"GTalk trả về mã {r.status_code} (không phải JSON)."
    if not isinstance(js, dict):
        return False, f"GTalk trả về dữ liệu lạ (mã {r.status_code})."
    if r.status_code == 200 and js.get("errorCode") == "success":
        return True, js.get("data") or {}
    err = (js.get("error") or {}).get("errorMessage") or js.get("errorCode") or f"mã {r.status_code}"
    return False, f"GTalk báo lỗi: {_gt_safe(err)}"


def gtalk_upload_image(channel_id: str, png: bytes, filename: str) -> tuple[bool, tuple | str]:
    """Tải ảnh lên GTalk (3 bước: initiate -> PUT S3 ảnh gốc + ảnh thu nhỏ -> complete).
    Trả (True, (fileId, rộng, cao)) hoặc (False, lý do). Mỗi kênh phải tải riêng vì file gắn với kênh."""
    im = Image.open(io.BytesIO(png))
    w, h = im.size
    thumb = im.copy()
    thumb.thumbnail((600, 600), Image.LANCZOS)          # vừa khung 600x600, giữ tỷ lệ, không phóng to
    tb = io.BytesIO()
    thumb.save(tb, format="PNG", optimize=True)
    ok, data = _gt_post("/api/gtalk/initiate-upload", {
        "ChannelId": channel_id, "FileName": filename, "FileSize": str(len(png)),
        "MimeType": "image/png", "Metadata": json.dumps({"width": w, "height": h})})
    if not ok:
        return False, data
    for url, payload in ((data.get("PresignedURL"), png), (data.get("PresignedThumbURL"), tb.getvalue())):
        if not url:
            return False, "GTalk không trả về link tải ảnh lên."
        try:
            r = requests.put(url, data=payload, headers={"Content-Type": "image/png"}, timeout=120)
        except requests.RequestException as exc:
            return False, f"Lỗi tải ảnh lên: {_gt_safe(exc)}"
        if r.status_code != 200:
            return False, (f"Tải ảnh lên kho lưu trữ thất bại (mã {r.status_code}"
                           + (", link đã hết hạn" if r.status_code == 403 else "") + ").")
    ok, done = _gt_post("/api/gtalk/complete-upload", {"UploadId": data.get("UploadId")})
    if not ok:
        return False, done
    return True, (str(done.get("Id")), w, h)


def gtalk_send_rank(channel_id: str, png: bytes, text: str, filename: str) -> tuple[bool, str]:
    """Gửi ảnh xếp hạng kèm thông báo vào MỘT nhóm GTalk.
    Thông báo <= 1024 ký tự làm chú thích của ảnh; dài hơn thì gửi ảnh rồi gửi tin nhắn riêng."""
    text = clean_tele_text(text)
    caption = text if len(text) <= GTALK_CAPTION_MAX else ""
    ok, up = gtalk_upload_image(channel_id, png, filename)
    if not ok:
        return False, str(up)
    file_id, w, h = up
    attachment: dict = {"items": [{"image": {"fileId": file_id, "width": w, "height": h}}]}
    if caption:
        attachment["caption"] = caption
    ok, err = _gt_post("/api/gtalk/send-message", {
        "channelId": channel_id, "clientMsgId": _gt_msg_id(), "content": {"attachment": attachment}})
    if not ok:
        return False, str(err)
    if text and not caption:
        ok, err = _gt_post("/api/gtalk/send-message", {
            "channelId": channel_id, "clientMsgId": _gt_msg_id(),
            "content": {"text": text, "parseMode": "PLAIN_TEXT"}})
        if not ok:
            return False, f"Đã gửi ảnh nhưng chưa gửi được thông báo: {err}"
        return True, "Đã gửi ảnh và thông báo (thông báo dài nên gửi thành tin riêng)."
    return True, "Đã gửi ảnh kèm thông báo."


def send_rank_everywhere(png: bytes, text: str, filename: str, use_telegram: bool,
                         groups: list[str]) -> list[tuple[str, bool, str]]:
    """Gửi cùng một ảnh + thông báo tới Telegram và/hoặc nhiều nhóm GTalk.
    Một nơi lỗi không làm dừng các nơi còn lại. Trả danh sách (nơi nhận, thành công, thông điệp)."""
    results: list[tuple[str, bool, str]] = []
    if use_telegram:
        ok, msg = send_telegram_photo(png, text, filename)
        results.append(("Telegram", ok, msg))
    for g in groups:
        cid = GTALK_CHANNELS.get(g)
        if not cid:
            results.append((f"GTalk · {g}", False, "Nhóm không còn trong cấu hình GTALK_CHANNELS."))
            continue
        try:
            ok, msg = gtalk_send_rank(cid, png, text, filename)
        except Exception as exc:  # noqa: BLE001  (một nhóm lỗi không làm hỏng cả loạt)
            ok, msg = False, f"Lỗi không xác định: {_gt_safe(exc)}"
        results.append((f"GTalk · {g}", ok, msg))
    return results


RANK_TONES = {
    "Vui vẻ, khích lệ": "Giọng thân thiện, tích cực, truyền năng lượng như một quản lý đang cổ vũ đội.",
    "Trang trọng": "Giọng nghiêm túc, lịch sự, như một thông báo chính thức của khu vực.",
}


def describe_period(a: pd.Timestamp, b: pd.Timestamp) -> tuple[str, str]:
    """Gọi đúng tên khoảng thời gian đang xem: 'ngày', 'tuần', 'tháng' hoặc 'từ … đến …'.
    Trả (mô tả, cách nói về lần tiếp theo). Dùng cho thông báo AI viết, tránh chữ 'kỳ' chung chung."""
    if a == b:
        return f"ngày {a:%d/%m/%Y}", "ngày mai"
    if a.weekday() == 0 and (b - a).days == 6:
        return f"tuần {a:%d/%m}–{b:%d/%m/%Y}", "tuần sau"
    if a.day == 1 and b == month_end(a):
        return f"tháng {a:%m/%Y}", "tháng sau"
    return f"từ ngày {a:%d/%m/%Y} đến ngày {b:%d/%m/%Y}", "thời gian tới"


def rank_notice_prompt(tone: str, thoi_gian: str, tiep_theo: str, pham_vi: str, top_txt: str,
                       n_total: int, n_dat: int) -> str:
    return f"""Bạn là Quản lý khu vực của GHN, soạn thông báo gửi vào nhóm Telegram của nhân viên giao hàng
về bảng xếp hạng tỷ lệ giao thành công (%GTC). {RANK_TONES.get(tone, '')}

SỐ LIỆU THẬT (chỉ dùng đúng những số này):
- Thời gian xếp hạng: {thoi_gian}. Phạm vi: {pham_vi}.
- Có {n_total} nhân viên xếp hạng, {n_dat} người đạt mục tiêu %GTC từ 80%.
- Top 3 (xếp theo %GTC cao nhất):
{top_txt}

YÊU CẦU — VIẾT NGẮN GỌN:
- Tiếng Việt, TỐI ĐA 350 ký tự, tối đa 5 dòng ngắn, VĂN BẢN THUẦN: không markdown, không dấu * hay #.
- Tối đa 4 emoji (tính cả 3 huy chương). Không rào đón, không câu sáo rỗng, không lặp ý.
- Gọi thời gian đúng như ghi ở "Thời gian xếp hạng" (ví dụ "ngày 21/10/2026", "tuần 20/10–26/10/2026",
  "tháng 10/2026"). TUYỆT ĐỐI không dùng từ "kỳ"; khi nói về lần sau thì dùng "{tiep_theo}".
- Đúng 4 ý, mỗi ý một dòng:
  1) Tiêu đề ngắn kèm thời gian xếp hạng.
  2) Top 3: tên và %GTC, viết gọn trên một dòng (ví dụ "🥇 Tên A 92,1% · 🥈 Tên B 90,5% · 🥉 Tên C 89,0%").
  3) "{n_dat}/{n_total} bạn đạt mục tiêu %GTC ≥ 80%" và một lời động viên ngắn.
  4) Một câu kêu gọi cho {tiep_theo}, nhắc xem ảnh bảng xếp hạng đính kèm.
- TUYỆT ĐỐI không nêu tên hay số liệu của người xếp thấp, không chê trách ai cụ thể.
- Giữ nguyên cách viết tên như trong số liệu. Không bịa thêm số liệu hay chính sách thưởng phạt.
- Chỉ trả về nội dung thông báo, không giải thích thêm."""


# ── Cảnh báo nhân sự ────────────────────────────────────────────────────
HR_DEFAULTS = {"low": 70.0, "streak": 3, "drop": 10.0, "absent": 3, "ratio": 50}
HR_QUIT_DAYS = 7     # không phát sinh đơn từ 7 ngày trở lên: coi như đã nghỉ việc, không hiển thị
HR_FLAG_COLORS = {"low": DANGER, "drop": ACCENT, "absent": "#6C757D", "gan": "#00B4D8"}


@st.cache_data(show_spinner=False)
def hr_daily(df: pd.DataFrame) -> pd.DataFrame:
    """Gom sheet Năng suất nhân viên về mỗi người một dòng mỗi ngày (MaNV, Nhân viên, Bưu cục, Ngày, Gán, GTC)."""
    cols = ["MaNV", "Nhân viên", "Bưu cục", "Ngày", "Gán", "GTC"]
    if df is None or df.empty or "Ngày" not in df.columns or "Bưu Cục" not in df.columns:
        return pd.DataFrame(columns=cols)
    c_nv = pick_col(df, [["nhan vien"]])
    c_gan = pick_col(df, [["gan giao"], ["so don gan"], ["gan"]])
    c_gtc = pick_col(df, [["giao tinh luong"], ["don gtc"], ["giao thanh cong"], ["gtc"]], exclude=["%"])
    if not (c_nv and c_gan and c_gtc):
        return pd.DataFrame(columns=cols)
    d = df[df["Ngày"].notna() & df[c_nv].notna()].copy()
    d = d[~d[c_nv].map(is_total_row)]
    d["Tên"] = d[c_nv].astype(str).str.strip()
    d = d[(d["Tên"] != "") & (d["Tên"] != "nan")]
    if d.empty:
        return pd.DataFrame(columns=cols)
    d["MaNV"] = d["Tên"].map(staff_id)
    d["Gán"] = pd.to_numeric(_as_series(d[c_gan]), errors="coerce").fillna(0)
    d["GTC"] = pd.to_numeric(_as_series(d[c_gtc]), errors="coerce").fillna(0)
    d = d.sort_values("Ngày")
    out = d.groupby(["MaNV", "Ngày"], as_index=False).agg(
        Gán=("Gán", "sum"), GTC=("GTC", "sum"), **{"Bưu cục": ("Bưu Cục", "last")})
    # Tên hiển thị: giữ bản ghi dài nhất (thường đầy đủ nhất) của mỗi mã
    names = d.assign(_l=d["Tên"].str.len()).sort_values("_l").groupby("MaNV")["Tên"].last()
    out["Nhân viên"] = out["MaNV"].map(names).map(staff_label)
    return out[cols]


@st.cache_data(show_spinner=False)
def hr_warnings(daily: pd.DataFrame, ref: pd.Timestamp, low: float = 70.0, streak: int = 3,
                drop: float = 10.0, absent: int = 3, ratio: float = 50) -> pd.DataFrame:
    """Dò 4 loại cảnh báo nhân sự trên dữ liệu theo ngày (từ hr_daily), tính tới ngày `ref`:
      low    — %GTC dưới `low`% trong `streak` ngày làm việc liền gần nhất
      drop   — %GTC 7 ngày gần nhất giảm từ `drop` điểm so với 7 ngày trước đó (mỗi bên ≥ 30 đơn gán)
      absent — đã `absent` ngày trở lên không có đơn (nhưng chưa tới HR_QUIT_DAYS)
    Người không có đơn từ HR_QUIT_DAYS ngày trở lên coi như đã nghỉ việc và bị bỏ qua.
      gan    — đơn gán bình quân/ngày trong 7 ngày dưới `ratio`% trung vị của bưu cục (làm ≥ 2 ngày)
    Mỗi nhân viên một dòng, chỉ giữ người có ít nhất một cảnh báo."""
    cols = ["Mức", "Nhân viên", "Bưu cục", "Cảnh báo", "%GTC 7 ngày", "%GTC 7 ngày trước",
            "Gán TB/ngày", "Ngày làm cuối", "_tags", "_flags", "_score", "_ma"]
    if daily is None or daily.empty:
        return pd.DataFrame(columns=cols)
    ref = pd.Timestamp(ref).normalize()
    d = daily[(daily["Ngày"] <= ref) & (daily["Ngày"] >= ref - pd.Timedelta(days=29))]
    d = d[d["Gán"] > 0]
    if d.empty:
        return pd.DataFrame(columns=cols)
    r_a, p_a, p_b = ref - pd.Timedelta(days=6), ref - pd.Timedelta(days=13), ref - pd.Timedelta(days=7)

    def pct(x):
        g = float(x["Gán"].sum())
        return float(x["GTC"].sum()) / g * 100 if g > 0 else None

    recent_all = d[d["Ngày"] >= r_a]
    per_staff = recent_all.groupby("MaNV").agg(n=("Ngày", "nunique"), gan=("Gán", "sum"),
                                              bc=("Bưu cục", "last"))
    per_staff = per_staff[per_staff["n"] >= 2]
    per_staff["avg"] = per_staff["gan"] / per_staff["n"]
    med_bc = per_staff.groupby("bc")["avg"].median()

    rows = []
    for ma, x in d.groupby("MaNV"):
        x = x.sort_values("Ngày")
        last = x["Ngày"].iloc[-1]
        bc = x["Bưu cục"].iloc[-1]
        rec, prev = x[x["Ngày"] >= r_a], x[(x["Ngày"] >= p_a) & (x["Ngày"] <= p_b)]
        p_rec, p_prev = pct(rec), pct(prev)
        avg_gan = float(rec["Gán"].sum()) / rec["Ngày"].nunique() if not rec.empty else None
        flags, tags, desc, score = [], [], [], 0.0

        days_off = (ref - last).days
        if days_off >= HR_QUIT_DAYS:
            continue
        if days_off >= absent:
            flags.append("absent")
            tags.append(f"Vắng {days_off} ngày")
            desc.append(f"{days_off} ngày không có đơn (làm cuối {last:%d/%m})")
            score += 2 if days_off >= 5 else 1
        else:
            day_pct = (x["GTC"] / x["Gán"] * 100).iloc[::-1]
            run = 0
            for v in day_pct:
                if v < low:
                    run += 1
                else:
                    break
            if run >= streak:
                flags.append("low")
                tags.append(f"%GTC < {low:g}% · {run} ngày")
                desc.append(f"%GTC dưới {low:g}% {run} ngày làm liền gần nhất")
                score += 2 if run >= max(5, streak + 2) else 1
        if (p_rec is not None and p_prev is not None and rec["Gán"].sum() >= 30
                and prev["Gán"].sum() >= 30 and p_prev - p_rec >= drop):
            flags.append("drop")
            tags.append(f"Giảm {p_prev - p_rec:.1f} điểm")
            desc.append(f"%GTC giảm {p_prev - p_rec:.1f} điểm ({p_prev:.1f}% → {p_rec:.1f}%)")
            score += 2 if p_prev - p_rec >= 2 * drop else 1
        med = med_bc.get(bc)
        if ma in per_staff.index and med and avg_gan is not None and avg_gan < med * ratio / 100:
            flags.append("gan")
            tags.append(f"Gán thấp {avg_gan / med * 100:.0f}%")
            desc.append(f"gán TB {avg_gan:,.0f} đơn/ngày, bằng {avg_gan / med * 100:.0f}% "
                        f"trung vị bưu cục ({med:,.0f})")
            score += 1
        if not flags:
            continue
        score += len(flags) - 1
        rows.append({
            "Mức": "Cao" if score >= 2 else "Trung bình",
            "Nhân viên": x["Nhân viên"].iloc[-1], "Bưu cục": bc,
            "Cảnh báo": (lambda s: s[:1].upper() + s[1:])("; ".join(desc)),
            "%GTC 7 ngày": p_rec, "%GTC 7 ngày trước": p_prev,
            "Gán TB/ngày": avg_gan, "Ngày làm cuối": last,
            "_tags": "|".join(tags), "_flags": "|".join(flags), "_score": score, "_ma": ma,
        })
    if not rows:
        return pd.DataFrame(columns=cols)
    out = pd.DataFrame(rows, columns=cols)
    out["_p"] = out["%GTC 7 ngày"].fillna(999)
    out = out.sort_values(["_score", "_p"], ascending=[False, True]).drop(columns="_p")
    return out.reset_index(drop=True)


@img_cache
def render_hr_image(rows: pd.DataFrame, title: str, subtitle: str, footer: str, legend: str) -> bytes:
    """Vẽ danh sách cảnh báo nhân sự thành ảnh PNG.
    `rows` gồm: Mức, Nhân viên, Bưu cục, %GTC 7 ngày, _tags (chữ ngắn), _flags (mã loại) — nối bằng '|'."""
    S = 2
    W, PAD = 1400 * S, 40 * S
    HEAD_H, TH_H, FOOT_H = 170 * S, 62 * S, 104 * S
    x_no, x_name, x_tags = PAD + 22 * S, PAD + 64 * S, 590 * S
    tags_max, r_pct = 1040 * S, 1195 * S
    pill_h, pill_gap = 38 * S, 10 * S

    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    f_tag = _font(True, 19 * S)

    def layout(tags):
        """Xếp các thẻ cảnh báo thành nhiều dòng nếu không vừa một dòng."""
        lines, cur, w = [], [], 0
        for t in tags:
            tw = probe.textlength(t, font=f_tag) + 28 * S
            if cur and x_tags + w + tw > tags_max:
                lines.append(cur)
                cur, w = [], 0
            cur.append((t, tw))
            w += tw + pill_gap
        if cur:
            lines.append(cur)
        return lines

    plans = [layout(str(r[4]).split("|")) for r in rows.itertuples(index=False)]
    heights = [max(80 * S, len(p) * (pill_h + 8 * S) + 26 * S) for p in plans]
    H = HEAD_H + 24 * S + TH_H + sum(heights) + FOOT_H

    c_primary, c_text, c_muted, c_line = _rgb(PRIMARY), _rgb(TEXT), _rgb(MUTED), _rgb(LINE)
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    f_th, f_td, f_tdb = _font(True, 22 * S), _font(False, 24 * S), _font(True, 25 * S)
    f_small = _font(False, 20 * S)
    _draw_header(img, d, W, title, subtitle, S, HEAD_H)

    y = HEAD_H + 24 * S
    d.rectangle([PAD, y, W - PAD, y + TH_H], fill=(232, 243, 250))
    mid = y + TH_H // 2
    d.text((x_no, mid), "#", font=f_th, fill=c_primary, anchor="mm")
    d.text((x_name, mid), "NHÂN VIÊN · BƯU CỤC", font=f_th, fill=c_primary, anchor="lm")
    d.text((x_tags, mid), "CẢNH BÁO", font=f_th, fill=c_primary, anchor="lm")
    d.text((r_pct, mid), "%GTC 7 NGÀY", font=f_th, fill=c_primary, anchor="rm")
    d.text((W - PAD - 14 * S, mid), "MỨC", font=f_th, fill=c_primary, anchor="rm")
    y += TH_H

    for i, (r, plan, rh) in enumerate(zip(rows.itertuples(index=False), plans, heights)):
        high = r[0] == "Cao"
        d.rectangle([PAD, y, W - PAD, y + rh], fill=(253, 240, 240) if high else
                    ((247, 250, 252) if i % 2 else (255, 255, 255)))
        d.line([PAD, y + rh, W - PAD, y + rh], fill=c_line, width=S)
        cy = y + rh // 2
        d.text((x_no, cy), str(i + 1), font=f_td, fill=c_muted, anchor="mm")
        d.text((x_name, cy - 15 * S), _fit_text(d, str(r[1]), f_tdb, x_tags - x_name - 24 * S),
               font=f_tdb, fill=c_text, anchor="lm")
        d.text((x_name, cy + 17 * S), _fit_text(d, str(r[2]), f_small, x_tags - x_name - 24 * S),
               font=f_small, fill=c_muted, anchor="lm")
        ty = cy - (len(plan) * (pill_h + 8 * S) - 8 * S) // 2
        flags = str(r[5]).split("|")
        k = 0
        for line in plan:
            tx = x_tags
            for t, tw in line:
                col = _rgb(HR_FLAG_COLORS.get(flags[k], MUTED))
                d.rounded_rectangle([tx, ty, tx + tw, ty + pill_h], radius=pill_h // 2, fill=col)
                d.text((tx + tw / 2, ty + pill_h // 2), t, font=f_tag, fill=(255, 255, 255), anchor="mm")
                tx += tw + pill_gap
                k += 1
            ty += pill_h + 8 * S
        p7 = r[3]
        d.text((r_pct, cy), "—" if p7 is None or pd.isna(p7) else f"{float(p7):.2f}%", font=f_tdb,
               fill=c_text, anchor="rm")
        pw, ph = 110 * S, 38 * S
        px1 = W - PAD - 14 * S
        d.rounded_rectangle([px1 - pw, cy - ph // 2, px1, cy + ph // 2], radius=ph // 2,
                            fill=_rgb(DANGER) if high else (255, 236, 204))
        d.text((px1 - pw // 2, cy), "CAO" if high else "TB", font=_font(True, 21 * S),
               fill=(255, 255, 255) if high else (156, 92, 0), anchor="mm")
        y += rh

    d.text((PAD, y + 30 * S), _fit_text(d, legend, f_small, W - 2 * PAD), font=f_small, fill=c_muted,
           anchor="lm")
    d.text((PAD, y + 66 * S), _fit_text(d, footer, f_small, W - 2 * PAD), font=f_small, fill=c_muted,
           anchor="lm")
    d.rectangle([PAD, y + FOOT_H - 4 * S, W - PAD, y + FOOT_H - 1 * S], fill=c_primary)
    return _png_bytes(img)


HR_FLAG_NAMES = {"low": "%GTC thấp liên tiếp", "drop": "%GTC giảm mạnh", "absent": "Vắng / không có đơn",
                 "gan": "Gán thấp"}


def hr_notice_data(hr: pd.DataFrame) -> tuple[str, str]:
    """Gom danh sách cảnh báo cho AI viết gọn: (người mức Cao kèm thẻ ngắn, nhóm còn lại theo loại cảnh báo).
    Tên bỏ mã nhân viên cho tin nhắn ngắn (ảnh đính kèm vẫn có mã)."""
    def ten(x):
        return re.sub(r"^\d+\s*·\s*", "", str(x))
    cao = hr[hr["Mức"] == "Cao"]
    def p7(r):
        v = r["%GTC 7 ngày"]
        return f" · %GTC 7 ngày {v:.1f}%" if v is not None and pd.notna(v) else ""
    cao_txt = "\n".join(f"  - {ten(r['Nhân viên'])} — {r['Bưu cục']}: {str(r['_tags']).replace('|', ' · ')}{p7(r)}"
                        for _, r in cao.iterrows()) or "  (không có)"
    con = hr[hr["Mức"] != "Cao"]
    nhom: dict[str, list[str]] = {}
    for _, r in con.iterrows():
        nhom.setdefault(str(r["_flags"]).split("|")[0], []).append(ten(r["Nhân viên"]))
    nhom_txt = "\n".join(f"  - {HR_FLAG_NAMES.get(k, k)} ({len(v)}): {', '.join(v)}"
                         for k, v in nhom.items()) or "  (không có)"
    return cao_txt, nhom_txt


def hr_notice_prompt(thoi_gian: str, ngay_du_lieu: str, pham_vi: str, nguong: str, cao_txt: str,
                     nhom_txt: str, n_total: int, n_cao: int) -> str:
    return f"""Bạn là Quản lý khu vực của GHN, soạn tin nhắn gửi vào nhóm QUẢN LÝ bưu cục (trưởng bưu cục,
điều phối) để cảnh báo các nhân viên giao hàng cần quan tâm. Giọng nghiêm túc, xây dựng.

SỐ LIỆU THẬT (chỉ dùng đúng những số này):
- Dữ liệu năng suất đến ngày {ngay_du_lieu}; so sánh 7 ngày gần nhất ({thoi_gian}) với 7 ngày trước đó.
- Phạm vi: {pham_vi}. Ngưỡng cảnh báo: {nguong}.
- {n_total} nhân viên cần chú ý, {n_cao} người mức Cao.
- Mức Cao (tên — bưu cục — vấn đề):
{cao_txt}
- Mức Trung bình, gom theo loại cảnh báo:
{nhom_txt}

YÊU CẦU — PHẦN ĐẦU NGẮN GỌN, PHẦN VIỆC CẦN LÀM CHI TIẾT:
- VĂN BẢN THUẦN (không markdown, không dấu * hay #), tối đa 3 emoji. Không câu rào đón,
  không giải thích lý thuyết, không lặp ý. Phần danh sách viết ngắn; phần "Việc NVXL cần làm" viết cụ thể.
  Tổng cố gắng dưới 1.300 ký tự.
- TUYỆT ĐỐI không dùng từ "kỳ". Không bịa nguyên nhân, số liệu hay hình thức kỷ luật. Giữ nguyên tên như trên.
- Bố cục đúng như sau:
  Dòng 1: "⚠️ Cảnh báo nhân sự — dữ liệu đến {ngay_du_lieu}: {n_total} người cần chú ý ({n_cao} mức Cao)."
  "Mức Cao:" rồi mỗi người một dòng "- Tên — bưu cục: vấn đề + con số chính".
  "Theo dõi:" rồi mỗi loại cảnh báo một dòng "- Loại (số người): tên, tên…".
  "Việc NVXL cần làm:" chỉ cho các loại cảnh báo đang có, ưu tiên người mức Cao trước. Mỗi việc một dòng,
  ghi rõ: LÀM GÌ — VỚI AI (tên) — KHI NÀO — KẾT QUẢ CẦN ĐẠT. Tổng 4–7 dòng. Gợi ý theo từng loại:
    %GTC thấp liên tiếp: trao đổi 1:1 trong hôm nay, cùng xem lý do đơn thất bại các ngày gần nhất
      (khách hẹn lại, không nghe máy, sai địa chỉ, không kịp giờ); kèm tuyến 1–2 buổi với bạn %GTC tốt;
      nhắc gọi xác nhận khách trước khi giao; mục tiêu %GTC về trên ngưỡng trong 3 ngày làm tới.
    %GTC giảm mạnh: hỏi thay đổi từ khi bắt đầu giảm (tuyến mới, loại đơn mới, xe, sức khỏe);
      điều chỉnh tuyến/đơn nếu cần; theo dõi %GTC hằng ngày trong 1 tuần.
    Vắng / không có đơn: gọi hỏi thăm trong hôm nay, xác nhận ngày đi làm lại; sắp người hỗ trợ tuyến;
      nếu bạn có ý định nghỉ thì ghi nhận lý do và báo nhân sự.
    Gán thấp: xem lại cách phân đơn so với các bạn cùng bưu cục; tăng dần đơn gán khoảng 10–15%/ngày
      và theo dõi để %GTC không giảm.
  Thêm một dòng: "Báo cáo kết quả trao đổi và cam kết của từng bạn mức Cao trước [hạn cụ thể, ví dụ 17h ngày mai]."
  Dòng cuối: "Chi tiết xem ảnh đính kèm."
- Chỉ trả về nội dung tin nhắn."""


# ── Chi tiết một nhân viên + hướng dẫn trao đổi 1:1 ─────────────────────
def hr_staff_chart(daily: pd.DataFrame, ma: str, ref: pd.Timestamp, low: float, days: int = 30):
    """Biểu đồ 30 ngày của một nhân viên: cột đơn gán, đơn GTC và đường %GTC.
    Ngày không có đơn vẫn giữ trên trục (cột trống) để thấy rõ ngày nghỉ / vắng."""
    ref = pd.Timestamp(ref).normalize()
    a = ref - pd.Timedelta(days=days - 1)
    d = daily[(daily["MaNV"] == ma) & (daily["Ngày"] >= a) & (daily["Ngày"] <= ref)]
    d = (d.groupby("Ngày")[["Gán", "GTC"]].sum()
          .reindex(pd.date_range(a, ref, freq="D"), fill_value=0).rename_axis("Ngày").reset_index())
    d["r"] = np.where(d["Gán"] > 0, d["GTC"] / d["Gán"].where(d["Gán"] > 0) * 100, np.nan)
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=d["Ngày"], y=d["Gán"], name="Đơn gán", marker_color=PRIMARY_SOFT,
                         marker_line_width=0, hoverinfo="x+y+name"), secondary_y=False)
    fig.add_trace(go.Bar(x=d["Ngày"], y=d["GTC"], name="Đơn GTC", marker_color=PRIMARY,
                         marker_line_width=0, hoverinfo="x+y+name"), secondary_y=False)
    fig.add_trace(go.Scatter(x=d["Ngày"], y=d["r"], name="% GTC", mode="lines+markers+text",
                             connectgaps=False, line=dict(color=ACCENT, width=3), marker=dict(size=7),
                             hoverinfo="x+y+name", text=point_labels(d["r"], pct_label, 12),
                             textposition="top center", cliponaxis=False,
                             textfont=dict(color=ACCENT, **LABEL_FONT)), secondary_y=True)
    # Vẽ ngưỡng thành một đường có tên trong chú thích (add_hline kèm chữ bị lệch chỗ khi có hai trục).
    fig.add_trace(go.Scatter(x=[d["Ngày"].iloc[0], d["Ngày"].iloc[-1]], y=[low, low], mode="lines",
                             name=f"Ngưỡng cảnh báo {low:g}%", hoverinfo="skip",
                             line=dict(color=DANGER, width=2, dash="dot")), secondary_y=True)
    fig.update_layout(barmode="overlay", height=430, title=f"Đơn gán · GTC · %GTC — {days} ngày gần nhất")
    fig.update_yaxes(title_text="Số đơn", secondary_y=False)
    fig.update_yaxes(title_text="% GTC", secondary_y=True, showgrid=False)
    band_axes(fig, d["Gán"].max())
    fig.update_xaxes(tickformat="%d/%m")
    return fig, d


HR_1ON1 = {
    "low": {
        "ten": "%GTC thấp nhiều ngày liền",
        "hoi": ["Mấy ngày gần đây đơn không giao được chủ yếu vì lý do gì: khách không nghe máy, hẹn lại, "
                "sai địa chỉ, hay không kịp giờ?",
                "Tuyến hoặc khu vực em chạy có gì thay đổi không (đơn xa hơn, đường khó, khách mới)?",
                "Em thường gọi khách trước khi đi giao không, gọi vào lúc nào?",
                "Em có đang gặp khó khăn về xe, điện thoại, sức khỏe hay việc riêng không?"],
        "lam": ["Cùng mở danh sách đơn thất bại mấy ngày gần nhất, xem lý do lặp lại nhiều nhất.",
                "Kèm tuyến 1–2 buổi cùng một bạn %GTC tốt ở khu vực gần.",
                "Thống nhất gọi xác nhận khách trước giờ giao, sắp lộ trình theo khung giờ khách hẹn."],
    },
    "drop": {
        "ten": "%GTC giảm mạnh so với tuần trước",
        "hoi": ["Từ khoảng ngày %GTC bắt đầu giảm (xem biểu đồ), công việc của em có gì khác không?",
                "Em có được chuyển tuyến, nhận thêm loại đơn mới (TikTok, hàng cồng kềnh…) không?",
                "Tuần trước em làm tốt hơn, theo em điều gì đã giúp em làm tốt lúc đó?"],
        "lam": ["Chỉ ra đúng ngày bắt đầu giảm trên biểu đồ để cùng tìm nguyên nhân cụ thể.",
                "Nếu do tuyến hoặc loại đơn khó: xem lại cách chia tuyến, chia đơn.",
                "Theo dõi %GTC hằng ngày trong 1 tuần tới, phản hồi sớm khi có cải thiện."],
    },
    "absent": {
        "ten": "Vắng / không có đơn mấy ngày gần đây",
        "hoi": ["Hỏi thăm trước: sức khỏe, gia đình em dạo này thế nào?",
                "Em có gặp khó khăn gì khiến mấy hôm nay chưa đi làm được không?",
                "Em dự kiến ngày nào quay lại làm? Bưu cục có thể hỗ trợ gì cho em?"],
        "lam": ["Liên hệ riêng (gọi điện hoặc gặp), không hỏi trong nhóm chung.",
                "Thống nhất ngày quay lại; nếu bạn có ý định nghỉ thì ghi nhận lý do và báo bộ phận nhân sự.",
                "Sắp xếp người hỗ trợ tuyến trong thời gian bạn vắng để khách không bị ảnh hưởng."],
    },
    "gan": {
        "ten": "Sản lượng gán thấp hơn nhiều so với bưu cục",
        "hoi": ["Em đang nhận ít đơn vì chủ động xin giảm, vì tuyến ít đơn, hay vì cách phân đơn?",
                "Em nghĩ mỗi ngày em có thể nhận thêm khoảng bao nhiêu đơn mà vẫn giao tốt?",
                "Có điều gì (xe, thời gian, sức khỏe) đang làm em khó nhận thêm đơn không?"],
        "lam": ["Xem lại cách phân đơn cho tuyến của bạn so với các bạn cùng bưu cục.",
                "Tăng dần đơn gán (khoảng 10–15% mỗi ngày), theo dõi để %GTC không bị giảm theo.",
                "Nếu vướng xe / sức khỏe / thời gian: ghi nhận và tìm cách hỗ trợ trước khi tăng đơn."],
    },
}


def hr_1on1_guide(r, low: float) -> str:
    """Hướng dẫn NVXL trao đổi 1:1 với một nhân viên, soạn theo đúng các cảnh báo của người đó."""
    flags = [f for f in str(r["_flags"]).split("|") if f in HR_1ON1]
    p7, p_prev = r["%GTC 7 ngày"], r["%GTC 7 ngày trước"]
    so_lieu = [f"Cảnh báo: {r['Cảnh báo']}"]
    if p7 is not None and pd.notna(p7):
        so_lieu.append(f"%GTC 7 ngày gần nhất: {p7:.2f}%"
                       + (f" (7 ngày trước: {p_prev:.2f}%)" if p_prev is not None and pd.notna(p_prev) else ""))
    if r["Gán TB/ngày"] is not None and pd.notna(r["Gán TB/ngày"]):
        so_lieu.append(f"Đơn gán bình quân: {r['Gán TB/ngày']:,.0f} đơn/ngày")
    so_lieu.append(f"Ngày làm gần nhất: {pd.Timestamp(r['Ngày làm cuối']):%d/%m/%Y}")
    muc_tieu = ("Xác nhận ngày quay lại làm và giữ liên lạc mỗi ngày cho tới khi đi làm lại."
                if flags == ["absent"] else
                f"%GTC từ {low:g}% trở lên trong 3 ngày làm tới, hướng tới 80%.")
    out = [f"#### Trao đổi 1:1 với {r['Nhân viên']} — mức {r['Mức']}",
           "**1. Chuẩn bị (5 phút)**",
           "- Xem biểu đồ ở trên, ghi lại vài con số chính để nói cho cụ thể:",
           *[f"  - {s}" for s in so_lieu],
           "- Chọn chỗ riêng, 15–20 phút, đầu hoặc cuối ca. Không trao đổi trước mặt đồng nghiệp.",
           "**2. Mở đầu**",
           "- Hỏi thăm, ghi nhận một điểm em làm tốt (chuyên cần, thái độ với khách, ngày %GTC cao…).",
           "- Nói rõ mục đích: cùng tìm cách để em làm tốt hơn, không phải để khiển trách.",
           "**3. Cùng nhìn số liệu**",
           "- Đưa số liệu thật, hỏi em nghĩ gì về các con số này trước khi nói nhận xét của mình."]
    if flags:
        out.append("**4. Tìm nguyên nhân — câu hỏi gợi ý**")
        for f in flags:
            out.append(f"- _{HR_1ON1[f]['ten']}:_")
            out += [f"  - {q}" for q in HR_1ON1[f]["hoi"]]
        out.append("**5. Thống nhất việc cần làm và hỗ trợ**")
        for f in flags:
            out += [f"- {x}" for x in HR_1ON1[f]["lam"]]
    out += ["**6. Chốt cam kết và hẹn theo dõi**",
            f"- Mục tiêu: {muc_tieu}",
            "- Chốt 1–2 việc cụ thể em sẽ làm, việc bưu cục sẽ hỗ trợ, và hẹn ngày xem lại (sau 3–5 ngày).",
            "- Ghi lại: nguyên nhân em nêu, cam kết hai bên, ngày hẹn.",
            "**Lưu ý:** lắng nghe nhiều hơn nói; hỏi câu mở; không so sánh với người khác trước mặt em; "
            "không kết luận hay nhắc kỷ luật khi chưa nghe em nói hết."]
    # Dòng trống trước mỗi tiêu đề in đậm để Markdown không dính tiêu đề vào gạch đầu dòng phía trên
    return "\n".join(("\n" + s) if s.startswith("**") else s for s in out)


def hr_1on1_prompt(r, low: float, ngay_txt: str) -> str:
    return f"""Bạn là chuyên gia quản lý nhân sự vận hành giao hàng của GHN. Soạn KỊCH BẢN TRAO ĐỔI 1:1 để nhân viên xử lý
(NVXL — người quản lý trực tiếp) nói chuyện riêng với một nhân viên giao hàng đang bị cảnh báo.

SỐ LIỆU THẬT (chỉ dùng đúng những số này):
- Nhân viên: {r['Nhân viên']} — bưu cục {r['Bưu cục']} — mức cảnh báo {r['Mức']}.
- Cảnh báo: {r['Cảnh báo']}.
- Ngưỡng %GTC cảnh báo {low:g}%, mục tiêu thưởng 80%.
- Số liệu theo ngày gần nhất (ngày: gán / GTC / %GTC):
{ngay_txt}

YÊU CẦU:
- Tiếng Việt, VĂN BẢN THUẦN (không markdown, không dấu * hay #), tối đa 1.500 ký tự, xưng "anh/chị" – "em".
- Gồm: câu mở đầu thân thiện có ghi nhận điểm tốt (nếu số liệu có ngày tốt thì nêu đúng ngày đó);
  cách nêu số liệu nhẹ nhàng; 4–5 câu hỏi mở đúng với các cảnh báo trên; 2–3 hành động cụ thể hai bên
  cùng thống nhất; câu chốt cam kết và hẹn ngày xem lại.
- Không quy kết, không đe dọa kỷ luật, không bịa nguyên nhân hay số liệu.
- Chỉ trả về kịch bản, không giải thích thêm."""


def one_on_one_panel(p: str, ident: str, guide: str, prompt_fn, filename: str) -> None:
    """Khung hướng dẫn 1:1 dùng chung: hiện hướng dẫn, nút AI soạn kịch bản riêng, nút tải .txt.
    `p` là tiền tố khóa ('hr', 'bc'); `ident` là mã đối tượng đang xem (nhân viên / bưu cục);
    `prompt_fn()` chỉ được gọi khi bấm nút AI."""
    k_txt = f"{p}_1on1_txt"
    with st.container(border=True):
        st.markdown(guide)
    kb = st.session_state.get(k_txt)
    kb = kb if kb and kb[0] == ident else None
    g1, g2 = st.columns(2, vertical_alignment="bottom")
    with g1:
        viet = st.button("AI SOẠN KỊCH BẢN 1:1 RIÊNG", key=f"btn_ai_{p}_1on1", width="stretch")
    with g2:
        txt = (guide.replace("#### ", "").replace("**", "").replace("_", "")
               + (f"\n\nKỊCH BẢN AI SOẠN:\n{kb[1]}" if kb else ""))
        st.download_button("TẢI HƯỚNG DẪN 1:1 (.TXT)", txt.encode("utf-8"), filename, "text/plain",
                           key=f"dl_{p}_1on1", width="stretch", on_click="ignore")
    if viet:
        with st.spinner("AI đang soạn kịch bản..."):
            ok_ai, ai_text = ask_ai_checked(prompt_fn())
        if ok_ai:
            st.session_state[k_txt] = (ident, clean_tele_text(ai_text))
            st.rerun()
        else:
            st.error(ai_text)
    if kb:
        st.markdown("**Kịch bản AI soạn** (đọc lại, chỉnh cho hợp trước khi dùng)")
        st.text_area("Kịch bản 1:1", kb[1], height=300, label_visibility="collapsed",
                     key=f"ta_{p}_1on1_" + hashlib.sha1(kb[1].encode()).hexdigest()[:10])


# ── Cảnh báo bưu cục %GTC thấp liên tục ─────────────────────────────────
def bc_daily(df: pd.DataFrame) -> pd.DataFrame:
    """Mỗi bưu cục một dòng mỗi ngày (bỏ dòng tổng): Bưu Cục, Ngày, Giá Trị (%, bình quân theo sản lượng), Trọng Số."""
    if df is None or df.empty:
        return pd.DataFrame(columns=["Bưu Cục", "Ngày", "Giá Trị", "Trọng Số"])
    d = df[~df["Bưu Cục"].map(is_total_row)].dropna(subset=["Giá Trị"])
    d = d.assign(_p=d["Giá Trị"] * d["Trọng Số"])
    g = d.groupby(["Bưu Cục", "Ngày"], as_index=False).agg(_p=("_p", "sum"), w=("Trọng Số", "sum"),
                                                            v=("Giá Trị", "mean"))
    g["Giá Trị"] = np.where(g["w"] > 0, g["_p"] / g["w"].where(g["w"] > 0), g["v"])
    return g.rename(columns={"w": "Trọng Số"})[["Bưu Cục", "Ngày", "Giá Trị", "Trọng Số"]]


def bc_warnings(gtc_day: pd.DataFrame, gan_day: pd.DataFrame, targets: dict, min_days: int = 3) -> pd.DataFrame:
    """Bưu cục có %GTC dưới mốc KPI liên tục từ `min_days` ngày có số liệu gần nhất trở lên.
    `targets`: {tên bưu cục: mốc %GTC}. Mức Cao khi kéo dài từ min_days+2 ngày hoặc ngày cuối thấp hơn mốc ≥ 10 điểm."""
    cols = ["Mức", "Bưu cục", "Số ngày liên tiếp dưới mốc", "%GTC ngày cuối", "%GTC 7 ngày",
            "%GTC 7 ngày trước", "Mốc KPI", "% Gán 7 ngày", "Sản lượng 7 ngày", "Ngày dữ liệu cuối",
            "_tu_ngay", "_score"]
    if gtc_day is None or gtc_day.empty:
        return pd.DataFrame(columns=cols)

    def wv(x):
        w = float(x["Trọng Số"].sum())
        return float((x["Giá Trị"] * x["Trọng Số"]).sum()) / w if w > 0 else None

    rows = []
    for bc, x in gtc_day.groupby("Bưu Cục"):
        x = x.sort_values("Ngày")
        tgt = float(targets.get(bc, 70.0))
        run, tu = 0, None
        for _, r in x.iloc[::-1].iterrows():
            if r["Giá Trị"] < tgt:
                run, tu = run + 1, r["Ngày"]
            else:
                break
        if run < min_days:
            continue
        last = x["Ngày"].iloc[-1]
        w7 = x[x["Ngày"] > last - pd.Timedelta(days=7)]
        wp = x[(x["Ngày"] <= last - pd.Timedelta(days=7)) & (x["Ngày"] > last - pd.Timedelta(days=14))]
        gn = gan_day[(gan_day["Bưu Cục"] == bc) & (gan_day["Ngày"] > last - pd.Timedelta(days=7))
                     & (gan_day["Ngày"] <= last)] if gan_day is not None and not gan_day.empty else gan_day
        p_last = float(x["Giá Trị"].iloc[-1])
        score = (2 if run >= min_days + 2 else 1) + (1 if tgt - p_last >= 10 else 0)
        rows.append({
            "Mức": "Cao" if score >= 2 else "Trung bình", "Bưu cục": bc,
            "Số ngày liên tiếp dưới mốc": run, "%GTC ngày cuối": p_last, "%GTC 7 ngày": wv(w7),
            "%GTC 7 ngày trước": wv(wp) if not wp.empty else None, "Mốc KPI": tgt,
            "% Gán 7 ngày": wv(gn) if gn is not None and not gn.empty else None,
            "Sản lượng 7 ngày": float(w7["Trọng Số"].sum()), "Ngày dữ liệu cuối": last,
            "_tu_ngay": tu, "_score": score,
        })
    if not rows:
        return pd.DataFrame(columns=cols)
    out = pd.DataFrame(rows, columns=cols)
    return out.sort_values(["_score", "Số ngày liên tiếp dưới mốc"], ascending=False).reset_index(drop=True)


def bc_1on1_guide(r, extra: dict) -> str:
    """Hướng dẫn Quản lý khu vực trao đổi 1:1 với NVXL (người phụ trách) của một bưu cục có %GTC thấp liên tục.
    `extra`: số liệu bổ sung đã tính sẵn (ca thấp nhất, TTS, nhân viên bị cảnh báo, biến động sản lượng)."""
    tgt = r["Mốc KPI"]
    so_lieu = [f"%GTC dưới mốc {tgt:g}% liên tục {r['Số ngày liên tiếp dưới mốc']} ngày "
               f"(từ {pd.Timestamp(r['_tu_ngay']):%d/%m} đến {pd.Timestamp(r['Ngày dữ liệu cuối']):%d/%m})",
               f"%GTC ngày cuối: {r['%GTC ngày cuối']:.2f}% — thấp hơn mốc {tgt - r['%GTC ngày cuối']:.2f} điểm"]
    if r["%GTC 7 ngày"] is not None and pd.notna(r["%GTC 7 ngày"]):
        so_lieu.append(f"%GTC 7 ngày: {r['%GTC 7 ngày']:.2f}%"
                       + (f" (7 ngày trước: {r['%GTC 7 ngày trước']:.2f}%)"
                          if r["%GTC 7 ngày trước"] is not None and pd.notna(r["%GTC 7 ngày trước"]) else ""))
    if r["% Gán 7 ngày"] is not None and pd.notna(r["% Gán 7 ngày"]):
        so_lieu.append(f"% gán đơn 7 ngày: {r['% Gán 7 ngày']:.2f}%")
    so_lieu += [v for v in (extra.get("vol"), extra.get("ca"), extra.get("tts"), extra.get("staff")) if v]
    hoi = ["Theo em, mấy ngày qua đơn không giao được chủ yếu vì lý do gì (khách hẹn lại, không liên lạc được, "
           "sai địa chỉ, không kịp giờ)? Em đã xem báo cáo lý do giao thất bại chưa?",
           "Hàng về bưu cục có trễ giờ không? Đơn được gán cho nhân viên lúc mấy giờ?"]
    gan = r["% Gán 7 ngày"]
    if gan is not None and pd.notna(gan) and gan < 95:
        hoi.append(f"% gán đơn chỉ {gan:.1f}%: còn đơn chưa gán hoặc gán trễ vì sao (thiếu người, hàng về muộn, "
                   "đơn sai tuyến)?")
    if extra.get("ca"):
        hoi.append("Ca có %GTC thấp nhất gặp vấn đề gì riêng (giờ hàng về, số người trong ca, loại hàng)?")
    if extra.get("staff"):
        hoi.append("Các bạn đang bị cảnh báo ở mục Cảnh báo nhân sự gặp khó khăn gì? Em đã trao đổi 1:1 với các bạn chưa?")
    if extra.get("vol_up"):
        hoi.append("Sản lượng tăng so với tuần trước: bưu cục có đủ người và đủ tuyến để giao hết không?")
    hoi.append("Em cần khu vực hỗ trợ gì nhất lúc này (người, xe, điều chỉnh tuyến, làm việc với kho)?")
    lam = ["Họp nhanh đầu ca 5–10 phút: nhắc mục tiêu %GTC trong ngày, chia tuyến, nhắc gọi khách trước khi giao.",
           "Gán đơn sớm ngay khi hàng về; xử lý dứt điểm đơn tồn, đơn hẹn lại từ hôm trước.",
           "Mỗi cuối ngày xem danh sách đơn thất bại theo lý do, giao lại ưu tiên trong sáng hôm sau.",
           "Kèm cặp riêng các nhân viên %GTC thấp; điều chỉnh tuyến nếu tuyến quá tải."]
    out = [f"#### Trao đổi 1:1 với NVXL bưu cục {r['Bưu cục']} — mức {r['Mức']}",
           "**1. Chuẩn bị (5–10 phút)**",
           "- Xem biểu đồ ở trên, ghi lại các con số chính:",
           *[f"  - {s}" for s in so_lieu],
           "- Hẹn riêng 20–30 phút (gặp trực tiếp hoặc gọi video), không trao đổi trong nhóm chung.",
           "**2. Mở đầu**",
           "- Ghi nhận nỗ lực của NVXL và bưu cục (ngày làm tốt, việc đã cải thiện).",
           "- Nói rõ mục đích: cùng tìm nguyên nhân và cách đưa %GTC về trên mốc, không phải để khiển trách.",
           "**3. Cùng nhìn số liệu**",
           "- Đưa số liệu thật, hỏi NVXL tự đánh giá trước: theo em vì sao bưu cục đang dưới mốc?",
           "**4. Tìm nguyên nhân — câu hỏi gợi ý**",
           *[f"- {q}" for q in hoi],
           "**5. Thống nhất việc cần làm và hỗ trợ**",
           *[f"- {x}" for x in lam],
           "**6. Chốt cam kết và hẹn theo dõi**",
           f"- Mục tiêu: %GTC từ {tgt:g}% trở lên trong 3 ngày tới; báo cáo nhanh kết quả mỗi cuối ngày.",
           "- Chốt 2–3 việc NVXL sẽ làm, việc khu vực sẽ hỗ trợ, và hẹn ngày xem lại (sau 3 ngày).",
           "- Ghi lại: nguyên nhân NVXL nêu, cam kết hai bên, ngày hẹn.",
           "**Lưu ý:** lắng nghe trước, hỏi câu mở; không so sánh bưu cục trước mặt người khác; "
           "tập trung vào việc cần làm, không quy lỗi cho cá nhân."]
    return "\n".join(("\n" + s) if s.startswith("**") else s for s in out)


def bc_1on1_prompt(r, extra: dict, ngay_txt: str) -> str:
    return f"""Bạn là Quản lý khu vực của GHN. Soạn KỊCH BẢN TRAO ĐỔI 1:1 để bạn nói chuyện riêng với NVXL
(người phụ trách) của một bưu cục đang có %GTC dưới mốc KPI nhiều ngày liên tục.

SỐ LIỆU THẬT (chỉ dùng đúng những số này):
- Bưu cục {r['Bưu cục']} — mức cảnh báo {r['Mức']}. Mốc %GTC {r['Mốc KPI']:g}%.
- %GTC dưới mốc liên tục {r['Số ngày liên tiếp dưới mốc']} ngày, ngày cuối {r['%GTC ngày cuối']:.2f}%.
- Số liệu bổ sung: {'; '.join(v for v in (extra.get('vol'), extra.get('ca'), extra.get('tts'), extra.get('staff')) if v) or 'không có'}.
- Theo ngày gần nhất (ngày: sản lượng / %GTC / % gán):
{ngay_txt}

YÊU CẦU:
- Tiếng Việt, VĂN BẢN THUẦN (không markdown, không dấu * hay #), tối đa 1.500 ký tự, xưng "anh/chị" – "em".
- Gồm: mở đầu ghi nhận nỗ lực; nêu số liệu ngắn gọn; 4–5 câu hỏi mở tìm nguyên nhân sát với số liệu
  (gán đơn, ca, nhân sự, sản lượng); 3 hành động cụ thể hai bên thống nhất; chốt mục tiêu và ngày hẹn xem lại.
- Không quy kết, không đe dọa kỷ luật, không bịa nguyên nhân hay số liệu. Chỉ trả về kịch bản."""


def notice_send_panel(p: str, ctx_sig: str, rewrite_label: str, bc: str, png_fn, filename: str) -> None:
    """Ô nội dung thông báo + chọn nơi gửi (Telegram và/hoặc nhiều nhóm GTalk) + nút gửi ảnh kèm thông báo.
    Dùng chung cho các mục có nút gửi; mọi khóa trạng thái bắt đầu bằng `p` (vd. 'rank', 'hr')."""
    if st.session_state.get(f"{p}_msg") and st.session_state.get(f"{p}_msg_ctx") != ctx_sig:
        st.warning("Bộ lọc hoặc số liệu đã đổi sau khi AI viết thông báo. "
                   f"Bấm '{rewrite_label}' để viết lại cho đúng.", icon="⚠️")
    msg_txt = st.text_area("Nội dung thông báo (đọc lại và sửa nếu cần trước khi gửi)",
                           key=f"{p}_msg", height=230)
    dai = len(clean_tele_text(msg_txt)) > TELE_CAPTION_MAX
    st.caption(f"{len(clean_tele_text(msg_txt))} ký tự · "
               + ("dài hơn 1.024 ký tự nên sẽ gửi ảnh trước, thông báo thành tin nhắn riêng."
                  if dai else "gửi kèm làm lời chú thích dưới ảnh."))
    # ── Chọn nơi gửi: Telegram và/hoặc một hay nhiều nhóm GTalk ─────────
    kenh_co = [k for k, on in (("Telegram", _tele_enabled()), ("GTalk", _gtalk_enabled())) if on]
    if GTALK_CFG_ERR:
        st.error(GTALK_CFG_ERR)
    if not kenh_co:
        st.info("Chưa cấu hình nơi gửi. Cần TELEGRAM_TOKEN + TELEGRAM_CHAT_ID (Telegram) "
                "và/hoặc GTALK_OA_TOKEN + GTALK_CHANNELS (GTalk) trên máy chủ.")
    kenh = st.multiselect("Gửi qua", kenh_co, default=kenh_co, key=f"{p}_channels")
    nhom: list[str] = []
    if "GTalk" in kenh:
        # Gợi ý sẵn nhóm có tên khớp bưu cục đang lọc; đổi bưu cục thì gợi ý lại.
        k_groups, k_for = f"{p}_gt_groups", f"{p}_gt_for"
        if st.session_state.get(k_for) != bc:
            bk = norm(bc)
            st.session_state[k_groups] = [
                g for g in GTALK_CHANNELS if norm(g) and (norm(g) in bk or bk in norm(g))]
            st.session_state[k_for] = bc
        st.session_state[k_groups] = [g for g in st.session_state.get(k_groups, []) if g in GTALK_CHANNELS]
        nhom = st.multiselect("Nhóm GTalk nhận (chọn được nhiều nhóm)", list(GTALK_CHANNELS), key=k_groups)
        if not nhom:
            st.caption("Chưa chọn nhóm GTalk nào. Tên nhóm khớp bưu cục đang lọc sẽ được chọn sẵn.")
    dich = ([] if "Telegram" not in kenh else ["Telegram"]) + [f"GTalk · {g}" for g in nhom]
    if dich:
        st.caption(f"Sẽ gửi tới {len(dich)} nơi: " + "; ".join(dich))
    co_noi_nhan = ("Telegram" in kenh) or bool(nhom)
    if st.button("GỬI ẢNH + THÔNG BÁO", key=f"btn_send_{p}_all",
                 disabled=not (co_noi_nhan and msg_txt.strip()), width="stretch"):
        with st.spinner(f"Đang gửi tới {len(dich)} nơi..."):
            kq = send_rank_everywhere(png_fn(), msg_txt, filename, "Telegram" in kenh, nhom)
        n_ok = sum(1 for _, ok_, _ in kq if ok_)
        (st.success if n_ok == len(kq) else st.warning if n_ok else st.error)(
            f"Đã gửi thành công {n_ok}/{len(kq)} nơi.")
        for ten, ok_, msg_ in kq:
            st.markdown(f"{'✅' if ok_ else '❌'} **{ten}** — {msg_}")


# ═══════════════════════════════════════════════════════════════════════
# 7. ĐĂNG NHẬP & PHÂN QUYỀN
# ═══════════════════════════════════════════════════════════════════════
for _k, _v in {"auth": None, "ai_cache": {}, "chat": [], "kpi_manual": {}}.items():
    st.session_state.setdefault(_k, _v)

ACCOUNTS = {
    ADMIN_ID: {"password": ADMIN_PASS, "role": "Giám Đốc.AM"},
    "USER": {"password": USER_PASS, "role": "Nhân Viên"},
}


@lru_cache(maxsize=1)
def logo_uri() -> str:
    """Logo công ty dạng data-URI (nhúng thẳng vào HTML). Trả về '' nếu chưa có file."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "logo.png")
    try:
        with open(path, "rb") as fh:
            return "data:image/png;base64," + base64.b64encode(fh.read()).decode("ascii")
    except OSError:
        return ""


def login_screen():
    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        if logo_uri():
            st.markdown(f'<div class="ghn-login-logo"><img src="{logo_uri()}" alt="GiaoHangNhanh"></div>',
                        unsafe_allow_html=True)
        st.markdown("""
        <div class="ghn-banner" style="text-align:center;">
            <h1>Trung Tâm Vận Hành</h1>
            <p>GIAO HÀNG NHANH — Hệ thống báo cáo nội bộ</p>
        </div>""", unsafe_allow_html=True)

        with st.form("login_form"):
            user_id = st.text_input("Mã nhân viên (ID)", placeholder="Nhập mã nhân viên")
            password = st.text_input("Mật khẩu", type="password")
            submitted = st.form_submit_button("ĐĂNG NHẬP", width="stretch")
            if submitted:
                info = ACCOUNTS.get(user_id.strip().upper())
                if info and password == info["password"]:
                    st.session_state.auth = {"id": user_id.strip().upper(), "role": info["role"]}
                    st.rerun()
                else:
                    st.error("ID hoặc mật khẩu không chính xác.")

        with st.expander("📱 Cài dashboard lên điện thoại"):
            st.markdown(APP_INSTALL_GUIDE)


if st.session_state.auth is None:
    login_screen()
    st.stop()

AUTH = st.session_state.auth
IS_ADMIN = AUTH["role"] == "Giám Đốc.AM"


# ═══════════════════════════════════════════════════════════════════════
# 8. NẠP TOÀN BỘ DỮ LIỆU
# ═══════════════════════════════════════════════════════════════════════
with st.spinner("Đang đồng bộ dữ liệu từ 12 Google Sheets..."):
    prefetch_sheets()
    # Cột thật đã đối chiếu với sheet:
    #   File1_BuuCuc / File2_TTS: Ngày | Cấp Quản Lý | Bưu cục | Volume | % Gán | % GTC | % Chuyển trả | Leadtime
    #   File3_TheoCa            : thêm cột "Loại Hàng (Ca)"
    #   Tỷ lệ Trả hàng          : Ngày | Cấp Quản Lý | Bưu cục | % Vol | % Return
    M_GTC = metric_frame("gtc_tong", [["% gtc"], ["gtc"], ["giao thanh cong"]])
    M_GAN = metric_frame("gtc_tong", [["% gan"], ["gan"]])
    M_GAN_TTS = metric_frame("gtc_tts", [["% gan"], ["gan"]])
    M_LEAD = metric_frame("gtc_tong", [["leadtime"], ["lead time"]], is_pct=False)
    M_CA = metric_frame("sl_theo_ca", [["% gtc"], ["gtc"]], extra_dim=[["loai hang"], ["ca"]])
    M_TRA = metric_frame("tra_hang", [["% return"], ["return"], ["chuyen tra"], ["tra hang"], ["tra"]])
    M_GTB = metric_frame("gtb_thu_tien",
                         [["da thu chuyen tra"], ["da thu"], ["gtb"], ["thu tien"]])
    M_TTS = metric_frame("gtc_tts", [["% gtc"], ["gtc tts"], ["gtc"]])
    M_ODR = metric_frame("odr_tts", [["odr"], ["ontime"], ["dung han"]])
    # OPR TikTok: Ngày | Quản Lý | Bưu cục | LTC (đơn lấy thành công) | %OPR TTS — trọng số là LTC
    M_OPR = metric_frame("opr_tts", [["opr"]], weight_keys=[["ltc"], ["lay thanh cong"]] + VOL_KEYS)
    M_DT = metric_frame("doanh_thu", [["doanh thu"]], weight_keys=None, is_pct=False)

    DF_KPI = safe_load("kpi")
    DF_KHM = safe_load("kh_moi")
    DF_PHEU = safe_load("pheu_kh")
    DF_LUONG = safe_load("ns_luong")
    DF_NSGTC = safe_load("ns_gtc")
    DF_NS_PREV = safe_load("ns_thang_truoc")   # năng suất tháng trước, cho tab Thi đua

# Lưu vào session_state để tab AI cố vấn đọc được
st.session_state["dataframes"] = {
    "GTC tổng": M_GTC, "Tỷ lệ trả hàng": M_TRA, "GTB thu tiền": M_GTB,
    "GTC TikTok": M_TTS, "ODR TikTok": M_ODR, "OPR TikTok": M_OPR, "Sản lượng theo ca": M_CA,
    "Doanh thu": M_DT, "Khách hàng mới": DF_KHM, "Phễu khách hàng": DF_PHEU,
    "Lương nhân viên": DF_LUONG, "Năng suất GTC": DF_NSGTC, "KPI": DF_KPI,
}

ALL_BC = bc_options(M_GTC, M_DT, DF_LUONG, DF_NSGTC)

def today_vn() -> pd.Timestamp:
    """Ngày hiện tại theo giờ Việt Nam (UTC+7), không phụ thuộc múi giờ máy chủ.
    Render chạy theo UTC nên nếu dùng datetime.now() thì từ 17h VN trở đi sẽ lệch 1 ngày."""
    return (pd.Timestamp.now('UTC') + timedelta(hours=7)).normalize().tz_localize(None)


TODAY_VN = today_vn()
YESTERDAY_VN = TODAY_VN - timedelta(days=1)

# Ngày mới nhất có trong dữ liệu — quét TOÀN BỘ 12 sheet, không chỉ vài sheet.
# Trước đây chỉ quét 3 khung nên nếu một sheet đọc sai ngày là cả dashboard lệch theo.
_ALL_FRAMES = [M_GTC, M_CA, M_TRA, M_GTB, M_TTS, M_ODR, M_OPR, M_DT,
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
QUICK_OPTIONS = ["Ngày", "Tuần", "Tháng"]   # bộ lọc "Chọn nhanh" của tab Vận hành, Kinh doanh
DEFAULT_7D_END = clamp(YESTERDAY_VN)
DEFAULT_7D_START = clamp(YESTERDAY_VN - timedelta(days=6))
if DEFAULT_7D_START > DEFAULT_7D_END:
    DEFAULT_7D_START = DEFAULT_7D_END


SHEET_LABELS = {
    "gtc_tong": "GTC tổng", "sl_theo_ca": "Sản lượng theo ca", "tra_hang": "Tỷ lệ trả hàng",
    "gtb_thu_tien": "GTB thu tiền", "gtc_tts": "GTC TikTok", "odr_tts": "ODR TikTok",
    "opr_tts": "OPR TikTok",
    "kpi": "Mốc KPI", "doanh_thu": "Doanh thu", "kh_moi": "Khách hàng mới",
    "pheu_kh": "Phễu khách hàng", "ns_luong": "Lương nhân viên", "ns_gtc": "Năng suất GTC",
    "ns_thang_truoc": "Năng suất tháng trước",
}


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
_logo_html = (f'<div class="ghn-logo-plate"><img src="{logo_uri()}" alt="GiaoHangNhanh"></div>'
              if logo_uri() else "")
st.markdown(f"""
<div class="ghn-banner">
  <div class="ghn-banner-row">{_logo_html}
    <div class="ghn-banner-text">
      <h1>Trung Tâm Vận Hành — GHN</h1>
      <p>Hiệu suất thực · Quyết định nhanh · AI cố vấn &nbsp;|&nbsp;
         {esc(AUTH['id'])} · {esc(AUTH['role'])} &nbsp;|&nbsp;
         Dữ liệu đến {REF_DATE:%d/%m/%Y} · Đồng bộ {datetime.now():%H:%M}</p>
    </div>
  </div>
</div>""", unsafe_allow_html=True)

NAV_PAGES = [
    ("tong_quan", "Tổng quan", ":material/dashboard:"),
    ("van_hanh", "Vận hành", ":material/local_shipping:"),
    ("kinh_doanh", "Kinh doanh", ":material/payments:"),
    ("kpi", "Tiến độ KPI", ":material/speed:"),
    ("nang_suat", "Năng suất & Lương", ":material/badge:"),
    ("canh_bao_ns", "Cảnh báo nhân sự", ":material/notification_important:"),
    ("thi_dua", "Thi đua", ":material/emoji_events:"),
    ("ai", "AI cố vấn", ":material/smart_toy:"),
]
_nav_keys = [k for k, _, _ in NAV_PAGES]
_nav_label = {k: f"{i} {t}" for k, t, i in NAV_PAGES}
# Mở lại đúng mục đang xem khi tải lại trang (lưu trên địa chỉ ?p=...)
if st.session_state.get("nav_page") not in _nav_keys:
    st.session_state["nav_page"] = (st.query_params.get("p") if st.query_params.get("p") in _nav_keys
                                    else _nav_keys[0])

with st.sidebar:
    st.markdown("<div class='nav-head'>MENU</div>", unsafe_allow_html=True)
    PAGE = st.radio("Menu", _nav_keys, format_func=_nav_label.get, key="nav_page",
                    label_visibility="collapsed",
                    on_change=lambda: st.session_state.update(_nav_changed=time.time()))
    if st.query_params.get("p") != PAGE:
        st.query_params["p"] = PAGE
    st.divider()
    st.markdown(f"### {AUTH['id']}")
    st.caption(f"Vai trò: {AUTH['role']}")
    st.divider()
    if st.button("Làm mới dữ liệu", width="stretch"):
        st.cache_data.clear()
        st.rerun()
    if st.button("Đăng xuất", width="stretch"):
        st.session_state.auth = None
        st.rerun()
    with st.expander("📱 Cài lên điện thoại"):
        st.markdown(APP_INSTALL_GUIDE)
    cau_hinh_loi = _kiem_tra_nguon()
    if cau_hinh_loi:
        st.divider()
        st.error("Khai báo nguồn dữ liệu sai:\n\n"
                 + "\n".join(f"- {e}" for e in cau_hinh_loi))
    errs = st.session_state.get("load_errors", {})
    if errs:
        st.divider()
        st.error(f"{len(errs)} nguồn chưa đọc được:\n\n"
                 + "\n".join(f"- **{SHEET_LABELS.get(k, k)}**: {v}" for k, v in errs.items()))

# Tab đang ẩn không vẽ widget nên Streamlit sẽ xóa giá trị bộ lọc của tab đó.
# Ghi lại giá trị ở đầu mỗi lượt chạy để bộ lọc còn nguyên khi quay lại tab.
_FILTER_KEY_PREFIXES = ("bc_", "quick_", "lh_", "nv_", "role_", "date_", "kpi_", "num_dt_", "rank_",
                        "td_", "hr_", "bcw_")
for _k in list(st.session_state.keys()):
    if isinstance(_k, str) and _k.startswith(_FILTER_KEY_PREFIXES):
        st.session_state[_k] = st.session_state[_k]

# Thứ tự tab: tổng quan → kết quả vận hành, kinh doanh → tiến độ KPI (tổng hợp cả hai)
# → nhóm nhân viên (năng suất, cảnh báo, thi đua) → AI.
# Mục đang mở do menu bên trái quyết định (PAGE). Chỉ chạy nội dung của mục đó cho nhanh.
if st.session_state.pop("_nav_changed", None):
    # Điện thoại: chọn xong mục thì tự đóng menu để thấy nội dung (máy tính giữ menu mở).
    st.html(f"""<script>/*{time.time()}*/
    if (window.innerWidth <= 640) {{
      var b = document.querySelector('[data-testid="stSidebarCollapseButton"] button');
      if (b) b.click();
    }}
    </script>""", unsafe_allow_javascript=True)


# ═══════════════════════════════════════════════════════════════════════
# TAB 1 — TỔNG QUAN
# ═══════════════════════════════════════════════════════════════════════
if PAGE == "tong_quan":
    with st.container():
        with st.columns([1.1, 2.9])[0]:
            bc_ov = st.selectbox("Phạm vi báo cáo", ALL_BC, key="bc_ov")

        g_gtc = scope(M_GTC, bc_ov)
        g_tra = scope(M_TRA, bc_ov)
        g_tts = scope(M_TTS, bc_ov)
        g_odr = scope(M_ODR, bc_ov)
        g_opr = scope(M_OPR, bc_ov)
        g_dt = scope(M_DT, bc_ov)

        t_gtc_ov = kpi_target([["kpi", "gtc"], ["% gtc"], ["gtc"]], 70.0,
                              exclude=["tts", "tiktok"], bc=bc_ov)
        t_tts_ov = kpi_target([["gtc tts"], ["tts"], ["tiktok"]], 80.0, bc=bc_ov)
        t_tra_ov = kpi_target([["tra hang"], ["tra"]], 5.0, bc=bc_ov)
        t_odr_ov = kpi_target([["odr"]], 98.0, bc=bc_ov)
        t_opr_ov = kpi_target([["opr"]], 100.0, bc=bc_ov)

        p_gtc = get_period_data(g_gtc, REF_DATE)
        p_tra = get_period_data(g_tra, REF_DATE)
        p_tts = get_period_data(g_tts, REF_DATE)
        p_odr = get_period_data(g_odr, REF_DATE)
        p_opr = get_period_data(g_opr, REF_DATE)
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

        _sub_tab1 = st.tabs(['Tổng hợp', 'Bưu cục diện đỏ', 'Diễn biến 30 ngày', 'Nhận định AI'])
        with _sub_tab1[0]:
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
            c5, c6, c7, _ = st.columns(4)
            with c5:
                st.markdown(metric_card("ODR TikTok", f"{p_odr['n']:,.2f}%",
                                        p_odr["n"] - p_odr["n1"], "%", True, p_odr["has_n1"],
                                        sub=f"· mốc {t_odr_ov:g}%"), unsafe_allow_html=True)
            with c6:
                st.markdown(metric_card("OPR TikTok", f"{p_opr['n']:,.2f}%",
                                        p_opr["n"] - p_opr["n1"], "%", True, p_opr["has_n1"],
                                        sub=f"· mốc {t_opr_ov:g}%"), unsafe_allow_html=True)
            with c7:
                # Trả hàng: càng thấp càng tốt nên tăng là xấu (đỏ)
                st.markdown(metric_card("Tỷ lệ trả hàng", f"{p_tra['n']:,.2f}%",
                                        p_tra["n"] - p_tra["n1"], "%", False, p_tra["has_n1"],
                                        sub=f"· tối đa {t_tra_ov:g}%"), unsafe_allow_html=True)

            section("Cảnh báo — chỉ số chưa đạt mốc")
            checks = [
                ("GTC tổng", p_gtc["n"], t_gtc_ov, True, "tỷ lệ giao thành công toàn khu vực"),
                ("GTC TikTok", p_tts["n"], t_tts_ov, True, "đơn sàn TikTok Shop"),
                ("ODR TikTok", p_odr["n"], t_odr_ov, True, "cam kết đúng hạn với sàn, thấp là bị phạt"),
                ("OPR TikTok", p_opr["n"], t_opr_ov, True, "lấy hàng đúng hạn với sàn"),
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

            # Tóm tắt cảnh báo nhân sự (chi tiết ở tab riêng), dùng ngưỡng đang chỉnh bên tab đó
            hr_day_ov = hr_daily(DF_NSGTC)
            hr_ov = pd.DataFrame()
            if bc_ov != "Tất cả" and not hr_day_ov.empty:
                hr_day_ov = hr_day_ov[hr_day_ov["Bưu cục"].map(norm) == norm(bc_ov)]
            if not hr_day_ov.empty:
                ss = st.session_state
                hr_ov = hr_warnings(hr_day_ov, hr_day_ov["Ngày"].max(),
                                    ss.get("hr_low", HR_DEFAULTS["low"]), int(ss.get("hr_streak", HR_DEFAULTS["streak"])),
                                    ss.get("hr_drop", HR_DEFAULTS["drop"]), int(ss.get("hr_absent", HR_DEFAULTS["absent"])),
                                    ss.get("hr_ratio", HR_DEFAULTS["ratio"]))
                if not hr_ov.empty:
                    n_cao_ov = int((hr_ov["Mức"] == "Cao").sum())
                    st.markdown(
                        f"<div class='ghn-alert {'danger' if n_cao_ov else ''}'>"
                        f"<span class='a-tag {'tag-danger' if n_cao_ov else 'tag-warn'}'>NHÂN SỰ</span>"
                        f"<b>{len(hr_ov)}</b> nhân viên cần chú ý, <b>{n_cao_ov}</b> người mức Cao. "
                        f"Xem chi tiết, tải ảnh và gửi thông báo ở mục <b>Cảnh báo nhân sự</b>.</div>",
                        unsafe_allow_html=True)

        with _sub_tab1[1]:
            # ── Cảnh báo bưu cục %GTC thấp liên tục ────────────────────────────
            section("Cảnh báo bưu cục — %GTC thấp liên tục")
            with st.columns([1.1, 2.9])[0]:
                bcw_days = st.number_input("Dưới mốc KPI từ (ngày liên tiếp)", 2, 14, 3, 1, key="bcw_days")
            gtc_day = bc_daily(M_GTC)
            gan_day = bc_daily(M_GAN)
            if bc_ov != "Tất cả" and not gtc_day.empty:
                gtc_day = gtc_day[gtc_day["Bưu Cục"].map(norm) == norm(bc_ov)]
            targets_bc = {b: kpi_target([["kpi", "gtc"], ["% gtc"], ["gtc"]], 70.0, exclude=["tts", "tiktok"], bc=b)
                          for b in gtc_day["Bưu Cục"].unique()}
            bw = bc_warnings(gtc_day, gan_day, targets_bc, int(bcw_days))
            if gtc_day.empty:
                note("Chưa có số liệu %GTC theo từng bưu cục.")
            elif bw.empty:
                st.markdown(
                    "<div class='ghn-alert ok'><span class='a-tag tag-ok'>ỔN ĐỊNH</span>"
                    f"Không có bưu cục nào dưới mốc %GTC từ {int(bcw_days)} ngày liên tiếp.</div>",
                    unsafe_allow_html=True)
            else:
                n_cao_bc = int((bw["Mức"] == "Cao").sum())
                st.markdown(
                    f"<div class='ghn-alert {'danger' if n_cao_bc else ''}'>"
                    f"<span class='a-tag {'tag-danger' if n_cao_bc else 'tag-warn'}'>"
                    f"{'CẦN XỬ LÝ' if n_cao_bc else 'THEO DÕI'}</span>"
                    f"<b>{len(bw)}</b> bưu cục có %GTC dưới mốc từ {int(bcw_days)} ngày liên tiếp, "
                    f"<b>{n_cao_bc}</b> bưu cục mức Cao.</div>", unsafe_allow_html=True)
                st.caption("👆 Bấm vào ô vuông đầu dòng để xem số liệu GTC và hướng dẫn trao đổi 1:1 với NVXL bưu cục đó.")
                chon_bc = st.dataframe(
                    bw.drop(columns=["_tu_ngay", "_score"]), width="stretch", hide_index=True,
                    on_select="rerun", selection_mode="single-row", key="tbl_bc_warn",
                    column_config={
                        "Số ngày liên tiếp dưới mốc": st.column_config.NumberColumn(format="%d ngày"),
                        "%GTC ngày cuối": st.column_config.NumberColumn(format="%.2f%%"),
                        "%GTC 7 ngày": st.column_config.NumberColumn(format="%.2f%%"),
                        "%GTC 7 ngày trước": st.column_config.NumberColumn(format="%.2f%%"),
                        "Mốc KPI": st.column_config.NumberColumn(format="%.0f%%"),
                        "% Gán 7 ngày": st.column_config.NumberColumn(format="%.2f%%"),
                        "Sản lượng 7 ngày": st.column_config.NumberColumn(format="%,d"),
                        "Ngày dữ liệu cuối": st.column_config.DateColumn(format="DD/MM/YYYY")})
                dong_bc = [i for i in chon_bc.selection.rows if 0 <= i < len(bw)]
                if dong_bc:
                    r_bc = bw.iloc[dong_bc[0]]
                    ten_bc, tgt_bc, last_bc = r_bc["Bưu cục"], float(r_bc["Mốc KPI"]), r_bc["Ngày dữ liệu cuối"]
                    section(f"Chi tiết bưu cục: {ten_bc}")
                    a30 = last_bc - timedelta(days=29)
                    g_bc = sl(scope(M_GTC, ten_bc), a30, last_bc)
                    gan_bc = sl(scope(M_GAN, ten_bc), a30, last_bc)

                    # Số liệu bổ sung cho hướng dẫn 1:1
                    extra_bc: dict = {}
                    d_bc = gtc_day[gtc_day["Bưu Cục"] == ten_bc]
                    v7 = float(d_bc[d_bc["Ngày"] > last_bc - timedelta(days=7)]["Trọng Số"].sum())
                    vp = float(d_bc[(d_bc["Ngày"] <= last_bc - timedelta(days=7))
                                    & (d_bc["Ngày"] > last_bc - timedelta(days=14))]["Trọng Số"].sum())
                    if vp > 0:
                        extra_bc["vol"] = (f"sản lượng 7 ngày {v7:,.0f} đơn, "
                                           f"{'tăng' if v7 >= vp else 'giảm'} {abs(v7 / vp - 1) * 100:.0f}% so với 7 ngày trước")
                        extra_bc["vol_up"] = v7 > vp * 1.1
                    ca7 = sl(scope(M_CA, ten_bc), last_bc - timedelta(days=6), last_bc)
                    if not ca7.empty and "Chiều" in ca7.columns:
                        ca_r = (ca7.assign(_p=ca7["Giá Trị"].fillna(0) * ca7["Trọng Số"]).groupby("Chiều")
                                   .agg(_p=("_p", "sum"), w=("Trọng Số", "sum")))
                        ca_r = ca_r[ca_r["w"] > 0]
                        if len(ca_r) > 1:
                            ca_r["r"] = ca_r["_p"] / ca_r["w"]
                            thap = ca_r["r"].idxmin()
                            extra_bc["ca"] = f"ca có %GTC thấp nhất 7 ngày: {thap} ({ca_r.loc[thap, 'r']:.1f}%)"
                    tts7 = sl(scope(M_TTS, ten_bc), last_bc - timedelta(days=6), last_bc)
                    if not tts7.empty:
                        extra_bc["tts"] = f"%GTC TikTok 7 ngày: {wavg(tts7['Giá Trị'], tts7['Trọng Số']):.1f}%"
                    nv_bc = (hr_ov[hr_ov["Bưu cục"].map(norm) == norm(ten_bc)] if not hr_ov.empty else hr_ov)
                    if nv_bc is not None and not nv_bc.empty:
                        cao = nv_bc[nv_bc["Mức"] == "Cao"]["Nhân viên"].head(5).tolist()
                        extra_bc["staff"] = (f"{len(nv_bc)} nhân viên đang bị cảnh báo"
                                             + (f" (mức Cao: {', '.join(cao)})" if cao else ""))

                    b1, b2, b3, b4 = st.columns(4)
                    p7b, ppb = r_bc["%GTC 7 ngày"], r_bc["%GTC 7 ngày trước"]
                    co7, cop = p7b is not None and pd.notna(p7b), ppb is not None and pd.notna(ppb)
                    with b1:
                        st.markdown(metric_card("%GTC ngày cuối", f"{r_bc['%GTC ngày cuối']:.2f}%",
                                                r_bc["%GTC ngày cuối"] - tgt_bc, "%", True, True,
                                                sub=f"so với mốc {tgt_bc:g}%"), unsafe_allow_html=True)
                    with b2:
                        st.markdown(metric_card("%GTC 7 ngày", f"{p7b:.2f}%" if co7 else "—",
                                                (p7b - ppb) if co7 and cop else None, "%", True, cop,
                                                sub="so với 7 ngày trước"), unsafe_allow_html=True)
                    with b3:
                        gb = r_bc["% Gán 7 ngày"]
                        st.markdown(metric_card("% Gán đơn 7 ngày",
                                                f"{gb:.2f}%" if gb is not None and pd.notna(gb) else "—", None,
                                                sub=f"sản lượng 7 ngày {r_bc['Sản lượng 7 ngày']:,.0f} đơn"),
                                    unsafe_allow_html=True)
                    with b4:
                        st.markdown(metric_card("Ngày liên tiếp dưới mốc", f"{int(r_bc['Số ngày liên tiếp dưới mốc'])} ngày",
                                                None, sub=f"từ {pd.Timestamp(r_bc['_tu_ngay']):%d/%m} · mức {r_bc['Mức']}",
                                                accent=r_bc["Mức"] == "Cao"), unsafe_allow_html=True)
                    combo_chart(g_bc, f"Sản lượng, %GTC và % gán đơn — {ten_bc} (30 ngày)", "Sản lượng", "% GTC",
                                tgt_bc, gan_df=gan_bc)

                    section("Hướng dẫn trao đổi 1:1 với NVXL bưu cục")

                    def bc_prompt() -> str:
                        g_d, gan_d = daily(g_bc).tail(14), daily(gan_bc)
                        gan_map = dict(zip(gan_d["Ngày"], gan_d["Giá Trị"]))
                        ngay_txt = "\n".join(
                            f"  {x['Ngày']:%d/%m}: {x['Trọng Số']:,.0f} / {x['Giá Trị']:.1f}% / "
                            + (f"{gan_map[x['Ngày']]:.1f}%" if x["Ngày"] in gan_map else "—")
                            for _, x in g_d.iterrows())
                        return bc_1on1_prompt(r_bc, extra_bc, ngay_txt)

                    one_on_one_panel("bc", ten_bc, bc_1on1_guide(r_bc, extra_bc), bc_prompt,
                                     f"trao_doi_1_1_NVXL_{re.sub(r'[^a-z0-9]+', '_', norm(ten_bc)).strip('_')}.txt")

        with _sub_tab1[2]:
            section("Diễn biến các chỉ số vận hành — 30 ngày gần nhất")
            w30 = REF_DATE - timedelta(days=29)
            series = [("%GTC tổng", daily(sl(g_gtc, w30, REF_DATE)), PRIMARY),
                      ("%GTC TikTok", daily(sl(g_tts, w30, REF_DATE)), "#00B4D8"),
                      ("ODR TikTok", daily(sl(g_odr, w30, REF_DATE)), SUCCESS),
                      ("%Trả hàng", daily(sl(g_tra, w30, REF_DATE)), DANGER)]
            series = [(n, d, c) for n, d, c in series if not d.empty]
            if series:
                fig_ov = go.Figure()
                pos_ov = label_layout([d["Giá Trị"] for _, d, _ in series])
                for (name, d, color), (tpos, off) in zip(series, pos_ov):
                    fig_ov.add_trace(go.Scatter(x=d["Ngày"], y=d["Giá Trị"], name=name,
                                                mode="lines+markers+text",
                                                line=dict(color=color, width=3), marker=dict(size=6),
                                                hoverinfo="x+y+name",
                                                text=point_labels(d["Giá Trị"], pct_label, 10, off),
                                                textposition=tpos, cliponaxis=False,
                                                textfont=dict(color=color, **LABEL_FONT)))
                fig_ov.add_hline(y=t_gtc_ov, line_dash="dot", line_color=ACCENT, line_width=2,
                                 annotation_text="Mốc GTC", annotation_position="top left")
                fig_ov.update_yaxes(ticksuffix="%")
                fig_ov.update_xaxes(tickformat="%d/%m")
                fig_ov.update_layout(height=480)
                st.plotly_chart(fig_ov, width="stretch")
                if max(len(d) for _, d, _ in series) < 2:
                    st.caption("Mới có 1 ngày dữ liệu — biểu đồ sẽ đầy đủ khi sheet tích lũy thêm ngày.")
            else:
                note("Chưa có dữ liệu vận hành trong 30 ngày gần nhất.")

        with _sub_tab1[3]:
            ai_advisor(
                "ov", "Tổng quan",
                f"""Ngày phân tích: {REF_DATE:%d/%m/%Y}. Phạm vi: {bc_ov}.

CHỈ SỐ HÔM NAY (so với hôm trước):
- Sản lượng: {p_vol['n']:,.0f} đơn (hôm trước {p_vol['n1']:,.0f})
- %GTC tổng: {p_gtc['n']:.2f}% (hôm trước {p_gtc['n1']:.2f}%) — mốc KPI {t_gtc_ov:.2f}%
- %GTC TikTok: {p_tts['n']:.2f}% (hôm trước {p_tts['n1']:.2f}%) — mốc KPI {t_tts_ov:.2f}%
- ODR TikTok: {p_odr['n']:.2f}% (hôm trước {p_odr['n1']:.2f}%) — mốc {t_odr_ov:.2f}%
- Tỷ lệ trả hàng: {p_tra['n']:.2f}% (hôm trước {p_tra['n1']:.2f}%) — ngưỡng tối đa {t_tra_ov:.2f}%

LŨY KẾ THÁNG:
- Doanh thu tháng: {fmt_money(p_dt['m'])} (tháng trước {fmt_money(p_dt['m1'])})

NHỊP TUẦN:
- %GTC tuần này {p_gtc['w']:.2f}% so với tuần trước {p_gtc['w1']:.2f}%
- %Trả hàng tuần này {p_tra['w']:.2f}% so với tuần trước {p_tra['w1']:.2f}%

CHỈ SỐ ĐANG TRƯỢT MỐC: {', '.join(f"{n} ({a:.2f}% / mốc {t:.2f}%)" for _, n, a, t, _, _ in issues) if issues else 'không có, mọi chỉ số đạt mốc'}""")


# ═══════════════════════════════════════════════════════════════════════
# TAB 2 — VẬN HÀNH
# ═══════════════════════════════════════════════════════════════════════
if PAGE == "van_hanh":
    with st.container():
        f1, f2, f3 = st.columns([1.1, 1.5, 1.2])
        with f1:
            bc_vh = st.selectbox("Bưu cục", ALL_BC, key="bc_vh")
        with f2:
            if st.session_state.get("quick_vh") not in QUICK_OPTIONS:   # giá trị cũ "7 ngày gần nhất"
                st.session_state.pop("quick_vh", None)
            quick_vh = st.radio("Chọn nhanh", QUICK_OPTIONS, horizontal=True, key="quick_vh")
        if quick_vh == "Ngày":
            a_vh, b_vh = DEFAULT_N1, DEFAULT_N1
        elif quick_vh == "Tuần":
            a_vh, b_vh = REF_DATE - timedelta(days=REF_DATE.weekday()), REF_DATE
        else:  # "Tháng"
            a_vh, b_vh = REF_DATE.replace(day=1), REF_DATE
        with f3:
            # sync_token = lựa chọn Chọn nhanh -> đổi nút là ô ngày tự cập nhật theo.
            a_vh, b_vh = synced_range_picker("Khoảng ngày", a_vh, b_vh, "date_vh",
                                             sync_token=quick_vh)

        # Biểu đồ theo ngày: lọc 1 ngày (hoặc vài ngày) thì vẫn vẽ 7 ngày gần nhất tính đến ngày cuối,
        # nếu không biểu đồ chỉ có 1 điểm, nhìn như không có dữ liệu. Thẻ số và bảng vẫn theo đúng khoảng đã chọn.
        chart_a = a_vh if (b_vh - a_vh).days >= 6 else b_vh - timedelta(days=6)

        def cs(frame):
            return sl(scope(frame, bc_vh), chart_a, b_vh)

        st.caption(f"Đang xem {a_vh:%d/%m/%Y} – {b_vh:%d/%m/%Y} · Bưu cục: {bc_vh}. "
                   "Mọi tỷ lệ % tính bằng trung bình có trọng số theo sản lượng."
                   + (f" Biểu đồ theo ngày hiển thị 7 ngày gần nhất ({chart_a:%d/%m} – {b_vh:%d/%m}) để thấy diễn biến."
                      if chart_a != a_vh else ""))

        t_gtc_vh = kpi_target([["kpi", "gtc"], ["% gtc"], ["gtc"]], 70.0,
                              exclude=["tts", "tiktok"], bc=bc_vh)
        t_tts_vh = kpi_target([["gtc tts"], ["tts"], ["tiktok"]], 80.0, bc=bc_vh)
        t_tra_vh = kpi_target([["tra hang"], ["tra"]], 5.0, bc=bc_vh)

        s_gtc = sl(scope(M_GTC, bc_vh), a_vh, b_vh)
        s_tra = sl(scope(M_TRA, bc_vh), a_vh, b_vh)
        s_gtb = sl(scope(M_GTB, bc_vh), a_vh, b_vh)
        s_tts = sl(scope(M_TTS, bc_vh), a_vh, b_vh)
        s_odr = sl(scope(M_ODR, bc_vh), a_vh, b_vh)
        s_opr = sl(scope(M_OPR, bc_vh), a_vh, b_vh)
        # Mốc OPR lấy ở sheet KPI nếu có cột OPR; chưa có thì không vẽ đường mốc (không tự đặt số).
        t_opr_vh = kpi_target([["opr"]], 0.0, bc=bc_vh) or None
        t_odr_vh = kpi_target([["odr"]], 98.0, bc=bc_vh)
        s_gan = sl(scope(M_GAN, bc_vh), a_vh, b_vh)
        s_gan_tts = sl(scope(M_GAN_TTS, bc_vh), a_vh, b_vh)
        s_lead = sl(scope(M_LEAD, bc_vh), a_vh, b_vh)
        s_ca = sl(scope(M_CA, bc_vh), a_vh, b_vh)

        _sub_tab2 = st.tabs(['GTC tổng', 'Theo ca', 'TikTok Shop', 'Trả hàng & GTB', 'Nhận định AI'])
        with _sub_tab2[0]:
            # 2.1 GTC tổng
            section("1. Báo cáo GTC tổng")
            period_cards(scope(M_GTC, bc_vh), REF_DATE, "%", True, "wavg", "%GTC")
            cA, cB = st.columns([1.6, 1])
            with cA:
                combo_chart(cs(M_GTC), "Sản lượng, %GTC và % gán đơn theo ngày", "Sản lượng", "% GTC", t_gtc_vh,
                            gan_df=cs(M_GAN))
            with cB:
                bc_bar_chart(sl(M_GTC, a_vh, b_vh), t_gtc_vh, True, "So sánh giữa bưu cục")

        with _sub_tab2[1]:
            # 2.2 Sản lượng và %GTC theo ca
            section("2. Sản lượng và %GTC theo ca làm việc")
            lh_options = (sorted({x for x in M_CA["Chiều"].dropna().astype(str).str.strip().unique()
                                  if x and x.lower() != "nan"})
                          if "Chiều" in M_CA.columns else [])
            lh_pick = st.multiselect("Loại hàng / ca làm việc", lh_options, default=lh_options, key="lh_vh")
            def ca_daily(d):
                if lh_pick and "Chiều" in d.columns:
                    d = d[d["Chiều"].isin(lh_pick)]
                if d.empty or "Chiều" not in d.columns:
                    return pd.DataFrame()
                g = (d.assign(_p=d["Giá Trị"].fillna(0) * d["Trọng Số"])
                      .groupby(["Ngày", "Chiều"], as_index=False)
                      .agg(_p=("_p", "sum"), w=("Trọng Số", "sum")))
                g["r"] = np.where(g["w"] > 0, g["_p"] / g["w"], np.nan)
                return g

            g_ca = ca_daily(s_ca)            # bảng: đúng khoảng đã chọn
            g_ca_chart = ca_daily(cs(M_CA))  # biểu đồ: ít nhất 7 ngày
            if not g_ca.empty:

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
                    for i, ca in enumerate(sorted(g_ca_chart["Chiều"].unique())):
                        sub_ca = g_ca_chart[g_ca_chart["Chiều"] == ca]
                        fig_ca1.add_trace(go.Bar(x=sub_ca["Ngày"], y=sub_ca["w"], name=ca,
                                                 marker_color=palette[i % len(palette)],
                                                 marker_line_width=0,
                                                 hoverinfo="x+y+name", text=point_labels(sub_ca["w"], num_label),
                                                 textposition="inside", insidetextanchor="middle",
                                                 textfont=dict(color="#FFFFFF", **LABEL_FONT)))
                    fig_ca1.update_layout(barmode="stack", title="Sản lượng theo ca", height=430)
                    fig_ca1.update_xaxes(tickformat="%d/%m")
                    st.plotly_chart(fig_ca1, width="stretch")
                with cD:
                    fig_ca2 = go.Figure()
                    ca_list = sorted(g_ca_chart["Chiều"].unique())
                    pos_ca = label_layout([g_ca_chart.loc[g_ca_chart["Chiều"] == ca, "r"] for ca in ca_list])
                    for i, ca in enumerate(ca_list):
                        sub_ca = g_ca_chart[g_ca_chart["Chiều"] == ca]
                        fig_ca2.add_trace(go.Scatter(x=sub_ca["Ngày"], y=sub_ca["r"], name=ca,
                                                     mode="lines+markers+text",
                                                     line=dict(color=palette[i % len(palette)], width=3),
                                                     marker=dict(size=6), hoverinfo="x+y+name",
                                                     text=point_labels(sub_ca["r"], pct_label, 10, pos_ca[i][1]),
                                                     textposition=pos_ca[i][0], cliponaxis=False,
                                                     textfont=dict(color=palette[i % len(palette)],
                                                                   **LABEL_FONT)))
                    fig_ca2.update_layout(title="%GTC theo ca", height=430)
                    fig_ca2.update_yaxes(ticksuffix="%", range=[0, 100])
                    fig_ca2.update_xaxes(tickformat="%d/%m")
                    st.plotly_chart(fig_ca2, width="stretch")
            else:
                note("Chưa đọc được cột ca hoặc loại hàng trong sheet Sản lượng theo ca.")

        with _sub_tab2[2]:
            # 2.3 GTC TTS
            section("3. GTC TikTok Shop")
            period_cards(scope(M_TTS, bc_vh), REF_DATE, "%", True, "wavg", "%GTC TTS")
            cG, cH = st.columns([1.6, 1])
            with cG:
                combo_chart(cs(M_TTS), "Sản lượng, %GTC và % gán đơn TikTok Shop", "Sản lượng TTS", "% GTC TTS",
                            t_tts_vh, gan_df=cs(M_GAN_TTS))
            with cH:
                bc_bar_chart(sl(M_TTS, a_vh, b_vh), t_tts_vh, True, "So sánh giữa bưu cục")

            # 2.4 ODR TTS
            section("4. ODR TikTok Shop — cam kết giao đúng hạn với sàn")
            period_cards(scope(M_ODR, bc_vh), REF_DATE, "%", True, "wavg", "ODR")
            line_chart(cs(M_ODR), "Tỷ lệ ODR theo ngày", ACCENT, "%", t_odr_vh)

            # 2.4b OPR TTS
            section("5. OPR TikTok Shop — lấy hàng đúng hạn")
            period_cards(scope(M_OPR, bc_vh), REF_DATE, "%", True, "wavg", "OPR")
            cO, cP = st.columns([1.6, 1])
            with cO:
                combo_chart(cs(M_OPR), "Đơn lấy thành công và %OPR TikTok Shop", "Đơn lấy thành công", "% OPR",
                            t_opr_vh, max_labels=9)
            with cP:
                bc_bar_chart(sl(M_OPR, a_vh, b_vh), t_opr_vh, True, "So sánh giữa bưu cục")

        with _sub_tab2[3]:
            # 2.5 Trả hàng
            section("6. Tỷ lệ trả hàng (càng thấp càng tốt)")
            period_cards(scope(M_TRA, bc_vh), REF_DATE, "%", False, "wavg", "%Trả hàng")
            cE, cF = st.columns([1.6, 1])
            with cE:
                line_chart(cs(M_TRA), "Tỷ lệ trả hàng theo ngày", DANGER, "%", t_tra_vh)
            with cF:
                bc_bar_chart(sl(M_TRA, a_vh, b_vh), t_tra_vh, False, "So sánh giữa bưu cục")

            # 2.6 GTB thu tiền
            section("7. Tỷ lệ GTB — giao thất bại nhưng thu được tiền")
            period_cards(scope(M_GTB, bc_vh), REF_DATE, "%", True, "wavg", "%GTB")
            cQ, cR = st.columns([1.6, 1])
            with cQ:
                line_chart(cs(M_GTB), "Tỷ lệ GTB thu tiền theo ngày", SUCCESS, "%")
            with cR:
                bc_bar_chart(sl(M_GTB, a_vh, b_vh), None, True, "So sánh giữa bưu cục")

        with _sub_tab2[4]:
            def _w(d):
                return wavg(d["Giá Trị"], d["Trọng Số"]) if d is not None and not d.empty else 0.0

            ai_advisor(
                "vh", "Vận hành",
                f"""Khoảng ngày: {a_vh:%d/%m/%Y} – {b_vh:%d/%m/%Y}. Bưu cục: {bc_vh}.
Loại hàng đang lọc: {', '.join(lh_pick) if lh_pick else 'tất cả'}.

BÌNH QUÂN TRONG KHOẢNG ĐÃ LỌC:
- %GTC tổng: {_w(s_gtc):.2f}% (mốc KPI {t_gtc_vh:.2f}%)
- %Trả hàng: {_w(s_tra):.2f}% (ngưỡng tối đa {t_tra_vh:.2f}%)
- %GTB thu tiền: {_w(s_gtb):.2f}%
- %GTC TikTok: {_w(s_tts):.2f}% (mốc KPI {t_tts_vh:.2f}%)
- ODR TikTok: {_w(s_odr):.2f}% (mốc {t_odr_vh:.2f}%)
- OPR TikTok (lấy hàng đúng hạn): {_w(s_opr):.2f}%{f" (mốc {t_opr_vh:.2f}%)" if t_opr_vh else ""}
- Tỷ lệ gán: {_w(s_gan):.2f}%
- Leadtime bình quân: {s_lead['Giá Trị'].mean() if not s_lead.empty else 0:.2f} giờ
- Tổng sản lượng: {s_gtc['Trọng Số'].sum() if not s_gtc.empty else 0:,.0f} đơn""")


# ═══════════════════════════════════════════════════════════════════════
# TAB 3 — KINH DOANH
# ═══════════════════════════════════════════════════════════════════════
if PAGE == "kinh_doanh":
    with st.container():
        k1, k3, k4 = st.columns([1.1, 1.7, 1.3])
        with k1:
            bc_kd = st.selectbox("Bưu cục", ALL_BC, key="bc_kd")
        with k3:
            if st.session_state.get("quick_kd") not in QUICK_OPTIONS:   # giá trị cũ "7 ngày gần nhất"
                st.session_state.pop("quick_kd", None)
            quick_kd = st.radio("Chọn nhanh", QUICK_OPTIONS, horizontal=True, key="quick_kd")
        if quick_kd == "Ngày":
            a_kd, b_kd = DEFAULT_N1, DEFAULT_N1
        elif quick_kd == "Tuần":
            a_kd, b_kd = REF_DATE - timedelta(days=REF_DATE.weekday()), REF_DATE
        else:  # "Tháng"
            a_kd, b_kd = REF_DATE.replace(day=1), REF_DATE
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
            st.warning("Chưa đọc được sheet doanh thu. Kiểm tra lại link và quyền chia sẻ của sheet "
                       "doanh thu.", icon="⚠️")
        else:
            dt_max = dt_scope["Ngày"].max()
            if pd.notna(dt_max) and dt_max.to_period("M") != REF_DATE.to_period("M"):
                st.warning(
                    f"Sheet doanh thu mới có dữ liệu đến **{dt_max:%d/%m/%Y}**, trong khi ngày phân "
                    f"tích là **{REF_DATE:%d/%m/%Y}**. Vì vậy con số 'lũy kế tháng này' đang bằng 0. "
                    "Cập nhật sheet doanh thu là hết.", icon="⚠️")

        _sub_tab3 = st.tabs(['Doanh thu', 'Khách hàng', 'Nhận định AI'])
        with _sub_tab3[0]:
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
                    st.markdown(metric_card("Dự kiến cuối tháng", fmt_money(forecast_dt), None,
                                            sub="theo tốc độ hiện tại", accent=True),
                                unsafe_allow_html=True)
                with e3:
                    thieu = max(target_dt - forecast_dt, 0)
                    st.markdown(metric_card("Còn thiếu so với mục tiêu", fmt_money(thieu), None,
                                            sub="nếu giữ nguyên tốc độ"), unsafe_allow_html=True)

            section("3. Biểu đồ doanh thu theo ngày")
            # Lọc 1 ngày / vài ngày thì biểu đồ vẫn vẽ 7 ngày gần nhất để thấy diễn biến.
            kd_chart_a = a_kd if (b_kd - a_kd).days >= 6 else b_kd - timedelta(days=6)
            d_kd_range = sl(dt_scope, kd_chart_a, b_kd)
            if kd_chart_a != a_kd:
                st.caption(f"Biểu đồ hiển thị 7 ngày gần nhất ({kd_chart_a:%d/%m} – {b_kd:%d/%m}).")
            if not d_kd_range.empty:
                # Vẽ theo từng ngày trong khoảng đã lọc. Khoảng ngày do bộ lọc "Chọn nhanh"
                # quyết định nên không cần thêm ô "Gộp theo" nữa.
                plot_kd = d_kd_range.groupby("Ngày", as_index=False)["Giá Trị"].sum()
                fig_kd = px.bar(plot_kd, x="Ngày", y="Giá Trị", title="Doanh thu theo ngày")
                fig_kd.update_traces(marker_color=PRIMARY, marker_line_width=0,
                                     text=point_labels(plot_kd["Giá Trị"], money_label),
                                     textposition="outside", cliponaxis=False,
                                     textfont=dict(color=PRIMARY, **LABEL_FONT),
                                     hovertemplate="%{x|%d/%m/%Y}<br>%{y:,.0f} đ<extra></extra>")
                fig_kd.update_xaxes(tickformat="%d/%m", title_text=None)
                fig_kd.update_yaxes(tickformat=",.0f", title_text="Doanh thu (đ)")
                fig_kd.update_layout(height=380, showlegend=False, margin=dict(t=90, b=70))
                st.plotly_chart(fig_kd, width="stretch")
            else:
                note("Chưa có doanh thu trong khoảng đã chọn.")

        with _sub_tab3[1]:
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
                    top = float(cnt["Số lượng"].max()) or 1.0
                    labels = [f"{st_} · {n:,} ({n / top:.0%})"
                              for st_, n in zip(cnt[status_col], cnt["Số lượng"])]
                    fig_funnel = go.Figure(go.Funnel(
                        y=labels, x=cnt["Số lượng"], textinfo="none",
                        marker=dict(color=[PRIMARY, "#00B4D8", ACCENT, SUCCESS, MUTED]),
                        connector=dict(line=dict(color=LINE, width=1))))
                    fig_funnel.update_yaxes(tickfont=dict(size=15))
                    fig_funnel.update_layout(title="Phễu trạng thái khách hàng", height=380, funnelgap=0.12, margin=dict(l=20, r=20),
                                             showlegend=False,
                                             hovermode="closest")
                    st.plotly_chart(fig_funnel, width="stretch")
                else:
                    note("Chưa đọc được cột Trạng thái trong sheet phễu khách hàng.")
            with fB:
                if not pheu_df.empty and status_col:
                    cnt = (pheu_df.groupby(status_col).size().reset_index(name="Số lượng")
                           .sort_values("Số lượng", ascending=False))
                    st.dataframe(cnt, width="stretch", hide_index=True,
                                 height=min(72 + 54 * len(cnt), 460))
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
                    st.dataframe(tn_show, width="stretch", hide_index=True, height=340)
                    st.download_button("TẢI CSV DANH SÁCH",
                                       tn_show.to_csv(index=False).encode("utf-8-sig"),
                                       "khach_hang_tiem_nang.csv", "text/csv", key="dl_tn", on_click="ignore")
                else:
                    note("Không có dòng nào ở trạng thái 'Khách hàng tiềm năng'.")
            else:
                note("Cần cột Trạng thái trong sheet Khách hàng mới để lọc danh sách tiềm năng.")

        with _sub_tab3[2]:
            ai_advisor(
                "kd", "Kinh doanh",
                f"""Khoảng ngày: {a_kd:%d/%m/%Y} – {b_kd:%d/%m/%Y}. Bưu cục: {bc_kd}.

DOANH THU:
- Hôm qua: {fmt_money(p_kd['n'])} (hôm kia {fmt_money(p_kd['n1'])})
- Tuần này: {fmt_money(p_kd['w'])} (tuần trước {fmt_money(p_kd['w1'])})
- Lũy kế tháng: {fmt_money(p_kd['m'])} (tháng trước {fmt_money(p_kd['m1'])})

TIẾN ĐỘ THÁNG:
- Mục tiêu tháng: {fmt_money(target_dt)}
- Đã qua {days_done}/{days_total} ngày
- Dự phóng cuối tháng: {fmt_money(forecast_dt)}
- Còn thiếu so với mục tiêu: {fmt_money(max(target_dt - forecast_dt, 0))}

KHÁCH HÀNG: {len(pheu_df) if not pheu_df.empty else 0} khách trong phễu.""")


# ═══════════════════════════════════════════════════════════════════════
# TAB 8 — CẢNH BÁO NHÂN SỰ
# ═══════════════════════════════════════════════════════════════════════
if PAGE == "canh_bao_ns":
    with st.container():
        with st.columns([1.1, 2.9])[0]:
            bc_hr = st.selectbox("Bưu cục", ALL_BC, key="bc_hr")
        section("Cảnh báo nhân sự")
        with st.expander("Chỉnh ngưỡng cảnh báo nhân sự"):
            h1, h2, h3, h4, h5 = st.columns(5)
            with h1:
                hr_low = st.number_input("%GTC thấp dưới (%)", 0.0, 100.0, HR_DEFAULTS["low"], 1.0,
                                         key="hr_low")
            with h2:
                hr_streak = st.number_input("…số ngày liền", 2, 14, HR_DEFAULTS["streak"], 1, key="hr_streak")
            with h3:
                hr_drop = st.number_input("%GTC giảm từ (điểm)", 1.0, 50.0, HR_DEFAULTS["drop"], 1.0,
                                          key="hr_drop")
            with h4:
                hr_absent = st.number_input("Vắng từ (ngày)", 1, HR_QUIT_DAYS - 1, HR_DEFAULTS["absent"], 1,
                                            key="hr_absent")
            with h5:
                hr_ratio = st.number_input("Gán dưới (% trung vị BC)", 5, 100, HR_DEFAULTS["ratio"], 5,
                                           key="hr_ratio")
            st.caption("So 7 ngày gần nhất với 7 ngày trước đó. %GTC giảm chỉ xét người có từ 30 đơn gán mỗi bên; "
                       "gán thấp so với trung vị đơn gán/ngày của nhân viên cùng bưu cục (làm từ 2 ngày). "
                       f"Vắng: không có đơn từ số ngày trên. Người không có đơn từ {HR_QUIT_DAYS} ngày trở lên "
                       "coi như đã nghỉ việc nên không hiển thị.")

        hr_day = hr_daily(DF_NSGTC)
        if bc_hr != "Tất cả" and not hr_day.empty:
            hr_day = hr_day[hr_day["Bưu cục"].map(norm) == norm(bc_hr)]
        if hr_day.empty:
            note("Chưa có dữ liệu Năng suất nhân viên cho phạm vi này.")
        else:
            hr_ref = hr_day["Ngày"].max()
            hr_a = hr_ref - timedelta(days=6)
            hr = hr_warnings(hr_day, hr_ref, hr_low, int(hr_streak), hr_drop, int(hr_absent), hr_ratio)
            st.caption(f"Dữ liệu năng suất đến **{hr_ref:%d/%m/%Y}** · 7 ngày gần nhất "
                       f"{hr_a:%d/%m}–{hr_ref:%d/%m/%Y} so với 7 ngày trước đó.")
            n_flag = {k: int(hr["_flags"].map(lambda f, k=k: k in f.split("|")).sum()) if not hr.empty else 0
                      for k in HR_FLAG_COLORS}
            k1, k2, k3, k4 = st.columns(4)
            for col_, k, ttl, sub in (
                    (k1, "low", "%GTC thấp liên tiếp", f"dưới {hr_low:g}% từ {int(hr_streak)} ngày liền"),
                    (k2, "drop", "%GTC giảm mạnh", f"giảm từ {hr_drop:g} điểm so 7 ngày trước"),
                    (k3, "absent", "Vắng / không có đơn",
                     f"{int(hr_absent)}–{HR_QUIT_DAYS - 1} ngày không có đơn"),
                    (k4, "gan", "Sản lượng gán thấp", f"dưới {hr_ratio}% trung vị bưu cục")):
                with col_:
                    st.markdown(metric_card(ttl, f"{n_flag[k]} người", None, sub=sub,
                                            accent=n_flag[k] > 0), unsafe_allow_html=True)
            if hr.empty:
                st.markdown(
                    "<div class='ghn-alert ok'><span class='a-tag tag-ok'>ỔN ĐỊNH</span>"
                    "Không có nhân viên nào chạm ngưỡng cảnh báo.</div>", unsafe_allow_html=True)
            else:
                _sub_tab8 = st.tabs(['Danh sách & trao đổi 1:1', 'Ảnh & gửi thông báo'])
                with _sub_tab8[0]:
                    n_cao = int((hr["Mức"] == "Cao").sum())
                    st.markdown(
                        f"<div class='ghn-alert {'danger' if n_cao else ''}'>"
                        f"<span class='a-tag {'tag-danger' if n_cao else 'tag-warn'}'>"
                        f"{'CẦN XỬ LÝ' if n_cao else 'THEO DÕI'}</span>"
                        f"<b>{len(hr)}</b> nhân viên cần chú ý, trong đó <b>{n_cao}</b> người mức Cao "
                        f"(nhiều cảnh báo cùng lúc hoặc lệch nặng).</div>", unsafe_allow_html=True)
                    st.caption("👆 Bấm vào ô vuông đầu dòng để xem biểu đồ GTC và hướng dẫn trao đổi 1:1 với nhân viên đó.")
                    # Khóa không bắt đầu bằng "hr_": bảng có chọn dòng không cho gán lại giá trị qua session_state.
                    chon = st.dataframe(
                        hr.drop(columns=["_tags", "_flags", "_score", "_ma"]), width="stretch", hide_index=True,
                        on_select="rerun", selection_mode="single-row", key="tbl_hr_staff",
                        column_config={
                            "%GTC 7 ngày": st.column_config.NumberColumn(format="%.2f%%"),
                            "%GTC 7 ngày trước": st.column_config.NumberColumn(format="%.2f%%"),
                            "Gán TB/ngày": st.column_config.NumberColumn(format="%.0f"),
                            "Ngày làm cuối": st.column_config.DateColumn(format="DD/MM/YYYY"),
                            "Cảnh báo": st.column_config.TextColumn(width="large")})
                    dong = [i for i in chon.selection.rows if 0 <= i < len(hr)]
                    if dong:
                        r_nv = hr.iloc[dong[0]]
                        section(f"Chi tiết: {r_nv['Nhân viên']}")
                        fig_nv, d_nv = hr_staff_chart(hr_day, r_nv["_ma"], hr_ref, hr_low)
                        co_lam = d_nv[d_nv["Gán"] > 0]
                        m1, m2, m3, m4 = st.columns(4)
                        p7, p_prev = r_nv["%GTC 7 ngày"], r_nv["%GTC 7 ngày trước"]
                        co_p7, co_prev = p7 is not None and pd.notna(p7), p_prev is not None and pd.notna(p_prev)
                        with m1:
                            st.markdown(metric_card("%GTC 7 ngày", f"{p7:.2f}%" if co_p7 else "—",
                                                    (p7 - p_prev) if co_p7 and co_prev else None, "%", True,
                                                    co_prev, sub="so với 7 ngày trước"), unsafe_allow_html=True)
                        with m2:
                            tong_gan = float(co_lam["Gán"].sum())
                            st.markdown(metric_card("%GTC 30 ngày",
                                                    f"{co_lam['GTC'].sum() / tong_gan * 100:.2f}%" if tong_gan else "—",
                                                    None, sub=f"{int(co_lam['GTC'].sum()):,}/{int(tong_gan):,} đơn"),
                                        unsafe_allow_html=True)
                        with m3:
                            st.markdown(metric_card("Ngày có đơn (30 ngày)", f"{len(co_lam)} ngày", None,
                                                    sub=f"làm gần nhất {pd.Timestamp(r_nv['Ngày làm cuối']):%d/%m}"),
                                        unsafe_allow_html=True)
                        with m4:
                            st.markdown(metric_card("Mức cảnh báo", str(r_nv["Mức"]), None,
                                                    sub=r_nv["_tags"].replace("|", " · "), accent=r_nv["Mức"] == "Cao"),
                                        unsafe_allow_html=True)
                        st.plotly_chart(fig_nv, width="stretch", key="chart_hr_staff")

                        section("Hướng dẫn NVXL trao đổi 1:1")
                        def hr_prompt() -> str:
                            ngay_txt = "\n".join(
                                f"  {x['Ngày']:%d/%m}: {int(x['Gán'])} / {int(x['GTC'])} / {x['r']:.1f}%"
                                if x["Gán"] > 0 else f"  {x['Ngày']:%d/%m}: không có đơn"
                                for _, x in d_nv.tail(14).iterrows())
                            return hr_1on1_prompt(r_nv, hr_low, ngay_txt)

                        one_on_one_panel("hr", r_nv["_ma"], hr_1on1_guide(r_nv, hr_low), hr_prompt,
                                         f"trao_doi_1_1_{r_nv['_ma']}.txt")

                with _sub_tab8[1]:
                    hr_nguong = (f"%GTC dưới {hr_low:g}% từ {int(hr_streak)} ngày liền; giảm từ {hr_drop:g} điểm; "
                                 f"vắng {int(hr_absent)}–{HR_QUIT_DAYS - 1} ngày; gán dưới {hr_ratio}% trung vị bưu cục")

                    def hr_png() -> bytes:
                        """Vẽ ảnh danh sách cảnh báo — chỉ chạy khi bấm tải, xem trước hoặc gửi."""
                        return render_hr_image(
                            hr[["Mức", "Nhân viên", "Bưu cục", "%GTC 7 ngày", "_tags", "_flags"]],
                            "CẢNH BÁO NHÂN SỰ",
                            f"7 ngày {hr_a:%d/%m} – {hr_ref:%d/%m/%Y}  ·  Bưu cục: {bc_hr}",
                            f"{len(hr)} nhân viên cần chú ý ({n_cao} mức Cao)  ·  "
                            f"Dữ liệu năng suất đến {hr_ref:%d/%m/%Y}",
                            "Ngưỡng: " + hr_nguong)

                    hb1, hb2 = st.columns(2, vertical_alignment="bottom")
                    with hb1:
                        st.download_button("TẢI ẢNH CẢNH BÁO NHÂN SỰ", hr_png,
                                           f"canh_bao_nhan_su_{hr_ref:%Y%m%d}.png", "image/png",
                                           key="dl_hr_img", width="stretch", on_click="ignore")
                    with hb2:
                        dang_xem = st.session_state.get("show_hr_preview", False)
                        st.button("ẨN ẢNH XEM TRƯỚC" if dang_xem else "XEM TRƯỚC ẢNH CẢNH BÁO",
                                  key="btn_hr_preview", width="stretch",
                                  on_click=lambda: st.session_state.update(
                                      show_hr_preview=not st.session_state.get("show_hr_preview", False)))
                    if st.session_state.get("show_hr_preview", False):
                        with st.spinner("Đang vẽ ảnh..."):
                            st.image(hr_png(), width="stretch")

                    st.markdown("**Thông báo cảnh báo gửi quản lý bưu cục (Telegram / GTalk)**")
                    st.caption("Danh sách có tên từng nhân viên — nên gửi vào nhóm quản lý / trưởng bưu cục, "
                               "không gửi vào nhóm chung của toàn bộ nhân viên.")
                    st.session_state.setdefault("hr_msg", "")
                    hr_ctx = f"{hr_ref:%Y%m%d}|{bc_hr}|{hr_nguong}|{len(hr)}|{n_cao}"
                    if st.button("AI VIẾT THÔNG BÁO CẢNH BÁO NHÂN SỰ", key="btn_ai_hr_notice", width="stretch"):
                        cao_txt, nhom_txt = hr_notice_data(hr)
                        tg_mo_ta, _ = describe_period(hr_a, hr_ref)
                        with st.spinner("AI đang soạn thông báo..."):
                            ok_ai, ai_text = ask_ai_checked(hr_notice_prompt(
                                tg_mo_ta, f"{hr_ref:%d/%m/%Y}",
                                "toàn bộ các bưu cục" if bc_hr == "Tất cả" else f"bưu cục {bc_hr}",
                                hr_nguong, cao_txt, nhom_txt, len(hr), n_cao))
                        if ok_ai:
                            st.session_state["hr_msg"] = clean_tele_text(ai_text)
                            st.session_state["hr_msg_ctx"] = hr_ctx
                        else:
                            st.error(ai_text)
                    notice_send_panel("hr", hr_ctx, "AI VIẾT THÔNG BÁO CẢNH BÁO NHÂN SỰ", bc_hr, hr_png,
                                      f"canh_bao_nhan_su_{hr_ref:%Y%m%d}.png")


# ═══════════════════════════════════════════════════════════════════════
# TAB 4 — NĂNG SUẤT VÀ LƯƠNG
# ═══════════════════════════════════════════════════════════════════════
if PAGE == "nang_suat":
    with st.container():
        nv_col_luong = pick_col(DF_LUONG, [["nhan vien"]])
        nv_col_gtc = pick_col(DF_NSGTC, [["nhan vien"]])

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

        # ── Kỳ lương GHN ───────────────────────────────────────────────────
        # Dùng chung hàm pay_period() để tên kỳ luôn nhất quán toàn app.
        # Kỳ được gọi theo THÁNG CHI LƯƠNG:
        #   Kỳ 20 tháng M     : dữ liệu 01–15 tháng M,        chi lương 20 tháng M
        #   Kỳ 05 tháng (M+1) : dữ liệu 16–hết tháng M,       chi lương 05 tháng (M+1)
        #
        # Mốc tính lấy theo NGÀY KẾT THÚC của bộ lọc, nên khi đổi bộ lọc ngày thì
        # bảng so sánh bên dưới cũng đổi kỳ theo, không còn cố định theo REF_DATE.
        anchor = b_ns if b_ns is not None else REF_DATE
        cur_a, cur_b, cur_name, prev_a, prev_b, prev_name = pay_period(anchor)

        st.info(
            f"**Kỳ lương đang xét:** {cur_name} — dữ liệu {cur_a:%d/%m/%Y} đến {cur_b:%d/%m/%Y}, "
            f"chi lương ngày {'20' if cur_name.startswith('Kỳ 20') else '05'}.  \n"
            f"**So với kỳ liền trước:** {prev_name} — dữ liệu {prev_a:%d/%m/%Y} đến {prev_b:%d/%m/%Y}.  \n"
            f"Quy ước: Kỳ 20 tháng M gồm dữ liệu ngày 01–15 tháng M, chi lương ngày 20 tháng M. "
            f"Kỳ 05 tháng M+1 gồm dữ liệu ngày 16 đến hết tháng M, chi lương ngày 05 tháng M+1. "
            f"Mốc kỳ chạy theo ngày kết thúc của bộ lọc ({anchor:%d/%m/%Y})."
        )

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

        _sub_tab4 = st.tabs(['Kỳ lương', '%GTC theo kỳ', 'Biểu đồ', 'Xếp hạng & gửi thông báo', 'Nhận định AI'])
        with _sub_tab4[0]:
            section("1. So sánh kỳ lương hiện tại với kỳ trước")
            def ky_row(label, fn, fmt, d_cur, d_prev, suffix, decimals):
                """Một dòng so sánh kỳ. Kỳ nào chưa có dữ liệu thì hiện '—' và không tính chênh lệch
                (trước đây hiện 0 kèm mũi tên đỏ, dễ hiểu nhầm là tụt hẳn về 0)."""
                has_cur = d_cur is not None and not d_cur.empty
                has_prev = d_prev is not None and not d_prev.empty
                v_cur = fn(d_cur) if has_cur else None
                v_prev = fn(d_prev) if has_prev else None
                delta = arrow_span(v_cur - v_prev, suffix, decimals) if has_cur and has_prev else "—"
                return [label, fmt(v_cur) if has_cur else "—", fmt(v_prev) if has_prev else "—", delta]

            rows_ky = [
                # Đơn giá: giữ 3 chữ số thập phân, không làm tròn về số nguyên.
                ky_row("Đơn giá trung bình", avg_price, lambda v: f"{v:,.3f} đ", L_cur, L_prev, " đ", 3),
                # Sản lượng GTC = Đơn GTC + Đơn GTBTT, lấy từ sheet Đơn Giá - Lương.
                ky_row("Sản lượng GTC", sum_gtc, lambda v: f"{v:,.0f} đơn", L_cur, L_prev, " đơn", 0),
                ky_row("%GTC", pct_gtc, lambda v: f"{v:,.2f}%", G_cur, G_prev, " pp", 2),
                ky_row("Tổng lương", total_salary, fmt_money, L_cur, L_prev, " đ", 0),
            ]
            st.markdown(html_table(["Chỉ tiêu", cur_name, prev_name, "Chênh lệch"], rows_ky),
                        unsafe_allow_html=True)
            st.caption("Sản lượng GTC = Đơn GTC + Đơn GTBTT (sheet Đơn Giá - Lương) · "
                       "%GTC lấy từ cột %GTC của sheet Năng suất nhân viên, bình quân có trọng số "
                       "theo sản lượng gán.")
            st.caption("Tổng lương = LHH LTC + LHH GTC + LHH GTBTT · "
                       + " · ".join(f"**{k}**: {v}" for k, v in SALARY_PARTS.items()))

        with _sub_tab4[1]:
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

        with _sub_tab4[2]:
            section("3. Biểu đồ sản lượng gán, sản lượng GTC và %GTC")
            if col_gan and col_gtc and not G_range.empty:
                g_ns = G_range.groupby("Ngày", as_index=False).agg({col_gan: "sum", col_gtc: "sum"})
                g_ns["r"] = np.where(g_ns[col_gan] > 0, g_ns[col_gtc] / g_ns[col_gan] * 100, 0.0)
                fig_ns = make_subplots(specs=[[{"secondary_y": True}]])
                ns_angle = -90 if len(g_ns) > 10 else 0
                fig_ns.add_trace(go.Bar(x=g_ns["Ngày"], y=g_ns[col_gan], name="Sản lượng gán",
                                        marker_color=PRIMARY_SOFT, marker_line_width=0,
                                        hoverinfo="x+y+name", text=point_labels(g_ns[col_gan], num_label), textposition="outside",
                                        textangle=ns_angle, cliponaxis=False,
                                        textfont=dict(color=PRIMARY, **LABEL_FONT)), secondary_y=False)
                fig_ns.add_trace(go.Bar(x=g_ns["Ngày"], y=g_ns[col_gtc], name="Sản lượng GTC",
                                        marker_color=PRIMARY, marker_line_width=0,
                                        hoverinfo="x+y+name", text=point_labels(g_ns[col_gtc], num_label), textposition="inside",
                                        insidetextanchor="end", textangle=ns_angle,
                                        textfont=dict(color="#FFFFFF", **LABEL_FONT)), secondary_y=False)
                fig_ns.add_trace(go.Scatter(x=g_ns["Ngày"], y=g_ns["r"], name="% GTC",
                                            mode="lines+markers+text", line=dict(color=ACCENT, width=3),
                                            marker=dict(size=7),
                                            hoverinfo="x+y+name", text=point_labels(g_ns["r"], pct_label), textposition="top center",
                                            cliponaxis=False, textfont=dict(color=ACCENT, **LABEL_FONT)),
                                 secondary_y=True)
                fig_ns.update_layout(barmode="overlay", height=470,
                                     title="Sản lượng gán · GTC · tỷ lệ")
                fig_ns.update_yaxes(title_text="Số đơn", secondary_y=False)
                fig_ns.update_yaxes(title_text="% GTC", secondary_y=True, ticksuffix="%", showgrid=False)
                band_axes(fig_ns, g_ns[col_gan].max())
                fig_ns.update_xaxes(tickformat="%d/%m")
                st.plotly_chart(fig_ns, width="stretch")
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
                                            marker=dict(size=7, color=PRIMARY),
                                            mode="lines+markers+text", cliponaxis=False,
                                            text=point_labels(g_price[col_price], lambda v: f"{v:,.0f}"),
                                            textposition="top center",
                                            textfont=dict(color=PRIMARY, **LABEL_FONT))
                    fig_price.update_yaxes(title_text="VNĐ")
                    fig_price.update_xaxes(tickformat="%d/%m")
                    fig_price.update_layout(height=330, showlegend=False, margin=dict(t=90, b=70))
                    st.plotly_chart(fig_price, width="stretch")
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
                                          marker=dict(size=7, color=SUCCESS),
                                          mode="lines+markers+text", cliponaxis=False,
                                          text=point_labels(g_pay["Tổng Lương"], money_label),
                                          textposition="top center",
                                          textfont=dict(color=SUCCESS, **LABEL_FONT))
                    fig_pay.update_yaxes(title_text="VNĐ")
                    fig_pay.update_xaxes(tickformat="%d/%m")
                    fig_pay.update_layout(height=330, showlegend=False, margin=dict(t=90, b=70))
                    st.plotly_chart(fig_pay, width="stretch")
                else:
                    note("Chưa đọc được các cột LHH LTC, LHH GTC, LHH GTBTT.")

        with _sub_tab4[3]:
            if col_gan and col_gtc and nv_col_gtc and not G_range.empty:
                section("5. Xếp hạng nhân viên theo %GTC")
                rank = G_range.groupby(nv_col_gtc, as_index=False).agg({col_gan: "sum", col_gtc: "sum"})
                rank["%GTC"] = np.where(rank[col_gan] > 0, rank[col_gtc] / rank[col_gan] * 100, 0.0)
                rank = rank.sort_values("%GTC", ascending=False).reset_index(drop=True)
                medals = ["🥇", "🥈", "🥉"]
                rank.insert(0, "Hạng", [f"{medals[i]} {i+1}" if i < 3 else str(i + 1)
                                        for i in range(len(rank))])
                rank["Mục tiêu (≥80%)"] = np.where(rank["%GTC"] >= 80, "Đạt", "Chưa")
                st.dataframe(rank, width="stretch", hide_index=True,
                             column_config={
                                 col_gan: st.column_config.NumberColumn("Đơn gán", format="%,d"),
                                 col_gtc: st.column_config.NumberColumn("Đơn GTC", format="%,d"),
                                 "%GTC": st.column_config.ProgressColumn("%GTC", format="%.2f%%",
                                                                         min_value=0, max_value=100)})
                bt1, bt2, bt3 = st.columns([1.3, 1, 1], vertical_alignment="bottom")
                with bt1:
                    n_pick = st.selectbox("Số nhân viên trong ảnh",
                                          ["Tất cả", "Top 10", "Top 20", "Top 50"], key="rank_img_n")
                top_n = {"Top 10": 10, "Top 20": 20, "Top 50": 50}.get(n_pick, len(rank))
                img_rows = pd.DataFrame({
                    "Hạng": range(1, len(rank) + 1),
                    "Nhân viên": rank[nv_col_gtc].astype(str),
                    "Đơn gán": pd.to_numeric(rank[col_gan], errors="coerce").fillna(0),
                    "Đơn GTC": pd.to_numeric(rank[col_gtc], errors="coerce").fillna(0),
                    "%GTC": rank["%GTC"],
                }).head(top_n)
                def png() -> bytes:
                    """Vẽ ảnh bảng xếp hạng — chỉ chạy khi cần (bấm tải, xem trước hoặc gửi), không vẽ mỗi lần mở tab."""
                    return render_rank_image(
                        img_rows, "BẢNG XẾP HẠNG NHÂN VIÊN THEO %GTC",
                        f"{a_ns:%d/%m/%Y} – {b_ns:%d/%m/%Y}  ·  Bưu cục: {bc_ns}",
                        f"Mục tiêu: %GTC ≥ 80%  ·  {len(img_rows)}/{len(rank)} nhân viên  ·  "
                        f"Dữ liệu đến {REF_DATE:%d/%m/%Y}")
                with bt2:
                    st.download_button("TẢI ẢNH BẢNG XẾP HẠNG", png,
                                       f"xep_hang_gtc_{b_ns:%Y%m%d}.png", "image/png",
                                       key="dl_rank_img", width="stretch", on_click="ignore")
                with bt3:
                    dang_xem = st.session_state.get("show_rank_preview", False)
                    st.button("ẨN ẢNH XEM TRƯỚC" if dang_xem else "XEM TRƯỚC ẢNH BẢNG XẾP HẠNG",
                              key="btn_rank_preview", width="stretch",
                              on_click=lambda: st.session_state.update(
                                  show_rank_preview=not st.session_state.get("show_rank_preview", False)))
                if st.session_state.get("show_rank_preview", False):
                    with st.spinner("Đang vẽ ảnh..."):
                        st.image(png(), width="stretch")

                # ── AI soạn thông báo + gửi ảnh qua Telegram ───────────────────────
                st.markdown("**Thông báo xếp hạng gửi nhân viên (Telegram / GTalk)**")
                st.session_state.setdefault("rank_msg", "")
                ky_txt = f"{a_ns:%d/%m/%Y} – {b_ns:%d/%m/%Y}"
                ctx_sig = f"{ky_txt}|{bc_ns}|{nv_ns}|{len(rank)}"
                n_dat_rank = int((rank["%GTC"] >= 80).sum())

                tn1, tn2 = st.columns([1.3, 2], vertical_alignment="bottom")
                with tn1:
                    tone = st.selectbox("Giọng văn thông báo", list(RANK_TONES), key="rank_tone")
                with tn2:
                    viet = st.button("AI VIẾT THÔNG BÁO XẾP HẠNG", key="btn_ai_rank_notice", width="stretch")
                if viet:
                    top_txt = "\n".join(
                        f"  {i}. {staff_label(r[nv_col_gtc])} — %GTC {r['%GTC']:.2f}% "
                        f"({int(r[col_gtc]):,} GTC / {int(r[col_gan]):,} gán)"
                        for i, (_, r) in enumerate(rank.head(3).iterrows(), start=1))
                    with st.spinner("AI đang soạn thông báo..."):
                        tg_mo_ta, tg_tiep = describe_period(a_ns, b_ns)
                        ok_ai, ai_text = ask_ai_checked(rank_notice_prompt(
                            tone, tg_mo_ta, tg_tiep, "toàn bộ các bưu cục" if bc_ns == "Tất cả" else f"bưu cục {bc_ns}",
                            top_txt, len(rank), n_dat_rank))
                    if ok_ai:
                        st.session_state["rank_msg"] = clean_tele_text(ai_text)
                        st.session_state["rank_msg_ctx"] = ctx_sig
                    else:
                        st.error(ai_text)

                notice_send_panel("rank", ctx_sig, "AI VIẾT THÔNG BÁO XẾP HẠNG", bc_ns, png,
                                  f"xep_hang_gtc_{b_ns:%Y%m%d}.png")

        with _sub_tab4[4]:
            ai_advisor(
                "ns", "Năng suất & Lương",
                f"""Bưu cục: {bc_ns}. Nhân viên: {nv_ns}.
Kỳ đang xét: {cur_name} (dữ liệu {cur_a:%d/%m/%Y} – {cur_b:%d/%m/%Y}).
Kỳ liền trước: {prev_name} (dữ liệu {prev_a:%d/%m/%Y} – {prev_b:%d/%m/%Y}).

SO SÁNH HAI KỲ:
- Đơn giá trung bình: {avg_price(L_cur):,.3f} đ / kỳ trước {avg_price(L_prev):,.3f} đ
- Sản lượng GTC (Đơn GTC + Đơn GTBTT): {sum_gtc(L_cur):,.0f} đơn / kỳ trước {sum_gtc(L_prev):,.0f} đơn
- %GTC: {pct_gtc(G_cur):.2f}% / kỳ trước {pct_gtc(G_prev):.2f}%
- Tổng lương: {fmt_money(total_salary(L_cur))} / kỳ trước {fmt_money(total_salary(L_prev))}

Mốc thưởng %GTC là 80%.""",
            extra_note="Lưu ý: đơn giá giảm mà sản lượng tăng thường là dấu hiệu cơ cấu đơn đổi "
                       "sang loại đơn giá thấp, cần soi kỹ trước khi kết luận nhân viên làm kém.")


# ═══════════════════════════════════════════════════════════════════════
# TAB 5 — TIẾN ĐỘ HOÀN THÀNH KPI
# ═══════════════════════════════════════════════════════════════════════
if PAGE == "kpi":
    with st.container():
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
        t_odr = kpi_target([["odr"]], 98.0, bc=bc_kpi)
        t_opr = kpi_target([["opr"]], 100.0, bc=bc_kpi)

        if DF_KPI.empty or DF_KPI.select_dtypes("number").notna().sum().sum() == 0:
            st.warning("Sheet KPI chưa có số liệu. Đang dùng mốc tạm — bạn chỉnh ở dưới, "
                       "hoặc điền vào sheet KPI là dashboard tự nhận.", icon="⚠️")

        with st.expander("Chỉnh mốc KPI thủ công"):
            x1, x2, x3, x4, x5 = st.columns(5)
            with x1:
                t_gtc = st.number_input("%GTC tổng tối thiểu", 0.0, 100.0, float(t_gtc), 0.5,
                                        key=f"kpi_gtc_{bc_kpi}")
            with x2:
                t_tts = st.number_input("%GTC TTS tối thiểu", 0.0, 100.0, float(t_tts), 0.5,
                                        key=f"kpi_tts_{bc_kpi}")
            with x3:
                t_tra = st.number_input("%Trả hàng tối đa", 0.0, 100.0, float(t_tra), 0.5,
                                        key=f"kpi_tra_{bc_kpi}")
            with x4:
                t_odr = st.number_input("ODR TTS tối thiểu", 0.0, 100.0, float(t_odr), 0.5,
                                        key=f"kpi_odr_{bc_kpi}")
            with x5:
                t_opr = st.number_input("OPR TTS tối thiểu", 0.0, 100.0, float(t_opr), 0.5,
                                        key=f"kpi_opr_{bc_kpi}")

        a_gtc = agg(scope(M_GTC, bc_kpi), a_kpi, b_kpi)
        a_tts = agg(scope(M_TTS, bc_kpi), a_kpi, b_kpi)
        a_tra = agg(scope(M_TRA, bc_kpi), a_kpi, b_kpi)
        a_odr = agg(scope(M_ODR, bc_kpi), a_kpi, b_kpi)
        a_opr = agg(scope(M_OPR, bc_kpi), a_kpi, b_kpi)

        _sub_tab5 = st.tabs(['Đồng hồ KPI', 'Đối chiếu chi tiết', 'Bám mốc theo ngày', 'Nhận định AI'])
        with _sub_tab5[0]:
            section("Đồng hồ đo tiến độ KPI")
            gc1, gc2, gc3 = st.columns(3)
            with gc1:
                gauge_chart("%GTC Tổng", a_gtc, t_gtc, True)
            with gc2:
                gauge_chart("%GTC TikTok Shop", a_tts, t_tts, True)
            with gc3:
                gauge_chart("%Trả hàng (thấp là tốt)", a_tra, t_tra, False)
            gc4, gc5, _ = st.columns(3)
            with gc4:
                gauge_chart("ODR TikTok Shop", a_odr, t_odr, True)
            with gc5:
                gauge_chart("OPR TikTok Shop", a_opr, t_opr, True)

        with _sub_tab5[1]:
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
                 kpi_row("%Trả hàng", a_tra, t_tra, False),
                 kpi_row("ODR TikTok Shop", a_odr, t_odr, True),
                 kpi_row("OPR TikTok Shop", a_opr, t_opr, True)]), unsafe_allow_html=True)

        with _sub_tab5[2]:
            section("Bám mốc theo ngày")
            kpi_series = []
            for frame, name, color, tgt in ((M_GTC, "%GTC Tổng", PRIMARY, t_gtc),
                                            (M_TTS, "%GTC TTS", SUCCESS, t_tts),
                                            (M_TRA, "%Trả hàng", DANGER, t_tra),
                                            (M_ODR, "ODR TTS", ACCENT, t_odr),
                                            (M_OPR, "OPR TTS", "#00B4D8", t_opr)):
                g = daily(sl(scope(frame, bc_kpi), a_kpi, b_kpi))
                if not g.empty:
                    kpi_series.append((g, name, color, tgt))
            if kpi_series:
                fig_kpi = go.Figure()
                pos_kpi = label_layout([g["Giá Trị"] for g, _, _, _ in kpi_series])
                for (g, name, color, tgt), (tpos, off) in zip(kpi_series, pos_kpi):
                    fig_kpi.add_trace(go.Scatter(x=g["Ngày"], y=g["Giá Trị"], name=name,
                                                 mode="lines+markers+text",
                                                 line=dict(color=color, width=3), marker=dict(size=6),
                                                 hoverinfo="x+y+name",
                                                 text=point_labels(g["Giá Trị"], pct_label, 10, off),
                                                 textposition=tpos, cliponaxis=False,
                                                 textfont=dict(color=color, **LABEL_FONT)))
                    fig_kpi.add_hline(y=tgt, line_dash="dot", line_color=color, line_width=1.5, opacity=0.5)
                fig_kpi.update_yaxes(ticksuffix="%")
                fig_kpi.update_xaxes(tickformat="%d/%m")
                fig_kpi.update_layout(height=470)
                st.plotly_chart(fig_kpi, width="stretch")

                tbl_kpi = daily(sl(scope(M_GTC, bc_kpi), a_kpi, b_kpi)).rename(
                    columns={"Giá Trị": "%GTC", "Trọng Số": "Sản lượng"})
                for frame, nm in ((M_TTS, "%GTC TTS"), (M_TRA, "%Trả hàng"), (M_ODR, "ODR TTS"),
                                  (M_OPR, "OPR TTS")):
                    d = daily(sl(scope(frame, bc_kpi), a_kpi, b_kpi))[["Ngày", "Giá Trị"]].rename(
                        columns={"Giá Trị": nm})
                    tbl_kpi = tbl_kpi.merge(d, on="Ngày", how="outer")
                tbl_kpi = tbl_kpi.sort_values("Ngày", ascending=False)
                tbl_kpi["Đạt mốc GTC"] = np.where(tbl_kpi["%GTC"] >= t_gtc, "Đạt", "Chưa")
                st.dataframe(tbl_kpi, width="stretch", hide_index=True, height=320,
                             column_config={
                                 "Ngày": st.column_config.DateColumn(format="DD/MM/YYYY"),
                                 "Sản lượng": st.column_config.NumberColumn(format="%,d"),
                                 "%GTC": st.column_config.ProgressColumn(format="%.2f%%",
                                                                         min_value=0, max_value=100),
                                 "%GTC TTS": st.column_config.NumberColumn(format="%.2f%%"),
                                 "%Trả hàng": st.column_config.NumberColumn(format="%.2f%%"),
                                 "ODR TTS": st.column_config.NumberColumn(format="%.2f%%"),
                                 "OPR TTS": st.column_config.NumberColumn(format="%.2f%%")})
                st.download_button("TẢI CSV", tbl_kpi.to_csv(index=False).encode("utf-8-sig"),
                                   "kpi_theo_ngay.csv", "text/csv", key="dl_kpi", on_click="ignore")
            else:
                note("Chưa có dữ liệu KPI trong khoảng đã chọn.")

        with _sub_tab5[3]:
            ai_advisor(
                "kpi", "Tiến độ KPI",
                f"""Khoảng ngày: {a_kpi:%d/%m/%Y} – {b_kpi:%d/%m/%Y}. Bưu cục: {bc_kpi}.

ĐỐI CHIẾU VỚI MỐC KPI:
- %GTC tổng: thực tế {a_gtc:.2f}% / mốc tối thiểu {t_gtc:.2f}% -> {'ĐẠT' if a_gtc >= t_gtc else 'CHƯA ĐẠT'}
- %GTC TikTok: thực tế {a_tts:.2f}% / mốc tối thiểu {t_tts:.2f}% -> {'ĐẠT' if a_tts >= t_tts else 'CHƯA ĐẠT'}
- %Trả hàng: thực tế {a_tra:.2f}% / ngưỡng tối đa {t_tra:.2f}% -> {'ĐẠT' if a_tra <= t_tra else 'CHƯA ĐẠT'}
- ODR TikTok: thực tế {a_odr:.2f}% / mốc tối thiểu {t_odr:.2f}% -> {'ĐẠT' if a_odr >= t_odr else 'CHƯA ĐẠT'}
- OPR TikTok: thực tế {a_opr:.2f}% / mốc tối thiểu {t_opr:.2f}% -> {'ĐẠT' if a_opr >= t_opr else 'CHƯA ĐẠT'}

Đã qua {(b_kpi - a_kpi).days + 1} ngày trong kỳ theo dõi.""",
            extra_note="Hãy ước lượng khả năng về đích của từng chỉ số nếu giữ nguyên tốc độ hiện tại, "
                       "và nói rõ cần kéo thêm bao nhiêu điểm phần trăm.")


# ═══════════════════════════════════════════════════════════════════════
# TAB 7 — THI ĐUA GIAO THÀNH CÔNG THÁNG
# ═══════════════════════════════════════════════════════════════════════
if PAGE == "thi_dua":
    with st.container():
        # Dùng div thay cho h2: quy tắc chung "h1,h2,h3,h4 { color: xanh đậm !important }"
        # sẽ đè lên màu trắng, khiến chữ xanh đậm chìm nghỉm trên nền xanh.
        st.markdown(f"""
    <div class="ghn-hero" style="background:linear-gradient(120deg,{PRIMARY} 0%,#00B4D8 100%);
                border-radius:10px;padding:20px 26px;margin-bottom:18px;
                box-shadow:0 3px 10px rgba(0,119,182,0.25);">
        <div class="ghn-hero-title">
            Bảng xếp hạng thi đua giao thành công {esc(st.session_state.get('td_mode', 'Tháng')).lower()}
        </div>
    </div>""", unsafe_allow_html=True)

        r1, r2, r3 = st.columns([1.2, 1, 1.4])
        with r1:
            bc_td = st.selectbox("Bưu cục", ALL_BC, key="bc_td")
        with r2:
            td_mode = st.radio("Thi đua theo", ["Tháng", "Tuần"], horizontal=True, key="td_mode")
        theo_thang = td_mode == "Tháng"

        # ── Gom dữ liệu theo nhân viên cho từng tháng ──────────────────────
        # ── Chuẩn hóa từng nguồn về một khung chung ────────────────────────
        def chuan_hoa(df: pd.DataFrame, ten_nguon: str) -> tuple[pd.DataFrame, dict]:
            """Đưa một sheet năng suất về khung: MaNV | Nhân Viên | Bưu Cục | Kỳ | Gán | GTC.

        Trả kèm nhật ký chẩn đoán để biết chính xác vì sao một nguồn không ra số,
        thay vì âm thầm hiện 0.
        """
            cols = ["MaNV", "Nhân Viên", "Bưu Cục", "Ngày", "Gán", "GTC"]
            log = {"Nguồn": ten_nguon, "Số dòng đọc được": 0, "Cột nhân viên": "—",
                   "Cột gán": "—", "Cột GTC": "—", "Khoảng ngày": "—",
                   "Số nhân viên": 0, "Tình trạng": ""}

            if df is None or df.empty:
                log["Tình trạng"] = "Không đọc được sheet hoặc sheet rỗng"
                return pd.DataFrame(columns=cols), log

            log["Số dòng đọc được"] = len(df)
            nv_c = pick_col(df, [["nhan vien"]])
            gan_c = pick_col(df, [["san luong gan"], ["gan giao"], ["so don gan"], ["gan"]])
            gtc_c = pick_col(df, [["san luong gtc"], ["don gtc"], ["giao thanh cong"], ["gtc"]],
                             exclude=["%"])
            log["Cột nhân viên"] = nv_c or "KHÔNG TÌM THẤY"
            log["Cột gán"] = gan_c or "KHÔNG TÌM THẤY"
            log["Cột GTC"] = gtc_c or "KHÔNG TÌM THẤY"

            if not (nv_c and gan_c and gtc_c):
                log["Tình trạng"] = "Thiếu cột bắt buộc"
                return pd.DataFrame(columns=cols), log

            d = df.copy()
            if "Ngày" in d.columns and d["Ngày"].notna().any():
                log["Khoảng ngày"] = f"{d['Ngày'].min():%d/%m/%Y} – {d['Ngày'].max():%d/%m/%Y}"
            else:
                log["Tình trạng"] = "Không đọc được cột ngày nên không xác định được tháng"
                return pd.DataFrame(columns=cols), log

            out = pd.DataFrame({
                "MaNV": d[nv_c].map(staff_id),
                "Nhân Viên": d[nv_c].astype(str).str.strip(),
                "Bưu Cục": d["Bưu Cục"] if "Bưu Cục" in d.columns else "Chưa phân loại",
                "Ngày": d["Ngày"],
                "Gán": pd.to_numeric(_as_series(d[gan_c]), errors="coerce").fillna(0),
                "GTC": pd.to_numeric(_as_series(d[gtc_c]), errors="coerce").fillna(0),
            }).dropna(subset=["Ngày"])

            log["Số nhân viên"] = out["MaNV"].nunique()
            log["Tình trạng"] = "Bình thường" if not out.empty else "Không còn dòng nào sau xử lý"
            return out, log

        raw_now, log_now = chuan_hoa(DF_NSGTC, "Năng suất nhân viên (tháng này)")
        raw_prev, log_prev = chuan_hoa(DF_NS_PREV, "Năng suất tháng trước")

        def nguon_loi_td() -> str:
            """Lý do ngắn gọn của nguồn nào đang không đọc được (thay cho bảng chẩn đoán đã bỏ)."""
            ly_do = [f"{lg['Nguồn']}: {lg['Tình trạng']}" for lg in (log_now, log_prev)
                     if lg["Tình trạng"] != "Bình thường"]
            return ("Nguyên nhân: " + "; ".join(ly_do) + ".") if ly_do else ""

        # Gộp CẢ HAI nguồn rồi mới tách theo tháng. Nhờ vậy nếu một sheet chứa sẵn dữ liệu
        # của cả hai tháng, hoặc một sheet hỏng, phần còn lại vẫn dùng được.
        # Ngày nào của một nhân viên đã có ở sheet tháng này thì bỏ dòng trùng ở sheet tháng trước.
        # (Trước đây khử trùng theo tháng + số đơn, nên hai NGÀY khác nhau có cùng số gán/GTC
        # bị coi là trùng và mất một ngày.)
        if not raw_now.empty and not raw_prev.empty:
            da_co = pd.MultiIndex.from_frame(raw_now[["MaNV", "Ngày"]])
            raw_prev = raw_prev[~pd.MultiIndex.from_frame(raw_prev[["MaNV", "Ngày"]]).isin(da_co)]
        kho = pd.concat([raw_now, raw_prev], ignore_index=True)
        kho["Kỳ"] = (kho["Ngày"].dt.to_period("M" if theo_thang else "W-SUN")
                     if not kho.empty else pd.Series(dtype="object"))

        def ten_ky(k) -> str:
            """'Tháng 09/2026' hoặc 'Tuần 22/09–28/09/2026' (tuần tính từ thứ Hai đến Chủ nhật)."""
            if theo_thang:
                return f"Tháng {k.month:02d}/{k.year}"
            return f"Tuần {k.start_time:%d/%m}–{k.end_time:%d/%m/%Y}"

        co_du_lieu_goc = not kho.empty
        if bc_td != "Tất cả" and not kho.empty:
            kho = kho[kho["Bưu Cục"].map(norm) == norm(bc_td)]
        chi_thieu_buu_cuc = co_du_lieu_goc and kho.empty

        if chi_thieu_buu_cuc:
            note(f"Bưu cục {bc_td} không có nhân viên nào trong dữ liệu năng suất. "
                 "Chọn bưu cục khác hoặc 'Tất cả'.")
        elif kho.empty:
            note("Chưa gộp được dữ liệu thi đua. " + nguon_loi_td())
        else:
            # Không dùng st.stop(): lệnh đó dừng CẢ TRANG (mất chân trang, các phần sau),
            # chứ không chỉ riêng tab này.
            ky_list = sorted(kho["Kỳ"].dropna().unique(), reverse=True)
            with r3:
                ky_now = st.selectbox("Kỳ thi đua", ky_list, format_func=ten_ky,
                                      key=f"td_ky_{td_mode}")
            ky_prev = ky_now - 1
            ngay_cuoi = kho["Ngày"].max()
            if not theo_thang and ky_now.end_time.normalize() > ngay_cuoi:
                st.caption(f"{ten_ky(ky_now)} chưa kết thúc — dữ liệu mới đến {ngay_cuoi:%d/%m/%Y}.")

            def gom_ky(ky) -> pd.DataFrame:
                """Gộp theo nhân viên trong một kỳ (tuần hoặc tháng).
        %GTC kỳ = tổng GTC / tổng gán, không lấy trung bình cộng %GTC từng ngày."""
                d = kho[kho["Kỳ"] == ky]
                if d.empty:
                    return pd.DataFrame(columns=["MaNV", "Nhân Viên", "Bưu Cục", "Gán", "GTC", "%GTC"])
                g = d.groupby("MaNV", as_index=False).agg(
                    **{"Nhân Viên": ("Nhân Viên", lambda x: max(x.astype(str), key=len)),
                       "Bưu Cục": ("Bưu Cục", "first"),
                       "Gán": ("Gán", "sum"),
                       "GTC": ("GTC", "sum")})
                g["%GTC"] = np.where(g["Gán"] > 0, g["GTC"] / g["Gán"] * 100, 0.0)
                return g

            cur_td = gom_ky(ky_now)
            prev_td = gom_ky(ky_prev)
            ten_n, ten_n1 = ten_ky(ky_now), ten_ky(ky_prev)
            ten_n_th, ten_n1_th = ten_n[0].lower() + ten_n[1:], ten_n1[0].lower() + ten_n1[1:]
            ky_slug = (f"thang_{ky_now.year}_{ky_now.month:02d}" if theo_thang
                       else f"tuan_{ky_now.start_time:%Y%m%d}")

            if prev_td.empty:
                st.warning(
                    f"Không có dữ liệu **{ten_n1_th}** trong cả hai sheet, nên cột %GTC kỳ trước "
                    f"đang bằng 0 và mức cải thiện bị thổi phồng đúng bằng %GTC {ten_n_th}. "
                    + nguon_loi_td(), icon="⚠️")
            else:
                khop = cur_td["MaNV"].isin(prev_td["MaNV"]).sum()
                st.caption(f"Đối chiếu {ten_n_th} với {ten_n1_th} · "
                           f"{len(cur_td)} nhân viên kỳ này, {len(prev_td)} nhân viên kỳ trước, "
                           f"{khop} người khớp mã ở cả hai kỳ.")

            if cur_td.empty:
                note("Chưa đọc được dữ liệu năng suất kỳ này. " + nguon_loi_td())
            else:
                # ── Ghép hai tháng theo MÃ nhân viên ───────────────────────────
                bxh = cur_td.merge(
                    prev_td[["MaNV", "%GTC"]].rename(columns={"%GTC": f"%GTC {ten_n1}"}),
                    on="MaNV", how="left")
                col_now = f"%GTC {ten_n}"
                col_prev = f"%GTC {ten_n1}"
                bxh = bxh.rename(columns={"%GTC": col_now})
                bxh[col_prev] = bxh[col_prev].fillna(0.0)
                bxh["Tỷ Lệ Cải Thiện"] = bxh[col_now] - bxh[col_prev]

                # ── Ba tiêu chí xếp hạng, hạng nhỏ là tốt ──────────────────────
                bxh["Xếp Hạng Gán"] = bxh["Gán"].rank(ascending=False, method="min").astype(int)
                bxh["Xếp Hạng %GTC"] = bxh[col_now].rank(ascending=False, method="min").astype(int)
                bxh["Xếp Hạng Cải Thiện"] = bxh["Tỷ Lệ Cải Thiện"].rank(ascending=False,
                                                                        method="min").astype(int)
                bxh["Tổng Điểm"] = (bxh["Xếp Hạng Gán"] + bxh["Xếp Hạng %GTC"]
                                    + bxh["Xếp Hạng Cải Thiện"]) / 3

                # Tổng điểm càng NHỎ càng tốt. Hoà điểm thì ai %GTC cao hơn xếp trước.
                bxh = bxh.sort_values(["Tổng Điểm", col_now], ascending=[True, False]).reset_index(drop=True)
                bxh["Xếp Hạng Tổng"] = np.arange(1, len(bxh) + 1)

                # ── Điều kiện thưởng: %GTC tháng N từ 80% trở lên ──────────────
                # Giải thưởng trao cho 3 người ĐỦ ĐIỀU KIỆN xếp cao nhất, không phải 3 hạng
                # đầu bảng. Nếu hạng 1 không đạt mốc 80% thì suất thưởng chuyển xuống người
                # đủ điều kiện kế tiếp.
                bxh["Đủ ĐK (≥80%)"] = np.where(bxh[col_now] >= 80, "Đạt", "Chưa")
                THUONG = {1: 1_000_000, 2: 500_000, 3: 300_000}

                def thuong_txt(h) -> str:
                    """Thưởng tiền là cơ cấu HÀNG THÁNG; xếp theo tuần thì chỉ vinh danh."""
                    return fmt_money(THUONG[int(h)]) if theo_thang else f"Vinh danh hạng {int(h)}"

                du_dk = bxh[bxh[col_now] >= 80].sort_values("Xếp Hạng Tổng")
                ma_thuong = {ma: pos for pos, ma in enumerate(du_dk["MaNV"].head(3), start=1)}

                bxh["Hạng Thưởng"] = bxh["MaNV"].map(ma_thuong)
                bxh["Thưởng"] = [
                    thuong_txt(h) if pd.notna(h) else
                    ("Không đủ ĐK" if r <= 3 else "—")
                    for h, r in zip(bxh["Hạng Thưởng"], bxh["Xếp Hạng Tổng"])
                ]

                _sub_tab7 = st.tabs(['Vinh danh top 3', 'Bảng xếp hạng', 'Mức cải thiện', 'Thể lệ', 'Nhận định AI'])
                with _sub_tab7[0]:
                    # ── Bục vinh danh ──────────────────────────────────────────────
                    section("Vinh danh top 3")
                    top3 = bxh[bxh["Hạng Thưởng"].notna()].sort_values("Hạng Thưởng")
                    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
                    pcols = st.columns(3)
                    if top3.empty:
                        with pcols[0]:
                            st.markdown(f"""
                    <div class="metric-card" style="border-left-color:{DANGER};text-align:center;">
                        <div class="m-title">Chưa có ai đủ điều kiện</div>
                        <div class="m-value" style="color:{DANGER};">0</div>
                        <div class="m-delta down">Không ai đạt mốc %GTC 80% {ten_n_th}</div>
                    </div>""", unsafe_allow_html=True)
                    for i, (_, row) in enumerate(top3.iterrows()):
                        with pcols[i]:
                            hang_thuong = int(row["Hạng Thưởng"])
                            hang_tong = int(row["Xếp Hạng Tổng"])
                            # Nếu hạng thưởng khác hạng tổng thì nói rõ, tránh người xem thắc mắc
                            # vì sao người xếp hạng 4 lại lên bục.
                            ghi_chu = (f"hạng tổng {hang_tong}" if hang_thuong != hang_tong
                                       else "dẫn đầu bảng xếp hạng")
                            st.markdown(f"""
                    <div class="metric-card" style="border-left-color:{SUCCESS};text-align:center;">
                        <div style="font-size:calc(35.75px * var(--fs));line-height:1;">{medals[hang_thuong]}</div>
                        <div class="m-title" style="margin-top:6px;">{esc(staff_label(row['Nhân Viên']))}</div>
                        <div class="m-value">{row[col_now]:.2f}%</div>
                        <div class="m-delta up">{thuong_txt(hang_thuong)}</div>
                        <div style="font-size:calc(14px * var(--fs));color:{MUTED};margin-top:4px;">
                            {row['Gán']:,.0f} đơn gán · {row['GTC']:,.0f} đơn GTC · {ghi_chu}
                        </div>
                    </div>""", unsafe_allow_html=True)

                    n_dat = int((bxh[col_now] >= 80).sum())
                    m1, m2, m3 = st.columns(3)
                    with m1:
                        st.markdown(metric_card("Số nhân viên dự thi", f"{len(bxh):,}", None,
                                                sub=ten_n_th), unsafe_allow_html=True)
                    with m2:
                        st.markdown(metric_card("Đạt điều kiện ≥80%", f"{n_dat:,}", None,
                                                sub=f"trên tổng {len(bxh)} người",
                                                accent=True), unsafe_allow_html=True)
                    with m3:
                        # Tổng thưởng = cộng đúng các suất đã trao (theo Hạng Thưởng), không
                        # cộng theo hạng tổng vì hạng tổng có thể rơi vào người chưa đủ điều kiện.
                        tong_thuong = (sum(THUONG[int(h)] for h in bxh["Hạng Thưởng"].dropna())
                                       if theo_thang else 0)
                        st.markdown(metric_card("Tổng tiền thưởng phải chi",
                                                fmt_money(tong_thuong) if theo_thang else "—", None,
                                                sub="theo kết quả hiện tại" if theo_thang
                                                else "thưởng tiền chỉ tính theo tháng"),
                                    unsafe_allow_html=True)

                    pham_vi = f"Bưu cục: {bc_td}"
                    if not top3.empty:
                        podium_cards = [
                            dict(rank=int(r["Hạng Thưởng"]), name=staff_label(r["Nhân Viên"]),
                                 pct=float(r[col_now]), prize=thuong_txt(r["Hạng Thưởng"]),
                                 detail=f"{r['Gán']:,.0f} đơn gán · {r['GTC']:,.0f} đơn GTC")
                            for _, r in top3.iterrows()]
                        podium_foot = (f"{len(bxh)} nhân viên dự thi  ·  {n_dat} người đạt điều kiện  ·  "
                                       f"Dữ liệu đến {kho['Ngày'].max():%d/%m/%Y}")

                        def podium_png() -> bytes:
                            return render_podium_image(
                                podium_cards, f"VINH DANH TOP 3 THI ĐUA — {ten_n.upper()}",
                                f"{pham_vi}  ·  Điều kiện: %GTC ≥ 80%", podium_foot)

                        pv1, pv2 = st.columns([1, 1], vertical_alignment="bottom")
                        with pv1:
                            st.download_button("TẢI ẢNH VINH DANH TOP 3", podium_png,
                                               f"vinh_danh_top3_{ky_slug}.png", "image/png",
                                               key="dl_td_podium", width="stretch", on_click="ignore")
                        with pv2:
                            show_pod = st.session_state.get("show_td_podium", False)
                            st.button("ẨN ẢNH XEM TRƯỚC" if show_pod else "XEM TRƯỚC ẢNH VINH DANH",
                                      key="btn_td_prev_podium", width="stretch",
                                      on_click=lambda: st.session_state.update(
                                          show_td_podium=not st.session_state.get("show_td_podium", False)))
                        if st.session_state.get("show_td_podium", False):
                            with st.spinner("Đang vẽ ảnh..."):
                                st.image(podium_png(), width="stretch")

                    # ── Bảng xếp hạng đầy đủ ───────────────────────────────────────
                with _sub_tab7[1]:
                    section("Bảng xếp hạng chi tiết")
                    show = bxh.copy()
                    show["Nhân Viên"] = show["Nhân Viên"].map(staff_label)
                    show["Hạng Thưởng"] = show["Hạng Thưởng"].map(
                        lambda h: f"{medals[int(h)]} {int(h)}" if pd.notna(h) else "—")
                    cols_order = ["Xếp Hạng Tổng", "Nhân Viên", "Bưu Cục", "Gán", "GTC",
                                  col_now, col_prev, "Tỷ Lệ Cải Thiện",
                                  "Xếp Hạng Gán", "Xếp Hạng %GTC", "Xếp Hạng Cải Thiện",
                                  "Tổng Điểm", "Đủ ĐK (≥80%)", "Hạng Thưởng", "Thưởng"]
                    show = show[cols_order]
                    st.dataframe(
                        show, width="stretch", hide_index=True, height=560,
                        column_config={
                            "Xếp Hạng Tổng": st.column_config.NumberColumn("Hạng", format="%d", width="small"),
                            "Gán": st.column_config.NumberColumn("Tổng Đơn Gán", format="%,d"),
                            "GTC": st.column_config.NumberColumn("Tổng Đơn GTC", format="%,d"),
                            col_now: st.column_config.NumberColumn(col_now, format="%.2f%%"),
                            col_prev: st.column_config.NumberColumn(col_prev, format="%.2f%%"),
                            "Tỷ Lệ Cải Thiện": st.column_config.NumberColumn("Cải Thiện (pp)", format="%+.2f"),
                            "Tổng Điểm": st.column_config.NumberColumn("Tổng Điểm", format="%.2f"),
                        })
                    ti1, ti2, ti3 = st.columns([1.3, 1, 1], vertical_alignment="bottom")
                    with ti1:
                        td_n = st.selectbox("Số nhân viên trong ảnh",
                                            ["Tất cả", "Top 10", "Top 20", "Top 50"], key="td_img_n")
                    top_n_td = {"Top 10": 10, "Top 20": 20, "Top 50": 50}.get(td_n, len(bxh))
                    img_td = pd.DataFrame({
                        "Hạng": bxh["Xếp Hạng Tổng"],
                        "Nhân viên": bxh["Nhân Viên"].map(staff_label),
                        "Bưu cục": bxh["Bưu Cục"].astype(str),
                        "Gán": bxh["Gán"], "GTC": bxh["GTC"],
                        "Now": bxh[col_now], "Prev": bxh[col_prev],
                        "Cải thiện": bxh["Tỷ Lệ Cải Thiện"], "Điểm": bxh["Tổng Điểm"],
                        "ĐK": bxh["Đủ ĐK (≥80%)"], "Thưởng": bxh["Thưởng"],
                        "Hạng thưởng": bxh["Hạng Thưởng"],
                    }).head(top_n_td)
                    def table_png() -> bytes:
                        return render_td_table_image(
                            img_td, f"BẢNG XẾP HẠNG THI ĐUA — {ten_n.upper()}",
                            f"{pham_vi}  ·  So với {ten_n1_th}  ·  Xếp theo tổng điểm 3 tiêu chí",
                            f"{len(img_td)}/{len(bxh)} nhân viên  ·  Tổng điểm càng nhỏ càng tốt  ·  "
                            f"Dữ liệu đến {kho['Ngày'].max():%d/%m/%Y}",
                            f"%GTC {ten_n}" if theo_thang else "%GTC kỳ này",
                            f"%GTC {ten_n1}" if theo_thang else "%GTC kỳ trước",
                            "THƯỞNG" if theo_thang else "VINH DANH")
                    with ti2:
                        st.download_button("TẢI ẢNH BẢNG XẾP HẠNG", table_png,
                                           f"bang_xep_hang_thi_dua_{ky_slug}.png", "image/png",
                                           key="dl_td_img", width="stretch", on_click="ignore")
                    with ti3:
                        st.download_button("TẢI CSV BẢNG XẾP HẠNG",
                                           show.to_csv(index=False).encode("utf-8-sig"),
                                           f"thi_dua_{ky_slug}.csv", "text/csv",
                                           key="dl_td", width="stretch", on_click="ignore")
                    show_tbl = st.session_state.get("show_td_table", False)
                    st.button("ẨN ẢNH XEM TRƯỚC" if show_tbl else "XEM TRƯỚC ẢNH BẢNG XẾP HẠNG",
                              key="btn_td_prev_table", width="stretch",
                              on_click=lambda: st.session_state.update(
                                  show_td_table=not st.session_state.get("show_td_table", False)))
                    if show_tbl:
                        with st.spinner("Đang vẽ ảnh..."):
                            st.image(table_png(), width="stretch")

                with _sub_tab7[2]:
                    # ── Biểu đồ cải thiện ──────────────────────────────────────────
                    section(f"Mức cải thiện %GTC so với {ten_n1_th}")
                    chart_td = bxh.sort_values("Tỷ Lệ Cải Thiện")
                    fig_td = go.Figure(go.Bar(
                        x=chart_td["Tỷ Lệ Cải Thiện"],
                        y=chart_td["Nhân Viên"].map(staff_label),
                        orientation="h",
                        marker=dict(color=[SUCCESS if v >= 0 else DANGER
                                           for v in chart_td["Tỷ Lệ Cải Thiện"]]),
                        text=[f"{v:+.2f}" for v in chart_td["Tỷ Lệ Cải Thiện"]],
                        textposition="outside", textfont=dict(size=15), cliponaxis=False,
                        hovertemplate="%{y}<br>Cải thiện %{x:+.2f} điểm phần trăm<extra></extra>"))
                    fig_td.add_vline(x=0, line_color=MUTED, line_width=1)
                    lim = float(max(abs(chart_td["Tỷ Lệ Cải Thiện"].min()),
                                    abs(chart_td["Tỷ Lệ Cải Thiện"].max()), 1)) * 1.35
                    fig_td.update_xaxes(range=[-lim, lim], title_text="Điểm phần trăm")
                    fig_td.update_yaxes(automargin=True, tickfont=dict(size=15))
                    fig_td.update_layout(height=max(360, 60 * len(chart_td) + 140),
                                         margin=dict(l=20, r=90, t=60, b=70), showlegend=False)
                    st.plotly_chart(fig_td, width="stretch")

                    # ── Thể lệ ─────────────────────────────────────────────────────
                with _sub_tab7[3]:
                    section("Thể lệ chương trình")
                    c_left, c_right = st.columns(2)
                    with c_left:
                        st.markdown(f"""
                <div class="ghn-alert">
                <b>CƠ CẤU THƯỞNG HÀNG THÁNG</b><br><br>
                🥇 Hạng 1 — <b>{fmt_money(1_000_000)}</b><br>
                🥈 Hạng 2 — <b>{fmt_money(500_000)}</b><br>
                🥉 Hạng 3 — <b>{fmt_money(300_000)}</b><br><br>
                <b>ĐIỀU KIỆN XÉT THƯỞNG</b><br>
                Tỷ lệ GTC tháng phải từ <b>80%</b> trở lên.<br><br>
                Giải trao cho <b>3 người đủ điều kiện xếp cao nhất</b>. Nếu người dẫn đầu bảng
                không đạt mốc 80% thì suất thưởng chuyển xuống người đủ điều kiện kế tiếp.
                </div>""", unsafe_allow_html=True)
                    with c_right:
                        st.markdown("""
                <div class="ghn-alert">
                <b>CÁCH TÍNH XẾP HẠNG</b><br><br>
                Xếp hạng riêng theo 3 tiêu chí, người tốt nhất mỗi tiêu chí được hạng 1:<br>
                1. <b>Số đơn gán</b> — gán nhiều nhất hạng 1<br>
                2. <b>Tỷ lệ GTC</b> — GTC cao nhất hạng 1<br>
                3. <b>Tỷ lệ cải thiện</b> — cải thiện nhiều nhất so với kỳ trước hạng 1<br><br>
                <b>Tổng điểm</b> = trung bình cộng thứ hạng của 3 tiêu chí.
                Tổng điểm càng <b>nhỏ</b> thì xếp hạng càng cao.<br>
                Nếu tổng điểm bằng nhau, ai có <b>%GTC cao hơn</b> xếp trước.
                </div>""", unsafe_allow_html=True)

                with _sub_tab7[4]:
                    # ── Cố vấn AI ──────────────────────────────────────────────────
                    top_txt = "\n".join(
                        f"- Hạng {int(r['Xếp Hạng Tổng'])}: {staff_label(r['Nhân Viên'])} "
                        f"({r['Bưu Cục']}) — gán {r['Gán']:,.0f}, GTC {r['GTC']:,.0f}, "
                        f"%GTC {r[col_now]:.2f}%, cải thiện {r['Tỷ Lệ Cải Thiện']:+.2f} pp, "
                        f"tổng điểm {r['Tổng Điểm']:.2f}, "
                        f"{'ĐƯỢC THƯỞNG hạng ' + str(int(r['Hạng Thưởng'])) if pd.notna(r['Hạng Thưởng']) else ('đủ điều kiện nhưng ngoài top 3' if r[col_now] >= 80 else 'CHƯA đủ điều kiện 80%')}"
                        for _, r in bxh.head(10).iterrows())
                    cuoi_txt = "\n".join(
                        f"- Hạng {int(r['Xếp Hạng Tổng'])}: {staff_label(r['Nhân Viên'])} "
                        f"— %GTC {r[col_now]:.2f}%, cải thiện {r['Tỷ Lệ Cải Thiện']:+.2f} pp"
                        for _, r in bxh.tail(5).iterrows())

                    ai_advisor(
                        "td", "Thi đua",
                        f"""Bảng xếp hạng thi đua giao thành công {ten_n_th}, so với {ten_n1_th}.
Phạm vi: {bc_td}. Tổng {len(bxh)} nhân viên dự thi, {n_dat} người đạt mốc %GTC từ 80%.

TOP 10:
{top_txt}

NHÓM CUỐI BẢNG:
{cuoi_txt}

{"Tổng tiền thưởng phải chi theo kết quả hiện tại: " + fmt_money(tong_thuong) + "." if theo_thang else "Xếp theo tuần: chỉ vinh danh, thưởng tiền tính theo tháng."}""",
                    extra_note="Cơ cấu thưởng tháng: 1.000.000 đ, 500.000 đ và 300.000 đ trao cho BA NGƯỜI "
                               "ĐỦ ĐIỀU KIỆN (%GTC kỳ từ 80% trở lên) xếp cao nhất. Nếu người dẫn đầu "
                               "bảng không đạt mốc 80% thì suất thưởng chuyển xuống người kế tiếp đủ điều kiện. "
                               "Xếp hạng dựa trên trung bình thứ hạng của 3 tiêu chí: số đơn gán, "
                               "tỷ lệ GTC, và mức cải thiện so với kỳ trước. Tổng điểm càng nhỏ càng tốt. "
                               "Hãy nêu rõ ai xứng đáng tuyên dương, ai đang tụt hạng cần kèm cặp, "
                               "và có trường hợp nào xếp hạng cao nhưng trượt điều kiện 80% không.")

# ═══════════════════════════════════════════════════════════════════════
# TAB 6 — AI CỐ VẤN
# ═══════════════════════════════════════════════════════════════════════
if PAGE == "ai":
    with st.container():
        st.markdown("Hỏi bằng tiếng Việt thường ngày. AI đọc trực tiếp các bảng dữ liệu "
                    "đã tải trong phiên làm việc này.")

        z1, z2 = st.columns([1, 2])
        with z1:
            bc_ai = st.selectbox("Bưu cục", ALL_BC, key="bc_ai")
        with z2:
            # Mặc định: 7 ngày gần nhất theo giờ Việt Nam
            a_ai, b_ai = date_range_picker("Khoảng ngày AI được đọc",
                                           DEFAULT_7D_START, DEFAULT_7D_END, "date_ai")

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
                ("ODR TIKTOK", M_ODR, "wavg"), ("OPR TIKTOK", M_OPR, "wavg"), ("DOANH THU", M_DT, "sum"),
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
                if s.empty:
                    continue

                # LỖI CŨ: cắt còn 8 cột đầu ([:8]) làm mất các cột nằm sau, trong đó có
                # "Đơn giá" (cột thứ 14 của sheet lương). AI vì thế không thấy đơn giá
                # và trả lời là không có dữ liệu. Nay giữ ĐỦ cột, chỉ bỏ cột rỗng hoàn toàn.
                keep = [c for c in s.columns if c != "Ngày" and not s[c].isna().all()]
                o = s[["Ngày"] + keep].copy()
                o["Ngày"] = o["Ngày"].dt.strftime("%d/%m/%Y")
                parts.append(f"\n--- {label} (đủ {len(keep)} cột) ---\n"
                             f"{o.head(600).to_csv(index=False)}")
                if len(o) > 600:
                    parts.append(f"(Đã cắt bớt, tổng cộng {len(o):,} dòng trong kỳ này.)\n")

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

GHI CHÚ VỀ BẢNG LUONG NHAN VIEN (đơn vị tiền là VNĐ):
- "Đơn giá" là đơn giá bình quân mỗi đơn của nhân viên trong ngày đó.
- "Đơn LTC" là đơn lấy thành công, "Đơn GTC" là đơn giao thành công,
  "Đơn GTBTT" là đơn giao thất bại nhưng thu được tiền.
- Sản lượng GTC dùng để tính lương = Đơn GTC + Đơn GTBTT.
- "LHH LTC", "LHH GTC", "LHH GTBTT" là ba khoản lương hoa hồng; tổng lương là tổng ba khoản này.
- Kỳ lương gọi theo tháng CHI lương: Kỳ 20 tháng M gồm dữ liệu ngày 01-15 tháng M;
  Kỳ 05 tháng M+1 gồm dữ liệu ngày 16 đến hết tháng M.
- Cột "Nhân Viên" ghi theo dạng "mã_họ tên" hoặc "mã-họ tên". Cùng một mã là cùng một người,
  kể cả khi tên viết khác nhau giữa các bảng.
- Khi tính đơn giá bình quân cho nhiều dòng, hãy nói rõ là trung bình cộng của các dòng nào.

Câu hỏi của người quản lý: {question}

Trả lời dựa ĐÚNG vào số liệu trên, gọi tên đích danh bưu cục hoặc nhân viên kèm con số cụ thể.
Nếu dữ liệu không đủ để trả lời, nói rõ là không có, tuyệt đối không suy đoán.
Trình bày bằng markdown, in đậm các con số quan trọng.""")
                st.markdown(answer)
                st.session_state.chat.append({"role": "assistant", "content": answer})


st.markdown(
    f"<div style='margin-top:36px;padding-top:16px;border-top:2px solid {LINE};"
    f"text-align:center;color:{MUTED};font-size: calc(15.25px * var(--fs));font-weight:600;'>"
    f"TRUNG TÂM VẬN HÀNH — GHN &nbsp;·&nbsp; Designed by AM Phan Van Chanh</div>",
    unsafe_allow_html=True)
