"""
pranera_knit/api/pick_order.py
Server-side whitelisted methods for the "Roll Pick Assignment" flow.

Roll Pick Assignment is a purpose-built doctype owned entirely by this
app (pranera_knit/knit_module/doctype/roll_pick_assignment) — not an
extension of another app's doctype, to avoid the cross-app drift issues
this app has hit before (Server Scripts and Custom Fields that only
existed on production and were never fixture-exported).

A supervisor sets a target weight (pick_qty) for a Work Order rather than
pre-selecting exact rolls — the worker free-scans rolls until the
cumulative picked weight falls within a +/-3% tolerance of that target.
Roll weights vary in the real world, so hitting an exact target
roll-by-roll isn't practical — a tolerance band is.

Two validations run on every scan:
  1. Warehouse match — the roll's actual current location (Roll.warehouse)
     must match whichever Source Warehouse the worker currently has
     selected (chosen dynamically in the execution page, not locked to
     whatever the supervisor set at creation — the worker may need to
     adjust it to match where the rolls actually physically are).
  2. Project match (pick_type == "To Work Order" only) — the roll's
     Project must match the target Work Order's Project, so material
     doesn't get misrouted into an unrelated project's job.

The +/-3% tolerance itself is enforced authoritatively server-side, in
knit.create_roll_picking_entry (not here) — that's the single point where
an Assignment's fulfillment actually becomes a real Stock Entry, so
that's where the final check has to live; a client-side-only check could
be bypassed by calling the API directly.
"""
import frappe
from frappe import _

TOLERANCE_PCT = 0.03


def _assert_assigned_to_me(doc):
    if doc.assigned_to != frappe.session.user:
        frappe.throw(_("This Pick Order is not assigned to you"), frappe.PermissionError)


def _already_picked_qty(assignment_name):
    """Sum of roll qty already submitted against this Assignment in prior
    sessions (each a separate Roll Wise Pick List + Stock Entry) — lets a
    worker who partially fulfilled it earlier resume and see progress."""
    linked = frappe.get_all(
        "Roll Wise Pick List",
        filters={"roll_pick_assignment": assignment_name, "docstatus": 1},
        pluck="name",
    )
    if not linked:
        return 0.0, []
    rows = frappe.get_all(
        "Roll Wise Pick Item",
        filters={"parenttype": "Roll Wise Pick List", "parent": ["in", linked]},
        fields=["roll_no", "item_code", "batch", "warehouse", "qty", "uom"],
    )
    total = sum(float(r.qty or 0) for r in rows)
    return total, rows


@frappe.whitelist()
def get_my_pick_orders():
    """Assignments given to the current user, still open (not yet
    Completed/Cancelled). Used by the "My Pick Orders" list page."""
    return frappe.get_all(
        "Roll Pick Assignment",
        filters={
            "assigned_to": frappe.session.user,
            "docstatus": 1,
            "status": ["in", ["Pending", "In Progress"]],
        },
        fields=[
            "name", "posting_date", "pick_type", "work_order", "project",
            "source_warehouse", "target_warehouse", "pick_qty", "status",
        ],
        order_by="posting_date desc, creation desc",
    )


@frappe.whitelist()
def get_pick_order_detail(name):
    """Full detail for one Assignment: the target (pick_qty + tolerance
    band) and whatever's already been picked against it in prior
    sessions, so a worker resuming mid-way sees accurate progress."""
    doc = frappe.get_doc("Roll Pick Assignment", name)
    _assert_assigned_to_me(doc)

    pick_qty = float(doc.pick_qty or 0)
    already_qty, already_rolls = _already_picked_qty(name)

    return {
        "name": doc.name,
        "posting_date": doc.posting_date,
        "status": doc.status,
        "pick_type": doc.pick_type,
        "document_name": doc.work_order,
        "project": doc.project,
        "source_warehouse": doc.source_warehouse,
        "target_warehouse": doc.target_warehouse,
        "pick_qty": pick_qty,
        "tolerance_min": round(pick_qty * (1 - TOLERANCE_PCT), 3),
        "tolerance_max": round(pick_qty * (1 + TOLERANCE_PCT), 3),
        "already_picked_qty": round(already_qty, 3),
        "already_picked_rolls": already_rolls,
        "remarks": doc.remarks,
    }


@frappe.whitelist()
def scan_pick_order_roll(pick_order, roll_no, source_warehouse):
    """Validates a freely-scanned roll against this Assignment's rules —
    NOT a pre-assigned list (there isn't one): warehouse match against
    whatever Source Warehouse the worker currently has selected, and (for
    "To Work Order" picks) Project match against the target Work Order.
    Returns the roll's data for the frontend to add to its running list;
    nothing is written to the database at this point — that only happens
    on final submit, same as the ordinary Roll Wise Pick List flow."""
    doc = frappe.get_doc("Roll Pick Assignment", pick_order)
    _assert_assigned_to_me(doc)

    if not source_warehouse:
        frappe.throw(_("Select a Source Warehouse first"))

    roll = frappe.db.get_value(
        "Roll", roll_no,
        ["item_code", "warehouse", "batch", "project", "roll_weight", "total_qty", "stock_uom"],
        as_dict=True,
    )
    if not roll:
        frappe.throw(_("Roll not found: {0}").format(roll_no))

    if roll.warehouse and roll.warehouse != source_warehouse:
        frappe.throw(_("Roll {0} is currently in {1}, not {2}").format(
            roll_no, roll.warehouse, source_warehouse))

    if doc.pick_type == "To Work Order" and doc.work_order:
        wo_project = frappe.db.get_value("Work Order", doc.work_order, "project")
        if wo_project and roll.project and wo_project != roll.project:
            frappe.throw(_(
                "Roll {0} belongs to Project {1}, but Work Order {2} belongs to Project {3} — "
                "rolls must match the target Work Order's project"
            ).format(roll_no, roll.project, doc.work_order, wo_project))

    # Dedupe against rolls already submitted for this Assignment in a
    # prior session (same-session duplicates are checked client-side,
    # since this session's picks aren't written to the DB until submit).
    linked_pick_lists = frappe.get_all(
        "Roll Wise Pick List",
        filters={"roll_pick_assignment": pick_order, "docstatus": 1},
        pluck="name",
    )
    if linked_pick_lists and frappe.db.exists("Roll Wise Pick Item", {
        "roll_no": roll_no, "parenttype": "Roll Wise Pick List", "parent": ["in", linked_pick_lists],
    }):
        frappe.throw(_("Roll {0} has already been picked for this Order").format(roll_no))

    qty = roll.total_qty if (roll.stock_uom or "").lower() == "pcs" else roll.roll_weight
    return {
        "roll_no": roll_no,
        "item_code": roll.item_code,
        "warehouse": roll.warehouse or source_warehouse,
        "batch_no": roll.batch,
        "qty": qty,
        "uom": roll.stock_uom or "Kgs",
    }


# ── Creating an Assignment (supervisor side) ────────────────────────────────
# Deliberately plain whitelisted Python, not a Server Script — see the note
# in knit.py's create_roll_picking_entry docstring on why: Server Scripts
# in this app have a history of existing only on production and never
# being fixture-exported, breaking on any fresh bench.

@frappe.whitelist()
def search_work_orders(txt=None):
    filters = {}
    if txt:
        filters["name"] = ["like", f"%{txt}%"]
    return frappe.get_all(
        "Work Order",
        filters=filters,
        fields=["name", "production_item", "status", "project"],
        limit=50,
        order_by="modified desc",
    )


@frappe.whitelist()
def search_assignable_users(txt=None):
    filters = {"enabled": 1}
    if txt:
        filters["full_name"] = ["like", f"%{txt}%"]
    return frappe.get_all(
        "User",
        filters=filters,
        fields=["name", "full_name"],
        limit=30,
        order_by="full_name asc",
    )


@frappe.whitelist()
def create_pick_order(pick_type, source_warehouse, target_warehouse, assigned_to, pick_qty,
                       document_name=None, project=None, remarks=None):
    """Creates + submits a Roll Pick Assignment with a target pick_qty —
    no roll pre-selection. Relies on Frappe's own DocType permissions
    (System Manager / Knitting Supervisor can create — see the doctype's
    permission list) rather than a hardcoded role check here — insert()
    is NOT called with ignore_permissions, so someone without create
    rights on this doctype gets a normal Frappe permission error."""
    if not assigned_to:
        frappe.throw(_("Assigned To is required"))
    pick_qty = float(pick_qty or 0)
    if pick_qty <= 0:
        frappe.throw(_("Pick Qty must be greater than zero"))

    company = frappe.db.get_value("Warehouse", source_warehouse, "company")
    if not company:
        frappe.throw(_("Could not determine Company from Source Warehouse"))

    doc = frappe.new_doc("Roll Pick Assignment")
    doc.company = company
    doc.status = "Pending"
    doc.pick_type = pick_type
    doc.source_warehouse = source_warehouse
    doc.target_warehouse = target_warehouse
    doc.assigned_to = assigned_to
    doc.pick_qty = pick_qty

    if pick_type in ("From Work Order", "To Work Order") and document_name:
        doc.work_order = document_name
        if not project:
            project = frappe.db.get_value("Work Order", document_name, "project")
    if project:
        doc.project = project
    if remarks:
        doc.remarks = remarks

    doc.insert()
    doc.submit()
    frappe.db.commit()
    return {"success": True, "name": doc.name}
