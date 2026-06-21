import json
import threading
import time
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file

from tts_engine import OUTPUT_DIR, run_generate, run_list_voices

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024

JOBS_DIR = OUTPUT_DIR / "jobs"
JOBS_DIR.mkdir(parents=True, exist_ok=True)
jobs_lock = threading.Lock()


def _job_path(job_id: str) -> Path:
    safe_id = job_id.replace("/", "").replace("..", "")
    return JOBS_DIR / f"{safe_id}.json"


def save_job(job_id: str, data: dict) -> None:
    with jobs_lock:
        _job_path(job_id).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def load_job(job_id: str) -> dict | None:
    path = _job_path(job_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def update_job(job_id: str, **fields) -> None:
    with jobs_lock:
        path = _job_path(job_id)
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        data.update(fields)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/voices")
def api_voices():
    locale = request.args.get("locale", "")
    try:
        voices = run_list_voices(locale or None)
        return jsonify({"ok": True, "voices": voices})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/tts", methods=["POST"])
def api_tts():
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    voice = data.get("voice", "vi-VN-HoaiMyNeural")
    rate = data.get("rate", "+0%")
    pitch = data.get("pitch", "+0Hz")
    volume = data.get("volume", "+0%")

    if not text:
        return jsonify({"ok": False, "error": "Vui lòng nhập nội dung truyện"}), 400

    job_id = f"job_{int(time.time() * 1000)}"
    save_job(
        job_id,
        {
            "status": "processing",
            "progress": 0,
            "total": 0,
            "error": None,
            "result": None,
        },
    )

    def worker():
        def on_progress(current, total):
            update_job(job_id, progress=current, total=total)

        try:
            result = run_generate(text, voice, rate, pitch, volume, on_progress)
            update_job(job_id, status="done", result=result)
        except Exception as e:
            update_job(job_id, status="error", error=str(e))

    threading.Thread(target=worker, daemon=True).start()
    return jsonify({"ok": True, "job_id": job_id})


@app.route("/api/tts/<job_id>/status")
def api_tts_status(job_id):
    job = load_job(job_id)
    if not job:
        return jsonify({"ok": False, "error": "Job không tồn tại"}), 404
    return jsonify({"ok": True, **job})


@app.route("/api/tts/<job_id>/audio")
def api_tts_audio(job_id):
    job = load_job(job_id)
    if not job or job["status"] != "done":
        return jsonify({"ok": False, "error": "Audio chưa sẵn sàng"}), 404

    filename = job["result"]["filename"]
    filepath = OUTPUT_DIR / filename
    if not filepath.exists():
        return jsonify({"ok": False, "error": "File không tồn tại"}), 404

    return send_file(filepath, mimetype="audio/mpeg", as_attachment=False)


@app.route("/api/tts/<job_id>/download")
def api_tts_download(job_id):
    job = load_job(job_id)
    if not job or job["status"] != "done":
        return jsonify({"ok": False, "error": "Audio chưa sẵn sàng"}), 404

    filename = job["result"]["filename"]
    filepath = OUTPUT_DIR / filename
    if not filepath.exists():
        return jsonify({"ok": False, "error": "File không tồn tại"}), 404

    return send_file(
        filepath,
        mimetype="audio/mpeg",
        as_attachment=True,
        download_name="truyen-audio.mp3",
    )


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    Path("output").mkdir(exist_ok=True)
    app.run(host="0.0.0.0", port=5000, debug=True)
