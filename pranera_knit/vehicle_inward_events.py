"""
pranera_knit/vehicle_inward_events.py

Validation for Vehicle Inward (doctype from patches/v1_6/add_vehicle_inward.py).

  * created_by is stamped once, on create.
  * vehicle_no is normalised to upper case without spaces ("tn 39 ab 1234"
    → "TN39AB1234") so the same vehicle always searches the same way.
  * mobile_no must be a 10-digit Indian mobile number (a leading +91 / 0
    is accepted and stripped).
  * Departure can't be before arrival.
  * Purpose decides which location applies: Pick Up → From, Drop → To.
    The other one is cleared, and the one in use must be a Building or one
    of LOCATION_EXTRAS.
"""
import re

import frappe
from frappe import _
from frappe.utils import get_datetime

LOCATION_EXTRAS = ("Purchase", "Subcontract")


def validate_location(value):
    return value in LOCATION_EXTRAS or bool(frappe.db.exists("Building", value))


def validate_vehicle_inward(doc, method=None):
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
