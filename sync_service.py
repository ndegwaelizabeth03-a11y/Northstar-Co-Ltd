"""
sync_service.py

This is the actual Day 3 deliverable:
    1. Poll the warehouse API on a 10seconds timer (every POLL_INTERVAL_SECONDS=10seconds)
    2. Cache the latest stock in memory (and on disk, so it survives a restart)
    3. Expose a query endpoint so other tools (like the support tool) can
       ask "what's in stock?" without hitting the warehouse API directly
    4. Serve a simple dashboard so a human can see the same thing

Run it with:  python3 sync_service.py
(make sure warehouse_api.py is already running first)

Dashboard:      http://127.0.0.1:5000/
Query endpoint: http://127.0.0.1:5000/inventory
"""

import json
import time
import threading
from datetime import datetime

import requests
from flask import Flask, jsonify, render_template_string

# ---- Config -----------------------------------------------------------
WAREHOUSE_API_URL = "http://127.0.0.1:5001/api/inventory"
POLL_INTERVAL_SECONDS = 10   # spec asks for 5 min in production; 10s while testing
CACHE_FILE = "cache.json"

# ---- The cache ----------------------------------------------------------
# This is the "single source of truth" the rest of the app reads from.
# We never make the support tool wait on the warehouse API -- it always
# reads this cache instead, which is the whole point of a sync service.
cache_lock = threading.Lock()
cache = {
    "items": [],
    "last_synced": None,
}


def poll_warehouse():
    """
    Runs forever in a background thread. Every POLL_INTERVAL_SECONDS=10seconds,
    it asks the warehouse API for the current inventory and updates
    the cache.
    """
    while True:
        try:
            response = requests.get(WAREHOUSE_API_URL, timeout=5)
            response.raise_for_status()
            items = response.json()

            with cache_lock:
                cache["items"] = items
                cache["last_synced"] = datetime.now().isoformat(timespec="seconds")

            # Also save to disk so the cache isn't lost if the service restarts
            with open(CACHE_FILE, "w") as f:
                json.dump(cache, f, indent=2)

            print(f"[{cache['last_synced']}] Synced {len(items)} items from warehouse API")

        except requests.exceptions.RequestException as e:
            # If the warehouse API is down, we keep serving the last good
            # cache instead of crashing -- that's the whole point of caching.
            print(f"[warning] Could not reach warehouse API: {e}")

        time.sleep(POLL_INTERVAL_SECONDS)


# ---- The Flask app --------------------------------------------------------
app = Flask(__name__)


@app.route("/inventory", methods=["GET"])
def get_inventory():
    """The query endpoint. This is what the support tool would call."""
    with cache_lock:
        return jsonify(cache)


@app.route("/inventory/<int:product_id>", methods=["GET"])
def get_single_product(product_id):
    """Look up stock for one product by ID."""
    with cache_lock:
        for item in cache["items"]:
            if item["product_id"] == product_id:
                return jsonify(item)
    return jsonify({"error": "product not found"}), 404


DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Northstar Inventory Dashboard</title>
    <meta http-equiv="refresh" content="10">
    <style>
        body { font-family: Arial, sans-serif; background: #f4f6f8; margin: 40px; }
        h1 { color: #1a1a2e; }
        .synced { color: #555; margin-bottom: 20px; }
        table { border-collapse: collapse; width: 100%; max-width: 700px; background: white; }
        th, td { padding: 12px 16px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #1a1a2e; color: white; }
        .in-stock { color: #1a7a3c; font-weight: bold; }
        .low-stock { color: #b8860b; font-weight: bold; }
        .out-of-stock { color: #c0392b; font-weight: bold; }
    </style>
</head>
<body>
    <h1>Northstar Live Inventory</h1>
    <p class="synced">Last synced from warehouse: {{ last_synced }} (page auto-refreshes every 10s)</p>
    <table>
        <tr><th>Product ID</th><th>Product Name</th><th>Quantity</th><th>Status</th></tr>
        {% for item in items %}
        <tr>
            <td>{{ item.product_id }}</td>
            <td>{{ item.product_name }}</td>
            <td>{{ item.quantity }}</td>
            <td>
                {% if item.quantity == 0 %}
                    <span class="out-of-stock">Out of stock</span>
                {% elif item.quantity < 5 %}
                    <span class="low-stock">Low stock</span>
                {% else %}
                    <span class="in-stock">In stock</span>
                {% endif %}
            </td>
        </tr>
        {% endfor %}
    </table>
</body>
</html>
"""


@app.route("/", methods=["GET"])
def dashboard():
    """Human-readable dashboard showing the cached inventory."""
    with cache_lock:
        return render_template_string(
            DASHBOARD_TEMPLATE,
            items=cache["items"],
            last_synced=cache["last_synced"] or "not synced yet",
        )


if __name__ == "__main__":
    # Start the background poller before the web server so there's
    # already data cached by the time someone loads the dashboard.
    poller_thread = threading.Thread(target=poll_warehouse, daemon=True)
    poller_thread.start()

    print("Sync service running on http://127.0.0.1:5000")
    print("Dashboard:      http://127.0.0.1:5000/")
    print("Query endpoint: http://127.0.0.1:5000/inventory")
    app.run(host="127.0.0.1", port=5000, debug=False)
