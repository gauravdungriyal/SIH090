import hashlib
import json
from uuid import uuid4

from fastapi import HTTPException

from app.catalogue.rules import (
    LANGUAGES,
    OFF_TOPIC_MESSAGE,
    classify_intent,
    extract,
    generate_descriptions,
    questions_for,
    validate_catalogue,
)
from app.gemini.client import GeminiClient
from app.models import CatalogueRecord
from app.repositories import CatalogueRepository, IdempotencyConflict
from app.schemas import Catalogue, CatalogueResponse, Intent, Processing


def check_language(language: str) -> None:
    if language not in LANGUAGES:
        raise HTTPException(
            status_code=422,
            detail={"code": "unsupported_language", "message": "Unsupported source language"},
        )


def fingerprint(payload: dict) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()


def record_response(record: CatalogueRecord, request_id: str) -> CatalogueResponse:
    return CatalogueResponse(
        request_id=request_id,
        catalogue_id=record.id,
        status=record.status,
        intent=record.intent,
        source_language=record.source_language,
        original_transcript=record.original_transcript,
        english_translation=record.english_translation,
        hindi_translation=record.hindi_translation,
        catalogue=Catalogue.model_validate(record.catalogue),
        missing_fields=record.missing_fields,
        clarification_questions=questions_for(record.missing_fields),
        warnings=record.warnings,
        processing=Processing(
            asr_provider=record.asr_provider,
            translation_provider=record.translation_provider,
        ),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def process_transcript(
    *,
    transcript: str,
    source_language: str,
    output_languages: list[str],
    artisan_id: str | None,
    session_id: str | None,
    request_id: str,
    repo: CatalogueRepository,
    gemini: GeminiClient,
    default_currency_inr: bool,
    idempotency_key: str | None = None,
    request_fingerprint: str | None = None,
    audio_used: bool = False,
) -> CatalogueResponse | dict:
    check_language(source_language)
    if not transcript.strip():
        raise HTTPException(
            status_code=422,
            detail={"code": "empty_transcript", "message": "Transcript must not be empty"},
        )
    for lang in output_languages:
        check_language(lang)
    if idempotency_key:
        found = repo.by_key(idempotency_key)
        if found:
            if found.fingerprint != request_fingerprint:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "idempotency_conflict",
                        "message": "Key used for a different request",
                    },
                )
            return record_response(found.catalogue, request_id)
    preliminary = classify_intent([transcript])
    if preliminary == Intent.OFF_TOPIC:
        return {
            "request_id": request_id,
            "intent": "OFF_TOPIC",
            "status": "rejected",
            "message": OFF_TOPIC_MESSAGE,
        }
    english = (
        transcript
        if source_language == "en"
        else gemini.translate_text(transcript, source_language, "en")
    )
    hindi = (
        transcript
        if source_language == "hi"
        else gemini.translate_text(transcript, source_language, "hi")
    )
    intent = classify_intent([transcript, english, hindi])
    if intent in (Intent.OFF_TOPIC, Intent.UNCLEAR):
        return {
            "request_id": request_id,
            "intent": intent.value,
            "status": "rejected",
            "message": OFF_TOPIC_MESSAGE,
        }
    catalogue = extract([transcript, english, hindi], default_currency_inr)
    missing, errors = validate_catalogue(catalogue, source_language)
    if errors:
        raise HTTPException(status_code=422, detail={"code": "invalid_catalogue", "errors": errors})
    catalogue = generate_descriptions(catalogue)
    for lang in output_languages:
        if lang not in ("en", "hi") and catalogue.description_en:
            catalogue.description_translations[lang] = gemini.translate_text(
                catalogue.description_en, "en", lang
            )
    record = CatalogueRecord(
        id=str(uuid4()),
        artisan_id=artisan_id,
        session_id=session_id,
        source_language=source_language,
        original_transcript=transcript,
        english_translation=english,
        hindi_translation=hindi,
        catalogue=catalogue.model_dump(),
        missing_fields=missing,
        status="needs_clarification" if missing else "draft_ready",
        intent=intent.value,
        warnings=[],
        audio_used=audio_used,
        asr_provider="Gemini" if audio_used else None,
        translation_provider="Gemini",
    )
    try:
        record = repo.create(record, idempotency_key, request_fingerprint)
    except IdempotencyConflict as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "idempotency_conflict", "message": "Key used for a different request"},
        ) from exc
    return record_response(record, request_id)


def update_record(
    record: CatalogueRecord, catalogue: Catalogue, repo: CatalogueRepository, request_id: str
) -> CatalogueResponse:
    missing, errors = validate_catalogue(catalogue, record.source_language)
    if errors:
        raise HTTPException(status_code=422, detail={"code": "invalid_catalogue", "errors": errors})
    catalogue = generate_descriptions(catalogue)
    record.catalogue = catalogue.model_dump()
    record.missing_fields = missing
    record.status = "needs_clarification" if missing else "draft_ready"
    record.intent = Intent.PRODUCT_CORRECTION.value
    repo.save(record)
    return record_response(record, request_id)
