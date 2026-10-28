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
