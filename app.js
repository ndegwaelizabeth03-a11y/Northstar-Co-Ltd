// app.js
// Talks to the backend's query endpoint (GET /inventory) and keeps the
// dashboard in sync. This is the "frontend" half of the pipeline:
// warehouse API -> sync_service cache -> this page.

const POLL_INTERVAL_MS = 10000; // match sync_service.py's POLL_INTERVAL_SECONDS

const tableBody = document.getElementById("inventoryBody");
const lastSyncedEl = document.getElementById("lastSynced");
const statusText = document.getElementById("statusText");
const pulseDot = document.getElementById("pulseDot");
const summaryRow = document.getElementById("summaryRow");

// Remember previous quantities so we can flash a row when something changes
let previousQuantities = {};

function statusForQuantity(qty) {
    if (qty === 0) return { label: "Out of stock", cls: "out-stock" };
    if (qty < 5) return { label: "Low stock", cls: "low-stock" };
    return { label: "In stock", cls: "in-stock" };
}

function renderInventory(items) {
    tableBody.innerHTML = "";

    items.forEach((item) => {
        const row = document.createElement("tr");
        const status = statusForQuantity(item.quantity);

        const changed =
            previousQuantities[item.product_id] !== undefined &&
            previousQuantities[item.product_id] !== item.quantity;

        if (changed) row.classList.add("changed");

        row.innerHTML = `
            <td class="id-cell">#${String(item.product_id).padStart(3, "0")}</td>
            <td>${item.product_name}</td>
            <td class="qty-cell">${item.quantity}</td>
            <td><span class="status-pill ${status.cls}">${status.label}</span></td>
        `;
        tableBody.appendChild(row);

        previousQuantities[item.product_id] = item.quantity;
    });

    renderSummary(items);
}

function renderSummary(items) {
    const totalUnits = items.reduce((sum, i) => sum + i.quantity, 0);
    const outOfStock = items.filter((i) => i.quantity === 0).length;
    const lowStock = items.filter((i) => i.quantity > 0 && i.quantity < 5).length;

    summaryRow.innerHTML = `
        <div class="summary-chip"><strong>${items.length}</strong> SKUs tracked</div>
        <div class="summary-chip"><strong>${totalUnits}</strong> total units</div>
        <div class="summary-chip"><strong>${lowStock}</strong> low stock</div>
        <div class="summary-chip"><strong>${outOfStock}</strong> out of stock</div>
    `;
}

function firePulse(online) {
    pulseDot.classList.toggle("offline", !online);
    pulseDot.classList.remove("firing");
    // restart the animation
    void pulseDot.offsetWidth;
    pulseDot.classList.add("firing");
}

async function fetchInventory() {
    try {
        const response = await fetch("/inventory");
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();

        renderInventory(data.items || []);
        lastSyncedEl.textContent = data.last_synced || "not synced yet";
        statusText.textContent = "Live";
        firePulse(true);
    } catch (err) {
        statusText.textContent = "Connection lost";
        firePulse(false);
        console.error("Failed to fetch /inventory:", err);
    }
}

// Initial load, then poll on the same cadence as the backend sync
fetchInventory();
setInterval(fetchInventory, POLL_INTERVAL_MS);
