import hashlib
import io

import numpy as np

from starscream.pipeline.metrics import record_fingerprint_fallback


def compute_spectral_hash(audio_bytes: bytes | None) -> str:
    """MFCC mean fingerprint → SHA-256. Placeholder hash when no audio."""
    if not audio_bytes:
        return hashlib.sha256(b"no-audio").hexdigest()

    try:
        import librosa

        y, sr = librosa.load(io.BytesIO(audio_bytes), sr=22050, mono=True)
        if len(y) == 0:
            return hashlib.sha256(b"empty-audio").hexdigest()
        mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=20)
        mean = np.mean(mfcc, axis=1)
        payload = mean.astype(np.float32).tobytes()
        return hashlib.sha256(payload).hexdigest()
    except Exception as exc:
        record_fingerprint_fallback(exc)
        if audio_bytes:
            return hashlib.sha256(audio_bytes[:4096]).hexdigest()
        return hashlib.sha256(b"no-audio").hexdigest()
