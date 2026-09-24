import httpx
import pytest

from app.bhashini.client import BhashiniClient, BhashiniError
from app.config import Settings


def make_client(handler):
    settings = Settings(
        bhashini_user_id="test-user",
        bhashini_api_key="test-key",
        bhashini_pipeline_id="test-pipeline",
        bhashini_config_url="https://config.test/pipeline",
        bhashini_compute_url="https://compute.test/pipeline",
    )
    return BhashiniClient(settings, httpx.Client(transport=httpx.MockTransport(handler)))


def test_bhashini_timeout(monkeypatch):
    monkeypatch.setattr("app.bhashini.client.time.sleep", lambda _: None)

    def timeout(request):
        raise httpx.ReadTimeout("timeout", request=request)

    with pytest.raises(BhashiniError) as error:
        make_client(timeout).translate_text("नमस्ते", "hi", "en")
    assert error.value.code == "timeout"


def test_bhashini_authentication_failure():
    def forbidden(request):
        return httpx.Response(401, json={"secret": "must not leak"})

    with pytest.raises(BhashiniError) as error:
        make_client(forbidden).translate_text("नमस्ते", "hi", "en")
    assert error.value.code == "authentication_failed"
    assert "secret" not in error.value.message


def test_malformed_bhashini_response():
    def malformed(request):
        return httpx.Response(200, json={"unexpected": []})

    with pytest.raises(BhashiniError) as error:
        make_client(malformed).translate_text("नमस्ते", "hi", "en")
    assert error.value.code == "malformed_response"


def test_bhashini_rate_limit(monkeypatch):
    monkeypatch.setattr("app.bhashini.client.time.sleep", lambda _: None)

    def limited(request):
        return httpx.Response(429)

    with pytest.raises(BhashiniError) as error:
        make_client(limited).translate_text("नमस्ते", "hi", "en")
    assert error.value.code == "rate_limited"


def test_bhashini_normalized_translation_and_service_fallback():
    def handler(request):
        if request.url.host == "config.test":
            assert request.headers["userid"] == "test-user"
            return httpx.Response(
                200,
                json={
                    "pipelineInferenceAPIEndPoint": {
                        "callbackUrl": "https://compute.test/pipeline",
                        "inferenceApiKey": {"name": "Authorization", "value": "temporary-token"},
                    },
                    "pipelineResponseConfig": [
                        {
                            "taskType": "translation",
                            "config": [
                                {
                                    "language": {"sourceLanguage": "hi", "targetLanguage": "en"},
                                    "serviceId": "available-service",
                                }
                            ],
                        }
                    ],
                },
            )
        assert request.headers["authorization"] == "temporary-token"
        return httpx.Response(200, json={"pipelineResponse": [{"output": [{"target": "Hello"}]}]})

    assert make_client(handler).translate_text("नमस्ते", "hi", "en") == "Hello"
