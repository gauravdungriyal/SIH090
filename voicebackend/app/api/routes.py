import hashlib
import re

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from sqlalchemy.orm import Session

from app.catalogue.rules import (
    LANGUAGES,
    OFF_TOPIC_MESSAGE,
    classify_intent,
    extract,
    generate_descriptions,
    questions_for,
    validate_catalogue,
)
from app.config import Settings, get_settings
from app.gemini.client import GeminiClient
from app.models import get_db
from app.repositories import CatalogueRepository
from app.schemas import (
    Catalogue,
    CataloguePatch,
    CatalogueResponse,
    Intent,
    ListResponse,
    RejectedResponse,
    TextRequest,
    TranscriptionResponse,
    ValidationRequest,
    ValidationResponse,
)
from app.services.catalogue import (
    check_language,
    fingerprint,
    process_transcript,
    record_response,
    retry_record_translations,
    update_record,
)
from app.services.translation import draft_status, translate_core
from app.validators import validate_audio

router = APIRouter()


def get_gemini(settings: Settings = Depends(get_settings)):
    client = GeminiClient(settings)
    try:
        yield client
    finally:
        client.close()


def parse_languages(raw: str) -> list[str]:
    values = [part.strip() for part in raw.split(",") if part.strip()]
    if not values:
        raise HTTPException(status_code=422, detail={"code": "missing_output_languages"})
    for value in values:
        check_language(value)
    return list(dict.fromkeys(values))


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/api/v1/languages")
def languages():
    return {
        "languages": [{"code": code, "name": name} for code, name in LANGUAGES.items()],
        "note": "Gemini's dedicated transcription model supports most listed languages. Tamil and Urdu use the configured audio fallback model; its accuracy may vary.",
    }


@router.post("/api/v1/transcriptions/from-audio", response_model=TranscriptionResponse)
async def transcribe_audio(
    request: Request,
    audio: UploadFile = File(...),
    source_language: str = Form(...),
    gemini: GeminiClient = Depends(get_gemini),
    settings: Settings = Depends(get_settings),
):
    check_language(source_language)
    data, audio_format, rate = await validate_audio(audio, settings)
    transcript = gemini.transcribe_audio(data, source_language, audio_format, rate)
    if not transcript or not transcript.strip():
        raise HTTPException(
            status_code=422,
            detail={"code": "empty_transcript", "message": "No speech was recognized"},
        )
    return TranscriptionResponse(
        request_id=request.state.request_id,
        source_language=source_language,
        transcript=transcript.strip(),
        audio_format=audio_format,
        sampling_rate_hz=rate,
    )


@router.post("/api/v1/catalogues/from-text", response_model=CatalogueResponse | RejectedResponse)
def from_text(
    body: TextRequest,
    request: Request,
    db: Session = Depends(get_db),
    gemini: GeminiClient = Depends(get_gemini),
    settings: Settings = Depends(get_settings),
    idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key", max_length=200),
):
    return process_transcript(
        transcript=body.text,
        source_language=body.source_language,
        output_languages=body.output_languages,
        artisan_id=body.artisan_id,
        session_id=body.session_id,
        request_id=request.state.request_id,
        repo=CatalogueRepository(db),
        gemini=gemini,
        default_currency_inr=settings.default_currency_inr,
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint(body.model_dump()),
    )


@router.post("/api/v1/catalogues/from-audio", response_model=CatalogueResponse | RejectedResponse)
async def from_audio(
    request: Request,
    audio: UploadFile = File(...),
    source_language: str = Form(...),
    output_languages: str = Form("hi,en"),
    artisan_id: str | None = Form(None),
    session_id: str | None = Form(None),
    db: Session = Depends(get_db),
    gemini: GeminiClient = Depends(get_gemini),
    settings: Settings = Depends(get_settings),
    idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key", max_length=200),
):
    check_language(source_language)
    languages = parse_languages(output_languages)
    data, audio_format, rate = await validate_audio(audio, settings)
    digest = hashlib.sha256(data).hexdigest()
    payload_fingerprint = fingerprint(
        {
            "audio": digest,
            "source_language": source_language,
            "output_languages": languages,
            "artisan_id": artisan_id,
            "session_id": session_id,
        }
    )
    repo = CatalogueRepository(db)
    if idempotency_key:
        found = repo.by_key(idempotency_key)
        if found:
            if found.fingerprint != payload_fingerprint:
                raise HTTPException(status_code=409, detail={"code": "idempotency_conflict"})
            return record_response(found.catalogue, request.state.request_id)
    transcript = gemini.transcribe_audio(data, source_language, audio_format, rate)
    return process_transcript(
        transcript=transcript,
        source_language=source_language,
        output_languages=languages,
        artisan_id=artisan_id,
        session_id=session_id,
        request_id=request.state.request_id,
        repo=repo,
        gemini=gemini,
        default_currency_inr=settings.default_currency_inr,
        idempotency_key=idempotency_key,
        request_fingerprint=payload_fingerprint,
        audio_used=True,
    )


@router.post(
    "/api/v1/catalogues/guided-answer", response_model=CatalogueResponse | RejectedResponse
)
async def guided_answer(
    request: Request,
    catalogue_id: str = Form(...),
    field: str = Form(...),
    source_language: str = Form(...),
    text: str | None = Form(None),
    audio: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    gemini: GeminiClient = Depends(get_gemini),
    settings: Settings = Depends(get_settings),
):
    check_language(source_language)
    allowed = {
        "product_name",
        "category",
        "materials",
        "craft_type",
        "colors",
        "dimensions",
        "price",
        "stock_quantity",
        "location",
        "is_handmade",
        "special_features",
        "care_instructions",
        "weight",
        "currency",
    }
    if field not in allowed:
        raise HTTPException(status_code=422, detail={"code": "unsupported_field"})
    repo = CatalogueRepository(db)
    record = repo.get(catalogue_id)
    if not record:
        raise HTTPException(status_code=404, detail={"code": "catalogue_not_found"})
    if bool(text and text.strip()) == bool(audio):
        raise HTTPException(
            status_code=422, detail={"code": "answer_required", "message": "Provide text or audio"}
        )
    audio_used = audio is not None
    if audio:
        data, audio_format, rate = await validate_audio(audio, settings)
        answer = gemini.transcribe_audio(data, source_language, audio_format, rate)
    else:
        answer = text.strip()
    if classify_intent([answer]) == Intent.OFF_TOPIC:
        return {
            "request_id": request.state.request_id,
            "intent": "OFF_TOPIC",
            "status": "rejected",
            "message": OFF_TOPIC_MESSAGE,
        }
    translations = translate_core(answer, source_language, gemini)
    english, hindi = translations.english, translations.hindi
    parsing_text = english or answer
    if field == "price" and not re.search(
        r"price|cost|₹|rs\.?|rupees?|रुप", parsing_text, re.IGNORECASE
    ):
        parsing_text = "price " + parsing_text
    if field == "stock_quantity" and not re.search(
        r"stock|quantity|units?|pieces?", parsing_text, re.IGNORECASE
    ):
        parsing_text = "stock " + parsing_text
    parsed = extract([parsing_text, hindi or ""], settings.default_currency_inr)
    catalogue = Catalogue.model_validate(record.catalogue)
    value = getattr(parsed, field)
    if field in {"product_name", "location", "care_instructions", "special_features"}:
        stripped = re.sub(r"[\x00-\x1f]", " ", answer).strip(" .।")[:150]
        if field == "product_name":
            value = parsed.product_name or re.sub(
                r"^(?:the )?(?:product )?name\s*(?:is|:)\s*", "", stripped, flags=re.IGNORECASE
            )
        elif field == "location":
            value = parsed.location or re.sub(
                r"^(?:made|crafted)\s+in\s+", "", stripped, flags=re.IGNORECASE
            )
        elif field == "care_instructions":
            value = stripped
        else:
            value = [stripped] if stripped else []
    elif field == "is_handmade" and value is None:
        if re.search(r"\b(yes|true)\b|हाँ|हां", f"{english or ''} {hindi or ''}", re.IGNORECASE):
            value = True
        elif re.search(r"\b(no|false)\b|नहीं", f"{english or ''} {hindi or ''}", re.IGNORECASE):
            value = False
    if field == "price" and value is not None:
        catalogue.currency = parsed.currency
    if field == "currency":
        if re.search(
            r"₹|\b(?:inr|rupees?|rs\.?)\b|रुप", f"{english or ''} {hindi or ''}", re.IGNORECASE
        ):
            value = "INR"
        else:
            value = None
    if (
        value is None
        or value == []
        or field == "dimensions"
        and not any(getattr(value, part) is not None for part in ("length", "width", "height"))
    ):
        record.warnings = [
            f"Could not extract {field}; please edit the field directly or answer again."
        ]
    else:
        setattr(catalogue, field, value)
        if field == "weight":
            catalogue.weight_unit = parsed.weight_unit
        record.warnings = []
    missing, errors = validate_catalogue(catalogue, record.source_language)
    if errors:
        raise HTTPException(status_code=422, detail={"code": "invalid_catalogue", "errors": errors})
    catalogue = generate_descriptions(catalogue)
    record.catalogue = catalogue.model_dump()
    record.missing_fields = missing
    record.translation_pending = record.translation_pending or translations.pending
    record.status = draft_status(missing, record.translation_pending)
    record.intent = Intent.PRODUCT_CORRECTION.value
    record.original_transcript += f"\n[{field}] {answer}"
    if english:
        record.english_translation = (record.english_translation or "") + f"\n[{field}] {english}"
    if hindi:
        record.hindi_translation = (record.hindi_translation or "") + f"\n[{field}] {hindi}"
    if audio_used and record.asr_provider != "Gemini":
        record.asr_provider = ", ".join(
            dict.fromkeys(filter(None, [record.asr_provider, "Gemini"]))
        )
    if translations.used_gemini and record.translation_provider != "Gemini":
        record.translation_provider = ", ".join(
            dict.fromkeys(filter(None, [record.translation_provider, "Gemini"]))
        )
    record.warnings.extend(
        warning for warning in translations.warnings if warning not in record.warnings
    )
    repo.save(record)
    return record_response(record, request.state.request_id)


@router.post("/api/v1/catalogues/validate", response_model=ValidationResponse)
def validate(body: ValidationRequest):
    missing, errors = validate_catalogue(body.catalogue, body.source_language)
    return ValidationResponse(
        valid=not missing and not errors,
        missing_fields=missing,
        errors=errors,
        clarification_questions=questions_for(missing),
    )


@router.post(
    "/api/v1/catalogues/{catalogue_id}/retry-translations", response_model=CatalogueResponse
)
def retry_translations(
    catalogue_id: str,
    request: Request,
    db: Session = Depends(get_db),
    gemini: GeminiClient = Depends(get_gemini),
):
    repo = CatalogueRepository(db)
    record = repo.get(catalogue_id)
    if not record:
        raise HTTPException(status_code=404, detail={"code": "catalogue_not_found"})
    return retry_record_translations(record, repo, gemini, request.state.request_id)


@router.get("/api/v1/catalogues/{catalogue_id}", response_model=CatalogueResponse)
def get_catalogue(catalogue_id: str, request: Request, db: Session = Depends(get_db)):
    record = CatalogueRepository(db).get(catalogue_id)
    if not record:
        raise HTTPException(status_code=404, detail={"code": "catalogue_not_found"})
    return record_response(record, request.state.request_id)


@router.put("/api/v1/catalogues/{catalogue_id}", response_model=CatalogueResponse)
def put_catalogue(
    catalogue_id: str, body: CataloguePatch, request: Request, db: Session = Depends(get_db)
):
    repo = CatalogueRepository(db)
    record = repo.get(catalogue_id)
    if not record:
        raise HTTPException(status_code=404, detail={"code": "catalogue_not_found"})
    return update_record(record, body.catalogue, repo, request.state.request_id)


@router.get("/api/v1/catalogues", response_model=ListResponse)
def list_catalogues(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=100),
    db: Session = Depends(get_db),
):
    records, total = CatalogueRepository(db).list(page, page_size, search)
    return ListResponse(
        items=[record_response(item, request.state.request_id) for item in records],
        total=total,
        page=page,
        page_size=page_size,
    )
