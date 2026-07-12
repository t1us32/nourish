import json
import os
import re
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

meals: list[Meal] = []

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
    product_url = f"https://world.openfoodfacts.org/api/v2/product/{code}.json?fields=code,product_name,product_name_uk,product_name_ru,generic_name,brands,nutriments"
    request = Request(product_url, headers={"User-Agent": "Nourish/1.0 (local nutrition tracker)"})
    try:
        with urlopen(request, timeout=10) as response:
            product_data = json.load(response)
    except Exception as error:
        raise HTTPException(status_code=502, detail="Barcode lookup is temporarily unavailable.") from error

    product = product_data.get("product", {})
    if product_data.get("status") != 1 or not product:
        raise HTTPException(status_code=404, detail="No food was found for this barcode.")
    return open_food_facts_food(product, code)

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

@app.get("/foods/barcode/{code}")
def get_food_by_barcode(code: str):
    if not code.isdigit() or not 8 <= len(code) <= 14:
        raise HTTPException(status_code=400, detail="Enter a valid 8 to 14 digit barcode.")
    return {"food": lookup_barcode(code)}

@app.get("/foods/search")
def search_foods(query: str = Query(min_length=2, max_length=100)):
    if query.isdigit() and 8 <= len(query) <= 14:
        try:
            return {"foods": [lookup_barcode(query)]}
        except HTTPException as error:
            if error.status_code != 404:
                raise

    api_key = os.getenv("FDC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="Food search is not configured.")

    params = urlencode({"api_key": api_key, "query": query, "pageSize": 10})
    try:
        with urlopen(f"https://api.nal.usda.gov/fdc/v1/foods/search?{params}", timeout=10) as response:
            data = json.load(response)
    except Exception as error:
        raise HTTPException(status_code=502, detail="Food search is temporarily unavailable.") from error

    foods = data.get("foods", [])

    # USDA's catalog is primarily English. Open Food Facts includes product names
    # contributed in Ukrainian and Russian, so use it for Cyrillic text queries.
    if re.search(r"[\u0400-\u052F]", query):
        search_params = urlencode({"search_terms": query, "search_simple": 1, "action": "process", "json": 1, "page_size": 10})
        request = Request(
            f"https://world.openfoodfacts.org/cgi/search.pl?{search_params}",
            headers={"User-Agent": "Nourish/1.0 (local nutrition tracker)"}
        )
        try:
            with urlopen(request, timeout=10) as response:
                product_data = json.load(response)
            foods = [open_food_facts_food(product, query) for product in product_data.get("products", [])] + foods
        except Exception:
            pass

    return {"foods": foods}
