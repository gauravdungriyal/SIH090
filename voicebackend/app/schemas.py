from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Intent(str, Enum):
    PRODUCT_DESCRIPTION = "PRODUCT_DESCRIPTION"
    PRODUCT_CORRECTION = "PRODUCT_CORRECTION"
    PRODUCT_QUESTION = "PRODUCT_QUESTION"
    UNCLEAR = "UNCLEAR"
    OFF_TOPIC = "OFF_TOPIC"


class Dimensions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    length: float | None = None
    width: float | None = None
    height: float | None = None
    unit: str | None = None

    @field_validator("length", "width", "height", mode="before")
    @classmethod
    def numeric_dimension(cls, value):
        if value is not None and (isinstance(value, bool) or not isinstance(value, int | float)):
            raise ValueError("Dimension must be numeric")
        return value


class Catalogue(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product_name: str | None = None
    category: str | None = None
    materials: list[str] = Field(default_factory=list)
    craft_type: str | None = None
    colors: list[str] = Field(default_factory=list)
    price: float | None = None
    currency: str | None = None
    stock_quantity: int | None = Field(default=None, strict=True)
    dimensions: Dimensions = Field(default_factory=Dimensions)
    weight: float | None = None
    weight_unit: str | None = None
    location: str | None = None
    is_handmade: bool | None = None
    special_features: list[str] = Field(default_factory=list)
    care_instructions: str | None = None
    description_en: str | None = None
    description_hi: str | None = None
    description_translations: dict[str, str] = Field(default_factory=dict)

    @field_validator("price", "weight", mode="before")
    @classmethod
    def numeric_value(cls, value):
        if value is not None and (isinstance(value, bool) or not isinstance(value, int | float)):
            raise ValueError("Value must be numeric")
        return value


class ClarificationQuestion(BaseModel):
    field: str
    question_en: str
    question_hi: str


class Processing(BaseModel):
    asr_provider: str | None = None
    translation_provider: str | None = None
    translation_pending: bool = False


class CatalogueResponse(BaseModel):
    request_id: str
    catalogue_id: str
    status: Literal["needs_clarification", "translation_pending", "draft_ready"]
    intent: Intent
    source_language: str
    original_transcript: str
    english_translation: str | None
    hindi_translation: str | None
    catalogue: Catalogue
    missing_fields: list[str]
    clarification_questions: list[ClarificationQuestion]
    warnings: list[str]
    processing: Processing
    created_at: datetime
    updated_at: datetime


class RejectedResponse(BaseModel):
    request_id: str
    intent: Literal["OFF_TOPIC", "UNCLEAR"]
    status: Literal["rejected"]
    message: str


class TranscriptionResponse(BaseModel):
    request_id: str
    source_language: str
    transcript: str
    audio_format: str
    sampling_rate_hz: int
    asr_provider: Literal["Gemini"] = "Gemini"


class TextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=10000)
    source_language: str
    output_languages: list[str] = Field(default_factory=lambda: ["hi", "en"], min_length=1)
    artisan_id: str | None = Field(default=None, max_length=100)
    session_id: str | None = Field(default=None, max_length=100)

    @field_validator("text")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Transcript must not be empty")
        return value.strip()


class ValidationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_language: str
    catalogue: Catalogue


class ValidationResponse(BaseModel):
    valid: bool
    missing_fields: list[str]
    errors: list[str]
    clarification_questions: list[ClarificationQuestion]


class CataloguePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    catalogue: Catalogue


GuidedField = Literal[
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
]


class ListResponse(BaseModel):
    items: list[CatalogueResponse]
    total: int
    page: int
    page_size: int
