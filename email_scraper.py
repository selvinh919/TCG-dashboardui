"""
Email scraper for TCGPlayer sale notifications
Monitors inbox for sale emails and extracts product info
"""
import imaplib
import email
from email.header import decode_header
import re
from datetime import datetime
import json
import os
from html.parser import HTMLParser

# File to store confirmed sale order IDs
CONFIRMED_SALES_FILE = 'confirmed_sales.json'

class HTMLStripper(HTMLParser):
    """Simple HTML tag stripper to convert HTML emails to plain text"""
    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.text = []
    
    def handle_data(self, data):
        self.text.append(data)
    
    def get_text(self):
        return ''.join(self.text)

def strip_html_tags(html):
    """Strip HTML tags from text"""
    stripper = HTMLStripper()
    try:
        stripper.feed(html)
        return stripper.get_text()
    except:
        # Fallback: simple regex strip
        return re.sub(r'<[^>]+>', '', html)


def load_confirmed_sales():
    """Load list of confirmed order IDs"""
    if os.path.exists(CONFIRMED_SALES_FILE):
        try:
            with open(CONFIRMED_SALES_FILE, 'r') as f:
                return json.load(f)
        except:
            return []
    return []

def save_confirmed_sale(order_id):
    """Add order ID to confirmed sales list"""
    confirmed = load_confirmed_sales()
    if order_id and order_id not in confirmed:
        confirmed.append(order_id)
        with open(CONFIRMED_SALES_FILE, 'w') as f:
            json.dump(confirmed, f, indent=2)
        print(f"[CACHE] Saved confirmed order: {order_id}")

class TCGEmailScraper:
    def __init__(self, email_address, password, imap_server='imap.gmail.com'):
        """
        Initialize email scraper
        
        Args:
            email_address: Your email address
            password: App password (for Gmail) or regular password
            imap_server: IMAP server address (default: Gmail)
        """
        self.email_address = email_address
        self.password = password
        self.imap_server = imap_server
        self.mail = None
    
    def connect(self):
        """Connect to email server"""
        try:
            self.mail = imaplib.IMAP4_SSL(self.imap_server)
            self.mail.login(self.email_address, self.password)
            print(f"[EMAIL] Connected to {self.email_address}")
            return True
        except Exception as e:
            print(f"[EMAIL ERROR] Failed to connect: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from email server"""
        if self.mail:
            self.mail.logout()
            print("[EMAIL] Disconnected")
    
    def fetch_tcgplayer_sales(self, unread_only=True, max_emails=50):
        """
        Fetch TCGPlayer sale notification emails
        
        Args:
            unread_only: Only fetch unread emails
            max_emails: Maximum number of emails to fetch
        
        Returns:
            List of sale notifications with product info
        """
        if not self.mail:
            if not self.connect():
                return []
        
        try:
            # Select inbox
            self.mail.select('INBOX')
            
            # Search criteria for TCGPlayer sale notifications
            # Subject line: "Your TCGplayer.com items of {product} have sold!"
            search_criteria = [
                '(FROM "TCGplayer" SUBJECT "have sold")',
                '(FROM "tcgplayer.com" SUBJECT "sold")',
                '(FROM "tcgplayer" SUBJECT "Order")',
                '(SUBJECT "TCGplayer.com items")',
                '(SUBJECT "Your TCGplayer.com items")'
            ]
            
            all_sales = []
            seen_order_ids = set()
            confirmed_sales = load_confirmed_sales()  # Load already confirmed sales
            
            for criteria in search_criteria:
                search_query = f'({criteria})'
                if unread_only:
                    search_query = f'(UNSEEN {criteria})'
                
                try:
                    status, messages = self.mail.search(None, search_query)
                    if status != 'OK':
                        continue
                    
                    email_ids = messages[0].split()
                    
                    # Limit to max_emails
                    email_ids = email_ids[-max_emails:]
                    
                    print(f"[EMAIL] Found {len(email_ids)} emails matching: {criteria}")
                    
                    for email_id in email_ids:
                        sale_data = self._parse_email(email_id)
                        if sale_data:
                            # Check for duplicate order IDs
                            order_id = None
                            if sale_data.get('products'):
                                order_id = sale_data['products'][0].get('order_id')
                            
                            # Skip if already confirmed
                            if order_id and order_id in confirmed_sales:
                                print(f"[EMAIL] Skipping already confirmed order: {order_id}")
                                continue
                            
                            # Skip if duplicate in this session
                            if order_id and order_id in seen_order_ids:
                                print(f"[EMAIL] Skipping duplicate order: {order_id}")
                                continue
                            
                            if order_id:
                                seen_order_ids.add(order_id)
                            
                            all_sales.append(sale_data)
                
                except Exception as e:
                    print(f"[EMAIL ERROR] Search failed for {criteria}: {e}")
                    continue
            
            return all_sales
            
        except Exception as e:
            print(f"[EMAIL ERROR] Failed to fetch emails: {e}")
            return []
    
    def _parse_email(self, email_id):
        """
        Parse individual email to extract sale information
        
        Args:
            email_id: Email ID from IMAP
        
        Returns:
            Dict with sale info or None if not a sale notification
        """
        try:
            status, msg_data = self.mail.fetch(email_id, '(RFC822)')
            if status != 'OK':
                return None
            
            # Parse email
            email_body = msg_data[0][1]
            email_message = email.message_from_bytes(email_body)
            
            # Get subject
            subject = self._decode_header(email_message['Subject'])
            
            # Get date
            date_str = email_message['Date']
            
            # Get body
            body = self._get_email_body(email_message)
            
            # Parse sale information from body
            sale_info = self._extract_sale_info(subject, body, date_str)
            
            if sale_info:
                sale_info['email_id'] = email_id.decode()
                return sale_info
            
            return None
            
        except Exception as e:
            print(f"[EMAIL ERROR] Failed to parse email {email_id}: {e}")
            return None
    
    def _decode_header(self, header):
        """Decode email header"""
        if header is None:
            return ""
        decoded = decode_header(header)
        result = ""
        for part, encoding in decoded:
            if isinstance(part, bytes):
                result += part.decode(encoding or 'utf-8', errors='ignore')
            else:
                result += part
        return result
    
    def _get_email_body(self, email_message):
        """Extract email body text"""
        body = ""
        
        if email_message.is_multipart():
            for part in email_message.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))
                
                if content_type == "text/plain" and "attachment" not in content_disposition:
                    try:
                        body += part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    except:
                        pass
                elif content_type == "text/html" and not body:
                    try:
                        body += part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    except:
                        pass
        else:
            try:
                body = email_message.get_payload(decode=True).decode('utf-8', errors='ignore')
            except:
                body = str(email_message.get_payload())
        
        return body
    
    def _extract_sale_info(self, subject, body, date_str):
        """
        Extract sale information from TCGPlayer email content
        
        TCGPlayer format:
        - Subject: "Your TCGplayer.com items of Mew ex - 151/165 have sold!"
        - Body: "1 Mew ex - 151/165/Near Mint Holofoil"
        - Order Total: $5.99
        - Order: 65A71D89-0F1F1F-5C620
        
        Args:
            subject: Email subject line
            body: Email body text (may be HTML)
            date_str: Email date string
        
        Returns:
            Dict with product info or None
        """
        
        # Strip HTML tags if email is HTML formatted
        if body.strip().startswith('<'):
            print(f"[EMAIL DEBUG] Converting HTML email to plain text...")
            body = strip_html_tags(body)
        
        # Clean up excessive whitespace
        body = re.sub(r'\n\s*\n', '\n', body)  # Remove blank lines
        body = re.sub(r'  +', ' ', body)  # Replace multiple spaces with single space
        
        # Debug: Print body sections
        print(f"[EMAIL DEBUG] ==========================================")
        print(f"[EMAIL DEBUG] Subject: {subject}")
        print(f"[EMAIL DEBUG] Body length: {len(body)} chars")
        print(f"[EMAIL DEBUG] Body preview (first 2000 chars):")
        print(f"[EMAIL DEBUG] {body[:2000]}")
        print(f"[EMAIL DEBUG] ---")
        print(f"[EMAIL DEBUG] Body preview (LAST 1000 chars):")
        print(f"[EMAIL DEBUG] {body[-1000:]}")
        print(f"[EMAIL DEBUG] ==========================================")
        
        sale_data = {
            'subject': subject,
            'date': date_str,
            'timestamp': datetime.now().isoformat(),
            'products': []
        }
        
        # Check if this is actually a sale notification
        if 'have sold' not in subject.lower() and 'order' not in body.lower():
            print(f"[EMAIL DEBUG] Rejected - no 'have sold' in subject or 'order' in body")
            return None
        
        # Extract order ID
        order_id_match = re.search(r'Order:\s*([A-Z0-9-]+)', body, re.IGNORECASE)
        order_id = order_id_match.group(1) if order_id_match else None
        
        # Extract order total (handle both $ and escaped $ from PowerShell)
        total_match = re.search(r'Order\s*Total:\s*[\$\`]\s*([\d.]+)', body, re.IGNORECASE)
        order_total = float(total_match.group(1)) if total_match else 0.0
        
        # Extract order date
        date_match = re.search(r'order date of\s+(\d{1,2}/\d{1,2}/\d{4})', body, re.IGNORECASE)
        order_date = date_match.group(1) if date_match else None
        
        # Extract product details from body
        # TCGPlayer format (multi-line):
        #   "1"
        #   "Dragonite V/Near Mint Holofoil"
        # OR single line: "1 Mew ex - 151/165/Near Mint Holofoil"
        
        found_products = []
        temp_products = []  # Collect products first to calculate total quantity
        
        # Look for product lines in the body
        lines = body.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Check if this line is just a quantity (1-2 digits)
            if re.match(r'^\d{1,2}$', line):
                quantity = int(line)
                # Next line should be product/condition
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    # Format: "Product Name/Condition" or "Product Name - 123/456/Condition"
                    if '/' in next_line:
                        # Split by last / to get condition
                        parts = next_line.rsplit('/', 1)
                        if len(parts) == 2:
                            product_part = parts[0].strip()
                            condition = parts[1].strip()
                            
                            # Check if product has card number (format: Name - 123/456)
                            card_match = re.search(r'^(.+?)\s+-\s+(\d+/\d+)$', product_part)
                            if card_match:
                                product_name = card_match.group(1).strip()
                                card_number = card_match.group(2).strip()
                            else:
                                product_name = product_part
                                card_number = ""
                            
                            full_name = f"{product_name} #{card_number}" if card_number else product_name
                            
                            # Skip duplicates
                            if any(p['name'] == full_name for p in temp_products):
                                i += 2
                                continue
                            
                            # Store temporarily (price calculated later)
                            temp_products.append({
                                'name': full_name,
                                'quantity': quantity,
                                'card_number': card_number,
                                'condition': condition,
                                'order_id': order_id,
                                'order_date': order_date
                            })
                            
                            i += 2  # Skip both quantity and product lines
                            continue
            
            # Fallback: Try old single-line patterns
            old_patterns = [
                r'^(\d+)\s+(.+?)\s+-\s+(\d+/\d+)/(.+)$',  # "1 Mew ex - 151/165/Near Mint"
                r'^(\d+)\s+(.+?)/(.+)$',  # "1 Dragonite V/Near Mint Holofoil"
            ]
            
            for pattern in old_patterns:
                match = re.match(pattern, line, re.IGNORECASE)
                if match:
                    try:
                        groups = match.groups()
                        
                        if len(groups) >= 4:
                            # Full format with card number and condition
                            quantity = int(groups[0])
                            product_name = groups[1].strip()
                            card_number = groups[2].strip()
                            condition = groups[3].strip()
                            
                        elif len(groups) >= 3:
                            # Has quantity, name, and condition
                            quantity = int(groups[0])
                            product_name = groups[1].strip()
                            card_number = ""
                            condition = groups[2].strip()
                        else:
                            i += 1
                            continue
                        
                        full_name = f"{product_name} #{card_number}" if card_number else product_name
                        
                        # Skip duplicates
                        if any(p['name'] == full_name for p in found_products):
                            break
                        
                        # Calculate per-item price
                        price_per_item = order_total / quantity if quantity > 0 and order_total > 0 else 0
                        
                        found_products.append({
                            'name': full_name,
                            'quantity': quantity,
                            'price': price_per_item,
                            'card_number': card_number,
                            'condition': condition,
                            'order_id': order_id,
                            'order_date': order_date
                        })
                        
                        print(f"[EMAIL] Extracted: {full_name} (Qty: {quantity}, ${price_per_item:.2f}, {condition})")
                        break
                        
                    except Exception as e:
                        print(f"[EMAIL ERROR] Failed to parse product line '{line}': {e}")
                        continue
            
            i += 1
        
        # Calculate total quantity across all products
        total_quantity = sum(p['quantity'] for p in temp_products)
        
        # Now calculate price per item based on total quantity
        if total_quantity > 0 and order_total > 0:
            price_per_item = order_total / total_quantity
            
            for product in temp_products:
                product['price'] = price_per_item
                found_products.append(product)
                print(f"[EMAIL] Extracted: {product['name']} (Qty: {product['quantity']}, ${price_per_item:.2f} each, {product['condition']})")
        elif temp_products:
            # If no order total, set price to 0
            for product in temp_products:
                product['price'] = 0
                found_products.append(product)
                print(f"[EMAIL] Extracted: {product['name']} (Qty: {product['quantity']}, $0.00, {product['condition']})")
        
        # If no products found with body patterns, try to extract from subject line
        if not found_products:
            # Subject: "Your TCGplayer.com items of Mew ex - 151/165 have sold!"
            subject_match = re.search(r'items of\s+([^-]+?)\s+-\s+(\d+/\d+)\s+have sold', subject, re.IGNORECASE)
            if subject_match:
                product_name = subject_match.group(1).strip()
                card_number = subject_match.group(2).strip()
                full_name = f"{product_name} #{card_number}"
                
                found_products.append({
                    'name': full_name,
                    'quantity': 1,  # Assume 1 if not specified
                    'price': order_total,
                    'card_number': card_number,
                    'condition': 'Unknown',
                    'order_id': order_id,
                    'order_date': order_date
                })
                
                print(f"[EMAIL] Extracted from subject: {full_name}")
        
        sale_data['products'] = found_products
        
        # Only return if we found at least one product
        if sale_data['products']:
            return sale_data
        
        print(f"[EMAIL] No products found in email. Subject: {subject[:50]}...")
        return None
    
    def mark_as_read(self, email_id):
        """Mark email as read"""
        try:
            self.mail.store(email_id, '+FLAGS', '\\Seen')
            return True
        except Exception as e:
            print(f"[EMAIL ERROR] Failed to mark as read: {e}")
            return False


def save_pending_sales(sales):
    """Save pending sales to file"""
    pending_file = 'pending_sales.json'
    
    try:
        # Load existing pending sales
        if os.path.exists(pending_file):
            with open(pending_file, 'r', encoding='utf-8') as f:
                existing = json.load(f)
        else:
            existing = []
        
        # Add new sales
        existing.extend(sales)
        
        # Save back
        with open(pending_file, 'w', encoding='utf-8') as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)
        
        print(f"[EMAIL] Saved {len(sales)} pending sales")
        return True
    
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to save pending sales: {e}")
        return False


def load_pending_sales():
    """Load pending sales from file"""
    pending_file = 'pending_sales.json'
    
    try:
        if os.path.exists(pending_file):
            with open(pending_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to load pending sales: {e}")
        return []


if __name__ == '__main__':
    # Test the scraper
    print("TCGPlayer Email Scraper Test")
    print("=" * 60)
    print("NOTE: You need to provide email credentials in settings.json")
    print("For Gmail, use an App Password: https://myaccount.google.com/apppasswords")
    print()
    
    # Load credentials from settings
    try:
        with open('settings.json', 'r') as f:
            settings = json.load(f)
        
        email_address = settings.get('email_address')
        email_password = settings.get('email_password')
        
        if not email_address or not email_password:
            print("Please add 'email_address' and 'email_password' to settings.json")
            exit(1)
        
        scraper = TCGEmailScraper(email_address, email_password)
        
        print(f"Connecting to {email_address}...")
        if scraper.connect():
            print("Fetching sale notifications...")
            sales = scraper.fetch_tcgplayer_sales(unread_only=False, max_emails=10)
            
            print(f"\nFound {len(sales)} sale notifications:")
            for i, sale in enumerate(sales, 1):
                print(f"\n{i}. {sale['subject']}")
                print(f"   Date: {sale['date']}")
                print(f"   Products: {len(sale['products'])}")
                for product in sale['products']:
                    print(f"      - {product['name']} (Qty: {product['quantity']}, ${product['price']})")
            
            scraper.disconnect()
        else:
            print("Failed to connect to email server")
    
    except FileNotFoundError:
        print("settings.json not found. Creating template...")
        template = {
            "email_address": "your_email@gmail.com",
            "email_password": "your_app_password_here",
            "tcgplayer_username": ""
        }
        with open('settings.json', 'w') as f:
            json.dump(template, f, indent=2)
        print("Please edit settings.json with your credentials")
