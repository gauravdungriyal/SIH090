import io
import wave
from types import SimpleNamespace


def wav_audio():
    stream = io.BytesIO()
    with wave.open(stream, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"\0\0" * 16000)
    return stream.getvalue()


def post_audio(client, source_language="hi", audio=None):
    return client.post(
        "/api/v1/transcriptions/from-audio",
        data={"source_language": source_language},
        files={
            "audio": ("recording.wav", audio if audio is not None else wav_audio(), "audio/wav")
        },
    )


def test_transcription_returns_original_text_without_creating_catalogue(client):
    response = post_audio(client)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["transcript"] == client.fake_gemini.transcript
    assert body["source_language"] == "hi"
    assert body["asr_provider"] == "Gemini"
    assert body["audio_format"] == "wav"
    assert body["sampling_rate_hz"] == 16000
    assert body["request_id"] == response.headers["X-Request-ID"]
    assert "catalogue_id" not in body
    assert client.get("/api/v1/catalogues").json()["total"] == 0
    assert client.fake_gemini.calls == [("asr", "hi", "wav")]


def test_transcription_rejects_invalid_audio(client):
    response = post_audio(client, audio=b"not audio")
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_audio_format"
    assert client.fake_gemini.calls == []


def test_transcription_rejects_unsupported_language(client):
    response = post_audio(client, source_language="fr")
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "unsupported_language"
    assert client.fake_gemini.calls == []


def test_transcription_rejects_empty_recognition(client):
    client.fake_gemini.transcript = "  "
    response = post_audio(client)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "empty_transcript"
    assert client.get("/api/v1/catalogues").json()["total"] == 0


def test_mobile_m4a_upload_uses_gemini(client, monkeypatch):
    monkeypatch.setattr(
        "app.validators.MutagenFile",
        lambda _: SimpleNamespace(info=SimpleNamespace(sample_rate=44100, length=1, channels=2)),
    )
    response = client.post(
        "/api/v1/transcriptions/from-audio",
        data={"source_language": "hi"},
        files={"audio": ("recording.m4a", b"\0\0\0\x18ftypM4A " + b"\0" * 16, "audio/mp4")},
    )
    assert response.status_code == 200, response.text
    assert response.json()["audio_format"] == "m4a"
    assert client.fake_gemini.calls == [("asr", "hi", "m4a")]
