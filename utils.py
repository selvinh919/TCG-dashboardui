import re
import requests
import json
import os

IMAGE_CACHE_FILE = "image_cache.json"
POKEMON_API_KEY = "6ba2f0c2-5c79-4ac5-a8c7-1578120779f8"

# ---------- Image Cache ----------
if os.path.exists(IMAGE_CACHE_FILE):
    with open(IMAGE_CACHE_FILE, "r", encoding="utf-8") as f:
        IMAGE_CACHE = json.load(f)
else:
    IMAGE_CACHE = {}

def save_cache():
    with open(IMAGE_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(IMAGE_CACHE, f, indent=2)

# ---------- Name Normalizer ----------
def normalize_card(raw_name):
    # Match card numbers in various formats: ###/###, #/###, ###/##, etc.
    number_match = re.search(r"(\d{{1,4}}/\d{{2,4}})", raw_name)
    card_number = number_match.group(1) if number_match else ""

    # Remove parenthetical content and common descriptors
    cleaned = re.sub(
        r"\(.*?\)|promo|stamped|cosmos|holo|reverse|full\s*art|alternate\s*art",
        "",
        raw_name,
        flags=re.I
    ).strip()

    # Remove the card number and any trailing dashes/spaces
    base_name = re.sub(r"\s*-*\s*\d{{1,4}}/\d{{2,4}}\s*-*\s*", "", cleaned).strip()
    base_name = re.sub(r"\s*-\s*$", "", base_name).strip()  # Remove trailing dash
    
    display_name = f"{{base_name}} {{card_number}}".strip() if card_number else base_name

    return display_name, base_name, card_number

# ---------- Pokémon Image Resolver ----------
def pokemon_image_logic(display_name):
    key = display_name.lower()

    if key in IMAGE_CACHE:
        return IMAGE_CACHE[key]

    # Build Pokémon API query
    name, _, number = normalize_card(display_name)
    query = f'name:"{name}"'

    if number:
        query += f' number:{number.split("/")[0]}'

    url = "https://api.pokemontcg.io/v2/cards"
    params = {"q": query, "pageSize": 1}
    headers = {"X-Api-Key": POKEMON_API_KEY}

    try:
        r = requests.get(url, params=params, headers=headers, timeout=4)
        if r.status_code == 200:
            data = r.json()
            if data.get("data"):
                image = data["data"][0]["images"]["small"]
                IMAGE_CACHE[key] = image
                save_cache()
                return image
    except requests.exceptions.RequestException:
        pass

    # Fallback
    IMAGE_CACHE[key] = "https://via.placeholder.com/80x110?text=TCG"
    save_cache()
    return IMAGE_CACHE[key]

# ---------- JustTCG Lookup ----------
import requests
import urllib.parse
from config import JUSTTCG_API_KEY, JUSTTCG_BASE

def justtcg_lookup(card_name):
    url = f"{JUSTTCG_BASE}/cards"
    params = {
        "q": card_name,
        "game": "pokemon"
    }
    headers = {
        "x-api-key": JUSTTCG_API_KEY
    }

    r = requests.get(url, params=params, headers=headers, timeout=5)
    if r.status_code != 200:
        return None

    data = r.json()
    if not data.get("results"):
        return None

    return data["results"][0]  # best match
