"""
pranera_knit/push.py
Phone / browser push notifications for the Knit App.

Delivery goes through Frappe's built-in Push Notification Relay
(frappe.push_notification.PushNotification). It's already enabled and
registered on erp.pranera.in: push_relay_server_url is set in site config
and Push Notification Settings holds the relay credentials. There are no
Firebase keys to manage here; the relay supplies the web config.

Project name: the relay keeps a Firebase setup per *project* (app). It is
known to serve "hrms" (Frappe HR uses it on this site); a new name like
"pranera_knit" only works if Frappe registers it on their relay. So the
project comes from site config `knit_push_project`, defaulting to "hrms".
The app and the server must use the same value; the app reads it from
api/push.get_push_config. A side effect of sharing "hrms" is that phones
which enabled Knit App notifications may also get Frappe HR notifications
(leave approvals etc.) for the same user, and vice versa.

Who gets what (wired in hooks.py / outward_request_events.py):
  * Roll Pick Assignment submitted     → the user it's assigned to
  * Outward Request created            → "NAP Warehouse User" role
  * Outward Request status changes     → the request's creator
  * Outward Request Completed          → "NAP Security" role (ready to load)
  * Vehicle Gate Entry: request added  → that request's creator (vehicle at gate)
  * Vehicle Gate Entry: departed       → creators of the requests it carried
  * Knit Down Approval posted         → "Knit Down Approver" role (production)
  * Knit Down Approved / Rejected     → whoever posted it (knitting), and
                                        the first approver on a two-level one
  * Knit Down Pending Final Approval  → the location's level-2 approvers

WhatsApp (whatsapp_alerts.py) is sent ONLY for Roll Pick Assignments, to
the assigned picker (send(..., whatsapp=True) below). Every other alert is
push-only. Meta caps how many business-initiated WhatsApp messages one
person receives (error 131049), so WhatsApp is kept for the one alert a
picker has to act on.

Sending never blocks or fails the document save: it's enqueued after
commit, and every error is logged instead of raised.
"""
import frappe
from frappe.utils import flt, get_url

DEFAULT_PROJECT = "hrms"
ICON = "/assets/pranera_knit/knit_app/icons/icon-192.png"
SKIP_USERS = {"Administrator", "Guest", None, ""}

OUTWARD_REQUEST_ROLES = ("NAP Warehouse User",)
SECURITY_ROLES = ("NAP Security",)
KNIT_DOWN_ROLES = ("Knit Down Approver",)


def project_name():
    return frappe.conf.get("knit_push_project") or DEFAULT_PROJECT


def is_enabled():
    try:
        return bool(frappe.db.get_single_value("Push Notification Settings", "enable_push_notification_relay")) \
            and bool(frappe.conf.get("push_relay_server_url"))
    except Exception:
        return False


def users_with_roles(roles, exclude=None):
    users = frappe.get_all(
        "Has Role",
        filters={"role": ["in", list(roles)], "parenttype": "User"},
        pluck="parent", distinct=True,
    )
    if not users:
        return []
    enabled = frappe.get_all(
        "User", filters={"name": ["in", users], "enabled": 1, "user_type": "System User"}, pluck="name"
    )
    skip = set(SKIP_USERS) | set(exclude or [])
    return [u for u in enabled if u not in skip]


def send(users, title, body, path="/knit-app", tag=None, ref=None, whatsapp=False, pick=None):
    """Queue a push to each user. `path` is the in-app route opened on tap;
    `ref` is (doctype, name) of the document the alert is about. With
    whatsapp=True the same alert also goes out on WhatsApp
    (whatsapp_alerts.py) — used only for the picker's Roll Pick Assignment."""
    users = sorted({u for u in (users or []) if u not in SKIP_USERS})
    if not users:
        return
    if whatsapp:
        try:
            from pranera_knit import whatsapp_alerts
            whatsapp_alerts.send(users, title, body, get_url(path), ref=ref, pick=pick)
        except Exception:
            frappe.log_error(title="Knit WhatsApp alert could not be queued")
    if not is_enabled():
        return
    frappe.enqueue(
        "pranera_knit.push.deliver",
        queue="short",
        enqueue_after_commit=True,
        users=users, title=title, body=body, link=get_url(path), tag=tag,
    )


def deliver(users, title, body, link, tag=None):
    from frappe.push_notification import PushNotification

    push = PushNotification(project_name())
    for user in users:
        try:
            push.send_notification_to_user(
                user, title, body, link=link, icon=get_url(ICON),
                data={"source": "pranera_knit", "tag": tag or ""},
            )
        except Exception:
            frappe.log_error(title=f"Knit push to {user} failed")


# ── Event handlers (hooks.py) ─────────────────────────────────────────────

def on_roll_pick_assignment_submit(doc, method=None):
    if not doc.get("assigned_to"):
        return
    target = doc.get("pick_qty")
    against = doc.get("work_order") or doc.get("sales_order") or doc.get("subcontracting_order") or ""
    parts = [f"{doc.pick_type} {against}".strip()]
    if target:
        parts.append(f"{target:g} kg")
    if doc.get("source_warehouse"):
        parts.append(f"from {doc.source_warehouse}")
    if doc.get("outward_request"):
        parts.append(f"for {doc.outward_request}")
    detail = ", ".join(parts)
    # The only alert that also goes out on WhatsApp, and only to the picker,
    # using the specific Utility template knit_pick_assigned.
    send([doc.assigned_to], "New pick assigned", f"{doc.name}: {detail}",
         "/knit-app/my-pick-orders", tag=f"rpa:{doc.name}", ref=("Roll Pick Assignment", doc.name),
         whatsapp=True, pick={"name": doc.name, "detail": detail})


def on_outward_request_insert(doc, method=None):
    source = f"WO {doc.work_order}" if doc.work_order else f"PO {doc.purchase_order}"
    send(users_with_roles(OUTWARD_REQUEST_ROLES, exclude=[doc.created_by]),
         "New Outward Request",
         f"{doc.name} → {doc.to_building} ({source}). Assign a roll pick.",
         f"/knit-app/outward-request?name={doc.name}", tag=f"or:{doc.name}", ref=("Outward Request", doc.name))


def outward_request_status_changed(name, old_status, new_status):
    """Called by outward_request_events.refresh_status when Status moves."""
    if (old_status or "") == (new_status or ""):
        return
    req = frappe.db.get_value("Outward Request", name, ["created_by", "to_building"], as_dict=True)
    if not req:
        return
    path = f"/knit-app/outward-request?name={name}"
    label = new_status or "back to Pending"
    send([req.created_by], f"Outward Request {label}",
         f"{name} → {req.to_building} is now {label}.", path, tag=f"or:{name}",
         ref=("Outward Request", name))
    if new_status == "Completed":
        send(users_with_roles(SECURITY_ROLES), "Ready to load",
             f"{name} → {req.to_building} is picked and transferred. Ready for the vehicle.",
             "/knit-app/vehicle-gate-entry", tag=f"or-ready:{name}", ref=("Outward Request", name))


def on_vehicle_gate_entry_update(doc, method=None):
    before = doc.get_doc_before_save()
    current = [r.outward_request for r in doc.get("outward_requests") or []]
    previous = {r.outward_request for r in (before.get("outward_requests") or [])} if before else set()

    added = [r for r in current if r not in previous]
    if added:
        for name, creator in _creators(added).items():
            send([creator], f"Vehicle at gate: {doc.vehicle_no}",
                 f"{doc.vehicle_no} ({doc.capacity}, {doc.driver_name}) is here to pick up {name}.",
                 f"/knit-app/outward-request?name={name}", tag=f"vge:{doc.name}:{name}",
                 ref=("Vehicle Gate Entry", doc.name))

    departed_now = doc.departure_datetime and not (before and before.departure_datetime)
    if departed_now and current:
        by_creator = {}
        for name, creator in _creators(current).items():
            by_creator.setdefault(creator, []).append(name)
        for creator, names in by_creator.items():
            send([creator], f"Vehicle departed: {doc.vehicle_no}",
                 f"{doc.vehicle_no} left with {', '.join(names)}.",
                 f"/knit-app/vehicle-gate-entry?name={doc.name}", tag=f"vge-out:{doc.name}",
                 ref=("Vehicle Gate Entry", doc.name))


def _creators(outward_requests):
    return {
        r.name: r.created_by
        for r in frappe.get_all("Outward Request", filters={"name": ["in", outward_requests]},
                                fields=["name", "created_by"])
        if r.created_by
    }


def _knit_down_detail(doc):
    if doc.get("knit_type") == "Collar Cuff":
        return (f"{doc.work_order} · {doc.workstation} · {doc.size or ''} · "
                f"N {flt(doc.no_of_needles):g} · C {flt(doc.no_of_course):g} · LL {doc.loop_length}")
    return f"{doc.work_order} · {doc.workstation} · GSM {flt(doc.gsm):g} · LL {doc.loop_length}"


def _knit_down_path(doc):
    page = "collar-cuff-knit-down" if doc.get("knit_type") == "Collar Cuff" else "knit-down"
    return f"/knit-app/{page}?name={doc.name}"


def on_knit_down_insert(doc, method=None):
    # An alert must never block saving the knit down itself.
    try:
        _knit_down_insert_alert(doc)
    except Exception:
        frappe.log_error(title=f"Knit down alert failed for {doc.name}")


def _knit_down_insert_alert(doc):
    # The approvers for this knit down's location (Knit Down Settings). If
    # none are set for it, every Knit Down Approver as before.
    from pranera_knit.knit_down_events import approvers_for
    everyone = users_with_roles(KNIT_DOWN_ROLES, exclude=[doc.requested_by])
    local = [u for u in everyone if u in approvers_for(doc.get("location"))]
    send(local or everyone,
         "Knit down ready for approval",
         f"{doc.name}: {_knit_down_detail(doc)} ({(doc.item_name or '').strip()[:60]})",
         _knit_down_path(doc), tag=f"kd:{doc.name}", ref=("Knit Down Approval", doc.name))


def on_knit_down_update(doc, method=None):
    try:
        _knit_down_decision_alert(doc)
    except Exception:
        frappe.log_error(title=f"Knit down alert failed for {doc.name}")


def _knit_down_decision_alert(doc):
    from pranera_knit.knit_down_events import FINAL, approvers_for
    if not doc.has_value_changed("status"):
        return
    if doc.status == FINAL:
        first = frappe.utils.get_fullname(doc.first_approved_by) if doc.get("first_approved_by") else ""
        body = f"{doc.name}: {_knit_down_detail(doc)} ({(doc.item_name or '').strip()[:60]})"
        if first:
            body += f" — approved at unit by {first}"
        if doc.get("first_approver_remarks"):
            body += f": {doc.first_approver_remarks}"
        send(sorted(approvers_for(doc.get("location"), level=2) - {doc.get("first_approved_by")}),
             "Knit down ready for final approval", body,
             _knit_down_path(doc), tag=f"kd:{doc.name}", ref=("Knit Down Approval", doc.name))
        return
    if doc.status not in ("Approved", "Rejected"):
        return
    body = f"{doc.name}: {_knit_down_detail(doc)}"
    if doc.approver_remarks:
        body += f" — {doc.approver_remarks}"
    to = [doc.requested_by]
    if doc.get("first_approved_by") and doc.first_approved_by not in to:
        to.append(doc.first_approved_by)
    send(to, f"Knit down {doc.status.lower()}", body,
         _knit_down_path(doc), tag=f"kd:{doc.name}", ref=("Knit Down Approval", doc.name))
