"""
pranera_knit/patches/v1_26/index_outward_request_links.py

Indexes the links followed to compute Outward Request picked / sent
quantities (outward_request_progress.py) and the Loading Scan checklist:

  Roll Pick Assignment.outward_request
  Roll Wise Pick List.roll_pick_assignment
  Stock Entry.custom_roll_wise_pick_list

None of them had an index, so joining them scanned Stock Entry in full.
"""
import frappe

INDEXES = [
    ("Roll Pick Assignment", "outward_request"),
    ("Roll Wise Pick List", "roll_pick_assignment"),
    ("Stock Entry", "custom_roll_wise_pick_list"),
]


def execute():
    for doctype, field in INDEXES:
        if frappe.db.table_exists(doctype) and frappe.db.has_column(doctype, field):
            frappe.db.add_index(doctype, [field])
