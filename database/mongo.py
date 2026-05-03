from datetime import datetime, timezone
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
import os

# ── Connection ────────────────────────────────────────────────
_client = None
_db = None
_collection = None

def _get_collection():
    """Lazy connection — only connects when first needed."""
    global _client, _db, _collection

    if _collection is not None:
        return _collection

    mongo_uri = os.environ.get("MONGO_URI")
    if not mongo_uri:
        raise ValueError(
            "MONGO_URI environment variable is not set. "
            "Add it to your .env file: MONGO_URI=mongodb+srv://..."
        )

    _client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)

    # Verify connection is alive
    _client.admin.command("ping")

    _db = _client["productlens"]
    _collection = _db["products"]

    # Index on asin for fast lookups
    _collection.create_index("asin", unique=True)

    print("✓ MongoDB Atlas connected successfully.")
    return _collection


# ── Public functions ──────────────────────────────────────────

def get_cached_product(asin: str) -> dict | None:
    """Return cached product if fetched within last 7 days, else None."""
    try:
        col = _get_collection()
        doc = col.find_one({"asin": asin})
        if not doc:
            return None

        fetched_at = doc.get("fetched_at")
        if fetched_at:
            # fetched_at is stored as UTC datetime
            age_days = (datetime.now(timezone.utc) - fetched_at).days
            if age_days < 7:
                # Remove MongoDB internal _id before returning
                doc.pop("_id", None)
                return doc

        return None

    except (ConnectionFailure, ServerSelectionTimeoutError) as e:
        print(f"⚠ MongoDB connection error (get): {e}")
        return None
    except Exception as e:
        print(f"⚠ MongoDB error (get): {e}")
        return None


def save_product(data: dict) -> None:
    """Insert or update product in MongoDB using ASIN as unique key."""
    try:
        col = _get_collection()
        data["fetched_at"] = datetime.now(timezone.utc)

        # Remove _id if present to avoid conflict on upsert
        data.pop("_id", None)

        col.update_one(
            {"asin": data["asin"]},
            {"$set": data},
            upsert=True  # insert if not exists, update if exists
        )

    except (ConnectionFailure, ServerSelectionTimeoutError) as e:
        print(f"⚠ MongoDB connection error (save): {e}")
    except Exception as e:
        print(f"⚠ MongoDB error (save): {e}")


def get_product_by_asin(asin: str) -> dict | None:
    """Get any stored product by ASIN regardless of age."""
    try:
        col = _get_collection()
        doc = col.find_one({"asin": asin})
        if doc:
            doc.pop("_id", None)
        return doc
    except Exception as e:
        print(f"⚠ MongoDB error (get_by_asin): {e}")
        return None