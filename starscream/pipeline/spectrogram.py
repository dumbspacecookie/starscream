"""Mel spectrogram PNG generation for recording previews."""

from __future__ import annotations

import io

import librosa
import numpy as np
from PIL import Image

SPECTROGRAM_WIDTH = 800
SPECTROGRAM_HEIGHT = 400


def generate_spectrogram(audio_bytes: bytes) -> bytes:
    """Render a log-mel spectrogram as an 800x400 PNG."""
    y, sr = librosa.load(io.BytesIO(audio_bytes), sr=22050, mono=True)
    if len(y) == 0:
        y = np.zeros(2205, dtype=np.float32)

    mel = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=128)
    log_mel = librosa.power_to_db(mel, ref=np.max)

    log_mel = log_mel - log_mel.min()
    peak = log_mel.max()
    if peak > 0:
        log_mel = log_mel / peak

    img_array = (log_mel * 255).astype(np.uint8).T
    img = Image.fromarray(img_array, mode="L")
    img = img.resize((SPECTROGRAM_WIDTH, SPECTROGRAM_HEIGHT), Image.Resampling.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
