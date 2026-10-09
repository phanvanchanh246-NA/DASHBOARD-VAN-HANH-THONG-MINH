"""
TRANG BÁO CÁO GIẢ LẬP — để chạy thử sync.py / inspect khi chưa có trang thật.

    python tests/mock_site.py            # mở http://127.0.0.1:8765  (tài khoản demo / demo123)

Có đủ 3 kiểu trang hay gặp:
  /van-hanh/giao-thanh-cong  — có bộ lọc "Hôm nay" + "Tìm kiếm" và nút "Xuất Excel" (file có 2 dòng tiêu đề phụ)
  /van-hanh/tra-hang         — bảng kiểu Ant Design (tiêu đề và thân tách 2 <table>), phân trang 3 trang
  /kpi                       — bảng dựng bằng <div role="grid">
"""
from __future__ import annotations

import io
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from openpyxl import Workbook

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
COOKIE = "sid=demo-session"

GTC = [("09/10/2026", f"BC{i:02d}", str(100 + i * 7), str(95 + i * 6)) for i in range(1, 9)]
TRA_HANG = [(f"DH{1000 + i}", f"BC{i % 5:02d}", "09/10/2026", ["Sai địa chỉ", "Khách từ chối", "Không liên lạc được"][i % 3])
            for i in range(1, 24)]
KPI = [("Tỷ lệ GTC", "97,2%", "95%"), ("Tỷ lệ trả hàng", "2,1%", "3%"), ("Đơn tồn", "134", "150")]

LAYOUT = """<!doctype html><html lang="vi"><head><meta charset="utf-8"><title>{title}</title>
<style>body{{font-family:sans-serif;margin:20px}} td,th{{border:1px solid #ccc;padding:4px 8px}}
.grid-row{{display:flex;gap:16px}} .hidden{{display:none}}</style></head><body>
<header>Xin chào demo · <a href="/logout">Đăng xuất</a> · <a href="/van-hanh/giao-thanh-cong">GTC</a>
· <a href="/van-hanh/tra-hang">Trả hàng</a> · <a href="/kpi">KPI</a></header><h1>{title}</h1>{body}</body></html>"""

LOGIN = """<!doctype html><html lang="vi"><head><meta charset="utf-8"><title>Đăng nhập</title></head><body>
<form method="post" action="/login"><h1>Đăng nhập hệ thống báo cáo</h1>
<input name="username" placeholder="Tên đăng nhập"><input type="password" name="password" placeholder="Mật khẩu">
<button type="submit" class="btn-login">Đăng nhập</button>{err}</form></body></html>"""


def rows_html(rows):
    return "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)


def page_gtc():
    body = f"""
<div class="filters"><button type="button" id="today">Hôm nay</button>
<button type="button" class="ant-btn ant-btn-primary" onclick="document.getElementById('kq').classList.remove('hidden')">
<span>Tìm kiếm</span></button>
<button type="button" class="ant-btn" onclick="location.href='/export/gtc.xlsx'"><span>Xuất Excel</span></button></div>
<div id="kq" class="hidden"><table class="ant-table"><thead><tr><th>Ngày</th><th>Bưu cục</th><th>Tổng đơn</th>
<th>Giao thành công</th></tr></thead><tbody>{rows_html(GTC)}</tbody></table></div>"""
    return LAYOUT.format(title="Giao thành công", body=body)


def page_tra_hang():
    import json
    body = """
<div class="ant-table"><div class="ant-table-header"><table><thead><tr><th>Mã đơn</th><th>Bưu cục</th><th>Ngày</th>
<th>Lý do</th></tr></thead></table></div><div class="ant-table-body"><table><tbody id="tb"></tbody></table></div></div>
<ul class="ant-pagination"><li class="ant-pagination-prev"><a>‹</a></li><li id="pg"></li>
<li class="ant-pagination-next" title="Trang sau"><button type="button">›</button></li></ul>
<script>
const DATA = %s, SIZE = 10; let p = 0;
function draw() {
  const rows = DATA.slice(p * SIZE, (p + 1) * SIZE);
  document.getElementById('tb').innerHTML = '<tr class="ant-table-measure-row"><td></td><td></td><td></td><td></td></tr>' +
    rows.map(r => '<tr class="ant-table-row">' + r.map(c => '<td>' + c + '</td>').join('') + '</tr>').join('');
  document.getElementById('pg').textContent = (p + 1) + '/' + Math.ceil(DATA.length / SIZE);
  const last = (p + 1) * SIZE >= DATA.length, nx = document.querySelector('.ant-pagination-next');
  nx.setAttribute('aria-disabled', last); nx.classList.toggle('ant-pagination-disabled', last);
}
document.querySelector('.ant-pagination-next').onclick = () => { if ((p + 1) * SIZE < DATA.length) { p++; setTimeout(draw, 300); } };
draw();
</script>""" % json.dumps(TRA_HANG, ensure_ascii=False)
    return LAYOUT.format(title="Trả hàng", body=body)


def page_kpi():
    head = '<div class="grid-row grid-header" role="row">' + "".join(
        f'<div class="grid-cell" role="columnheader">{h}</div>' for h in ("Chỉ tiêu", "Thực tế", "Mục tiêu")) + "</div>"
    rows = "".join('<div class="grid-row" role="row">' + "".join(
        f'<div class="grid-cell" role="gridcell">{c}</div>' for c in r) + "</div>" for r in KPI)
    return LAYOUT.format(title="KPI", body=f'<div role="grid">{head}{rows}</div>')


def xlsx_gtc() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "GTC"
    ws.append(["BÁO CÁO GIAO THÀNH CÔNG"])
    ws.append(["Ngày xuất: 09/10/2026"])
    ws.append(["Ngày", "Bưu cục", "Tổng đơn", "Giao thành công"])
    for r in GTC:
        ws.append(list(r))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code=200, body=b"", ctype="text/html; charset=utf-8", headers=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body if isinstance(body, bytes) else body.encode("utf-8"))

    def authed(self):
        return COOKIE in (self.headers.get("Cookie") or "")

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/login":
            return self.send(body=LOGIN.format(err=""))
        if path == "/logout":
            return self.send(302, headers={"Location": "/login", "Set-Cookie": "sid=; Max-Age=0; Path=/"})
        if not self.authed():
            return self.send(302, headers={"Location": "/login"})
        pages = {"/": page_gtc, "/dashboard": page_gtc, "/van-hanh/giao-thanh-cong": page_gtc,
                 "/van-hanh/tra-hang": page_tra_hang, "/kpi": page_kpi}
        if path in pages:
            return self.send(body=pages[path]())
        if path == "/export/gtc.xlsx":
            return self.send(body=xlsx_gtc(),
                             ctype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": 'attachment; filename="BaoCao_GTC.xlsx"'})
        self.send(404, body="Không có trang")

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        form = parse_qs(self.rfile.read(n).decode("utf-8"))
        if form.get("username") == ["demo"] and form.get("password") == ["demo123"]:
            return self.send(302, headers={"Location": "/dashboard", "Set-Cookie": f"{COOKIE}; Path=/"})
        self.send(body=LOGIN.format(err="<p>Sai tài khoản</p>"))


if __name__ == "__main__":
    print(f"Trang giả lập: http://127.0.0.1:{PORT}  (demo / demo123)")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
