"""
pranera_knit/patches/v1_8/add_vge_expected_arrival.py

Adds "Expected Arrival Date and Time" (expected_arrival_datetime, optional)
to Vehicle Gate Entry, placed just before Arrival Date and Time.

Vehicle Gate Entry is a patch-created custom DocType (v1_6), already live,
so the field is inserted into the existing DocType here. v1_6's FIELDS list
includes it too, so a fresh install gets it from v1_6 and this is a no-op.
"""
import frappe

FIELD = {
    "fieldname": "expected_arrival_datetime",
    "label": "Expected Arrival Date and Time",
    "fieldtype": "Datetime",
    "in_list_view": 1,
    "description": "When the vehicle is expected at the gate",
}


def execute():
    if not frappe.db.exists("DocType", "Vehicle Gate Entry"):
        return
    doc = frappe.get_doc("DocType", "Vehicle Gate Entry")
    if any(f.fieldname == FIELD["fieldname"] for f in doc.fields):
        return

    new = doc.append("fields", FIELD)
    # Move it right before arrival_datetime (append adds it at the end).
    fields = [f for f in doc.fields if f is not new]
    pos = next((i for i, f in enumerate(fields) if f.fieldname == "arrival_datetime"), len(fields))
    fields.insert(pos, new)
    for i, f in enumerate(fields, start=1):
        f.idx = i
    doc.fields = fields
    doc.save(ignore_permissions=True)
