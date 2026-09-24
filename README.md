# SIH090

Smart India Hackathon project for an AI-assisted artisan catalogue application.

## Repository layout

| Folder | Purpose | Status |
| --- | --- | --- |
| [`voicebackend/`](voicebackend/) | Voice-to-catalogue API using Bhashini and deterministic product rules | Implemented |
| [`imageRecognitionBackend/`](imageRecognitionBackend/) | Future product image recognition service | Reserved |
| [`priceDeterminationBackend/`](priceDeterminationBackend/) | Future pricing support service | Reserved |
| [`Frontend/`](Frontend/) | Future mobile or web application | Reserved |

Each component owns its dependencies, configuration example, tests and documentation. Run the implemented backend from its own directory:

```bash
cd voicebackend
python -m pip install -e ".[dev]"
cp .env.example .env
python -m uvicorn app.main:app --reload
```

See the [voice backend README](voicebackend/README.md) for Bhashini credentials, API examples, Docker setup and test commands. Keep real credentials in local `.env` files; they are ignored by Git.
