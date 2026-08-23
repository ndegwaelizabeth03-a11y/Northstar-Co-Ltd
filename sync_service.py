"""
sync_service.py

Day 3 deliverable:

1. Poll the warehouse API every 10 seconds.
2. If a polling request fails, retry up to 3 times using
   exponential backoff (1s, 2s, and 4s).
3. Cache the latest stock in memory and on disk so it survives
   a service restart.
4. Expose a query endpoint so other tools can ask
   "what's in stock?" without hitting the warehouse API directly.
5. Serve a simple dashboard so a human can see the same inventory.

If all retries fail, the service keeps serving the last successfully
cached inventory and continues normal polling.

Run with:
    python3 sync_service.py

Dashboard:
    http://127.0.0.1:5000/

Query endpoint:
    http://127.0.0.1:5000/inventory
"""

import json
import time
import threading
from datetime import datetime

import requests
from flask import Flask, jsonify, render_template_string


# ---------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------

WAREHOUSE_API_URL = "http://127.0.0.1:5001/api/inventory"

# Poll the warehouse every 10 seconds
POLL_INTERVAL_SECONDS = 10

# File used to store the latest successful inventory
CACHE_FILE = "cache.json"


# ---------------------------------------------------------------------
# IN-MEMORY CACHE
# ---------------------------------------------------------------------

# The cache is the single source of truth for the rest of the service.
# Other tools do NOT need to contact the warehouse API directly.

cache_lock = threading.Lock()

cache = {
    "items": [],
    "last_synced": None,
}


# ---------------------------------------------------------------------
# LOAD CACHE FROM DISK
# ---------------------------------------------------------------------

def load_cache():
    """
    Load the last successfully cached inventory from disk.

    This allows the service to continue serving inventory
    even after a restart.
    """

    global cache

    try:
        with open(CACHE_FILE, "r") as f:
            saved_cache = json.load(f)

        with cache_lock:
            cache["items"] = saved_cache.get("items", [])
            cache["last_synced"] = saved_cache.get("last_synced")

        print(
            f"[startup] Loaded {len(cache['items'])} items "
            f"from disk cache."
        )

    except FileNotFoundError:

        print(
            "[startup] No existing cache found. "
            "Starting with empty cache."
        )

    except (json.JSONDecodeError, OSError) as e:

        print(
            f"[startup warning] Could not load cache: {e}"
        )


# ---------------------------------------------------------------------
# POLL WAREHOUSE API
# ---------------------------------------------------------------------

def poll_warehouse():
    """
    Poll the warehouse API every 10 seconds.

    If a request fails, retry up to 3 times using
    exponential backoff:

        Attempt 1 -> wait 1 second
        Attempt 2 -> wait 2 seconds
        Attempt 3 -> wait 4 seconds

    If all retries fail, keep serving the last good cache.
    """

    MAX_RETRIES = 3
    INITIAL_BACKOFF_SECONDS = 1

    while True:

        for attempt in range(MAX_RETRIES + 1):

            try:

                response = requests.get(
                    WAREHOUSE_API_URL,
                    timeout=5
                )

                response.raise_for_status()

                items = response.json()

                # -------------------------------------------------
                # SUCCESSFUL REQUEST
                # -------------------------------------------------

                with cache_lock:

                    cache["items"] = items

                    cache["last_synced"] = datetime.now().isoformat(
                        timespec="seconds"
                    )

                # -------------------------------------------------
                # SAVE CACHE TO DISK
                # -------------------------------------------------

                with open(CACHE_FILE, "w") as f:

                    json.dump(
                        cache,
                        f,
                        indent=2
                    )

                print(
                    f"[{cache['last_synced']}] "
                    f"Synced {len(items)} items "
                    f"from warehouse API"
                )

                # Request succeeded, so stop retrying.
                break

            except requests.exceptions.RequestException as e:

                # -------------------------------------------------
                # REQUEST FAILED
                # -------------------------------------------------

                if attempt < MAX_RETRIES:

                    # Exponential backoff:
                    # 1 second, 2 seconds, 4 seconds

                    backoff_time = (
                        INITIAL_BACKOFF_SECONDS
                        * (2 ** attempt)
                    )

                    print(
                        f"[warning] "
                        f"Warehouse API request failed: {e}"
                    )

                    print(
                        f"[retry] "
                        f"Attempt {attempt + 1}/{MAX_RETRIES} "
                        f"in {backoff_time} seconds..."
                    )

                    time.sleep(backoff_time)

                else:

                    # -------------------------------------------------
                    # ALL RETRIES FAILED
                    # -------------------------------------------------

                    print(
                        f"[error] "
                        f"All {MAX_RETRIES} retries failed. "
                        f"Keeping the last good cache."
                    )

        # -------------------------------------------------------------
        # NORMAL POLLING INTERVAL
        # -------------------------------------------------------------

        time.sleep(POLL_INTERVAL_SECONDS)


# ---------------------------------------------------------------------
# FLASK APPLICATION
# ---------------------------------------------------------------------

app = Flask(__name__)


# ---------------------------------------------------------------------
# QUERY ENDPOINT
# ---------------------------------------------------------------------

@app.route("/inventory", methods=["GET"])
def get_inventory():
    """
    Return the cached inventory.

    Support tools can call this endpoint instead of
    contacting the warehouse API directly.
    """

    with cache_lock:

        return jsonify(cache)


# ---------------------------------------------------------------------
# SINGLE PRODUCT ENDPOINT
# ---------------------------------------------------------------------

@app.route("/inventory/<int:product_id>", methods=["GET"])
def get_single_product(product_id):
    """
    Look up stock for one product by ID.
    """

    with cache_lock:

        for item in cache["items"]:

            if item["product_id"] == product_id:

                return jsonify(item)

    return jsonify(
        {"error": "product not found"}
    ), 404


# ---------------------------------------------------------------------
# DASHBOARD HTML
# ---------------------------------------------------------------------

DASHBOARD_TEMPLATE = """
<!DOCTYPE html>

<html>

<head>

    <title>Northstar Inventory Dashboard</title>

    <meta http-equiv="refresh" content="10">

    <style>

        body {
            font-family: Arial, sans-serif;
            background: #f4f6f8;
            margin: 40px;
        }

        h1 {
            color: #1a1a2e;
        }

        .synced {
            color: #555;
            margin-bottom: 20px;
        }

        table {
            border-collapse: collapse;
            width: 100%;
            max-width: 700px;
            background: white;
        }

        th, td {
            padding: 12px 16px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }

        th {
            background: #1a1a2e;
            color: white;
        }

        .in-stock {
            color: #1a7a3c;
            font-weight: bold;
        }

        .low-stock {
            color: #b8860b;
            font-weight: bold;
        }

        .out-of-stock {
            color: #c0392b;
            font-weight: bold;
        }

    </style>

</head>


<body>

    <h1>Northstar Live Inventory</h1>

    <p class="synced">

        Last synced from warehouse:

        {{ last_synced }}

        (page auto-refreshes every 10s)

    </p>


    <table>

        <tr>

            <th>Product ID</th>

            <th>Product Name</th>

            <th>Quantity</th>

            <th>Status</th>

        </tr>


        {% for item in items %}

        <tr>

            <td>
                {{ item.product_id }}
            </td>

            <td>
                {{ item.product_name }}
            </td>

            <td>
                {{ item.quantity }}
            </td>

            <td>

                {% if item.quantity == 0 %}

                    <span class="out-of-stock">
                        Out of stock
                    </span>

                {% elif item.quantity < 5 %}

                    <span class="low-stock">
                        Low stock
                    </span>

                {% else %}

                    <span class="in-stock">
                        In stock
                    </span>

                {% endif %}

            </td>

        </tr>

        {% endfor %}

    </table>

</body>

</html>
"""


# ---------------------------------------------------------------------
# DASHBOARD ROUTE
# ---------------------------------------------------------------------

@app.route("/", methods=["GET"])
def dashboard():
    """
    Human-readable dashboard showing the cached inventory.
    """

    with cache_lock:

        return render_template_string(
            DASHBOARD_TEMPLATE,
            items=cache["items"],
            last_synced=(
                cache["last_synced"]
                or "not synced yet"
            ),
        )


# ---------------------------------------------------------------------
# START SERVICE
# ---------------------------------------------------------------------

if __name__ == "__main__":

    # ---------------------------------------------------------------
    # Load the previous cache from disk first.
    # ---------------------------------------------------------------

    load_cache()

    # ---------------------------------------------------------------
    # Start the background polling thread.
    # ---------------------------------------------------------------

    poller_thread = threading.Thread(
        target=poll_warehouse,
        daemon=True
    )

    poller_thread.start()

    # ---------------------------------------------------------------
    # Display service information.
    # ---------------------------------------------------------------

    print(
        "Sync service running on "
        "http://127.0.0.1:5000"
    )

    print(
        "Dashboard:      "
        "http://127.0.0.1:5000/"
    )

    print(
        "Query endpoint: "
        "http://127.0.0.1:5000/inventory"
    )

    # ---------------------------------------------------------------
    # Start Flask server.
    # ---------------------------------------------------------------

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
        use_reloader=False
    )
