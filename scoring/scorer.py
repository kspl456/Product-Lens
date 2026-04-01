"""
Scoring Engine — Total Trust Score (TTS)

Components:
  1. Price Score       (15%) — relative value vs other products in comparison set
  2. Rating Score      (25%) — normalized star rating 0-5
  3. Sentiment Score   (30%) — overall review sentiment
  4. Aspect Score      (20%) — weighted average of top aspect sentiments
  5. RARI Penalty      (10%) — authenticity modifier

All individual scores are 0-100. TTS is 0-100.
"""

from typing import Optional


# ---------- Individual scorers ----------

def score_price(price: Optional[float], all_prices: list[float]) -> float:
    """Lower price among compared products = higher score."""
    valid = [p for p in all_prices if p and p > 0]
    if not valid or not price or price <= 0:
        return 50.0  # neutral if missing
    min_p, max_p = min(valid), max(valid)
    if max_p == min_p:
        return 75.0  # only one price point — decent default
    # Invert: cheapest gets 100, most expensive gets 0
    score = (1 - (price - min_p) / (max_p - min_p)) * 100
    return round(score, 2)


def score_rating(rating: Optional[float]) -> float:
    """Normalize 0-5 star rating to 0-100."""
    if rating is None:
        return 50.0
    rating = max(0.0, min(5.0, float(rating)))
    return round((rating / 5.0) * 100, 2)


def score_sentiment(overall_sentiment: dict) -> float:
    """
    Convert overall sentiment stats to 0-100.
    Uses mean compound score (-1 to 1) shifted to 0-100.
    """
    mean = overall_sentiment.get("mean", 0.0)
    # Shift from [-1,1] to [0,100]
    return round((mean + 1) / 2 * 100, 2)


def score_aspects(aspect_sentiments: dict) -> float:
    """
    Average of top-mentioned aspect scores (0-100).
    Weights each aspect by mention count.
    """
    if not aspect_sentiments:
        return 50.0

    total_weight = 0
    weighted_sum = 0.0
    for aspect, data in aspect_sentiments.items():
        score_raw = data.get("score", 0.0)  # -1 to 1
        score_100 = (score_raw + 1) / 2 * 100
        weight = data.get("mention_count", 1)
        weighted_sum += score_100 * weight
        total_weight += weight

    if total_weight == 0:
        return 50.0
    return round(weighted_sum / total_weight, 2)


def score_rari(rari_score: int) -> float:
    """Convert RARI risk (0-100, higher = riskier) to a 0-100 trustworthiness score."""
    return round(100 - rari_score, 2)


# ---------- Total Trust Score ----------

WEIGHTS = {
    "price":     0.15,
    "rating":    0.25,
    "sentiment": 0.30,
    "aspects":   0.20,
    "rari":      0.10,
}

def compute_total_score(
    price_score: float,
    rating_score: float,
    sentiment_score: float,
    aspect_score: float,
    rari_score_val: float,
) -> dict:
    """Return component scores and final TTS."""
    components = {
        "price_score":     round(price_score, 1),
        "rating_score":    round(rating_score, 1),
        "sentiment_score": round(sentiment_score, 1),
        "aspect_score":    round(aspect_score, 1),
        "rari_trust":      round(rari_score_val, 1),
    }
    tts = (
        WEIGHTS["price"]     * price_score +
        WEIGHTS["rating"]    * rating_score +
        WEIGHTS["sentiment"] * sentiment_score +
        WEIGHTS["aspects"]   * aspect_score +
        WEIGHTS["rari"]      * rari_score_val
    )
    return {
        "components": components,
        "weights": WEIGHTS,
        "total_trust_score": round(tts, 1),
    }


def rank_products(products_results: list[dict]) -> list[dict]:
    """
    Given list of product result dicts (each with 'total_trust_score'),
    return sorted list with rank and recommendation flag.
    """
    sorted_products = sorted(
        products_results,
        key=lambda x: x.get("scoring", {}).get("total_trust_score", 0),
        reverse=True
    )
    for i, p in enumerate(sorted_products):
        p["rank"] = i + 1
        p["recommended"] = (i == 0)
    return sorted_products