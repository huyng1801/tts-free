# TTS Free

Trình chuyển văn bản thành giọng nói (Text-to-Speech) miễn phí, không giới hạn ký tự — tối ưu cho làm truyện audio trên điện thoại.

## Tính năng

- **Không giới hạn ký tự** — tự động chia đoạn và ghép audio
- **Edge TTS** — giọng đọc tự nhiên, hỗ trợ tiếng Việt
- **Giao diện mobile-first** — thiết kế tối ưu cho điện thoại
- **Tùy chỉnh** — tốc độ, cao độ, âm lượng
- **Nghe & tải MP3** — phát trực tiếp hoặc tải về

## Cài đặt local

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Cần ffmpeg để ghép audio dài
# Ubuntu: sudo apt install ffmpeg
# Windows: choco install ffmpeg

python app.py
```

Mở http://localhost:5000 trên trình duyệt điện thoại (cùng mạng WiFi).

## Deploy production

```bash
chmod +x deploy/install.sh
sudo ./deploy/install.sh
```

## Stack

- Python 3.10+
- Flask + Gunicorn
- edge-tts
- ffmpeg (ghép audio)

## License

MIT
