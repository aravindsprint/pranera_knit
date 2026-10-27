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
    for r in rows:
        r["created_by_name"] = full_names.get(r.created_by, r.created_by)
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
