from flask import Flask, render_template, request, jsonify
import traceback

from data_ingestion.serp_fetcher import fetch_product_details
from processing.cleaner import clean_reviews
from processing.aspect_extraction import extract_aspects_bulk
from processing.sentiment import analyze_reviews_overall, analyze_aspects_sentiment
from authenticity.rari import calc_rari, filter_reviews_if_needed
from scoring.scorer import (
    score_price, score_rating, score_sentiment,
    score_aspects, score_rari, compute_total_score, rank_products
)
from database.mongo import get_cached_product, save_product

app = Flask(__name__)


def process_product(url: str, all_prices_ref: list) -> dict:
    """Full pipeline for one product URL."""
    from data_ingestion.serp_fetcher import extract_asin
    asin = extract_asin(url)
    if not asin:
        return {"error": f"Could not extract ASIN from URL: {url}", "url": url}

    # --- Cache check ---
    cached = get_cached_product(asin)
    if cached:
        raw = cached
        raw["_from_cache"] = True
    else:
        raw = fetch_product_details(url)
        raw["_from_cache"] = False

    # --- Clean reviews ---
    cleaned_reviews = clean_reviews(raw.get("reviews", []))

    # --- RARI ---
    rari_result = calc_rari(cleaned_reviews)

    # --- Filter reviews if needed ---
    analysis_reviews = filter_reviews_if_needed(cleaned_reviews, rari_result)

    # --- Aspect extraction + sentiment ---
    category = raw.get("category", "general")
    aspect_texts = extract_aspects_bulk(analysis_reviews, category)
    aspect_sentiments = analyze_aspects_sentiment(aspect_texts)

    # --- Overall sentiment ---
    overall_sentiment = analyze_reviews_overall(analysis_reviews)

    # --- Save to DB (raw + processed summary) ---
    save_doc = dict(raw)
    save_doc["reviews"] = raw.get("reviews", [])  # store original
    save_doc["rari"] = rari_result
    save_doc["overall_sentiment"] = overall_sentiment
    save_doc["aspect_sentiments"] = aspect_sentiments
    if not raw.get("_from_cache"):
        save_product(save_doc)

    # Collect price for cross-product scoring (filled later)
    price = raw.get("price")
    if price:
        all_prices_ref.append(price)

    no_reviews = len(raw.get("reviews", [])) == 0

    return {
        "asin": asin,
        "url": url,
        "title": raw.get("title", "Unknown"),
        "price": price,
        "seller": raw.get("seller", "Unknown"),
        "rating": raw.get("rating"),
        "category": category,
        "rari": rari_result,
        "overall_sentiment": overall_sentiment,
        "aspect_sentiments": aspect_sentiments,
        "total_reviews": raw.get("total_reviews", 0),
        "thumbnail": raw.get("thumbnail"),
        "no_reviews": no_reviews,
        "_from_cache": raw.get("_from_cache", False),
    }


def process_product_from_raw(asin: str, url: str, raw: dict, all_prices_ref: list) -> dict:
    """Run the analysis pipeline on already-fetched raw product data."""
    # --- Clean reviews ---
    cleaned_reviews = clean_reviews(raw.get("reviews", []))

    # --- RARI ---
    rari_result = calc_rari(cleaned_reviews)

    # --- Filter reviews if needed ---
    analysis_reviews = filter_reviews_if_needed(cleaned_reviews, rari_result)

    # --- Aspect extraction + sentiment ---
    category = raw.get("category", "general")
    aspect_texts = extract_aspects_bulk(analysis_reviews, category)
    aspect_sentiments = analyze_aspects_sentiment(aspect_texts)

    # --- Overall sentiment ---
    overall_sentiment = analyze_reviews_overall(analysis_reviews)

    # --- Save to DB ---
    save_doc = dict(raw)
    save_doc["reviews"] = raw.get("reviews", [])
    save_doc["rari"] = rari_result
    save_doc["overall_sentiment"] = overall_sentiment
    save_doc["aspect_sentiments"] = aspect_sentiments
    if not raw.get("_from_cache"):
        save_product(save_doc)

    price = raw.get("price")
    if price:
        all_prices_ref.append(price)

    no_reviews = len(raw.get("reviews", [])) == 0

    return {
        "asin": asin,
        "url": url,
        "title": raw.get("title", "Unknown"),
        "price": price,
        "seller": raw.get("seller", "Unknown"),
        "rating": raw.get("rating"),
        "category": category,
        "rari": rari_result,
        "overall_sentiment": overall_sentiment,
        "aspect_sentiments": aspect_sentiments,
        "total_reviews": raw.get("total_reviews", 0),
        "thumbnail": raw.get("thumbnail"),
        "no_reviews": no_reviews,
        "_from_cache": raw.get("_from_cache", False),
    }


def apply_scores(products: list[dict], all_prices: list[float]) -> list[dict]:
    """Compute and attach scoring to each product dict."""

    # --- Find shared features across all valid products ---
    # Only features that appear in ALL products are used for aspect scoring.
    # This ensures fair comparison — a product with more features isn't rewarded.
    valid_products = [p for p in products if "error" not in p]
    if valid_products:
        # Get feature sets for each product
        feature_sets = [
            set(p.get("aspect_sentiments", {}).keys())
            for p in valid_products
        ]
        # Intersection = only features mentioned in every product
        shared_features = set.intersection(*feature_sets) if feature_sets else set()
    else:
        shared_features = set()

    for p in products:
        if "error" in p:
            p["scoring"] = {"total_trust_score": 0, "components": {}, "weights": {}}
            p["shared_features"] = []
            continue

        ps = score_price(p.get("price"), all_prices)
        rs = score_rating(p.get("rating"))
        ss = score_sentiment(p.get("overall_sentiment", {}))

        # Score only on shared features for fair cross-product comparison
        all_aspects = p.get("aspect_sentiments", {})
        shared_aspects = {k: v for k, v in all_aspects.items() if k in shared_features}
        # Fall back to all aspects if no shared features found (e.g. single product)
        aspects_for_scoring = shared_aspects if shared_aspects else all_aspects
        as_ = score_aspects(aspects_for_scoring)

        rari_trust = score_rari(p.get("rari", {}).get("score", 0))
        p["scoring"] = compute_total_score(ps, rs, ss, as_, rari_trust)

        # Attach shared features list so frontend can highlight them
        p["shared_features"] = list(shared_features)

    return products


@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")


def _is_new_product(raw: dict) -> bool:
    """A product is considered new if it has no reviews and no rating."""
    has_reviews = bool(raw.get("reviews"))
    has_rating  = bool(raw.get("rating"))
    has_total   = raw.get("total_reviews", 0) > 0
    return not has_reviews and not has_rating and not has_total


def _normalise_category(cat: str) -> str:
    """Reduce category to a comparable root word for matching."""
    if not cat:
        return "general"
    cat = cat.lower().strip()
    # Map sub-categories to their root
    mapping = {
        "mobile": "electronics", "laptop": "electronics", "headphone": "electronics",
        "earphone": "electronics", "earring": "electronics", "speaker": "electronics",
        "camera": "electronics", "television": "electronics", "tv": "electronics",
        "watch": "watches", "smartwatch": "watches",
        "shoe": "fashion", "shirt": "fashion", "saree": "fashion",
        "clothing": "fashion", "footwear": "fashion", "jewellery": "fashion",
        "coffee": "grocery", "grocery": "grocery", "food": "grocery",
        "book": "books", "novel": "books",
        "furniture": "furniture", "sofa": "furniture", "chair": "furniture",
    }
    for key, root in mapping.items():
        if key in cat:
            return root
    return cat


@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json()
    urls = data.get("urls", [])

    if not urls or len(urls) < 2 or len(urls) > 5:
        return jsonify({"error": "Please provide between 2 and 5 Amazon product URLs."}), 400

    # ── Step 1: Fetch all product raw data first ──────────────
    all_prices = []
    raw_products = []

    for url in urls:
        try:
            from data_ingestion.serp_fetcher import extract_asin
            asin = extract_asin(url.strip())
            if not asin:
                raw_products.append({"error": f"Could not extract ASIN from URL: {url}", "url": url})
                continue

            cached = get_cached_product(asin)
            if cached:
                raw = cached
                raw["_from_cache"] = True
            else:
                raw = fetch_product_details(url.strip())
                raw["_from_cache"] = False

            raw_products.append({"asin": asin, "url": url.strip(), "raw": raw})

        except Exception as e:
            raw_products.append({"error": str(e), "url": url})

    # ── Step 2: Check for new products ────────────────────────
    new_products = []
    for item in raw_products:
        if "error" in item:
            continue
        if _is_new_product(item["raw"]):
            new_products.append(item["raw"].get("title", item["url"]))

    if new_products:
        names = " | ".join(new_products)
        return jsonify({
            "error": (
                f"The following product(s) appear to be newly listed on Amazon "
                f"with no reviews or ratings yet: {names}. "
                f"ProductLens needs customer reviews to analyse and compare products fairly. "
                f"Please try again once the product has received some reviews."
            )
        }), 400

    # ── Step 3: Check all products are in same category ───────
    categories = []
    for item in raw_products:
        if "error" not in item:
            cat = item["raw"].get("category", "general")
            categories.append(_normalise_category(cat))

    unique_cats = set(categories)
    if len(unique_cats) > 1:
        # Build readable list of product → category pairs
        cat_list = []
        for item in raw_products:
            if "error" not in item:
                title = item["raw"].get("title", item["url"])
                cat   = item["raw"].get("category", "General")
                cat_list.append(f'"{title[:50]}..." ({cat})')
        cat_detail = "  |  ".join(cat_list)
        return jsonify({
            "error": (
                f"The products you entered appear to be from different categories "
                f"and cannot be compared fairly.  {cat_detail}.  "
                f"Please compare products of the same type — "
                f"for example, two smartphones, two laptops, or two watches."
            )
        }), 400

    # ── Step 4: Run full pipeline on all products ─────────────
    products = []
    errors   = []

    for item in raw_products:
        if "error" in item:
            errors.append({"url": item["url"], "error": item["error"]})
            products.append({"error": item["error"], "url": item["url"]})
            continue
        try:
            result = process_product_from_raw(
                item["asin"], item["url"], item["raw"], all_prices
            )
            products.append(result)
        except Exception as e:
            errors.append({"url": item["url"], "error": str(e), "trace": traceback.format_exc()})
            products.append({"error": str(e), "url": item["url"]})

    # Scoring requires all prices for relative comparison
    products = apply_scores(products, all_prices)

    # Rank
    ranked = rank_products(products)

    return jsonify({
        "products": ranked,
        "errors": errors,
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)