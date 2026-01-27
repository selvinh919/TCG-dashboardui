# 🚀 eBay Sell Inventory API Setup Guide

## What's New?

Your dashboard now supports **two eBay listing methods**:

1. **Old Method** - Trading API (XML-based, manual shipping)
2. **NEW: Inventory API** - Modern REST API with Business Policies ✨

The Inventory API allows you to use **eBay Standard Envelope** shipping for cards under $20, making it profitable to sell low-value cards!

---

## 📋 What You Need

To use the new Inventory API, you need **3 Business Policy IDs** from eBay:

### 1. Fulfillment Policy ID
- **What it is**: Your shipping rules (eBay Standard Envelope for cards!)
- **Where to get it**: https://www.ebay.com/sh/ovw/business
- Go to "Business Policies" → "Fulfillment Policies"
- Create a policy with **eBay Standard Envelope** enabled
- Copy the Policy ID (long string of numbers)

### 2. Payment Policy ID
- **What it is**: How buyers pay you
- **Where to get it**: Same page as above, "Payment Policies" tab
- Create or use existing payment policy
- Copy the Policy ID

### 3. Return Policy ID
- **What it is**: Your return rules (30 days, buyer pays, etc.)
- **Where to get it**: Same page, "Return Policies" tab
- Create or use existing return policy
- Copy the Policy ID

---

## ⚙️ Configuration Steps

### Step 1: Get Your Business Policy IDs

1. Go to: https://www.ebay.com/sh/ovw/business
2. Click "Business Policies"
3. For **Fulfillment Policy**:
   - Click "Create Policy"
   - Name: "Trading Cards - Standard Envelope"
   - Enable **eBay Standard Envelope** option
   - Set to free shipping or $0.99 shipping
   - Save and copy the Policy ID
4. Repeat for Payment and Return policies
5. Copy all 3 Policy IDs

### Step 2: Add IDs to Your Dashboard

1. Open your dashboard: http://localhost:5000
2. Click **⚙️ Settings** button
3. Scroll to **"📦 eBay Business Policies (Inventory API)"** section
4. Paste your 3 Policy IDs:
   - Fulfillment Policy ID
   - Payment Policy ID
   - Return Policy ID
5. Click **💾 Save Settings**

---

## 🎯 How to Use

### Listing a Card with Inventory API

1. Find a card in your inventory
2. Click **"📦 List eBay (Inv API)"** button (green button)
3. Set price, quantity, condition
4. Click **List on eBay**
5. Done! Card is live in seconds

### Features of Inventory API:

✅ Uses your Business Policies automatically
✅ eBay Standard Envelope shipping for cards <$20
✅ Clean SKU-based inventory management
✅ Better for bulk listing (hundreds of cards)
✅ More reliable than old Trading API

### eBay Price Comparison

- Click **🔍 Check** button in the "eBay Low" column
- Instantly see lowest eBay price for that card
- Compare with your Market price
- Find profitable arbitrage opportunities

---

## 🔧 API Credentials You Already Have

Your existing eBay credentials work with the Inventory API:

- ✅ App ID (Client ID): `YOUR_APP_ID` (from eBay Developer Portal)
- ✅ Cert ID (Client Secret): `YOUR_CERT_ID` (from eBay Developer Portal)
- ✅ Dev ID: `YOUR_DEV_ID` (from eBay Developer Portal)
- ✅ OAuth Token: Already configured in ebay_config.py

**You only need to add the 3 Business Policy IDs!**

---

## 🚨 Important Notes

### Sandbox vs Production

- Currently set to **sandbox** mode (testing)
- Listings will appear on eBay sandbox (not live site)
- When ready for production:
  1. Change `environment` in `ebay_config.py` to `'production'`
  2. Get production OAuth token from eBay
  3. Get production Business Policy IDs

### Shipping Strategy

The app auto-selects shipping based on price:

- **Cards under $20**: eBay Standard Envelope (tracked, $0.99-$1.32)
- **Cards over $20**: Calculated shipping (buyer pays)

This is why eBay Standard Envelope is so important - it makes low-value cards profitable!

### Multi-Platform Reselling

You now have a complete reselling hub:

- **TCGPlayer**: Manage inventory, scrape prices
- **eBay**: Quick list with Inventory API
- **Analytics**: Compare eBay vs TCGPlayer prices
- **Graded Cards**: Sell on eBay (TCGPlayer doesn't allow)

---

## 🎓 Workflow Example

### Scenario: You have a $5 card

1. **Check eBay price**: Click 🔍 Check → See eBay lowest is $8
2. **Decide to list**: Click "List eBay (Inv API)" 
3. **Set price**: $7.99 (competitive)
4. **Auto shipping**: eBay Standard Envelope selected (<$20)
5. **List**: Card goes live with free/cheap tracked shipping
6. **Profit**: $7.99 - $5 cost - $1.32 shipping - fees = ~$1-2 profit

Without eBay Standard Envelope, you'd lose money on shipping!

---

## 🐛 Troubleshooting

### Error: "Missing fulfillment_policy_id"

- You haven't added your Business Policy IDs yet
- Go to Settings → Add all 3 Policy IDs → Save

### Error: "Invalid credentials"

- Your OAuth token may have expired
- Get a new token from eBay Developer portal
- Update `user_token` in `ebay_config.py`

### Price check returns "No data"

- eBay Browse API didn't find listings
- Try searching manually on eBay to confirm
- Card might be too rare or misspelled

### Old "List eBay" button still shows

- Both buttons are available so you can compare
- Green button = New Inventory API (recommended)
- Blue button = Old Trading API (legacy)

---

## 📊 Analytics Dashboard (Coming Soon)

Your setup supports these future features:

- [ ] eBay vs TCGPlayer price comparison charts
- [ ] Profit margin calculator
- [ ] Best arbitrage opportunities highlighter
- [ ] Bulk listing queue
- [ ] Cross-platform inventory sync
- [ ] Auto-repricing based on eBay competition

---

## 🎉 You're Ready!

Once you add your 3 Business Policy IDs, you can:

- List hundreds of cards in minutes
- Use eBay Standard Envelope for cheap shipping
- Compare prices across TCGPlayer and eBay
- Build a real multi-platform reselling business

### Next Steps:

1. Get your Business Policy IDs from eBay
2. Add them in Settings
3. Test listing a card with Inventory API
4. Check the eBay price comparison feature
5. Scale up your operation!

---

## 🆘 Need Help?

- eBay Developer Portal: https://developer.ebay.com
- Business Policies: https://www.ebay.com/sh/ovw/business
- eBay Standard Envelope Info: https://www.ebay.com/help/selling/shipping-items/setting-shipping-options/ebay-standard-envelope

Happy selling! 🚀
