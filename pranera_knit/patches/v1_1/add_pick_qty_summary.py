"""
pranera_knit/patches/v1_1/add_pick_qty_summary.py

Extends Roll Pick Assignment / Roll Pick Batch Item — owned by the
Textiles And Garments app, not this one — via Custom Fields + a Property
Setter only. Same non-invasive pattern as
patches/v1_0/add_pick_order_persistence.py, so this app never forks
another app's DocType source.

Adds:
  1. "Stock UOM" on "Roll Pick Batch Item" — fetched from Batch.stock_uom
     (itself fetched from the batch's Item on the Batch doctype already),
     read-only.
  2. A Property Setter so "batch_items" also shows on the Roll Pick
     Assignment form for pick_type == "To Work Order" (previously: From
     Batch / To Sales Order only). Batch restriction for "To Work Order"
     picks is optional and was already supported server-side
     (api/pick_order.py's scan_pick_order_roll, since commit
     "Optional batch restriction for To Work Order pick orders") — the
     form just never showed the field for that pick_type, so a
     supervisor had no way to actually populate it.
  3. A new child doctype "Roll Pick Qty Summary" (uom, total_qty) and a
     new read-only Table field "pick_qty_summary" on Roll Pick
     Assignment. Batches named in batch_items can carry different Stock
     UOMs, so a single summed Pick Qty number would silently mix units —
     this shows the total broken out per UOM instead. Kept in sync by
     pranera_knit.pick_qty_summary.set_pick_qty_summary, registered as a
     "validate" doc_event in hooks.py (see that file for why a doc_event
     is the right mechanism for a doctype this app doesn't own).
"""
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def execute():
    _create_qty_summary_child_doctype()
    _add_custom_fields()
    _widen_batch_items_depends_on()


def _create_qty_summary_child_doctype():
    if frappe.db.exists("DocType", "Roll Pick Qty Summary"):
        return

    frappe.get_doc({
        "doctype": "DocType",
        "name": "Roll Pick Qty Summary",
        "module": "Textiles And Garments",
        "custom": 1,
        "istable": 1,
        "editable_grid": 0,
        "fields": [
            {
                "fieldname": "uom", "label": "UOM", "fieldtype": "Link",
                "options": "UOM", "in_list_view": 1, "read_only": 1,
            },
            {
                "fieldname": "total_qty", "label": "Total Qty", "fieldtype": "Float",
                "in_list_view": 1, "read_only": 1,
            },
        ],
        "permissions": [
            {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1},
        ],
    }).insert(ignore_permissions=True)


def _add_custom_fields():
    create_custom_fields({
        "Roll Pick Batch Item": [
            {
                "fieldname": "stock_uom",
                "label": "Stock UOM",
                "fieldtype": "Link",
                "options": "UOM",
                "fetch_from": "batch.stock_uom",
                "read_only": 1,
                "insert_after": "qty",
                "in_list_view": 1,
            },
        ],
        "Roll Pick Assignment": [
            {
                "fieldname": "pick_qty_summary",
                "label": "Pick Qty (by UOM)",
                "fieldtype": "Table",
                "options": "Roll Pick Qty Summary",
                "insert_after": "pick_qty",
                "read_only": 1,
                "depends_on": "eval:doc.batch_items && doc.batch_items.length",
                "description": (
                    "Auto-computed from Batch Items whenever it's used — replaces "
                    "reading a single Pick Qty number, since batches can carry "
                    "different Stock UOMs and a single summed total would mix units. "
                    "Pick Qty itself is still kept as the grand total across all UOMs, "
                    "for the tolerance-based scan flow that already reads it."
                ),
            },
        ],
    }, ignore_validate=True, update=True)


def _widen_batch_items_depends_on():
    make_property_setter(
        "Roll Pick Assignment", "batch_items", "depends_on",
        "eval:doc.pick_type=='From Batch' || doc.pick_type=='To Sales Order' || doc.pick_type=='To Work Order'",
        "Text",
    )
