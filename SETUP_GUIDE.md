# TCG Inventory Bot - Clean Setup

## Active Files

### Core Files (Required)
- **server.py** - Flask web server with API endpoints
- **run.py** - Scraper orchestrator
- **scraper.py** - TCGPlayer web scraper
- **config.py** - Configuration settings
- **analyzer.py** - Price change analysis
- **notifier.py** - Desktop notifications
- **utils.py** - Helper functions
- **inventory_dashboard.html** - Dynamic web dashboard

### Data Files
- **state.json** - Current inventory data
- **image_cache.json** - Cached product images
- **recently_added.json** - Tracks newly added products

### Folders
- **.venv/** - Python virtual environment
- **tcg_playwright_profile/** - Browser profile for scraping

## Removed Files
- ❌ build_dashboard.py - No longer needed (dashboard now loads dynamically)
- ❌ card_debug.html - Debug file
- ❌ inspect_tcg_html.py - Debug script
- ❌ manual_true_check.py - Debug script
- ❌ justtcg.py - Unused
- ❌ pokemon_tcg_api.py - Not used (we use HTML scraping instead)

## How It Works

### 1. Search & Add Products
- Search TCGPlayer from dashboard
- View market and lowest prices
- Add to pending list with quantity

### 2. Set Prices
- Cost price: $ or % of market
- Ask price: Your selling price
- Quantity: How many copies

### 3. Add to TCGPlayer
- Click "Add to TCGPlayer"
- Opens admin page
- Fill in prices and save

### 4. Sync
- Click "Sync" button
- Scrapes your inventory
- Updates dashboard (3 seconds)
- No page reload needed!

## API Endpoints

- `GET /` - Dashboard HTML
- `GET /api/inventory` - Get inventory data
- `POST /sync` - Sync inventory from TCGPlayer
- `GET /search-products?q=...&game=...` - Search products
- `POST /mark-added` - Mark product as recently added

## Features

✅ Real-time inventory loading
✅ Product search (6 TCG games)
✅ Pending products staging
✅ eBay affiliate links
✅ Smart cost pricing ($ or %)
✅ Quantity management
✅ Fast sync (3 seconds)
✅ No page reload needed
✅ Browser cache prevention
