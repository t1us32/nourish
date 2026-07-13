import json
import os
import re
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

load_dotenv()

app = FastAPI(title="Nourish API")

class Meal(BaseModel):
    name: str
    calories: int
    protein: int = 0
    fat: int = 0
    carbs: int = 0

class SearchHistoryItem(BaseModel):
    query: str

meals: list[Meal] = []
search_history_path = Path(os.getenv("SEARCH_HISTORY_PATH", "recent-searches.json"))


def log(message: str):
    print(message, flush=True)

try:
    recent_searches = json.loads(search_history_path.read_text())
    if not isinstance(recent_searches, list) or not all(isinstance(item, str) for item in recent_searches):
        recent_searches = []
except (OSError, json.JSONDecodeError):
    recent_searches = []

def open_food_facts_food(product: dict, fallback_code: str):
    nutriments = product.get("nutriments", {})
    return {
        "fdcId": f"off-{product.get('code', fallback_code)}",
        "description": product.get("product_name") or product.get("product_name_uk") or product.get("product_name_ru") or product.get("generic_name") or fallback_code,
        "brandOwner": product.get("brands") or "Open Food Facts",
        "dataType": "Open Food Facts",
        "foodNutrients": [
            {"nutrientName": "Energy", "value": nutriments.get("energy-kcal_100g", 0)},
            {"nutrientName": "Protein", "value": nutriments.get("proteins_100g", 0)},
            {"nutrientName": "Total lipid (fat)", "value": nutriments.get("fat_100g", 0)},
            {"nutrientName": "Carbohydrate, by difference", "value": nutriments.get("carbohydrates_100g", 0)}
        ]
    }

def lookup_barcode(code: str):
    log(f"barcode.lookup start code={code}")
    product_url = f"https://world.openfoodfacts.org/api/v2/product/{code}.json?fields=code,product_name,product_name_uk,product_name_ru,generic_name,brands,nutriments"
    request = Request(product_url, headers={"User-Agent": "Nourish/1.0 (local nutrition tracker)"})
    try:
        with urlopen(request, timeout=10) as response:
            product_data = json.load(response)
    except Exception as error:
        log(f"barcode.lookup error code={code} error={type(error).__name__}: {error}")
        raise HTTPException(status_code=502, detail="Barcode lookup is temporarily unavailable.") from error

    product = product_data.get("product", {})
    if product_data.get("status") != 1 or not product:
        log(f"barcode.lookup miss code={code}")
        raise HTTPException(status_code=404, detail="No food was found for this barcode.")
    log(f"barcode.lookup hit code={code} name={product.get('product_name') or product.get('generic_name') or code}")
    return open_food_facts_food(product, code)

def open_food_facts_search(query: str):
    log(f"barcode.off_search start query={query}")
    search_params = urlencode({"search_terms": query, "search_simple": 1, "action": "process", "json": 1, "page_size": 10})
    request = Request(
        f"https://world.openfoodfacts.org/cgi/search.pl?{search_params}",
        headers={"User-Agent": "Nourish/1.0 (local nutrition tracker)"}
    )
    try:
        with urlopen(request, timeout=10) as response:
            product_data = json.load(response)
        foods = [open_food_facts_food(product, query) for product in product_data.get("products", [])]
        log(f"barcode.off_search done query={query} count={len(foods)}")
        return foods
    except Exception as error:
        log(f"barcode.off_search error query={query} error={type(error).__name__}: {error}")
        return []

def search_by_barcode(code: str):
    log(f"barcode.search start code={code}")
    try:
        return lookup_barcode(code)
    except HTTPException as error:
        if error.status_code != 404:
            log(f"barcode.search error code={code} status={error.status_code}")
            raise

    foods = open_food_facts_search(code)
    if foods:
        log(f"barcode.search fallback_hit code={code} name={foods[0].get('description')}")
        return foods[0]
    log(f"barcode.search not_found code={code}")
    raise HTTPException(status_code=404, detail="No food was found for this barcode.")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/meals")
def list_meals():
    return meals

@app.post("/meals", status_code=201)
def create_meal(meal: Meal):
    meals.append(meal)
    return meal

@app.get("/foods/recent-searches")
def list_recent_searches():
    return {"searches": recent_searches}

@app.post("/foods/recent-searches")
def save_recent_search(item: SearchHistoryItem):
    query = " ".join(item.query.split())[:100]
    if len(query) < 2:
        raise HTTPException(status_code=400, detail="Search text must be at least 2 characters.")
    recent_searches[:] = [saved for saved in recent_searches if saved.casefold() != query.casefold()]
    recent_searches.insert(0, query)
    del recent_searches[8:]
    try:
        search_history_path.parent.mkdir(parents=True, exist_ok=True)
        search_history_path.write_text(json.dumps(recent_searches))
    except OSError as error:
        raise HTTPException(status_code=500, detail="Could not save recent searches.") from error
    return {"searches": recent_searches}

@app.get("/foods/barcode/{code}")
def get_food_by_barcode(code: str):
    if not code.isdigit() or not 8 <= len(code) <= 14:
        raise HTTPException(status_code=400, detail="Enter a valid 8 to 14 digit barcode.")
    return {"food": search_by_barcode(code)}

@app.get("/foods/search")
def search_foods(query: str = Query(min_length=2, max_length=100)):
    if query.isdigit() and 8 <= len(query) <= 14:
        try:
            return {"foods": [search_by_barcode(query)]}
        except HTTPException as error:
            if error.status_code != 404:
                raise

    api_key = os.getenv("FDC_API_KEY")
    foods = []
    if api_key:
        params = urlencode({"api_key": api_key, "query": query, "pageSize": 10})
        try:
            with urlopen(f"https://api.nal.usda.gov/fdc/v1/foods/search?{params}", timeout=10) as response:
                foods = json.load(response).get("foods", [])
        except Exception:
            pass

    # Open Food Facts keeps search available when USDA is not configured and
    # improves coverage for international products.
    if not foods or re.search(r"[\u0400-\u052F]", query):
        foods = open_food_facts_search(query) + foods

    return {"foods": foods}
