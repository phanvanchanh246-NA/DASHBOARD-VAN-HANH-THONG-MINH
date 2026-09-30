#!/usr/bin/env bash
# Cài đặt trên VPS Ubuntu/Debian:  bash install.sh
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
RUN_USER="${SUDO_USER:-$(whoami)}"
cd "$DIR"

echo "==> Cài Python"
sudo apt-get update -y
sudo apt-get install -y python3 python3-venv python3-pip

echo "==> Tạo môi trường ảo và cài thư viện"
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

echo "==> Cài Chromium cho Playwright"
sudo "$DIR/.venv/bin/python" -m playwright install-deps chromium
sudo -u "$RUN_USER" "$DIR/.venv/bin/python" -m playwright install chromium

[ -f config.yaml ] || { cp config.example.yaml config.yaml; echo "   đã tạo config.yaml — hãy sửa lại"; }
[ -f .env ] || { cp .env.example .env; chmod 600 .env; echo "   đã tạo .env — hãy điền mật khẩu"; }
chown "$RUN_USER" config.yaml .env 2>/dev/null || true

echo "==> Cài lịch chạy tự động (systemd timer)"
for f in bao-cao-sync.service bao-cao-sync.timer; do
  sed -e "s#__DIR__#$DIR#g" -e "s#__USER__#$RUN_USER#g" "systemd/$f" | sudo tee "/etc/systemd/system/$f" >/dev/null
done
sudo systemctl daemon-reload
sudo systemctl enable --now bao-cao-sync.timer

cat <<MSG

Xong. Các bước tiếp theo:
  1. Sửa $DIR/config.yaml và $DIR/.env
  2. Đặt file service account vào $DIR/credentials.json
  3. Chạy thử (không ghi Sheet):  cd $DIR && set -a && . ./.env && set +a && .venv/bin/python sync.py --dry-run
  4. Chạy thật một lần:           sudo systemctl start bao-cao-sync.service
  5. Xem nhật ký:                 journalctl -u bao-cao-sync -n 100 --no-pager
  6. Xem lịch chạy kế tiếp:       systemctl list-timers bao-cao-sync.timer
MSG
