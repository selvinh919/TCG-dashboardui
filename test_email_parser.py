"""
Test the email parser with the sample TCGPlayer email
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from email_scraper import TCGEmailScraper

# Sample email data from the user
sample_subject = "Your TCGplayer.com items of Mew ex - 151/165 have sold!"
sample_body = """
Selvin,

Payment for this order has been received and is being held for you until this order is confirmed as delivered.

Order: 65A71D89-0F1F1F-5C620
Order Total: $5.99

ORDER DETAILS
See all >
1 Mew ex - 151/165/Near Mint Holofoil
Remember to ship this order no later than 48 hours after the order date of 1/26/2026.

Confirm Shipment

Thanks,
Team TCGplayer
"""
sample_date = "Sun, 26 Jan 2026 02:19:00 +0000"

# Create scraper instance
scraper = TCGEmailScraper("test@example.com", "password")

# Test the parser
print("=" * 60)
print("Testing TCGPlayer Email Parser")
print("=" * 60)
print()
print(f"Subject: {sample_subject}")
print()
print("Body preview:")
print(sample_body[:200] + "...")
print()
print("=" * 60)
print("PARSING RESULTS:")
print("=" * 60)
print()

result = scraper._extract_sale_info(sample_subject, sample_body, sample_date)

if result:
    print(f"✅ Successfully parsed email!")
    print()
    print(f"Date: {result['date']}")
    print(f"Products found: {len(result['products'])}")
    print()
    
    for i, product in enumerate(result['products'], 1):
        print(f"Product {i}:")
        print(f"  Name: {product['name']}")
        print(f"  Quantity: {product['quantity']}")
        print(f"  Price: ${product['price']:.2f}")
        print(f"  Card Number: {product.get('card_number', 'N/A')}")
        print(f"  Condition: {product.get('condition', 'N/A')}")
        print(f"  Order ID: {product.get('order_id', 'N/A')}")
        print(f"  Order Date: {product.get('order_date', 'N/A')}")
        print()
else:
    print("❌ Failed to parse email - no products found")
    print()
    print("This means the regex patterns didn't match the email format.")
    print("Please check the email_scraper.py file and adjust the patterns.")

print("=" * 60)
