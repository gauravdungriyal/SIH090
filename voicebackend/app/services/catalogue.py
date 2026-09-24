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
from app.gemini.client import GeminiClient, GeminiError
from app.models import CatalogueRecord
from app.repositories import CatalogueRepository, IdempotencyConflict
from app.schemas import Catalogue, CatalogueResponse, Intent, Processing
from app.services.translation import (
    PENDING_TRANSLATION_WARNING,
    draft_status,
    translate_core,
    translate_descriptions,
)


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
            translation_pending=record.translation_pending,
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
    translations = translate_core(transcript, source_language, gemini)
    if translations.pending and preliminary == Intent.UNCLEAR:
        raise GeminiError(
            "translation_unavailable",
            "Gemini translation is temporarily unavailable; retry this request",
            503,
        )
    english, hindi = translations.english, translations.hindi
    intent = classify_intent(list(filter(None, [transcript, english, hindi])))
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
    additional_pending = (
        False
        if translations.pending
        else translate_descriptions(catalogue, output_languages, gemini)
    )
    translation_pending = translations.pending or additional_pending
    warnings = translations.warnings.copy()
    if additional_pending and PENDING_TRANSLATION_WARNING not in warnings:
        warnings.append(PENDING_TRANSLATION_WARNING)
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
        status=draft_status(missing, translation_pending),
        intent=intent.value,
        warnings=warnings,
        audio_used=audio_used,
        asr_provider="Gemini" if audio_used else None,
        translation_provider=(
            "Gemini" if translations.used_gemini or catalogue.description_translations else None
        ),
        translation_pending=translation_pending,
        requested_output_languages=output_languages,
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
    record.status = draft_status(missing, record.translation_pending)
    record.intent = Intent.PRODUCT_CORRECTION.value
    repo.save(record)
    return record_response(record, request_id)


def retry_record_translations(
    record: CatalogueRecord,
    repo: CatalogueRepository,
    gemini: GeminiClient,
    request_id: str,
) -> CatalogueResponse:
    if not record.translation_pending:
        return record_response(record, request_id)
    translations = translate_core(record.original_transcript, record.source_language, gemini)
    if translations.english:
        record.english_translation = translations.english
    if translations.hindi:
        record.hindi_translation = translations.hindi
    catalogue = Catalogue.model_validate(record.catalogue)
    additional_pending = (
        False
        if translations.pending
        else translate_descriptions(
            catalogue, record.requested_output_languages or ["hi", "en"], gemini
        )
    )
    record.catalogue = catalogue.model_dump()
    record.translation_pending = translations.pending or additional_pending
    record.status = draft_status(record.missing_fields, record.translation_pending)
    record.warnings = [
        warning for warning in record.warnings if warning != PENDING_TRANSLATION_WARNING
    ]
    if record.translation_pending:
        record.warnings.append(PENDING_TRANSLATION_WARNING)
    if translations.used_gemini or catalogue.description_translations:
        record.translation_provider = ", ".join(
            dict.fromkeys(filter(None, [record.translation_provider, "Gemini"]))
        )
    repo.save(record)
    return record_response(record, request_id)
