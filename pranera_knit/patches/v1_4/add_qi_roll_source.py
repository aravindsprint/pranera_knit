"""
pranera_knit/patches/v1_4/add_qi_roll_source.py

Lets a Roll Pick Assignment be fulfilled with OLD rolls whose only record
is a row in a QI Report Details' "Roll Details" table (no Roll document).
Their stickers carry "item_code#batch_no#lot_no#roll_no".

Custom Fields only (same non-invasive pattern as patches/v1_1), since
these doctypes belong to the Textiles And Garments app:

  1. Roll Pick Assignment.roll_source — Select "Roll" / "QI Report Details"
     (default "Roll"). Decides where scan_pick_order_roll looks a scanned
     roll up. allow_on_submit so an already-submitted Assignment can be
     switched.
  2. Roll Pick Assignment Scan.qi_report — which QI report the scanned
     roll came from (QI roll numbers are NOT unique across reports, and
     many collide with unrelated Roll names).
  3. Roll Wise Pick Item.qi_report — same, carried onto the submitted pick
     list so the row is never mistaken for a Roll document.
"""
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    create_custom_fields({
        "Roll Pick Assignment": [
            {
                "fieldname": "roll_source",
                "label": "Roll Source",
                "fieldtype": "Select",
                "options": "Roll\nQI Report Details",
                "default": "Roll",
                "insert_after": "pick_type",
                "allow_on_submit": 1,
                "in_standard_filter": 1,
                "description": (
                    "Roll: scan rolls created in this app (Roll doctype). "
                    "QI Report Details: scan old rolls whose sticker is "
                    "item#batch#lot#roll_no — weight and UOM are taken from "
                    "the QI Report Details' Roll Details row."
                ),
            },
        ],
        "Roll Pick Assignment Scan": [
            {
                "fieldname": "qi_report",
                "label": "QI Report",
                "fieldtype": "Link",
                "options": "QI Report Details",
                "insert_after": "roll_weight",
                "read_only": 1,
            },
        ],
        "Roll Wise Pick Item": [
            {
                "fieldname": "qi_report",
                "label": "QI Report",
                "fieldtype": "Link",
                "options": "QI Report Details",
                "insert_after": "roll_no",
                "read_only": 1,
                "in_list_view": 0,
            },
        ],
    }, ignore_validate=True, update=True)
