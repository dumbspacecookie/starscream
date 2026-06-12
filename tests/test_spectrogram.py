import io
import uuid
from unittest.mock import MagicMock, patch

import numpy as np
import soundfile as sf
from PIL import Image

from starscream.pipeline.spectrogram import (
    SPECTROGRAM_HEIGHT,
    SPECTROGRAM_WIDTH,
    generate_spectrogram,
)


def _make_wav_bytes(duration_s: float = 0.5, sr: int = 48000) -> bytes:
    t = np.linspace(0, duration_s, int(sr * duration_s), endpoint=False)
    audio = 0.1 * np.sin(2 * np.pi * 440 * t)
    buf = io.BytesIO()
    sf.write(buf, audio, sr, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def test_generate_spectrogram_returns_png():
    png_bytes = generate_spectrogram(_make_wav_bytes())

    assert png_bytes[:8] == b"\x89PNG\r\n\x1a\n"

    img = Image.open(io.BytesIO(png_bytes))
    assert img.format == "PNG"
    assert img.size == (SPECTROGRAM_WIDTH, SPECTROGRAM_HEIGHT)


def test_generate_spectrogram_handles_empty_audio():
    silent = np.zeros(22050, dtype=np.float32)
    buf = io.BytesIO()
    sf.write(buf, silent, 22050, format="WAV", subtype="PCM_16")

    png_bytes = generate_spectrogram(buf.getvalue())
    img = Image.open(io.BytesIO(png_bytes))
    assert img.size == (SPECTROGRAM_WIDTH, SPECTROGRAM_HEIGHT)


@patch("starscream.storage.s3._client")
def test_put_spectrogram_stores_png(mock_client):
    from starscream.storage import put_spectrogram

    mock_s3 = MagicMock()
    mock_client.return_value = mock_s3
    recording_id = str(uuid.uuid4())
    data = b"\x89PNG\r\n\x1a\nfake"

    with patch("starscream.storage.s3.get_settings") as mock_settings:
        mock_settings.return_value.s3_bucket = "test-bucket"
        key = put_spectrogram(recording_id, data)

    assert key == f"spectrogram/{recording_id}.png"
    mock_s3.put_object.assert_called_once_with(
        Bucket="test-bucket",
        Key=key,
        Body=data,
        ContentType="image/png",
    )


@patch("starscream.api.routes.recordings.get_spectrogram_bytes")
@patch("starscream.api.routes.recordings.get_audio_bytes")
@patch("starscream.pipeline.spectrogram.generate_spectrogram")
@patch("starscream.api.routes.recordings.put_spectrogram")
def test_get_spectrogram_serves_cached(
    mock_put,
    mock_generate,
    mock_get_audio,
    mock_get_spect,
):
    from fastapi.testclient import TestClient

    from starscream.api.main import app
    from starscream.db.models import Recording

    recording_id = uuid.uuid4()
    cached_png = b"\x89PNG\r\n\x1a\ncached"

    mock_recording = MagicMock(spec=Recording)
    mock_recording.spectrogram_key = f"spectrogram/{recording_id}.png"
    mock_recording.flac_key = "flac/x.flac"
    mock_recording.mp3_key = None
    mock_get_spect.return_value = cached_png

    mock_db = MagicMock()
    mock_db.get.return_value = mock_recording

    from starscream.db.session import get_db

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        client = TestClient(app)
        response = client.get(f"/v1/recordings/{recording_id}/spectrogram.png")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.content == cached_png
    assert response.headers["content-type"] == "image/png"
    mock_generate.assert_not_called()
    mock_put.assert_not_called()
    mock_get_audio.assert_not_called()


@patch("starscream.api.routes.recordings.get_spectrogram_bytes")
@patch("starscream.api.routes.recordings.get_audio_bytes")
@patch("starscream.pipeline.spectrogram.generate_spectrogram")
@patch("starscream.api.routes.recordings.put_spectrogram")
def test_get_spectrogram_generates_on_demand(
    mock_put,
    mock_generate,
    mock_get_audio,
    mock_get_spect,
):
    from fastapi.testclient import TestClient

    from starscream.api.main import app
    from starscream.db.models import Recording

    recording_id = uuid.uuid4()
    generated_png = generate_spectrogram(_make_wav_bytes())

    mock_recording = MagicMock(spec=Recording)
    mock_recording.spectrogram_key = None
    mock_recording.flac_key = "flac/x.flac"
    mock_recording.mp3_key = None
    mock_get_audio.return_value = _make_wav_bytes()
    mock_generate.return_value = generated_png
    mock_put.return_value = f"spectrogram/{recording_id}.png"

    mock_db = MagicMock()
    mock_db.get.return_value = mock_recording

    from starscream.db.session import get_db

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        client = TestClient(app)
        response = client.get(f"/v1/recordings/{recording_id}/spectrogram.png")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.content == generated_png
    mock_generate.assert_called_once()
    mock_put.assert_called_once()
    mock_db.commit.assert_called_once()


@patch("starscream.api.routes.recordings.get_spectrogram_bytes")
def test_get_spectrogram_404_without_audio(mock_get_spect):
    from fastapi.testclient import TestClient

    from starscream.api.main import app
    from starscream.db.models import Recording

    recording_id = uuid.uuid4()
    mock_recording = MagicMock(spec=Recording)
    mock_recording.spectrogram_key = None
    mock_recording.flac_key = None
    mock_recording.mp3_key = None

    mock_db = MagicMock()
    mock_db.get.return_value = mock_recording

    from starscream.db.session import get_db

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        client = TestClient(app)
        response = client.get(f"/v1/recordings/{recording_id}/spectrogram.png")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
