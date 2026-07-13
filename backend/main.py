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

# USDA's catalogue is primarily English, while Open Food Facts has better
# coverage for Russian-labelled products. Search both forms for common foods.
RUSSIAN_FOOD_ALIASES = {
    "куриная грудка": "chicken breast",
    "куриное филе": "chicken breast",
    "куриный фарш": "ground chicken",
    "говяжий фарш": "ground beef",
    "творожный сыр": "cream cheese",
    "творог": "cottage cheese",
    "греческий йогурт": "greek yogurt",
    "овсяные хлопья": "oats",
    "овсянка": "oatmeal",
    "гречка": "buckwheat",
    "рис": "rice",
    "макароны": "pasta",
    "картофель": "potato",
    "яблоко": "apple",
    "яблоки": "apple",
    "банан": "banana",
    "курица": "chicken",
    "курицу": "chicken",
    "курицы": "chicken",
    "говядина": "beef",
    "свинина": "pork",
    "рыба": "fish",
    "лосось": "salmon",
    "яйцо": "egg",
    "яйца": "eggs",
    "молоко": "milk",
    "кефир": "kefir",
    "йогурт": "yogurt",
    "сыр": "cheese",
    "хлеб": "bread",
}

LOW_QUALITY_FOOD_TERMS = (
    "bar",
    "батончик",
    "cake",
    "candy",
    "chips",
    "cookie",
    "dessert",
    "drink",
    "juice",
    "nugget",
    "pie",
    "pizza",
    "sauce",
    "soda",
    "торт",
    "конфет",
    "пирог",
    "печенье",
    "пицц",
    "напиток",
    "наггет",
    "сок",
    "соус",
    "чипс",
)

# Reliable per-100 g entries for the foods people log most often. They keep
# basic searches useful when third-party catalogues are slow or unavailable.
BASIC_FOODS = {
    "apple": ("Apple, raw", "Яблоко, сырое", 52, 0.3, 0.2, 13.8),
    "banana": ("Banana, raw", "Банан, сырой", 89, 1.1, 0.3, 22.8),
    "chicken": ("Chicken, meat only, raw", "Курица, мясо, сырое", 120, 22.5, 2.6, 0),
    "chicken breast": ("Chicken breast, raw", "Куриная грудка, сырая", 120, 22.5, 2.6, 0),
    "ground chicken": ("Ground chicken, raw", "Куриный фарш, сырой", 143, 17.5, 8.1, 0),
    "beef": ("Beef, lean, raw", "Говядина постная, сырая", 187, 20.5, 11.4, 0),
    "ground beef": ("Ground beef, raw", "Фарш говяжий, сырой", 212, 18.6, 14.0, 0),
    "pork": ("Pork, lean, raw", "Свинина постная, сырая", 143, 21.0, 5.9, 0),
    "fish": ("White fish, raw", "Белая рыба, сырая", 96, 20.0, 1.7, 0),
    "salmon": ("Salmon, raw", "Лосось, сырой", 208, 20.4, 13.4, 0),
    "egg": ("Chicken egg, whole", "Яйцо куриное", 143, 12.6, 9.5, 0.7),
    "eggs": ("Chicken eggs, whole", "Яйца куриные", 143, 12.6, 9.5, 0.7),
    "milk": ("Milk, 2.5% fat", "Молоко 2.5%", 52, 3.0, 2.5, 4.7),
    "kefir": ("Kefir, 2.5% fat", "Кефир 2.5%", 53, 3.0, 2.5, 4.0),
    "yogurt": ("Natural yogurt, 2.5% fat", "Йогурт натуральный 2.5%", 60, 4.3, 2.5, 5.0),
    "greek yogurt": ("Greek yogurt, plain", "Йогурт греческий натуральный", 97, 9.0, 5.0, 3.9),
    "cottage cheese": ("Cottage cheese, 5% fat", "Творог 5%", 121, 17.0, 5.0, 3.0),
    "oats": ("Oats, dry", "Овсяные хлопья, сухие", 379, 13.2, 6.5, 67.7),
    "oatmeal": ("Oatmeal, cooked", "Овсяная каша, готовая", 71, 2.5, 1.5, 12.0),
    "buckwheat": ("Buckwheat, dry", "Гречка, сухая", 343, 13.3, 3.4, 71.5),
    "rice": ("Rice, cooked", "Рис, приготовленный", 130, 2.4, 0.3, 28.0),
    "pasta": ("Pasta, cooked", "Макароны, приготовленные", 157, 5.8, 0.9, 30.9),
    "potato": ("Potato, boiled", "Картофель, отварной", 87, 1.9, 0.1, 20.1),
}


def log(message: str):
    print(message, flush=True)


def food_search_queries(query: str):
    normalized_query = " ".join(query.casefold().split())
    translated = next(
        (
            english
            for russian, english in RUSSIAN_FOOD_ALIASES.items()
            if russian in normalized_query
        ),
        None,
    )
    return [query] if not translated else [query, translated]


def basic_food_terms(query: str):
    normalized_query = " ".join(query.casefold().split())
    canonical = next(
        (
            english
            for russian, english in RUSSIAN_FOOD_ALIASES.items()
            if russian in normalized_query
        ),
        None,
    )
    if not canonical and normalized_query in RUSSIAN_FOOD_ALIASES.values():
        canonical = normalized_query
    if not canonical:
        return None, ()

    aliases = [russian for russian, english in RUSSIAN_FOOD_ALIASES.items() if english == canonical]
    return canonical, tuple({canonical, *aliases})


def basic_food(query: str):
    canonical, _ = basic_food_terms(query)
    food = BASIC_FOODS.get(canonical)
    if not food:
        return None

    english_name, russian_name, calories, protein, fat, carbs = food
    description = russian_name if re.search(r"[\u0400-\u052F]", query) else english_name
    return {
        "fdcId": f"nourish-basic-{canonical.replace(' ', '-')}",
        "description": description,
        "brandOwner": "Nourish basics",
        "dataType": "Nourish basics",
        "foodNutrients": [
            {"nutrientName": "Energy", "value": calories},
            {"nutrientName": "Protein", "value": protein},
            {"nutrientName": "Total lipid (fat)", "value": fat},
            {"nutrientName": "Carbohydrate, by difference", "value": carbs},
        ],
    }


def food_result_score(food: dict, query: str):
    canonical, aliases = basic_food_terms(query)
    if not canonical:
        return 0

    description = str(food.get("description", "")).casefold()
    data_type = str(food.get("dataType", "")).casefold()
    score = 0
    if description == canonical:
        score += 120
    elif description.startswith(canonical):
        score += 80
    elif any(alias in description for alias in aliases):
        score += 45

    if data_type == "foundation":
        score += 60
    elif data_type == "sr legacy":
        score += 50
    elif "survey" in data_type:
        score += 35
    elif "branded" in data_type or "open food facts" in data_type:
        score -= 15

    if any(term in description for term in LOW_QUALITY_FOOD_TERMS):
        score -= 100
    return score


def rank_foods(foods: list[dict], query: str):
    if not basic_food_terms(query)[0]:
        return foods

    ranked = sorted(foods, key=lambda food: food_result_score(food, query), reverse=True)
    useful = [food for food in ranked if food_result_score(food, query) > 0]
    return useful or ranked


def unique_foods(foods: list[dict]):
    seen = set()
    unique = []
    for food in foods:
        food_id = food.get("fdcId")
        if food_id in seen:
            continue
        seen.add(food_id)
        unique.append(food)
    return unique

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
    candidates = [code]
    stripped = code.lstrip("0")
    if stripped and stripped not in candidates:
        candidates.append(stripped)
    if len(code) == 13 and code[:-1] not in candidates:
        candidates.append(code[:-1])
    if len(code) >= 12:
        upc12 = code[-12:]
        if upc12 not in candidates:
            candidates.append(upc12)
    log(f"barcode.search candidates code={code} candidates={candidates}")
    try:
        return lookup_barcode(code)
    except HTTPException as error:
        if error.status_code != 404:
            log(f"barcode.search error code={code} status={error.status_code}")
            raise

    for candidate in candidates:
        foods = open_food_facts_search(candidate)
        if foods:
            log(f"barcode.search fallback_hit code={code} candidate={candidate} name={foods[0].get('description')}")
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

    if food := basic_food(query):
        return {"foods": [food]}

    search_queries = food_search_queries(query)
    api_key = os.getenv("FDC_API_KEY")
    foods = []
    if api_key:
        for search_query in search_queries:
            params = urlencode({"api_key": api_key, "query": search_query, "pageSize": 10})
            try:
                with urlopen(f"https://api.nal.usda.gov/fdc/v1/foods/search?{params}", timeout=10) as response:
                    foods.extend(json.load(response).get("foods", []))
            except Exception:
                pass

    # Open Food Facts keeps search available when USDA is not configured and
    # improves coverage for international products.
    if not foods or re.search(r"[\u0400-\u052F]", query):
        open_foods = []
        for search_query in search_queries:
            open_foods.extend(open_food_facts_search(search_query))
        foods = open_foods + foods

    return {"foods": rank_foods(unique_foods(foods), query)[:10]}
