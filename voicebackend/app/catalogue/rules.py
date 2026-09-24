"""Auditable, deterministic product parsing and safe text generation."""

import json
import math
import re
from importlib.resources import files

from app.schemas import Catalogue, ClarificationQuestion, Dimensions, Intent

VOCAB = json.loads(files("app.catalogue").joinpath("vocabulary.json").read_text(encoding="utf-8"))
OFF_TOPIC_MESSAGE = "I can only help create or update artisan product catalogue entries."
REQUIRED = ("product_name", "category", "materials", "price", "stock_quantity", "source_language")
LANGUAGES = {
    "as": "Assamese",
    "bn": "Bengali",
    "en": "English",
    "gu": "Gujarati",
    "hi": "Hindi",
    "kn": "Kannada",
    "ml": "Malayalam",
    "mr": "Marathi",
    "or": "Odia",
    "pa": "Punjabi",
    "ta": "Tamil",
    "te": "Telugu",
    "ur": "Urdu",
}
QUESTIONS = {
    "product_name": ("What is the product name?", "उत्पाद का नाम क्या है?"),
    "category": ("What type of product is it?", "यह किस प्रकार का उत्पाद है?"),
    "materials": ("Which material is used?", "कौन सी सामग्री इस्तेमाल हुई है?"),
    "craft_type": (
        "Which traditional craft or technique is used?",
        "कौन सी पारंपरिक कला या तकनीक इस्तेमाल हुई है?",
    ),
    "colors": ("What is its colour?", "इसका रंग क्या है?"),
    "dimensions": ("What are its dimensions?", "इसके माप क्या हैं?"),
    "price": ("What is its selling price?", "इसकी बिक्री कीमत क्या है?"),
    "currency": ("Which currency is the price in?", "कीमत किस मुद्रा में है?"),
    "stock_quantity": ("How many units are available?", "कितनी इकाइयाँ उपलब्ध हैं?"),
    "location": ("Where was it made?", "यह कहाँ बनाया गया था?"),
    "is_handmade": ("Is it handmade?", "क्या यह हाथ से बनाया गया है?"),
    "special_features": ("Are there any special features?", "क्या इसकी कोई विशेषताएँ हैं?"),
    "care_instructions": (
        "What care instructions should the buyer follow?",
        "खरीदार को इसकी देखभाल कैसे करनी चाहिए?",
    ),
    "weight": ("What is its weight?", "इसका वजन कितना है?"),
}
NUM = r"-?\d[\d,]*(?:\.\d+)?"
RUPEE = r"(?:₹|rs\.?|inr|rupees?|रुपये|रुपए|रुपया)"
UNIT_MAP = {
    "cm": "cm",
    "centimetre": "cm",
    "centimeter": "cm",
    "सेमी": "cm",
    "mm": "mm",
    "millimetre": "mm",
    "meter": "m",
    "metre": "m",
    "m": "m",
    "मीटर": "m",
    "inch": "in",
    "inches": "in",
    "इंच": "in",
    "ft": "ft",
    "feet": "ft",
    "फीट": "ft",
}
WEIGHT_MAP = {
    "g": "g",
    "gram": "g",
    "grams": "g",
    "ग्राम": "g",
    "kg": "kg",
    "kilogram": "kg",
    "किलो": "kg",
}
NUMBER_WORDS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "एक": 1,
    "दो": 2,
    "तीन": 3,
    "चार": 4,
    "पांच": 5,
    "पाँच": 5,
    "छह": 6,
    "सात": 7,
    "आठ": 8,
    "नौ": 9,
    "दस": 10,
    "ग्यारह": 11,
    "बारह": 12,
    "तेरह": 13,
    "चौदह": 14,
    "पंद्रह": 15,
    "सोलह": 16,
    "सत्रह": 17,
    "अठारह": 18,
    "उन्नीस": 19,
    "बीस": 20,
    "तीस": 30,
    "चालीस": 40,
    "पचास": 50,
    "सौ": 100,
    "हजार": 1000,
    "हज़ार": 1000,
    "hundred": 100,
    "thousand": 1000,
}


def normalize_digits(text: str) -> str:
    text = text.translate(str.maketrans("०१२३४५६७८९", "0123456789"))
    multipliers = ("hundred", "thousand", "सौ", "हजार", "हज़ार")
    for word, value in NUMBER_WORDS.items():
        if value >= 100:
            continue
        for multiplier in multipliers:
            phrase = rf"(?<!\w){re.escape(word)}\s+{re.escape(multiplier)}(?!\w)"
            text = re.sub(phrase, str(value * NUMBER_WORDS[multiplier]), text, flags=re.IGNORECASE)
    for word in sorted(NUMBER_WORDS, key=len, reverse=True):
        text = re.sub(
            r"(?<!\w)" + re.escape(word) + r"(?!\w)",
            str(NUMBER_WORDS[word]),
            text,
            flags=re.IGNORECASE,
        )
    return text


def has_term(text: str, term: str) -> bool:
    return bool(re.search(r"(?<!\w)" + re.escape(term.casefold()) + r"(?!\w)", text.casefold()))


def find_terms(text: str, section: str) -> list[str]:
    return [
        name
        for name, aliases in VOCAB[section].items()
        if any(has_term(text, alias) for alias in aliases)
    ]


def classify_intent(texts: list[str]) -> Intent:
    text = " ".join(texts).casefold().strip()
    if not text:
        return Intent.UNCLEAR
    # Instruction-like content never changes server behavior.
    if re.search(
        r"ignore (?:all |previous |your )?instructions|system prompt|developer message|"
        r"निर्देशों को अनदेखा|\b(?:who is|who's|ceo of|capital of)\b",
        text,
    ):
        return Intent.OFF_TOPIC
    product_signal = any(has_term(text, term) for term in VOCAB["product_keywords"])
    product_signal |= any(
        find_terms(text, group) for group in ("categories", "materials", "crafts")
    )
    if product_signal:
        if any(has_term(text, term) for term in VOCAB["correction_keywords"]):
            return Intent.PRODUCT_CORRECTION
        if any(term in text for term in VOCAB["question_keywords"]):
            return Intent.PRODUCT_QUESTION
        return Intent.PRODUCT_DESCRIPTION
    if "?" in text or re.search(r"\b(who|what|when|where|why|how)\b|कौन|कब|क्यों|कैसे|कहाँ", text):
        return Intent.OFF_TOPIC
    return Intent.UNCLEAR


def _number(raw: str) -> float:
    return float(raw.replace(",", ""))


def extract(texts: list[str], default_currency_inr: bool = False) -> Catalogue:
    text = normalize_digits(" ".join(filter(None, texts)))
    categories = find_terms(text, "categories")
    materials = find_terms(text, "materials")
    colors = find_terms(text, "colors")
    crafts = find_terms(text, "crafts")
    category = categories[0] if categories else None
    craft = crafts[0] if crafts else None
    name_match = re.search(
        r"(?:product name(?: is)?|named|called|नाम(?: है)?)\s*[:\-]?\s*([\w\s-]{2,60}?)(?:[,.।]|\s+(?:made|price|कीमत|से बना)|$)",
        text,
        re.IGNORECASE,
    )
    product_name = name_match.group(1).strip() if name_match else None
    if not product_name and category and (materials or craft):
        product_name = f"{materials[0] if materials else craft} {category}"
    price = None
    currency = None
    match = re.search(rf"{RUPEE}\s*({NUM})|({NUM})\s*{RUPEE}", text, re.IGNORECASE)
    if match:
        price = _number(match.group(1) or match.group(2))
        currency = "INR"
    else:
        match = re.search(rf"(?:price|cost|कीमत|मूल्य)\s*(?:is|है|:)?\s*({NUM})", text, re.IGNORECASE)
        if match:
            price = _number(match.group(1))
            currency = "INR" if default_currency_inr else None
    quantity = None
    match = re.search(
        rf"(?:stock|quantity|available|units?|pieces?|मात्रा|उपलब्ध|पीस)\s*(?:is|है|:)?\s*({NUM})|({NUM})\s*(?:pieces?|units?|पीस|इकाइयाँ|नग)",
        text,
        re.IGNORECASE,
    )
    if match:
        value = _number(match.group(1) or match.group(2))
        quantity = int(value) if value.is_integer() else value
    unit_pattern = "|".join(sorted(map(re.escape, UNIT_MAP), key=len, reverse=True))
    dims = Dimensions()
    match = re.search(
        rf"({NUM})\s*[x×]\s*({NUM})(?:\s*[x×]\s*({NUM}))?\s*({unit_pattern})\b", text, re.IGNORECASE
    )
    if match:
        dims = Dimensions(
            length=_number(match.group(1)),
            width=_number(match.group(2)),
            height=_number(match.group(3)) if match.group(3) else None,
            unit=UNIT_MAP[match.group(4).casefold()],
        )
    else:
        values = {}
        for field, labels in {
            "length": "length|लंबाई",
            "width": "width|चौड़ाई",
            "height": "height|ऊंचाई",
        }.items():
            match = re.search(
                rf"(?:{labels})\s*(?:is|है|:)?\s*({NUM})\s*({unit_pattern})", text, re.IGNORECASE
            )
            if match:
                values[field] = _number(match.group(1))
                values["unit"] = UNIT_MAP[match.group(2).casefold()]
        dims = Dimensions(**values)
    weight, weight_unit = None, None
    weight_units = "|".join(sorted(map(re.escape, WEIGHT_MAP), key=len, reverse=True))
    match = re.search(
        rf"(?:weight|वजन)\s*(?:is|है|:)?\s*({NUM})\s*({weight_units})\b", text, re.IGNORECASE
    )
    if match:
        weight, weight_unit = _number(match.group(1)), WEIGHT_MAP[match.group(2).casefold()]
    location = None
    match = re.search(
        r"(?:made in|crafted in|में बना(?:या)?|में तैयार)\s+([\w\s-]{2,50}?)(?:[,.।]|\s+(?:and|with|price|कीमत|है)|$)",
        text,
        re.IGNORECASE,
    )
    if match:
        location = match.group(1).strip()
    if not location:
        match = re.search(r"([\w-]{2,40})\s+में\s+(?:बना|बनी|बनाया|तैयार)", text)
        if match:
            location = match.group(1)
    handmade = None
    if any(has_term(text, term) for term in VOCAB["handmade_negative"]):
        handmade = False
    elif any(has_term(text, term) for term in VOCAB["handmade_positive"]):
        handmade = True
    care = None
    match = re.search(
        r"(?:care instructions?|wash|clean|देखभाल|धोएं)\s*(?:are|:|है)?\s+([^,.।]{3,150})",
        text,
        re.IGNORECASE,
    )
    if match:
        care = match.group(1).strip()
    features = []
    match = re.search(
        r"(?:special features?|विशेषताएँ)\s*(?:are|:|हैं)?\s+([^,.।]{3,150})", text, re.IGNORECASE
    )
    if match:
        features = [match.group(1).strip()]
    return Catalogue(
        product_name=product_name,
        category=category,
        materials=materials,
        craft_type=craft,
        colors=colors,
        price=price,
        currency=currency,
        stock_quantity=quantity,
        dimensions=dims,
        weight=weight,
        weight_unit=weight_unit,
        location=location,
        is_handmade=handmade,
        special_features=features,
        care_instructions=care,
    )


def validate_catalogue(catalogue: Catalogue, source_language: str) -> tuple[list[str], list[str]]:
    missing = [
        field
        for field in REQUIRED
        if (field == "source_language" and not source_language)
        or (
            field != "source_language"
            and (getattr(catalogue, field) is None or getattr(catalogue, field) == [])
        )
    ]
    if catalogue.price is not None and not catalogue.currency:
        missing.append("currency")
    errors = []
    if source_language not in LANGUAGES:
        errors.append("Unsupported source language")
    if catalogue.price is not None and (not math.isfinite(catalogue.price) or catalogue.price <= 0):
        errors.append("Price must be positive")
    if catalogue.stock_quantity is not None and (
        isinstance(catalogue.stock_quantity, bool) or catalogue.stock_quantity < 0
    ):
        errors.append("Stock quantity must be a non-negative integer")
    for field in ("length", "width", "height"):
        value = getattr(catalogue.dimensions, field)
        if value is not None and (not math.isfinite(value) or value <= 0):
            errors.append(f"{field.capitalize()} must be positive")
    if any(
        getattr(catalogue.dimensions, field) is not None for field in ("length", "width", "height")
    ) and catalogue.dimensions.unit not in set(UNIT_MAP.values()):
        errors.append("A supported dimension unit is required")
    if catalogue.weight is not None and (
        not math.isfinite(catalogue.weight) or catalogue.weight <= 0
    ):
        errors.append("Weight must be positive")
    if catalogue.weight is not None and catalogue.weight_unit not in set(WEIGHT_MAP.values()):
        errors.append("A supported weight unit is required")
    if catalogue.product_name is not None and not catalogue.product_name.strip():
        errors.append("Product name must not be blank")
    return missing, errors


def questions_for(fields: list[str]) -> list[ClarificationQuestion]:
    return [
        ClarificationQuestion(
            field=field, question_en=QUESTIONS[field][0], question_hi=QUESTIONS[field][1]
        )
        for field in fields
        if field in QUESTIONS
    ]


def _hindi_label(value: str, section: str) -> str:
    aliases = VOCAB[section].get(value, [])
    return next((alias for alias in aliases if re.search(r"[\u0900-\u097f]", alias)), value)


def generate_descriptions(c: Catalogue) -> Catalogue:
    en = []
    hi = []
    name_en = c.product_name or c.category
    name_hi = c.product_name or c.category
    if c.category and c.materials and c.product_name == f"{c.materials[0]} {c.category}":
        name_hi = (
            f"{_hindi_label(c.materials[0], 'materials')} {_hindi_label(c.category, 'categories')}"
        )
    elif c.category and c.craft_type and c.product_name == f"{c.craft_type} {c.category}":
        name_hi = f"{_hindi_label(c.craft_type, 'crafts')} {_hindi_label(c.category, 'categories')}"
    elif c.product_name == c.category and c.category:
        name_hi = _hindi_label(c.category, "categories")
    if name_en:
        handmade_en = "handmade " if c.is_handmade is True else ""
        handmade_hi = "हस्तनिर्मित " if c.is_handmade is True else ""
        en.append(f"This is a {handmade_en}{name_en}.")
        hi.append(f"यह {handmade_hi}{name_hi} है।")
    if c.materials:
        en.append(f"Made using {', '.join(c.materials)}.")
        hi.append(f"{', '.join(_hindi_label(x, 'materials') for x in c.materials)} से बनाया गया है।")
    if c.craft_type:
        en.append(f"It features {c.craft_type}.")
        hi.append(f"इसमें {_hindi_label(c.craft_type, 'crafts')} कला का उपयोग किया गया है।")
    if c.colors:
        en.append(f"Available in {', '.join(c.colors)}.")
        hi.append(f"{', '.join(_hindi_label(x, 'colors') for x in c.colors)} रंग में उपलब्ध है।")
    if c.location:
        en.append(f"Crafted in {c.location}.")
        hi.append(f"{c.location} में तैयार किया गया है।")
    if c.price is not None and c.currency:
        display = f"{c.price:g}"
        amount = f"₹{display}" if c.currency == "INR" else f"{display} {c.currency or ''}".strip()
        en.append(f"Priced at {amount}.")
        hi.append(f"इसकी कीमत {amount} है।")
    c.description_en = " ".join(en) or None
    c.description_hi = " ".join(hi) or None
    c.description_translations = {}
    return c
