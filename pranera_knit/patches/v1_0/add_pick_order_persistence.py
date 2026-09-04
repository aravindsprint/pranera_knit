"""
pranera_knit/patches/v1_0/add_pick_order_persistence.py

Adds server-side persistence for an in-progress Pick Order Execution
session, so a worker can close the app mid-scan and resume later without
losing what they already scanned (previously: everything lived only in
the browser's Pinia store and was wiped on unmount / page refresh).

Adds:
  1. A new child doctype "Roll Pick Assignment Scan" — one row per roll
     scanned against a Roll Pick Assignment that hasn't been submitted
     yet.
  2. Three new fields on "Roll Pick Assignment":
       - scanned_rolls              (Table -> Roll Pick Assignment Scan)
       - execution_source_warehouse (Link -> Warehouse)
       - execution_target_warehouse (Link -> Warehouse)
     The execution_* fields hold the worker's current choice at execution
     time, separate from the supervisor-set source_warehouse /
     target_warehouse on the Assignment itself — the worker can override
     either if the rolls are actually sitting somewhere else, or the
     material needs to land somewhere else, without changing the
     original Assignment.

Created as a genuine app-owned DocType (via this patch, guarded by an
exists() check) + Custom Fields rather than a production-only tweak —
see the note at the top of api/pick_order.py on why this app avoids
that pattern.
"""
import frappe


def execute():
    _create_scan_child_doctype()
    _add_execution_fields()


def _create_scan_child_doctype():
    if frappe.db.exists("DocType", "Roll Pick Assignment Scan"):
        return

    doc = frappe.get_doc({
        "doctype": "DocType",
        "name": "Roll Pick Assignment Scan",
        "module": "Textiles And Garments",
        "custom": 1,
        "istable": 1,
        "editable_grid": 1,
        "fields": [
            {
                "fieldname": "roll_no", "label": "Roll No", "fieldtype": "Data",
                "reqd": 1, "in_list_view": 1,
            },
            {
                "fieldname": "item_code", "label": "Item Code", "fieldtype": "Link",
                "options": "Item", "in_list_view": 1,
            },
            {
                "fieldname": "warehouse", "label": "Warehouse", "fieldtype": "Link",
                "options": "Warehouse", "in_list_view": 1,
                "description": "Source warehouse the worker had selected at the moment this roll was scanned",
            },
            {
                "fieldname": "batch_no", "label": "Batch No", "fieldtype": "Data",
                "in_list_view": 1,
            },
            {
                "fieldname": "qty", "label": "Qty", "fieldtype": "Float",
                "in_list_view": 1,
            },
            {
                "fieldname": "uom", "label": "UOM", "fieldtype": "Data",
            },
            {
                "fieldname": "scanned_by", "label": "Scanned By", "fieldtype": "Link",
                "options": "User", "read_only": 1,
            },
            {
                "fieldname": "scanned_at", "label": "Scanned At", "fieldtype": "Datetime",
                "read_only": 1,
            },
        ],
        "permissions": [
            {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1},
        ],
    })
    doc.insert(ignore_permissions=True)


def _add_execution_fields():
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

    custom_fields = {
        "Roll Pick Assignment": [
            {
                "fieldname": "scanned_rolls",
                "label": "Scanned Rolls (In Progress)",
                "fieldtype": "Table",
                "options": "Roll Pick Assignment Scan",
                "insert_after": "pick_qty",
                "description": (
                    "Rolls scanned so far for this Assignment but not yet submitted as a "
                    "Stock Entry. Persisted server-side so a worker can close the app and "
                    "resume later without rescanning. Cleared automatically once the final "
                    "Pick Entry is created."
                ),
            },
            {
                "fieldname": "execution_source_warehouse",
                "label": "Execution Source Warehouse",
                "fieldtype": "Link",
                "options": "Warehouse",
                "insert_after": "scanned_rolls",
                "description": (
                    "Worker's current Source Warehouse selection during execution — defaults "
                    "to Source Warehouse but can be changed on the scan screen if the rolls "
                    "are actually sitting somewhere else. Persisted so a worker resuming "
                    "later sees their last choice."
                ),
            },
            {
                "fieldname": "execution_target_warehouse",
                "label": "Execution Target Warehouse",
                "fieldtype": "Link",
                "options": "Warehouse",
                "insert_after": "execution_source_warehouse",
                "description": (
                    "Worker's current Target Warehouse selection during execution — defaults "
                    "to Target Warehouse but can be changed on the scan screen. Persisted so "
                    "a worker resuming later sees their last choice."
                ),
            },
        ]
    }
    create_custom_fields(custom_fields, ignore_validate=True, update=True)
