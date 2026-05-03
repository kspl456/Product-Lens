
import re
import html


def clean_text(text: str) -> str:
    """Clean review/product text for NLP processing."""
    if not text:
        return ""
    text = html.unescape(text)
    text = re.sub(r"http\S+|www\.\S+", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    # Keep letters, digits, basic punctuation useful for sentiment
    text = re.sub(r"[^\w\s\.\,\!\?\'\-]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def clean_reviews(reviews: list[dict]) -> list[dict]:
    """Return reviews with cleaned content field."""
    cleaned = []
    for r in reviews:
        cr = dict(r)
        cr["content_clean"] = clean_text(r.get("content", ""))
        cr["title_clean"] = clean_text(r.get("title", ""))
        cr["full_clean"] = (cr["title_clean"] + " " + cr["content_clean"]).strip()
        cleaned.append(cr)
    return cleaned

