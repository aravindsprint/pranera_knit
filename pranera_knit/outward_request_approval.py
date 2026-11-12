"""
pranera_knit/outward_request_approval.py

Same-day cut-off rules for Outward Request (settings: "Outward Request
Settings", created by patches/v1_14).

  * Default date — before the cut-off time (default 15:00, server time)
    a new request defaults to today; from the cut-off onwards, to tomorrow.
  * No past dates — a new request, or an edit that changes the date, can't
    be dated before today.
  * Same-day approval — dating a request TODAY at or after the cut-off sets
    same_day_approval = "Pending" and alerts the approvers. A Roll Pick
    Assignment can't be created from it until an approver approves it.
    A request created (or re-dated) by an approver is approved
    automatically. Moving the date to a later day clears the approval.
    With "Require Approval…" unticked, today's date is simply allowed.

The approval fields are only ever written here (validate, approve, reject);
values sent from the client or Desk are ignored.
"""
import datetime

import frappe
from frappe import _
from frappe.utils import add_days, get_fullname, get_time, getdate, now_datetime

SETTINGS = "Outward Request Settings"
DEFAULT_CUTOFF = datetime.time(15, 0)
DEFAULT_APPROVERS = ("fabric@praneraservices.com",)

PENDING, APPROVED, REJECTED = "Pending", "Approved", "Rejected"
APPROVAL_FIELDS = ("same_day_approval", "approval_requested_on", "approved_by",
                   "approved_on", "approval_remarks")


# ── Settings ──────────────────────────────────────────────────────────────

def get_settings():
    """{cutoff: time, require_approval: bool, approvers: [user]} — falls back
    to 15:00 / approval on / fabric@ until the v1_14 patch has run."""
    if not frappe.db.exists("DocType", SETTINGS):
        return frappe._dict(cutoff=DEFAULT_CUTOFF, require_approval=True,
                            approvers=_enabled([u for u in DEFAULT_APPROVERS]))
    s = frappe.get_cached_doc(SETTINGS)
    cutoff = get_time(s.same_day_cutoff_time) if s.same_day_cutoff_time else DEFAULT_CUTOFF
    return frappe._dict(
        cutoff=cutoff,
        require_approval=bool(s.require_same_day_approval),
        approvers=_enabled([r.user for r in (s.get("approvers") or []) if r.user]),
    )


def _enabled(users):
    if not users:
        return []
    return frappe.get_all("User", filters={"name": ["in", users], "enabled": 1}, pluck="name")


def is_approver(user=None, settings=None):
    user = user or frappe.session.user
    settings = settings or get_settings()
    return user in settings.approvers


# ── Date rules ────────────────────────────────────────────────────────────

def is_after_cutoff(now=None, settings=None):
    now = now or now_datetime()
    settings = settings or get_settings()
    return now.time() >= settings.cutoff


def default_request_date(now=None, settings=None):
    now = now or now_datetime()
    today = now.date()
    return add_days(today, 1) if is_after_cutoff(now, settings) else today


def needs_same_day_approval(date, now=None, settings=None):
    now = now or now_datetime()
    settings = settings or get_settings()
    return (settings.require_approval and getdate(date) == now.date()
            and is_after_cutoff(now, settings))


def fmt_cutoff(settings=None):
    settings = settings or get_settings()
    return settings.cutoff.strftime("%I:%M %p").lstrip("0")


# ── validate (called from outward_request_events.validate_outward_request) ─

def apply(doc):
    """Past-date check and same-day approval state for a request being saved."""
    before = None if doc.is_new() else doc.get_doc_before_save()
    date_changed = before is None or getdate(before.date) != getdate(doc.date)

    if not date_changed:
        # Approval state only changes through this module — ignore anything
        # the client or Desk sent.
        for f in APPROVAL_FIELDS:
            doc.set(f, before.get(f))
        return

    now = now_datetime()
    if getdate(doc.date) < now.date():
        frappe.throw(_("Date {0} is in the past. An Outward Request can only be dated today or later.")
                     .format(frappe.format(doc.date, {"fieldtype": "Date"})),
                     title=_("Invalid Date"))

    settings = get_settings()
    for f in APPROVAL_FIELDS:
        doc.set(f, None)
    if not needs_same_day_approval(doc.date, now, settings):
        return

    user = frappe.session.user
    if is_approver(user, settings):
        doc.same_day_approval = APPROVED
        doc.approval_requested_on = now
        doc.approved_by = user
        doc.approved_on = now
        doc.approval_remarks = _("Auto-approved: created by an approver")
        return

    if not settings.approvers:
        frappe.throw(_("Requests dated today after {0} need approval, but no approver is set in "
                       "Outward Request Settings. Choose tomorrow's date or ask an admin to add one.")
                     .format(fmt_cutoff(settings)), title=_("Approval Needed"))

    doc.same_day_approval = PENDING
    doc.approval_requested_on = now
    doc.flags.same_day_approval_requested = True


def on_update(doc, method=None):
    """Alert the approvers once the request asking for approval is saved."""
    if not doc.flags.get("same_day_approval_requested"):
        return
    doc.flags.same_day_approval_requested = False
    from pranera_knit.push import send

    settings = get_settings()
    who = get_fullname(doc.created_by or frappe.session.user)
    source = f"WO {doc.work_order}" if doc.work_order else f"PO {doc.purchase_order}"
    send(settings.approvers, "Same-day approval needed",
         f"{who}: {doc.name} → {doc.to_building} ({source}) for today, raised after {fmt_cutoff(settings)}.",
         f"/knit-app/outward-request?name={doc.name}", tag=f"or-approval:{doc.name}",
         ref=("Outward Request", doc.name))


# ── Gate for the pick flow ────────────────────────────────────────────────

def assert_cleared(doc):
    """Blocks a Roll Pick Assignment until a same-day request is approved."""
    state = doc.get("same_day_approval")
    if state == PENDING:
        frappe.throw(_("Outward Request {0} is waiting for same-day approval. A Roll Pick Assignment "
                       "can be created once an approver approves it.").format(doc.name),
                     title=_("Approval Pending"))
    if state == REJECTED:
        frappe.throw(_("Same-day approval for Outward Request {0} was rejected. Change its date to "
                       "tomorrow or later to continue.").format(doc.name),
                     title=_("Approval Rejected"))


def before_roll_pick_assignment_submit(doc, method=None):
    """Roll Pick Assignment hook — covers assignments submitted from Desk too."""
    if doc.get("outward_request"):
        assert_cleared(frappe.get_doc("Outward Request", doc.outward_request))


# ── Approve / reject ──────────────────────────────────────────────────────

def decide(name, approve, remarks=None):
    settings = get_settings()
    user = frappe.session.user
    if not is_approver(user, settings):
        frappe.throw(_("Only the approvers in Outward Request Settings can approve same-day requests"),
                     frappe.PermissionError)

    current = frappe.db.get_value("Outward Request", name,
                                  ["same_day_approval", "created_by", "to_building"], as_dict=True)
    if not current:
        frappe.throw(_("Outward Request {0} not found").format(name))
    if current.same_day_approval != PENDING:
        frappe.throw(_("Outward Request {0} is not waiting for approval").format(name))
    remarks = (remarks or "").strip()
    if not approve and not remarks:
        frappe.throw(_("Give a reason for rejecting"))

    state = APPROVED if approve else REJECTED
    frappe.db.set_value("Outward Request", name, {
        "same_day_approval": state,
        "approved_by": user,
        "approved_on": now_datetime(),
        "approval_remarks": remarks or None,
    }, update_modified=True)

    doc = frappe.get_doc("Outward Request", name)
    doc.add_comment("Info", _("Same-day request {0} by {1}{2}").format(
        state.lower(), get_fullname(user), f": {remarks}" if remarks else ""))

    from pranera_knit.push import send
    detail = f" — {remarks}" if remarks else ""
    send([current.created_by], f"Same-day request {state.lower()}",
         f"{name} → {current.to_building} was {state.lower()} by {get_fullname(user)}{detail}",
         f"/knit-app/outward-request?name={name}", tag=f"or-approval:{name}",
         ref=("Outward Request", name))
