import requests
import time

# Pokemon TCG API Configuration
POKEMON_API_KEY = "6ba2f0c2-5c79-4ac5-a8c7-1578120779f8"
BASE_URL = "https://api.pokemontcg.io/v2"

# Global counter for API calls
_api_call_count = 0
_last_api_call_time = 0

def enrich_card(name, card_number=None, max_calls=None, delay=0):
    """
    Fetch card IMAGE and TCGPlayer Product ID from Pokemon TCG API.
    (Prices come from TCGPlayer scraper, not API)
    
    Returns:
    {
      set_name: str or None,
      image: str (URL) or None,
      rarity: str or None,
      tcgplayer_id: int or None  (for Edit on TCG button)
    }
    or None if not found/error
    
    Args:
        name: Card name to search for
        card_number: Optional card number for more precise search
        max_calls: Maximum API calls allowed (None for unlimited)
        delay: Seconds to wait between API calls
    """
    global _api_call_count, _last_api_call_time
    
    # Check if we've hit the maximum call limit
    if max_calls is not None and _api_call_count >= max_calls:
        print(f"[SKIPPED] {name} - API call limit reached ({_api_call_count}/{max_calls})")
        return None
    
    # Rate limiting: wait if needed
    if delay > 0 and _last_api_call_time > 0:
        elapsed = time.time() - _last_api_call_time
        if elapsed < delay:
            wait_time = delay - elapsed
            time.sleep(wait_time)
    
    # Build search query
    query_parts = [f'name:"{name}"']
    if card_number:
        # Extract just the number part (e.g., "25" from "25/102")
        num_part = card_number.split('/')[0]
        query_parts.append(f'number:{num_part}')
    
    query = ' '.join(query_parts)
    
    params = {
        'q': query,
        'pageSize': 1  # Only need the best match
    }
    
    headers = {
        'X-Api-Key': POKEMON_API_KEY
    }
    
    try:
        # Increment API call counter and update timestamp
        _api_call_count += 1
        _last_api_call_time = time.time()
        
        print(f"[API Call {_api_call_count}] Fetching: {name}")
        
        r = requests.get(
            f"{BASE_URL}/cards",
            params=params,
            headers=headers,
            timeout=5
        )
        
        if r.status_code == 429:  # Rate limit error
            print(f"⚠️  RATE LIMIT for {name} - Consider increasing delay")
            return None
        
        if r.status_code != 200:
            print(f"❌ API Error for {name}: {r.status_code} - {r.text}")
            return None
        
        data = r.json()
        if not data.get('data'):
            print(f"⚠️  No match found for {name}")
            return None
        
        card = data['data'][0]
        
        # Get set name
        set_data = card.get('set', {})
        set_name = set_data.get('name')
        
        # Get image URL
        images = card.get('images', {})
        image_url = images.get('small')  # Use small image for dashboard
        
        # Get rarity
        rarity = card.get('rarity')
        
        # Get TCGPlayer Product ID (for Edit on TCG button)
        tcgplayer_data = card.get('tcgplayer', {})
        tcgplayer_id = tcgplayer_data.get('productId')
        
        result = {
            'set_name': set_name,
            'image': image_url,
            'rarity': rarity,
            'tcgplayer_id': tcgplayer_id
        }
        
        print(f"✅ Found: {card.get('name')} ({set_name}) [TCG ID: {tcgplayer_id}]")
        return result
        
    except requests.RequestException as e:
        print(f"❌ Request failed for {name}: {e}")
        return None
    except Exception as e:
        print(f"❌ Unexpected error for {name}: {e}")
        return None

def get_api_call_count():
    """Return the current API call count"""
    return _api_call_count

def reset_api_call_count():
    """Reset the API call counter"""
    global _api_call_count
    _api_call_count = 0
