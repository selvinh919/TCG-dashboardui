"""
Simple Flask server to serve dashboard and handle sync requests
"""
from flask import Flask, send_file, jsonify, request
import subprocess
import threading
import time
import os
import json
import requests
from bs4 import BeautifulSoup
import re
from difflib import SequenceMatcher


app = Flask(__name__)

# Track last sync time to prevent rate limiting
last_sync_time = 0
SYNC_COOLDOWN = 60  # 60 seconds between syncs

# Search cache (TTL: 5 minutes)
search_cache = {}
SEARCH_CACHE_TTL = 300

from flask import render_template

@app.route('/')
def dashboard():
    return render_template('inventory_dashboard.html')


@app.route('/sync', methods=['POST'])
def sync():
    """Run the sync process (scrape only, don't rebuild HTML)"""
    global last_sync_time
    
    current_time = time.time()
    time_since_last_sync = current_time - last_sync_time
    
    # Check cooldown to prevent rate limiting
    if time_since_last_sync < SYNC_COOLDOWN:
        remaining = int(SYNC_COOLDOWN - time_since_last_sync)
        return jsonify({
            'status': 'error',
            'message': f'Please wait {remaining} seconds before syncing again'
        }), 429
    
    # Update last sync time
    last_sync_time = current_time
    
    # Run sync in background thread
    def run_sync():
        try:
            # Get the Python executable from the virtual environment
            python_exe = os.path.join(os.path.dirname(__file__), '.venv', 'Scripts', 'python.exe')
            if not os.path.exists(python_exe):
                python_exe = 'python'  # Fallback to system python
            
            print("[SYNC] Starting scraper...")
            result1 = subprocess.run([python_exe, 'run.py'], 
                                    capture_output=True, 
                                    text=True,
                                    cwd=os.path.dirname(__file__))
            
            if result1.returncode != 0:
                print(f"[ERROR] Scraper failed: {result1.stderr}")
                return
            
            # DON'T rebuild dashboard - it will overwrite our custom HTML
            # The dashboard will load data from /api/inventory endpoint instead
            print("[SYNC] Complete! Data updated in state.json")
            
        except Exception as e:
            print(f"[ERROR] Sync failed: {e}")
    
    # Start sync in background
    thread = threading.Thread(target=run_sync, daemon=True)
    thread.start()
    
    return jsonify({
        'status': 'success',
        'message': 'Syncing... Inventory will refresh in 3 seconds'
    })

@app.route('/api/inventory', methods=['GET'])
def get_inventory():
    """Return inventory data from state.json"""
    try:
        with open('state.json', 'r', encoding='utf-8') as f:
            items = json.load(f)
        
        # Calculate totals
        total_ask = sum(float(item.get('price', 0)) * item.get('qty', 1) for item in items)
        total_market = sum(item.get('market', 0) * item.get('qty', 1) for item in items if item.get('market'))
        net_delta = total_market - total_ask
        
        return jsonify({
            'status': 'success',
            'items': items,
            'totals': {
                'ask': total_ask,
                'market': total_market,
                'delta': net_delta
            }
        })
    except FileNotFoundError:
        return jsonify({
            'status': 'error',
            'message': 'No inventory data found. Run sync first.',
            'items': [],
            'totals': {'ask': 0, 'market': 0, 'delta': 0}
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e),
            'items': [],
            'totals': {'ask': 0, 'market': 0, 'delta': 0}
        }), 500

@app.route('/api/autocomplete')
def autocomplete():
    """Autocomplete endpoint - uses same logic as search"""
    return search_products()

@app.route('/search-products', methods=['GET'])
def search_products():
    """Search for TCGPlayer products with smart query fallbacks"""
    query = request.args.get('q', '')
    game = request.args.get('game', 'pokemon')
    
    if not query:
        return jsonify({'status': 'error', 'message': 'Search query required'}), 400
    
    # Check cache first
    cache_key = f"{game}:{query.lower()}"
    current_time = time.time()
    
    if cache_key in search_cache:
        cached_data, timestamp = search_cache[cache_key]
        if current_time - timestamp < SEARCH_CACHE_TTL:
            print(f"[SEARCH] Returning cached results for '{query}'")
            cached_data['cached'] = True
            return jsonify(cached_data)
    
    try:
        from playwright.sync_api import sync_playwright
        
        # Try multiple search strategies
        search_queries = [query]
        
        # Strategy 1: Original query
        # Strategy 2: If query contains set code (e.g., "oricorio gg04/gg70"), try just the card name
        query_lower = query.lower()
        if '/' in query or any(c.isdigit() for c in query):
            # Extract likely card name (text before numbers/set codes)
            card_name = re.sub(r'\s*[#\-]*\s*[a-z]*\d+[/\-]?[a-z]*\d*\s*$', '', query, flags=re.IGNORECASE).strip()
            if card_name and card_name != query:
                search_queries.append(card_name)
                print(f"[SEARCH] Extracted card name: '{card_name}'")
        
        # Strategy 3: Remove special characters and try again
        clean_query = re.sub(r'[#\-/]', ' ', query).strip()
        if clean_query != query and clean_query not in search_queries:
            search_queries.append(clean_query)
        
        print(f"[SEARCH] Will try {len(search_queries)} search strategies: {search_queries}")
        
        results = []
        
        # Create browser for this search (optimized for speed)
        with sync_playwright() as p:
            profile_path = os.path.join(os.path.dirname(__file__), 'tcg_playwright_profile')
            
            browser = p.chromium.launch_persistent_context(
                profile_path,
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-features=IsolateOrigins,site-per-process',
                    '--disable-site-isolation-trials',
                    '--disable-gpu',
                    '--disable-dev-shm-usage',
                    '--disable-extensions',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-web-security',
                    '--disable-features=VizDisplayCompositor'
                ],
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1280, 'height': 720},
                java_script_enabled=True,
                ignore_https_errors=True
            )
            
            page = browser.pages[0] if browser.pages else browser.new_page()
            
            # Try each search query until we get results
            for attempt, search_query in enumerate(search_queries):
                search_url = f"https://www.tcgplayer.com/search/{game}/product?productLineName={game}&q={requests.utils.quote(search_query)}&view=grid"
                
                print(f"[SEARCH] Attempt {attempt + 1}: {search_url}")
                # Use 'commit' for fastest loading - don't wait for all resources
                page.goto(search_url, wait_until='commit', timeout=10000)
                
                # Wait only for product links to appear
                try:
                    page.wait_for_selector('a[href*="/product/"]', timeout=2000)
                except:
                    # If no products found quickly, wait a bit more
                    page.wait_for_timeout(500)
                
                # Get all product links in one go
                all_links = page.query_selector_all('a[href*="/product/"]')
                print(f"[SEARCH] Found {len(all_links)} product links")
                
                seen_ids = set()
                
                for link in all_links[:60]:  # Check up to 60 links for more results
                    try:
                        href = link.get_attribute('href')
                        if not href:
                            continue
                        
                        # Extract product ID from URL
                        match = re.search(r'/product/(\d+)', href)
                        if not match:
                            continue
                        
                        product_id = match.group(1)
                        
                        # Skip duplicates
                        if product_id in seen_ids:
                            continue
                        seen_ids.add(product_id)
                        
                        # Get product name - optimized single pass
                        name = ''
                        
                        try:
                            # Try getting text content first (fastest)
                            text = link.inner_text().strip()
                            if text and 3 < len(text) < 200 and not text.lower().startswith('view'):
                                name = text
                            else:
                                # Fallback: try img alt or aria-label
                                img = link.query_selector('img')
                                if img:
                                    alt = img.get_attribute('alt')
                                    if alt and len(alt) > 3:
                                        name = alt
                                if not name:
                                    aria_label = link.get_attribute('aria-label')
                                    if aria_label and len(aria_label) > 3:
                                        name = aria_label
                        except:
                            pass
                        
                        if not name:
                            continue
                        
                        # Quick cleanup - minimal processing for speed
                        name = ' '.join(name.split())
                        
                        # Fast price extraction - get both market and lowest prices
                        lowest_price = 0
                        market_price = 0
                        
                        # Extract lowest price from "XXX listings from $X.XX" pattern
                        lowest_match = re.search(r'listings\s+from\s+\$(\d+\.\d{2})', name)
                        if lowest_match:
                            lowest_price = float(lowest_match.group(1))
                        
                        # Extract market price from "Market Price: $X.XX" pattern
                        market_match = re.search(r'Market\s+Price:\s*\$(\d+\.\d{2})', name)
                        if market_match:
                            market_price = float(market_match.group(1))
                        
                        # Quick name cleaning - remove price text
                        display_name = re.sub(r'\d+\s+listings.*', '', name)
                        display_name = re.sub(r'Market\s+Price.*', '', display_name)
                        display_name = display_name.strip()
                        
                        # Clean up redundant information and formatting
                        # Remove product type prefixes like "Miscellaneous Cards & Products Rare, "
                        display_name = re.sub(r'^[^#]+?,\s*', '', display_name)
                        
                        # Extract the main card number pattern (e.g., #059/131 or #059)
                        card_number = ''
                        number_match = re.search(r'#([\d/]+)', display_name)
                        if number_match:
                            card_number = number_match.group(1)
                            # Remove duplicate card numbers at the end if they match
                            # e.g., "Umbreon - 059 (Cosmos Holo) #059/131" -> keep only one
                            if card_number:
                                # Remove trailing duplicate: "#059/131" at the end
                                display_name = re.sub(r'\s*#?' + re.escape(card_number) + r'\s*$', '', display_name)
                                # Remove leading duplicate: "#059/131 " at the start
                                display_name = re.sub(r'^#?' + re.escape(card_number) + r'\s+', '', display_name)
                        
                        # Final cleanup - remove extra spaces and trailing dashes
                        display_name = re.sub(r'\s+', ' ', display_name).strip()
                        display_name = display_name.strip(' ,-')
                        
                        # Improved image URL extraction - check multiple sources
                        image_url = ''
                        try:
                            img = link.query_selector('img')
                            if img:
                                # Try multiple image source attributes (for lazy loading)
                                src = (img.get_attribute('src') or 
                                       img.get_attribute('data-src') or 
                                       img.get_attribute('data-lazy-src') or 
                                       img.get_attribute('data-image') or
                                       '')
                                
                                # Also check srcset if src is empty or placeholder
                                if not src or 'placeholder' in src.lower() or 'data:' in src:
                                    srcset = img.get_attribute('srcset') or ''
                                    if srcset:
                                        # Extract first URL from srcset
                                        first_url = srcset.split(',')[0].strip().split(' ')[0]
                                        if first_url:
                                            src = first_url
                                
                                # Validate and clean image URL
                                if src:
                                    if src.startswith('//'):
                                        image_url = 'https:' + src
                                    elif src.startswith('/'):
                                        image_url = 'https://www.tcgplayer.com' + src
                                    elif src.startswith('http'):
                                        image_url = src
                                    
                                    # Skip invalid images: data URIs, svgs, placeholders, "coming soon" images
                                    skip_patterns = ['data:', '.svg', 'placeholder', 'coming-soon', 'comingsoon', 'no-image', 'noimage']
                                    if any(pattern in image_url.lower() for pattern in skip_patterns):
                                        image_url = ''
                        except:
                            pass
                        
                        # Fallback to CDN image when missing
                        if not image_url and product_id:
                            image_url = f"https://tcgplayer-cdn.tcgplayer.com/product/{product_id}_in_200x200.jpg"

                        results.append({
                            'productId': product_id,
                            'name': display_name[:150],
                            'fullName': display_name[:150],
                            'set': game.title(),
                            'number': card_number,
                            'imageUrl': image_url,
                            'marketPrice': market_price,
                            'lowestPrice': lowest_price
                        })
                        
                        # Collect more results for better selection
                        if len(results) >= 30:
                            break
                    
                    except Exception as e:
                        continue
                
                # If we found results, stop trying other queries
                if len(results) > 0:
                    print(f"[SEARCH] Found {len(results)} results with query: '{search_query}'")
                    break
            
            # If we searched by card name alone and original query had a set code, try to filter results
            if len(results) > 1 and len(search_queries) > 1 and attempt > 0:
                # Extract set code from original query (e.g., "gg04", "183/159")
                original_lower = query.lower()
                set_code_match = re.search(r'([a-z]*\d+[/\-]?[a-z]*\d+)', original_lower)
                if set_code_match:
                    set_code = set_code_match.group(1).replace('-', '/').replace(' ', '')
                    print(f"[SEARCH] Filtering results for set code: {set_code}")
                    
                    # Filter results that match the set code
                    filtered = [r for r in results if set_code in r.get('number', '').lower() or set_code in r.get('fullName', '').lower()]
                    if filtered:
                        results = filtered
            
            browser.close()
        
        print(f"[SEARCH] Returning {len(results)} products for '{query}'")
        
        # Cache the results
        response_data = {'status': 'success', 'results': results, 'cached': False}
        search_cache[cache_key] = (response_data, current_time)
        
        # Clean old cache entries (keep cache size manageable)
        if len(search_cache) > 100:
            oldest_keys = sorted(search_cache.keys(), key=lambda k: search_cache[k][1])[:20]
            for key in oldest_keys:
                del search_cache[key]
        
        return jsonify(response_data)
        
    except Exception as e:
        print(f"[ERROR] Search failed: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/pending-sales')
def get_pending_sales():
    """Return pending sales data"""
    try:
        with open('pending_sales.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify({'status': 'success', 'sales': data})
    except FileNotFoundError:
        return jsonify({'status': 'success', 'sales': []})

@app.route('/api/settings', methods=['GET'])
def get_settings():
    """Return settings data"""
    try:
        with open('settings.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify({'status': 'success', 'settings': data})
    except FileNotFoundError:
        return jsonify({'status': 'success', 'settings': {}})

@app.route('/mark-added', methods=['POST'])
def mark_added():
    """Mark a product as recently added"""
    try:
        data = request.json
        product_id = data.get('productId')
        
        if not product_id:
            return jsonify({'status': 'error', 'message': 'Product ID required'}), 400
        
        # Load recently added list
        recently_added_file = 'recently_added.json'
        recently_added = []
        
        if os.path.exists(recently_added_file):
            with open(recently_added_file, 'r') as f:
                recently_added = json.load(f)
        
        # Add product if not already in list
        if product_id not in recently_added:
            recently_added.append(product_id)
            
            with open(recently_added_file, 'w') as f:
                json.dump(recently_added, f)
        
        return jsonify({'status': 'success', 'message': 'Product marked as recently added'})
        
    except Exception as e:
        print(f"[ERROR] Mark added failed: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/email-scrape', methods=['POST'])
def email_scrape():
    """Trigger email scraping for sold orders"""
    try:
        def run_email_scrape():
            try:
                python_exe = os.path.join(os.path.dirname(__file__), '.venv', 'Scripts', 'python.exe')
                if not os.path.exists(python_exe):
                    python_exe = 'python'
                
                print("[EMAIL_SCRAPE] Starting email scraper...")
                result = subprocess.run([python_exe, 'email_scraper.py'], 
                                      capture_output=True, 
                                      text=True,
                                      cwd=os.path.dirname(__file__))
                
                if result.returncode == 0:
                    print("[EMAIL_SCRAPE] Complete!")
                    # Automatically run auto-match after scraping
                    print("[EMAIL_SCRAPE] Auto-matching with inventory...")
                    auto_match_pending_sales_internal()
                else:
                    print(f"[ERROR] Email scraper failed: {result.stderr}")
                    
            except Exception as e:
                print(f"[ERROR] Email scrape failed: {e}")
        
        thread = threading.Thread(target=run_email_scrape, daemon=True)
        thread.start()
        
        return jsonify({
            'status': 'success',
            'message': 'Email scraping started... Check pending sales in a few moments.'
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/sold/pending', methods=['GET'])
def get_pending_sales_api():
    """Get pending sales that need confirmation"""
    try:
        with open('pending_sales.json', 'r', encoding='utf-8') as f:
            sales = json.load(f)

        # Auto-enrich pending sales with inventory metadata (images, tcg_product_id)
        if sales and os.path.exists('state.json'):
            with open('state.json', 'r', encoding='utf-8') as f:
                inventory = json.load(f)
            if enrich_items_with_inventory(sales, inventory):
                with open('pending_sales.json', 'w', encoding='utf-8') as f:
                    json.dump(sales, f, indent=2)

        return jsonify({'status': 'success', 'sales': sales})
    except FileNotFoundError:
        return jsonify({'status': 'success', 'sales': []})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/sold/pending/update', methods=['POST'])
def update_pending_sale():
    """Update a pending sale (edit details before confirming)"""
    try:
        data = request.json
        sale_id = data.get('id')
        
        with open('pending_sales.json', 'r', encoding='utf-8') as f:
            sales = json.load(f)
        
        for sale in sales:
            if sale.get('id') == sale_id:
                sale.update({
                    'name': data.get('name', sale.get('name')),
                    'qty': data.get('qty', sale.get('qty')),
                    'sold_price': data.get('sold_price', sale.get('sold_price')),
                    'cost': data.get('cost', sale.get('cost')),
                    'platform': data.get('platform', sale.get('platform')),
                    'sold_date': data.get('sold_date', sale.get('sold_date'))
                })
                break
        
        with open('pending_sales.json', 'w', encoding='utf-8') as f:
            json.dump(sales, f, indent=2)
        
        return jsonify({'status': 'success', 'message': 'Sale updated'})
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/sold/pending/confirm', methods=['POST'])
def confirm_pending_sale():
    """Confirm a pending sale and move it to sold items"""
    try:
        data = request.json
        sale_id = data.get('id')
        
        with open('pending_sales.json', 'r', encoding='utf-8') as f:
            pending_sales = json.load(f)
        
        confirmed_sale = None
        remaining_sales = []
        for sale in pending_sales:
            if sale.get('id') == sale_id:
                confirmed_sale = sale.copy()  # Make a copy to preserve all data
                confirmed_sale['confirmed'] = True
                # Ensure image and tcg_product_id are preserved
                if not confirmed_sale.get('image'):
                    confirmed_sale['image'] = None
                if not confirmed_sale.get('tcg_product_id'):
                    confirmed_sale['tcg_product_id'] = None
            else:
                remaining_sales.append(sale)
        
        if not confirmed_sale:
            return jsonify({'status': 'error', 'message': 'Sale not found'}), 404
        
        sold_file = 'sold_items.json'
        sold_items = []
        if os.path.exists(sold_file):
            with open(sold_file, 'r', encoding='utf-8') as f:
                try:
                    sold_items = json.load(f)
                except:
                    sold_items = []
        
        sold_items.append(confirmed_sale)
        
        with open('pending_sales.json', 'w', encoding='utf-8') as f:
            json.dump(remaining_sales, f, indent=2)
        
        with open(sold_file, 'w', encoding='utf-8') as f:
            json.dump(sold_items, f, indent=2)
        
        return jsonify({'status': 'success', 'message': 'Sale confirmed and moved to sold items'})
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/sold/pending/delete', methods=['POST'])
def delete_pending_sale():
    """Delete a pending sale"""
    try:
        data = request.json
        sale_id = data.get('id')
        
        with open('pending_sales.json', 'r', encoding='utf-8') as f:
            sales = json.load(f)
        
        sales = [s for s in sales if s.get('id') != sale_id]
        
        with open('pending_sales.json', 'w', encoding='utf-8') as f:
            json.dump(sales, f, indent=2)
        
        return jsonify({'status': 'success', 'message': 'Sale deleted'})
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/sold-items', methods=['GET'])
def get_sold_items():
    """Get all confirmed sold items"""
    try:
        with open('sold_items.json', 'r', encoding='utf-8') as f:
            items = json.load(f)

        # Auto-enrich sold items with inventory metadata (images, tcg_product_id)
        if items and os.path.exists('state.json'):
            with open('state.json', 'r', encoding='utf-8') as f:
                inventory = json.load(f)
            if enrich_items_with_inventory(items, inventory):
                with open('sold_items.json', 'w', encoding='utf-8') as f:
                    json.dump(items, f, indent=2)
        
        total_revenue = sum(item.get('sold_price', 0) * item.get('qty', 1) for item in items)
        total_cost = sum(item.get('cost', 0) * item.get('qty', 1) for item in items)
        total_profit = total_revenue - total_cost
        
        return jsonify({
            'status': 'success',
            'items': items,
            'totals': {
                'revenue': total_revenue,
                'cost': total_cost,
                'profit': total_profit
            }
        })
    except FileNotFoundError:
        return jsonify({
            'status': 'success',
            'items': [],
            'totals': {'revenue': 0, 'cost': 0, 'profit': 0}
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/settings', methods=['POST'])
def save_settings():
    """Save settings including email credentials"""
    try:
        settings = request.json
        with open('settings.json', 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2)
        return jsonify({'status': 'success', 'message': 'Settings saved'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

def fuzzy_match_score(str1, str2):
    """Calculate similarity score between two strings (0-1)"""
    return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()

def enrich_items_with_inventory(items, inventory, min_score=0.9):
    """Fill missing image/tcg fields on pending/sold items by matching inventory."""
    updated = False
    for item in items:
        if item.get('image') and item.get('tcg_product_id'):
            continue

        # 1) Exact product ID match if present
        item_pid = item.get('tcg_product_id')
        if item_pid:
            exact = next((inv for inv in inventory if str(inv.get('tcg_product_id')) == str(item_pid)), None)
            if exact:
                if not item.get('image'):
                    item['image'] = exact.get('image')
                    updated = True
                if not item.get('set_name'):
                    item['set_name'] = exact.get('set_name')
                    updated = True
                if not item.get('card_number'):
                    item['card_number'] = exact.get('card_number')
                    updated = True
                if not item.get('market'):
                    item['market'] = exact.get('market')
                    updated = True
                continue

        # 2) Set + card number match if present
        item_set = (item.get('set_name') or '').strip().lower()
        item_num = (item.get('card_number') or '').strip().lower()
        if item_set and item_num:
            exact = next(
                (inv for inv in inventory
                 if (inv.get('set_name') or '').strip().lower() == item_set
                 and (inv.get('card_number') or '').strip().lower() == item_num),
                None
            )
            if exact:
                if not item.get('image'):
                    item['image'] = exact.get('image')
                    updated = True
                if not item.get('tcg_product_id'):
                    item['tcg_product_id'] = exact.get('tcg_product_id')
                    updated = True
                if not item.get('market'):
                    item['market'] = exact.get('market')
                    updated = True
                continue

        # 3) Fuzzy match by name with higher threshold
        item_name = (item.get('name') or item.get('display_name') or '').strip()
        if not item_name:
            continue

        best_match = None
        best_score = 0
        for inv in inventory:
            inv_name = (inv.get('display_name') or inv.get('name') or '').strip()
            if not inv_name:
                continue
            score = fuzzy_match_score(item_name, inv_name)
            if score > best_score:
                best_score = score
                best_match = inv

        if best_match and best_score >= min_score:
            if not item.get('image'):
                item['image'] = best_match.get('image')
                updated = True
            if not item.get('tcg_product_id'):
                item['tcg_product_id'] = best_match.get('tcg_product_id')
                updated = True
            if not item.get('set_name'):
                item['set_name'] = best_match.get('set_name')
                updated = True
            if not item.get('card_number'):
                item['card_number'] = best_match.get('card_number')
                updated = True
            if not item.get('market'):
                item['market'] = best_match.get('market')
                updated = True

    return updated

@app.route('/api/sold/pending/match-inventory', methods=['POST'])
def match_pending_with_inventory():
    """
    Match a pending sale with inventory items
    Returns potential matches from current inventory
    """
    try:
        data = request.json
        sale_name = data.get('name', '')
        
        # Load current inventory
        if not os.path.exists('state.json'):
            return jsonify({
                'status': 'error',
                'message': 'Inventory not initialized. Run sync first.'
            }), 400

        with open('state.json', 'r', encoding='utf-8') as f:
            inventory = json.load(f)
        
        # Find matches
        matches = []
        for item in inventory:
            item_name = item.get('name', '')
            
            # Calculate similarity
            score = fuzzy_match_score(sale_name, item_name)
            
            # Include if score > 0.7 or exact match
            if score > 0.7:
                matches.append({
                    'score': round(score, 2),
                    'inventory_item': item,
                    'match_type': 'exact' if score > 0.95 else 'fuzzy'
                })
        
        # Sort by score descending
        matches.sort(key=lambda x: x['score'], reverse=True)
        
        return jsonify({
            'status': 'success',
            'matches': matches[:5]  # Return top 5 matches
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


def auto_match_pending_sales_internal():
    """Internal function to auto-match pending sales with inventory"""
    try:
        # Load pending sales
        if not os.path.exists('pending_sales.json'):
            return 0
            
        with open('pending_sales.json', 'r', encoding='utf-8') as f:
            pending_sales = json.load(f)
        
        # Load inventory
        if not os.path.exists('state.json'):
            return jsonify({
                'status': 'error',
                'message': 'Inventory not initialized. Run sync first.'
            }), 400

        with open('state.json', 'r', encoding='utf-8') as f:
            inventory = json.load(f)
        
        match_count = 0
        
        for sale in pending_sales:
            if sale.get('matched'):
                continue  # Skip already matched
            
            sale_name = sale.get('name', '')
            best_match = None
            best_score = 0
            
            # Find best match
            for item in inventory:
                item_name = item.get('name', '')
                score = fuzzy_match_score(sale_name, item_name)
                
                if score > best_score:
                    best_score = score
                    best_match = item
            
            # If good match found (>80% similarity)
            if best_match and best_score > 0.8:
                # Update sale with inventory data
                sale['matched'] = True
                sale['match_score'] = round(best_score, 2)
                sale['tcg_product_id'] = best_match.get('tcg_product_id')
                sale['image'] = best_match.get('image')
                sale['set_name'] = best_match.get('set_name')
                sale['card_number'] = best_match.get('card_number')
                sale['market'] = best_match.get('market')
                
                # If inventory has cost, use it
                if best_match.get('cost'):
                    sale['cost'] = best_match.get('cost')
                
                # If inventory has price, use as guide for sold_price
                if sale.get('sold_price', 0) == 0 and best_match.get('price'):
                    sale['suggested_price'] = best_match.get('price')
                
                match_count += 1
        
        # Save updated pending sales
        with open('pending_sales.json', 'w', encoding='utf-8') as f:
            json.dump(pending_sales, f, indent=2)
        
        print(f"[AUTO_MATCH] Matched {match_count} items with inventory")
        return match_count
        
    except Exception as e:
        print(f"[ERROR] Auto-match failed: {e}")
        return 0

@app.route('/api/sold/pending/auto-match', methods=['POST'])
def auto_match_pending_sales():
    """
    Automatically match all pending sales with inventory
    Updates pending sales with inventory data
    """
    try:
        match_count = auto_match_pending_sales_internal()
        return jsonify({
            'status': 'success',
            'message': f'Matched {match_count} items with inventory',
            'matched_count': match_count
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/sold/pending/allocate-price', methods=['POST'])
def allocate_order_price():
    """
    Auto-allocate order total to items based on market prices
    """
    try:
        data = request.json
        order_id = data.get('order_id')
        
        if not order_id:
            return jsonify({'status': 'error', 'message': 'Order ID required'}), 400
        
        # Load pending sales
        with open('pending_sales.json', 'r', encoding='utf-8') as f:
            pending_sales = json.load(f)
        
        # Find all items for this order
        order_items = [s for s in pending_sales if s.get('order_id') == order_id]
        
        if not order_items:
            return jsonify({'status': 'error', 'message': 'No items found for order'}), 404
        
        # Get order total
        order_total = order_items[0].get('order_total', 0)
        
        if order_total == 0:
            return jsonify({'status': 'error', 'message': 'Order total is 0'}), 400
        
        # Calculate total market value
        total_market = sum(item.get('market', 0) for item in order_items)
        
        if total_market == 0:
            # Equal split if no market prices
            price_per_item = order_total / len(order_items)
            for item in order_items:
                item['sold_price'] = round(price_per_item, 2)
        else:
            # Proportional split based on market prices
            for item in order_items:
                market_value = item.get('market', 0)
                proportion = market_value / total_market
                item['sold_price'] = round(order_total * proportion, 2)
        
        # Save updated pending sales
        with open('pending_sales.json', 'w', encoding='utf-8') as f:
            json.dump(pending_sales, f, indent=2)
        
        return jsonify({
            'status': 'success',
            'message': f'Allocated ${order_total} to {len(order_items)} items'
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/sold/pending/confirm-with-inventory-update', methods=['POST'])
def confirm_sale_and_update_inventory():
    """
    Confirm a pending sale AND update inventory (decrement qty or remove)
    """
    try:
        data = request.json
        sale_id = data.get('id')
        update_inventory = data.get('update_inventory', True)
        
        # Load pending sales
        with open('pending_sales.json', 'r', encoding='utf-8') as f:
            pending_sales = json.load(f)
        
        # Find the sale
        confirmed_sale = None
        remaining_sales = []
        for sale in pending_sales:
            if sale.get('id') == sale_id:
                confirmed_sale = sale
                confirmed_sale['confirmed'] = True
            else:
                remaining_sales.append(sale)
        
        if not confirmed_sale:
            return jsonify({'status': 'error', 'message': 'Sale not found'}), 404
        
        # Update inventory if requested
        if not os.path.exists('state.json'):
            return jsonify({
                'status': 'error',
                'message': 'Inventory not initialized. Run sync first.'
            }), 400
        if update_inventory and confirmed_sale.get('matched'):
            with open('state.json', 'r', encoding='utf-8') as f:
                inventory = json.load(f)
            
            # Find matching inventory item
            sale_name = confirmed_sale.get('name', '')
            for i, item in enumerate(inventory):
                if fuzzy_match_score(sale_name, item.get('name', '')) > 0.8:
                    # Decrement quantity
                    current_qty = item.get('qty', 1)
                    sold_qty = confirmed_sale.get('qty', 1)
                    new_qty = max(0, current_qty - sold_qty)
                    
                    if new_qty == 0:
                        # Remove from inventory
                        inventory.pop(i)
                    else:
                        # Update quantity
                        inventory[i]['qty'] = new_qty
                    
                    break
            
            # Save updated inventory
            with open('state.json', 'w', encoding='utf-8') as f:
                json.dump(inventory, f, indent=2)
        
        # Add to sold items
        sold_file = 'sold_items.json'
        sold_items = []
        if os.path.exists(sold_file):
            with open(sold_file, 'r', encoding='utf-8') as f:
                try:
                    sold_items = json.load(f)
                except:
                    sold_items = []
        
        # Calculate profit
        sold_price = confirmed_sale.get('sold_price', 0)
        cost = confirmed_sale.get('cost', 0)
        qty = confirmed_sale.get('qty', 1)
        confirmed_sale['profit'] = round((sold_price - cost) * qty, 2)
        
        sold_items.append(confirmed_sale)
        
        # Save files
        with open('pending_sales.json', 'w', encoding='utf-8') as f:
            json.dump(remaining_sales, f, indent=2)
        
        with open(sold_file, 'w', encoding='utf-8') as f:
            json.dump(sold_items, f, indent=2)
        
        return jsonify({
            'status': 'success',
            'message': 'Sale confirmed and inventory updated',
            'inventory_updated': update_inventory
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/sold/stats', methods=['GET'])
def get_sold_stats():
    """
    Get statistics for sold items
    """
    try:
        # Load sold items
        sold_file = 'sold_items.json'
        if not os.path.exists(sold_file):
            return jsonify({
                'status': 'success',
                'stats': {
                    'total_items': 0,
                    'total_revenue': 0,
                    'total_cost': 0,
                    'total_profit': 0,
                    'avg_profit_margin': 0
                }
            })
        
        with open(sold_file, 'r', encoding='utf-8') as f:
            sold_items = json.load(f)
        
        total_items = len(sold_items)
        total_revenue = sum(item.get('sold_price', 0) * item.get('qty', 1) for item in sold_items)
        total_cost = sum(item.get('cost', 0) * item.get('qty', 1) for item in sold_items)
        total_profit = total_revenue - total_cost
        avg_profit_margin = (total_profit / total_revenue * 100) if total_revenue > 0 else 0
        
        # Group by platform
        platform_stats = {}
        for item in sold_items:
            platform = item.get('platform', 'Unknown')
            if platform not in platform_stats:
                platform_stats[platform] = {'count': 0, 'revenue': 0}
            platform_stats[platform]['count'] += item.get('qty', 1)
            platform_stats[platform]['revenue'] += item.get('sold_price', 0) * item.get('qty', 1)
        
        # Recent sales (last 30 days)
        from datetime import datetime, timedelta
        thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        recent_sales = [
            item for item in sold_items 
            if item.get('sold_date', '') >= thirty_days_ago
        ]
        recent_revenue = sum(item.get('sold_price', 0) * item.get('qty', 1) for item in recent_sales)
        
        return jsonify({
            'status': 'success',
            'stats': {
                'total_items': total_items,
                'total_revenue': round(total_revenue, 2),
                'total_cost': round(total_cost, 2),
                'total_profit': round(total_profit, 2),
                'avg_profit_margin': round(avg_profit_margin, 2),
                'platform_stats': platform_stats,
                'recent_sales_30d': len(recent_sales),
                'recent_revenue_30d': round(recent_revenue, 2)
            }
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# Add this helper function at module level
def init_enhanced_endpoints(flask_app):
    """
    Initialize all enhanced endpoints
    Call this from your main server.py after app is created
    """
    # All endpoints are already decorated above
    pass


if __name__ == '__main__':
    print("=" * 60)
    print("TCG Inventory Dashboard Server")
    print("=" * 60)
    print("Dashboard: http://localhost:5000")
    print("Press Ctrl+C to stop")
    print("=" * 60)
    app.run(debug=False, port=5000)
