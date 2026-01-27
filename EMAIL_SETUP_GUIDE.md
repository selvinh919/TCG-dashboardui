# 📧 Email Auto-Detection Setup Guide

## Overview
Your TCG Inventory Dashboard can now automatically detect sales from TCGPlayer email notifications and prompt you to mark them as sold!

## Features
- ✅ **Automatic Email Scanning** - Monitors your inbox for TCGPlayer sale notifications
- 🔔 **Sticky Notifications** - Sale alerts appear at bottom of screen and won't dismiss until you confirm
- 🎯 **Smart Matching** - Attempts to match email sales with your inventory
- 📊 **Profit Tracking** - Automatically calculates profit when you confirm sales
- ⏰ **Auto-Scan Options** - Scan on startup or every 5 minutes

---

## Setup Instructions

### Step 1: Get Your Email Password

#### For Gmail Users (Recommended):
1. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
2. Sign in if prompted
3. Under "Select app", choose **Mail**
4. Under "Select device", choose **Other** and type "TCG Dashboard"
5. Click **Generate**
6. **Copy the 16-character app password** (spaces don't matter)
7. Keep this password safe - you'll enter it in settings

#### For Outlook/Office 365:
- Use your regular email password
- Make sure IMAP is enabled in Outlook settings

#### For Yahoo Mail:
1. Go to Yahoo Account Security
2. Enable "Allow apps that use less secure sign in"
3. OR generate an App Password similar to Gmail

---

### Step 2: Configure Dashboard Settings

1. Open your dashboard at `http://localhost:5000`
2. Click **⚙️ Settings** tab
3. Scroll to **📧 Email Integration** section
4. Fill in:
   - **Email Address**: Your email where TCGPlayer sends sale notifications
   - **Email Password**: Your app password (or regular password)
   - **IMAP Server**: Select your email provider (Gmail, Outlook, Yahoo, etc.)
   - **Auto-scan Email**: Choose when to check for new sales:
     - `Manual Only` - Click "📧 Scan Emails" button manually
     - `On Dashboard Load` - Auto-scan when you open the dashboard
     - `Every 5 Minutes` - Continuous background scanning
5. Click **💾 Save Settings**
6. Click **🔍 Test Email Connection** to verify it works

---

### Step 3: Provide Sample Email

**IMPORTANT:** For the scraper to work accurately, I need to see a sample TCGPlayer sale notification email!

**Please provide:**
1. **Forward** a TCGPlayer sale email to yourself
2. **Copy/paste the entire email content** (text and/or HTML)
3. **Share it with me** so I can customize the email parser

**What I'm looking for:**
- Subject line format (e.g., "Your product sold on TCGPlayer")
- Product name location in email
- Quantity information
- Price information
- Set/card number details
- Order ID or sale reference

---

### Step 4: Scan for Sales

Once configured:
1. Click **📧 Scan Emails** button in the top bar
2. Or wait for auto-scan (if enabled)
3. New sales will appear in a **sticky banner at the bottom** of the screen

---

## How It Works

### When a Sale is Detected:

1. **Banner Appears** 🔔
   - Green banner slides up from bottom
   - Shows product name, quantity, price, and date
   - Won't disappear until you take action

2. **Confirm Sale** ✅
   - Attempts to match with inventory by name
   - If found: Automatically marks as sold and moves to Sold Items page
   - If not found: Asks if you want to record it anyway
   - Calculates profit based on your cost data

3. **Dismiss** ✖
   - Removes notification without taking action
   - Use for duplicate notifications or false positives

4. **Dismiss All**
   - Clear all pending sale notifications at once

---

## Email Parser Customization

Once you provide a sample email, I will customize the parser to extract:

- ✅ Product name (e.g., "Charizard ex - 199/165")
- ✅ Set name (e.g., "Scarlet & Violet 151")
- ✅ Card number (e.g., "199/165")
- ✅ Quantity sold
- ✅ Sale price
- ✅ Order date/time
- ✅ Platform (TCGPlayer, eBay, etc.)

---

## Troubleshooting

### "Failed to connect to email server"
- Check email address and password are correct
- For Gmail: Make sure you're using App Password, not your regular password
- For Yahoo: Enable "less secure apps" or use App Password
- Check IMAP server is correct for your provider

### "No new sales found"
- Make sure you have unread TCGPlayer sale notification emails
- Try changing "unread only" to include all recent emails
- Check that TCGPlayer sends to the email you configured

### Sales not matching inventory
- Product names in emails might be formatted differently
- You can still confirm manually - it will just prompt you
- Provide sample emails so I can improve matching

---

## Security Notes

- ✅ Email passwords are stored in `settings.json` on your local machine only
- ✅ No data is sent to external servers
- ✅ App Passwords are more secure than regular passwords
- ✅ You can revoke App Passwords anytime from your email provider
- ⚠️ Never share your `settings.json` file or commit it to public repositories

---

## Next Steps

**📧 Please provide a sample TCGPlayer sale notification email so I can:**
1. Parse the exact format of your notifications
2. Extract product details accurately
3. Match sales to your inventory correctly
4. Handle any special formatting or edge cases

**Send me:**
- The full email text (copy/paste)
- Or a screenshot of the email
- Multiple samples if formats vary (single card vs bulk orders)

Once I have this, I'll customize the email parser to work perfectly with your notifications! 🚀
