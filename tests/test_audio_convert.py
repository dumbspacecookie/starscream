import io

import numpy as np
import pytest
import soundfile as sf

from starscream.pipeline.audio_convert import (
    AudioMetadata,
    flac_header_valid,
    is_mp3,
    mp3_header_valid,
    normalize_upload,
    reencode_mp3_proxy,
)


def _make_wav_bytes(duration_s: float = 0.5, sr: int = 48000, channels: int = 1) -> bytes:
    samples = int(sr * duration_s)
    t = np.linspace(0, duration_s, samples, endpoint=False)
    if channels == 1:
        audio = 0.1 * np.sin(2 * np.pi * 440 * t)
    else:
        left = 0.1 * np.sin(2 * np.pi * 440 * t)
        right = 0.1 * np.sin(2 * np.pi * 880 * t)
        audio = np.column_stack([left, right])
    buf = io.BytesIO()
    sf.write(buf, audio, sr, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def test_normalize_upload_produces_valid_flac():
    wav = _make_wav_bytes(duration_s=0.5, sr=48000)
    flac_bytes, mp3_bytes, meta = normalize_upload(wav, "clip.wav")

    assert flac_header_valid(flac_bytes)
    assert isinstance(meta, AudioMetadata)
    assert meta.sample_rate == 48000
    assert meta.channels == 1
    assert meta.bit_depth == 16
    assert meta.duration == pytest.approx(0.5, abs=0.05)

    info = sf.info(io.BytesIO(flac_bytes))
    assert info.format == "FLAC"
    assert info.samplerate == 48000

    if mp3_bytes is not None:
        assert mp3_header_valid(mp3_bytes)


def test_normalize_upload_stereo():
    wav = _make_wav_bytes(duration_s=0.25, sr=44100, channels=2)
    flac_bytes, _, meta = normalize_upload(wav, "stereo.wav")

    assert flac_header_valid(flac_bytes)
    assert meta.channels == 2
    assert meta.sample_rate == 44100


def test_is_mp3_detects_headers():
    assert not is_mp3(_make_wav_bytes())
    assert is_mp3(b"ID3" + b"\x00" * 10)
    assert is_mp3(b"\xff\xfb\x90" + b"\x00" * 10)


def test_reencode_mp3_proxy_returns_bytes_or_none():
    fake_mp3 = b"ID3" + b"\x00" * 64
    result = reencode_mp3_proxy(fake_mp3)
    assert result is None or mp3_header_valid(result)
