"""
pranera_knit/api/vehicle_inward.py
Whitelisted methods behind the knit-app "Vehicle Inward" page.
Validation lives in vehicle_inward_events.py.
"""
import frappe
from frappe.utils import today

from pranera_knit.vehicle_inward_events import LOCATION_EXTRAS

EDITABLE = ("date", "vehicle_no", "driver_name", "mobile_no", "capacity",
            "arrival_datetime", "departure_datetime", "purpose",
            "from_location", "to_location")

LIST_FIELDS = ["name", "date", "vehicle_no", "driver_name", "mobile_no", "capacity",
               "arrival_datetime", "departure_datetime", "purpose",
               "from_location", "to_location", "created_by"]


@frappe.whitelist()
def get_form_options():
    """Capacity choices (from the DocType, so Desk and the app always match)
    and From / To choices: every enabled Building plus Purchase / Subcontract."""
    capacity = frappe.get_meta("Vehicle Inward").get_field("capacity").options or ""
    buildings = frappe.get_all("Building", filters={"disabled": 0},
                               pluck="name", order_by="building_name asc")
    return {
        "capacities": [c for c in capacity.split("\n") if c],
        "locations": [{"value": b, "label": b, "group": "Building"} for b in buildings]
                     + [{"value": x, "label": x, "group": "Other"} for x in LOCATION_EXTRAS],
    }


@frappe.whitelist()
def save_vehicle_inward(name=None, **values):
    doc = frappe.get_doc("Vehicle Inward", name) if name else frappe.new_doc("Vehicle Inward")
    for key in EDITABLE:
        if key in values:
            doc.set(key, values[key] or None)
    if not doc.date:
        doc.date = today()
    doc.save()
    frappe.db.commit()
    return get_vehicle_inward(doc.name)


@frappe.whitelist()
def mark_departed(name):
    """One-tap departure: stamps now() as departure time."""
    doc = frappe.get_doc("Vehicle Inward", name)
    doc.departure_datetime = frappe.utils.now_datetime()
    doc.save()
    frappe.db.commit()
    return get_vehicle_inward(doc.name)


@frappe.whitelist()
def get_vehicle_inward(name):
    doc = frappe.get_doc("Vehicle Inward", name)
    doc.check_permission("read")
    out = doc.as_dict()
    out["created_by_name"] = frappe.utils.get_fullname(doc.created_by) if doc.created_by else ""
    return out


@frappe.whitelist()
def list_vehicle_inwards(txt=None, state=None, limit=50):
    """state: "" (all) | "inside" (no departure yet) | "departed"."""
    filters = {}
    if state == "inside":
        filters["departure_datetime"] = ["is", "not set"]
    elif state == "departed":
        filters["departure_datetime"] = ["is", "set"]
    or_filters = None
    if txt:
        like = f"%{txt}%"
        or_filters = {"name": ["like", like], "vehicle_no": ["like", like.replace(" ", "")],
                      "driver_name": ["like", like], "mobile_no": ["like", like],
                      "from_location": ["like", like], "to_location": ["like", like]}
    rows = frappe.get_list("Vehicle Inward", filters=filters, or_filters=or_filters,
                           fields=LIST_FIELDS, order_by="creation desc",
                           limit_page_length=int(limit or 50))
    users = {r.created_by for r in rows if r.created_by}
    names = {u.name: u.full_name for u in frappe.get_all(
        "User", filters={"name": ["in", list(users) or [""]]}, fields=["name", "full_name"])}
    for r in rows:
        r["created_by_name"] = names.get(r.created_by, r.created_by)
    return rows
