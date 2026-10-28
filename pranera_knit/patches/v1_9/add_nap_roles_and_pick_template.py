"""
pranera_knit/patches/v1_9/add_nap_roles_and_pick_template.py

1. Roles for the Knit App alerts (pranera_knit/push.py):
     "NAP Warehouse User" → gets the "New Outward Request" push
     "NAP Security"       → gets the "Ready to load" push
   and assigns them to the users in ROLE_USERS (skipped if a user doesn't
   exist). Adding/removing people later is done the normal way: User →
   Roles in Desk; the alerts pick up whoever has the role at send time.

2. WhatsApp template "knit_pick_assigned" (Utility) for the Roll Pick
   Assignment alert, submitted to Meta through whatsnext. It's worded as a
   task notification for one specific pick so Meta keeps it in the Utility
   category (Utility is not subject to the per-user cap that rejected most
   of the generic knit_app_alert messages, error 131049).
   pranera_knit/whatsapp_alerts.py uses it once it's Approved and falls back
   to knit_app_alert until then.

Meta / network errors are logged, not raised; the template then stays a
Draft in Whatsnext → Templates and can be submitted from there.
"""
import json

import frappe

ROLES = ("NAP Warehouse User", "NAP Security")
ROLE_USERS = {
    "NAP Warehouse User": ["praveen_d@pss.com", "raghunath@praneraservices.com"],
    "NAP Security": ["security_nap_wh@pss.com"],
}

PICK_TEMPLATE = "knit_pick_assigned"
PICK_BODY = (
    "Hello {{1}},\n\n"
    "Pick order {{2}} has been assigned to you.\n"
    "Details: {{3}}\n\n"
    "Please complete the pick in the Knit App: {{4}}\n\n"
    "Pranera Knit"
)
PICK_SAMPLES = {
    "1": "Ravi",
    "2": "RPA-1030",
    "3": "From Work Order WO/26/12317, 250 Kgs",
    "4": "https://erp.pranera.in/knit-app/my-pick-orders",
}


def execute():
    _roles()
    _pick_template()


def _roles():
    for role in ROLES:
        if not frappe.db.exists("Role", role):
            frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(ignore_permissions=True)
    for role, users in ROLE_USERS.items():
        for user in users:
            if not frappe.db.exists("User", user):
                continue
            doc = frappe.get_doc("User", user)
            if role not in {r.role for r in doc.roles}:
                doc.append("roles", {"role": role})
                doc.save(ignore_permissions=True)
    frappe.db.commit()


def _pick_template():
    if not frappe.db.exists("DocType", "Whatsnext Message Template"):
        return
    if not frappe.db.exists("Whatsnext Message Template", PICK_TEMPLATE):
        frappe.get_doc({
            "doctype": "Whatsnext Message Template",
            "template_name": PICK_TEMPLATE,
            "provider": "Meta",
            "language": "en",
            "category": "Utility",
            "header_type": "None",
            "body": PICK_BODY,
            "variables_sample": json.dumps(PICK_SAMPLES),
            "approval_status": "Draft",
        }).insert(ignore_permissions=True)
        frappe.db.commit()

    t = frappe.db.get_value("Whatsnext Message Template", PICK_TEMPLATE,
                            ["approval_status", "meta_template_id"], as_dict=True)
    if t.meta_template_id or t.approval_status in ("Pending", "Approved"):
        return
    try:
        frappe.get_attr("whatsnext.whatsnext.api.submit_template_to_meta")(PICK_TEMPLATE)
        frappe.db.commit()
    except Exception:
        frappe.db.rollback()
        frappe.log_error(title="pranera_knit: could not submit WhatsApp template knit_pick_assigned to Meta")
