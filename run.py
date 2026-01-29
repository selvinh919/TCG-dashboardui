import json
import os
import subprocess
import re

from scraper import scrape_inventory
from analyzer import analyze
from notifier import send
from config import *
from utils import normalize_card

STATE_PATH = "state.json"

# ---------- Load previous state ----------
if os.path.exists(STATE_PATH):
    with open(STATE_PATH, "r", encoding="utf-8") as f:
        prev = json.load(f)
else:
    prev = []

# ---------- Step 1: Scrape raw inventory ----------
current = scrape_inventory(STORE_URL)

# ---------- Step 2: Normalize card names ----------
print(f"\n[INFO] Normalizing {len(current)} items...\n")

for item in current:
    # Use card number from scraper if available, otherwise try to extract from name
    card_number = item.get("card_number", "")
    
    if not card_number:
        # Fallback: try to extract from name using normalize_card
        display_name, base_name, extracted_number = normalize_card(item["name"])
        card_number = extracted_number
        item["base_name"] = base_name
    else:
        # Already have card number from scraper
        # Clean the name - remove any existing card number from the name
        base_name = item["name"]
        # Remove patterns like "- 009/165" or "009/165" from the name
        base_name = re.sub(r"\s*-\s*[A-Z]?\d{1,4}/\d{2,4}\s*", "", base_name)
        base_name = re.sub(r"\s+[A-Z]?\d{1,4}/\d{2,4}\s*$", "", base_name)
        base_name = base_name.strip()
        item["base_name"] = base_name
    
    item["card_number"] = card_number
    
    # Build clean display name: "Card Name #Card Number"
    if card_number:
        item["display_name"] = f"{item['base_name']} #{card_number}"
    else:
        item["display_name"] = item["base_name"]
    
    # Set default image if not found in scraper
    if not item.get("image"):
        item["image"] = None

# Note: All data now comes from TCGPlayer scraper - no API calls needed!
print(f"[INFO] All data extracted from TCGPlayer (no API calls needed)")

# ---------- Step 3: Analyze changes ----------
events = analyze(prev, current)

# ---------- Step 4: Save enriched state ----------
with open(STATE_PATH, "w", encoding="utf-8") as f:
    json.dump(current, f, indent=2)

# ---------- Step 5: Discord summary ----------
send(
    DISCORD_WEBHOOK,
    "📦 INVENTORY SUMMARY",
    f"Total Inventory Value: ${events['total_value']:,.2f}\n"
    f"Listings: {len(current)}",
    3447003
)

# ---------- Step 6: Alerts ----------
for sale in events["sales"]:
    send(
        DISCORD_WEBHOOK,
        "🧾 ITEM SOLD",
        f"{sale['name']}\nQty: {sale.get('qty', 'N/A')}",
        3066993
    )

for p in events["price_changes"]:
    direction = "📈" if p["new"] > p["old"] else "📉"
    send(
        DISCORD_WEBHOOK,
        f"{direction} PRICE CHANGE",
        f"{p['name']}\n${p['old']} → ${p['new']}",
        3447003
    )

# ---------- Step 7: Build dashboard ----------
# SKIP building dashboard - it will overwrite custom HTML
# Dashboard now loads data dynamically from /api/inventory endpoint
print("[INFO] Dashboard will load data dynamically from server")