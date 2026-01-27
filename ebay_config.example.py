"""
eBay API Configuration Template
Get your credentials from: https://developer.ebay.com/my/keys
Get Business Policy IDs from: https://www.ebay.com/sh/ovw/business
"""

# Your eBay API Credentials
EBAY_CONFIG = {
    'app_id': 'YOUR_EBAY_APP_ID_CLIENT_ID',  # Client ID from eBay Developer
    'cert_id': 'YOUR_EBAY_CERT_ID_CLIENT_SECRET',  # Client Secret from eBay Developer
    'dev_id': 'YOUR_EBAY_DEV_ID',
    'user_token': 'YOUR_EBAY_OAUTH_TOKEN',
    
    # Environment: 'production' or 'sandbox'
    'environment': 'sandbox',
    
    # eBay Business Policies (get from https://www.ebay.com/sh/ovw/business)
    # These enable eBay Standard Envelope for cards!
    'fulfillment_policy_id': 'YOUR_FULFILLMENT_POLICY_ID',
    'payment_policy_id': 'YOUR_PAYMENT_POLICY_ID',
    'return_policy_id': 'YOUR_RETURN_POLICY_ID',
    
    # Marketplace
    'marketplace_id': 'EBAY_US',
    
    # Seller information
    'postal_code': '10001',
    
    # Default listing settings
    'default_shipping': {
        'price': 0.00,
        'service': 'eBay Standard Envelope'
    }
}
