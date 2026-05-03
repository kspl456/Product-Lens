from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

_analyzer = SentimentIntensityAnalyzer()


def get_compound_score(text: str) -> float:
    """Return compound VADER score (-1 to 1)."""
    if not text:
        return 0.0
    return _analyzer.polarity_scores(text)["compound"]


def classify_sentiment(score: float) -> str:
    if score >= 0.05:
        return "positive"
    elif score <= -0.05:
        return "negative"
    return "neutral"


def analyze_reviews_overall(reviews: list[dict]) -> dict:
    """Compute overall sentiment stats across all reviews."""
    scores = []
    for r in reviews:
        text = r.get("full_clean", r.get("content_clean", ""))
        if text:
            scores.append(get_compound_score(text))

    if not scores:
        return {"mean": 0.0, "positive_pct": 0.0, "negative_pct": 0.0, "neutral_pct": 0.0}

    pos = sum(1 for s in scores if s >= 0.05)
    neg = sum(1 for s in scores if s <= -0.05)
    neu = len(scores) - pos - neg
    n = len(scores)

    return {
        "mean": round(sum(scores) / n, 4),
        "positive_pct": round(pos / n * 100, 1),
        "negative_pct": round(neg / n * 100, 1),
        "neutral_pct": round(neu / n * 100, 1),
        "count": n,
    }


def analyze_aspects_sentiment(aspect_texts: dict) -> dict:
    """
    Given {aspect: [text_snippets]}, return {aspect: {score, label, count}}.
    """
    results = {}
    for aspect, snippets in aspect_texts.items():
        if not snippets:
            continue
        scores = [get_compound_score(s) for s in snippets]
        mean = sum(scores) / len(scores)
        results[aspect] = {
            "score": round(mean, 4),
            "label": classify_sentiment(mean),
            "mention_count": len(snippets),
        }
    # Sort by mention count descending
    results = dict(sorted(results.items(), key=lambda x: -x[1]["mention_count"]))
    return results