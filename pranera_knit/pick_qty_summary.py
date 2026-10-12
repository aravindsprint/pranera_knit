"""
pranera_knit/pick_qty_summary.py

Keeps Roll Pick Assignment.pick_qty_summary (the per-UOM breakdown added
by patches/v1_1/add_pick_qty_summary.py) — and the underlying pick_qty
grand total that the tolerance-based free-scan flow already reads
(api/pick_order.py, RollWisePickOrderExecutionPage.vue) — in sync with
batch_items whenever it's used.

Each summary row carries two numbers per UOM:
  * total_qty    — the TARGET qty from batch_items (unchanged; this is what
                   pick_qty / the ±3% tolerance is built from).
  * total_weight — the PICKED weight in kg, summed from the
                   batch_wise_pick_item.weight of every submitted Roll Wise
                   Pick List linked to this assignment (patches/v1_3).
                   For Pcs items this is the physical roll weight, not a
                   piece count.

Registered as a "validate" doc_event against "Roll Pick Assignment" in
hooks.py — a doctype this app doesn't own (it belongs to Textiles And
Garments). Because the assignment is usually already submitted by the
time its pick lists are, total_weight is also refreshed from the Roll
Wise Pick List's on_submit / on_cancel (refresh_from_pick_list).
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

    weights = picked_weight_by_uom(doc.name) if not doc.is_new() else {}

    doc.set("pick_qty_summary", [])
    for uom, qty in totals.items():
        doc.append("pick_qty_summary", {
            "uom": uom,
            "total_qty": qty,
            "total_weight": weights.get(uom, 0),
        })
    # A UOM that was picked but isn't in the targets still gets its weight shown.
    for uom, weight in weights.items():
        if uom not in totals:
            doc.append("pick_qty_summary", {
                "uom": uom, "total_qty": 0, "total_weight": weight,
            })

    # Pick Qty stays the single grand total across all UOMs (targets only) —
    # the per-UOM table above is the human-readable view; this remains the
    # one number the tolerance-based scan flow (api/pick_order.py) reads.
    doc.pick_qty = sum(totals.values())


def picked_weight_by_uom(roll_pick_assignment):
    """{uom: kg} from every submitted Roll Wise Pick List of this assignment."""
    if not roll_pick_assignment:
        return {}
    rows = frappe.db.sql(
        """
        SELECT b.uom, SUM(IFNULL(b.weight, 0)) AS weight
        FROM `tabBatch Wise Pick Item` b
        JOIN `tabRoll Wise Pick List` p ON p.name = b.parent
        WHERE b.parenttype = 'Roll Wise Pick List'
          AND p.docstatus = 1
          AND p.roll_pick_assignment = %s
        GROUP BY b.uom
        """,
        roll_pick_assignment,
        as_dict=True,
    )
    return {r.uom or "": round(float(r.weight or 0), 3) for r in rows}


def refresh_summary_weight(roll_pick_assignment):
    """Write total_weight onto an assignment's existing summary rows in
    place (works on a submitted assignment, no re-save)."""
    if not roll_pick_assignment or not frappe.db.exists(
        "Roll Pick Assignment", roll_pick_assignment
    ):
        return

    weights = picked_weight_by_uom(roll_pick_assignment)
    rows = frappe.get_all(
        "Roll Pick Qty Summary",
        filters={
            "parent": roll_pick_assignment,
            "parenttype": "Roll Pick Assignment",
            "parentfield": "pick_qty_summary",
        },
        fields=["name", "uom", "idx"],
        order_by="idx asc",
    )
    seen = set()
    for r in rows:
        seen.add(r.uom or "")
        frappe.db.set_value(
            "Roll Pick Qty Summary", r.name, "total_weight",
            weights.get(r.uom or "", 0), update_modified=False,
        )

    next_idx = (rows[-1].idx if rows else 0) + 1
    for uom, weight in weights.items():
        if uom in seen:
            continue
        row = frappe.get_doc({
            "doctype": "Roll Pick Qty Summary",
            "parent": roll_pick_assignment,
            "parenttype": "Roll Pick Assignment",
            "parentfield": "pick_qty_summary",
            "idx": next_idx,
            "uom": uom,
            "total_qty": 0,
            "total_weight": weight,
            "docstatus": frappe.db.get_value(
                "Roll Pick Assignment", roll_pick_assignment, "docstatus"
            ),
        })
        row.db_insert()
        next_idx += 1


def refresh_from_pick_list(doc, method=None):
    """Roll Wise Pick List on_submit / on_cancel hook."""
    refresh_summary_weight(doc.get("roll_pick_assignment"))


def _batch_stock_uom(batch):
    if not batch:
        return None
    return frappe.db.get_value("Batch", batch, "stock_uom")
