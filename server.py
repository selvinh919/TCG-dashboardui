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

app = Flask(__name__)

# Track last sync time to prevent rate limiting
last_sync_time = 0
SYNC_COOLDOWN = 60  # 60 seconds between syncs

# Search cache (TTL: 5 minutes)
search_cache = {}
SEARCH_CACHE_TTL = 300

@app.route('/')
def dashboard():
    """Serve the dashboard HTML"""
    response = send_file('inventory_dashboard.html')
    # Prevent caching in browser
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

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
                
                for link in all_links[:30]:  # Check up to 30 links for more results
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
                        if len(results) >= 15:
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

@app.route('/api/settings')
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

if __name__ == '__main__':
    print("=" * 60)
    print("TCG Inventory Dashboard Server")
    print("=" * 60)
    print("Dashboard: http://localhost:5000")
    print("Press Ctrl+C to stop")
    print("=" * 60)
    app.run(debug=False, port=5000)
