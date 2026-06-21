import asyncio
import re
import subprocess
import tempfile
import uuid
from pathlib import Path

import edge_tts

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

CHUNK_SIZE = 4000


def split_text(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= CHUNK_SIZE:
        return [text]

    chunks: list[str] = []
    paragraphs = re.split(r"\n\s*\n", text)

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(para) <= CHUNK_SIZE:
            chunks.append(para)
            continue

        sentences = re.split(r"(?<=[.!?…])\s+", para)
        current = ""
        for sentence in sentences:
            if len(current) + len(sentence) + 1 <= CHUNK_SIZE:
                current = f"{current} {sentence}".strip() if current else sentence
            else:
                if current:
                    chunks.append(current)
                if len(sentence) <= CHUNK_SIZE:
                    current = sentence
                else:
                    for i in range(0, len(sentence), CHUNK_SIZE):
                        chunks.append(sentence[i : i + CHUNK_SIZE])
                    current = ""
        if current:
            chunks.append(current)

    return chunks


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
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch, volume=volume)
    await communicate.save(str(output_path))


def merge_audio_files(files: list[Path], output_path: Path) -> None:
    if len(files) == 1:
        files[0].rename(output_path)
        return

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        for fp in files:
            escaped = str(fp.resolve()).replace("'", "'\\''")
            f.write(f"file '{escaped}'\n")
        list_path = f.name

    try:
        subprocess.run(
            [
                "ffmpeg",
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
        )
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
        raise ValueError("Văn bản trống")

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
