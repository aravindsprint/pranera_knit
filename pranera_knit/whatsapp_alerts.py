"""
pranera_knit/whatsapp_alerts.py
WhatsApp copies of the Knit App notifications, sent through the
**whatsnext** app — the WhatsApp integration this site actually uses
(Whatsnext Settings → Meta Cloud API; the CRM lead alerts go out the same
way). frappe_whatsapp is installed too but no longer sends.

Sending: whatsnext.whatsnext.api.send_template_message(to, template,
parameters, reference_doctype, reference_name, automated=1) — the same
call whatsnext's own notification engine makes from background jobs. It
creates the Whatsnext Message record, calls Meta and stores the status /
error on that record, so every alert is visible in the Whatsnext inbox
and message log. Its app-user check only applies to direct HTTP calls,
not to internal calls like this one; the job still runs as Administrator
so template / document permissions of whoever triggered the alert can
never block the send.

Template: one generic Utility template, "knit_app_alert" (created and
submitted to Meta by patches/v1_7/add_whatsapp_alert_template.py):

    Pranera Knit App alert
    *{{1}}*        ← title, e.g. "New pick assigned"
    {{2}}          ← detail line
    Open in the app: {{3}}   ← link
    This is an automated message from Pranera ERP.

Nothing is sent until its approval_status is "Approved". Site config:
`knit_whatsapp_template` overrides the template name;
`knit_whatsapp_disabled: 1` switches WhatsApp off without touching push.

Recipients' numbers: the active Employee linked to the user
(cell_number), else User.mobile_no. Users with neither are skipped.

Called from pranera_knit.push.send. Runs in the background after commit;
failures are recorded on the Whatsnext Message (by whatsnext) or in the
Error Log, never raised.
"""
import re

import frappe

TEMPLATE_NAME = "knit_app_alert"
SEND = "whatsnext.whatsnext.api.send_template_message"


def template_name():
    return frappe.conf.get("knit_whatsapp_template") or TEMPLATE_NAME


def is_enabled():
    if frappe.conf.get("knit_whatsapp_disabled"):
        return False
    try:
        return frappe.db.get_value("Whatsnext Message Template", template_name(), "approval_status") == "Approved" \
            and bool(frappe.db.get_single_value("Whatsnext Settings", "meta_enabled"))
    except Exception:
        return False  # whatsnext not installed


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
    if not numbers:
        return
    params = {"1": _param(title, 60), "2": _param(body, 500), "3": _param(link, 300)}
    ref_doctype, ref_name = (ref or [None, None])
    send_template_message = frappe.get_attr(SEND)

    previous_user = frappe.session.user
    frappe.set_user("Administrator")
    try:
        for user in users:
            number = numbers.get(user)
            if not number:
                continue
            try:
                send_template_message(
                    to=number, template=template_name(), parameters=params,
                    reference_doctype=ref_doctype, reference_name=ref_name, automated=1,
                )
                frappe.db.commit()
            except Exception:
                frappe.db.rollback()
                frappe.log_error(title=f"Knit WhatsApp to {user} failed")
    finally:
        frappe.set_user(previous_user)
