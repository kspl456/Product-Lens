import re
import requests as _requests
from serpapi import GoogleSearch
from config import SERP_API_KEY

# Short URL domains used by Amazon share button
_SHORT_URL_DOMAINS = ("amzn.in", "amzn.to", "a.co")


def _expand_url(url: str) -> str:
    """Follow redirects on short URLs to get the full Amazon product URL.
    Uses GET with a browser user-agent — HEAD requests are blocked by amzn.in.
    """
    try:
        resp = _requests.get(
            url,
            allow_redirects=True,
            timeout=15,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                )
            }
        )
        # The final URL after all redirects contains the full Amazon product URL
        final_url = resp.url
        print(f"Short URL expanded: {url} → {final_url}")
        return final_url
    except Exception as e:
        print(f"Could not expand short URL {url}: {e}")
        raise ValueError(
            f"Could not resolve the short link: {url}\n"
            "Please open the product on Amazon, copy the URL directly "
            "from the browser address bar, and paste that instead."
        )


def _is_short_url(url: str) -> bool:
    """Check if URL is an Amazon short URL from the share button."""
    return any(domain in url for domain in _SHORT_URL_DOMAINS)


def extract_asin(url: str) -> str | None:
    """Extract Amazon ASIN from product URL. Expands short URLs automatically."""
    # Expand short URLs first
    if _is_short_url(url):
        url = _expand_url(url)

    patterns = [
        r"/dp/([A-Z0-9]{10})",
        r"/gp/product/([A-Z0-9]{10})",
        r"asin=([A-Z0-9]{10})",
        r"/([A-Z0-9]{10})(?:/|\?|$)",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None


def fetch_product_details(amazon_url: str) -> dict:
    # Expand short URL before anything else
    if _is_short_url(amazon_url):
        amazon_url = _expand_url(amazon_url)

    asin = extract_asin(amazon_url)
    if not asin:
        raise ValueError(f"Could not extract ASIN from URL: {amazon_url}")

    params = {
        "engine": "amazon_product",
        "asin": asin,
        "amazon_domain": "amazon.in",
        "api_key": SERP_API_KEY,
    }

    # Use GoogleSearch exactly like the working test script
    search = GoogleSearch(params)
    results = search.get_dict()

    if "product_results" not in results:
        raise ValueError(f"SerpAPI error: {results.get('error', 'No product_results')}")

    product = results.get("product_results", {})

    # Title
    title = product.get("title", "Unknown Product")

    # Price — same multi-tier logic as working test
    price = _extract_price(product)

    # Rating
    rating = product.get("rating")
    if rating:
        try:
            rating = float(rating)
        except (ValueError, TypeError):
            rating = None

    # Total review count — product.reviews is the Amazon integer (e.g. 22836)
    total_reviews = product.get("reviews", 0)
    print(f"=== DEBUG ===")
    print(f"total_reviews value: {total_reviews}")
    print(f"product keys: {list(product.keys())}")
    print(f"product.reviews raw: {product.get('reviews')}")

    # Seller / brand
    seller = product.get("brand", "Amazon / Unknown").replace("Brand: ", "").strip()

    # Category — same logic as working test
    category = _extract_category(product, results)

    # Thumbnail
    thumbnail = product.get("thumbnail") or None

    # Review objects — for analysis pipeline
    review_list = _extract_reviews(results)

    return {
        "asin": asin,
        "url": amazon_url,
        "title": title,
        "price": price,
        "seller": seller,
        "rating": rating,
        "category": category,
        "reviews": review_list,
        "total_reviews": total_reviews,
        "thumbnail": thumbnail,
    }


def _extract_price(product: dict) -> float | None:
    """Multi-tier price extraction — same as working test script."""
    # 1. Direct extracted price
    if product.get("extracted_price"):
        return float(product["extracted_price"])

    # 2. Buybox winner
    buybox = product.get("buybox_winner", {})
    if buybox.get("price", {}).get("value"):
        return float(buybox["price"]["value"])

    # 3. Offers list
    for offer in product.get("offers", []):
        if offer.get("price", {}).get("value"):
            return float(offer["price"]["value"])

    # 4. Variant price fallback
    for variant in product.get("variants", []):
        for item in variant.get("items", []):
            if item.get("price", {}).get("value"):
                return float(item["price"]["value"])

    # 5. Raw price string
    raw = product.get("price")
    if raw:
        return _parse_price(raw)

    return None


def _extract_category(product: dict, results: dict) -> str:
    """Category extraction — same as working test script."""
    # 1. Breadcrumb categories
    categories = product.get("categories", [])
    if categories:
        return categories[-1].get("name", "General")

    # 2. Best sellers rank (most specific sub-category)
    product_details = results.get("product_details", {})
    bsr = product_details.get("best_sellers_rank", [])
    if bsr:
        return bsr[-1].get("link_text") or bsr[0].get("link_text") or "General"

    # 3. Infer from title keywords
    title = product.get("title", "").lower()
    keyword_map = {
        "mobile": "Mobile Phones",
        "laptop": "Computers",
        "headphone": "Audio",
        "earphone": "Audio",
        "earring": "Jewellery",
        "watch": "Watches",
        "coffee": "Grocery",
        "charger": "Electronics Accessories",
        "shoe": "Footwear",
        "shirt": "Clothing",
        "saree": "Clothing",
    }
    for key, cat in keyword_map.items():
        if key in title:
            return cat

    return "General"


def _extract_reviews(results: dict) -> list[dict]:
    """Extract reviews from amazon_product response."""
    reviews = []
    authors_reviews = results.get("reviews_information", {}).get("authors_reviews", [])
    for r in authors_reviews:
        reviews.append({
            "title": r.get("title", ""),
            "content": r.get("text", ""),
            "rating": r.get("rating"),
            "verified": "Verified Purchase" in r.get("author", ""),
            "date": r.get("date", ""),
        })
    return reviews


def _parse_price(raw) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    cleaned = re.sub(r"[^\d.]", "", str(raw))
    try:
        return float(cleaned)
    except ValueError:
        return None
