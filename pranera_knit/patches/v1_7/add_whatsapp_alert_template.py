"""
pranera_knit/patches/v1_7/add_whatsapp_alert_template.py

Creates the "knit_app_alert" template in **whatsnext** (Whatsnext Message
Template) and submits it to Meta through whatsnext's own
submit_template_to_meta, using the WhatsApp Business Account configured in
Whatsnext Settings. Used by pranera_knit/whatsapp_alerts.py; alerts start
once Meta approves it (usually minutes, sometimes up to a day) and whatsnext
records approval_status = "Approved".

A Meta / network error is logged, not raised — migrate must never fail
over this. The template is still saved as a Draft in that case; open it in
the Whatsnext app (Templates) and submit it from there.

Meta rules this body follows: Utility category, no variable at the very
start or end of the body, a sample value for every variable.
"""
import json

import frappe

TEMPLATE_NAME = "knit_app_alert"
BODY = (
    "Pranera Knit App alert\n\n"
    "*{{1}}*\n"
    "{{2}}\n\n"
    "Open in the app: {{3}}\n\n"
    "This is an automated message from Pranera ERP."
)
SAMPLES = {
    "1": "New pick assigned",
    "2": "RPA-0812: To Work Order 250 kg for OR/26/00012",
    "3": "https://erp.pranera.in/knit-app/my-pick-orders",
}


def execute():
    if not frappe.db.exists("DocType", "Whatsnext Message Template"):
        return  # whatsnext not installed

    if not frappe.db.exists("Whatsnext Message Template", TEMPLATE_NAME):
        frappe.get_doc({
            "doctype": "Whatsnext Message Template",
            "template_name": TEMPLATE_NAME,
            "provider": "Meta",
            "language": "en",
            "category": "Utility",
            "header_type": "None",
            "body": BODY,
            "variables_sample": json.dumps(SAMPLES),
            "approval_status": "Draft",
        }).insert(ignore_permissions=True)
        frappe.db.commit()

    status = frappe.db.get_value("Whatsnext Message Template", TEMPLATE_NAME,
                                 ["approval_status", "meta_template_id"], as_dict=True)
    if status.meta_template_id or status.approval_status in ("Pending", "Approved"):
        return

    try:
        submit = frappe.get_attr("whatsnext.whatsnext.api.submit_template_to_meta")
        submit(TEMPLATE_NAME)
        frappe.db.commit()
    except Exception:
        frappe.db.rollback()
        frappe.log_error(title="pranera_knit: could not submit WhatsApp template knit_app_alert to Meta")
