"""
Enhanced Email scraper to extract sold order information from TCGplayer
"""
import imaplib
import email
from email.header import decode_header
from email import policy
import re
import json
from datetime import datetime
import os
from bs4 import BeautifulSoup

class EmailScraper:
    def __init__(self, email_address, password, imap_server='imap.gmail.com'):
        """Initialize email scraper with credentials"""
        self.email_address = email_address
        self.password = password
        self.imap_server = imap_server
        self.mail = None
        
    def connect(self):
        """Connect to email server"""
        try:
            self.mail = imaplib.IMAP4_SSL(self.imap_server)
            self.mail.login(self.email_address, self.password)
            print(f"[INFO] Successfully connected to {self.email_address}")
            return True
        except Exception as e:
            print(f"[ERROR] Failed to connect: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from email server"""
        if self.mail:
            try:
                self.mail.close()
                self.mail.logout()
            except:
                pass
    
    def decode_email_subject(self, subject):
        """Decode email subject line"""
        if subject is None:
            return ""
        decoded = decode_header(subject)
        subject_parts = []
        for part, encoding in decoded:
            if isinstance(part, bytes):
                subject_parts.append(part.decode(encoding or 'utf-8', errors='ignore'))
            else:
                subject_parts.append(part)
        return ''.join(subject_parts)
    
    def get_email_body(self, msg):
        """Extract email body text from HTML"""
        body = ""
        html_body = ""
        
        # Handle both old and new email parsing
        if hasattr(msg, 'walk'):
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))
                
                try:
                    if content_type == "text/html" and "attachment" not in content_disposition:
                        if hasattr(part, 'get_content'):
                            html_body = part.get_content()
                        else:
                            html_body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        break
                    elif content_type == "text/plain" and "attachment" not in content_disposition and not html_body:
                        if hasattr(part, 'get_content'):
                            body = part.get_content()
                        else:
                            body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                except:
                    pass
        
        # If we got HTML, convert it to text
        if html_body:
            try:
                soup = BeautifulSoup(html_body, 'html.parser')
                body = soup.get_text()
            except:
                body = html_body
        
        return body
    
    def parse_tcgplayer_order(self, subject, body, date):
        """
        Parse TCGPlayer order confirmation email
        
        Email format example:
        Subject: Your TCGplayer.com items of Dragonite (52 Delta) and 1 more items have sold!
        
        Body contains:
        Order: 65A71D89-145FE5-0235A
        Order Total: $8.69
        
        ORDER DETAILS
        1 Dragonite V/Near Mint Holofoil
        1 Dragonite (52 Delta)/Heavily Played Holofoil
        """
        products = []
        
        # Extract order ID
        order_id_match = re.search(r'Order:\s*([A-Z0-9-]+)', body, re.IGNORECASE)
        order_id = order_id_match.group(1) if order_id_match else None
        
        if not order_id:
            # Try alternate pattern from older emails
            order_id_match = re.search(r'Order #?:?\s*([A-Z0-9-]+)', body, re.IGNORECASE)
            order_id = order_id_match.group(1) if order_id_match else None
        
        # Extract order total
        total_match = re.search(r'Order Total:\s*\$(\d+\.\d{2})', body, re.IGNORECASE)
        order_total = float(total_match.group(1)) if total_match else 0
        
        print(f"[DEBUG] Parsing TCGPlayer order: {order_id}, Total: ${order_total}")
        
        # Extract items - they appear as:
        # "1 Dragonite V/Near Mint Holofoil"
        # "1 Dragonite (52 Delta)/Heavily Played Holofoil"
        
        # Pattern: quantity (number) + card name + / + condition
        # The card name can include parentheses, numbers, special chars
        item_pattern = r'(\d+)\s+(.+?)/((?:Near Mint|Lightly Played|Moderately Played|Heavily Played|Damaged)(?:\s+Holofoil)?)'
        
        matches = re.finditer(item_pattern, body, re.IGNORECASE | re.MULTILINE)
        
        for match in matches:
            qty = int(match.group(1))
            card_name = match.group(2).strip()
            condition = match.group(3).strip()
            
            # Clean up card name
            card_name = re.sub(r'\s+', ' ', card_name)
            
            # Skip if this looks like a metadata line
            if any(skip in card_name.lower() for skip in ['order details', 'see all', 'remember to ship']):
                continue
            
            print(f"[DEBUG] Found item: {qty}x {card_name} ({condition})")
            
            # Try to extract set name and card number if present
            set_name = None
            card_number = None
            
            # Pattern for set names in parentheses: "Card Name (Set Name)"
            set_match = re.search(r'\(([^)]+)\)', card_name)
            if set_match:
                set_name = set_match.group(1)
            
            # Pattern for card numbers: #123 or #123/456
            number_match = re.search(r'#?(\d{1,4}(?:/\d{2,4})?)', card_name)
            if number_match:
                card_number = number_match.group(1)
            
            products.append({
                'name': card_name,
                'qty': qty,
                'condition': condition,
                'sold_price': 0.0,  # Individual prices not shown, user will need to allocate
                'platform': 'TCGPlayer',
                'order_id': order_id,
                'sold_date': date,
                'order_total': order_total,
                'set_name': set_name,
                'card_number': card_number,
                'image': None,  # Will be populated from inventory match or TCGplayer search
                'tcg_product_id': None
            })
        
        # If no items found with condition pattern, try simpler pattern
        if not products:
            print("[DEBUG] No items found with condition pattern, trying simpler pattern...")
            # Try pattern: number + text (without condition)
            simple_pattern = r'^(\d+)\s+([A-Za-z0-9\s\(\)#\-,\.\']+?)$'
            lines = body.split('\n')
            
            # Look for lines after "ORDER DETAILS"
            found_order_details = False
            for line in lines:
                line = line.strip()
                
                if 'ORDER DETAILS' in line.upper():
                    found_order_details = True
                    continue
                
                if found_order_details and line:
                    # Stop at certain keywords
                    if any(stop in line.lower() for stop in ['remember to ship', 'confirm shipment', 'thanks,', 'note:']):
                        break
                    
                    simple_match = re.match(simple_pattern, line)
                    if simple_match:
                        qty = int(simple_match.group(1))
                        card_name = simple_match.group(2).strip()
                        
                        # Clean up
                        card_name = re.sub(r'\s+', ' ', card_name)
                        
                        if len(card_name) > 3:  # Valid card name
                            print(f"[DEBUG] Found simple item: {qty}x {card_name}")
                            
                            # Try to extract set/number
                            set_name = None
                            card_number = None
                            set_match = re.search(r'\(([^)]+)\)', card_name)
                            if set_match:
                                set_name = set_match.group(1)
                            number_match = re.search(r'#?(\d{1,4}(?:/\d{2,4})?)', card_name)
                            if number_match:
                                card_number = number_match.group(1)
                            
                            products.append({
                                'name': card_name,
                                'qty': qty,
                                'condition': 'Unknown',
                                'sold_price': 0.0,
                                'platform': 'TCGPlayer',
                                'order_id': order_id,
                                'sold_date': date,
                                'order_total': order_total,
                                'set_name': set_name,
                                'card_number': card_number,
                                'image': None,
                                'tcg_product_id': None
                            })
        
        return products
    
    def parse_ebay_order(self, subject, body, date):
        """Parse eBay order notification email"""
        products = []
        
        # eBay subject usually: "You sold: [Item Name]"
        order_match = re.search(r'Order number:\s*(\d+-\d+)', body, re.IGNORECASE)
        order_id = order_match.group(1) if order_match else None
        
        # Try to extract item name from subject
        if 'you sold' in subject.lower():
            name_match = re.search(r'You sold:?\s*(.+?)(?:\s*-\s*eBay|\s*$)', subject, re.IGNORECASE)
            if name_match:
                name = name_match.group(1).strip()
                
                # Find price in body
                price_pattern = r'\$(\d+\.\d{2})'
                prices = re.findall(price_pattern, body)
                
                if prices:
                    # Usually the first significant price is the sale price
                    for price_str in prices:
                        price = float(price_str)
                        if price > 0.50:  # Ignore tiny amounts
                            products.append({
                                'name': name,
                                'qty': 1,
                                'condition': 'Unknown',
                                'sold_price': price,
                                'platform': 'eBay',
                                'order_id': order_id,
                                'sold_date': date,
                                'order_total': price
                            })
                            break
        
        return products
    
    def scrape_sold_orders(self, days=30, platforms=['tcgplayer', 'ebay']):
        """
        Scrape emails for sold orders
        
        Args:
            days: Number of days to look back
            platforms: List of platforms to search for
        """
        if not self.connect():
            return []
        
        all_products = []
        
        try:
            # Select inbox
            self.mail.select('inbox')
            
            # Build search criteria based on platforms
            search_criteria = []
            
            if 'tcgplayer' in platforms:
                # Search for TCGPlayer order emails - they use "have sold" in subject
                search_criteria.extend([
                    '(FROM "sales@tcgplayer.com")',
                    '(FROM "orders@tcgplayer.com")',
                    '(SUBJECT "have sold")',
                    '(SUBJECT "items have sold")'
                ])
            
            if 'ebay' in platforms:
                # Search for eBay order emails
                search_criteria.extend([
                    '(FROM "ebay@ebay.com" SUBJECT "sold")',
                    '(FROM "ebay.com" SUBJECT "You sold")',
                ])
            
            # Search for emails
            all_email_ids = []
            for criteria in search_criteria:
                try:
                    _, message_ids = self.mail.search(None, criteria)
                    if message_ids and message_ids[0]:
                        email_ids = message_ids[0].split()
                        all_email_ids.extend(email_ids)
                        print(f"[INFO] Found {len(email_ids)} emails with criteria: {criteria}")
                except Exception as e:
                    print(f"[WARN] Search failed for {criteria}: {e}")
                    continue
            
            # Remove duplicates
            all_email_ids = list(set(all_email_ids))
            
            print(f"[INFO] Found {len(all_email_ids)} total potential order emails")
            
            # Process each email (limit to last 100 to avoid overwhelming)
            for email_id in all_email_ids[-100:]:
                try:
                    _, msg_data = self.mail.fetch(email_id, '(RFC822)')
                    email_body = msg_data[0][1]
                    
                    # Parse with new policy for better handling
                    msg = email.message_from_bytes(email_body, policy=policy.default)
                    
                    # Get email details
                    subject = self.decode_email_subject(msg['subject'])
                    from_email = msg['from']
                    date_str = msg['date']
                    
                    # Parse date
                    try:
                        # Try parsing the date
                        if '(' in date_str:
                            date_str = date_str.split('(')[0].strip()
                        
                        # Multiple date format attempts
                        for fmt in ['%a, %d %b %Y %H:%M:%S %z', '%d %b %Y %H:%M:%S %z', '%a, %d %b %Y %H:%M:%S']:
                            try:
                                date = datetime.strptime(date_str, fmt)
                                date_str = date.strftime('%Y-%m-%d')
                                break
                            except:
                                continue
                        else:
                            # Fallback to current date
                            date_str = datetime.now().strftime('%Y-%m-%d')
                    except:
                        date_str = datetime.now().strftime('%Y-%m-%d')
                    
                    body = self.get_email_body(msg)
                    
                    print(f"[INFO] Processing: {subject[:60]}...")
                    
                    # Parse based on sender
                    products = []
                    if 'tcgplayer' in from_email.lower():
                        products = self.parse_tcgplayer_order(subject, body, date_str)
                    elif 'ebay' in from_email.lower():
                        products = self.parse_ebay_order(subject, body, date_str)
                    
                    if products:
                        print(f"[SUCCESS] Extracted {len(products)} products from email")
                        all_products.extend(products)
                    else:
                        print(f"[WARN] No products extracted from email")
                    
                except Exception as e:
                    print(f"[ERROR] Failed to process email: {e}")
                    import traceback
                    traceback.print_exc()
                    continue
        
        finally:
            self.disconnect()
        
        return all_products

def load_email_settings():
    """Load email credentials from settings.json"""
    if os.path.exists('settings.json'):
        with open('settings.json', 'r', encoding='utf-8') as f:
            settings = json.load(f)
            return {
                'email': settings.get('email_address', ''),
                'password': settings.get('email_password', ''),
                'imap_server': settings.get('imap_server', 'imap.gmail.com')
            }
    return {'email': '', 'password': '', 'imap_server': 'imap.gmail.com'}

def save_pending_sales(products):
    """Save extracted products to pending_sales.json for review"""
    pending_file = 'pending_sales.json'
    
    # Load existing pending sales
    existing_sales = []
    if os.path.exists(pending_file):
        with open(pending_file, 'r', encoding='utf-8') as f:
            try:
                existing_sales = json.load(f)
            except:
                existing_sales = []
    
    # Load inventory for matching
    inventory = []
    if os.path.exists('state.json'):
        with open('state.json', 'r', encoding='utf-8') as f:
            try:
                inventory = json.load(f)
            except:
                inventory = []
    
    # Add new products with confirmation status
    new_count = 0
    for product in products:
        # Check if already exists (by order_id and name)
        exists = any(
            p.get('order_id') == product.get('order_id') and 
            p.get('name') == product['name']
            for p in existing_sales
        )
        
        if not exists:
            # Generate unique ID
            max_id = max([p.get('id', 0) for p in existing_sales], default=0)
            product['id'] = max_id + 1
            product['confirmed'] = False
            
            # Try to match with inventory
            matched = match_with_inventory(product, inventory)
            if matched:
                product.update(matched)
                print(f"[MATCH] Matched '{product['name']}' with inventory")
            else:
                # Set defaults if not matched
                if not product.get('cost'):
                    product['cost'] = 0.0
                if not product.get('sold_price'):
                    # Suggest equal split of order total
                    order_items_count = len([p for p in products if p.get('order_id') == product.get('order_id')])
                    if order_items_count > 0:
                        product['sold_price'] = round(product.get('order_total', 0) / order_items_count, 2)
                    else:
                        product['sold_price'] = 0.0
            
            existing_sales.append(product)
            new_count += 1
    
    # Save back to file
    with open(pending_file, 'w', encoding='utf-8') as f:
        json.dump(existing_sales, f, indent=2)
    
    print(f"[SUCCESS] Saved {new_count} new pending sales to {pending_file}")
    return new_count


def match_with_inventory(product, inventory):
    """
    Try to match a product with inventory items
    Returns dict with matched data or None
    """
    from difflib import SequenceMatcher
    
    product_name = product.get('name', '').lower()
    best_match = None
    best_score = 0
    
    for item in inventory:
        item_name = item.get('name', '').lower()
        
        # Calculate similarity
        score = SequenceMatcher(None, product_name, item_name).ratio()
        
        if score > best_score:
            best_score = score
            best_match = item
    
    # If we found a good match (>80% similarity)
    if best_match and best_score > 0.8:
        return {
            'image': best_match.get('image'),
            'tcg_product_id': best_match.get('tcg_product_id'),
            'set_name': best_match.get('set_name'),
            'card_number': best_match.get('card_number'),
            'market': best_match.get('market'),
            'cost': best_match.get('cost', 0.0),  # Use inventory cost if available
            'matched': True,
            'match_score': round(best_score, 2)
        }
    
    return None

def main():
    """Main function to run email scraper"""
    print("=" * 60)
    print("TCGPlayer Email Order Scraper")
    print("=" * 60)
    
    # Load settings
    settings = load_email_settings()
    
    if not settings['email'] or not settings['password']:
        print("[ERROR] Email credentials not found in settings.json")
        print("Please add 'email_address' and 'email_password' to settings.json")
        print("\nFor Gmail users:")
        print("1. Enable 2-factor authentication")
        print("2. Generate an 'App Password' at: https://myaccount.google.com/apppasswords")
        print("3. Use the app password (not your regular password) in settings.json")
        return
    
    # Initialize scraper
    scraper = EmailScraper(
        settings['email'],
        settings['password'],
        settings['imap_server']
    )
    
    # Scrape orders
    print("\n[INFO] Scanning emails for sold orders...")
    products = scraper.scrape_sold_orders(days=30, platforms=['tcgplayer', 'ebay'])
    
    if products:
        print(f"\n[SUCCESS] Found {len(products)} sold items")
        
        # Display summary
        print("\nOrder Summary:")
        order_groups = {}
        for p in products:
            order_id = p.get('order_id', 'Unknown')
            if order_id not in order_groups:
                order_groups[order_id] = []
            order_groups[order_id].append(p)
        
        for order_id, items in order_groups.items():
            print(f"\n  Order: {order_id}")
            for item in items:
                print(f"    - {item['qty']}x {item['name']}")
        
        # Save to pending sales
        new_count = save_pending_sales(products)
        print(f"\n[INFO] {new_count} new items added to pending sales")
        print("[INFO] Go to the Sold tab in your dashboard to review and confirm these sales")
    else:
        print("\n[INFO] No new sold orders found in emails")
        print("[TIP] Make sure your email credentials are correct in settings.json")
        print("[TIP] For Gmail, you need to use an App Password, not your regular password")

if __name__ == '__main__':
    main()
