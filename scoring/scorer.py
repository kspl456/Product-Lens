from typing import Optional

# ── Weights ───────────────────────────────────────────────────
# Budget OFF: RARI 22%, Rating 32%, Sentiment 28%, Aspects 18%
# Budget ON:  RARI 20%, Price 12%, Rating 27%, Sentiment 23%, Aspects 18%

WEIGHTS_BUDGET_OFF = {
    "rari":      0.22,
    "rating":    0.32,
    "sentiment": 0.28,
    "aspects":   0.18,
    "price":     0.00,   # not used when budget is off
}

WEIGHTS_BUDGET_ON = {
    "rari":      0.20,
    "price":     0.12,
    "rating":    0.27,
    "sentiment": 0.23,
    "aspects":   0.18,
}


def score_price(price: Optional[float], all_prices: list[float], budget_priority: bool = False) -> float:
    """
    Price Score = (Min Price / Product Price) × 100
    Lower price → higher score.
    Only meaningful when budget_priority is ON.
    """
    if not budget_priority:
        return 50.0   # ignored in weighting when budget OFF, but keep a neutral value

    valid = [p for p in all_prices if p and p > 0]
    if not valid or not price or price <= 0:
        return 50.0

    min_p = min(valid)
    score = (min_p / price) * 100
    return round(min(score, 100.0), 2)


def score_rating(rating: Optional[float]) -> float:
    """
    Rating Score = (Star Rating / 5) × 100
    Converts Amazon 0–5 star rating to 0–100.
    """
    if rating is None:
        return 50.0
    rating = max(0.0, min(5.0, float(rating)))
    return round((rating / 5.0) * 100, 2)


def score_sentiment(overall_sentiment: dict) -> float:
    """
    Sentiment Score = ((Mean Compound Score + 1) / 2) × 100
    Mean compound is VADER compound averaged across reviews (range -1 to +1).
    Result is already scaled to 0–100.
    """
    mean = overall_sentiment.get("mean", 0.0)
    score = ((mean + 1) / 2) * 100
    return round(score, 2)


def score_aspects(aspect_sentiments: dict) -> float:
    """
    Aspect Score = ((Average Aspect Score + 1) / 2) × 100
    Each aspect score is -1 to +1; weighted by mention count.
    """
    if not aspect_sentiments:
        return 50.0

    total_weight = 0
    weighted_sum = 0.0
    for aspect, data in aspect_sentiments.items():
        score_raw = data.get("score", 0.0)          # -1 to +1
        score_100 = ((score_raw + 1) / 2) * 100     # convert to 0–100
        weight = data.get("mention_count", 1)
        weighted_sum += score_100 * weight
        total_weight += weight

    if total_weight == 0:
        return 50.0
    return round(weighted_sum / total_weight, 2)


def score_rari(rari_score: int) -> float:
    """
    RARI Score = Authenticity Score (0–100)
    rari_score from calc_rari() is a *risk* score (higher = more suspicious).
    Convert: Authenticity = 100 − Risk Percentage
    """
    return round(100 - rari_score, 2)


def compute_total_score(
    price_score: float,
    rating_score: float,
    sentiment_score: float,
    aspect_score: float,
    rari_score_val: float,
    budget_priority: bool = False,
) -> dict:
    """
    Budget OFF:
        Trust Score = 0.22×RARI + 0.32×Rating + 0.28×Sentiment + 0.18×Aspect

    Budget ON:
        Trust Score = 0.20×RARI + 0.12×Price + 0.27×Rating + 0.23×Sentiment + 0.18×Aspect
    """
    weights = WEIGHTS_BUDGET_ON if budget_priority else WEIGHTS_BUDGET_OFF

    # price_score is only included in components (and shown in UI) when budget is ON
    components = {
        "rating_score":    round(rating_score, 1),
        "sentiment_score": round(sentiment_score, 1),
        "aspect_score":    round(aspect_score, 1),
        "rari_trust":      round(rari_score_val, 1),
    }
    if budget_priority:
        components["price_score"] = round(price_score, 1)

    if budget_priority:
        tts = (
            weights["rari"]      * rari_score_val +
            weights["price"]     * price_score +
            weights["rating"]    * rating_score +
            weights["sentiment"] * sentiment_score +
            weights["aspects"]   * aspect_score
        )
    else:
        tts = (
            weights["rari"]      * rari_score_val +
            weights["rating"]    * rating_score +
            weights["sentiment"] * sentiment_score +
            weights["aspects"]   * aspect_score
        )

    return {
        "components":        components,
        "weights":           weights,
        "total_trust_score": round(tts, 1),
        "budget_priority":   budget_priority,
    }


def rank_products(products_results: list[dict]) -> list[dict]:
    sorted_products = sorted(
        products_results,
        key=lambda x: x.get("scoring", {}).get("total_trust_score", 0),
        reverse=True,
    )
    for i, p in enumerate(sorted_products):
        p["rank"] = i + 1
        p["recommended"] = (i == 0)
    return sorted_products