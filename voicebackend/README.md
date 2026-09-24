# Voice and Catalogue Microservice

A FastAPI backend for turning an artisan's spoken or typed product details into an editable catalogue draft. Bhashini provides ASR, translation and optional transliteration. Product intent, field extraction, validation and descriptions are deterministic rules; no general-purpose LLM runs in this service.

## Architecture and request flow

```text
mobile/web client -> FastAPI -> audio validation -> Bhashini ASR
                                 -> Bhashini Hindi/English translation
                                 -> intent rules -> vocabulary/regex extraction
                                 -> validation -> controlled descriptions
                                 -> SQLAlchemy draft -> JSON response
```

`app/api` contains HTTP routes, `app/bhashini` the reusable ULCA pipeline client, `app/catalogue` the rules and editable vocabulary, `app/services` the workflow, `app/repositories.py` persistence operations, `app/models.py` SQLAlchemy tables, `app/schemas.py` Pydantic contracts, `app/validators.py` audio checks, and `tests` the mocked tests. Configuration is in `app/config.py` and `.env.example`.

The Bhashini adapter makes a Pipeline Config call, selects a service for the requested language pair, then makes a Pipeline Compute call using the returned inference key. The configured service IDs are preferred when available; a pipeline-supported service is selected otherwise. This follows the [official pipeline flow](https://dibd-bhashini.gitbook.io/bhashini-apis/pipeline-config-call) and [response contract](https://bhashini.gitbook.io/bhashini-apis/pipeline-config-call/response-payload). ASR and translations are separate calls to keep error handling and normalization simple.

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

The API runs at `http://127.0.0.1:8000`. Open the [interactive API tester](http://127.0.0.1:8000/tester) to choose an endpoint, edit its request, send it to the local service, and compare the live response with a clearly labelled example. It also explains request and response fields for each operation. FastAPI OpenAPI docs are at `/docs`, the raw schema at `/openapi.json`, and `/health` confirms the process is running. Configure credentials before trying translation or audio requests. Health, language listing, draft reads and validation do not need Bhashini credentials.

### Bhashini credentials

Register or log in through the [Bhashini developer portal](https://bhashini.gov.in/ulca/user/register). Get `userID` and `ulcaApiKey` from **My Profile**, and select a pipeline ID that supports the needed ASR and translation language pairs. Put these in `BHASHINI_USER_ID`, `BHASHINI_API_KEY` and `BHASHINI_PIPELINE_ID` in `.env`. The [official config documentation](https://dibd-bhashini.gitbook.io/bhashini-apis/pipeline-config-call) describes these credentials and the pipeline request. Never put `.env` in version control or send the credentials to a mobile app.

The remaining variables in `.env.example` control preferred service IDs, config and compute URLs, database URL, audio limits, timeouts, CORS, INR default policy and the per-process rate-limit hook. `BHASHINI_TRANSLITERATION_SERVICE_ID` is optional; the client exposes `transliterate_text()` for a future script-specific UX. Model and language availability depend on the chosen Bhashini pipeline, so `/api/v1/languages` lists candidate input codes rather than promising that every model supports them.

### Docker

```bash
docker build -t voice-catalogue .
docker run --rm -p 8000:8000 --env-file .env -e DATABASE_URL=sqlite:////service/data/catalogue.db -v catalogue-data:/service/data voice-catalogue
```

The Docker image uses SQLite in a persistent volume. For PostgreSQL, install a PostgreSQL SQLAlchemy driver and set `DATABASE_URL` to a PostgreSQL URL. Tables use portable SQLAlchemy types, but this prototype uses `create_all` rather than schema migrations.

## API

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/health` | Liveness |
| GET | `/api/v1/languages` | Candidate language codes |
| POST | `/api/v1/catalogues/from-audio` | Upload WAV, FLAC or MP3 and create a draft |
| POST | `/api/v1/catalogues/from-text` | Create a draft from a transcript |
| POST | `/api/v1/catalogues/guided-answer` | Record one answer for one existing draft field |
| POST | `/api/v1/catalogues/validate` | Validate an editable catalogue object |
| GET | `/api/v1/catalogues/{catalogue_id}` | Read a draft |
| PUT | `/api/v1/catalogues/{catalogue_id}` | Replace editable catalogue fields |
| GET | `/api/v1/catalogues` | List with `page`, `page_size`, and `search` |

`from-audio` uses multipart fields `audio`, `source_language`, `output_languages` (comma-separated, default `hi,en`), optional `artisan_id`, and optional `session_id`. Uploads must be mono WAV, FLAC or MP3, 8–48 kHz, and at most 60 seconds by default. `guided-answer` uses multipart fields `catalogue_id`, `field`, `source_language`, and either `text` or `audio`. The 12 guided fields are `product_name`, `category`, `materials`, `craft_type`, `colors`, `dimensions`, `price`, `stock_quantity`, `location`, `is_handmade`, `special_features`, and `care_instructions`. `weight` and `currency` answers are also supported. Each audio answer goes through Bhashini ASR. `from-text` accepts JSON with `text`, `source_language`, `output_languages`, `artisan_id`, and `session_id`. Supported candidate codes: `as`, `bn`, `en`, `gu`, `hi`, `kn`, `ml`, `mr`, `or`, `pa`, `ta`, `te`, `ur`.

For creation calls, send `X-Idempotency-Key` to safely retry the same request. A repeated key with different input returns HTTP 409. All responses include an `X-Request-ID` header, and successful drafts include `request_id` in JSON. A draft status is `needs_clarification` or `draft_ready`; off-topic content returns `rejected` without a catalogue ID or an answer to the question.

### curl examples

```bash
curl -X POST http://127.0.0.1:8000/api/v1/catalogues/from-text \
  -H 'Content-Type: application/json' -H 'X-Idempotency-Key: sample-1' \
  -d '{"text":"यह हाथ से बना जूट का बैग ₹500 में है और 10 पीस उपलब्ध हैं","source_language":"hi","output_languages":["hi","en"]}'

curl -X POST http://127.0.0.1:8000/api/v1/catalogues/from-audio \
  -F 'audio=@sample.wav;type=audio/wav' -F 'source_language=hi' \
  -F 'output_languages=hi,en' -F 'session_id=demo-session'

curl -X POST http://127.0.0.1:8000/api/v1/catalogues/guided-answer \
  -F 'catalogue_id=YOUR_UUID' -F 'field=stock_quantity' \
  -F 'source_language=hi' -F 'audio=@answer.wav;type=audio/wav'

curl 'http://127.0.0.1:8000/api/v1/catalogues?page=1&page_size=20&search=jute'
```

For a correction, GET the draft, edit its `catalogue` object in the frontend, and PUT `{"catalogue": {...}}` to the same catalogue ID. The server recomputes validation and descriptions. The frontend should display the original transcript, all extracted fields, warnings and clarification questions before any publishing action in the larger application. No publish route is included here.

## Rules and privacy

The vocabulary is in `app/catalogue/vocabulary.json`. Extend aliases there for categories, materials, colours, crafts, product cues and handmade signals. Unknown values stay `null` or an empty list. `product_name` is derived only when both a category and an observed material or craft are present, or when the user explicitly names it. A numeric price needs an explicit rupee cue to set INR unless `DEFAULT_CURRENCY_INR=true`. Required fields are name, category, material, price, stock quantity and source language. A zero stock count is valid. Description templates omit missing facts; they do not add quality, certification or provenance claims.

The service reads audio within the configured size limit and never permanently saves raw audio or filenames. The multipart framework may spool large uploads to an operating-system temporary file; each upload is explicitly closed after validation and the framework cleans up request files after the request. Upload signatures, MIME type, duration, sample rate, channels and size are checked before ASR. Transcripts and translations are saved for review; do not send sensitive personal details in a product recording. Bhashini credentials are read from environment variables and are excluded from error responses and logs. CORS is configured by `CORS_ORIGINS`; the included rate limiter is a single-process IP-based hook.

## Tests and checks

```bash
python -m ruff format --check app tests
python -m ruff check app tests
python -m pytest -q
```

Tests mock Bhashini and need no real credentials. They cover Hindi and mixed text, extraction and validation edge cases, off-topic rejection, injection-like input, Bhashini timeout/authentication/malformed responses, audio upload, guided corrections, listing and duplicate requests.

## Known limitations

The parser is rule based and vocabulary coverage is intentionally small. Regional language quality follows Bhashini's available models and translation quality. Live Bhashini credentials and models are not exercised by the test suite. The language list is a candidate list; unsupported model pairs fail with a clear error. More scripts and synonyms should be added to the JSON vocabulary as real recordings are reviewed. Generated non-Hindi/non-English descriptions use Bhashini translation and should be reviewed by the artisan. For a public deployment, add authentication and artisan ownership checks, shared rate limiting, database migrations, and a publication approval workflow.
