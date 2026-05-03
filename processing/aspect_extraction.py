import spacy

nlp = spacy.load("en_core_web_sm")

# Category-aware aspect keywords
CATEGORY_ASPECTS = {
    "electronics": [
        "battery", "camera", "performance", "display", "screen",
        "sound", "audio", "speaker", "processor", "speed", "storage",
        "build", "design", "charging", "connectivity", "wifi", "bluetooth",
        "software", "app", "interface", "image", "video", "quality",
        "heating", "temperature", "weight", "size", "price", "value",
        "delivery", "packaging", "warranty", "support",
    ],
    "appliances": [
        "noise", "efficiency", "energy", "capacity", "performance",
        "installation", "cleaning", "maintenance", "size", "weight",
        "temperature", "heating", "cooling", "washing", "drying",
        "build", "quality", "design", "control", "setting",
        "price", "value", "delivery", "warranty", "support",
    ],
    "fashion": [
        "fit", "size", "color", "fabric", "material", "comfort",
        "style", "design", "stitching", "quality", "durability",
        "washing", "color", "look", "feel", "texture",
        "price", "value", "delivery", "packaging",
    ],
    "general": [
        "quality", "price", "value", "delivery", "packaging",
        "build", "design", "performance", "durability", "support",
        "size", "weight", "material", "color",
    ],
}

# Flatten all aspects for lookup
ALL_ASPECTS = set()
for aspects in CATEGORY_ASPECTS.values():
    ALL_ASPECTS.update(aspects)


def get_aspects_for_category(category: str) -> list[str]:
    cat_lower = category.lower()
    for key in CATEGORY_ASPECTS:
        if key in cat_lower:
            return CATEGORY_ASPECTS[key]
    return CATEGORY_ASPECTS["general"]


def extract_aspects(text: str, category: str = "general") -> list[str]:
    """Extract aspect keywords mentioned in text."""
    if not text:
        return []
    
    relevant_aspects = get_aspects_for_category(category)
    doc = nlp(text.lower())
    found = set()

    # Check noun chunks and tokens against aspect list
    for chunk in doc.noun_chunks:
        for aspect in relevant_aspects:
            if aspect in chunk.text:
                found.add(aspect)

    for token in doc:
        if token.text in relevant_aspects and not token.is_stop:
            found.add(token.text)

    return list(found)


def extract_aspects_bulk(reviews: list[dict], category: str = "general") -> dict:
    """
    Extract aspects from all reviews and collect associated text snippets.
    Returns {aspect: [sentence/snippet, ...]}
    """
    aspect_texts: dict[str, list[str]] = {}
    relevant_aspects = get_aspects_for_category(category)

    for review in reviews:
        text = review.get("full_clean", review.get("content_clean", ""))
        if not text:
            continue
        doc = nlp(text.lower())
        for sent in doc.sents:
            sent_text = sent.text
            for aspect in relevant_aspects:
                if aspect in sent_text:
                    aspect_texts.setdefault(aspect, []).append(sent_text)

    return aspect_texts
