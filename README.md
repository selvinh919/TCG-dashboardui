# TCG Inventory Management Bot

A comprehensive inventory management system for trading card game sellers on TCGPlayer. Features automated email scanning for sales notifications, inventory tracking, market price monitoring, and eBay listing integration.

## Features

- 📊 **Inventory Dashboard** - Track all your cards with real-time market prices
- 📧 **Email Sales Scanner** - Automatically detect TCGPlayer sales from your email
- 💰 **Profit Tracking** - Monitor costs, sales prices, and profit margins
- 🔍 **Smart Search** - Search TCGPlayer for cards with automated price fetching
- 📦 **eBay Integration** - Quick listing tools for eBay sales
- 🎯 **Multi-line Order Support** - Handles orders with multiple cards automatically

## Setup

### Prerequisites

- Python 3.8 or higher
- Gmail account with App Password enabled (for email scanning)
- TCGPlayer seller account (optional, for inventory sync)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/tcg_inventory_bot.git
   cd tcg_inventory_bot
   ```

2. **Create virtual environment**
   ```bash
   python -m venv .venv
   ```

3. **Activate virtual environment**
   - Windows:
     ```bash
     .venv\Scripts\activate
     ```
   - Mac/Linux:
     ```bash
     source .venv/bin/activate
     ```

4. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

5. **Configure settings**
   - Copy `settings.example.json` to `settings.json`
   - Update with your credentials:
     ```json
     {
       "email_address": "your_email@gmail.com",
       "email_password": "your_gmail_app_password",
       "imap_server": "imap.gmail.com",
       "tcgplayer_username": "your_tcgplayer_username",
       "default_markup": 15,
       "auto_scan": "interval"
     }
     ```

### Gmail App Password Setup

For email scanning to work, you need a Gmail App Password:

1. Go to your [Google Account](https://myaccount.google.com/)
2. Select **Security** > **2-Step Verification** (enable if not already)
3. At the bottom, select **App passwords**
4. Select **Mail** and your device
5. Copy the 16-character password and use it in `settings.json`

## Usage

### Starting the Server

```bash
python server.py
```

Then open your browser to: `http://localhost:5000`

### Email Scanning

1. Go to the **Settings** tab
2. Enter your email credentials
3. Click **Scan for Sales** to check for new TCGPlayer sale notifications
4. Confirm sales to:
   - Mark items as sold in inventory
   - Track profit/loss
   - Cache order IDs to prevent duplicates

### Adding Inventory

1. Use the search bar to find cards on TCGPlayer
2. Click **Add to Inventory**
3. Enter your cost and quantity
4. Item is automatically added with current market price

### Viewing Sales

- Go to the **Sold** tab to see all confirmed sales
- View profit/loss per item
- Export data for accounting

## Project Structure

```
tcg_inventory_bot/
├── server.py                 # Flask server & API endpoints
├── run.py                    # Main scraper script
├── scraper.py                # TCGPlayer scraping logic
├── email_scraper.py          # Email scanning for sales
├── analyzer.py               # Price analysis tools
├── notifier.py               # Notification system
├── inventory_dashboard.html  # Main dashboard UI
├── settings.json             # User configuration (gitignored)
├── state.json                # Inventory data (gitignored)
└── requirements.txt          # Python dependencies
```

## Configuration Files

- `settings.json` - Your credentials and preferences (create from `settings.example.json`)
- `state.json` - Auto-generated inventory data
- `confirmed_sales.json` - Auto-generated cache of confirmed orders
- `pending_sales.json` - Auto-generated pending sales from email scans

⚠️ **Never commit files with actual credentials to GitHub!**

## Features in Detail

### Email Sales Detection

The bot scans your Gmail for TCGPlayer sale notifications with this format:
```
Your TCGplayer.com items of [Product Name] have sold!
Order: [ORDER-ID]
Order Total: $XX.XX
1
Product Name/Condition
```

Multi-product orders are automatically grouped by Order ID.

### Profit Tracking

- Enter your cost per item when confirming sales
- Edit sold prices if needed (auto-calculated from order total / quantity)
- Real-time profit calculation shows green for profit, red for loss
- Sold items saved to localStorage for persistent tracking

### Smart Search

Search by:
- Card name: "Charizard"
- Set + number: "Charizard 151/165"
- Partial matches with automatic fallbacks

## Troubleshooting

### Email Connection Fails
- Verify Gmail App Password is correct (not your regular password)
- Check that 2-Step Verification is enabled
- Make sure IMAP is enabled in Gmail settings

### No Products Found
- Check that `playwright` browsers are installed: `playwright install chromium`
- Verify TCGPlayer website is accessible

### Port Already in Use
```bash
# Windows
Stop-Process -Id (Get-NetTCPConnection -LocalPort 5000).OwningProcess -Force

# Mac/Linux
lsof -ti:5000 | xargs kill -9
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Built with Flask, Playwright, and BeautifulSoup
- TCGPlayer for market data
- Gmail API for email scanning

## Support

For issues, questions, or suggestions, please open an issue on GitHub.

---

**⚠️ Security Note:** This tool requires email access. Always use App Passwords, never share your credentials, and keep `settings.json` private.
