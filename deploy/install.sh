#!/bin/bash
set -e

APP_DIR="/opt/tts-free"
REPO="https://github.com/huyng1801/tts-free.git"

echo "==> Cài dependencies hệ thống..."
apt-get update -qq
apt-get install -y python3 python3-pip python3-venv git nginx ffmpeg

echo "==> Clone / cập nhật mã nguồn..."
if [ -d "$APP_DIR/.git" ]; then
    cd "$APP_DIR"
    git pull origin master
else
    rm -rf "$APP_DIR"
    git clone "$REPO" "$APP_DIR"
    cd "$APP_DIR"
fi

echo "==> Tạo virtual environment..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "==> Tạo thư mục output..."
mkdir -p output
chown -R www-data:www-data "$APP_DIR"

echo "==> Cấu hình systemd..."
cp deploy/tts-free.service /etc/systemd/system/tts-free.service
systemctl daemon-reload
systemctl enable tts-free
systemctl restart tts-free

echo "==> Cấu hình nginx..."
cp deploy/nginx.conf /etc/nginx/sites-available/tts-free
ln -sf /etc/nginx/sites-available/tts-free /etc/nginx/sites-enabled/tts-free
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl restart nginx

echo "==> Hoàn tất!"
echo "Truy cập: http://$(curl -s ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')"
systemctl status tts-free --no-pager
