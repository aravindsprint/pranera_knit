"""
pranera_knit/patches/v1_21/outward_request_deadline_and_daily_limit.py

Outward Request: previous-day deadline and daily Kgs limit
(rules in pranera_knit/outward_request_approval.py).

  * "Same-day Cut-off Time" now means the deadline on the day BEFORE the
    request date; relabelled and set to 23:30 (only if still the old 15:00
    default — a time an admin chose on purpose is kept).
  * New setting "Daily Kgs Limit" (default 15,000; 0 = no limit): fabric
    Kgs on all requests for one date together. Collar / cuff not counted.
  * New Outward Request field approval_reason: why approval is needed
    (late, over the daily limit, or both).
  * The "Same-day Approval" section and field are relabelled "Approval".
"""
import frappe

from pranera_knit.patches.v1_5.add_outward_request import _ensure_doctype

SETTINGS = "Outward Request Settings"

SETTINGS_FIELDS = [
    {"fieldname": "daily_kgs_limit", "label": "Daily Kgs Limit", "fieldtype": "Float",
     "default": "15000", "insert_after": "require_same_day_approval",
     "description": "Fabric Kgs on all Outward Requests for the same date together. A request that "
                    "goes over it needs approval. Collar and cuff items are not counted. 0 = no limit."},
]

REQUEST_FIELDS = [
    {"fieldname": "approval_reason", "label": "Approval Reason", "fieldtype": "Small Text",
     "read_only": 1, "no_copy": 1, "insert_after": "approval_requested_on"},
]

LABELS = {
    SETTINGS: {
        "same_day_cutoff_time": ("Order Deadline (day before)",
                                 "A request for a date must be created before this time on the day "
                                 "before. Later requests need approval. Default 11:30 PM."),
        "require_same_day_approval": ("Require Approval for Late Requests",
                                      "When ticked, a request made after the deadline is sent to the "
                                      "approvers below. When unticked, it's simply allowed."),
        "approvers": (None, "Users who approve late requests and requests over the daily Kgs limit. "
                            "Requests they create themselves are approved automatically."),
    },
    "Outward Request": {
        "section_same_day_approval": ("Approval", None),
        "same_day_approval": ("Approval", "Set when the request is late or goes over the daily Kgs "
                                          "limit (Outward Request Settings)"),
    },
}


def execute():
    if not frappe.db.exists("DocType", SETTINGS):
        return
    _ensure_doctype(SETTINGS, _plain(SETTINGS_FIELDS), {})
    _ensure_doctype("Outward Request", _plain(REQUEST_FIELDS), {})
    _place_after(SETTINGS, SETTINGS_FIELDS)
    _place_after("Outward Request", REQUEST_FIELDS)

    for doctype, fields in LABELS.items():
        doc = frappe.get_doc("DocType", doctype)
        for f in doc.fields:
            if f.fieldname in fields:
                label, description = fields[f.fieldname]
                if label:
                    f.label = label
                if description:
                    f.description = description
            if doctype == SETTINGS and f.fieldname == "same_day_cutoff_time":
                f.default = "23:30:00"
        doc.save(ignore_permissions=True)

    settings = frappe.get_single(SETTINGS)
    changed = False
    if str(settings.same_day_cutoff_time or "") in ("", "15:00:00", "15:00"):
        settings.same_day_cutoff_time = "23:30:00"
        changed = True
    if settings.get("daily_kgs_limit") in (None, ""):
        settings.daily_kgs_limit = 15000
        changed = True
    if changed:
        settings.save(ignore_permissions=True)
    frappe.clear_cache(doctype=SETTINGS)


def _plain(fields):
    return [{k: v for k, v in f.items() if k != "insert_after"} for f in fields]


def _place_after(doctype, fields):
    """Move newly added fields to sit after their insert_after field."""
    doc = frappe.get_doc("DocType", doctype)
    moved = False
    for spec in fields:
        rows = {f.fieldname: f for f in doc.fields}
        row, after = rows.get(spec["fieldname"]), rows.get(spec.get("insert_after"))
        if not row or not after or doc.fields.index(row) == doc.fields.index(after) + 1:
            continue
        doc.fields.remove(row)
        doc.fields.insert(doc.fields.index(after) + 1, row)
        moved = True
    if moved:
        for i, f in enumerate(doc.fields, start=1):
            f.idx = i
        doc.save(ignore_permissions=True)
