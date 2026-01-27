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

@app.route('/search-products', methods=['GET'])
def search_products():
    """Search for TCGPlayer products with smart query fallbacks"""
    query = request.args.get('q', '')
    game = request.args.get('game', 'pokemon')
    
    if not query:
        return jsonify({'status': 'error', 'message': 'Search query required'}), 400
    
    try:
        from playwright.sync_api import sync_playwright
        
        # Try multiple search strategies
        search_queries = [query]
        
        # Strategy 1: Original query
        # Strategy 2: If query contains set code (e.g., "oricorio gg04/gg70"), try just the card name
        query_lower = query.lower()
        if '/' in query or any(c.isdigit() for c in query):
            # Extract likely card name (text before numbers/set codes)
            import re
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
        
        with sync_playwright() as p:
            profile_path = os.path.join(os.path.dirname(__file__), 'tcg_playwright_profile')
            
            browser = p.chromium.launch_persistent_context(
                profile_path,
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-features=IsolateOrigins,site-per-process',
                    '--disable-site-isolation-trials'
                ],
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080},
                java_script_enabled=True
            )
            
            page = browser.pages[0] if browser.pages else browser.new_page()
            
            # Try each search query until we get results
            for attempt, search_query in enumerate(search_queries):
                search_url = f"https://www.tcgplayer.com/search/{game}/product?productLineName={game}&q={requests.utils.quote(search_query)}&view=grid"
                
                print(f"[SEARCH] Attempt {attempt + 1}: {search_url}")
                page.goto(search_url, wait_until='domcontentloaded', timeout=20000)
                
                # Wait for results
                try:
                    page.wait_for_selector('article, .product-card, .search-result, [class*="product"]', timeout=5000)
                    print(f"[SEARCH] Products loaded")
                except:
                    print(f"[SEARCH] Timeout waiting for products")
                
                page.wait_for_timeout(1500)
                
                # Get page HTML and check for results
                html_content = page.content()
                print(f"[SEARCH] Page HTML length: {len(html_content)}")
                
                # Try multiple selector strategies
                product_links = []
                all_links = page.query_selector_all('a[href*="/product/"]')
                print(f"[SEARCH] Found {len(all_links)} product links")
                
                seen_ids = set()
                
                for link in all_links[:30]:  # Check up to 30 links
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
                        
                        # Get product name - try multiple methods
                        name = ''
                        
                        # Method 1: Get text from the link
                        try:
                            text = link.inner_text().strip()
                            if text and 3 < len(text) < 200 and not text.lower().startswith('view'):
                                name = text
                                print(f"[SEARCH] Product {product_id}: {name}")
                        except:
                            pass
                        
                        # Method 2: Try alt text from image
                        if not name:
                            try:
                                img = link.query_selector('img')
                                if img:
                                    alt = img.get_attribute('alt')
                                    if alt and len(alt) > 3:
                                        name = alt
                                        print(f"[SEARCH] Product {product_id} (from img alt): {name}")
                            except:
                                pass
                        
                        # Method 3: Get aria-label
                        if not name:
                            try:
                                aria_label = link.get_attribute('aria-label')
                                if aria_label and len(aria_label) > 3:
                                    name = aria_label
                                    print(f"[SEARCH] Product {product_id} (from aria): {name}")
                            except:
                                pass
                        
                        if not name:
                            print(f"[SEARCH] Skipping product {product_id} - no name found")
                            continue
                        
                        # Clean up name
                        name = ' '.join(name.split())
                        
                        # Initialize prices
                        lowest_price = 0
                        market_price = 0
                        
                        # Extract lowest price from "XXX listings from $X.XX" pattern
                        lowest_match = re.search(r'(\d+)\s+listings\s+from\s+\$([\d.]+)', name)
                        if lowest_match:
                            lowest_price = float(lowest_match.group(2))
                            print(f"[SEARCH] Found lowest price in text: ${lowest_price}")
                        
                        # Extract market price from "Market Price:$X.XX" pattern
                        market_match = re.search(r'Market\s+Price:\s*\$([\d.]+)', name)
                        if market_match:
                            market_price = float(market_match.group(1))
                            print(f"[SEARCH] Found market price in text: ${market_price}")
                        
                        # Clean the product name - remove extra data
                        # Pattern: "SET, #NUMBER NAME - NUMBER XXX listings from $X.XX Market Price:$X.XX"
                        cleaned_name = name
                        
                        # Remove "XXX listings from $X.XX" pattern
                        cleaned_name = re.sub(r'\d+\s+listings\s+from\s+\$[\d.]+', '', cleaned_name)
                        
                        # Remove "Market Price:$X.XX" pattern
                        cleaned_name = re.sub(r'Market\s+Price:\s*\$[\d.]+', '', cleaned_name)
                        
                        # Try to extract card number if present
                        card_number = ''
                        number_match = re.search(r'#(\d+[^\s]*)', cleaned_name)
                        if number_match:
                            card_number = number_match.group(1)
                        
                        # Remove duplicate card numbers (e.g., "#173 Eevee - 173")
                        cleaned_name = re.sub(r'\s*-\s*\d+\s*$', '', cleaned_name)
                        
                        # Clean up extra commas, spaces, and dashes
                        cleaned_name = re.sub(r'\s*,\s*#', ' #', cleaned_name)
                        cleaned_name = re.sub(r'\s+', ' ', cleaned_name).strip()
                        
                        # Try to extract set name (everything before first comma or "Promo, #")
                        set_name = game.title()
                        set_match = re.match(r'^([^,#]+?)(?:,|\s+Promo|\s+#)', cleaned_name)
                        if set_match:
                            set_name = set_match.group(1).strip()
                        
                        # Get just the card name (after # or after set name)
                        card_name_only = cleaned_name
                        if '#' in cleaned_name:
                            parts = cleaned_name.split('#', 1)
                            if len(parts) > 1:
                                # Get everything after the #NUMBER part
                                after_number = parts[1]
                                # Remove the number itself
                                card_name_only = re.sub(r'^[\d/]+\s*', '', after_number).strip()
                        
                        # Final cleanup
                        card_name_only = card_name_only.strip(' ,-')
                        
                        print(f"[SEARCH] Cleaned: {card_name_only} (#{card_number}) Market:${market_price} Lowest:${lowest_price}")
                        
                        # Get image URL
                        image_url = ''
                        try:
                            img = link.query_selector('img')
                            if img:
                                src = img.get_attribute('src')
                                if src:
                                    if src.startswith('//'):
                                        image_url = 'https:' + src
                                    elif src.startswith('/'):
                                        image_url = 'https://www.tcgplayer.com' + src
                                    elif src.startswith('http'):
                                        image_url = src
                        except:
                            pass
                        
                        # Try to find market price from parent element if not already found
                        if market_price == 0:
                            try:
                                # Look for parent article/card container
                                parent = link.evaluate_handle('el => el.closest("article, [class*=\"product\"], [class*=\"card\"]")')
                                if parent:
                                    # Get all text from parent
                                    parent_text = parent.as_element().inner_text()
                                    # Look for price patterns like $1.23 or Market Price: $1.23
                                    price_matches = re.findall(r'\$([0-9]+\.[0-9]{2})', parent_text)
                                    if price_matches:
                                        # Usually the first or second price is the market price
                                        market_price = float(price_matches[0])
                                        print(f"[SEARCH] Found price ${market_price} for {name[:30]}")
                            except Exception as e:
                                pass
                        
                        results.append({
                            'productId': product_id,
                            'name': card_name_only[:150] if card_name_only else cleaned_name[:150],
                            'fullName': cleaned_name[:150],
                            'set': set_name,
                            'number': card_number,
                            'imageUrl': image_url,
                            'marketPrice': market_price,
                            'lowestPrice': lowest_price
                        })
                        
                        if len(results) >= 8:
                            break
                    
                    except Exception as e:
                        print(f"[SEARCH] Error parsing link: {e}")
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
                        print(f"[SEARCH] Filtered from {len(results)} to {len(filtered)} results")
                        results = filtered
            
            browser.close()
        
        print(f"[SEARCH] Returning {len(results)} products")
        
        return jsonify({'status': 'success', 'results': results})
        
    except Exception as e:
        print(f"[ERROR] Search failed: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500

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
