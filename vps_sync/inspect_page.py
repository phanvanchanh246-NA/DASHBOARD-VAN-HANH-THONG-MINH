"""
KHẢO SÁT TRANG BÁO CÁO — tự tìm nút Xuất, bảng dữ liệu, nút trang sau và viết sẵn đoạn config.

Chạy trên MÁY TÍNH CÁ NHÂN (có màn hình), không phải trên VPS:

    python sync.py inspect https://trang-bao-cao/login --name gtc_tong

1. Cửa sổ trình duyệt mở ra → đăng nhập, vào trang báo cáo, chọn bộ lọc, bấm Tìm kiếm như mọi khi.
2. Quay lại cửa sổ dòng lệnh, bấm Enter.
3. Công cụ quét trang, (tùy chọn) bấm thử nút Xuất để kiểm tra file, rồi in ra đoạn YAML
   và lưu vào state/goi_y_<name>.yaml để dán vào config.yaml.

Phiên đăng nhập cũng được lưu vào state/session.json (dùng được cho VPS nếu trang có OTP).
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import pandas as pd
import yaml

from sync import DOWNLOAD_DIR, SESSION_FILE, STATE_DIR, open_browser, read_file

log = logging.getLogger("sync")

# Ghi lại thao tác bấm / nhập của người dùng, kèm selector gợi ý cho từng phần tử.
RECORDER_JS = r"""
(() => {
  if (window.__baoCaoRec) return;
  window.__baoCaoRec = true;
  const q = s => s.replace(/'/g, "\\'");
  const txt = el => (el.innerText || el.value || '').replace(/\s+/g, ' ').trim();
  const autoId = id => /\d{3,}|^[a-f0-9-]{16,}$|^(rc|el|mui|react|ember)[-_]/i.test(id);
  window.__selectorOf = el => {
    if (el.id && !autoId(el.id)) return '#' + CSS.escape(el.id);
    const name = el.getAttribute('name');
    if (name && /^(input|select|textarea)$/i.test(el.tagName)) return `${el.tagName.toLowerCase()}[name='${q(name)}']`;
    const ph = el.getAttribute('placeholder');
    if (ph) return `[placeholder='${q(ph)}']`;
    const t = txt(el);
    if (t && t.length <= 40) {
      const tag = el.tagName.toLowerCase();
      return /^(button|a|li|label)$/.test(tag) ? `${tag}:has-text('${q(t)}')` : `text=${t}`;
    }
    const parts = [];
    for (let e = el; e && e.nodeType === 1 && e !== document.body; e = e.parentElement) {
      let p = e.tagName.toLowerCase();
      const sib = Array.from(e.parentElement ? e.parentElement.children : []).filter(x => x.tagName === e.tagName);
      if (sib.length > 1) p += `:nth-of-type(${sib.indexOf(e) + 1})`;
      parts.unshift(p);
    }
    return parts.join(' > ');
  };
  const target = el => el.closest('button, a, [role=button], [role=tab], [role=option], li, label, input, select') || el;
  document.addEventListener('click', e => {
    const el = target(e.target);
    if (/^(input|select|textarea)$/i.test(el.tagName) && el.type !== 'checkbox' && el.type !== 'radio') return;
    window.__baoCaoLog && window.__baoCaoLog({action: 'click', selector: window.__selectorOf(el), text: txt(el).slice(0, 60)});
  }, true);
  document.addEventListener('change', e => {
    const el = e.target;
    if (!/^(input|select|textarea)$/i.test(el.tagName) || el.type === 'password' || el.type === 'checkbox' || el.type === 'radio') return;
    window.__baoCaoLog && window.__baoCaoLog({action: el.tagName === 'SELECT' ? 'select' : 'fill',
                                             selector: window.__selectorOf(el), value: el.value});
  }, true);
})();
"""

# Quét trang: nút xuất, bảng <table>, bảng <div role=grid>, nút trang sau, form đăng nhập.
SCAN_JS = r"""
() => {
  const vis = el => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0 &&
                      getComputedStyle(el).visibility !== 'hidden'; };
  const txt = el => (el.innerText || el.value || el.title || el.getAttribute('aria-label') || '').replace(/\s+/g, ' ').trim();
  const sel = window.__selectorOf;
  const out = {exports: [], tables: [], grids: [], next: [], login: null, logout: null};

  const clickable = Array.from(document.querySelectorAll('button, a, [role=button], input[type=button], input[type=submit], li, span'))
    .filter(vis);
  const seen = new Set();
  for (const el of clickable) {
    const t = txt(el);
    if (!t || t.length > 40 || !/xuất|export|excel|csv|tải\s*(về|xuống)|download/i.test(t)) continue;
    if (/đăng\s*xuất|logout|log\s*out|sign\s*out/i.test(t)) continue;
    const top = el.closest('button, a, [role=button]') || el;
    if (seen.has(top)) continue;
    seen.add(top);
    out.exports.push({selector: sel(top), text: txt(top)});
  }

  // Ưu tiên nút ghi rõ Excel/CSV
  out.exports.sort((a, b) => /excel|csv|xlsx/i.test(b.text) - /excel|csv|xlsx/i.test(a.text));

  const cells = tr => Array.from(tr.querySelectorAll('th,td')).map(c => c.innerText.replace(/\s+/g, ' ').trim());
  // index = thứ tự trong các bảng khớp 'table:has(tbody tr td)' (đúng selector ghi vào config)
  Array.from(document.querySelectorAll('table')).filter(t => t.querySelector('tbody tr td')).forEach((t, i) => {
    if (!vis(t)) return;
    let head = Array.from(t.querySelectorAll('thead tr'));
    const box = t.parentElement && t.parentElement.closest('.ant-table, .el-table, .vxe-table, .k-grid');
    if (!head.length && box) head = Array.from(box.querySelectorAll('thead tr'));
    const body = Array.from(t.querySelectorAll('tbody tr')).filter(tr => cells(tr).some(Boolean));
    if (!body.length) return;   // bảng chỉ có tiêu đề (phần đầu của bảng Ant Design) → bỏ
    const header = head.length ? cells(head[head.length - 1]) : cells(body[0]);
    out.tables.push({index: i, rows: body.length, header, sample: cells(body[0])});
  });

  const grid = document.querySelector('[role=grid], [role=treegrid]');
  if (grid && grid.tagName !== 'TABLE' && vis(grid)) {
    const heads = Array.from(grid.querySelectorAll('[role=columnheader]')).map(txt);
    const rows = grid.querySelectorAll('[role=row]:has([role=gridcell])').length;
    if (rows) out.grids.push({header: heads, rows});
  }

  const nextCss = ['li.ant-pagination-next', '.el-pagination .btn-next', '.pagination .next a',
                   '.page-item.next a', '.paginate_button.next', '.k-pager-nav.k-pager-next',
                   "[aria-label='Next page']", "[aria-label='Trang sau']", "[title='Trang sau']", "[title='Next Page']"];
  for (const c of nextCss) {
    try { const el = document.querySelector(c); if (el && vis(el)) out.next.push(c); } catch (e) {}
  }
  for (const el of clickable) {
    const t = txt(el);
    if (/^(trang sau|sau|tiếp|next|›|»|>)$/i.test(t)) { out.next.push(sel(el.closest('button, a, li') || el)); break; }
  }

  const pw = Array.from(document.querySelectorAll('input[type=password]')).find(vis);
  if (pw) {
    const form = pw.closest('form') || document;
    const user = Array.from(form.querySelectorAll('input:not([type=hidden]):not([type=password]):not([type=checkbox])'))
      .find(vis);
    const btn = Array.from(form.querySelectorAll('button, input[type=submit], [role=button]')).find(vis);
    out.login = {user: user && sel(user), pass: sel(pw), submit: btn && sel(btn)};
  }
  const lo = clickable.find(el => /^(đăng xuất|thoát|logout|log out|sign out)$/i.test(txt(el)));
  if (lo) out.logout = txt(lo);
  return out;
}
"""


def _count(page, selector: str) -> int:
    try:
        return page.locator(selector).count()
    except Exception:
        return 0


def _guess_header_row(path: Path) -> tuple[int, list[str]]:
    """Tìm dòng tiêu đề thật trong file Excel/CSV (bỏ qua các dòng tên báo cáo, ngày xuất ở đầu)."""
    if path.suffix.lower() in (".xlsx", ".xlsm", ".xls"):
        df = pd.read_excel(path, header=None, dtype=str, nrows=30)
    else:
        df = read_file(path, {"read": {"header_row": 1}})
        return 1, [str(c) for c in df.columns]
    filled = df.notna().sum(axis=1)
    best = filled.max()
    for i, n in filled.items():
        if n >= max(2, best * 0.6):
            return int(i) + 1, [str(v) for v in df.iloc[i].tolist() if pd.notna(v)]
    return 1, [str(v) for v in df.iloc[0].tolist()]


def _try_export(page, selector: str, name: str) -> dict | None:
    try:
        with page.expect_download(timeout=120_000) as info:
            page.locator(selector).first.click()
        dl = info.value
    except Exception as e:
        print(f"   ✘ bấm '{selector}' nhưng không thấy file tải về ({e.__class__.__name__}).")
        print("     Có thể nút này mở thêm 1 hộp thoại — khi đó cần thêm bước click vào steps.")
        return None
    DOWNLOAD_DIR.mkdir(exist_ok=True)
    path = DOWNLOAD_DIR / f"inspect_{name}_{dl.suggested_filename}"
    dl.save_as(str(path))
    header_row, cols = _guess_header_row(path)
    print(f"   ✔ tải được {path.name} — tiêu đề ở dòng {header_row}: {cols}")
    return {"header_row": header_row, "columns": cols}


def build_job(scan: dict, name: str, url: str, steps: list[dict], export_info: dict | None) -> dict:
    job: dict = {"name": name}
    all_steps = [{"goto": url}] + steps
    if scan["exports"]:
        job["kind"] = "download"
        if scan["tables"]:
            all_steps.append({"wait_for": "table tbody tr"})
        job["steps"] = all_steps
        job["download_click"] = scan["exports"][0]["selector"]
        job["read"] = {"sheet": 0, "header_row": (export_info or {}).get("header_row", 1)}
        cols = (export_info or {}).get("columns") or []
    elif scan["tables"]:
        best = max(scan["tables"], key=lambda t: t["rows"])
        job["kind"] = "table"
        all_steps.append({"wait_for": "table tbody tr"})
        job["steps"] = all_steps
        job["table"] = {"selector": "table:has(tbody tr td)", "index": best["index"]}
        cols = best["header"]
    elif scan["grids"]:
        job["kind"] = "table"
        all_steps.append({"wait_for": "[role=gridcell]"})
        job["steps"] = all_steps
        job["table"] = {"grid": {"row_selector": "[role=row]:has([role=gridcell])",
                                 "cell_selector": "[role=gridcell]",
                                 "header_selector": "[role=columnheader]"}}
        cols = scan["grids"][0]["header"]
    else:
        raise SystemExit("Không thấy nút Xuất hay bảng dữ liệu nào trên trang. "
                         "Hãy chắc là bảng đã hiện kết quả trước khi bấm Enter.")
    if job["kind"] == "table" and scan["next"]:
        job["table"]["next_selector"] = scan["next"][0]
        job["table"]["max_pages"] = 20
    # Chỉ tự điền cột khóa khi thấy cột kiểu "Mã đơn"; không có thì so cả dòng (an toàn hơn đoán sai).
    ids = [c for c in cols if re.search(r"^(mã|ma |id\b|số đơn|code|order)", str(c), re.I)]
    if ids:
        job["key_columns"] = ids[:1]
    job["add_timestamp_column"] = "Thời điểm cập nhật"
    job["target"] = {"sheet_url": "DAN_LINK_TAB_GOOGLE_SHEET_CO_GID_VAO_DAY"}
    return job


def cmd_inspect(url: str, name: str, headless: bool = False) -> Path:
    from playwright.sync_api import sync_playwright

    events: list[dict] = []
    with sync_playwright() as pw:
        browser, context = open_browser(pw, headed=not headless)
        context.add_init_script(RECORDER_JS)

        def on_event(source, ev):
            ev["url"] = source["frame"].url
            events.append(ev)
        context.expose_binding("__baoCaoLog", on_event)

        page = context.new_page()
        page.goto(url, wait_until="networkidle")
        first = page.evaluate(SCAN_JS)
        login_url = page.url if first["login"] else None

        if not headless:
            input("\n→ Đăng nhập, mở trang báo cáo, chọn bộ lọc và bấm Tìm kiếm cho bảng hiện kết quả.\n"
                  "  Xong thì quay lại đây bấm Enter… ")
        page = context.pages[-1]          # nếu trang báo cáo mở ở tab mới
        page.wait_for_load_state("networkidle")
        report_url = page.url
        scan = page.evaluate(SCAN_JS)

        print(f"\nTrang báo cáo: {report_url}")
        print(f"Nút Xuất tìm được: {len(scan['exports'])}")
        for i, e in enumerate(scan["exports"], 1):
            print(f"  {i}. {e['text']!r:30}  selector: {e['selector']}  (khớp {_count(page, e['selector'])} phần tử)")
        print(f"Bảng <table> có dữ liệu: {len(scan['tables'])}")
        for t in scan["tables"]:
            print(f"  [index {t['index']}] {t['rows']} dòng — cột: {t['header']}")
            print(f"       dòng đầu: {t['sample']}")
        for g in scan["grids"]:
            print(f"Bảng dạng <div role=grid>: {g['rows']} dòng — cột: {g['header']}")
        print(f"Nút trang sau: {scan['next'] or 'không có'}")

        # Thao tác người dùng đã làm trên trang báo cáo (sau lần mở trang cuối cùng).
        steps = []
        for ev in events:
            if ev["url"].split("#")[0] != report_url.split("#")[0]:
                continue
            if ev["action"] == "click":
                if any(ev["selector"] == e["selector"] for e in scan["exports"]):
                    continue
                steps.append({"click": ev["selector"]})
            else:
                steps.append({ev["action"]: {"selector": ev["selector"], "value": ev["value"]}})
        if steps:
            print(f"Các thao tác lọc bạn vừa làm (sẽ đưa vào steps): {steps}")

        export_info = None
        if scan["exports"] and not headless:
            ans = input(f"\nBấm thử nút '{scan['exports'][0]['text']}' để kiểm tra file tải về? (y/N) ")
            if ans.strip().lower().startswith("y"):
                export_info = _try_export(page, scan["exports"][0]["selector"], name)
        elif scan["exports"]:
            export_info = _try_export(page, scan["exports"][0]["selector"], name)

        STATE_DIR.mkdir(exist_ok=True)
        context.storage_state(path=str(SESSION_FILE))
        browser.close()

    out: dict = {}
    if first["login"]:
        lg = first["login"]
        marker = f"text={scan['logout']}" if scan["logout"] else "table"
        out["login"] = {
            "url": login_url,
            "check_url": report_url,
            "logged_in_selector": marker,
            "steps": [s for s in [
                {"goto": login_url},
                lg["user"] and {"fill": {"selector": lg["user"], "value": "${BAO_CAO_USER}"}},
                {"fill": {"selector": lg["pass"], "value": "${BAO_CAO_PASS}"}},
                lg["submit"] and {"click": lg["submit"]},
                {"wait_ms": 3000},
            ] if s],
        }
    out["jobs"] = [build_job(scan, name, report_url, steps, export_info)]

    text = yaml.safe_dump(out, allow_unicode=True, sort_keys=False, width=120)
    path = STATE_DIR / f"goi_y_{name}.yaml"
    path.write_text("# Gợi ý do 'sync.py inspect' tạo — kiểm tra lại rồi dán vào config.yaml\n" + text,
                    encoding="utf-8")
    print("\n" + "═" * 70 + "\n" + text + "═" * 70)
    print(f"Đã lưu vào {path}")
    print("Việc còn lại: sửa target.sheet_url (link tab Google Sheet có gid=), xem lại key_columns,\n"
          "rồi chạy: python sync.py --dry-run --job " + name)
    return path
