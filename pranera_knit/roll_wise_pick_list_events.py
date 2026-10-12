import frappe


def set_batch_wise_weight(doc, method=None):
    """Batch Wise Pick Item belongs to the Textiles And Garments app, not
    this one — reached via doc_event the same way Roll Pick Assignment's
    pick_qty_summary is (see hooks.py's note on that hook).

    "weight" is a Custom Field (see the Batch Wise Pick Item-weight
    Custom Field) holding the total ROLL WEIGHT of the matching Roll Wise
    Pick Item rows, grouped by Item Code + Warehouse + Batch. This is the
    physical weight in kg regardless of the item's UOM — for Pcs items
    (collars/cuffs) Qty is a piece count, so weight must come from
    roll_weight, never from Qty.

    roll_weight is fetch_from roll_no.roll_weight; _validate_links fills
    it before validate hooks run, but if it's still empty (e.g. a roll
    with no weight set yet) we read it straight off the Roll.

    Batch-transfer picks have no Roll Wise Pick Item rows at all (see
    create_roll_picking_entry in knit.py) — those groups keep falling
    back to the batch row's own Qty, as before."""
    rows = doc.get("batch_wise_pick_item") or []
    if not rows:
        return

    weights = {}
    for roll in doc.get("roll_wise_pick_item") or []:
        roll_weight = float(roll.roll_weight or 0)
        # QI-sourced rows (qi_report set) carry their own weight; their
        # roll_no is not a Roll document, so never look it up there.
        if not roll_weight and roll.roll_no and not roll.get("qi_report"):
            roll_weight = float(
                frappe.db.get_value("Roll", roll.roll_no, "roll_weight") or 0
            )
            roll.roll_weight = roll_weight
        key = (roll.item_code, roll.warehouse, roll.batch)
        weights[key] = weights.get(key, 0.0) + roll_weight

    qty_totals = {}
    for row in rows:
        key = (row.item_code, row.warehouse, row.batch)
        qty_totals[key] = qty_totals.get(key, 0.0) + float(row.qty or 0)

    for row in rows:
        key = (row.item_code, row.warehouse, row.batch)
        if key in weights:
            row.weight = round(weights[key], 3)
        else:
            row.weight = qty_totals[key]


def on_stock_entry_submit(doc, method=None):
    """When a Stock Entry created via the Roll-wise Pick List app is
    submitted, push the transfer's target warehouse onto every Roll it
    moved — so each roll's `warehouse` field always reflects where it
    physically is right now, not just where it started."""
    _sync_roll_warehouse(doc, reverse=False)


def on_stock_entry_cancel(doc, method=None):
    """Mirror of the above: if the Stock Entry is cancelled, put each
    roll's warehouse back to the transfer's source warehouse, since the
    move never actually happened."""
    _sync_roll_warehouse(doc, reverse=True)


def _sync_roll_warehouse(doc, reverse):
    # Scoped strictly to Stock Entries created via the Roll Wise Pick List
    # app (custom_roll_wise_pick_list set on submit — see
    # create_roll_picking_entry in api/knit.py). Every other Stock Entry
    # in the system (ordinary Material Transfers, Manufacture entries,
    # etc.) is untouched.
    pick_list_name = doc.get("custom_roll_wise_pick_list")
    if not pick_list_name or not doc.items:
        return

    # create_roll_picking_entry always applies one uniform source/target
    # warehouse pair across every item row of a given roll-wise pick's
    # Stock Entry — safe to read off the first row rather than per-item.
    target_warehouse = doc.items[0].t_warehouse
    source_warehouse = doc.items[0].s_warehouse
    new_warehouse = source_warehouse if reverse else target_warehouse
    if not new_warehouse:
        return

    if not frappe.db.exists("Roll Wise Pick List", pick_list_name):
        return
    pick_list = frappe.get_doc("Roll Wise Pick List", pick_list_name)

    # Skip QI-sourced rows: their roll_no is a QI Report Details roll
    # number, not a Roll document (and may collide with an unrelated one).
    roll_nos = [
        row.roll_no for row in (pick_list.get("roll_wise_pick_item") or [])
        if row.roll_no and not row.get("qi_report")
    ]
    if not roll_nos:
        return  # batch-transfer pick — no individual rolls tracked

    for roll_no in roll_nos:
        if frappe.db.exists("Roll", roll_no):
            frappe.db.set_value("Roll", roll_no, "warehouse", new_warehouse)
