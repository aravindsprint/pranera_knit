"""
pranera_knit/patches/v1_23/add_loading_scan.py

Loading scan: security scans every roll put on a vehicle and the app
cross-checks them against the outbound Stock Entries of that Vehicle Gate
Entry (all its Outward Requests together). Logic: api/loading_scan.py.

Creates:
  "Loading Scan"  one record per scan: vehicle_gate_entry, roll_no, result
                  (Matched / Not in list), the matched stock entry / pick
                  list / item / batch / qty, scanned_by, scanned_at.
                  One record per scan (not a child table) so several
                  security phones can scan the same vehicle at once.
  Knit App Page "loading-scan" (via the v1_10 seeding).
"""
import frappe

from pranera_knit.patches.v1_10.add_knit_app_page_access import execute as seed_pages

MODULE = "Knit Module"
DOCTYPE = "Loading Scan"
SCAN_ROLES = ("Security", "Gate Security", "NAP Security", "Stock User", "Stock Manager")

FIELDS = [
    {"fieldname": "vehicle_gate_entry", "label": "Vehicle Gate Entry", "fieldtype": "Link",
     "options": "Vehicle Gate Entry", "reqd": 1, "in_list_view": 1, "in_standard_filter": 1,
     "search_index": 1},
    {"fieldname": "roll_no", "label": "Roll No", "fieldtype": "Data", "reqd": 1, "in_list_view": 1,
     "search_index": 1},
    {"fieldname": "result", "label": "Result", "fieldtype": "Select",
     "options": "Matched\nNot in list", "reqd": 1, "in_list_view": 1, "in_standard_filter": 1},
    {"fieldname": "column_break_1", "fieldtype": "Column Break"},
    {"fieldname": "stock_entry", "label": "Stock Entry", "fieldtype": "Link", "options": "Stock Entry"},
    {"fieldname": "pick_list", "label": "Roll Wise Pick List", "fieldtype": "Link",
     "options": "Roll Wise Pick List"},
    {"fieldname": "outward_request", "label": "Outward Request", "fieldtype": "Link",
     "options": "Outward Request"},
    {"fieldname": "section_item", "fieldtype": "Section Break"},
    {"fieldname": "item_code", "label": "Item", "fieldtype": "Link", "options": "Item"},
    {"fieldname": "batch", "label": "Batch", "fieldtype": "Link", "options": "Batch"},
    {"fieldname": "column_break_2", "fieldtype": "Column Break"},
    {"fieldname": "qty", "label": "Qty", "fieldtype": "Float"},
    {"fieldname": "uom", "label": "UOM", "fieldtype": "Data"},
    {"fieldname": "section_by", "fieldtype": "Section Break"},
    {"fieldname": "scanned_by", "label": "Scanned By", "fieldtype": "Link", "options": "User",
     "read_only": 1},
    {"fieldname": "scanned_at", "label": "Scanned At", "fieldtype": "Datetime", "read_only": 1},
    {"fieldname": "column_break_3", "fieldtype": "Column Break"},
    {"fieldname": "raw_value", "label": "Scanned Text", "fieldtype": "Data", "read_only": 1},
]


def execute():
    if not frappe.db.exists("DocType", DOCTYPE):
        perms = [{"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1,
                  "report": 1, "export": 1}]
        perms += [{"role": r, "read": 1, "create": 1, "delete": 1, "report": 1}
                  for r in SCAN_ROLES if frappe.db.exists("Role", r)]
        frappe.get_doc({
            "doctype": "DocType", "name": DOCTYPE, "module": MODULE, "custom": 1,
            "autoname": "hash", "track_changes": 0, "sort_field": "creation", "sort_order": "DESC",
            "title_field": "roll_no", "fields": FIELDS, "permissions": perms,
        }).insert(ignore_permissions=True)
    else:
        doc = frappe.get_doc("DocType", DOCTYPE)
        existing = {f.fieldname for f in doc.fields}
        for f in FIELDS:
            if f["fieldname"] not in existing:
                doc.append("fields", f)
        doc.save(ignore_permissions=True)

    seed_pages()
