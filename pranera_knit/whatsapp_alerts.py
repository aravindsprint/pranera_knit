"""
pranera_knit/whatsapp_alerts.py
WhatsApp copies of the Knit App notifications, sent through the
frappe_whatsapp app that's already live on this site (the same path the
CRM lead alerts use: insert an Outgoing "WhatsApp Message" with an
approved template; frappe_whatsapp calls Meta in before_insert).

Template: one generic UTILITY template, "knit_app_alert" (created by
patches/v1_7/add_whatsapp_alert_template.py, which submits it to Meta):

    Pranera Knit App alert
    *{{1}}*        ← title, e.g. "New pick assigned"
    {{2}}          ← detail line
    Open in the app: {{3}}   ← link
    This is an automated message from Pranera ERP.

The template doc name can be overridden with site config
`knit_whatsapp_template`; set `knit_whatsapp_disabled: 1` to switch
WhatsApp off without touching push. Nothing is sent until the template's
status is APPROVED (frappe_whatsapp's webhook / "Fetch templates" keeps
that in sync with Meta).

Recipients' numbers: the active Employee linked to the user
(cell_number), else User.mobile_no. Users with neither are skipped.
Numbers are normalised to 91XXXXXXXXXX for 10-digit Indian mobiles.

Called from pranera_knit.push.send, so every push event also goes out on
WhatsApp. Runs in the background after commit; every failure is logged to
the Error Log and never raised.
"""
import json
import re

import frappe

TEMPLATE_NAME = "knit_app_alert"


def template_name():
    """WhatsApp Templates doc name. frappe_whatsapp names templates
    "<template_name>-<language_code>", but the code can be blank at naming
    time (e.g. "crm_lead_status_update_v2-"), so look it up instead."""
    if frappe.conf.get("knit_whatsapp_template"):
        return frappe.conf.get("knit_whatsapp_template")
    return frappe.db.get_value("WhatsApp Templates", {"template_name": TEMPLATE_NAME}, "name")


def is_enabled():
    if frappe.conf.get("knit_whatsapp_disabled"):
        return False
    try:
        name = template_name()
        return bool(name) and frappe.db.get_value("WhatsApp Templates", name, "status") == "APPROVED"
    except Exception:
        return False  # frappe_whatsapp not installed


def normalise_mobile(raw):
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if len(digits) == 10 and digits[0] in "6789":
        return "91" + digits
    if len(digits) == 12 and digits.startswith("91"):
        return digits
    return digits if len(digits) >= 11 else None  # other countries already carry a code


def mobiles_for(users):
    users = [u for u in users if u]
    if not users:
        return {}
    out = {}
    for e in frappe.get_all("Employee", filters={"user_id": ["in", users], "status": "Active"},
                            fields=["user_id", "cell_number"]):
        if e.cell_number and e.user_id not in out:
            out[e.user_id] = e.cell_number
    missing = [u for u in users if u not in out]
    if missing:
        for u in frappe.get_all("User", filters={"name": ["in", missing]}, fields=["name", "mobile_no"]):
            if u.mobile_no:
                out[u.name] = u.mobile_no
    return {u: n for u, n in ((u, normalise_mobile(m)) for u, m in out.items()) if n}


def _param(text, limit):
    # Meta rejects template parameters with newlines, tabs or 4+ spaces.
    text = re.sub(r"[\r\n\t]+", " ", str(text or ""))
    text = re.sub(r" {4,}", "   ", text).strip()
    return text[:limit] or "-"


def send(users, title, body, link, ref=None):
    if not users or not is_enabled():
        return
    frappe.enqueue(
        "pranera_knit.whatsapp_alerts.deliver",
        queue="short",
        enqueue_after_commit=True,
        users=sorted(set(users)), title=title, body=body, link=link, ref=list(ref) if ref else None,
    )


def deliver(users, title, body, link, ref=None):
    if not is_enabled():
        return
    numbers = mobiles_for(users)
    params = json.dumps({"1": _param(title, 60), "2": _param(body, 500), "3": _param(link, 300)})
    ref_doctype, ref_name = (ref or [None, None])
    for user in users:
        number = numbers.get(user)
        if not number:
            continue
        try:
            frappe.get_doc({
                "doctype": "WhatsApp Message",
                "type": "Outgoing",
                "to": number,
                "message_type": "Template",
                "content_type": "text",
                "template": template_name(),
                "body_param": params,
                "reference_doctype": ref_doctype or "User",
                "reference_name": ref_name or user,
            }).insert(ignore_permissions=True)
            frappe.db.commit()
        except Exception:
            frappe.db.rollback()
            frappe.log_error(title=f"Knit WhatsApp to {user} failed")
