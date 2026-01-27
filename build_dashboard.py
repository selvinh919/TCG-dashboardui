import json, os, urllib.parse
from config import EBAY_CAMPAIGN_ID

STATE_PATH = "state.json"

with open(STATE_PATH, "r", encoding="utf-8") as f:
    items = json.load(f)

rows = ""

total_ask = 0
total_market = 0

for item in items:
    name = item.get("display_name", item["name"])
    base_name = item.get("base_name", name)
    card_number = item.get("card_number", "")
    set_name = item.get("set_name", "")
    price = float(item.get("price", 0))
    market = item.get("market")
    qty = item.get("qty", 1)
    image = item.get("image", "")
    tcg_url = item.get("tcg_url")  # Public product page
    tcg_product_id = item.get("tcg_product_id")  # Product ID from URL

    total_ask += price * qty
    if market:
        total_market += market * qty

    delta = "—"
    row_class = ""

    if market is not None:
        diff = market - price
        if diff < 0:
            row_class = "danger"
            delta = f"-${abs(diff):.2f}"
        else:
            row_class = "good"
            delta = f"+${diff:.2f}"

    # Build search queries using base name + card number
    search_query = f"{base_name} {card_number}".strip()
    
    # eBay sold/completed listings
    ebay_sold_url = f"https://www.ebay.com/sch/i.html?_nkw={urllib.parse.quote(search_query)}&LH_Sold=1&LH_Complete=1"
    
    # eBay active listings with affiliate link
    ebay_listings_url = (
        f"https://www.ebay.com/sch/i.html?_nkw={urllib.parse.quote(search_query)}"
        f"&mkcid=1&mkrid=711-53200-19255-0&siteid=0&campid={EBAY_CAMPAIGN_ID}"
        f"&customid=&toolid=10001&mkevt=1"
    )
    
    # TCG search
    tcg_search = tcg_url if tcg_url else f"https://www.tcgplayer.com/search/pokemon/product?q={urllib.parse.quote(search_query)}"
    
    # TCG Edit (admin panel)
    if tcg_product_id:
        tcg_edit = f"https://store.tcgplayer.com/admin/product/manage/{tcg_product_id}"
    else:
        tcg_edit = tcg_search

    # Determine if this is a sealed product (box, pack, collection, etc.)
    # If card has a card number, it's a single card (even if name contains "box")
    if card_number:
        product_type = 'single'
    else:
        # No card number - check if it's a sealed product
        is_sealed = any(keyword in name.lower() for keyword in [
            'elite trainer box', 'booster pack', 'booster bundle', 
            'collection', 'bundle', 'tin', 'premium collection',
            'box set', 'trainer box', 'deck', 'gift box'
        ])
        product_type = 'sealed' if is_sealed else 'single'

    rows += f"""
    <tr class="{row_class}" data-type="{product_type}">
        <td class="image-cell">
          <a href="{tcg_edit}" target="_blank">
            <img src="{image}" onerror="this.src='https://via.placeholder.com/80x110?text=NO+IMAGE'">
          </a>
          <img class="image-preview" src="{image}" onerror="this.src='https://via.placeholder.com/80x110?text=NO+IMAGE'">
        </td>
        <td>
            <strong>{base_name}{f' #{card_number}' if card_number else ''}</strong>
            {f'<br><small style="color:#888">{set_name}</small>' if set_name else ''}
        </td>
        <td>${price:.2f}</td>
        <td>{f"${market:.2f}" if market else "—"}</td>
        <td><strong>{delta}</strong></td>
        <td>
            <a href="{ebay_sold_url}" target="_blank">🟦 eBay Sold</a><br>
            <a href="{ebay_listings_url}" target="_blank">🟦 eBay Buy</a><br>
            <a href="{tcg_search}" target="_blank">🟪 TCG</a><br>
            <a href="{tcg_edit}" target="_blank">✏️ Edit</a>
        </td>
    </tr>
    """

net_delta = total_market - total_ask

html = f"""
<!DOCTYPE html>
<html>
<head>
<title>TCG Inventory Dashboard</title>
<style>
body {{ background:#0f0f0f; color:#eaeaea; font-family:Arial; }}
table {{ width:100%; border-collapse:collapse; }}
td, th {{ padding:8px; }}
img {{ width:48px; cursor:pointer; }}
.image-cell {{ position:relative; }}
.image-preview {{ display:none; position:absolute; left:100%; top:50%; transform:translateY(-50%); z-index:9999; height:200px; width:auto; margin-left:20px; box-shadow:0 0 20px rgba(0,0,0,0.9); border:2px solid #444; border-radius:8px; }}
.image-cell:hover .image-preview {{ display:block; }}
.good {{ background:#0d2a17; }}
.danger {{ background:#3a0d0d; }}
.stats {{ display:flex; gap:20px; margin-bottom:12px; align-items:center; }}
.stats div {{ padding:10px; background:#1a1a1a; border-radius:6px; }}
.controls {{ display:flex; gap:12px; margin-bottom:12px; align-items:center; }}
input[type="text"] {{ padding:8px; background:#1a1a1a; color:#eaeaea; border:1px solid #444; border-radius:4px; width:300px; }}
select {{ padding:8px; background:#1a1a1a; color:#eaeaea; border:1px solid #444; border-radius:4px; }}
a {{ color:#8ab4f8; text-decoration:none; }}
button {{ padding:8px 16px; background:#1a1a1a; color:#eaeaea; border:1px solid #444; border-radius:4px; cursor:pointer; }}
button:hover {{ background:#2a2a2a; }}
button.active {{ background:#2a5a2a; border-color:#4a8a4a; }}
#syncBtn {{ background:#1a4a1a; border-color:#2a6a2a; }}
#syncBtn:hover {{ background:#2a5a2a; }}
#syncBtn:disabled {{ background:#333; color:#666; cursor:not-allowed; }}
.sync-status {{ padding:8px 12px; background:#1a1a1a; border-radius:4px; font-size:14px; }}
.sync-status.success {{ background:#0d2a17; color:#4a8a4a; }}
.sync-status.error {{ background:#3a0d0d; color:#ff6666; }}
.hidden {{ display:none; }}
</style>
<script>
function filterTable() {{
  const searchInput = document.getElementById('searchInput').value.toLowerCase();
  const sortFilter = document.getElementById('sortFilter').value;
  const viewFilter = document.getElementById('viewFilter').value;
  const rows = Array.from(document.querySelectorAll('tbody tr'));
  
  rows.forEach(row => {{
    const name = row.cells[1].textContent.toLowerCase();
    const matchesSearch = name.includes(searchInput);
    const productType = row.getAttribute('data-type');
    
    let matchesView = true;
    if (viewFilter === 'singles') {{
      matchesView = productType === 'single';
    }} else if (viewFilter === 'sealed') {{
      matchesView = productType === 'sealed';
    }}
    // 'all' shows everything
    
    if (matchesSearch && matchesView) {{
      row.style.display = '';
    }} else {{
      row.style.display = 'none';
    }}
  }});
  
  // Sort if needed
  if (sortFilter !== 'none') {{
    const tbody = document.querySelector('tbody');
    const sortedRows = rows.sort((a, b) => {{
      if (sortFilter === 'name') {{
        return a.cells[1].textContent.localeCompare(b.cells[1].textContent);
      }} else if (sortFilter === 'price') {{
        const priceA = parseFloat(a.cells[2].textContent.replace('$', ''));
        const priceB = parseFloat(b.cells[2].textContent.replace('$', ''));
        return priceB - priceA;
      }} else if (sortFilter === 'delta') {{
        const deltaA = parseFloat(a.cells[4].textContent.replace(/[^0-9.-]/g, ''));
        const deltaB = parseFloat(b.cells[4].textContent.replace(/[^0-9.-]/g, ''));
        return deltaB - deltaA;
      }}
      return 0;
    }});
    sortedRows.forEach(row => tbody.appendChild(row));
  }}
}}

async function syncData() {{
  const btn = document.getElementById('syncBtn');
  const status = document.getElementById('syncStatus');
  
  // Disable button
  btn.disabled = true;
  btn.textContent = '🔄 Syncing...';
  status.textContent = 'Fetching latest data from TCGPlayer...';
  status.className = 'sync-status';
  status.style.display = 'block';
  
  try {{
    const response = await fetch('/sync', {{ method: 'POST' }});
    const data = await response.json();
    
    if (response.ok) {{
      status.textContent = data.message;
      status.className = 'sync-status success';
      
      // Auto-refresh after 30 seconds
      setTimeout(() => {{
        location.reload();
      }}, 30000);
    }} else {{
      status.textContent = data.message;
      status.className = 'sync-status error';
      btn.disabled = false;
      btn.textContent = '🔄 Sync';
    }}
  }} catch (error) {{
    status.textContent = 'Error: Could not connect to server. Make sure server.py is running.';
    status.className = 'sync-status error';
    btn.disabled = false;
    btn.textContent = '🔄 Sync';
  }}
}}
</script>
</head>
<body>

<h2>📦 TCG Inventory Dashboard</h2>

<div class="stats">
  <div>Ask: <strong>${total_ask:,.2f}</strong></div>
  <div>Market: <strong>${total_market:,.2f}</strong></div>
  <div>Δ: <strong>${net_delta:,.2f}</strong></div>
</div>

<div class="controls">
  <input type="text" id="searchInput" placeholder="Search cards..." onkeyup="filterTable()">
  <select id="viewFilter" onchange="filterTable()">
    <option value="all">Show All</option>
    <option value="singles">Show Singles</option>
    <option value="sealed">Show Sealed</option>
  </select>
  <select id="sortFilter" onchange="filterTable()">
    <option value="none">Sort by...</option>
    <option value="name">Name</option>
    <option value="price">Price (High to Low)</option>
    <option value="delta">Profit (High to Low)</option>
  </select>
  <button id="syncBtn" onclick="syncData()">🔄 Sync</button>
</div>

<div id="syncStatus" class="sync-status" style="display:none; margin-bottom:12px;"></div>

<table>
<thead>
<tr>
<th>Image</th><th>Card Name</th><th>Ask</th><th>Market</th><th>Δ</th><th>Actions</th>
</tr>
</thead>
<tbody>
{rows}
</tbody>
</table>

</body>
</html>
"""

with open("inventory_dashboard.html", "w", encoding="utf-8") as f:
    f.write(html)

print("[SUCCESS] inventory_dashboard.html generated")
