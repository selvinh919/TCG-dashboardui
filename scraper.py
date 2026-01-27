from playwright.sync_api import sync_playwright
import time
import re
import json
import os

def get_card_image(card):
    images = card.get("images", [])

    if isinstance(images, list):
        # Prefer FRONT / STANDARD images
        for img in images:
            img_type = img.get("type", "").lower()
            if img_type in ("standard", "front"):
                return img.get("url")

        # Fallback: anything that's not a back
        for img in images:
            if "back" not in img.get("url", "").lower():
                return img.get("url")

        # Last resort
        if images:
            return images[0].get("url")

    return card.get("imageUrl")


def clean_price(text):
    return float(re.sub(r"[^\d.]", "", text))

def load_settings():
    """Load settings from settings.json"""
    if os.path.exists('settings.json'):
        with open('settings.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'tcgplayer_username': ''}

def scrape_inventory(base_url=None):
    """Scrape TCG inventory. If base_url is None, load from settings."""
    if base_url is None:
        settings = load_settings()
        username = settings.get('tcgplayer_username', '')
        if username:
            # Auto-construct the store URL from username
            base_url = f'https://store.tcgplayer.com/{username}/admin/inventory'
        else:
            base_url = 'https://store.tcgplayer.com/admin/product/inventory'
    items = []
    seen_names = set()
    page_num = 1

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-gpu',
                '--no-sandbox',
                '--disable-dev-shm-usage'
            ]
        )
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080}
        )
        page = context.new_page()
        
        # Block images and other heavy resources
        page.route('**/*', lambda route: route.abort() if route.request.resource_type in ['image', 'font', 'media'] else route.continue_())
        
        # Add stealth scripts
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = {runtime: {}};
        """)

        while True:
            url = f"{base_url}&page={page_num}&view=list"
            print(f"[INFO] Scraping page {page_num}")
            page.goto(url, timeout=30000, wait_until='domcontentloaded')

            # ✅ WAIT for market prices to render (faster)
            try:
                page.wait_for_selector(
                    "span.product-card__market-price--value",
                    timeout=8000
                )
            except:
                print("[WARN] Market price selector not found yet")

            # Trigger lazy loading (faster scrolling)
            for _ in range(4):
                page.mouse.wheel(0, 5000)
                time.sleep(0.5)

            cards = page.query_selector_all("div.search-result")

            if not cards:
                print("[INFO] No listings found — stopping pagination")
                break

            new_items = 0

            for card in cards:
                try:
                    title_el = card.query_selector("span.product-card__title")
                    price_el = card.query_selector("span.inventory__price-with-shipping")

                    if not title_el or not price_el:
                        continue

                    name = title_el.inner_text().strip()

                    if name in seen_names:
                        continue
                    seen_names.add(name)

                    price = clean_price(price_el.inner_text())

                    # ✅ MARKET PRICE EXTRACTION
                    market = None
                    market_el = (
                        card.query_selector("span.product-card__market-price--value")
                        or card.query_selector("span:has-text('Market Price')")
                    )

                    if market_el:
                        m = re.search(r"\$([\d\.]+)", market_el.inner_text())
                        if m:
                            market = float(m.group(1))

                    # ✅ EXTRACT TCGPlayer PRODUCT URL & ID & SET NAME & CARD NUMBER
                    tcg_url = None
                    tcg_product_id = None
                    set_name = None
                    card_number = None
                    link_el = card.query_selector("a")
                    if link_el:
                        href = link_el.get_attribute("href")
                        if href:
                            # Extract product ID from URL like: /product/502551/pokemon-sv-scarlet...
                            product_match = re.search(r"/product/(\d+)/", href)
                            if product_match:
                                tcg_product_id = product_match.group(1)
                            
                            # Make absolute URL
                            if href.startswith("/"):
                                tcg_url = f"https://www.tcgplayer.com{href}"
                            else:
                                tcg_url = href
                        
                        # Extract set name and card number from link text
                        # Format is usually: "Set Name\nCard Type, #123/456" or "Set Name\nCard Type"
                        link_text = link_el.inner_text().strip()
                        if link_text:
                            lines = link_text.split("\n")
                            if lines:
                                # First line is usually the set name
                                set_name = lines[0].strip()
                                
                                # Look for card number in any line (format: #123/456 or #P02/094, etc.)
                                for line in lines:
                                    card_num_match = re.search(r"#([A-Z]?\d{1,4}/\d{2,4})", line)
                                    if card_num_match:
                                        card_number = card_num_match.group(1)
                                        break

                    # ✅ EXTRACT IMAGE URL (construct from product ID)
                    image_url = None
                    if tcg_product_id:
                        # TCGPlayer uses consistent image URLs based on product ID
                        image_url = f"https://tcgplayer-cdn.tcgplayer.com/product/{tcg_product_id}_in_200x200.jpg"
                    else:
                        # Fallback: try to scrape from img tag
                        img_el = card.query_selector("img")
                        if img_el:
                            src = img_el.get_attribute("src") or img_el.get_attribute("data-src")
                            # Skip lazy-load placeholder images
                            if src and not src.startswith("data:image"):
                                image_url = src

                    items.append({
                        "name": name,
                        "price": price,
                        "market": market,
                        "qty": 1,
                        "tcg_url": tcg_url,
                        "tcg_product_id": tcg_product_id,
                        "image": image_url,
                        "set_name": set_name,
                        "card_number": card_number  # Extracted from link text
                    })

                    new_items += 1

                except Exception as e:
                    continue

            print(f"[INFO] Page {page_num}: added {new_items} items")

            if new_items == 0:
                print("[INFO] No new items detected — pagination complete")
                break

            page_num += 1
            time.sleep(2)

        browser.close()

    print(f"[SUMMARY] Total public listings found: {len(items)}")
    return items
