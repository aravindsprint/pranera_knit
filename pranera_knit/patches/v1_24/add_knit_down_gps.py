"""
pranera_knit/patches/v1_24/add_knit_down_gps.py

GPS check for knit down approval (rules in knit_down_events.check_gps).

Knit Down Settings:
  require_gps   Check, default on: a Knit Down Approver must be at the unit
                to approve / reject (System Manager exempt)
  gps_radius_m  Int, default 200: how close (metres) to the Location's
                Latitude / Longitude counts as "at the unit"
Knit Down Approval (read only, filled when approved / rejected):
  decision_latitude, decision_longitude, decision_accuracy_m,
  decision_distance_m

Each unit's coordinates go on its Location record (Desk → Location →
Latitude / Longitude). Until they're set, approvers get "has no GPS
coordinates yet" for that unit.
"""
import frappe

SETTINGS_FIELDS = [
    {"fieldname": "section_gps", "fieldtype": "Section Break", "label": "GPS"},
    {"fieldname": "require_gps", "label": "Require GPS", "fieldtype": "Check", "default": "1",
     "description": "Knit Down Approvers must be at the unit (phone GPS) to approve or reject. "
                    "Unit position = Latitude / Longitude on the Location record. "
                    "System Managers are exempt."},
    {"fieldname": "gps_radius_m", "label": "GPS Range (metres)", "fieldtype": "Int", "default": "200",
     "depends_on": "require_gps"},
]

DECISION_FIELDS = [
    {"fieldname": "section_decision_gps", "fieldtype": "Section Break", "label": "Approved From",
     "collapsible": 1, "depends_on": "eval:doc.decision_latitude"},
    {"fieldname": "decision_latitude", "label": "Latitude", "fieldtype": "Float", "precision": "6",
     "read_only": 1, "no_copy": 1},
    {"fieldname": "decision_longitude", "label": "Longitude", "fieldtype": "Float", "precision": "6",
     "read_only": 1, "no_copy": 1},
    {"fieldname": "column_break_decision_gps", "fieldtype": "Column Break"},
    {"fieldname": "decision_distance_m", "label": "Distance from Unit (m)", "fieldtype": "Int",
     "read_only": 1, "no_copy": 1},
    {"fieldname": "decision_accuracy_m", "label": "GPS Accuracy (m)", "fieldtype": "Float",
     "precision": "0", "read_only": 1, "no_copy": 1},
]


def _append(doctype, fields):
    doc = frappe.get_doc("DocType", doctype)
    existing = {f.fieldname for f in doc.fields}
    added = False
    for f in fields:
        if f["fieldname"] not in existing:
            doc.append("fields", f)
            added = True
    if added:
        doc.save(ignore_permissions=True)


def execute():
    if frappe.db.exists("DocType", "Knit Down Settings"):
        _append("Knit Down Settings", SETTINGS_FIELDS)
        frappe.clear_cache(doctype="Knit Down Settings")
        s = frappe.get_single("Knit Down Settings")
        if not s.get("gps_radius_m"):
            s.require_gps = 1
            s.gps_radius_m = 200
            s.save(ignore_permissions=True)
    if frappe.db.exists("DocType", "Knit Down Approval"):
        _append("Knit Down Approval", DECISION_FIELDS)
