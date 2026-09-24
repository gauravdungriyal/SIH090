import io
import re
import wave

from fastapi import HTTPException, UploadFile
from mutagen import File as MutagenFile
from mutagen import MutagenError

from app.config import Settings


async def validate_audio(upload: UploadFile, settings: Settings) -> tuple[bytes, str, int]:
    limit = settings.max_audio_size_mb * 1024 * 1024
    data = await upload.read(limit + 1)
    await upload.close()
    if not data or len(data) > limit:
        raise HTTPException(
            status_code=413,
            detail={"code": "invalid_audio_size", "message": "Audio is empty or too large"},
        )
    safe_filename = re.sub(r"[^A-Za-z0-9._-]", "_", re.split(r"[\\/]", upload.filename or "")[-1])[
        :100
    ]
    # Ignore the client filename. No file is written to disk.
    if data.startswith(b"RIFF") and data[8:12] == b"WAVE":
        audio_format, media_types = (
            "wav",
            {"audio/wav", "audio/wave", "audio/x-wav", "application/octet-stream"},
        )
        try:
            with wave.open(io.BytesIO(data), "rb") as stream:
                rate = stream.getframerate()
                duration = stream.getnframes() / rate
                channels = stream.getnchannels()
        except (wave.Error, EOFError, ZeroDivisionError) as exc:
            raise HTTPException(status_code=422, detail={"code": "invalid_audio"}) from exc
    elif data.startswith(b"fLaC"):
        audio_format, media_types = (
            "flac",
            {"audio/flac", "audio/x-flac", "application/octet-stream"},
        )
        try:
            parsed = MutagenFile(io.BytesIO(data))
        except (MutagenError, ValueError, OSError) as exc:
            raise HTTPException(status_code=422, detail={"code": "invalid_audio"}) from exc
        if not parsed or not parsed.info:
            raise HTTPException(status_code=422, detail={"code": "invalid_audio"})
        rate, duration, channels = parsed.info.sample_rate, parsed.info.length, parsed.info.channels
    elif data.startswith(b"ID3") or data[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        audio_format, media_types = "mp3", {"audio/mpeg", "audio/mp3", "application/octet-stream"}
        try:
            parsed = MutagenFile(io.BytesIO(data))
        except (MutagenError, ValueError, OSError) as exc:
            raise HTTPException(status_code=422, detail={"code": "invalid_audio"}) from exc
        if not parsed or not parsed.info:
            raise HTTPException(status_code=422, detail={"code": "invalid_audio"})
        rate, duration, channels = parsed.info.sample_rate, parsed.info.length, parsed.info.channels
    else:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_audio_format", "message": "Use WAV, FLAC, or MP3 audio"},
        )
    if upload.content_type not in media_types:
        raise HTTPException(status_code=422, detail={"code": "invalid_audio_type"})
    extension = safe_filename.rsplit(".", 1)[-1].lower() if "." in safe_filename else ""
    if extension in {"wav", "flac", "mp3"} and extension != audio_format:
        raise HTTPException(status_code=422, detail={"code": "invalid_audio_format"})
    if (
        not 0 < duration <= settings.max_audio_duration_seconds
        or not 8000 <= rate <= 48000
        or channels != 1
    ):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "invalid_audio_properties",
                "message": "Use mono audio, 8–48 kHz, within the duration limit",
            },
        )
    return data, audio_format, rate
