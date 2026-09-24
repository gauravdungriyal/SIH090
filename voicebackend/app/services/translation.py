"""Best-effort translation for product drafts during temporary Gemini outages."""

from dataclasses import dataclass, field

from app.gemini.client import GeminiClient, GeminiError
from app.schemas import Catalogue

RETRYABLE_TRANSLATION_ERRORS = {"timeout", "service_unavailable", "rate_limited"}
PENDING_TRANSLATION_WARNING = (
    "Gemini translation is temporarily unavailable. The original transcript is saved; "
    "retry translations before publishing."
)


@dataclass
class CoreTranslations:
    english: str | None = None
    hindi: str | None = None
    used_gemini: bool = False
    warnings: list[str] = field(default_factory=list)

    @property
    def pending(self) -> bool:
        return not self.english or not self.hindi


def translate_core(text: str, source_language: str, gemini: GeminiClient) -> CoreTranslations:
    result = CoreTranslations(
        english=text if source_language == "en" else None,
        hindi=text if source_language == "hi" else None,
    )
    for language, attribute in (("en", "english"), ("hi", "hindi")):
        if getattr(result, attribute) is not None:
            continue
        try:
            translated = gemini.translate_text(text, source_language, language)
        except GeminiError as exc:
            if exc.code not in RETRYABLE_TRANSLATION_ERRORS:
                raise
            result.warnings.append(PENDING_TRANSLATION_WARNING)
            break
        setattr(result, attribute, translated)
        result.used_gemini = True
    return result


def draft_status(missing_fields: list[str], translation_pending: bool) -> str:
    if missing_fields:
        return "needs_clarification"
    return "translation_pending" if translation_pending else "draft_ready"


def translate_descriptions(
    catalogue: Catalogue, output_languages: list[str], gemini: GeminiClient
) -> bool:
    """Fill requested description languages; return whether some remain pending."""
    if not catalogue.description_en:
        return False
    pending = False
    for language in output_languages:
        if language in ("en", "hi") or language in catalogue.description_translations:
            continue
        try:
            catalogue.description_translations[language] = gemini.translate_text(
                catalogue.description_en, "en", language
            )
        except GeminiError as exc:
            if exc.code not in RETRYABLE_TRANSLATION_ERRORS:
                raise
            pending = True
            break
    return pending or any(
        language not in ("en", "hi") and language not in catalogue.description_translations
        for language in output_languages
    )
