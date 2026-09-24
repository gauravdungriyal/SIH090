"""Small ULCA pipeline adapter. No transcript or credential is logged."""

import base64
import logging
import time
from dataclasses import dataclass

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


class BhashiniError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 502):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class PipelineConfig:
    compute_url: str
    compute_token: str
    services: dict[str, list[dict]]


class BhashiniClient:
    def __init__(self, settings: Settings, http_client: httpx.Client | None = None):
        self.settings = settings
        self.http = http_client or httpx.Client(
            timeout=httpx.Timeout(settings.request_timeout_seconds, connect=5.0)
        )

    def _post(self, url: str, headers: dict, body: dict) -> dict:
        for attempt in range(3):
            try:
                response = self.http.post(url, headers=headers, json=body)
                if response.status_code in (401, 403):
                    raise BhashiniError(
                        "authentication_failed", "Bhashini authentication failed", 502
                    )
                if response.status_code == 429:
                    if attempt < 2:
                        time.sleep(0.25 * (2**attempt))
                        continue
                    raise BhashiniError("rate_limited", "Bhashini rate limit reached", 503)
                if response.status_code >= 500:
                    if attempt < 2:
                        time.sleep(0.25 * (2**attempt))
                        continue
                    raise BhashiniError("service_unavailable", "Bhashini service unavailable", 503)
                if response.status_code >= 400:
                    raise BhashiniError("invalid_request", "Bhashini rejected the request", 422)
                try:
                    data = response.json()
                except ValueError as exc:
                    raise BhashiniError("malformed_response", "Invalid Bhashini response") from exc
                if not isinstance(data, dict):
                    raise BhashiniError("malformed_response", "Invalid Bhashini response")
                return data
            except httpx.TimeoutException as exc:
                if attempt == 2:
                    logger.warning("Bhashini request timed out")
                    raise BhashiniError("timeout", "Bhashini request timed out", 504) from exc
                time.sleep(0.25 * (2**attempt))
            except httpx.RequestError as exc:
                if attempt == 2:
                    logger.warning("Bhashini connection failed")
                    raise BhashiniError(
                        "service_unavailable", "Bhashini service unavailable", 503
                    ) from exc
                time.sleep(0.25 * (2**attempt))
        raise BhashiniError("service_unavailable", "Bhashini service unavailable", 503)

    def get_pipeline_config(self, tasks: list[dict]) -> PipelineConfig:
        cfg = self.settings
        if not all((cfg.bhashini_user_id, cfg.bhashini_api_key, cfg.bhashini_pipeline_id)):
            raise BhashiniError("not_configured", "Bhashini credentials are not configured", 503)
        response = self._post(
            cfg.bhashini_config_url,
            {"userID": cfg.bhashini_user_id, "ulcaApiKey": cfg.bhashini_api_key},
            {
                "pipelineTasks": tasks,
                "pipelineRequestConfig": {"pipelineId": cfg.bhashini_pipeline_id},
            },
        )
        endpoint = response.get("pipelineInferenceAPIEndPoint") or {}
        if not isinstance(endpoint, dict):
            raise BhashiniError("malformed_response", "Invalid Bhashini pipeline configuration")
        token = endpoint.get("inferenceApiKey") or {}
        if isinstance(token, dict):
            token = token.get("value") or token.get("Authorization")
        url = endpoint.get("callbackUrl") or cfg.bhashini_compute_url
        entries = response.get("pipelineResponseConfig")
        if not isinstance(entries, list) or not isinstance(token, str) or not token:
            raise BhashiniError("malformed_response", "Invalid Bhashini pipeline configuration")
        services = {}
        for entry in entries:
            if isinstance(entry, dict) and isinstance(entry.get("config"), list):
                services[entry.get("taskType", "")] = entry["config"]
        return PipelineConfig(url, token, services)

    @staticmethod
    def _service(
        config: PipelineConfig, task: str, source: str, target: str | None, preferred: str
    ) -> str:
        matches = []
        for option in config.services.get(task, []):
            lang = option.get("language", {})
            if lang.get("sourceLanguage") == source and (
                target is None or lang.get("targetLanguage") == target
            ):
                matches.append(option.get("serviceId"))
        if preferred in matches:
            return preferred
        for service in matches:
            if service:
                return service
        raise BhashiniError(
            "unsupported_language", "Bhashini model does not support this language pair", 422
        )

    def _compute(
        self,
        config: PipelineConfig,
        task: str,
        service_id: str,
        source: str,
        target: str | None,
        input_data: dict,
        extra_config: dict | None = None,
    ) -> str:
        language = {"sourceLanguage": source}
        if target:
            language["targetLanguage"] = target
        body = {
            "pipelineTasks": [
                {
                    "taskType": task,
                    "config": {
                        "language": language,
                        "serviceId": service_id,
                        **(extra_config or {}),
                    },
                }
            ],
            "inputData": input_data,
        }
        response = self._post(config.compute_url, {"Authorization": config.compute_token}, body)
        try:
            result = response["pipelineResponse"][0]["output"][0]
            value = result["source"] if task == "asr" else result["target"]
            if not isinstance(value, str):
                raise TypeError("invalid result")
            if not value.strip():
                if task == "asr":
                    raise BhashiniError("empty_transcript", "No speech was recognized", 422)
                raise ValueError("empty result")
            return value.strip()
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise BhashiniError("malformed_response", "Invalid Bhashini response") from exc

    def transcribe_audio(
        self, audio: bytes, source_language: str, audio_format: str, sampling_rate: int
    ) -> str:
        config = self.get_pipeline_config(
            [{"taskType": "asr", "config": {"language": {"sourceLanguage": source_language}}}]
        )
        service = self._service(
            config, "asr", source_language, None, self.settings.bhashini_asr_service_id
        )
        try:
            return self._compute(
                config,
                "asr",
                service,
                source_language,
                None,
                {"audio": [{"audioContent": base64.b64encode(audio).decode("ascii")}]},
                {"audioFormat": audio_format, "samplingRate": sampling_rate},
            )
        except BhashiniError as exc:
            if exc.code == "invalid_request":
                raise BhashiniError("invalid_audio", "Bhashini rejected the audio", 422) from exc
            raise

    def translate_text(self, text: str, source_language: str, target_language: str) -> str:
        if source_language == target_language:
            return text
        config = self.get_pipeline_config(
            [
                {
                    "taskType": "translation",
                    "config": {
                        "language": {
                            "sourceLanguage": source_language,
                            "targetLanguage": target_language,
                        }
                    },
                }
            ]
        )
        service = self._service(
            config,
            "translation",
            source_language,
            target_language,
            self.settings.bhashini_translation_service_id,
        )
        return self._compute(
            config,
            "translation",
            service,
            source_language,
            target_language,
            {"input": [{"source": text}]},
        )

    def transliterate_text(self, text: str, source_language: str, target_language: str) -> str:
        config = self.get_pipeline_config(
            [
                {
                    "taskType": "transliteration",
                    "config": {
                        "language": {
                            "sourceLanguage": source_language,
                            "targetLanguage": target_language,
                        }
                    },
                }
            ]
        )
        service = self._service(
            config,
            "transliteration",
            source_language,
            target_language,
            self.settings.bhashini_transliteration_service_id,
        )
        return self._compute(
            config,
            "transliteration",
            service,
            source_language,
            target_language,
            {"input": [{"source": text}]},
        )

    def process_asr_translation_pipeline(
        self, audio: bytes, source_language: str, audio_format: str, sampling_rate: int
    ) -> dict:
        transcript = self.transcribe_audio(audio, source_language, audio_format, sampling_rate)
        return {
            "original_transcript": transcript,
            "english_translation": self.translate_text(transcript, source_language, "en"),
            "hindi_translation": self.translate_text(transcript, source_language, "hi"),
        }
