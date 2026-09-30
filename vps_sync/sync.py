"""
ĐỒNG BỘ BÁO CÁO CÔNG TY → GOOGLE SHEETS CỦA DASHBOARD (chạy trên VPS)

Mỗi lần chạy:
  1. Mở trình duyệt ẩn (Chromium/Playwright), đăng nhập trang báo cáo công ty
     (dùng lại phiên đã lưu nếu còn hạn).
  2. Với từng "job" trong config.yaml:
       - kind: download → bấm nút Xuất file, đọc file Excel/CSV tải về
       - kind: table    → đọc bảng đang hiển thị trên trang (thay cho bôi đen + copy)
  3. Nối các dòng MỚI vào tab Google Sheet đích (dòng đã có thì bỏ qua).

Lệnh:
    python sync.py                    # chạy tất cả job
    python sync.py --job gtc_tong     # chỉ chạy 1 job
    python sync.py --dry-run          # lấy dữ liệu, in thử, KHÔNG ghi Sheet
    python sync.py login --headed     # mở trình duyệt có giao diện để đăng nhập tay
                                      # (khi có OTP/captcha), lưu phiên vào state/

Biến môi trường:
    GOOGLE_CREDENTIALS  — đường dẫn file JSON service account (mặc định: credentials.json)
    CHROMIUM_PATH       — (tùy chọn) đường dẫn Chromium có sẵn trên máy
    TELEGRAM_TOKEN / TELEGRAM_CHAT_ID — (tùy chọn) báo lỗi qua Telegram
    Các biến tự đặt như BAO_CAO_USER, BAO_CAO_PASS được dùng trong config qua ${TEN_BIEN}.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import yaml

BASE_DIR = Path(__file__).resolve().parent
STATE_DIR = BASE_DIR / "state"
DOWNLOAD_DIR = BASE_DIR / "downloads"
SESSION_FILE = STATE_DIR / "session.json"
TZ = ZoneInfo("Asia/Ho_Chi_Minh")

log = logging.getLogger("sync")


# ═══════════════════════════════════════════════════════════════════════
# 1. CẤU HÌNH
# ═══════════════════════════════════════════════════════════════════════
def _expand_env(value):
    """Thay ${TEN_BIEN} bằng giá trị biến môi trường, để không ghi mật khẩu vào config."""
    if isinstance(value, str):
        def repl(m):
            name = m.group(1)
            if name not in os.environ:
                raise SystemExit(f"Thiếu biến môi trường {name} (được dùng trong config.yaml)")
            return os.environ[name]
        return re.sub(r"\$\{(\w+)\}", repl, value)
    if isinstance(value, list):
        return [_expand_env(v) for v in value]
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    return value


def load_config(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"Không thấy {path}. Hãy copy config.example.yaml thành config.yaml rồi sửa.")
    cfg = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    cfg = _expand_env(cfg)
    names = [j.get("name") for j in cfg.get("jobs", [])]
    if not names or any(not n for n in names):
        raise SystemExit("config.yaml: mỗi job phải có 'name'")
    if len(set(names)) != len(names):
        raise SystemExit("config.yaml: tên job bị trùng")
    for job in cfg["jobs"]:
        if job.get("kind") not in ("download", "table"):
            raise SystemExit(f"Job '{job['name']}': kind phải là 'download' hoặc 'table'")
        if not job.get("target", {}).get("sheet_url"):
            raise SystemExit(f"Job '{job['name']}': thiếu target.sheet_url")
    return cfg


# ═══════════════════════════════════════════════════════════════════════
# 2. TRÌNH DUYỆT — ĐĂNG NHẬP & CÁC BƯỚC THAO TÁC
# ═══════════════════════════════════════════════════════════════════════
def run_steps(page, steps: list | None) -> None:
    """Thực hiện lần lượt các bước thao tác trên trang.

    Mỗi bước là 1 dict một khóa, ví dụ:
        - goto: https://...            mở trang
        - click: "text=Xuất Excel"     bấm
        - fill: {selector: "#user", value: "abc"}
        - select: {selector: "#kho", value: "HCM"}
        - press: {selector: "#search", key: "Enter"}
        - wait_for: ".ant-table-row"   chờ phần tử xuất hiện
        - wait_ms: 2000                nghỉ (mili giây)
    """
    for step in steps or []:
        if not isinstance(step, dict) or len(step) != 1:
            raise ValueError(f"Bước không hợp lệ: {step!r}")
        action, arg = next(iter(step.items()))
        log.debug("  bước %s: %s", action, arg)
        if action == "goto":
            page.goto(arg, wait_until="networkidle")
        elif action == "click":
            page.locator(arg).first.click()
        elif action == "fill":
            page.locator(arg["selector"]).first.fill(str(arg["value"]))
        elif action == "select":
            page.locator(arg["selector"]).first.select_option(str(arg["value"]))
        elif action == "press":
            page.locator(arg["selector"]).first.press(arg["key"])
        elif action == "wait_for":
            page.locator(arg).first.wait_for(state="visible")
        elif action == "wait_ms":
            page.wait_for_timeout(int(arg))
        else:
            raise ValueError(f"Không hiểu bước '{action}'")


def is_logged_in(page, login_cfg: dict) -> bool:
    check_url = login_cfg.get("check_url")
    if not check_url:
        return False
    page.goto(check_url, wait_until="networkidle")
    marker = login_cfg.get("logged_in_selector")
    if marker:
        try:
            page.locator(marker).first.wait_for(state="visible", timeout=8000)
            return True
        except Exception:
            return False
    # Không có selector đánh dấu: coi như chưa đăng nhập nếu bị chuyển về trang login.
    return "login" not in page.url.lower()


def ensure_login(context, page, login_cfg: dict | None) -> None:
    if not login_cfg:
        return
    if is_logged_in(page, login_cfg):
        log.info("Dùng lại phiên đăng nhập đã lưu")
        return
    if not login_cfg.get("steps"):
        raise RuntimeError("Phiên đăng nhập hết hạn và config không có login.steps — "
                           "hãy chạy lại 'python sync.py login --headed'")
    log.info("Đăng nhập lại…")
    run_steps(page, login_cfg["steps"])
    if login_cfg.get("check_url") and not is_logged_in(page, login_cfg):
        raise RuntimeError("Đăng nhập thất bại (sai mật khẩu, hoặc trang yêu cầu OTP/captcha)")
    STATE_DIR.mkdir(exist_ok=True)
    context.storage_state(path=str(SESSION_FILE))


def open_browser(pw, headed: bool = False):
    launch_kwargs = {"headless": not headed}
    if os.environ.get("CHROMIUM_PATH"):
        launch_kwargs["executable_path"] = os.environ["CHROMIUM_PATH"]
    browser = pw.chromium.launch(**launch_kwargs)
    ctx_kwargs = {"accept_downloads": True, "locale": "vi-VN", "timezone_id": "Asia/Ho_Chi_Minh",
                  "viewport": {"width": 1600, "height": 1000}}
    if SESSION_FILE.exists():
        ctx_kwargs["storage_state"] = str(SESSION_FILE)
    context = browser.new_context(**ctx_kwargs)
    context.set_default_timeout(60_000)
    return browser, context


# ═══════════════════════════════════════════════════════════════════════
# 3. LẤY DỮ LIỆU
# ═══════════════════════════════════════════════════════════════════════
def read_file(path: Path, job: dict) -> pd.DataFrame:
    opts = job.get("read", {})
    header = opts.get("header_row", 1) - 1       # người dùng đếm từ 1 như Excel
    suffix = path.suffix.lower()
    if suffix in (".xlsx", ".xlsm", ".xls"):
        return pd.read_excel(path, sheet_name=opts.get("sheet", 0), header=header, dtype=str)
    if suffix in (".csv", ".txt"):
        raw = path.read_bytes()
        for enc in ("utf-8-sig", "utf-16", "cp1258", "latin-1"):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        return pd.read_csv(io.StringIO(text), header=header, dtype=str,
                           sep=opts.get("sep") or None, engine="python")
    raise RuntimeError(f"Không đọc được định dạng file {path.name}")


def fetch_download(page, job: dict) -> pd.DataFrame:
    run_steps(page, job.get("steps"))
    with page.expect_download(timeout=job.get("download_timeout_ms", 180_000)) as dl_info:
        page.locator(job["download_click"]).first.click()
    dl = dl_info.value
    DOWNLOAD_DIR.mkdir(exist_ok=True)
    stamp = datetime.now(TZ).strftime("%Y%m%d_%H%M%S")
    path = DOWNLOAD_DIR / f"{job['name']}_{stamp}_{dl.suggested_filename}"
    dl.save_as(str(path))
    log.info("  đã tải %s", path.name)
    return read_file(path, job)


def _grid_to_df(page, grid: dict) -> pd.DataFrame:
    """Đọc bảng dựng bằng thẻ <div> (không phải <table>) theo selector dòng/ô."""
    rows = page.locator(grid["row_selector"]).evaluate_all(
        "(rows, cell) => rows.map(r => Array.from(r.querySelectorAll(cell))"
        ".map(c => c.innerText.trim()))",
        grid["cell_selector"],
    )
    rows = [r for r in rows if any(r)]
    if not rows:
        return pd.DataFrame()
    if grid.get("header_selector"):
        header = page.locator(grid["header_selector"]).all_inner_texts()
        header = [h.strip() for h in header]
    else:
        header, rows = rows[0], rows[1:]
    width = len(header)
    rows = [(r + [""] * width)[:width] for r in rows]
    return pd.DataFrame(rows, columns=header)


def _table_to_df(page, selector: str, index: int) -> pd.DataFrame:
    """Đọc bảng <table> đúng như chữ hiển thị (giống bôi đen + copy), không tự đổi kiểu số."""
    tables = page.locator(selector)
    count = tables.count()
    if count == 0:
        raise RuntimeError(f"Không thấy bảng '{selector}' trên trang")
    if index >= count:
        raise RuntimeError(f"Trang chỉ có {count} bảng khớp '{selector}', không có bảng số {index + 1}")
    data = tables.nth(index).evaluate("""t => {
        const cells = tr => Array.from(tr.querySelectorAll('th,td')).map(c => c.innerText.trim());
        const head = Array.from(t.querySelectorAll('thead tr'));
        let header = head.length ? cells(head[head.length - 1]) : null;
        let body = Array.from(t.querySelectorAll('tbody tr')).map(cells);
        if (!body.length) body = Array.from(t.querySelectorAll('tr')).map(cells);
        if (!header) header = body.shift() || [];
        return {header, body};
    }""")
    header = data["header"]
    width = len(header)
    rows = [(r + [""] * width)[:width] for r in data["body"] if any(r)]
    return pd.DataFrame(rows, columns=header)


def fetch_table(page, job: dict) -> pd.DataFrame:
    run_steps(page, job.get("steps"))
    tcfg = job.get("table", {})
    frames = []
    for page_no in range(int(tcfg.get("max_pages", 1))):
        if "grid" in tcfg:
            df = _grid_to_df(page, tcfg["grid"])
        else:
            df = _table_to_df(page, tcfg.get("selector", "table"), int(tcfg.get("index", 0)))
        frames.append(df)
        nxt = tcfg.get("next_selector")
        if not nxt:
            break
        btn = page.locator(nxt).first
        if btn.count() == 0 or not btn.is_enabled() or btn.get_attribute("aria-disabled") == "true":
            break
        btn.click()
        page.wait_for_timeout(int(tcfg.get("page_wait_ms", 1500)))
        log.info("  sang trang %d", page_no + 2)
    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return df


def clean_df(df: pd.DataFrame, job: dict) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    df = df.loc[:, [c for c in df.columns if c and not c.startswith("Unnamed")]]
    df = df.fillna("").astype(str).apply(lambda s: s.str.strip())
    df = df.replace({"nan": "", "None": "", "NaT": ""})
    df = df[(df != "").any(axis=1)]
    if job.get("columns"):
        missing = [c for c in job["columns"] if c not in df.columns]
        if missing:
            raise RuntimeError(f"Báo cáo không có cột {missing}. Cột hiện có: {list(df.columns)}")
        df = df[job["columns"]]
    if job.get("rename"):
        df = df.rename(columns=job["rename"])
    stamp_col = job.get("add_timestamp_column")
    if stamp_col:
        df[stamp_col] = datetime.now(TZ).strftime("%d/%m/%Y %H:%M")
    return df.reset_index(drop=True)


# ═══════════════════════════════════════════════════════════════════════
# 4. GHI GOOGLE SHEETS — CHỈ NỐI DÒNG MỚI
# ═══════════════════════════════════════════════════════════════════════
def _norm(v) -> str:
    return re.sub(r"\s+", " ", str(v)).strip()


def row_key(names: list[str], values: list[str]) -> str:
    """Khóa của 1 dòng = các cặp cột=giá trị khác rỗng, sắp theo tên cột.
    Nhờ vậy báo cáo thêm cột mới hay đổi thứ tự cột thì dòng cũ vẫn được nhận ra."""
    pairs = sorted((n, _norm(v)) for n, v in zip(names, values) if _norm(v))
    return hashlib.sha1(json.dumps(pairs, ensure_ascii=False).encode("utf-8")).hexdigest()


def _seen_file(job_name: str) -> Path:
    return STATE_DIR / f"seen_{job_name}.json"


def load_seen(job_name: str) -> set[str]:
    f = _seen_file(job_name)
    return set(json.loads(f.read_text())) if f.exists() else set()


def save_seen(job_name: str, keys: set[str]) -> None:
    STATE_DIR.mkdir(exist_ok=True)
    _seen_file(job_name).write_text(json.dumps(sorted(keys)))


def plan_append(existing: list[list[str]], df: pd.DataFrame, key_columns: list[str] | None,
                seen: set[str]) -> tuple[list[str], list[list[str]], set[str]]:
    """Tính header cần ghi và các dòng mới cần nối thêm.

    Trả về (header, rows_to_append, keys_of_new_rows).
    - Sheet trống → header = cột của báo cáo.
    - Sheet đã có header → giữ thứ tự cột của Sheet; cột mới xuất hiện được thêm vào cuối.
    - Dòng trùng (theo key_columns, hoặc cả dòng nếu không khai) với Sheet
      hoặc với các lần chạy trước (state/seen_*.json) thì bỏ qua.
    """
    header = [_norm(h) for h in existing[0]] if existing and any(existing[0]) else []
    extra = [c for c in df.columns if c not in header]
    header = header + extra

    keys = key_columns or [c for c in df.columns]
    missing = [k for k in keys if k not in header]
    if missing:
        raise RuntimeError(f"Cột khóa {missing} không có trong dữ liệu")
    key_idx = [header.index(k) for k in keys]

    known = set(seen)
    for r in existing[1:]:
        padded = r + [""] * (len(header) - len(r))
        known.add(row_key(keys, [padded[i] for i in key_idx]))

    new_rows, new_keys = [], set()
    aligned = df.reindex(columns=header).fillna("").astype(str)
    for values in aligned.values.tolist():
        k = row_key(keys, [values[i] for i in key_idx])
        if k in known or k in new_keys:
            continue
        new_keys.add(k)
        new_rows.append(values)
    return header, new_rows, new_keys


def open_worksheet(gc, sheet_url: str, tab: str | None):
    sh = gc.open_by_url(sheet_url)
    if tab:
        try:
            return sh.worksheet(tab)
        except Exception:
            log.info("  tạo tab mới '%s'", tab)
            return sh.add_worksheet(title=tab, rows=1000, cols=26)
    m = re.search(r"[#?&]gid=(\d+)", sheet_url)
    return sh.get_worksheet_by_id(int(m.group(1))) if m else sh.sheet1


def write_append(gc, job: dict, df: pd.DataFrame) -> int:
    target = job["target"]
    ws = open_worksheet(gc, target["sheet_url"], target.get("tab"))
    existing = ws.get_all_values()
    seen = load_seen(job["name"])
    # Cột thời điểm cập nhật đổi mỗi lần chạy → không được tính vào khóa chống trùng.
    key_columns = job.get("key_columns") or [c for c in df.columns if c != job.get("add_timestamp_column")]
    header, rows, new_keys = plan_append(existing, df, key_columns, seen)

    old_header = existing[0] if existing else []
    if [_norm(h) for h in old_header] != header:
        if ws.col_count < len(header):
            ws.add_cols(len(header) - ws.col_count)
        ws.update(range_name="A1", values=[header], value_input_option="RAW")
    if rows:
        ws.append_rows(rows, value_input_option="USER_ENTERED", insert_data_option="INSERT_ROWS",
                       table_range="A1")
    save_seen(job["name"], seen | new_keys)
    return len(rows)


def google_client():
    import gspread
    cred = os.environ.get("GOOGLE_CREDENTIALS", str(BASE_DIR / "credentials.json"))
    if not Path(cred).exists():
        raise SystemExit(f"Không thấy file service account {cred} (xem README mục 2)")
    return gspread.service_account(filename=cred)


# ═══════════════════════════════════════════════════════════════════════
# 5. CHẠY
# ═══════════════════════════════════════════════════════════════════════
def notify(text: str) -> None:
    token, chat = os.environ.get("TELEGRAM_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not (token and chat):
        return
    try:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      data={"chat_id": chat, "text": text[:4000]}, timeout=15)
    except Exception as e:
        log.warning("Không gửi được Telegram: %s", e)


def cmd_login(cfg: dict, headed: bool) -> None:
    from playwright.sync_api import sync_playwright
    login_cfg = cfg.get("login") or {}
    with sync_playwright() as pw:
        browser, context = open_browser(pw, headed=headed)
        page = context.new_page()
        if headed:
            page.goto(login_cfg.get("url") or login_cfg.get("check_url") or "about:blank")
            input("Đăng nhập trong cửa sổ trình duyệt, xong thì bấm Enter ở đây… ")
        else:
            ensure_login(context, page, login_cfg)
        STATE_DIR.mkdir(exist_ok=True)
        context.storage_state(path=str(SESSION_FILE))
        browser.close()
    print(f"Đã lưu phiên đăng nhập vào {SESSION_FILE}")


def cmd_sync(cfg: dict, only: str | None, dry_run: bool) -> int:
    from playwright.sync_api import sync_playwright
    jobs = [j for j in cfg["jobs"] if not only or j["name"] == only]
    if not jobs:
        raise SystemExit(f"Không có job tên '{only}'")
    gc = None if dry_run else google_client()
    errors = []
    with sync_playwright() as pw:
        browser, context = open_browser(pw)
        page = context.new_page()
        ensure_login(context, page, cfg.get("login"))
        for job in jobs:
            if job.get("enabled") is False:
                continue
            t0 = time.time()
            log.info("▶ %s (%s)", job["name"], job["kind"])
            try:
                df = fetch_download(page, job) if job["kind"] == "download" else fetch_table(page, job)
                df = clean_df(df, job)
                log.info("  lấy được %d dòng, %d cột", len(df), len(df.columns))
                if dry_run:
                    print(f"\n=== {job['name']} — {len(df)} dòng ===")
                    print(df.head(10).to_string(index=False))
                    continue
                if df.empty:
                    raise RuntimeError("báo cáo trống — kiểm tra lại bộ lọc/selector")
                n = write_append(gc, job, df)
                log.info("  ✔ nối thêm %d dòng mới (%.1fs)", n, time.time() - t0)
            except Exception as e:
                log.exception("  ✘ lỗi job %s", job["name"])
                errors.append(f"{job['name']}: {e}")
                DOWNLOAD_DIR.mkdir(exist_ok=True)
                try:
                    page.screenshot(path=str(DOWNLOAD_DIR / f"loi_{job['name']}.png"), full_page=True)
                except Exception:
                    pass
        if cfg.get("login"):
            # Lưu lại cookie mới nhất để lần sau không phải đăng nhập lại.
            STATE_DIR.mkdir(exist_ok=True)
            context.storage_state(path=str(SESSION_FILE))
        browser.close()
    if errors:
        notify("⚠️ Đồng bộ báo cáo lỗi:\n" + "\n".join(errors))
        return 1
    return 0


def cleanup_downloads(keep_days: int = 7) -> None:
    if not DOWNLOAD_DIR.exists():
        return
    cutoff = time.time() - keep_days * 86400
    for f in DOWNLOAD_DIR.iterdir():
        if f.is_file() and f.stat().st_mtime < cutoff:
            f.unlink()


def main() -> None:
    ap = argparse.ArgumentParser(description="Đồng bộ báo cáo công ty → Google Sheets")
    ap.add_argument("command", nargs="?", default="sync", choices=["sync", "login"])
    ap.add_argument("--config", default=str(BASE_DIR / "config.yaml"))
    ap.add_argument("--job", help="chỉ chạy job có tên này")
    ap.add_argument("--dry-run", action="store_true", help="không ghi Google Sheets")
    ap.add_argument("--headed", action="store_true", help="hiện cửa sổ trình duyệt (dùng với login)")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    cfg = load_config(Path(args.config))
    if args.command == "login":
        cmd_login(cfg, args.headed)
        return
    cleanup_downloads()
    sys.exit(cmd_sync(cfg, args.job, args.dry_run))


if __name__ == "__main__":
    main()
