"""
pranera_knit/patches/v1_22/add_knit_down_approver_locations.py

Knit Down approval by location (rules in knit_down_events.can_approve).

Creates:
  "Knit Down Approver Location"  child: user, full_name, location
  "Knit Down Settings"           single: approver_locations table
                                 (one row per approver + location; an
                                 approver with several sites gets a row each)
Adds to "Knit Down Approval":
  location  Link → Location, copied from the Work Order's custom_location;
            existing knit downs are back-filled.

Until an admin fills in Knit Down Settings, Knit Down Approvers can't
decide any knit down — only System Managers can. Fill it in right after
deploying: Desk → Knit Down Settings.
"""
import frappe

MODULE = "Knit Module"

CHILD_FIELDS = [
    {"fieldname": "user", "label": "Approver", "fieldtype": "Link", "options": "User",
     "reqd": 1, "in_list_view": 1, "columns": 4},
    {"fieldname": "full_name", "label": "Full Name", "fieldtype": "Data", "read_only": 1,
     "fetch_from": "user.full_name", "in_list_view": 1, "columns": 3},
    {"fieldname": "location", "label": "Location", "fieldtype": "Link", "options": "Location",
     "reqd": 1, "in_list_view": 1, "columns": 3},
]

SETTINGS_FIELDS = [
    {"fieldname": "approver_locations", "label": "Approver Locations", "fieldtype": "Table",
     "options": "Knit Down Approver Location",
     "description": "A Knit Down Approver can only approve or reject knit downs of Work Orders at "
                    "their locations here (Work Order → Location). One row per approver and "
                    "location. Knit downs with no location: System Manager only. "
                    "System Managers can always approve."},
]

LOCATION_FIELD = {"fieldname": "location", "label": "Location", "fieldtype": "Link",
                  "options": "Location", "read_only": 1, "in_list_view": 1,
                  "in_standard_filter": 1}


def execute():
    if not frappe.db.exists("DocType", "Knit Down Approver Location"):
        frappe.get_doc({
            "doctype": "DocType", "name": "Knit Down Approver Location", "module": MODULE,
            "custom": 1, "istable": 1, "editable_grid": 1, "fields": CHILD_FIELDS,
        }).insert(ignore_permissions=True)

    if not frappe.db.exists("DocType", "Knit Down Settings"):
        frappe.get_doc({
            "doctype": "DocType", "name": "Knit Down Settings", "module": MODULE,
            "custom": 1, "issingle": 1, "fields": SETTINGS_FIELDS,
            "permissions": [{"role": "System Manager", "read": 1, "write": 1, "create": 1}],
        }).insert(ignore_permissions=True)

    if frappe.db.exists("DocType", "Knit Down Approval"):
        doc = frappe.get_doc("DocType", "Knit Down Approval")
        if not any(f.fieldname == "location" for f in doc.fields):
            row = doc.append("fields", LOCATION_FIELD)
            doc.fields.remove(row)
            after = next((i for i, f in enumerate(doc.fields) if f.fieldname == "knit_type"),
                         next(i for i, f in enumerate(doc.fields) if f.fieldname == "job_card"))
            doc.fields.insert(after + 1, row)
            for i, f in enumerate(doc.fields, start=1):
                f.idx = i
            doc.save(ignore_permissions=True)
        frappe.db.sql("""
            UPDATE `tabKnit Down Approval` kd
            JOIN `tabWork Order` wo ON wo.name = kd.work_order
            SET kd.location = wo.custom_location
            WHERE IFNULL(kd.location, '') = '' AND IFNULL(wo.custom_location, '') != ''
        """)
