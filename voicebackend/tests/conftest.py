import os

os.environ["DATABASE_URL"] = "sqlite://"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import get_gemini
from app.main import app
from app.models import Base, get_db


class FakeGemini:
    def __init__(self):
        self.transcript = "हाथ से बना जूट का बैग ₹500 में है और 10 पीस उपलब्ध हैं"
        self.calls = []
        self.translation_failure = None

    def translate_text(self, text, source, target):
        self.calls.append(("translation", source, target))
        if self.translation_failure:
            raise self.translation_failure
        return text

    def transcribe_audio(self, audio, source, audio_format, sampling_rate):
        self.calls.append(("asr", source, audio_format))
        return self.transcript


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    fake = FakeGemini()

    def test_db():
        with session_factory() as db:
            yield db

    app.dependency_overrides[get_db] = test_db
    app.dependency_overrides[get_gemini] = lambda: fake
    with TestClient(app) as test_client:
        test_client.fake_gemini = fake
        yield test_client
    app.dependency_overrides.clear()
    engine.dispose()
