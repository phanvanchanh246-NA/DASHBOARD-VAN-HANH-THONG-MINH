# Đồng bộ báo cáo công ty → Google Sheets (chạy trên VPS)

Công cụ này chạy trên VPS theo lịch (mặc định 7h05, 12h05, 17h05, 22h05 giờ Việt Nam):

1. Mở trình duyệt ẩn, **đăng nhập trang báo cáo công ty** (lưu phiên để lần sau không phải đăng nhập lại).
2. Lấy dữ liệu theo 2 cách:
   - `kind: download` — trang **có nút Xuất Excel/CSV**: tự bấm nút, đọc file tải về.
   - `kind: table` — trang **không xuất được, phải bôi đen + copy**: tự đọc bảng đang hiển thị (tự bấm "Trang sau" nếu có nhiều trang).
3. **Nối thêm dòng mới** vào tab Google Sheet của bạn (chính các link đang dùng trong `app.py`), dòng đã có thì bỏ qua → dashboard tự hiện số mới.

```
Trang báo cáo công ty ──(VPS: Chromium ẩn)──► Google Sheet của bạn ──► Dashboard (app.py)
```

---

## 1. Chuẩn bị VPS

VPS Ubuntu 22.04/24.04, tối thiểu 1 CPU / 2 GB RAM (Chromium cần RAM). VPS phải truy cập được
trang báo cáo công ty — nếu trang chỉ vào được bằng mạng nội bộ/VPN công ty thì VPS cũng phải nằm trong mạng đó.

```bash
git clone https://github.com/phanvanchanh246-NA/DASHBOARD-VAN-HANH-THONG-MINH.git
cd DASHBOARD-VAN-HANH-THONG-MINH/vps_sync
bash install.sh
```

`install.sh` cài Python, thư viện, Chromium, tạo `config.yaml` + `.env` và bật lịch chạy tự động.

## 2. Cho phép VPS ghi vào Google Sheet (service account)

1. Vào <https://console.cloud.google.com> → tạo project (hoặc dùng project có sẵn).
2. **APIs & Services → Library** → bật **Google Sheets API** và **Google Drive API**.
3. **IAM & Admin → Service Accounts → Create** → vào tài khoản vừa tạo → **Keys → Add key → JSON** → tải file về.
4. Đổi tên file thành `credentials.json`, chép lên VPS vào thư mục `vps_sync/`:
   ```bash
   scp credentials.json ubuntu@IP_VPS:~/DASHBOARD-VAN-HANH-THONG-MINH/vps_sync/
   ```
5. Mở file JSON, copy email dạng `...@....iam.gserviceaccount.com`, rồi mở **từng Google Sheet đích**
   → **Chia sẻ** → dán email đó → quyền **Người chỉnh sửa**.

## 3. Điền mật khẩu và cấu hình

`nano .env` — điền tài khoản trang báo cáo:

```
BAO_CAO_USER=ten_dang_nhap
BAO_CAO_PASS=mat_khau
GOOGLE_CREDENTIALS=/home/ubuntu/DASHBOARD-VAN-HANH-THONG-MINH/vps_sync/credentials.json
```

`nano config.yaml` — khai trang đăng nhập và từng báo cáo (xem chú thích trong file). Mỗi báo cáo là 1 `job`:

| Mục | Ý nghĩa |
|---|---|
| `steps` | Các thao tác trước khi lấy dữ liệu: mở trang, chọn ngày, bấm Tìm kiếm… |
| `download_click` | (download) nút Xuất file |
| `table.selector` / `table.next_selector` | (table) bảng cần đọc / nút trang sau |
| `columns` | Chỉ lấy các cột này (bỏ trống = lấy hết) |
| `key_columns` | Cột xác định 1 dòng là duy nhất, VD `["Mã đơn"]`. Bỏ trống = so toàn bộ dòng |
| `add_timestamp_column` | Thêm cột ghi thời điểm lấy dữ liệu |
| `target.sheet_url` | Link tab Google Sheet đích (có `gid=`), copy từ `app.py` |

### Tìm "selector" cho nút bấm / bảng

Trên **máy tính cá nhân** (có màn hình):

```bash
pip install playwright && playwright install chromium
playwright codegen https://dia-chi-trang-bao-cao
```

Đăng nhập và bấm thử như bình thường — cửa sổ bên cạnh sẽ hiện code như
`page.get_by_role("button", name="Xuất Excel").click()` hoặc `page.locator("#btnExport").click()`.
Trong config dùng dạng chữ tương ứng: `"button:has-text('Xuất Excel')"` hoặc `"#btnExport"`.

## 4. Chạy thử

```bash
cd ~/DASHBOARD-VAN-HANH-THONG-MINH/vps_sync
set -a && . ./.env && set +a
.venv/bin/python sync.py --dry-run            # chỉ in dữ liệu lấy được, KHÔNG ghi Sheet
.venv/bin/python sync.py --dry-run --job tra_hang
.venv/bin/python sync.py                      # chạy thật
```

Job bị lỗi sẽ có ảnh chụp màn hình tại `downloads/loi_<tên job>.png` để xem trang đang hiển thị gì.

## 5. Chạy tự động

```bash
systemctl list-timers bao-cao-sync.timer          # xem lần chạy kế tiếp
sudo systemctl start bao-cao-sync.service         # chạy ngay 1 lần
journalctl -u bao-cao-sync -n 100 --no-pager      # xem nhật ký
```

Đổi giờ chạy: sửa các dòng `OnCalendar=` trong `/etc/systemd/system/bao-cao-sync.timer`
rồi `sudo systemctl daemon-reload`.

Báo lỗi qua Telegram: điền `TELEGRAM_TOKEN` và `TELEGRAM_CHAT_ID` trong `.env` (dùng chung bot với dashboard).

## 6. Trang có OTP / captcha

Không tự đăng nhập được bằng mật khẩu. Khi đó:

1. Trong `config.yaml` xóa phần `login.steps` (giữ `check_url` và `logged_in_selector`).
2. Trên máy có màn hình: `python sync.py login --headed` → đăng nhập tay → Enter.
3. Chép `state/session.json` lên VPS vào `vps_sync/state/`.

Khi phiên hết hạn, tool sẽ báo lỗi (và gửi Telegram) để bạn đăng nhập lại.

## Lưu ý

- Chỉ dùng với tài khoản và dữ liệu bạn được công ty cho phép truy cập; nên hỏi IT trước khi tự động hóa.
- `config.yaml`, `.env`, `credentials.json`, `state/` đã được đưa vào `.gitignore` — **không commit** các file này.
- Dòng đã ghi được nhớ trong `state/seen_<job>.json`; xóa file này nếu muốn ghi lại từ đầu.
