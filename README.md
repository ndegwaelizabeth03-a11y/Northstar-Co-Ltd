# Northstar Inventory Sync 

A live inventory sync service for Northstar Retail Co.'s support tool.
It polls a warehouse API on a timer, caches the result, and exposes
a query endpoint + dashboard so the support tool (or a human) always
gets an instant, up-to-date answer to "is this in stock?"

## How it works

```
warehouse_api.py          sync_service.py
(simulated warehouse) --> polls every 10s --> cache.json / in-memory
   port 5001                  |
                               v
                     GET /inventory   (query endpoint)
                     GET /            (dashboard)
                          port 5000
```

- `warehouse_api.py` — stands in for Northstar's real warehouse system.
  Serves `GET /api/inventory`.
- `sync_service.py` —  Polls the warehouse API
  every 10 seconds(POLL_INTERVAL_SECONDS=10) for easy grading and testing (specification calls for
  5 minutes in production). Caches the latest
  stock, and serves:
  - `GET /inventory` — returns the full cached inventory as JSON (the query endpoint)
  - `GET /inventory/<id>` — performs a single product lookup
  - `GET /` — provides a human-readable dashboard that auto-refreshes every 10s to display real-time updates

## Run it locally

```bash
pip install -r requirements.txt

# terminal 1
python3 warehouse_api.py

# terminal 2
python3 sync_service.py
```

Then open:
- Dashboard: http://127.0.0.1:5000/
- Query endpoint: http://127.0.0.1:5000/inventory

## Starting inventory

| Product ID | Product Name     | Quantity |
| ---------- | -----------------| -------- |
| ELYV-001   | Elysia Vanilla   | 12       |
| ATH-001    | Atheeri          | 8        |
| KHC-001    | Khair Confection | 5        |
| YY-001     | Yum Yum          | 0        |
| JZG-001    | Jazaab Gold      | 7        |

(`warehouse_api.py` randomly nudges quantities on each poll so the
dashboard has something real to show changing over time.)





