"""
pranera_knit/outward_request_events.py

Validation for Outward Request, and the status tracking that follows it
through the existing pick flow:

    Outward Request
      └─ Roll Pick Assignment   (outward_request, docstatus 1)  → "Roll Pick Assigned"
          └─ Roll Wise Pick List (roll_pick_assignment, docstatus 1) → "Picked"
              └─ Stock Entry   (custom_roll_wise_pick_list, docstatus 1) → "Completed"

Status        : "" | Roll Pick Assigned | Picked | Completed
Doc Status    : Pending (nothing assigned yet) | Processing | Completed
(request_status — "docstatus" is a reserved column, see the v1_5 patch.)

Status is always RECOMPUTED from the linked documents rather than nudged
forward step by step, so cancelling a Stock Entry / Pick List /
Assignment rolls the request back to whatever stage is still true.

Ordering note: create_roll_picking_entry (api/knit.py) stamps
roll_pick_assignment onto the Roll Wise Pick List with db_set only AFTER
both the pick list and its Stock Entry have been submitted, so the
on_submit hooks below can't yet walk back to the request on that path.
That function calls refresh_for_assignment() itself once the link is in
place. The hooks still cover every later change — a draft Stock Entry
submitted from Desk, any cancel, re-linking an Assignment.
"""
import frappe
from frappe import _
from frappe.utils import now_datetime, flt

PENDING, PROCESSING, COMPLETED = "Pending", "Processing", "Completed"
ASSIGNED, PICKED = "Roll Pick Assigned", "Picked"

# Legacy rule from before "From" was selectable: with no From building set,
# every row's warehouse must be a NAP warehouse (name LIKE 'NAP%'). Once a
# From building is set, the row's warehouse only has to belong to that
# building (_validate_from_and_warehouses) — e.g. JV_WAREHOUSE → JV/A107.
WAREHOUSE_PREFIX = "NAP"
QTY_TOLERANCE = 0.001


def is_allowed_warehouse(warehouse, from_building=None):
    if not warehouse:
        return False
    if from_building:
        return True
    return warehouse.upper().startswith(WAREHOUSE_PREFIX)


# ── Outward Request itself ────────────────────────────────────────────────

def validate_outward_request(doc, method=None):
    if bool(doc.work_order) == bool(doc.purchase_order):
        frappe.throw(_("Set either a Work Order or a Purchase Order (exactly one)"))

    if not doc.get("items"):
        frappe.throw(_("Add at least one item"))
    for row in doc.items:
        if flt(row.qty) <= 0:
            frappe.throw(_("Row {0}: Qty must be greater than zero").format(row.idx))
        if row.batch:
            batch_item = frappe.db.get_value("Batch", row.batch, "item")
            if batch_item and batch_item != row.item_code:
                frappe.throw(_("Row {0}: Batch {1} belongs to item {2}, not {3}")
                             .format(row.idx, row.batch, batch_item, row.item_code))

    # Past-date check + same-day approval (cut-off time, approvers) —
    # see outward_request_approval.py.
    from pranera_knit import outward_request_approval
    outward_request_approval.apply(doc)

    # One request per Work Order; From ≠ To; row warehouses in From.
    validate_one_request_per_work_order(doc)
    _validate_from_and_warehouses(doc)
    # NAP% warehouses only; qty ≤ free stock; Work Order qty match.
    _validate_warehouse_prefix(doc)
    _validate_free_stock(doc)
    _validate_work_order_qty(doc)

    if doc.is_new():
        doc.created_by = doc.created_by or frappe.session.user
        doc.created_on = doc.created_on or now_datetime()
        doc.status = ""
        doc.request_status = PENDING
        return

    # Once a pick has been assigned against it, the request is what the
    # floor is working to — don't let it change underneath them.
    if frappe.db.get_value("Outward Request", doc.name, "request_status") != PENDING:
        frappe.throw(_("Outward Request {0} is already being processed and can no longer be edited")
                     .format(doc.name))


def existing_request_for_work_order(work_order, exclude=None):
    if not work_order:
        return None
    return frappe.db.get_value(
        "Outward Request",
        {"work_order": work_order, "name": ["!=", exclude or ""]},
        "name", order_by="creation asc",
    )


def validate_one_request_per_work_order(doc):
    if not doc.get("work_order"):
        return
    if not (doc.is_new() or doc.has_value_changed("work_order")):
        return
    other = existing_request_for_work_order(doc.work_order, exclude=doc.name)
    if other:
        frappe.throw(
            _("Work Order {0} already has Outward Request {1}. Only one Outward Request "
              "is allowed per Work Order — open {1} and edit it instead.")
            .format(doc.work_order, other),
            title=_("Duplicate Outward Request"),
        )


def _validate_from_and_warehouses(doc):
    from_building = doc.get("from_building")
    if from_building and from_building == doc.get("to_building"):
        frappe.throw(_("From and To can't be the same building ({0})").format(from_building))

    warehouses = {r.get("warehouse") for r in doc.get("items") or [] if r.get("warehouse")}
    if not warehouses:
        return
    wh_building = dict(frappe.get_all(
        "Warehouse", filters={"name": ["in", list(warehouses)]},
        fields=["name", "building"], as_list=True,
    ))
    for row in doc.items:
        wh = row.get("warehouse")
        if not wh:
            continue
        if not row.batch:
            frappe.throw(_("Row {0}: pick a Batch along with Warehouse {1}").format(row.idx, wh))
        building = wh_building.get(wh)
        if from_building and building and building != from_building:
            frappe.throw(_("Row {0}: Warehouse {1} is in {2}, not in From building {3}")
                         .format(row.idx, wh, building, from_building))


def _validate_warehouse_prefix(doc):
    from_building = doc.get("from_building")
    for row in doc.get("items") or []:
        wh = row.get("warehouse")
        if wh and not is_allowed_warehouse(wh, from_building):
            frappe.throw(_("Row {0}: Warehouse {1} is not allowed — only {2}% warehouses can be used")
                         .format(row.idx, wh, WAREHOUSE_PREFIX))


def _validate_free_stock(doc):
    """What this request takes from each (batch, warehouse), summed over its
    rows, must not exceed that pair's free qty: Stock Ledger balance minus
    what other not-yet-Completed Outward Requests reserve there (the same
    "free" number the batch dropdown shows)."""
    from pranera_knit.api.outward_request import _batch_balances, _reservations, _stock_info

    taken, first_row = {}, {}
    for row in doc.get("items") or []:
        if not (row.batch and row.get("warehouse")):
            continue
        key = (row.batch, row.warehouse)
        taken[key] = taken.get(key, 0.0) + flt(row.qty)
        first_row.setdefault(key, row)
    if not taken:
        return

    batches = list({b for b, _w in taken})
    stock = {(b.batch, b.warehouse): b.qty for b in _batch_balances(batches)}
    reservations = _reservations(batches, exclude_request=doc.name if not doc.is_new() else None)
    for key, qty in taken.items():
        batch, wh = key
        free = _stock_info(batch, wh, stock.get(key, 0), reservations.get(batch, []))["available_qty"]
        if flt(qty) - flt(free) > QTY_TOLERANCE:
            row = first_row[key]
            frappe.throw(
                _("Row {0}: Qty {1} {2} of Batch {3} in {4} is more than the free stock {5} {2}")
                .format(row.idx, round(flt(qty), 3), row.stock_uom or "", batch, wh,
                        round(max(flt(free), 0), 3)),
                title=_("Not enough free stock"),
            )


def work_order_required_qty(work_order):
    """{item_code: total required_qty} from the Work Order's Required Items."""
    out = {}
    for r in frappe.get_all(
        "Work Order Item",
        filters={"parenttype": "Work Order", "parent": work_order},
        fields=["item_code", "required_qty"],
    ):
        out[r.item_code] = round(out.get(r.item_code, 0.0) + flt(r.required_qty), 3)
    return out


def _validate_work_order_qty(doc):
    """Work Order requests: an item may be left out (only part of the
    Required Items is sent from NAP), but an item that IS on the request
    must total exactly its Required Qty — summed over its rows, since one
    item can be split across several batches."""
    if not doc.get("work_order"):
        return
    required = work_order_required_qty(doc.work_order)

    entered, uom = {}, {}
    for row in doc.get("items") or []:
        if row.item_code not in required:
            frappe.throw(_("Row {0}: Item {1} is not in Work Order {2}'s Required Items")
                         .format(row.idx, row.item_code, doc.work_order))
        entered[row.item_code] = entered.get(row.item_code, 0.0) + flt(row.qty)
        uom.setdefault(row.item_code, row.stock_uom or "")

    mismatched = [
        _("{0}: entered {1}, required {2} {3}").format(
            item, round(qty, 3), required[item], uom[item])
        for item, qty in entered.items()
        if abs(round(qty, 3) - required[item]) > QTY_TOLERANCE
    ]
    if mismatched:
        frappe.throw(
            _("Qty must match the Work Order {0}'s Required Qty for each item sent:")
            .format(doc.work_order) + " " + "; ".join(mismatched),
            title=_("Qty doesn't match the Work Order"),
        )


def on_trash_outward_request(doc, method=None):
    linked = frappe.get_all(
        "Roll Pick Assignment",
        filters={"outward_request": doc.name, "docstatus": ["<", 2]},
        pluck="name", limit=1,
    )
    if linked:
        frappe.throw(_("Cannot delete: Roll Pick Assignment {0} is linked to this request")
                     .format(linked[0]))


# ── Status computation ────────────────────────────────────────────────────

def compute_status(outward_request):
    assignments = frappe.get_all(
        "Roll Pick Assignment",
        filters={"outward_request": outward_request, "docstatus": 1},
        pluck="name",
    )
    if not assignments:
        return "", PENDING

    pick_lists = frappe.get_all(
        "Roll Wise Pick List",
        filters={"roll_pick_assignment": ["in", assignments], "docstatus": 1},
        pluck="name",
    )
    if not pick_lists:
        return ASSIGNED, PROCESSING

    has_submitted_entry = frappe.db.exists(
        "Stock Entry",
        {"custom_roll_wise_pick_list": ["in", pick_lists], "docstatus": 1},
    )
    if has_submitted_entry:
        return COMPLETED, COMPLETED
    return PICKED, PROCESSING


def refresh_status(outward_request):
    if not outward_request or not frappe.db.exists("Outward Request", outward_request):
        return
    status, request_status = compute_status(outward_request)
    current = frappe.db.get_value(
        "Outward Request", outward_request, ["status", "request_status"], as_dict=True
    )
    if (current.status or "") == status and current.request_status == request_status:
        return
    frappe.db.set_value(
        "Outward Request", outward_request,
        {"status": status, "request_status": request_status},
        update_modified=True,
    )
    if (current.status or "") != status:
        from pranera_knit.push import outward_request_status_changed
        outward_request_status_changed(outward_request, current.status, status)


def refresh_for_assignment(roll_pick_assignment):
    if not roll_pick_assignment:
        return
    refresh_status(frappe.db.get_value("Roll Pick Assignment", roll_pick_assignment, "outward_request"))


def refresh_for_pick_list(roll_wise_pick_list):
    if not roll_wise_pick_list:
        return
    refresh_for_assignment(
        frappe.db.get_value("Roll Wise Pick List", roll_wise_pick_list, "roll_pick_assignment")
    )


# ── doc_events (wired in hooks.py) ────────────────────────────────────────

def on_roll_pick_assignment_change(doc, method=None):
    refresh_status(doc.get("outward_request"))
    # Assignment re-pointed at a different request (allow_on_submit field)
    # — the old one may need to fall back to Pending.
    before = doc.get_doc_before_save() if method == "on_update_after_submit" else None
    if before and before.get("outward_request") != doc.get("outward_request"):
        refresh_status(before.get("outward_request"))


def on_roll_wise_pick_list_change(doc, method=None):
    refresh_for_assignment(doc.get("roll_pick_assignment"))


def on_stock_entry_change(doc, method=None):
    refresh_for_pick_list(doc.get("custom_roll_wise_pick_list"))
