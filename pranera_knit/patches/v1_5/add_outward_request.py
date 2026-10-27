"""
pranera_knit/patches/v1_5/add_outward_request.py

Adds the "Outward Request" flow — a request to send material out to
another Building, against either a Work Order or a (subcontracting)
Purchase Order. The items table is pre-filled from that document (see
pranera_knit/outward_request.py → get_items) and then progresses through
the existing pick flow:

    Outward Request ──(outward_request)── Roll Pick Assignment
        └─ Roll Wise Pick List (roll_pick_assignment)
            └─ Stock Entry (custom_roll_wise_pick_list, submitted)

Creates:
  1. Child DocType "Outward Request Item"  — item_code / batch / qty / stock_uom
  2. DocType "Outward Request"             — date, to_building, work_order,
     purchase_order, items, created_by, created_on, status, request_status
  3. Custom Field "Roll Pick Assignment-outward_request" (Link) — how a
     pick is tied back to the request so status can be tracked.

"Doc Status" is stored as request_status — "docstatus" is a reserved
Frappe column and can't be used as a fieldname.

Same app-owned, patch-created pattern as v1_0/add_pick_order_persistence.py
(guarded by exists()). Re-running is safe: when the DocType already exists,
any field in the spec it's missing is appended rather than skipped, so a
later patch can extend FIELDS without a separate migration path.
"""
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

MODULE = "Knit Module"

PERMISSIONS = [
    {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "report": 1, "export": 1},
    {"role": "Stock Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "report": 1, "export": 1},
    {"role": "Stock User", "read": 1, "write": 1, "create": 1, "report": 1},
    {"role": "Roll Picker", "read": 1},
]

ITEM_FIELDS = [
    {"fieldname": "item_code", "label": "Item Code", "fieldtype": "Link", "options": "Item",
     "reqd": 1, "in_list_view": 1, "columns": 4},
    {"fieldname": "batch", "label": "Batch", "fieldtype": "Link", "options": "Batch",
     "in_list_view": 1, "columns": 3},
    {"fieldname": "qty", "label": "Qty", "fieldtype": "Float", "reqd": 1,
     "in_list_view": 1, "columns": 2},
    {"fieldname": "stock_uom", "label": "Stock UOM", "fieldtype": "Link", "options": "UOM",
     "in_list_view": 1, "columns": 1},
]

REQUEST_FIELDS = [
    {"fieldname": "date", "label": "Date", "fieldtype": "Date", "reqd": 1,
     "default": "Today", "in_list_view": 1},
    {"fieldname": "to_building", "label": "To", "fieldtype": "Link", "options": "Building",
     "reqd": 1, "in_list_view": 1, "in_standard_filter": 1},
    {"fieldname": "column_break_ref", "fieldtype": "Column Break"},
    {"fieldname": "work_order", "label": "Work Order", "fieldtype": "Link", "options": "Work Order",
     "in_standard_filter": 1,
     "description": "Items are fetched from this Work Order's Required Items"},
    {"fieldname": "purchase_order", "label": "Purchase Order", "fieldtype": "Link",
     "options": "Purchase Order", "in_standard_filter": 1,
     "description": "Items are fetched from the Raw Materials Supplied table of the "
                    "submitted Subcontracting Receipt(s) linked to this Purchase Order"},
    {"fieldname": "section_items", "fieldtype": "Section Break", "label": "Items"},
    {"fieldname": "items", "label": "Items", "fieldtype": "Table",
     "options": "Outward Request Item", "reqd": 1},
    {"fieldname": "section_tracking", "fieldtype": "Section Break", "label": "Tracking"},
    {"fieldname": "created_by", "label": "Created By", "fieldtype": "Link", "options": "User",
     "read_only": 1},
    {"fieldname": "created_on", "label": "Created On", "fieldtype": "Datetime", "read_only": 1},
    {"fieldname": "column_break_status", "fieldtype": "Column Break"},
    {"fieldname": "status", "label": "Status", "fieldtype": "Select",
     "options": "\nRoll Pick Assigned\nPicked\nCompleted", "read_only": 1,
     "in_list_view": 1, "in_standard_filter": 1, "no_copy": 1,
     "description": "Roll Pick Assigned → a Roll Pick Assignment is linked; Picked → its "
                    "Roll Wise Pick List is submitted; Completed → the Stock Entry for that "
                    "pick list is submitted"},
    {"fieldname": "request_status", "label": "Doc Status", "fieldtype": "Select",
     "options": "Pending\nProcessing\nCompleted", "default": "Pending", "read_only": 1,
     "in_list_view": 1, "in_standard_filter": 1, "no_copy": 1},
]


def execute():
    _ensure_doctype("Outward Request Item", ITEM_FIELDS, {
        "istable": 1,
        "editable_grid": 1,
    })
    _ensure_doctype("Outward Request", REQUEST_FIELDS, {
        "autoname": "OR/.YY./.#####",
        "naming_rule": "Expression (old style)",
        "track_changes": 1,
        "sort_field": "creation",
        "sort_order": "DESC",
        "search_fields": "to_building,work_order,purchase_order",
        "permissions": PERMISSIONS,
    })
    create_custom_fields({
        "Roll Pick Assignment": [
            {
                "fieldname": "outward_request",
                "label": "Outward Request",
                "fieldtype": "Link",
                "options": "Outward Request",
                "insert_after": "purchase_order",
                "allow_on_submit": 1,
                "description": "Outward Request this pick fulfils — drives that request's Status",
            },
        ],
    }, ignore_validate=True, update=True)


def _ensure_doctype(name, fields, props):
    if not frappe.db.exists("DocType", name):
        doc = frappe.get_doc({
            "doctype": "DocType",
            "name": name,
            "module": MODULE,
            "custom": 1,
            "fields": fields,
            **props,
        })
        if not props.get("istable") and "permissions" not in props:
            doc.set("permissions", PERMISSIONS)
        doc.insert(ignore_permissions=True)
        return

    doc = frappe.get_doc("DocType", name)
    existing = {f.fieldname for f in doc.fields}
    missing = [f for f in fields if f["fieldname"] not in existing]
    if not missing:
        return
    for f in missing:
        doc.append("fields", f)
    doc.save(ignore_permissions=True)
