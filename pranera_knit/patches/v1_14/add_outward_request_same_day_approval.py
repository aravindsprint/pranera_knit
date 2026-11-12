"""
pranera_knit/patches/v1_14/add_outward_request_same_day_approval.py

Same-day cut-off for Outward Requests.

After the cut-off time (default 3:00 PM, server time) a new request is
dated tomorrow by default. Keeping today's date after the cut-off needs
approval from one of the configured approvers. Dates in the past are never
allowed. The rules live in pranera_knit/outward_request_approval.py.

Creates:
  1. Child DocType "Outward Request Approver"   — user, full_name
  2. Single DocType "Outward Request Settings"  — same_day_cutoff_time,
     require_same_day_approval, approvers. Seeded with 15:00 and
     fabric@praneraservices.com (when that user exists).
  3. Outward Request fields — same_day_approval (Pending / Approved /
     Rejected), approval_requested_on, approved_by, approved_on,
     approval_remarks.

Same app-owned, patch-created pattern as v1_5 (re-running only appends
missing fields).
"""
import frappe

from pranera_knit.patches.v1_5.add_outward_request import _ensure_doctype

DEFAULT_CUTOFF = "15:00:00"
DEFAULT_APPROVERS = ("fabric@praneraservices.com",)

SETTINGS_PERMISSIONS = [
    {"role": "System Manager", "read": 1, "write": 1, "create": 1},
    {"role": "Stock Manager", "read": 1, "write": 1, "create": 1},
    {"role": "Stock User", "read": 1},
]

APPROVER_FIELDS = [
    {"fieldname": "user", "label": "User", "fieldtype": "Link", "options": "User",
     "reqd": 1, "in_list_view": 1, "columns": 5},
    {"fieldname": "full_name", "label": "Full Name", "fieldtype": "Data",
     "fetch_from": "user.full_name", "read_only": 1, "in_list_view": 1, "columns": 5},
]

SETTINGS_FIELDS = [
    {"fieldname": "same_day_cutoff_time", "label": "Same-day Cut-off Time", "fieldtype": "Time",
     "default": DEFAULT_CUTOFF, "reqd": 1,
     "description": "From this time onwards a new Outward Request is dated tomorrow by default."},
    {"fieldname": "require_same_day_approval", "label": "Require Approval for Same-day After Cut-off",
     "fieldtype": "Check", "default": "1",
     "description": "When ticked, keeping today's date after the cut-off sends the request to "
                    "the approvers below. When unticked, today's date is simply allowed."},
    {"fieldname": "section_approvers", "fieldtype": "Section Break", "label": "Approvers"},
    {"fieldname": "approvers", "label": "Approvers", "fieldtype": "Table",
     "options": "Outward Request Approver",
     "description": "Users who can approve same-day requests made after the cut-off. "
                    "Requests they create themselves are approved automatically."},
]

REQUEST_FIELDS = [
    {"fieldname": "section_same_day_approval", "fieldtype": "Section Break",
     "label": "Same-day Approval", "collapsible": 1,
     "depends_on": "eval:doc.same_day_approval"},
    {"fieldname": "same_day_approval", "label": "Same-day Approval", "fieldtype": "Select",
     "options": "\nPending\nApproved\nRejected", "read_only": 1, "no_copy": 1,
     "in_list_view": 1, "in_standard_filter": 1,
     "description": "Set when the request is dated today after the cut-off time "
                    "(Outward Request Settings)"},
    {"fieldname": "approval_requested_on", "label": "Approval Requested On", "fieldtype": "Datetime",
     "read_only": 1, "no_copy": 1},
    {"fieldname": "column_break_approval", "fieldtype": "Column Break"},
    {"fieldname": "approved_by", "label": "Approved / Rejected By", "fieldtype": "Link",
     "options": "User", "read_only": 1, "no_copy": 1},
    {"fieldname": "approved_on", "label": "Approved / Rejected On", "fieldtype": "Datetime",
     "read_only": 1, "no_copy": 1},
    {"fieldname": "approval_remarks", "label": "Approval Remarks", "fieldtype": "Small Text",
     "read_only": 1, "no_copy": 1},
]


def execute():
    _ensure_doctype("Outward Request Approver", APPROVER_FIELDS, {
        "istable": 1,
        "editable_grid": 1,
    })
    _ensure_doctype("Outward Request Settings", SETTINGS_FIELDS, {
        "issingle": 1,
        "permissions": SETTINGS_PERMISSIONS,
    })
    _ensure_doctype("Outward Request", REQUEST_FIELDS, {})
    _seed_settings()


def _seed_settings():
    settings = frappe.get_single("Outward Request Settings")
    changed = False
    if not settings.same_day_cutoff_time:
        settings.same_day_cutoff_time = DEFAULT_CUTOFF
        settings.require_same_day_approval = 1
        changed = True
    if not settings.get("approvers"):
        for user in DEFAULT_APPROVERS:
            if frappe.db.exists("User", user):
                settings.append("approvers", {"user": user})
                changed = True
    if changed:
        settings.save(ignore_permissions=True)
