"""
Adds Roll Pick Assignment.allow_old_roll_scan (Check, default off).

When ticked, scan_pick_order_roll also accepts rolls that were never put on
a submitted Roll Packing List with a Stock Entry and aren't linked to a
Purchase / Subcontracting Receipt — old manufactured rolls and bought-in /
subcontracted rolls — as long as their batch was brought into stock by a
submitted Manufacture / Repack / Material Receipt Stock Entry, Purchase
Receipt, Subcontracting Receipt or Stock Reconciliation.

Custom Field only (same pattern as the roll_source patch), since Roll Pick
Assignment belongs to the Textiles And Garments app. allow_on_submit so a
supervisor can switch it on an already-submitted Assignment.
"""
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    create_custom_fields({
        "Roll Pick Assignment": [
            {
                "fieldname": "allow_old_roll_scan",
                "label": "Allow Old Roll Scan",
                "fieldtype": "Check",
                "default": "0",
                "insert_after": "roll_source",
                "allow_on_submit": 1,
                "in_standard_filter": 1,
                "description": (
                    "Also accept old rolls that are not on a Roll Packing List with a "
                    "Stock Entry and not linked to a Purchase / Subcontracting Receipt, "
                    "as long as their batch was received into stock."
                ),
            },
        ],
    }, ignore_validate=True, update=True)
