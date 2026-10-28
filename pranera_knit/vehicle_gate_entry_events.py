"""
pranera_knit/vehicle_gate_entry_events.py

Validation for Vehicle Gate Entry (doctype from patches/v1_6/add_vehicle_gate_entry.py).

  * created_by is stamped once, on create.
  * vehicle_no is normalised to upper case without spaces ("tn 39 ab 1234"
    → "TN39AB1234") so the same vehicle always searches the same way.
  * mobile_no must be a 10-digit Indian mobile number (a leading +91 / 0
    is accepted and stripped).
  * Departure can't be before arrival.
  * Purpose decides which location applies: Pick Up → From, Drop → To.
    The other one is cleared, and the one in use must be a Building or one
    of LOCATION_EXTRAS.
  * outward_requests (Pick Up only — cleared for a Drop): no duplicates,
    and an Outward Request can only be on one Vehicle Gate Entry, so the
    request always points at a single vehicle.
"""
import re

import frappe
from frappe import _
from frappe.utils import get_datetime

LOCATION_EXTRAS = ("Purchase", "Subcontract")


def validate_location(value):
    return value in LOCATION_EXTRAS or bool(frappe.db.exists("Building", value))


def validate_vehicle_gate_entry(doc, method=None):
    if doc.is_new() and not doc.created_by:
        doc.created_by = frappe.session.user

    doc.vehicle_no = re.sub(r"[\s-]+", "", doc.vehicle_no or "").upper()
    if not doc.vehicle_no:
        frappe.throw(_("Vehicle No is required"))

    digits = re.sub(r"\D", "", doc.mobile_no or "")
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if not re.fullmatch(r"[6-9]\d{9}", digits):
        frappe.throw(_("Mobile No must be a 10-digit mobile number"))
    doc.mobile_no = digits

    if doc.departure_datetime and doc.arrival_datetime and \
            get_datetime(doc.departure_datetime) < get_datetime(doc.arrival_datetime):
        frappe.throw(_("Departure can't be before Arrival"))

    if doc.purpose == "Pick Up":
        doc.to_location = None
        field, label = "from_location", _("From")
    elif doc.purpose == "Drop":
        doc.from_location = None
        field, label = "to_location", _("To")
    else:
        frappe.throw(_("Purpose must be Pick Up or Drop"))

    value = doc.get(field)
    if not value:
        frappe.throw(_("{0} is required for {1}").format(label, doc.purpose))
    if not validate_location(value):
        frappe.throw(_("{0}: '{1}' is not a Building, Purchase or Subcontract").format(label, value))

    _validate_outward_requests(doc)


def _validate_outward_requests(doc):
    if doc.purpose != "Pick Up":
        doc.set("outward_requests", [])
        return

    seen = set()
    for row in doc.get("outward_requests") or []:
        if not row.outward_request:
            frappe.throw(_("Row {0}: select an Outward Request").format(row.idx))
        if row.outward_request in seen:
            frappe.throw(_("Outward Request {0} is added twice").format(row.outward_request))
        seen.add(row.outward_request)
    if not seen:
        return

    taken = frappe.get_all(
        "Vehicle Gate Entry Outward Request",
        filters={"parenttype": "Vehicle Gate Entry", "outward_request": ["in", list(seen)],
                 "parent": ["!=", doc.name or ""]},
        fields=["outward_request", "parent"], limit=1,
    )
    if taken:
        vehicle = frappe.db.get_value("Vehicle Gate Entry", taken[0].parent, "vehicle_no")
        frappe.throw(_("Outward Request {0} is already on Vehicle Gate Entry {1} ({2})")
                     .format(taken[0].outward_request, taken[0].parent, vehicle))


def vehicles_for_outward_requests(names):
    """{outward_request: [gate entry summary, ...]} — used by
    api/outward_request.py. Safe before the v1_6 patch has run."""
    names = [n for n in (names or []) if n]
    if not names or not frappe.db.exists("DocType", "Vehicle Gate Entry Outward Request"):
        return {}
    rows = frappe.get_all(
        "Vehicle Gate Entry Outward Request",
        filters={"parenttype": "Vehicle Gate Entry", "outward_request": ["in", names]},
        fields=["outward_request", "parent"],
    )
    if not rows:
        return {}
    entries = {
        e.name: e for e in frappe.get_all(
            "Vehicle Gate Entry",
            filters={"name": ["in", list({r.parent for r in rows})]},
            fields=["name", "vehicle_no", "driver_name", "mobile_no", "capacity",
                    "expected_arrival_datetime", "arrival_datetime", "departure_datetime"],
        )
    }
    out = {}
    for r in rows:
        if r.parent in entries:
            out.setdefault(r.outward_request, []).append(entries[r.parent])
    return out
