"""
warehouse_api.py

This pretends to be Northstar's real warehouse system.
In real life, Northstar would already have this running somewhere
and would just hand you a URL. Since we don't have that, this file
plays that role so the rest of the project has something real to
poll against.

Run it with:  python3 warehouse_api.py
It starts a tiny web server on http://127.0.0.1:5001
"""

from flask import Flask, jsonify
import random

app = Flask(__name__)

# This is the "source of truth" inventory sitting in the warehouse.
# In a real system this would live in a database. Here it's just a
# Python list of dictionaries so it's easy to read.
inventory = [
    {"product_id": 1, "product_name": "Elysia Vanilla",   "quantity": 12},
    {"product_id": 2, "product_name": "Atheeri",          "quantity": 8},
    {"product_id": 3, "product_name": "Khair Confection", "quantity": 5},
    {"product_id": 4, "product_name": "Yum Yum",          "quantity": 0},
    {"product_id": 5, "product_name": "Jazaab Gold",      "quantity": 7},
]


@app.route("/api/inventory", methods=["GET"])
def get_inventory():
    """
    This is the endpoint our sync service will poll.
    Every time it's called, there's a small chance a random item's
    stock changes slightly -- just so your dashboard has something
    real to show changing over time, like a real warehouse would.
    """
    if random.random() < 0.4:  # 40% chance something changes each poll
        item = random.choice(inventory)
        change = random.choice([-2, -1, 1, 2])
        item["quantity"] = max(0, item["quantity"] + change)

    return jsonify(inventory)


if __name__ == "__main__":
    print("Northstar warehouse API (simulated) running on http://127.0.0.1:5001")
    app.run(host="127.0.0.1", port=5001, debug=False)
