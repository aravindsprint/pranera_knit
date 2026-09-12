"""
pranera_knit/pick_qty_summary.py

Keeps Roll Pick Assignment.pick_qty_summary (the per-UOM breakdown added
by patches/v1_1/add_pick_qty_summary.py) — and the underlying pick_qty
grand total that the tolerance-based free-scan flow already reads
(api/pick_order.py, RollWisePickOrderExecutionPage.vue) — in sync with
batch_items whenever it's used.

Registered as a "validate" doc_event against "Roll Pick Assignment" in
hooks.py — a doctype this app doesn't own (it belongs to Textiles And
Garments), the same pattern already used for the "Stock Entry" doc_event
below it, which likewise reaches into a doctype owned elsewhere.
"""
import frappe


def set_pick_qty_summary(doc, method=None):
    if not doc.get("batch_items"):
        return

    totals = {}
    for row in doc.batch_items:
        if not row.qty:
            continue
        uom = row.get("stock_uom") or _batch_stock_uom(row.batch) or ""
        totals[uom] = totals.get(uom, 0) + row.qty

    doc.set("pick_qty_summary", [])
    for uom, qty in totals.items():
        doc.append("pick_qty_summary", {"uom": uom, "total_qty": qty})

    # Pick Qty stays the single grand total across all UOMs — the per-UOM
    # table above is the human-readable view; this remains the one number
    # the tolerance-based scan flow (api/pick_order.py) actually reads.
    doc.pick_qty = sum(totals.values())


def _batch_stock_uom(batch):
    if not batch:
        return None
    return frappe.db.get_value("Batch", batch, "stock_uom")
