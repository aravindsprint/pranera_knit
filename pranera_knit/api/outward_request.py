"""
pranera_knit/api/outward_request.py
Whitelisted methods behind the knit-app "Outward Request" page.

Item fetching (get_outward_request_items):

  Purchase Order → every SUBMITTED, non-return Subcontracting Receipt that
  has a row against this PO (Subcontracting Receipt Item.purchase_order),
  then each receipt's "Raw Materials Supplied" table (Subcontracting
  Receipt Supplied Item):
      item_code ← rm_item_code
      stock_uom ← stock_uom
      qty       ← consumed_qty (required_qty if consumed is empty)
      batch     ← batch_no — but on this site batch_no is normally blank
                  and the real batch lives in the row's Serial and Batch
                  Bundle, so the bundle's entries are used whenever one is
                  set (one output row per bundle batch, qty = |entry qty|).
  A PO can have several receipts, and one receipt repeats the same raw
  material once per finished item, so rows are merged on
  (item_code, batch, stock_uom) — in first-seen order.

  Work Order → its "Required Items" table (Work Order Item):
      item_code, stock_uom, qty ← required_qty. Work Order Item has no
      batch, so batch is left blank for the user to fill if needed.

Status tracking for saved requests lives in outward_request_events.py.
"""
import frappe
from frappe import _
from frappe.utils import flt, today

from pranera_knit.vehicle_gate_entry_events import vehicles_for_outward_requests

LIST_FIELDS = [
    "name", "date", "to_building", "work_order", "purchase_order",
    "created_by", "created_on", "status", "request_status", "modified",
]


# ── Fetch items ───────────────────────────────────────────────────────────

@frappe.whitelist()
def get_outward_request_items(work_order=None, purchase_order=None):
    if bool(work_order) == bool(purchase_order):
        frappe.throw(_("Pass either a Work Order or a Purchase Order"))
    if purchase_order:
        return _items_from_purchase_order(purchase_order)
    return _items_from_work_order(work_order)


def _items_from_purchase_order(purchase_order):
    if not frappe.db.exists("Purchase Order", purchase_order):
        frappe.throw(_("Purchase Order {0} not found").format(purchase_order))

    receipt_names = frappe.get_all(
        "Subcontracting Receipt Item",
        filters={"purchase_order": purchase_order, "docstatus": 1},
        pluck="parent", distinct=True,
    )
    receipts = frappe.get_all(
        "Subcontracting Receipt",
        filters={"name": ["in", receipt_names or [""]], "docstatus": 1, "is_return": 0},
        pluck="name", order_by="posting_date asc, creation asc",
    )
    if not receipts:
        frappe.throw(_("No submitted Subcontracting Receipt found for Purchase Order {0}")
                     .format(purchase_order))

    supplied = frappe.get_all(
        "Subcontracting Receipt Supplied Item",
        filters={"parenttype": "Subcontracting Receipt", "parent": ["in", receipts]},
        fields=["parent", "idx", "rm_item_code", "batch_no", "serial_and_batch_bundle",
                "consumed_qty", "required_qty", "stock_uom"],
    )
    order = {name: i for i, name in enumerate(receipts)}
    supplied.sort(key=lambda r: (order[r.parent], r.idx))

    bundle_names = [r.serial_and_batch_bundle for r in supplied if r.serial_and_batch_bundle]
    bundle_entries = {}
    if bundle_names:
        for e in frappe.get_all(
            "Serial and Batch Entry",
            filters={"parent": ["in", bundle_names]},
            fields=["parent", "batch_no", "qty"], order_by="idx asc",
        ):
            if e.batch_no:
                bundle_entries.setdefault(e.parent, []).append(e)

    merged = {}
    for r in supplied:
        entries = bundle_entries.get(r.serial_and_batch_bundle)
        if entries:
            parts = [(e.batch_no, abs(flt(e.qty))) for e in entries]
        else:
            parts = [(r.batch_no or "", flt(r.consumed_qty) or flt(r.required_qty))]
        for batch, qty in parts:
            _merge(merged, r.rm_item_code, batch, r.stock_uom, qty)

    return {"source": "Purchase Order", "receipts": receipts, "items": _rows(merged)}


def _items_from_work_order(work_order):
    wo = frappe.db.get_value("Work Order", work_order, ["name", "docstatus"], as_dict=True)
    if not wo:
        frappe.throw(_("Work Order {0} not found").format(work_order))
    if wo.docstatus == 2:
        frappe.throw(_("Work Order {0} is cancelled").format(work_order))

    required = frappe.get_all(
        "Work Order Item",
        filters={"parenttype": "Work Order", "parent": work_order},
        fields=["item_code", "stock_uom", "required_qty"],
        order_by="idx asc",
    )
    if not required:
        frappe.throw(_("Work Order {0} has no Required Items").format(work_order))

    merged = {}
    for r in required:
        _merge(merged, r.item_code, "", r.stock_uom, flt(r.required_qty))
    return {"source": "Work Order", "receipts": [], "items": _rows(merged)}


def _merge(merged, item_code, batch, stock_uom, qty):
    key = (item_code, batch or "", stock_uom or "")
    if key in merged:
        merged[key]["qty"] += qty
    else:
        merged[key] = {"item_code": item_code, "batch": batch or "", "stock_uom": stock_uom or "", "qty": qty}


def _rows(merged):
    rows = []
    for r in merged.values():
        r["qty"] = round(r["qty"], 3)
        if r["qty"] > 0:
            rows.append(r)
    return rows


# ── Create / update / read ────────────────────────────────────────────────

@frappe.whitelist()
def save_outward_request(date=None, to_building=None, work_order=None, purchase_order=None,
                         items=None, name=None):
    """Create (no name) or update (name, only while Pending) a request.
    validate_outward_request in outward_request_events.py enforces the
    rules either way, so this stays a thin wrapper."""
    items = frappe.parse_json(items) if isinstance(items, str) else (items or [])

    doc = frappe.get_doc("Outward Request", name) if name else frappe.new_doc("Outward Request")
    doc.date = date or today()
    doc.to_building = to_building
    doc.work_order = work_order or None
    doc.purchase_order = purchase_order or None
    doc.set("items", [])
    for r in items:
        doc.append("items", {
            "item_code": r.get("item_code"),
            "batch": r.get("batch") or None,
            "qty": flt(r.get("qty")),
            "stock_uom": r.get("stock_uom") or None,
        })
    doc.save()
    frappe.db.commit()
    return get_outward_request(doc.name)


@frappe.whitelist()
def get_outward_request(name):
    doc = frappe.get_doc("Outward Request", name)
    doc.check_permission("read")
    out = doc.as_dict()
    out["created_by_name"] = frappe.utils.get_fullname(doc.created_by) if doc.created_by else ""
    out["roll_pick_assignments"] = frappe.get_all(
        "Roll Pick Assignment",
        filters={"outward_request": name, "docstatus": ["<", 2]},
        fields=["name", "status", "assigned_to", "docstatus"],
        order_by="creation asc",
    )
    out["vehicle_gate_entries"] = vehicles_for_outward_requests([name]).get(name, [])
    return out


@frappe.whitelist()
def list_outward_requests(request_status=None, txt=None, limit=50):
    filters = {}
    if request_status:
        filters["request_status"] = request_status
    or_filters = None
    if txt:
        like = f"%{txt}%"
        or_filters = {
            "name": ["like", like], "to_building": ["like", like],
            "work_order": ["like", like], "purchase_order": ["like", like],
        }
    rows = frappe.get_list(
        "Outward Request", filters=filters, or_filters=or_filters,
        fields=LIST_FIELDS, order_by="creation desc", limit_page_length=int(limit or 50),
    )
    names = {r.created_by for r in rows if r.created_by}
    full_names = {
        u.name: u.full_name
        for u in frappe.get_all("User", filters={"name": ["in", list(names) or [""]]},
                                fields=["name", "full_name"])
    }
    vehicles = vehicles_for_outward_requests([r.name for r in rows])
    for r in rows:
        r["created_by_name"] = full_names.get(r.created_by, r.created_by)
        r["vehicle_nos"] = [v.vehicle_no for v in vehicles.get(r.name, [])]
    return rows


# ── Lookups for the form ──────────────────────────────────────────────────

@frappe.whitelist()
def get_buildings():
    return frappe.get_all(
        "Building", filters={"disabled": 0},
        fields=["name", "building_name", "building_code", "city"],
        order_by="building_name asc", limit_page_length=0,
    )


@frappe.whitelist()
def search_work_orders(txt=None):
    filters = {"docstatus": 1}
    if txt:
        filters["name"] = ["like", f"%{txt}%"]
    return frappe.get_all(
        "Work Order", filters=filters,
        fields=["name", "production_item", "status"],
        limit=30, order_by="modified desc",
    )


@frappe.whitelist()
def search_purchase_orders(txt=None):
    """Only subcontracted POs — those are the only ones that can have a
    Subcontracting Receipt to fetch Raw Materials Supplied from."""
    filters = {"docstatus": 1, "is_subcontracted": 1}
    if txt:
        filters["name"] = ["like", f"%{txt}%"]
    return frappe.get_all(
        "Purchase Order", filters=filters,
        fields=["name", "supplier_name", "status"],
        limit=30, order_by="modified desc",
    )


# ── Roll Pick Assignment from a request ───────────────────────────────────
#
# Work Order request → "To Work Order". When rows carry batches, those
#   become batch_items (same as a PO request below): per-UOM ±3% targets,
#   so Pcs collars/cuffs are picked and checked too, and scans are limited
#   to those batches; rows without a batch are reported as `excluded`.
#   Only when NO row has a batch is it a free scan: pick_qty
#   = total Kgs on the request (editable). Scans are limited to the
#   request's item codes (see _record_scan in pick_order.py) instead of the
#   usual "batches this WO manufactured" rule, since a request moves the
#   WO's REQUIRED items. Free-scan picks are checked in a single Kgs bucket
#   (get_pick_qty_targets_by_uom), so non-Kgs rows don't count toward it.
#
# Purchase Order request → "To Subcontracting Order", linked to the PO's
#   Subcontracting Order (target warehouse defaults to its job-worker
#   warehouse). Rows WITH a batch become batch_items — per-UOM ±3% targets
#   and scans restricted to those batches. Rows without a batch (labels,
#   buttons, cartons…) aren't rolls and can't be scanned, so they're left
#   out and reported back as `excluded`.

def _assignment_plan(doc):
    plan = {"outward_request": doc.name, "excluded": [], "batch_items": [], "uom_totals": {}}
    for r in doc.items:
        uom = r.stock_uom or "Kgs"
        plan["uom_totals"][uom] = round(plan["uom_totals"].get(uom, 0.0) + flt(r.qty), 3)

    # Rows WITH a batch become planned batches (one per batch, qty summed);
    # rows without one can't be roll-picked and are reported as excluded.
    merged = {}
    excluded = []
    for r in doc.items:
        if not r.batch:
            excluded.append({"item_code": r.item_code, "qty": flt(r.qty), "stock_uom": r.stock_uom})
            continue
        if r.batch in merged:
            merged[r.batch]["qty"] += flt(r.qty)
        else:
            merged[r.batch] = {"batch": r.batch, "item_code": r.item_code,
                               "qty": flt(r.qty), "stock_uom": r.stock_uom}

    if doc.work_order:
        wo = frappe.db.get_value("Work Order", doc.work_order,
                                 ["project", "wip_warehouse", "source_warehouse"], as_dict=True) or {}
        plan.update({
            "pick_type": "To Work Order",
            "document_name": doc.work_order,
            "project": wo.get("project"),
            "default_source_warehouse": wo.get("source_warehouse"),
            "default_target_warehouse": wo.get("wip_warehouse"),
            "subcontracting_orders": [],
        })
        if merged:
            # Batched rows (Kgs fabric AND Pcs collars/cuffs) become the
            # Assignment's Batch Items: each UOM gets its own ±3% target and
            # scans are restricted to these batches.
            plan.update({
                "batch_items": list(merged.values()),
                "pick_qty": round(sum(b["qty"] for b in merged.values()), 3),
                "excluded": excluded,
                "non_kgs": {},
            })
        else:
            # No batches at all: free scan against a single kg target.
            plan.update({
                "pick_qty": plan["uom_totals"].get("Kgs", 0.0),
                "non_kgs": {u: q for u, q in plan["uom_totals"].items() if u != "Kgs"},
            })
        return plan

    sco = frappe.get_all(
        "Subcontracting Order",
        filters={"purchase_order": doc.purchase_order, "docstatus": 1},
        fields=["name", "supplier_warehouse", "status"],
        order_by="creation desc",
    )
    plan["excluded"] = excluded
    plan.update({
        "pick_type": "To Subcontracting Order",
        "document_name": doc.purchase_order,
        "project": frappe.db.get_value("Purchase Order", doc.purchase_order, "project"),
        "batch_items": list(merged.values()),
        "pick_qty": round(sum(b["qty"] for b in merged.values()), 3),
        "subcontracting_orders": sco,
        "default_source_warehouse": None,
        "default_target_warehouse": sco[0].supplier_warehouse if sco else None,
        "non_kgs": {},
    })
    return plan


@frappe.whitelist()
def get_pick_assignment_defaults(name):
    doc = frappe.get_doc("Outward Request", name)
    doc.check_permission("read")
    return _assignment_plan(doc)


@frappe.whitelist()
def create_roll_pick_assignment(name, source_warehouse, target_warehouse, assigned_to,
                                subcontracting_order=None, pick_qty=None, remarks=None,
                                roll_source=None):
    """Creates + submits a Roll Pick Assignment for this request via the
    existing pick_order.create_pick_order (same validations, same status
    flow). Batch rows and pick type come from the saved request, not the
    caller — only warehouses, assignee, the WO free-scan target and the
    PO's Subcontracting Order are chosen on the form."""
    from pranera_knit.api.pick_order import create_pick_order

    doc = frappe.get_doc("Outward Request", name)
    doc.check_permission("write")
    if doc.request_status != "Pending":
        frappe.throw(_("Outward Request {0} is already {1}").format(name, doc.request_status))

    plan = _assignment_plan(doc)
    if not source_warehouse or not target_warehouse:
        frappe.throw(_("Source and Target Warehouse are required"))

    args = dict(
        pick_type=plan["pick_type"],
        source_warehouse=source_warehouse,
        target_warehouse=target_warehouse,
        assigned_to=assigned_to,
        project=plan.get("project"),
        remarks=remarks or _("Outward Request {0} → {1}").format(name, doc.to_building),
        roll_source=roll_source,
        outward_request=name,
    )

    if plan["pick_type"] == "To Work Order" and plan["batch_items"]:
        args.update(
            document_name=plan["document_name"],
            batch_items=[{"batch": b["batch"], "qty": b["qty"]} for b in plan["batch_items"]],
        )
    elif plan["pick_type"] == "To Work Order":
        target = flt(pick_qty) or plan["pick_qty"]
        if target <= 0:
            frappe.throw(_("Enter the Pick Qty (kg) — this request has no Kgs items to default from"))
        args.update(document_name=plan["document_name"], pick_qty=target)
    else:
        valid = {s.name for s in plan["subcontracting_orders"]}
        if not valid:
            frappe.throw(_("No submitted Subcontracting Order found for Purchase Order {0}")
                         .format(doc.purchase_order))
        subcontracting_order = subcontracting_order or plan["subcontracting_orders"][0].name
        if subcontracting_order not in valid:
            frappe.throw(_("Subcontracting Order {0} is not linked to Purchase Order {1}")
                         .format(subcontracting_order, doc.purchase_order))
        if not plan["batch_items"]:
            frappe.throw(_("None of this request's items has a batch, so there is nothing to roll-pick"))
        args.update(
            purchase_order=doc.purchase_order,
            subcontracting_order=subcontracting_order,
            batch_items=[{"batch": b["batch"], "qty": b["qty"]} for b in plan["batch_items"]],
        )

    result = create_pick_order(**args)
    return {"name": result.get("name"), "outward_request": get_outward_request(name)}


@frappe.whitelist()
def search_batches(item_code, txt=None):
    """Batch dropdown on an Outward Request item row: enabled batches of
    this item only, in-stock first (batch_qty is ERPNext's maintained total
    across warehouses), then newest."""
    if not item_code:
        return []
    frappe.has_permission("Batch", "read", throw=True)
    # Plain SQL: Frappe v15's get_all rejects expressions such as
    # "(batch_qty > 0) desc" in order_by ("Illegal SQL Query"), which made
    # the dropdown come back empty.
    conditions, values = ["item = %(item)s", "disabled = 0"], {"item": item_code}
    if txt:
        conditions.append("name like %(txt)s")
        values["txt"] = f"%{txt}%"
    return frappe.db.sql(
        f"""select name, batch_qty, stock_uom, expiry_date
        from `tabBatch`
        where {" and ".join(conditions)}
        order by (batch_qty > 0) desc, creation desc
        limit 30""",
        values, as_dict=True,
    )
