import asyncio
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

import edge_tts

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

CHUNK_SIZE = 3500
MAX_RETRIES = 3
RETRY_DELAY = 2


def get_ffmpeg() -> str:
    for candidate in (shutil.which("ffmpeg"), "/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg"):
        if candidate and Path(candidate).exists():
            return candidate
    raise FileNotFoundError("ffmpeg không tìm thấy. Cài đặt: apt install ffmpeg")


def sanitize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Emoji và ký tự trang trí hay gây lỗi edge-tts
    text = re.sub(
        r"[\U0001F300-\U0001FAFF\U00002700-\U000027BF\U0000FE00-\U0000FE0F\U0000200D]",
        "",
        text,
    )
    return text.strip()


def _split_long_block(block: str) -> list[str]:
    if len(block) <= CHUNK_SIZE:
        return [block]

    parts: list[str] = []
    sentences = re.split(r"(?<=[.!?…:;])\s+", block)
    current = ""

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        if len(sentence) > CHUNK_SIZE:
            if current:
                parts.append(current)
                current = ""
            for i in range(0, len(sentence), CHUNK_SIZE):
                parts.append(sentence[i : i + CHUNK_SIZE])
            continue
        if not current:
            current = sentence
        elif len(current) + 1 + len(sentence) <= CHUNK_SIZE:
            current = f"{current} {sentence}"
        else:
            parts.append(current)
            current = sentence

    if current:
        parts.append(current)
    return parts


def split_text(text: str) -> list[str]:
    text = sanitize_text(text)
    if not text:
        return []
    if len(text) <= CHUNK_SIZE:
        return [text]

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paragraphs:
        return _split_long_block(text)

    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        if len(para) > CHUNK_SIZE:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(_split_long_block(para))
            continue

        if not current:
            current = para
        elif len(current) + 2 + len(para) <= CHUNK_SIZE:
            current = f"{current}\n\n{para}"
        else:
            chunks.append(current)
            current = para

    if current:
        chunks.append(current)

    return [c for c in chunks if c.strip()]


async def list_voices(locale: str | None = None) -> list[dict]:
    voices = await edge_tts.list_voices()
    result = []
    for v in voices:
        if locale and not v["Locale"].lower().startswith(locale.lower()):
            continue
        result.append(
            {
                "name": v["ShortName"],
                "locale": v["Locale"],
                "gender": v["Gender"],
                "friendly": v["FriendlyName"],
            }
        )
    result.sort(key=lambda x: (x["locale"], x["name"]))
    return result


async def synthesize_chunk(
    text: str,
    voice: str,
    rate: str,
    pitch: str,
    volume: str,
    output_path: Path,
) -> None:
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch, volume=volume)
            await communicate.save(str(output_path))
            if output_path.stat().st_size < 100:
                raise RuntimeError("File audio rỗng")
            return
        except Exception as e:
            last_error = e
            output_path.unlink(missing_ok=True)
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY * attempt)
    raise RuntimeError(
        f"Không tạo được audio sau {MAX_RETRIES} lần thử. "
        f"Chi tiết: {last_error}"
    )


def merge_audio_files(files: list[Path], output_path: Path) -> None:
    if len(files) == 1:
        files[0].rename(output_path)
        return

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        for fp in files:
            escaped = str(fp.resolve()).replace("'", "'\\''")
            f.write(f"file '{escaped}'\n")
        list_path = f.name

    try:
        result = subprocess.run(
            [
                get_ffmpeg(),
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                list_path,
                "-c",
                "copy",
                str(output_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Ghép audio thất bại: {e.stderr or e}") from e
    finally:
        Path(list_path).unlink(missing_ok=True)
        for fp in files:
            fp.unlink(missing_ok=True)


async def generate_speech(
    text: str,
    voice: str,
    rate: str = "+0%",
    pitch: str = "+0Hz",
    volume: str = "+0%",
    progress_callback=None,
) -> dict:
    job_id = uuid.uuid4().hex[:12]
    chunks = split_text(text)
    if not chunks:
        raise ValueError("Văn bản trống sau khi xử lý")

    job_dir = OUTPUT_DIR / job_id
    job_dir.mkdir(exist_ok=True)
    chunk_files: list[Path] = []

    total = len(chunks)
    for i, chunk in enumerate(chunks):
        chunk_path = job_dir / f"part_{i:04d}.mp3"
        await synthesize_chunk(chunk, voice, rate, pitch, volume, chunk_path)
        chunk_files.append(chunk_path)
        if progress_callback:
            progress_callback(i + 1, total)
        if i < total - 1:
            await asyncio.sleep(0.5)

    final_path = OUTPUT_DIR / f"{job_id}.mp3"
    merge_audio_files(chunk_files, final_path)

    for fp in job_dir.iterdir():
        fp.unlink(missing_ok=True)
    job_dir.rmdir()

    return {
        "job_id": job_id,
        "filename": f"{job_id}.mp3",
        "chunks": total,
        "size": final_path.stat().st_size,
    }


def run_generate(text, voice, rate, pitch, volume, progress_callback=None):
    return asyncio.run(
        generate_speech(text, voice, rate, pitch, volume, progress_callback)
    )


def run_list_voices(locale=None):
    return asyncio.run(list_voices(locale))
