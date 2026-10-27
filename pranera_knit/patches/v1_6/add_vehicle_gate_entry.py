"""
pranera_knit/patches/v1_6/add_vehicle_gate_entry.py

Creates the "Vehicle Gate Entry" DocType: a gate log of vehicles coming in
to pick up or drop material.

Fields: date, vehicle_no, driver_name, mobile_no, capacity (0.25 – 20
ton), arrival_datetime, departure_datetime, purpose (Pick Up / Drop),
from_location / to_location, outward_requests, created_by.

outward_requests (Pick Up only) is a child table of "Vehicle Gate Entry
Outward Request" rows — the Outward Requests this vehicle is collecting.
Each request can be on one gate entry at a time (enforced in
vehicle_gate_entry_events.py); api/outward_request.py reads the table
back to show the vehicle on the request.

from_location is shown for a Pick Up and to_location for a Drop. Both
hold either a Building name or one of the fixed values in
LOCATION_EXTRAS ("Purchase", "Subcontract"), so they're Data fields
rather than a Link; vehicle_gate_entry_events.validate checks the value.

Same app-owned, patch-created pattern as v1_5/add_outward_request.py.
Re-running appends any field missing from an existing DocType and
refreshes the capacity options.
"""
import frappe

MODULE = "Knit Module"


def capacity_options():
    """0.25 – 2 ton in 0.25 steps, 2.5 – 5 in 0.5 steps, 6 – 20 in 1 ton steps."""
    values = [x / 4 for x in range(1, 9)] + [x / 2 for x in range(5, 11)] + list(range(6, 21))
    return ["{:g} Ton".format(v) for v in values]


PERMISSIONS = [
    {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "report": 1, "export": 1},
    {"role": "Stock Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "report": 1, "export": 1},
    {"role": "Stock User", "read": 1, "write": 1, "create": 1, "report": 1},
]

CHILD_FIELDS = [
    {"fieldname": "outward_request", "label": "Outward Request", "fieldtype": "Link",
     "options": "Outward Request", "reqd": 1, "in_list_view": 1, "columns": 3},
    {"fieldname": "to_building", "label": "To", "fieldtype": "Link", "options": "Building",
     "fetch_from": "outward_request.to_building", "read_only": 1, "in_list_view": 1, "columns": 3},
    {"fieldname": "work_order", "label": "Work Order", "fieldtype": "Link", "options": "Work Order",
     "fetch_from": "outward_request.work_order", "read_only": 1, "in_list_view": 1, "columns": 2},
    {"fieldname": "purchase_order", "label": "Purchase Order", "fieldtype": "Link",
     "options": "Purchase Order", "fetch_from": "outward_request.purchase_order", "read_only": 1,
     "in_list_view": 1, "columns": 2},
]

FIELDS = [
    {"fieldname": "date", "label": "Date", "fieldtype": "Date", "reqd": 1, "default": "Today",
     "in_list_view": 1, "in_standard_filter": 1},
    {"fieldname": "vehicle_no", "label": "Vehicle No", "fieldtype": "Data", "reqd": 1,
     "in_list_view": 1, "in_standard_filter": 1},
    {"fieldname": "driver_name", "label": "Driver Name", "fieldtype": "Data", "reqd": 1},
    {"fieldname": "mobile_no", "label": "Mobile No", "fieldtype": "Data", "reqd": 1},
    {"fieldname": "capacity", "label": "Capacity", "fieldtype": "Select", "reqd": 1,
     "options": "\n".join(capacity_options())},
    {"fieldname": "column_break_times", "fieldtype": "Column Break"},
    {"fieldname": "arrival_datetime", "label": "Arrival Date and Time", "fieldtype": "Datetime",
     "reqd": 1, "default": "now", "in_list_view": 1},
    {"fieldname": "departure_datetime", "label": "Departure Date and Time", "fieldtype": "Datetime"},
    {"fieldname": "purpose", "label": "Purpose", "fieldtype": "Select", "reqd": 1,
     "options": "Pick Up\nDrop", "in_list_view": 1, "in_standard_filter": 1},
    {"fieldname": "from_location", "label": "From", "fieldtype": "Data",
     "depends_on": "eval:doc.purpose=='Pick Up'",
     "mandatory_depends_on": "eval:doc.purpose=='Pick Up'",
     "description": "A Building, or Purchase / Subcontract"},
    {"fieldname": "to_location", "label": "To", "fieldtype": "Data",
     "depends_on": "eval:doc.purpose=='Drop'",
     "mandatory_depends_on": "eval:doc.purpose=='Drop'",
     "description": "A Building, or Purchase / Subcontract"},
    {"fieldname": "section_outward", "fieldtype": "Section Break", "label": "Outward Requests",
     "depends_on": "eval:doc.purpose=='Pick Up'"},
    {"fieldname": "outward_requests", "label": "Outward Requests", "fieldtype": "Table",
     "options": "Vehicle Gate Entry Outward Request",
     "description": "Outward Requests this vehicle is picking up"},
    {"fieldname": "section_tracking", "fieldtype": "Section Break", "label": "Tracking"},
    {"fieldname": "created_by", "label": "Created By", "fieldtype": "Link", "options": "User",
     "read_only": 1},
]


def execute():
    if not frappe.db.exists("DocType", "Vehicle Gate Entry Outward Request"):
        frappe.get_doc({
            "doctype": "DocType",
            "name": "Vehicle Gate Entry Outward Request",
            "module": MODULE,
            "custom": 1,
            "istable": 1,
            "editable_grid": 1,
            "fields": CHILD_FIELDS,
        }).insert(ignore_permissions=True)

    if not frappe.db.exists("DocType", "Vehicle Gate Entry"):
        frappe.get_doc({
            "doctype": "DocType",
            "name": "Vehicle Gate Entry",
            "module": MODULE,
            "custom": 1,
            "autoname": "VGE/.YY./.#####",
            "naming_rule": "Expression (old style)",
            "track_changes": 1,
            "sort_field": "creation",
            "sort_order": "DESC",
            "search_fields": "vehicle_no,driver_name,purpose",
            "title_field": "vehicle_no",
            "fields": FIELDS,
            "permissions": PERMISSIONS,
        }).insert(ignore_permissions=True)
        return

    doc = frappe.get_doc("DocType", "Vehicle Gate Entry")
    existing = {f.fieldname: f for f in doc.fields}
    for f in FIELDS:
        if f["fieldname"] not in existing:
            doc.append("fields", f)
    if "capacity" in existing:
        existing["capacity"].options = "\n".join(capacity_options())
    doc.save(ignore_permissions=True)
