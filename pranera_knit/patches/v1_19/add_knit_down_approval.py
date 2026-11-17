"""
pranera_knit/patches/v1_19/add_knit_down_approval.py

Knit Down Approval: before bulk knitting, the knitting team runs a knit
down (sample) on the machine and the production team approves it. This
used to be a WhatsApp post per WO + machine ("Knit Down & Inline Approval"
group); now it's a record in the Knit App (page "knit-down").

Creates:
  "Knit Down Approval Yarn"  child: yarn item, BOM % and actual %
  "Knit Down Approval"       one knit down per Work Order + machine
                             (Workstation): required Dia / GG / GSM / LL
                             from the Work Order next to the actual values,
                             yarn %, photo, remarks, and the approval
                             (status Pending / Approved / Rejected,
                             approved_by, approved_on, approver_remarks).
  Role "Knit Down Approver"  production team; the only role (besides
                             System Manager) that can approve / reject.
  Knit App Page "knit-down"  via the v1_10 seeding (open to all by default).

Default "knit_down_required_from" = the day this patch runs. Fabric
knitting job cards of Work Orders created on/after that date can't be
submitted (rolls) without an Approved knit down for their WO + machine
(knit_down_events.ensure_approved). Older Work Orders already running on
the floor are not affected. Change it in System Console with
frappe.db.set_default("knit_down_required_from", "YYYY-MM-DD").

Validation / rules: knit_down_events.py. App API: api/knit_down.py.
Same app-owned, patch-created DocType pattern as v1_6. Re-running appends
any missing field.
"""
import frappe
from frappe.utils import today

from pranera_knit.patches.v1_10.add_knit_app_page_access import execute as seed_pages

MODULE = "Knit Module"
APPROVER_ROLE = "Knit Down Approver"

PERMISSIONS = [
    {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "report": 1, "export": 1},
    {"role": APPROVER_ROLE, "read": 1, "write": 1, "create": 1, "report": 1, "export": 1},
    {"role": "Knitting Supervisor", "read": 1, "write": 1, "create": 1, "report": 1},
    {"role": "Fabric Knitting Supervisor", "read": 1, "write": 1, "create": 1, "report": 1},
    {"role": "Collar Cuff Knitting Supervisor", "read": 1, "write": 1, "create": 1, "report": 1},
    {"role": "Knitting", "read": 1, "write": 1, "create": 1, "report": 1},
    {"role": "Production User", "read": 1, "report": 1},
    {"role": "Job Card Operator", "read": 1},
]

CHILD_FIELDS = [
    {"fieldname": "item_code", "label": "Yarn", "fieldtype": "Link", "options": "Item",
     "reqd": 1, "in_list_view": 1, "columns": 3},
    {"fieldname": "item_name", "label": "Yarn Name", "fieldtype": "Data", "read_only": 1,
     "fetch_from": "item_code.item_name", "in_list_view": 1, "columns": 4},
    {"fieldname": "bom_percent", "label": "BOM %", "fieldtype": "Percent", "read_only": 1,
     "in_list_view": 1, "columns": 1},
    {"fieldname": "actual_percent", "label": "Actual %", "fieldtype": "Percent", "reqd": 1,
     "in_list_view": 1, "columns": 2},
]

FIELDS = [
    {"fieldname": "work_order", "label": "Work Order", "fieldtype": "Link", "options": "Work Order",
     "reqd": 1, "in_list_view": 1, "in_standard_filter": 1, "search_index": 1},
    {"fieldname": "workstation", "label": "Machine", "fieldtype": "Link", "options": "Workstation",
     "reqd": 1, "in_list_view": 1, "in_standard_filter": 1},
    {"fieldname": "job_card", "label": "Job Card", "fieldtype": "Link", "options": "Job Card"},
    {"fieldname": "column_break_head", "fieldtype": "Column Break"},
    {"fieldname": "status", "label": "Status", "fieldtype": "Select", "options": "Pending\nApproved\nRejected",
     "default": "Pending", "read_only": 1, "in_list_view": 1, "in_standard_filter": 1, "bold": 1},
    {"fieldname": "production_item", "label": "Fabric", "fieldtype": "Link", "options": "Item",
     "read_only": 1, "fetch_from": "work_order.production_item"},
    {"fieldname": "item_name", "label": "Fabric Name", "fieldtype": "Data", "read_only": 1,
     "fetch_from": "work_order.item_name"},

    {"fieldname": "section_spec", "fieldtype": "Section Break", "label": "Knit Down"},
    {"fieldname": "required_dia", "label": "Required Dia", "fieldtype": "Float", "read_only": 1},
    {"fieldname": "dia", "label": "Dia", "fieldtype": "Float", "reqd": 1},
    {"fieldname": "required_gg", "label": "Required Gauge", "fieldtype": "Float", "read_only": 1},
    {"fieldname": "gauge", "label": "Gauge", "fieldtype": "Float", "reqd": 1},
    {"fieldname": "column_break_spec", "fieldtype": "Column Break"},
    {"fieldname": "required_gsm", "label": "Required GSM", "fieldtype": "Float", "read_only": 1},
    {"fieldname": "gsm", "label": "GSM", "fieldtype": "Float", "reqd": 1},
    {"fieldname": "required_ll", "label": "Required Loop Length", "fieldtype": "Data", "read_only": 1},
    {"fieldname": "loop_length", "label": "Loop Length (cm)", "fieldtype": "Data", "reqd": 1,
     "description": "e.g. 31 or 21/13 for two feeders"},

    {"fieldname": "section_yarn", "fieldtype": "Section Break", "label": "Yarn"},
    {"fieldname": "yarns", "label": "Yarn", "fieldtype": "Table", "options": "Knit Down Approval Yarn"},

    {"fieldname": "section_sample", "fieldtype": "Section Break", "label": "Sample"},
    {"fieldname": "photo", "label": "Photo", "fieldtype": "Attach Image"},
    {"fieldname": "column_break_sample", "fieldtype": "Column Break"},
    {"fieldname": "knitting_remarks", "label": "Knitting Remarks", "fieldtype": "Small Text"},

    {"fieldname": "section_approval", "fieldtype": "Section Break", "label": "Approval"},
    {"fieldname": "requested_by", "label": "Requested By", "fieldtype": "Link", "options": "User",
     "read_only": 1},
    {"fieldname": "requested_on", "label": "Requested On", "fieldtype": "Datetime", "read_only": 1},
    {"fieldname": "column_break_approval", "fieldtype": "Column Break"},
    {"fieldname": "approved_by", "label": "Approved / Rejected By", "fieldtype": "Link", "options": "User",
     "read_only": 1},
    {"fieldname": "approved_on", "label": "Approved / Rejected On", "fieldtype": "Datetime", "read_only": 1},
    {"fieldname": "approver_remarks", "label": "Approver Remarks", "fieldtype": "Small Text", "read_only": 1},
]


def execute():
    if not frappe.db.exists("Role", APPROVER_ROLE):
        frappe.get_doc({"doctype": "Role", "role_name": APPROVER_ROLE, "desk_access": 1}).insert(
            ignore_permissions=True)

    if not frappe.db.exists("DocType", "Knit Down Approval Yarn"):
        frappe.get_doc({
            "doctype": "DocType", "name": "Knit Down Approval Yarn", "module": MODULE,
            "custom": 1, "istable": 1, "editable_grid": 1, "fields": CHILD_FIELDS,
        }).insert(ignore_permissions=True)

    # Permissions reference these roles; skip any that don't exist on a site.
    perms = [p for p in PERMISSIONS if frappe.db.exists("Role", p["role"])]

    if not frappe.db.exists("DocType", "Knit Down Approval"):
        frappe.get_doc({
            "doctype": "DocType", "name": "Knit Down Approval", "module": MODULE, "custom": 1,
            "autoname": "KD/.YY./.#####", "naming_rule": "Expression (old style)",
            "track_changes": 1, "sort_field": "creation", "sort_order": "DESC",
            "search_fields": "work_order,workstation,status,item_name",
            "title_field": "item_name", "show_title_field_in_link": 0,
            "fields": FIELDS, "permissions": perms,
        }).insert(ignore_permissions=True)
    else:
        doc = frappe.get_doc("DocType", "Knit Down Approval")
        existing = {f.fieldname for f in doc.fields}
        for f in FIELDS:
            if f["fieldname"] not in existing:
                doc.append("fields", f)
        doc.save(ignore_permissions=True)

    if not frappe.db.get_default("knit_down_required_from"):
        frappe.db.set_default("knit_down_required_from", today())

    seed_pages()
