# Voice and Catalogue Microservice

A FastAPI backend for turning an artisan's spoken or typed product details into an editable catalogue draft. Gemini provides speech transcription, translation, and optional transliteration. Product intent, field extraction, validation, and descriptions remain deterministic backend rules; Gemini is never used to answer general-knowledge questions.

## Architecture and request flow

```text
mobile/web client -> FastAPI -> audio validation -> Gemini transcription
                                 -> Gemini Hindi/English translation
                                 -> intent rules -> vocabulary/regex extraction
                                 -> validation -> controlled descriptions
                                 -> SQLAlchemy draft -> JSON response
```

`app/api` contains HTTP routes, `app/gemini` the narrow Gemini client, `app/catalogue` the rules and editable vocabulary, `app/services` the workflow, `app/repositories.py` persistence operations, `app/models.py` SQLAlchemy tables, `app/schemas.py` Pydantic contracts, `app/validators.py` audio checks, and `tests` the mocked tests. Configuration is in `app/config.py` and `.env.example`. The standalone transcription route ends after speech recognition; it does not translate, extract fields, or save a draft.

The Gemini adapter uploads audio from memory to Google's Files API, calls the dedicated `gemini-3.5-transcribe` model in verbatim mode, and deletes the uploaded file in a cleanup step. The documented transcription model covers most listed languages. Tamil and Urdu use the configured general audio model because they are absent from the dedicated model's published language list; verify those transcripts carefully. Translation and transliteration use a separate configurable text model. Interactions requests set `store=false` to disable server-side interaction storage. See Google's [transcription guide](https://ai.google.dev/gemini-api/docs/transcribe) and [Files API guide](https://ai.google.dev/gemini-api/docs/files).

## Install and run locally

Python 3.11 or newer is required.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -e ".[dev]"
cp .env.example .env             # Windows PowerShell: Copy-Item .env.example .env
python -m uvicorn app.main:app --reload
```

The API runs at `http://127.0.0.1:8000`. Open the [interactive API tester](http://127.0.0.1:8000/tester) to choose an endpoint, edit its request, send it to the local service, and compare the live response with a clearly labelled example. Select **Transcribe audio** to upload a file or use **Record → Stop → Play → Transcribe**. The browser converts a microphone recording to 16 kHz mono WAV. After transcription succeeds, the transcript appears above the live JSON response; **Use transcript to create catalogue** fills the text workflow. Microphone access requires browser permission and localhost or HTTPS. FastAPI OpenAPI docs are at `/docs`, the raw schema at `/openapi.json`, and `/health` confirms the process is running. Configure `GEMINI_API_KEY` before trying translation or audio requests. Health, language listing, draft reads, and validation do not need an API key.

### Gemini credentials

Create a Gemini API key in [Google AI Studio](https://ai.google.dev/gemini-api/docs/get-started) and set `GEMINI_API_KEY` in `voicebackend/.env`. The backend reads it server-side. Never put `.env` in version control or send the key to a mobile app. API access, quotas, and billing depend on your Google AI Studio project.

The model IDs in `.env.example` are configurable. `GEMINI_TEXT_TIMEOUT_SECONDS` bounds each text translation call independently of the longer audio timeout. The remaining variables control the database URL, audio limits, CORS, INR default policy, and the per-process rate-limit hook. `/api/v1/languages` lists candidate input codes; Tamil and Urdu transcription uses the general audio fallback model. The backend exposes `transliterate_text()` for a future script-specific UX.

### Docker

```bash
docker build -t voice-catalogue .
docker run --rm -p 8000:8000 --env-file .env -e DATABASE_URL=sqlite:////service/data/catalogue.db -v catalogue-data:/service/data voice-catalogue
```

The Docker image uses SQLite in a persistent volume. For PostgreSQL, install a PostgreSQL SQLAlchemy driver and set `DATABASE_URL` to a PostgreSQL URL. Tables use portable SQLAlchemy types. Startup adds provider attribution columns to older databases so Bhashini drafts remain labelled correctly; use versioned migrations for a larger deployment.

## API

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/health` | Liveness |
| GET | `/api/v1/languages` | Candidate language codes |
| POST | `/api/v1/transcriptions/from-audio` | Gemini transcript only; no catalogue draft |
| POST | `/api/v1/catalogues/from-audio` | Upload WAV, FLAC, MP3 or M4A and create a draft |
| POST | `/api/v1/catalogues/from-text` | Create a draft from a transcript |
| POST | `/api/v1/catalogues/guided-answer` | Record one answer for one existing draft field |
| POST | `/api/v1/catalogues/validate` | Validate an editable catalogue object |
| POST | `/api/v1/catalogues/{catalogue_id}/retry-translations` | Retry missing Gemini translations on the same draft |
| GET | `/api/v1/catalogues/{catalogue_id}` | Read a draft |
| PUT | `/api/v1/catalogues/{catalogue_id}` | Replace editable catalogue fields |
| GET | `/api/v1/catalogues` | List with `page`, `page_size`, and `search` |

`transcriptions/from-audio` accepts multipart fields `audio` and `source_language`. It returns `request_id`, `source_language`, `transcript`, `audio_format`, `sampling_rate_hz`, and `asr_provider`; it does not create a catalogue. `catalogues/from-audio` also accepts `output_languages` (comma-separated, default `hi,en`), optional `artisan_id`, and optional `session_id`. Uploads may be mono or stereo WAV, FLAC, MP3, or M4A at 8–48 kHz and at most 60 seconds by default. `guided-answer` uses multipart fields `catalogue_id`, `field`, `source_language`, and either `text` or `audio`. The 12 guided fields are `product_name`, `category`, `materials`, `craft_type`, `colors`, `dimensions`, `price`, `stock_quantity`, `location`, `is_handmade`, `special_features`, and `care_instructions`. `weight` and `currency` answers are also supported. Each audio answer goes through Gemini transcription. `from-text` accepts JSON with `text`, `source_language`, `output_languages`, `artisan_id`, and `session_id`. Supported candidate codes: `as`, `bn`, `en`, `gu`, `hi`, `kn`, `ml`, `mr`, `or`, `pa`, `ta`, `te`, `ur`.

For creation calls, send `X-Idempotency-Key` to safely retry the same request. A repeated key with different input returns HTTP 409. All responses include an `X-Request-ID` header, and successful drafts include `request_id` in JSON. A draft status is `needs_clarification`, `translation_pending`, or `draft_ready`; off-topic content returns `rejected` without a catalogue ID or an answer to the question.

When Gemini text translation times out, is rate limited, or returns a temporary service error, a clearly product-related transcript can still produce a draft from the original text. Unavailable transcript translations stay `null`; `processing.translation_pending` is `true`, and `warnings` explain the limitation. The original transcript and extracted fields are saved. If the product also lacks required fields, the status remains `needs_clarification`; otherwise it is `translation_pending`. Use the retry endpoint or the tester's **Retry translations** button when Gemini recovers. The retry updates translations and requested description languages without changing extracted facts or creating another draft. Inputs that cannot be safely classified without translation return HTTP 503 for a later retry. Authentication and configuration errors remain explicit errors.

### curl examples

```bash
curl -X POST http://127.0.0.1:8000/api/v1/catalogues/from-text \
  -H 'Content-Type: application/json' -H 'X-Idempotency-Key: sample-1' \
  -d '{"text":"यह हाथ से बना जूट का बैग ₹500 में है और 10 पीस उपलब्ध हैं","source_language":"hi","output_languages":["hi","en"]}'

curl -X POST http://127.0.0.1:8000/api/v1/catalogues/from-audio \
  -F 'audio=@sample.wav;type=audio/wav' -F 'source_language=hi' \
  -F 'output_languages=hi,en' -F 'session_id=demo-session'

curl -X POST http://127.0.0.1:8000/api/v1/transcriptions/from-audio \
  -F 'audio=@sample.wav;type=audio/wav' -F 'source_language=hi'

curl -X POST http://127.0.0.1:8000/api/v1/catalogues/guided-answer \
  -F 'catalogue_id=YOUR_UUID' -F 'field=stock_quantity' \
  -F 'source_language=hi' -F 'audio=@answer.wav;type=audio/wav'

curl -X POST http://127.0.0.1:8000/api/v1/catalogues/YOUR_UUID/retry-translations

curl 'http://127.0.0.1:8000/api/v1/catalogues?page=1&page_size=20&search=jute'
```

For a correction, GET the draft, edit its `catalogue` object in the frontend, and PUT `{"catalogue": {...}}` to the same catalogue ID. The server recomputes validation and descriptions. The frontend should display the original transcript, all extracted fields, warnings and clarification questions before any publishing action in the larger application. No publish route is included here.

## Rules and privacy

The vocabulary is in `app/catalogue/vocabulary.json`. Extend aliases there for categories, materials, colours, crafts, product cues and handmade signals. Unknown values stay `null` or an empty list. `product_name` is derived only when both a category and an observed material or craft are present, or when the user explicitly names it. A numeric price needs an explicit rupee cue to set INR unless `DEFAULT_CURRENCY_INR=true`. Required fields are name, category, material, price, stock quantity and source language. A zero stock count is valid. Description templates omit missing facts; they do not add quality, certification or provenance claims.

The service reads audio within the configured size limit and never permanently saves raw audio or filenames locally. The multipart framework may spool large uploads to an operating-system temporary file; each upload is explicitly closed after validation and the framework cleans up request files after the request. Upload signatures, MIME type, duration, sample rate, channels, and size are checked before transcription. Gemini Files API uploads are deleted in a cleanup step; if deletion fails, Google documents automatic deletion after 48 hours. Audio and text are sent to Google for processing, so tell artisans this in your product privacy notice. Transcripts and translations are saved for review; avoid unnecessary personal details in recordings. The Gemini key is read from environment variables and excluded from responses and logs. CORS is configured by `CORS_ORIGINS`; the included rate limiter is a single-process IP-based hook.

## Tests and checks

```bash
python -m ruff format --check app tests
python -m ruff check app tests
python -m pytest -q
```

Tests mock Gemini and need no real credentials. They cover Hindi and mixed text, extraction and validation edge cases, off-topic rejection, injection-like input, Gemini timeout/authentication/malformed responses, audio upload and cleanup, guided corrections, legacy provider migration, listing, and duplicate requests.

## Known limitations

The parser is rule based and vocabulary coverage is intentionally small. Gemini transcription and translation can make mistakes, especially for mixed speech, names, Tamil, and Urdu. During a translation outage, regional-language drafts may have fewer extracted fields because the rules only know the configured vocabulary; do not publish while `translation_pending` is true. Live Gemini credentials and models are not exercised by the test suite. More scripts and synonyms should be added to the JSON vocabulary as real recordings are reviewed. Generated non-Hindi/non-English descriptions use Gemini translation and should be reviewed by the artisan. For a public deployment, add authentication and artisan ownership checks, shared rate limiting, versioned database migrations, and a publication approval workflow.
