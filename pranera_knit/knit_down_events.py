"""
pranera_knit/knit_down_events.py

Rules for Knit Down Approval (doctype from patches/v1_19/add_knit_down_approval.py,
collar / cuff fields from patches/v1_20/add_collar_cuff_knit_down.py).

Two kinds, one doctype (knit_type, set from the Work Order's operation):
  Fabric       operation KNITTING            Dia, Gauge, GSM, Loop Length
  Collar Cuff  COLLAR / CUFF KNITTING        Size, Needles, Course, Texture,
                                             Loop Length, Ply, Gauge
Each has its own Knit App page (knit-down / collar-cuff-knit-down).

Approval by location (patches/v1_22): a Knit Down Approver can only
approve / reject knit downs whose location (the Work Order's
custom_location, copied to the knit down) is one of theirs in Knit Down
Settings → Approver Locations. Knit downs with no location can only be
decided by a System Manager. System Manager can decide any.

Two levels (patches/v1_27): each Approver Locations row has an Approval
Level. At a location with any level-2 row (e.g. Pranera HO), a level-1
approval only moves the knit down to "Pending Final Approval" (first
approver / time / remarks kept in first_approved_*); one of the
location's level-2 approvers then approves or rejects it. Level 2 has no
GPS check. Rolls stay blocked until the final approval. Locations with
no level-2 row keep the single approval. System Manager can decide
either stage.

GPS (patches/v1_24): with "Require GPS" on in Knit Down Settings, a Knit
Down Approver's phone must also be within "GPS Range (metres)" (default
200) of the knit down's Location (Location → Latitude / Longitude) when
approving or rejecting. The app sends the position; the decision, the
position and the distance are saved on the knit down. System Manager is
exempt. Deciding from Desk (no position) is refused for approvers.

The flow
--------
Before bulk knitting a Work Order on a machine, the knitting team runs a
knit down (sample) and posts it: WO, machine, actual Dia / Gauge / GSM /
Loop Length and yarn %. The production team (role "Knit Down Approver")
approves or rejects it. A rejected knit down is not edited — the knitting
team corrects the machine and posts a new one, so every attempt stays on
record.

validate_knit_down
  * New records always start Pending, stamped with requested_by / _on.
  * Job Card and machine are kept consistent with the Work Order: a job
    card must belong to the WO; with only a machine, the WO's open job
    card on that machine is linked.
  * Required Dia / GG / GSM / LL are copied from the Work Order
    (required_dia, required_gg, required_gsm, required_ll) for the
    approver to compare against.
  * Yarn rows default to the BOM's yarns and %; actual % must total 100
    (±1).
  * Only one live (Pending or Approved) knit down per WO + machine.
  * Pending → Approved / Rejected only by a Knit Down Approver (or System
    Manager); a rejection needs a remark. Once decided, a knit down is
    closed: no further changes.

ensure_approved
  Called from api/job_card_submit.submit_roll_packing_list_v2: a fabric
  knitting job card (operation KNITTING, Work Order in Kgs, WO created on
  or after the "knit_down_required_from" default) can't submit its rolls
  until its WO + machine has an Approved knit down.
"""
import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, now_datetime

APPROVER_ROLE = "Knit Down Approver"
APPROVER_ROLES = {APPROVER_ROLE, "System Manager"}
KNIT_OPERATION = "KNITTING"
FABRIC = "Fabric"
COLLAR_CUFF = "Collar Cuff"
OPERATIONS_BY_TYPE = {
    FABRIC: (KNIT_OPERATION,),
    COLLAR_CUFF: ("COLLAR KNITTING", "CUFF KNITTING"),
}
PENDING = "Pending"
FINAL = "Pending Final Approval"
OPEN_STATUSES = (PENDING, FINAL)
LIVE_STATUSES = (PENDING, FINAL, "Approved")
CLOSED_STATUSES = ("Approved", "Rejected")
PERCENT_TOLERANCE = 1.0

# Knit down values the knitting team enters; frozen once decided.
ENTRY_FIELDS = ("work_order", "workstation", "job_card", "dia", "gauge", "gsm", "loop_length",
                "size", "no_of_needles", "no_of_course", "texture", "no_of_ply",
                "photo", "knitting_remarks")
# (Work Order field, Knit Down field) copied for the approver to compare.
SPEC_FIELDS = {
    FABRIC: (("required_dia", "required_dia"), ("required_gg", "required_gg"),
             ("required_gsm", "required_gsm"), ("required_ll", "required_ll")),
    COLLAR_CUFF: (("width", "required_size"), ("no_of_needles", "required_needles"),
                  ("no_of_course", "required_course"), ("no_of_ply", "required_ply"),
                  ("required_gg", "required_gg"), ("required_ll", "required_ll")),
}


def operations_for(knit_type):
    return OPERATIONS_BY_TYPE.get(knit_type or FABRIC, OPERATIONS_BY_TYPE[FABRIC])


def knit_type_of_operation(operation):
    op = (operation or "").strip().upper()
    for knit_type, ops in OPERATIONS_BY_TYPE.items():
        if op in ops:
            return knit_type
    return None


def knit_type_for(work_order):
    """Fabric / Collar Cuff from the Work Order's knitting operation, or None."""
    for op in frappe.get_all("Work Order Operation",
                             filters={"parent": work_order, "parenttype": "Work Order"},
                             pluck="operation", order_by="idx asc"):
        knit_type = knit_type_of_operation(op)
        if knit_type:
            return knit_type
    return None


SETTINGS = "Knit Down Settings"
BYPASS_ROLE = "System Manager"


def is_approver(user=None):
    """Has an approving role at all (Knit Down Approver or System Manager)."""
    return bool(APPROVER_ROLES & set(frappe.get_roles(user or frappe.session.user)))


def _approver_rows(filters):
    """Knit Down Settings → Approver Locations rows as {user, location, level}."""
    if not frappe.db.exists("DocType", "Knit Down Approver Location"):
        return []
    has_level = frappe.get_meta("Knit Down Approver Location").has_field("level")
    rows = frappe.get_all("Knit Down Approver Location", filters=dict(filters, parenttype=SETTINGS),
                          fields=["user", "location"] + (["level"] if has_level else []))
    for r in rows:
        r.level = cint(r.get("level")) or 1
    return rows


def approver_locations(user=None, level=None):
    """Locations this user approves knit downs for (Knit Down Settings),
    optionally only at one approval level."""
    rows = _approver_rows({"user": user or frappe.session.user})
    return {r.location for r in rows if level is None or r.level == level}


def needs_final_approval(location):
    """True when `location` has a level-2 (final) approver."""
    return bool(location) and any(r.level == 2 for r in _approver_rows({"location": location}))


def stage_level(status):
    """Approval level that decides a knit down in `status`."""
    return 2 if status == FINAL else 1


def can_approve(user=None, location=None, status=PENDING):
    """Can `user` decide a knit down at `location` that is in `status`?
    System Manager: always. Knit Down Approver: only at one of their
    locations, at the level for that stage (Pending → level 1, Pending
    Final Approval → level 2). No location on the knit down → no."""
    user = user or frappe.session.user
    roles = set(frappe.get_roles(user))
    if BYPASS_ROLE in roles:
        return True
    if APPROVER_ROLE not in roles or not location:
        return False
    return location in approver_locations(user, level=stage_level(status))


def gps_settings():
    if not frappe.db.exists("DocType", SETTINGS) or \
            not frappe.get_meta(SETTINGS).has_field("require_gps"):
        return frappe._dict(required=False, radius=200)
    s = frappe.get_cached_doc(SETTINGS)
    return frappe._dict(required=bool(s.get("require_gps")), radius=cint(s.get("gps_radius_m")) or 200)


def needs_gps(user=None):
    user = user or frappe.session.user
    return gps_settings().required and BYPASS_ROLE not in frappe.get_roles(user)


def distance_m(lat1, lon1, lat2, lon2):
    """Great-circle distance in metres (haversine)."""
    import math
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def check_gps(doc, gps):
    """Throws unless `gps` ({latitude, longitude, accuracy}) is within range of
    the knit down's Location. Saves the position and distance on `doc`."""
    settings = gps_settings()
    lat, lng = flt((gps or {}).get("latitude")), flt((gps or {}).get("longitude"))
    if not gps or (not lat and not lng):
        frappe.throw(_("Your location is needed to approve or reject a knit down. Allow location "
                       "access for the Knit App in your phone / browser and try again."),
                     title=_("Location Needed"))
    loc = frappe.db.get_value("Location", doc.location, ["latitude", "longitude"], as_dict=True) \
        if doc.get("location") else None
    if not loc or (not flt(loc.latitude) and not flt(loc.longitude)):
        frappe.throw(_("{0} has no GPS coordinates yet. Ask an admin to set Latitude / Longitude "
                       "on Location {0}.").format(doc.get("location") or _("This location")),
                     title=_("Location Not Set Up"))
    dist = distance_m(lat, lng, flt(loc.latitude), flt(loc.longitude))
    for f, v in (("decision_latitude", lat), ("decision_longitude", lng),
                 ("decision_accuracy_m", flt((gps or {}).get("accuracy"))),
                 ("decision_distance_m", round(dist))):
        if doc.meta.has_field(f):
            doc.set(f, v)
    if dist > settings.radius:
        frappe.throw(_("You are about {0} m from {1}. You must be within {2} m of the unit to "
                       "approve or reject this knit down.")
                     .format("{:,.0f}".format(dist), doc.location, settings.radius),
                     title=_("Not at the Unit"))
    return dist


def approvers_for(location, level=1):
    """Users who may decide a knit down at `location` at `level` (for alerts)."""
    if not location:
        return set()
    return {r.user for r in _approver_rows({"location": location}) if r.level == level}


# ── Validation ────────────────────────────────────────────────────────────

def validate_knit_down(doc, method=None):
    before = None if doc.is_new() else doc.get_doc_before_save()

    if before and before.status in CLOSED_STATUSES:
        if doc.status != before.status or _entry_changed(before, doc):
            frappe.throw(_("Knit Down {0} is already {1}. Post a new knit down instead.")
                         .format(doc.name, before.status))
        return
    if before and before.status == FINAL and _entry_changed(before, doc):
        frappe.throw(_("Knit Down {0} is already approved at the unit and waiting for final "
                       "approval; it can't be changed").format(doc.name))

    if doc.is_new():
        doc.status = "Pending"
        doc.requested_by = frappe.session.user
        doc.requested_on = now_datetime()
        doc.approved_by = doc.approved_on = doc.approver_remarks = None
        for f in ("first_approved_by", "first_approved_on", "first_approver_remarks"):
            if doc.meta.has_field(f):
                doc.set(f, None)

    _validate_work_order(doc)
    _link_job_card(doc)
    _copy_required_spec(doc)
    _validate_values(doc)
    _validate_yarns(doc)
    _validate_unique(doc)
    _validate_decision(doc, before)


def _entry_changed(before, doc):
    if any((before.get(f) or None) != (doc.get(f) or None) for f in ENTRY_FIELDS):
        return True
    old = [(r.item_code, flt(r.actual_percent)) for r in before.get("yarns") or []]
    new = [(r.item_code, flt(r.actual_percent)) for r in doc.get("yarns") or []]
    return old != new


def _validate_work_order(doc):
    wo = frappe.db.get_value("Work Order", doc.work_order,
                             ["docstatus", "status", "production_item", "item_name"], as_dict=True)
    if not wo or wo.docstatus != 1:
        frappe.throw(_("Work Order {0} is not submitted").format(doc.work_order))
    if doc.is_new() and wo.status in ("Stopped", "Closed", "Cancelled", "Completed"):
        frappe.throw(_("Work Order {0} is {1}").format(doc.work_order, wo.status))
    doc.production_item = wo.production_item
    doc.item_name = (wo.item_name or "").strip()
    if frappe.get_meta("Knit Down Approval").has_field("location"):
        doc.location = frappe.db.get_value("Work Order", doc.work_order, "custom_location") or None
    knit_type = knit_type_for(doc.work_order)
    if not knit_type:
        frappe.throw(_("Work Order {0} has no knitting operation").format(doc.work_order))
    doc.knit_type = knit_type


def _link_job_card(doc):
    if doc.job_card:
        jc = frappe.db.get_value("Job Card", doc.job_card, ["work_order", "workstation"], as_dict=True)
        if not jc or jc.work_order != doc.work_order:
            frappe.throw(_("Job Card {0} is not for Work Order {1}").format(doc.job_card, doc.work_order))
        if not doc.workstation:
            doc.workstation = jc.workstation
        return
    if not doc.workstation:
        frappe.throw(_("Machine is required"))
    doc.job_card = frappe.db.get_value(
        "Job Card",
        {"work_order": doc.work_order, "workstation": doc.workstation, "docstatus": ["<", 2]},
        "name", order_by="creation desc",
    )


def _copy_required_spec(doc):
    pairs = SPEC_FIELDS[doc.knit_type or FABRIC]
    meta = frappe.get_meta("Work Order")
    fields = [src for src, _dst in pairs if meta.has_field(src)]
    if not fields:
        return
    values = frappe.db.get_value("Work Order", doc.work_order, fields, as_dict=True) or {}
    for src, dst in pairs:
        if src in values:
            v = values[src]
            doc.set(dst, ("{:g}".format(flt(v)) if v not in (None, "") else None) if dst == "required_ll" else v)


def _validate_values(doc):
    # The app posts numbers as text ("163"); store real numbers so later
    # code (push alerts, comparisons) doesn't trip over a str.
    for field in ("dia", "gauge", "gsm", "no_of_needles", "no_of_course", "no_of_ply"):
        doc.set(field, flt(doc.get(field)))
    for field in ("size", "texture"):
        doc.set(field, (doc.get(field) or "").strip() or None)

    if doc.knit_type == COLLAR_CUFF:
        numbers = (("no_of_needles", _("No of Needles")), ("no_of_course", _("No of Course")),
                   ("no_of_ply", _("No of Ply")), ("gauge", _("Gauge")))
        texts = (("size", _("Size")), ("texture", _("Texture")))
    else:
        numbers = (("dia", _("Dia")), ("gauge", _("Gauge")), ("gsm", _("GSM")))
        texts = ()
    for field, label in numbers:
        if doc.get(field) <= 0:
            frappe.throw(_("{0} must be greater than 0").format(label))
    for field, label in texts:
        if not doc.get(field):
            frappe.throw(_("{0} is required").format(label))
    doc.loop_length = (doc.loop_length or "").strip()
    if not doc.loop_length:
        frappe.throw(_("Loop Length is required"))


def bom_yarns(work_order):
    """[{item_code, item_name, bom_percent}] from the Work Order's BOM."""
    bom = frappe.db.get_value("Work Order", work_order, "bom_no")
    if not bom:
        return []
    rows = frappe.get_all("BOM Item", filters={"parent": bom, "parenttype": "BOM"},
                          fields=["item_code", "item_name", "stock_qty", "qty"], order_by="idx asc")
    total = sum(flt(r.stock_qty or r.qty) for r in rows)
    return [{
        "item_code": r.item_code,
        "item_name": r.item_name,
        "bom_percent": flt(flt(r.stock_qty or r.qty) * 100 / total, 2) if total else 0,
    } for r in rows]


def _validate_yarns(doc):
    bom = {y["item_code"]: y for y in bom_yarns(doc.work_order)}
    if not doc.get("yarns"):
        for y in bom.values():
            doc.append("yarns", dict(y, actual_percent=y["bom_percent"]))
    if not doc.get("yarns"):
        frappe.throw(_("Add the yarn % for this knit down"))

    seen = set()
    for row in doc.yarns:
        if row.item_code in seen:
            frappe.throw(_("Yarn {0} is listed twice").format(row.item_code))
        seen.add(row.item_code)
        if flt(row.actual_percent) < 0:
            frappe.throw(_("Yarn % can't be negative ({0})").format(row.item_code))
        if row.item_code in bom:
            row.bom_percent = bom[row.item_code]["bom_percent"]
            row.item_name = row.item_name or bom[row.item_code]["item_name"]

    total = sum(flt(r.actual_percent) for r in doc.yarns)
    if abs(total - 100) > PERCENT_TOLERANCE:
        frappe.throw(_("Yarn % must add up to 100 (now {0})").format("{:g}".format(flt(total, 2))))


def _validate_unique(doc):
    other = frappe.db.get_value(
        "Knit Down Approval",
        {"work_order": doc.work_order, "workstation": doc.workstation,
         "status": ["in", LIVE_STATUSES], "name": ["!=", doc.name or ""]},
        ["name", "status"], as_dict=True,
    )
    if other:
        frappe.throw(_("{0} on {1} already has a {2} knit down ({3})")
                     .format(doc.work_order, doc.workstation, other.status.lower(), other.name))


def _validate_decision(doc, before):
    old_status = before.status if before else PENDING
    if doc.status == old_status:
        return
    allowed = {PENDING: (FINAL,) + CLOSED_STATUSES, FINAL: CLOSED_STATUSES}
    if doc.status not in allowed.get(old_status, ()):
        frappe.throw(_("Invalid status change {0} → {1}").format(old_status, doc.status))
    final_stage = old_status == FINAL
    level_2 = not final_stage and needs_final_approval(doc.get("location"))
    # A level-1 approval at a two-level location only clears the first
    # stage; "Approved" asked for there means "Pending Final Approval".
    if not final_stage and doc.status == "Approved" and level_2:
        doc.status = FINAL
    if doc.status == FINAL and not level_2:
        frappe.throw(_("{0} has no final approver set in Knit Down Settings")
                     .format(doc.get("location") or _("This location")))

    if not can_approve(location=doc.get("location"), status=old_status):
        who = _("a level-2 (final) approver") if final_stage else _("a {0}").format(APPROVER_ROLE)
        frappe.throw(_("You can't approve or reject knit downs for {0} at this stage. Ask {1} for "
                       "that location (Knit Down Settings) or a System Manager.")
                     .format(doc.get("location") or _("a Work Order with no location"), who),
                     frappe.PermissionError)
    if needs_gps() and not final_stage:
        # Position comes from the Knit App (api/knit_down._decide → flags.gps).
        # Final (level 2) approval can be given from anywhere.
        check_gps(doc, doc.flags.get("gps"))
    if doc.status == "Rejected" and not (doc.approver_remarks or "").strip():
        frappe.throw(_("Add a remark saying why the knit down is rejected"))
    if doc.status == FINAL:
        doc.first_approved_by = frappe.session.user
        doc.first_approved_on = now_datetime()
        doc.first_approver_remarks = doc.approver_remarks
        doc.approved_by = doc.approved_on = doc.approver_remarks = None
        return
    doc.approved_by = frappe.session.user
    doc.approved_on = now_datetime()


# ── Gate on roll submit ───────────────────────────────────────────────────

def is_required(job_card):
    """True when this job card needs an Approved knit down before its rolls
    can be submitted: fabric knitting (operation KNITTING, WO in Kgs) on a
    Work Order created on/after knit_down_required_from."""
    start = frappe.db.get_default("knit_down_required_from")
    if not start or not frappe.db.exists("DocType", "Knit Down Approval"):
        return False
    jc = frappe.db.get_value("Job Card", job_card, ["operation", "work_order"], as_dict=True)
    if not jc or (jc.operation or "").strip().upper() != KNIT_OPERATION:
        return False
    wo = frappe.db.get_value("Work Order", jc.work_order, ["stock_uom", "creation"], as_dict=True)
    if not wo or (wo.stock_uom or "").strip().lower() != "kgs":
        return False
    return getdate(wo.creation) >= getdate(start)


def latest_for(work_order, workstation):
    """Latest knit down for a WO + machine, as {name, status, ...} or None."""
    if not (work_order and workstation) or not frappe.db.exists("DocType", "Knit Down Approval"):
        return None
    return frappe.db.get_value(
        "Knit Down Approval", {"work_order": work_order, "workstation": workstation},
        ["name", "status", "approved_by", "approved_on", "approver_remarks", "requested_on"],
        as_dict=True, order_by="creation desc",
    )


def job_card_status(job_card):
    jc = frappe.db.get_value("Job Card", job_card, ["work_order", "workstation"], as_dict=True) or {}
    kd = latest_for(jc.get("work_order"), jc.get("workstation"))
    return {
        "required": is_required(job_card),
        "work_order": jc.get("work_order"),
        "workstation": jc.get("workstation"),
        "knit_down": kd,
        "approved": bool(kd and kd.status == "Approved"),
    }


def ensure_approved(job_card, work_order=None):
    if not is_required(job_card):
        return
    s = job_card_status(job_card)
    if s["approved"]:
        return
    kd = s["knit_down"]
    where = "{0} on {1}".format(s["work_order"], s["workstation"])
    if not kd:
        msg = _("Knit down not approved for {0}. Post the knit down in Knit App → Knit Down Approval "
                "and get it approved by production before submitting rolls.").format(where)
    elif kd.status == FINAL:
        msg = _("Knit down {0} for {1} is approved at the unit and waiting for final approval. "
                "Rolls can be submitted once it's finally approved.").format(kd.name, where)
    elif kd.status == "Pending":
        msg = _("Knit down {0} for {1} is waiting for production approval. "
                "Rolls can be submitted once it's approved.").format(kd.name, where)
    else:
        msg = _("Knit down {0} for {1} was rejected{2}. Post a new knit down and get it approved "
                "before submitting rolls.").format(
                    kd.name, where, ": " + kd.approver_remarks if kd.approver_remarks else "")
    frappe.throw(msg, title=_("Knit Down Approval Required"))
