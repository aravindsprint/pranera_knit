"""
pranera_knit/patches/v1_15/add_outward_request_from_warehouse.py

Outward Request — "From" building and a warehouse per row.

  * Outward Request.from_building  (Link Building, "From") right after Date,
    next to "To". The Knit App page pre-fills it with NAP
    (api/outward_request.py DEFAULT_FROM_BUILDING).
  * Outward Request Item.warehouse (Link Warehouse) right after Batch — the
    batch dropdown picks a (batch, warehouse) pair, and reservations are
    counted per pair.

pranera_roll ships the same fields (its patches/v1_4); whichever runs first
adds them and the other is a no-op.
"""
import frappe

# (field spec, insert after)
NEW_REQUEST_FIELDS = [
    ({"fieldname": "from_building", "label": "From", "fieldtype": "Link", "options": "Building",
      "in_list_view": 1, "in_standard_filter": 1,
      "description": "Building the material leaves from — the Roll App only lists "
                     "batch stock in this building's warehouses"}, "date"),
]
NEW_ITEM_FIELDS = [
    ({"fieldname": "warehouse", "label": "Warehouse", "fieldtype": "Link", "options": "Warehouse",
      "in_list_view": 1, "columns": 2,
      "description": "Where this row's batch qty is taken from — reserved against "
                     "that warehouse's stock until the request is Completed"}, "batch"),
]
# Grid widths once Warehouse joins the list view (total 10).
ITEM_COLUMNS = {"item_code": 3, "batch": 3, "warehouse": 2, "qty": 1, "stock_uom": 1}


def execute():
    _insert_fields("Outward Request Item", NEW_ITEM_FIELDS, columns=ITEM_COLUMNS)
    _insert_fields("Outward Request", NEW_REQUEST_FIELDS)


def _insert_fields(doctype, specs, columns=None):
    doc = frappe.get_doc("DocType", doctype)
    existing = {f.fieldname for f in doc.fields}
    changed = False

    for spec, after in specs:
        if spec["fieldname"] in existing:
            continue
        fields = list(doc.fields)
        pos = next((i + 1 for i, f in enumerate(fields) if f.fieldname == after), len(fields))
        doc.fields = []
        for f in fields[:pos]:
            doc.append("fields", f)
        doc.append("fields", spec)
        for f in fields[pos:]:
            doc.append("fields", f)
        existing.add(spec["fieldname"])
        changed = True

    if columns:
        for f in doc.fields:
            if f.fieldname in columns and f.columns != columns[f.fieldname]:
                f.columns = columns[f.fieldname]
                changed = True

    if changed:
        for i, f in enumerate(doc.fields, start=1):
            f.idx = i
        doc.save(ignore_permissions=True)
