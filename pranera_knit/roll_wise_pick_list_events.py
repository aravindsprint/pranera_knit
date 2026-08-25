import frappe


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

    roll_nos = [
        row.roll_no for row in (pick_list.get("roll_wise_pick_item") or [])
        if row.roll_no
    ]
    if not roll_nos:
        return  # batch-transfer pick — no individual rolls tracked

    for roll_no in roll_nos:
        if frappe.db.exists("Roll", roll_no):
            frappe.db.set_value("Roll", roll_no, "warehouse", new_warehouse)
