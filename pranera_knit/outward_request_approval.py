"""
pranera_knit/outward_request_approval.py

Approval rules for Outward Request (settings: "Outward Request Settings",
created by patches/v1_14; deadline + daily limit from patches/v1_21).

  * Deadline — a request for date D must be created before the cut-off
    time (default 23:30, server time) on the day BEFORE D. So by 11:30 PM
    tonight you can still order for tomorrow; after it, tomorrow's
    requests are late, and a request for today is always late.
  * Default date — the first date that isn't late: tomorrow, or the day
    after from the cut-off onwards.
  * No past dates — a new request, or an edit that changes the date, can't
    be dated before today.
  * Daily limit — fabric (Kgs) on all requests for the same date together
    may not exceed "Daily Kgs Limit" (default 15,000). Collar and cuff
    items (item group containing COLLAR / CUFF, counted in Pcs) don't
    count. Rejected requests don't count.
  * Approval — a late request, or one that takes its date over the daily
    limit, gets same_day_approval = "Pending" (approval_reason says why)
    and alerts the approvers. A Roll Pick Assignment can't be created from
    it until an approver approves it. A request created or changed by an
    approver is approved automatically. With "Require Approval…" unticked,
    a late date is simply allowed (the daily limit still applies).
    The check reruns when the date or the request's counted Kgs change.

The approval fields are only ever written here (validate, approve, reject);
values sent from the client or Desk are ignored.
"""
import datetime

import frappe
from frappe import _
from frappe.utils import add_days, flt, get_fullname, get_time, getdate, now_datetime

SETTINGS = "Outward Request Settings"
DEFAULT_CUTOFF = datetime.time(23, 30)
DEFAULT_DAILY_KGS_LIMIT = 15000.0
EXEMPT_GROUP_WORDS = ("COLLAR", "CUFF")
DEFAULT_APPROVERS = ("fabric@praneraservices.com",)

PENDING, APPROVED, REJECTED = "Pending", "Approved", "Rejected"
APPROVAL_FIELDS = ("same_day_approval", "approval_requested_on", "approved_by",
                   "approved_on", "approval_remarks", "approval_reason")


# ── Settings ──────────────────────────────────────────────────────────────

def get_settings():
    """{cutoff: time, require_approval: bool, approvers: [user]} — falls back
    to 15:00 / approval on / fabric@ until the v1_14 patch has run."""
    if not frappe.db.exists("DocType", SETTINGS):
        return frappe._dict(cutoff=DEFAULT_CUTOFF, require_approval=True,
                            daily_kgs_limit=DEFAULT_DAILY_KGS_LIMIT,
                            approvers=_enabled([u for u in DEFAULT_APPROVERS]))
    s = frappe.get_cached_doc(SETTINGS)
    cutoff = get_time(s.same_day_cutoff_time) if s.same_day_cutoff_time else DEFAULT_CUTOFF
    limit = s.get("daily_kgs_limit")
    return frappe._dict(
        cutoff=cutoff,
        require_approval=bool(s.require_same_day_approval),
        daily_kgs_limit=DEFAULT_DAILY_KGS_LIMIT if limit is None else flt(limit),
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


def deadline_for(date, settings=None):
    """Last moment to create a request for `date`: cut-off time the day before."""
    settings = settings or get_settings()
    return datetime.datetime.combine(getdate(add_days(date, -1)), settings.cutoff)


def is_late(date, now=None, settings=None):
    now = now or now_datetime()
    return now >= deadline_for(date, settings)


def default_request_date(now=None, settings=None):
    now = now or now_datetime()
    return add_days(now.date(), 2 if is_after_cutoff(now, settings) else 1)


def needs_same_day_approval(date, now=None, settings=None):
    """Kept for callers of the old name: is this date late (and approval on)?"""
    settings = settings or get_settings()
    return settings.require_approval and is_late(date, now, settings)


# ── Daily Kgs limit ───────────────────────────────────────────────────────

def _exempt_items(item_codes):
    """Collar / cuff items: item group contains COLLAR or CUFF."""
    if not item_codes:
        return set()
    rows = frappe.get_all("Item", filters={"name": ["in", list(item_codes)]},
                          fields=["name", "item_group"])
    return {r.name for r in rows
            if any(w in (r.item_group or "").upper() for w in EXEMPT_GROUP_WORDS)}


def counted_kgs(rows):
    """Kgs that count towards the daily limit: Kgs rows, collar / cuff excluded."""
    rows = [r for r in rows or [] if (r.get("stock_uom") or "").strip().lower() == "kgs"]
    exempt = _exempt_items({r.get("item_code") for r in rows if r.get("item_code")})
    return sum(flt(r.get("qty")) for r in rows if r.get("item_code") not in exempt)


def kgs_booked(date, exclude=None):
    """Counted Kgs on all other (not rejected) requests for `date`."""
    rows = frappe.db.sql("""
        SELECT i.item_code, i.qty, i.stock_uom
        FROM `tabOutward Request Item` i
        JOIN `tabOutward Request` r ON r.name = i.parent AND i.parenttype = 'Outward Request'
        WHERE r.date = %(date)s AND r.name != %(exclude)s
          AND IFNULL(r.same_day_approval, '') != 'Rejected'
    """, {"date": getdate(date), "exclude": exclude or ""}, as_dict=True)
    return counted_kgs(rows)


def fmt_kgs(value):
    return "{:,.0f}".format(flt(value))


def approval_reasons(doc, now=None, settings=None):
    """Why this request needs approval ([] = it doesn't)."""
    now = now or now_datetime()
    settings = settings or get_settings()
    reasons = []
    if settings.require_approval and is_late(doc.date, now, settings):
        reasons.append(_("Late: requests for {0} closed at {1} on {2}").format(
            frappe.format(doc.date, {"fieldtype": "Date"}), fmt_cutoff(settings),
            frappe.format(add_days(doc.date, -1), {"fieldtype": "Date"})))
    limit = flt(settings.daily_kgs_limit)
    if limit > 0:
        mine = counted_kgs(doc.get("items"))
        total = kgs_booked(doc.date, exclude=doc.name if not doc.is_new() else None) + mine
        if mine > 0 and total > limit:
            reasons.append(_("Over daily limit: {0} Kgs booked for {1} (limit {2} Kgs)").format(
                fmt_kgs(total), frappe.format(doc.date, {"fieldtype": "Date"}), fmt_kgs(limit)))
    return reasons


def fmt_cutoff(settings=None):
    settings = settings or get_settings()
    return settings.cutoff.strftime("%I:%M %p").lstrip("0")


# ── validate (called from outward_request_events.validate_outward_request) ─

def apply(doc):
    """Past-date check and approval state (late / over daily limit) for a
    request being saved."""
    before = None if doc.is_new() else doc.get_doc_before_save()
    date_changed = before is None or getdate(before.date) != getdate(doc.date)
    kgs_changed = before is not None and \
        round(counted_kgs(before.get("items")), 3) != round(counted_kgs(doc.get("items")), 3)

    if not date_changed and not kgs_changed:
        # Approval state only changes through this module — ignore anything
        # the client or Desk sent.
        for f in APPROVAL_FIELDS:
            doc.set(f, before.get(f))
        return

    now = now_datetime()
    if date_changed and getdate(doc.date) < now.date():
        frappe.throw(_("Date {0} is in the past. An Outward Request can only be dated today or later.")
                     .format(frappe.format(doc.date, {"fieldtype": "Date"})),
                     title=_("Invalid Date"))

    settings = get_settings()
    reasons = approval_reasons(doc, now, settings)
    if not date_changed and before.get("same_day_approval") == APPROVED and not reasons:
        # Approved earlier; this edit lowered the Kgs — nothing new to approve.
        for f in APPROVAL_FIELDS:
            doc.set(f, before.get(f))
        return
    for f in APPROVAL_FIELDS:
        doc.set(f, None)
    if not reasons:
        return
    doc.approval_reason = "\n".join(reasons)

    user = frappe.session.user
    if is_approver(user, settings):
        doc.same_day_approval = APPROVED
        doc.approval_requested_on = now
        doc.approved_by = user
        doc.approved_on = now
        doc.approval_remarks = _("Auto-approved: created by an approver")
        return

    if not settings.approvers:
        frappe.throw(_("This request needs approval ({0}), but no approver is set in "
                       "Outward Request Settings. Ask an admin to add one.")
                     .format("; ".join(reasons)), title=_("Approval Needed"))

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
    reason = (doc.get("approval_reason") or "").replace("\n", "; ")
    send(settings.approvers, "Outward Request approval needed",
         f"{who}: {doc.name} → {doc.to_building} ({source}) for "
         f"{frappe.format(doc.date, {'fieldtype': 'Date'})}. {reason}",
         f"/knit-app/outward-request?name={doc.name}", tag=f"or-approval:{doc.name}",
         ref=("Outward Request", doc.name))


# ── Gate for the pick flow ────────────────────────────────────────────────

def assert_cleared(doc):
    """Blocks a Roll Pick Assignment until a request needing approval is approved."""
    state = doc.get("same_day_approval")
    if state == PENDING:
        frappe.throw(_("Outward Request {0} is waiting for approval. A Roll Pick Assignment "
                       "can be created once an approver approves it.").format(doc.name),
                     title=_("Approval Pending"))
    if state == REJECTED:
        frappe.throw(_("Outward Request {0} was rejected by the approver. Change its date or "
                       "quantity to continue.").format(doc.name),
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
        frappe.throw(_("Only the approvers in Outward Request Settings can approve outward requests"),
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
    doc.add_comment("Info", _("Outward Request {0} by {1}{2}").format(
        state.lower(), get_fullname(user), f": {remarks}" if remarks else ""))

    from pranera_knit.push import send
    detail = f" — {remarks}" if remarks else ""
    send([current.created_by], f"Outward Request {state.lower()}",
         f"{name} → {current.to_building} was {state.lower()} by {get_fullname(user)}{detail}",
         f"/knit-app/outward-request?name={name}", tag=f"or-approval:{name}",
         ref=("Outward Request", name))
