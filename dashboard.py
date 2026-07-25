"""
Writes a tiny static dashboard into docs/ so GitHub Pages can serve it for free.
No server, no JS build step — just a JSON data file + a plain HTML page that
fetches it client-side and renders a table, color-coded by buy/sell strength.
"""
import json
import os
from datetime import datetime, timezone

DOCS_DIR = "docs"
DATA_FILE = os.path.join(DOCS_DIR, "data.json")
INDEX_FILE = os.path.join(DOCS_DIR, "index.html")

INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Crypto Signal Dashboard</title>
<style>
  body { font-family: -apple-system, Roboto, Arial, sans-serif; background:#0f1115; color:#e6e6e6; margin:0; padding:16px; }
  h1 { font-size:1.3rem; margin-bottom:4px; }
  #updated { color:#888; font-size:0.85rem; margin-bottom:16px; }
  table { width:100%; border-collapse:collapse; font-size:0.9rem; }
  th, td { padding:10px 8px; text-align:left; border-bottom:1px solid #262a33; }
  th { color:#999; font-weight:600; font-size:0.75rem; text-transform:uppercase; }
  .buy { color:#3ddc84; font-weight:700; }
  .sell { color:#ff5c5c; font-weight:700; }
  .neutral { color:#888; }
  .badge { display:inline-block; padding:2px 8px; border-radius:6px; font-size:0.75rem; font-weight:700; }
  .badge-buy { background:#123321; color:#3ddc84; }
  .badge-sell { background:#3a1616; color:#ff5c5c; }
  .badge-neutral { background:#1c1f26; color:#888; }
  #empty { color:#888; padding:24px 0; text-align:center; }
</style>
</head>
<body>
  <h1>📊 Crypto Signal Dashboard</h1>
  <div id="updated">Loading…</div>
  <table id="tbl">
    <thead>
      <tr><th>Coin</th><th>Price</th><th>Buy</th><th>Sell</th><th>RSI</th><th>Signal</th></tr>
    </thead>
    <tbody id="rows"></tbody>
  </table>
  <div id="empty" style="display:none;">No data yet — the bot hasn't completed a run.</div>

<script>
async function load() {
  const res = await fetch('data.json?t=' + Date.now());
  const data = await res.json();
  document.getElementById('updated').textContent = 'Last updated: ' + new Date(data.updated_utc).toLocaleString();
  const rows = document.getElementById('rows');
  rows.innerHTML = '';
  if (!data.coins || data.coins.length === 0) {
    document.getElementById('empty').style.display = 'block';
    return;
  }
  data.coins.sort((a,b) => Math.max(b.buy_strength,b.sell_strength) - Math.max(a.buy_strength,a.sell_strength));
  for (const c of data.coins) {
    const tr = document.createElement('tr');
    let badge = '<span class="badge badge-neutral">watching</span>';
    if (c.buy_strength >= 70) badge = '<span class="badge badge-buy">🟢 HEAVY BUY</span>';
    else if (c.sell_strength >= 70) badge = '<span class="badge badge-sell">🔴 HEAVY SELL</span>';
    tr.innerHTML = `
      <td><strong>${c.symbol}</strong></td>
      <td>$${c.last_price}</td>
      <td class="buy">${c.buy_strength}</td>
      <td class="sell">${c.sell_strength}</td>
      <td class="neutral">${c.rsi}</td>
      <td>${badge}</td>`;
    rows.appendChild(tr);
  }
}
load();
setInterval(load, 60000); // refresh view every 60s (data itself updates every ~5 min)
</script>
</body>
</html>
"""


def write_dashboard(results: list[tuple[str, str, dict]]):
    """results: list of (symbol, source, metrics_dict) as produced in main.py"""
    os.makedirs(DOCS_DIR, exist_ok=True)

    payload = {
        "updated_utc": datetime.now(timezone.utc).isoformat(),
        "coins": [
            {
                "symbol": symbol,
                "source": source,
                "last_price": m["last_price"],
                "buy_strength": m["buy_strength"],
                "sell_strength": m["sell_strength"],
                "rsi": m["rsi"],
            }
            for symbol, source, m in results
        ],
    }

    with open(DATA_FILE, "w") as f:
        json.dump(payload, f, indent=2)

    # Only write index.html if it doesn't exist yet (avoid clobbering any manual edits)
    if not os.path.exists(INDEX_FILE):
        with open(INDEX_FILE, "w") as f:
            f.write(INDEX_HTML)
