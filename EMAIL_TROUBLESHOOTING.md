# Email Connection Troubleshooting Guide

## Common Issues and Solutions

### ❌ "Invalid credentials" or "Authentication failed"

This is the MOST COMMON issue, especially for Gmail users.

#### For Gmail Users:
**Gmail REQUIRES an App Password - NOT your regular Gmail password!**

1. **Generate an App Password:**
   - Go to: https://myaccount.google.com/apppasswords
   - Select "Mail" application
   - Select "Other (Custom name)" device
   - Type: "TCG Dashboard"
   - Click "Generate"
   - You'll get a 16-character password like: `abcd efgh ijkl mnop`

2. **Important: Remove ALL spaces from the App Password**
   - Example: `abcd efgh ijkl mnop` → `abcdefghijklmnop`
   - Copy the password WITHOUT spaces

3. **Enable IMAP in Gmail:**
   - Go to Gmail Settings → Forwarding and POP/IMAP
   - Enable IMAP
   - Save changes

4. **Use the correct IMAP server:**
   - Select "Gmail (imap.gmail.com)" from the dropdown

5. **Test the connection:**
   - Click "Test Email Connection" in the Settings page
   - Should see "✅ Email connection successful!"

#### For Outlook/Hotmail Users:
- Your regular password usually works
- IMAP server: `outlook.office365.com`
- Make sure IMAP is enabled in Outlook settings

#### For Yahoo Mail Users:
- Generate an App Password: https://login.yahoo.com/account/security
- Enable "Allow apps that use less secure sign in"
- IMAP server: `imap.mail.yahoo.com`

### ❌ "Connection timeout" or "Cannot connect"

1. Check your internet connection
2. Verify the IMAP server address is correct
3. Check if your firewall/antivirus is blocking port 993 (IMAP SSL)
4. Some corporate networks block IMAP - try from home

### ❌ Settings not saving between sessions

Your settings ARE being saved to `settings.json`. If you think they're not:

1. Check the file exists: `c:\Users\selvi\OneDrive\Desktop\tcg_inventory_bot\settings.json`
2. Make sure you clicked "Save Settings" button
3. Refresh the page - settings should reload automatically
4. Check browser console (F12) for any error messages

### ❌ Password field shows dots (••••••••)

This is normal! It's a password field for security.

**NEW FEATURE:** Click the 👁️ eye icon next to the password field to show/hide your password. This helps you verify you entered the App Password correctly (no spaces!).

## Debugging Steps

If email connection still fails:

1. **Verify your email credentials:**
   - Click the 👁️ button to show your password
   - Make sure it's the App Password (16 chars, no spaces)
   - NOT your regular email password

2. **Test manually with Python:**
   ```powershell
   python -c "import imaplib; imap = imaplib.IMAP4_SSL('imap.gmail.com'); imap.login('your.email@gmail.com', 'yourapppassword'); print('SUCCESS')"
   ```

3. **Check the browser console (F12):**
   - Look for error messages when you click "Test Email Connection"
   - Share any error messages for help

4. **Check settings.json:**
   - Open the file in a text editor
   - Verify email_address and email_password are correct
   - Make sure there are no extra quotes or spaces

## Still Having Issues?

1. Take a screenshot of:
   - The Settings page (with password visible using 👁️ button)
   - Any error messages
   - The browser console (F12)

2. Verify:
   - Email provider (Gmail, Outlook, Yahoo, etc.)
   - Whether you're using an App Password or regular password
   - IMAP server address

3. Common mistakes:
   - Using regular Gmail password instead of App Password
   - Forgetting to remove spaces from App Password
   - IMAP not enabled in email settings
   - Wrong IMAP server address
