from collections import Counter
from datetime import datetime
import re


def calc_rari(reviews: list[dict]) -> dict:
    """
    Calculate Review Authenticity Risk Index (RARI).

    Signals checked:
    1. Sudden burst: many reviews with same/close date
    2. Duplicate/near-duplicate content (>= 10 same content)
    3. Generic short reviews
    4. Extremely high review count in short period (burst)

    Returns:
        {
          "score": 0-100,
          "level": "low"|"medium"|"high",
          "fake_likely": bool,
          "alerts": [...],
          "use_verified_only": bool,
          "verified_count": int,
        }
    """
    if not reviews:
        return {
            "score": 0, "level": "unknown", "fake_likely": False,
            "alerts": [], "use_verified_only": False, "verified_count": 0,
            "no_reviews": True,
        }

    alerts = []
    risk_score = 0

    contents = [r.get("content", "").strip().lower() for r in reviews]
    content_counts = Counter(contents)

    # --- Signal 1: Duplicate content (≥10 identical reviews) ---
    max_dup = max(content_counts.values()) if content_counts else 0
    exact_dups = sum(1 for c, cnt in content_counts.items() if cnt >= 10 and c)
    if exact_dups > 0:
        risk_score += 35
        alerts.append(f"{exact_dups} review(s) appear ≥10 times — likely duplicated content.")

    # --- Signal 2: Moderate duplicates (3-9 copies) ---
    moderate_dups = sum(1 for c, cnt in content_counts.items() if 3 <= cnt < 10 and c)
    if moderate_dups > 0:
        risk_score += min(moderate_dups * 5, 20)
        alerts.append(f"{moderate_dups} review(s) appear 3–9 times — some repetition detected.")

    # --- Signal 3: Review burst (many reviews on same date) ---
    dates = [r.get("date", "") for r in reviews if r.get("date")]
    date_counts = Counter(dates)
    max_same_day = max(date_counts.values()) if date_counts else 0
    if max_same_day >= 15:
        risk_score += 30
        alerts.append(f"{max_same_day} reviews posted on the same date — possible review burst.")
    elif max_same_day >= 8:
        risk_score += 15
        alerts.append(f"{max_same_day} reviews on one date — minor burst pattern detected.")

    # --- Signal 4: Generic/filler reviews ---
    GENERIC_PHRASES = [
        "good product", "nice product", "good", "nice", "ok", "okay",
        "awesome", "great", "perfect", "love it", "best product", "worst product",
        "bad", "not good", "not bad", "excellent",
    ]
    generic_count = sum(1 for c in contents if c in GENERIC_PHRASES)
    generic_ratio = generic_count / max(len(reviews), 1)
    if generic_ratio > 0.3:
        risk_score += 20
        alerts.append(f"{generic_count} reviews ({generic_ratio*100:.0f}%) are very generic one-liners.")
    elif generic_ratio > 0.1:
        risk_score += 8
        alerts.append(f"{generic_count} reviews are generic one-liners.")

    # --- Signal 5: Very short reviews dominate ---
    short_reviews = sum(1 for c in contents if len(c.split()) <= 3 and c)
    short_ratio = short_reviews / max(len(reviews), 1)
    if short_ratio > 0.4:
        risk_score += 10
        alerts.append(f"{short_ratio*100:.0f}% of reviews are extremely short (≤3 words).")

    risk_score = min(risk_score, 100)

    level = "low" if risk_score < 30 else ("medium" if risk_score < 60 else "high")
    fake_likely = risk_score >= 30

    # Count verified reviews
    verified_count = sum(1 for r in reviews if r.get("verified", False))

    return {
        "score": risk_score,
        "level": level,
        "fake_likely": fake_likely,
        "alerts": alerts,
        "use_verified_only": fake_likely,
        "verified_count": verified_count,
        "total_reviews": len(reviews),
    }


def filter_reviews_if_needed(reviews: list[dict], rari_result: dict) -> list[dict]:
    """If RARI says to use verified only, filter; otherwise return all."""
    if rari_result.get("use_verified_only") and rari_result.get("verified_count", 0) > 0:
        return [r for r in reviews if r.get("verified", False)]
    return reviews