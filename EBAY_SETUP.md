# eBay Integration Setup Guide

## Step 1: Get eBay API Credentials

1. Go to https://developer.ebay.com/
2. Sign in with your eBay account
3. Navigate to "My Account" → "Application Keys"
4. Create a new application or use existing one
5. Copy these credentials:
   - **App ID (Client ID)**
   - **Cert ID (Client Secret)**
   - **Dev ID**

## Step 2: Get OAuth User Token

1. Go to https://developer.ebay.com/my/auth/?env=sandbox&index=0
2. Sign in to get your OAuth token for sandbox testing
3. For production, use: https://developer.ebay.com/my/auth/?env=production&index=0
4. Copy the **User Token**

## Step 3: Configure ebay_config.py

Open `ebay_config.py` and fill in your credentials:

```python
EBAY_CONFIG = {
    'app_id': 'YourAppID-here',
    'cert_id': 'YourCertID-here', 
    'dev_id': 'YourDevID-here',
    'user_token': 'YourUserToken-here',
    'environment': 'sandbox',  # Use 'sandbox' for testing
}
```

## Step 4: Update PayPal Email

In `server.py`, find the eBay listing section and update:
```python
'PayPalEmailAddress': 'your_paypal_email@example.com',
```

## Step 5: Update Your Postal Code

In `server.py`, update your zip code:
```python
'PostalCode': '10001',  # Your actual zip code
```

## Step 6: Testing with Sandbox

- Start with `environment: 'sandbox'` to test without creating real listings
- Sandbox listings appear at: https://sandbox.ebay.com
- Real eBay account won't be affected

## Step 7: Go Live

When ready for production:
1. Change `environment` to `'production'` in `ebay_config.py`
2. Get production OAuth token from step 2
3. Restart the server

## Features

- **Quick List Button**: Click "📦 List eBay" on any inventory item
- **Pre-filled Data**: Market price, images automatically populated
- **Custom Settings**: Set quantity, condition, shipping per listing
- **Instant Listing**: Creates eBay listing in seconds
- **Auto-open**: Opens new listing in browser after creation

## Troubleshooting

**"eBay config not found"**
- Make sure `ebay_config.py` exists and has valid credentials

**"Authentication error"**
- Your OAuth token expired (refresh every 2 hours for sandbox)
- Get a new token from developer portal

**"Category error"**
- Default category is CCG Individual Cards (183454)
- Adjust in server.py if needed

**"PayPal error"**
- Update PayPalEmailAddress in server.py
- Must match your eBay-linked PayPal

## Rate Limits

- Sandbox: Unlimited for testing
- Production: Based on your eBay seller limits
- Check: https://developer.ebay.com/api-docs/static/rate-limiting.html
