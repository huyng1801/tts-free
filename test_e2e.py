"""End-to-end test suite for TTS Free deployed app."""
import json
import sys
import time
import urllib.error
import urllib.request

BASE = "http://103.72.97.87:8888"
TIMEOUT = 30
TTS_TIMEOUT = 180

passed = 0
failed = 0
results = []


def test(name, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        results.append(f"  PASS  {name}" + (f" — {detail}" if detail else ""))
    else:
        failed += 1
        results.append(f"  FAIL  {name}" + (f" — {detail}" if detail else ""))


def fetch(url, method="GET", data=None, headers=None, timeout=TIMEOUT):
    req = urllib.request.Request(url, method=method, headers=headers or {})
    if data is not None:
        req.data = data
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read()
        return resp.status, resp.headers, body


def main():
    print(f"\n=== E2E Test: {BASE} ===\n")

    # 1. Health
    try:
        status, _, body = fetch(f"{BASE}/health")
        data = json.loads(body)
        test("Health check", status == 200 and data.get("status") == "ok", str(data))
    except Exception as e:
        test("Health check", False, str(e))

    # 2. Homepage
    try:
        status, headers, body = fetch(f"{BASE}/")
        html = body.decode("utf-8")
        checks = [
            "TTS Free" in html,
            "textInput" in html,
            "voiceSelect" in html,
            "generateBtn" in html,
            "audioPlayer" in html,
            "downloadBtn" in html,
            "rateSlider" in html,
            "pitchSlider" in html,
            "volumeSlider" in html,
        ]
        test("Homepage HTML", status == 200 and all(checks), f"{sum(checks)}/{len(checks)} elements")
    except Exception as e:
        test("Homepage HTML", False, str(e))

    # 3. Static assets
    for path in ["/static/css/style.css", "/static/js/app.js"]:
        try:
            status, _, body = fetch(f"{BASE}{path}")
            test(f"Static {path}", status == 200 and len(body) > 100, f"{len(body)} bytes")
        except Exception as e:
            test(f"Static {path}", False, str(e))

    # 4. Voices API
    try:
        status, _, body = fetch(f"{BASE}/api/voices?locale=vi")
        data = json.loads(body)
        voices = data.get("voices", [])
        names = [v["name"] for v in voices]
        has_hoai_my = "vi-VN-HoaiMyNeural" in names
        has_nam_minh = "vi-VN-NamMinhNeural" in names
        test(
            "Voices API (vi)",
            data.get("ok") and len(voices) >= 2 and has_hoai_my and has_nam_minh,
            f"{len(voices)} voices",
        )
    except Exception as e:
        test("Voices API (vi)", False, str(e))

    # 5. Empty text error
    try:
        payload = json.dumps({"text": "", "voice": "vi-VN-HoaiMyNeural"}).encode()
        req = urllib.request.Request(
            f"{BASE}/api/tts",
            data=payload,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            urllib.request.urlopen(req, timeout=TIMEOUT)
            test("Empty text validation", False, "Should return 400")
        except urllib.error.HTTPError as e:
            body = json.loads(e.read())
            test("Empty text validation", e.code == 400 and not body.get("ok"), f"HTTP {e.code}")
    except Exception as e:
        test("Empty text validation", False, str(e))

    # 6. TTS generation — short text
    job_id = None
    try:
        payload = json.dumps(
            {
                "text": "Xin chào. Đây là bài test truyện audio TTS Free.",
                "voice": "vi-VN-HoaiMyNeural",
                "rate": "+0%",
                "pitch": "+0Hz",
                "volume": "+0%",
            }
        ).encode()
        status, _, body = fetch(f"{BASE}/api/tts", method="POST", data=payload)
        data = json.loads(body)
        job_id = data.get("job_id")
        test("TTS create job", data.get("ok") and job_id, f"job_id={job_id}")
    except Exception as e:
        test("TTS create job", False, str(e))

    # 7. Poll until done
    if job_id:
        done = False
        error = None
        result = None
        start = time.time()
        try:
            while time.time() - start < TTS_TIMEOUT:
                status, _, body = fetch(f"{BASE}/api/tts/{job_id}/status")
                data = json.loads(body)
                if data.get("status") == "done":
                    done = True
                    result = data.get("result")
                    break
                if data.get("status") == "error":
                    error = data.get("error")
                    break
                time.sleep(1)
            test(
                "TTS job completion",
                done and result,
                f"{result.get('chunks')} chunks, {result.get('size')} bytes" if result else error or "timeout",
            )
        except Exception as e:
            test("TTS job completion", False, str(e))

        # 8. Audio stream
        if done:
            try:
                status, headers, body = fetch(f"{BASE}/api/tts/{job_id}/audio", timeout=60)
                is_mp3 = body[:3] == b"ID3" or body[:2] == b"\xff\xfb" or body[:2] == b"\xff\xf3"
                test(
                    "Audio playback endpoint",
                    status == 200 and len(body) > 1000 and is_mp3,
                    f"{len(body)} bytes, content-type={headers.get('Content-Type')}",
                )
            except Exception as e:
                test("Audio playback endpoint", False, str(e))

            # 9. Download
            try:
                status, headers, body = fetch(f"{BASE}/api/tts/{job_id}/download", timeout=60)
                is_mp3 = body[:3] == b"ID3" or body[:2] == b"\xff\xfb" or body[:2] == b"\xff\xf3"
                test(
                    "Audio download endpoint",
                    status == 200 and len(body) > 1000 and is_mp3,
                    f"{len(body)} bytes",
                )
            except Exception as e:
                test("Audio download endpoint", False, str(e))

    # 10. Long text chunking
    job_id2 = None
    try:
        long_text = ("Đoạn truyện số một. " * 300).strip()  # ~6000 chars
        payload = json.dumps(
            {
                "text": long_text,
                "voice": "vi-VN-NamMinhNeural",
                "rate": "-10%",
                "pitch": "+2Hz",
                "volume": "+5%",
            }
        ).encode()
        status, _, body = fetch(f"{BASE}/api/tts", method="POST", data=payload, timeout=60)
        data = json.loads(body)
        job_id2 = data.get("job_id")
        test("Long text job create", data.get("ok") and job_id2, f"{len(long_text)} chars")
    except Exception as e:
        test("Long text job create", False, str(e))

    if job_id2:
        done2 = False
        chunks = 0
        start = time.time()
        try:
            while time.time() - start < TTS_TIMEOUT:
                status, _, body = fetch(f"{BASE}/api/tts/{job_id2}/status")
                data = json.loads(body)
                if data.get("total"):
                    chunks = data["total"]
                if data.get("status") == "done":
                    done2 = True
                    break
                if data.get("status") == "error":
                    test("Long text chunking", False, data.get("error"))
                    break
                time.sleep(2)
            if done2:
                test("Long text chunking", chunks >= 2, f"{chunks} chunks merged")
            elif not done2:
                test("Long text chunking", False, "timeout")
        except Exception as e:
            test("Long text chunking", False, str(e))

    # 11. Invalid job
    try:
        req = urllib.request.Request(f"{BASE}/api/tts/invalid_job/status")
        try:
            urllib.request.urlopen(req, timeout=TIMEOUT)
            test("Invalid job 404", False, "Should return 404")
        except urllib.error.HTTPError as e:
            test("Invalid job 404", e.code == 404, f"HTTP {e.code}")
    except Exception as e:
        test("Invalid job 404", False, str(e))

    print("\n".join(results))
    print(f"\n=== Kết quả: {passed} passed, {failed} failed ===\n")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
