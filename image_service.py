import requests

IMAGE_CACHE = {}

PLACEHOLDER = "https://via.placeholder.com/80x110?text=NO+IMAGE"

def get_item_image(name: str, ebay_image: str | None = None):
    key = name.lower().strip()

    # 1️⃣ Cache hit
    if key in IMAGE_CACHE:
        return IMAGE_CACHE[key]

    # 2️⃣ eBay image first (best match)
    if ebay_image:
        IMAGE_CACHE[key] = ebay_image
        return ebay_image

    # 3️⃣ Pokémon fallback (cards only)
    if "pokemon" in key:
        try:
            r = requests.get(
                f"https://api.pokemontcg.io/v2/cards?q=name:{name}",
                timeout=3,
            )
            data = r.json()
            if data["data"]:
                img = data["data"][0]["images"]["small"]
                IMAGE_CACHE[key] = img
                return img
        except:
            pass

    # 4️⃣ Fallback
    IMAGE_CACHE[key] = PLACEHOLDER
    return PLACEHOLDER
