"""
pranera_knit/api/push.py
What the Knit App needs to turn on push notifications (see pranera_knit/push.py).
"""
import frappe

from pranera_knit.push import is_enabled, project_name, send


@frappe.whitelist()
def get_push_config():
    return {
        "enabled": is_enabled(),
        "relay_url": frappe.conf.get("push_relay_server_url") or "",
        "project": project_name(),
    }


@frappe.whitelist()
def send_test_notification():
    """Sends a test push to the current user — the 'Send test' button."""
    if not is_enabled():
        frappe.throw("Push Notification Relay is not enabled on this site")
    send([frappe.session.user], "Knit App notifications are on",
         "You'll get alerts for picks, outward requests and vehicles here.",
         "/knit-app/home", tag="test")
    return {"queued": True}
