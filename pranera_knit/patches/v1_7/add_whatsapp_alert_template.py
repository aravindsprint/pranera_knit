"""
pranera_knit/patches/v1_7/add_whatsapp_alert_template.py

Creates the "knit_app_alert" WhatsApp template used by
pranera_knit/whatsapp_alerts.py. Inserting a "WhatsApp Templates" doc
makes frappe_whatsapp submit it to Meta (after_insert), so this patch is
what files the template for approval. Messages start going out once Meta
marks it APPROVED (usually minutes, sometimes up to a day).

A Meta error (e.g. the WhatsApp account isn't reachable during migrate)
is logged, not raised: migrate must never fail over this. In that case
create the template by hand in WhatsApp Templates with the values below.

Meta rules this body follows: UTILITY category, no variable at the very
start or end, sample values without commas (frappe_whatsapp splits the
samples on ",").
"""
import frappe

TEMPLATE_NAME = "knit_app_alert"
BODY = (
    "Pranera Knit App alert\n\n"
    "*{{1}}*\n"
    "{{2}}\n\n"
    "Open in the app: {{3}}\n\n"
    "This is an automated message from Pranera ERP."
)
SAMPLES = ",".join([
    "New pick assigned",
    "RPA-0812 To Work Order 250 kg for OR/26/00012",
    "https://erp.pranera.in/knit-app/my-pick-orders",
])


def execute():
    if not frappe.db.exists("DocType", "WhatsApp Templates"):
        return  # frappe_whatsapp not installed
    if frappe.db.exists("WhatsApp Templates", {"template_name": TEMPLATE_NAME}):
        return

    language = "en" if frappe.db.exists("Language", "en") else None
    try:
        frappe.get_doc({
            "doctype": "WhatsApp Templates",
            "template_name": TEMPLATE_NAME,
            "category": "UTILITY",
            "language": language,
            "language_code": "en",
            "template": BODY,
            "sample_values": SAMPLES,
        }).insert(ignore_permissions=True)
    except Exception:
        frappe.db.rollback()
        frappe.log_error(title="pranera_knit: could not create WhatsApp template knit_app_alert")
