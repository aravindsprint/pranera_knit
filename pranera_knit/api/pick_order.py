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

Validations that run on every scan:
  1. Project match (pick_type == "To Work Order" only) — the roll's
     Project must match the target Work Order's Project, so material
     doesn't get misrouted into an unrelated project's job.
  2. Batch match (whenever the Assignment is tied to a Work Order) — if
     the supervisor named specific batches (batch_items rows — optional
     for "To Work Order"), the roll's batch must be one of those. Other-
     wise it must be one this Work Order actually produced, per the
     is_finished_item rows of its own submitted Stock Entry (Manufacture)
     — not just any batch of the same item code sitting in the warehouse.
  3. No duplicate scan — a roll can't be scanned twice, either within
     this in-progress session or against a prior submitted session for
     this same Assignment.

There is deliberately NO check that Roll.warehouse matches the selected
Source Warehouse — Roll.warehouse is only ever pushed forward by
roll_wise_pick_list_events.py, scoped to a different app's Stock Entries,
so it's frequently stale for a roll's actual current location and isn't a
trustworthy gate. The worker's selected Source Warehouse is trusted and
is exactly what gets recorded against the scan (see scan_pick_order_roll).

The +/-3% tolerance itself is enforced authoritatively server-side, in
knit.create_roll_picking_entry (not here) — that's the single point where
an Assignment's fulfillment actually becomes a real Stock Entry, so
that's where the final check has to live; a client-side-only check could
be bypassed by calling the API directly.

── Session persistence ──────────────────────────────────────────────────
Every scan is written immediately to the Assignment's own scanned_rolls
child table (see patches/v1_0/add_pick_order_persistence.py), not just
held in the browser's Pinia store. That means a worker can close the app,
lose signal, or come back the next shift, reopen the same Assignment, and
see exactly what they'd already scanned — nothing is lost until the final
submit_pick_order() call, which is also the only place scanned_rolls gets
cleared. execution_source_warehouse / execution_target_warehouse are the
worker's current, persisted choice for this session — they default to the
Assignment's own source_warehouse / target_warehouse but can be changed
independently (e.g. rolls turned out to be sitting somewhere else, or the
material needs to land somewhere other than originally planned) without
touching the original Assignment fields.
"""
import frappe
from frappe import _
from frappe.utils import now_datetime

from pranera_knit.api.knit import create_roll_picking_entry

TOLERANCE_PCT = 0.03


def _assert_assigned_to_me(doc):
    if doc.assigned_to != frappe.session.user:
        frappe.throw(_("This Pick Order is not assigned to you"), frappe.PermissionError)


def _resolve_document_name(doc):
    """Which linked document a pick_type points at — must mirror the
    pick_type branches in knit.create_roll_picking_entry() exactly, since
    that value is what gets stamped onto the resulting Stock Entry
    (se.work_order / se.subcontracting_order / etc). Falls back to
    work_order for any pick_type not listed here (From Work Order,
    Manual Roll Pick), matching the pre-existing default."""
    if doc.pick_type == "To Sales Order":
        return doc.sales_order
    if doc.pick_type in ("To Subcontracting Order", "From Subcontracting Order"):
        return doc.subcontracting_order
    return doc.work_order


def _valid_batches_for_work_order(work_order):
    """Batches of the finished good actually produced against this Work
    Order — read from its submitted Stock Entry (Manufacture) rows where
    is_finished_item=1, NOT from Roll.work_order. Roll.work_order is set
    once at roll-creation time and can drift; the Stock Entry (Manufacture)
    is the authoritative record of which batches this Work Order actually
    output (same is_finished_item convention already relied on for batch
    naming — see the dyeing/finishing batch tracing work)."""
    se_names = frappe.get_all(
        "Stock Entry",
        filters={"work_order": work_order, "stock_entry_type": "Manufacture", "docstatus": 1},
        pluck="name",
    )
    if not se_names:
        return set()
    batches = frappe.get_all(
        "Stock Entry Detail",
        filters={
            "parenttype": "Stock Entry",
            "parent": ["in", se_names],
            "is_finished_item": 1,
        },
        pluck="batch_no",
    )
    return {b for b in batches if b}


def _already_picked_qty(assignment_name):
    """Sum of roll qty already submitted against this Assignment in prior
    sessions (each a separate Roll Wise Pick List + Stock Entry) — lets a
    worker who partially fulfilled it earlier resume and see progress.
    (In normal operation there's only ever one submitted pick list per
    Assignment, since submit_pick_order marks it Completed — this mainly
    covers an amended/re-submitted Assignment.)"""
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
    Completed/Cancelled). Used by the "My Pick Orders" list page — includes
    each Assignment's in-progress scan progress (picked_qty / picked_rolls),
    since a Pending/In Progress Assignment's only progress lives in its
    persisted-but-unsubmitted scanned_rolls (once submitted, status flips to
    Completed and it drops out of this list entirely)."""
    assignments = frappe.get_all(
        "Roll Pick Assignment",
        filters={
            "assigned_to": frappe.session.user,
            "docstatus": 1,
            "status": ["in", ["Pending", "In Progress"]],
        },
        fields=[
            "name", "posting_date", "pick_type", "work_order", "project",
            "sales_order", "manufactured_qty",
            "source_warehouse", "target_warehouse", "pick_qty", "status",
        ],
        order_by="posting_date desc, creation desc",
    )
    if not assignments:
        return assignments

    names = [a.name for a in assignments]
    scan_rows = frappe.get_all(
        "Roll Pick Assignment Scan",
        filters={"parenttype": "Roll Pick Assignment", "parent": ["in", names]},
        fields=["parent", "qty"],
    )
    progress = {}
    for row in scan_rows:
        p = progress.setdefault(row.parent, {"qty": 0.0, "rolls": 0})
        p["qty"] += float(row.qty or 0)
        p["rolls"] += 1

    for a in assignments:
        p = progress.get(a.name, {"qty": 0.0, "rolls": 0})
        a["picked_qty"] = round(p["qty"], 3)
        a["picked_rolls"] = p["rolls"]

    return assignments


@frappe.whitelist()
def get_pick_order_detail(name):
    """Full detail for one Assignment: the target (pick_qty + tolerance
    band), whatever's already been picked in prior submitted sessions,
    and whatever's currently scanned-but-not-yet-submitted (persisted, so
    a worker resuming mid-way sees exactly where they left off)."""
    doc = frappe.get_doc("Roll Pick Assignment", name)
    _assert_assigned_to_me(doc)

    pick_qty = float(doc.pick_qty or 0)
    already_qty, already_rolls = _already_picked_qty(name)

    scanned_rolls = [
        {
            "roll_no": r.roll_no,
            "item_code": r.item_code,
            "warehouse": r.warehouse,
            "batch_no": r.batch_no,
            "qty": r.qty,
            "uom": r.uom,
        }
        for r in (doc.scanned_rolls or [])
    ]

    return {
        "name": doc.name,
        "posting_date": doc.posting_date,
        "status": doc.status,
        "pick_type": doc.pick_type,
        "document_name": _resolve_document_name(doc),
        "sales_order": doc.sales_order,
        "purchase_order": doc.purchase_order,
        "subcontracting_order": doc.subcontracting_order,
        "manufactured_qty": doc.manufactured_qty,
        "project": doc.project,
        "source_warehouse": doc.source_warehouse,
        "target_warehouse": doc.target_warehouse,
        "execution_source_warehouse": doc.execution_source_warehouse or doc.source_warehouse,
        "execution_target_warehouse": doc.execution_target_warehouse or doc.target_warehouse,
        "pick_qty": pick_qty,
        "tolerance_min": round(pick_qty * (1 - TOLERANCE_PCT), 3),
        "tolerance_max": round(pick_qty * (1 + TOLERANCE_PCT), 3),
        "already_picked_qty": round(already_qty, 3),
        "already_picked_rolls": already_rolls,
        "scanned_rolls": scanned_rolls,
        "batch_items": [
            {"batch": r.batch, "qty": r.qty} for r in (doc.batch_items or [])
        ],
        "remarks": doc.remarks,
    }


@frappe.whitelist()
def update_pick_order_execution(pick_order, source_warehouse=None, target_warehouse=None):
    """Persists the worker's current Source/Target Warehouse choice for
    this execution session, independent of scanning. Call this whenever
    either dropdown changes so a resumed session (different device, next
    shift, after a refresh) shows the same choice rather than snapping
    back to the Assignment's original warehouses.

    Changing the Source Warehouse mid-session also rewrites the
    `warehouse` field on every roll already scanned this session
    (doc.scanned_rolls) to match — those rows were recorded against
    whichever Source Warehouse was selected at the moment they were
    scanned, so leaving them on a stale value after the worker corrects
    the warehouse would silently misstate where that material actually
    came from. This mirrors scan_pick_order_roll, which always stamps
    the *currently selected* Source Warehouse onto a scan rather than
    trusting Roll.warehouse (see the module docstring)."""
    doc = frappe.get_doc("Roll Pick Assignment", pick_order)
    _assert_assigned_to_me(doc)

    warehouse_changed = source_warehouse is not None and source_warehouse != doc.execution_source_warehouse

    if warehouse_changed:
        # Child-table rows are involved, so this needs a real save (not
        # db_set, which only ever touches the parent's own column).
        doc.execution_source_warehouse = source_warehouse
        for row in (doc.scanned_rolls or []):
            row.warehouse = source_warehouse
        if target_warehouse is not None:
            doc.execution_target_warehouse = target_warehouse
        doc.save(ignore_permissions=True)
    else:
        # No scanned rolls to touch — keep the previous lightweight,
        # non-modified-bumping writes for a plain warehouse selection.
        if source_warehouse is not None:
            doc.db_set("execution_source_warehouse", source_warehouse, update_modified=False)
        if target_warehouse is not None:
            doc.db_set("execution_target_warehouse", target_warehouse, update_modified=False)
    frappe.db.commit()
    return {"success": True}


@frappe.whitelist()
def scan_pick_order_roll(pick_order, roll_no, source_warehouse):
    """Validates a freely-scanned roll against this Assignment's rules —
    NOT a pre-assigned list (there isn't one): Project match against the
    target Work Order (for "To Work Order" picks) and batch match. The
    roll's own warehouse field is not checked (see module docstring) —
    the scan is simply recorded against whichever Source Warehouse the
    worker currently has selected.

    On success, the roll is written immediately to the Assignment's
    scanned_rolls child table — this is the persistence layer: nothing
    lives only in the browser anymore, so a worker who closes the app
    before submitting can reopen the same Assignment and pick up exactly
    where they left off."""
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

    if doc.pick_type == "To Work Order" and doc.work_order:
        wo_project = frappe.db.get_value("Work Order", doc.work_order, "project")
        if wo_project and roll.project and wo_project != roll.project:
            frappe.throw(_(
                "Roll {0} belongs to Project {1}, but Work Order {2} belongs to Project {3} — "
                "rolls must match the target Work Order's project"
            ).format(roll_no, roll.project, doc.work_order, wo_project))

    # Batch match. If this Assignment has explicit batch_items rows —
    # "From Batch" / "To Sales Order" picks always have these (and have no
    # work_order), and a "To Work Order" pick may optionally be restricted
    # to specific batches this way too — the roll's batch must be one of
    # those named batches. This is checked first and independently of
    # work_order, since batch_items is the tighter, explicitly-supervisor-
    # set constraint whenever it's present.
    #
    # Only when there are no batch_items at all and this is a Work Order
    # pick do we fall back to the broader check: the roll's batch must be
    # one this Work Order actually produced, per its submitted Stock Entry
    # (Manufacture) finished-item rows — not just any batch of the same
    # item code sitting in the warehouse.
    if doc.batch_items:
        allowed_batches = {r.batch for r in doc.batch_items if r.batch}
        if not roll.batch or roll.batch not in allowed_batches:
            frappe.throw(_(
                "Roll {0}'s batch {1} is not one of the batches specified for this "
                "Pick Order ({2})"
            ).format(roll_no, roll.batch or _("(no batch)"), ", ".join(sorted(allowed_batches))))
    elif doc.work_order:
        valid_batches = _valid_batches_for_work_order(doc.work_order)
        if not valid_batches:
            frappe.throw(_(
                "No submitted Stock Entry (Manufacture) finished-goods batches found for "
                "Work Order {0} — cannot verify roll batches against it"
            ).format(doc.work_order))
        if not roll.batch or roll.batch not in valid_batches:
            frappe.throw(_(
                "Roll {0}'s batch {1} does not belong to Work Order {2}'s manufactured "
                "finished goods"
            ).format(roll_no, roll.batch or _("(no batch)"), doc.work_order))

    # Dedupe against rolls already submitted for this Assignment in a
    # prior completed session...
    linked_pick_lists = frappe.get_all(
        "Roll Wise Pick List",
        filters={"roll_pick_assignment": pick_order, "docstatus": 1},
        pluck="name",
    )
    if linked_pick_lists and frappe.db.exists("Roll Wise Pick Item", {
        "roll_no": roll_no, "parenttype": "Roll Wise Pick List", "parent": ["in", linked_pick_lists],
    }):
        frappe.throw(_("Roll {0} has already been picked for this Order").format(roll_no))

    # ...and against rolls already scanned (persisted) THIS in-progress
    # session, whether from this device or an earlier one.
    if any(r.roll_no == roll_no for r in (doc.scanned_rolls or [])):
        frappe.throw(_("Roll {0} has already been scanned for this Order").format(roll_no))

    # Roll.warehouse is NOT a reliable "where is this roll right now" signal —
    # it's only ever pushed forward by roll_wise_pick_list_events.py, scoped
    # strictly to Stock Entries created via the (separate) Roll Wise Pick
    # List app, so it commonly reflects some unrelated past movement rather
    # than this pick session. The warehouse recorded against this scan must
    # be whichever Source Warehouse the worker actually has selected right
    # now — that's what they physically walked to and scanned from.
    qty = roll.total_qty if (roll.stock_uom or "").lower() == "pcs" else roll.roll_weight
    result = {
        "roll_no": roll_no,
        "item_code": roll.item_code,
        "warehouse": source_warehouse,
        "batch_no": roll.batch,
        "qty": qty,
        "uom": roll.stock_uom or "Kgs",
    }

    doc.append("scanned_rolls", {
        "roll_no": result["roll_no"],
        "item_code": result["item_code"],
        "warehouse": result["warehouse"],
        "batch_no": result["batch_no"],
        "qty": result["qty"],
        "uom": result["uom"],
        "scanned_by": frappe.session.user,
        "scanned_at": now_datetime(),
    })
    doc.execution_source_warehouse = source_warehouse
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return result


@frappe.whitelist()
def remove_scanned_roll(pick_order, roll_no):
    """Removes a persisted (not-yet-submitted) roll from this Assignment's
    scan session — the server-side counterpart to the execution page's
    per-row remove button."""
    doc = frappe.get_doc("Roll Pick Assignment", pick_order)
    _assert_assigned_to_me(doc)

    before = len(doc.scanned_rolls or [])
    doc.set("scanned_rolls", [r for r in (doc.scanned_rolls or []) if r.roll_no != roll_no])
    if len(doc.scanned_rolls) == before:
        frappe.throw(_("Roll {0} was not found in this session").format(roll_no))

    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {"success": True}


@frappe.whitelist()
def submit_pick_order(pick_order, posting_date):
    """Final submission for a Pick Order Execution session. Builds the
    picked-rolls list from what's persisted server-side (scanned_rolls) —
    NOT from anything the client passes in — so the source of truth for
    what actually gets moved is always the Assignment's own saved scan
    history, not a client-supplied payload. Delegates the actual Roll
    Wise Pick List + Stock Entry creation (and the authoritative +/-3%
    tolerance check) to knit.create_roll_picking_entry, then clears
    scanned_rolls now that they've become a real, submitted pick list —
    this is the one and only pick entry this Assignment will ever
    produce."""
    doc = frappe.get_doc("Roll Pick Assignment", pick_order)
    _assert_assigned_to_me(doc)

    if not doc.scanned_rolls:
        frappe.throw(_("Scan at least one roll before submitting"))

    source_warehouse = doc.execution_source_warehouse or doc.source_warehouse
    target_warehouse = doc.execution_target_warehouse or doc.target_warehouse

    rolls = [
        {
            "roll_no": r.roll_no,
            "item_code": r.item_code,
            "batch_no": r.batch_no,
            "qty": r.qty,
            "uom": r.uom,
        }
        for r in doc.scanned_rolls
    ]

    result = create_roll_picking_entry(
        pick_type=doc.pick_type,
        document_name=_resolve_document_name(doc),
        source_warehouse=source_warehouse,
        target_warehouse=target_warehouse,
        posting_date=posting_date,
        project=doc.project,
        rolls=rolls,
        roll_pick_assignment=pick_order,
    )

    # Now that these rolls are a real submitted pick list, clear the
    # in-progress scan session.
    doc.reload()
    doc.set("scanned_rolls", [])
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return result


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
def search_sales_orders(txt=None):
    filters = {"docstatus": 1}
    if txt:
        filters["name"] = ["like", f"%{txt}%"]
    return frappe.get_all(
        "Sales Order",
        filters=filters,
        fields=["name", "customer", "status"],
        limit=50,
        order_by="modified desc",
    )


@frappe.whitelist()
def search_batches(txt=None):
    filters = {}
    if txt:
        filters["name"] = ["like", f"%{txt}%"]
    return frappe.get_all(
        "Batch",
        filters=filters,
        fields=["name", "item", "batch_qty"],
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
def create_pick_order(pick_type, source_warehouse, target_warehouse, assigned_to, pick_qty=None,
                       document_name=None, project=None, remarks=None, sales_order=None,
                       batch_items=None, purchase_order=None, subcontracting_order=None):
    """Creates + submits a Roll Pick Assignment.

    For "From Work Order" / "Manual Roll Pick", pick_qty is the
    supervisor-entered target weight, as before.

    For "From Batch" / "To Sales Order", pick_qty is NOT taken from the
    caller — it's derived from the batch_items rows (sum of qty), mirroring
    Roll Pick Assignment.set_pick_qty_from_batch_items() which recomputes
    the same total server-side on save. "To Sales Order" additionally
    requires a Sales Order to link.

    "To Work Order" is a middle case: batch_items is OPTIONAL. Leave it
    empty and this behaves exactly like "From Work Order" — supervisor
    sets a free-scan target weight, worker can scan any roll belonging to
    the Work Order's own manufactured finished goods. Add one or more
    Batch/Qty rows and the pick gets restricted to exactly those
    batches — pick_qty is then derived from their sum (same as "From
    Batch"), and scan_pick_order_roll() enforces the roll's batch is one
    of the named ones instead of just "any batch this Work Order
    produced". One row covers the single-batch case; multiple rows cover
    the multi-batch case — same child table either way.
    """
    if not assigned_to:
        frappe.throw(_("Assigned To is required"))

    batch_items = frappe.parse_json(batch_items) if isinstance(batch_items, str) else (batch_items or [])
    mandatory_batch_items_types = ("From Batch", "To Sales Order")
    optional_batch_items_types = ("To Work Order",)
    uses_batch_items = pick_type in mandatory_batch_items_types or (
        pick_type in optional_batch_items_types and bool(batch_items)
    )

    if uses_batch_items:
        if pick_type in mandatory_batch_items_types and not batch_items:
            frappe.throw(_("Add at least one Batch / Qty row"))
        for row in batch_items:
            if not row.get("batch") or float(row.get("qty") or 0) <= 0:
                frappe.throw(_("Each row needs a Batch and a Qty greater than zero"))
        pick_qty = sum(float(row.get("qty") or 0) for row in batch_items)
    else:
        pick_qty = float(pick_qty or 0)
        if pick_qty <= 0:
            frappe.throw(_("Pick Qty must be greater than zero"))

    if pick_type == "To Sales Order" and not sales_order:
        frappe.throw(_("Sales Order is required for a 'To Sales Order' pick"))
    if pick_type == "To Subcontracting Order" and not subcontracting_order:
        frappe.throw(_("Subcontracting Order is required for a 'To Subcontracting Order' pick"))

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
    if pick_type == "To Sales Order" and sales_order:
        doc.sales_order = sales_order
    if pick_type == "To Subcontracting Order" and subcontracting_order:
        doc.subcontracting_order = subcontracting_order
        if purchase_order:
            doc.purchase_order = purchase_order
    if uses_batch_items:
        for row in batch_items:
            doc.append("batch_items", {"batch": row.get("batch"), "qty": row.get("qty")})
    if project:
        doc.project = project
    if remarks:
        doc.remarks = remarks

    doc.insert()
    doc.submit()
    frappe.db.commit()
    return {"success": True, "name": doc.name}
