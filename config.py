import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("RESTAURANT_DB", os.path.join(BASE_DIR, "data", "restaurant.db"))
SAMPLE_DIR = os.path.join(BASE_DIR, "data", "sample")
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-secret")
PER_PAGE = 15
