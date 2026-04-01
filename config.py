import os
from dotenv import load_dotenv

load_dotenv()

SERP_API_KEY = os.getenv("SERP_API_KEY")
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = "product_eval_db"
CACHE_DAYS = 7