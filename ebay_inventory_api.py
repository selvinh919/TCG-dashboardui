"""
eBay Sell Inventory API Integration
Modern REST API for managing inventory and creating listings with Business Policies
"""

import requests
import json
from typing import Dict, Any, Optional
from ebay_config import EBAY_CONFIG


class eBayInventoryAPI:
    """eBay Sell Inventory API client"""
    
    def __init__(self):
        self.environment = EBAY_CONFIG['environment']
        self.token = EBAY_CONFIG['user_token']
        
        # API Base URLs
        if self.environment == 'sandbox':
            self.base_url = 'https://api.sandbox.ebay.com'
        else:
            self.base_url = 'https://api.ebay.com'
        
        # Headers
        self.headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Content-Language': 'en-US'
        }

    def _merchant_location_key(self) -> str:
        return EBAY_CONFIG.get('merchant_location_key', 'default_location')

    def ensure_merchant_location(self) -> Dict[str, Any]:
        """Create/update the inventory location used by offers.

        This is required for publish and is where the ship-from country (Item.Country)
        is derived from.
        """
        key = self._merchant_location_key()
        url = f'{self.base_url}/sell/inventory/v1/location/{key}'

        payload = {
            'name': 'Default ship-from location',
            'merchantLocationStatus': 'ENABLED',
            'locationTypes': ['WAREHOUSE'],
            'location': {
                'address': {
                    'addressLine1': EBAY_CONFIG.get('address_line1', '123 Main St'),
                    'city': EBAY_CONFIG.get('city', 'New York'),
                    'stateOrProvince': EBAY_CONFIG.get('state_or_province', 'NY'),
                    'postalCode': EBAY_CONFIG.get('postal_code', '10001'),
                    'country': EBAY_CONFIG.get('country', 'US')
                }
            }
        }

        response = requests.put(url, headers=self.headers, json=payload)
        if response.status_code in [200, 201, 204]:
            return {'status': 'success', 'merchant_location_key': key}

        error = response.json() if response.text else {'error': response.text}
        print(f"[EBAY ERROR] Ensure merchant location failed: {error}")
        return {'status': 'error', 'error': error}

    @staticmethod
    def _is_item_country_error(error: Any) -> bool:
        if not isinstance(error, dict):
            return False
        for err in error.get('errors', []) or []:
            msg = (err.get('message') or '').lower()
            if 'item.country' in msg:
                return True
            for param in err.get('parameters', []) or []:
                if (param.get('value') or '').strip() == 'Item.Country':
                    return True
        return False

    @staticmethod
    def _extract_offer_id_from_error(error: Any) -> Optional[str]:
        if not isinstance(error, dict):
            return None
        for err in error.get('errors', []) or []:
            for param in err.get('parameters', []) or []:
                if param.get('name') == 'offerId' and param.get('value'):
                    return param.get('value')
        return None
    
    def create_inventory_item(self, sku: str, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Step 1: Create or replace inventory item
        
        Args:
            sku: Unique identifier for the item (e.g., "charizard-4-base")
            product_data: Card data with name, image, condition, quantity
        
        Returns:
            Response dict with status
        """
        url = f'{self.base_url}/sell/inventory/v1/inventory_item/{sku}'
        
        # Map condition to eBay format
        condition_mapping = {
            'Near mint or better': 'LIKE_NEW',
            'Lightly played': 'VERY_GOOD',
            'Moderately played': 'GOOD',
            'Heavily played': 'ACCEPTABLE'
        }
        
        ebay_condition = condition_mapping.get(
            product_data.get('condition', 'Near mint or better'),
            'LIKE_NEW'
        )
        
        # Build inventory item payload
        payload = {
            'availability': {
                'shipToLocationAvailability': {
                    'quantity': product_data.get('quantity', 1)
                }
            },
            'condition': ebay_condition,
            'product': {
                'title': product_data['title'][:80],  # eBay max 80 chars
                'description': product_data.get('description', f"Trading Card - {product_data['title']}"),
                'imageUrls': [product_data['image']] if product_data.get('image') else [],
                'aspects': {
                    'Game': [product_data.get('game', 'Pokémon')],
                    'Card Condition': [product_data.get('condition', 'Near Mint or Better')],
                    'Language': ['English'],
                    'Card Type': ['Pokémon' if 'pokemon' in product_data.get('game', '').lower() else 'Single']
                }
            },
            'packageWeightAndSize': {
                'dimensions': {
                    'height': 5,
                    'length': 7,
                    'width': 0.1,
                    'unit': 'INCH'
                },
                'weight': {
                    'value': 0.5,
                    'unit': 'OUNCE'
                }
            }
        }
        
        response = requests.put(url, headers=self.headers, json=payload)
        
        if response.status_code in [200, 201, 204]:
            print(f"[EBAY] Created inventory item: {sku}")
            return {'status': 'success', 'sku': sku}
        else:
            error = response.json() if response.text else {'error': response.text}
            print(f"[EBAY ERROR] Create inventory failed: {error}")
            return {'status': 'error', 'error': error}
    
    def get_offers_by_sku(self, sku: str) -> Dict[str, Any]:
        """
        Get existing offers for a SKU
        
        Args:
            sku: SKU to search for
        
        Returns:
            Response with offers list
        """
        url = f'{self.base_url}/sell/inventory/v1/offer'
        params = {'sku': sku}
        
        response = requests.get(url, headers=self.headers, params=params)
        
        if response.status_code == 200:
            data = response.json()
            offers = data.get('offers', [])
            return {'status': 'success', 'offers': offers}
        else:
            error = response.json() if response.text else {'error': response.text}
            return {'status': 'error', 'error': error}
    
    def create_offer(self, sku: str, price: float, quantity: int = 1) -> Dict[str, Any]:
        """
        Step 2: Create an offer for the inventory item
        
        Args:
            sku: SKU of the inventory item
            price: Listing price
            quantity: Available quantity
        
        Returns:
            Response with offer_id
        """
        url = f'{self.base_url}/sell/inventory/v1/offer'
        
        # Validate business policy IDs
        if not EBAY_CONFIG.get('fulfillment_policy_id'):
            return {'status': 'error', 'error': 'Missing fulfillment_policy_id in ebay_config.py'}
        if not EBAY_CONFIG.get('payment_policy_id'):
            return {'status': 'error', 'error': 'Missing payment_policy_id in ebay_config.py'}
        if not EBAY_CONFIG.get('return_policy_id'):
            return {'status': 'error', 'error': 'Missing return_policy_id in ebay_config.py'}
        
        # Ensure inventory location exists (required for publish)
        loc_result = self.ensure_merchant_location()
        if loc_result['status'] == 'error':
            return loc_result

        # Build offer payload
        payload = {
            'sku': sku,
            'marketplaceId': EBAY_CONFIG.get('marketplace_id', 'EBAY_US'),
            'format': 'FIXED_PRICE',
            'listingDuration': 'GTC',  # Good Till Cancelled
            'availableQuantity': quantity,
            'categoryId': '183454',  # CCG Individual Cards
            'merchantLocationKey': self._merchant_location_key(),
            'listingPolicies': {
                'fulfillmentPolicyId': EBAY_CONFIG['fulfillment_policy_id'],
                'paymentPolicyId': EBAY_CONFIG['payment_policy_id'],
                'returnPolicyId': EBAY_CONFIG['return_policy_id']
            },
            'pricingSummary': {
                'price': {
                    'value': str(max(0.99, price)),  # Min $0.99
                    'currency': 'USD'
                }
            },
        }
        
        response = requests.post(url, headers=self.headers, json=payload)
        
        if response.status_code in [200, 201]:
            data = response.json()
            offer_id = data.get('offerId')
            print(f"[EBAY] Created offer: {offer_id}")
            return {'status': 'success', 'offer_id': offer_id}
        else:
            error = response.json() if response.text else {'error': response.text}
            
            # Only treat errorId=25002 as a duplicate-offer when an offerId is provided.
            existing_offer_id = self._extract_offer_id_from_error(error)
            if existing_offer_id:
                print(f"[EBAY] Found existing offer: {existing_offer_id}, updating...")
                update_result = self.update_offer(existing_offer_id, sku, price, quantity)
                if update_result['status'] == 'success':
                    return {'status': 'success', 'offer_id': existing_offer_id, 'existing': True}
                return update_result
            
            print(f"[EBAY ERROR] Create offer failed: {error}")
            return {'status': 'error', 'error': error}
    
    def update_offer(self, offer_id: str, sku: str, price: float, quantity: int = 1) -> Dict[str, Any]:
        """
        Update an existing offer with new data (including location)
        
        Args:
            offer_id: Existing offer ID to update
            sku: SKU of the inventory item
            price: Listing price
            quantity: Available quantity
        
        Returns:
            Response with status
        """
        url = f'{self.base_url}/sell/inventory/v1/offer/{offer_id}'
        
        loc_result = self.ensure_merchant_location()
        if loc_result['status'] == 'error':
            return loc_result

        # Build offer payload (same as create)
        payload = {
            'sku': sku,
            'marketplaceId': EBAY_CONFIG.get('marketplace_id', 'EBAY_US'),
            'format': 'FIXED_PRICE',
            'listingDuration': 'GTC',
            'availableQuantity': quantity,
            'categoryId': '183454',
            'merchantLocationKey': self._merchant_location_key(),
            'listingPolicies': {
                'fulfillmentPolicyId': EBAY_CONFIG['fulfillment_policy_id'],
                'paymentPolicyId': EBAY_CONFIG['payment_policy_id'],
                'returnPolicyId': EBAY_CONFIG['return_policy_id']
            },
            'pricingSummary': {
                'price': {
                    'value': str(max(0.99, price)),
                    'currency': 'USD'
                }
            },
        }
        
        response = requests.put(url, headers=self.headers, json=payload)
        
        if response.status_code in [200, 204]:
            print(f"[EBAY] Updated offer: {offer_id}")
            return {'status': 'success', 'offer_id': offer_id}
        else:
            error = response.json() if response.text else {'error': response.text}
            print(f"[EBAY ERROR] Update offer failed: {error}")
            return {'status': 'error', 'error': error}
    
    def publish_offer(self, offer_id: str, *, sku: Optional[str] = None, price: Optional[float] = None, quantity: Optional[int] = None) -> Dict[str, Any]:
        """
        Step 3: Publish the offer live on eBay
        
        Args:
            offer_id: The offer ID from create_offer
        
        Returns:
            Response with listing_id
        """
        url = f'{self.base_url}/sell/inventory/v1/offer/{offer_id}/publish'
        
        response = requests.post(url, headers=self.headers)
        
        if response.status_code in [200, 201]:
            data = response.json()
            listing_id = data.get('listingId')
            
            # Build eBay URL
            if self.environment == 'sandbox':
                listing_url = f"https://sandbox.ebay.com/itm/{listing_id}"
            else:
                listing_url = f"https://www.ebay.com/itm/{listing_id}"
            
            print(f"[EBAY] Published listing: {listing_id}")
            return {
                'status': 'success',
                'listing_id': listing_id,
                'listing_url': listing_url
            }
        else:
            error = response.json() if response.text else {'error': response.text}
            print(f"[EBAY ERROR] Publish failed: {error}")

            # Auto-recover the common sandbox failure where the offer references a missing/invalid
            # merchant location (shows up as Item.Country missing).
            if self._is_item_country_error(error) and sku and price is not None and quantity is not None:
                loc_result = self.ensure_merchant_location()
                if loc_result['status'] == 'success':
                    update_result = self.update_offer(offer_id, sku, price, quantity)
                    if update_result['status'] == 'success':
                        retry = requests.post(url, headers=self.headers)
                        if retry.status_code in [200, 201]:
                            data = retry.json()
                            listing_id = data.get('listingId')
                            if self.environment == 'sandbox':
                                listing_url = f"https://sandbox.ebay.com/itm/{listing_id}"
                            else:
                                listing_url = f"https://www.ebay.com/itm/{listing_id}"
                            print(f"[EBAY] Published listing (after repair): {listing_id}")
                            return {
                                'status': 'success',
                                'listing_id': listing_id,
                                'listing_url': listing_url
                            }
                        retry_error = retry.json() if retry.text else {'error': retry.text}
                        print(f"[EBAY ERROR] Publish retry failed: {retry_error}")
                        return {'status': 'error', 'error': retry_error}

                return {'status': 'error', 'error': error}

            return {'status': 'error', 'error': error}
    
    def list_card(self, card_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Complete listing flow: create inventory → create offer → publish
        
        Args:
            card_data: Dict with name, set, number, condition, price, quantity, image
        
        Returns:
            Response with listing URL
        """
        # Generate SKU
        name = card_data.get('name', 'card')
        set_name = card_data.get('set', 'set')
        number = card_data.get('number', '1')
        
        # Clean for SKU (alphanumeric + hyphens)
        sku = f"{name}-{number}-{set_name}".lower()
        sku = ''.join(c if c.isalnum() or c == '-' else '-' for c in sku)
        sku = sku[:50]  # Max 50 chars
        
        # Build title
        title = f"{name} {number}/{set_name}"
        
        # Step 1: Create inventory item
        product_data = {
            'title': title,
            'description': f"{title} - {card_data.get('condition', 'Near Mint')} condition. Fast shipping!",
            'image': card_data.get('image', ''),
            'condition': card_data.get('condition', 'Near mint or better'),
            'quantity': card_data.get('quantity', 1),
            'game': card_data.get('game', 'Pokémon')
        }
        
        result = self.create_inventory_item(sku, product_data)
        if result['status'] == 'error':
            return result
        
        # Step 2: Create offer
        price = card_data.get('price', 1.00)
        quantity = card_data.get('quantity', 1)
        
        result = self.create_offer(sku, price, quantity)
        if result['status'] == 'error':
            return result
        
        offer_id = result['offer_id']
        
        # Step 3: Publish offer
        result = self.publish_offer(offer_id, sku=sku, price=price, quantity=quantity)
        if result['status'] == 'error':
            return result
        
        return {
            'status': 'success',
            'sku': sku,
            'offer_id': offer_id,
            'listing_id': result['listing_id'],
            'listing_url': result['listing_url'],
            'message': f"Listed on eBay! {result['listing_url']}"
        }
    
    def get_ebay_lowest_price(self, search_query: str) -> Optional[float]:
        """
        Get lowest Ask price on eBay for comparison analytics
        
        Args:
            search_query: Card name to search
        
        Returns:
            Lowest price found, or None
        """
        # Use eBay Browse API to search completed listings
        url = f'{self.base_url}/buy/browse/v1/item_summary/search'
        
        params = {
            'q': search_query,
            'category_ids': '183454',  # CCG cards
            'limit': 10,
            'sort': 'price'  # Lowest first
        }
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            if response.status_code == 200:
                data = response.json()
                items = data.get('itemSummaries', [])
                if items:
                    lowest = float(items[0]['price']['value'])
                    print(f"[EBAY] Lowest price for '{search_query}': ${lowest}")
                    return lowest
            return None
        except Exception as e:
            print(f"[EBAY ERROR] Price check failed: {e}")
            return None
