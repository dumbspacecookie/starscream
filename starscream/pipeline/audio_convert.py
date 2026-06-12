"""Convert uploaded audio to FLAC originals and optional 192kbps MP3 proxies."""

from __future__ import annotations

import io
import logging
import shutil
import subprocess
from dataclasses import dataclass

import soundfile as sf

logger = logging.getLogger(__name__)

MP3_BITRATE = "192k"

_SUBTYPE_BIT_DEPTH = {
    "PCM_16": 16,
    "PCM_24": 24,
    "PCM_32": 32,
    "PCM_U8": 8,
    "FLOAT": 32,
    "DOUBLE": 64,
}


@dataclass(frozen=True)
class AudioMetadata:
    sample_rate: int
    channels: int
    bit_depth: int | None
    duration: float


def is_mp3(audio_bytes: bytes) -> bool:
    if len(audio_bytes) < 2:
        return False
    return audio_bytes[:3] == b"ID3" or audio_bytes[:2] == b"\xff\xfb"


def _subtype_bit_depth(subtype: str) -> int | None:
    return _SUBTYPE_BIT_DEPTH.get(subtype.upper().replace(" ", "_"))


def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _encode_mp3_from_bytes(audio_bytes: bytes, *, input_format: str | None = None) -> bytes | None:
    """Re-encode audio bytes to 192kbps MP3 via ffmpeg; returns None if ffmpeg unavailable."""
    if not _ffmpeg_available():
        return None

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
    ]
    if input_format:
        cmd.extend(["-f", input_format])
    cmd.extend(
        [
            "-i",
            "pipe:0",
            "-codec:a",
            "libmp3lame",
            "-b:a",
            MP3_BITRATE,
            "-f",
            "mp3",
            "pipe:1",
        ]
    )

    try:
        proc = subprocess.run(
            cmd,
            input=audio_bytes,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        logger.debug("ffmpeg mp3 encode failed: %s", exc)
        return None

    if proc.returncode != 0 or not proc.stdout:
        logger.debug(
            "ffmpeg mp3 encode failed (code=%s): %s",
            proc.returncode,
            proc.stderr.decode(errors="replace")[:200],
        )
        return None
    return proc.stdout


def reencode_mp3_proxy(mp3_bytes: bytes) -> bytes | None:
    """Normalize an existing MP3 preview to 192kbps when ffmpeg is available."""
    return _encode_mp3_from_bytes(mp3_bytes)


def normalize_upload(
    audio_bytes: bytes,
    filename: str,
) -> tuple[bytes, bytes | None, AudioMetadata]:
    """Convert a lossless upload to FLAC and optional 192kbps MP3 proxy."""
    del filename  # reserved for future format hints / logging

    source = io.BytesIO(audio_bytes)
    info = sf.info(source)
    source.seek(0)
    data, sample_rate = sf.read(source, dtype="float64", always_2d=True)

    flac_buf = io.BytesIO()
    sf.write(flac_buf, data, sample_rate, format="FLAC")
    flac_bytes = flac_buf.getvalue()

    mp3_bytes = _encode_mp3_from_bytes(flac_bytes, input_format="flac")

    channels = info.channels
    duration = float(info.duration)
    if duration <= 0 and sample_rate:
        duration = data.shape[0] / sample_rate

    metadata = AudioMetadata(
        sample_rate=int(sample_rate),
        channels=int(channels),
        bit_depth=_subtype_bit_depth(info.subtype),
        duration=duration,
    )
    return flac_bytes, mp3_bytes, metadata


def flac_header_valid(flac_bytes: bytes) -> bool:
    return flac_bytes.startswith(b"fLaC")


def mp3_header_valid(mp3_bytes: bytes) -> bool:
    return is_mp3(mp3_bytes)
