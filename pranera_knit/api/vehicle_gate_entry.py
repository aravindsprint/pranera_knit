"""
pranera_knit/api/vehicle_gate_entry.py
Whitelisted methods behind the knit-app "Vehicle Gate Entry" page.
Validation lives in vehicle_gate_entry_events.py.

Pick Up entries carry the Outward Requests the vehicle is collecting
(outward_requests child table). save_vehicle_gate_entry takes them as a
plain list of request names; search_outward_requests offers the ones not
already on another gate entry.
"""
import frappe
from frappe.utils import today

from pranera_knit.vehicle_gate_entry_events import LOCATION_EXTRAS

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
    capacity = frappe.get_meta("Vehicle Gate Entry").get_field("capacity").options or ""
    buildings = frappe.get_all("Building", filters={"disabled": 0},
                               pluck="name", order_by="building_name asc")
    return {
        "capacities": [c for c in capacity.split("\n") if c],
        "locations": [{"value": b, "label": b, "group": "Building"} for b in buildings]
                     + [{"value": x, "label": x, "group": "Other"} for x in LOCATION_EXTRAS],
    }


@frappe.whitelist()
def save_vehicle_gate_entry(name=None, outward_requests=None, **values):
    doc = frappe.get_doc("Vehicle Gate Entry", name) if name else frappe.new_doc("Vehicle Gate Entry")
    for key in EDITABLE:
        if key in values:
            doc.set(key, values[key] or None)
    if outward_requests is not None:
        if isinstance(outward_requests, str):
            outward_requests = frappe.parse_json(outward_requests)
        doc.set("outward_requests", [{"outward_request": r} for r in outward_requests or [] if r])
    if not doc.date:
        doc.date = today()
    doc.save()
    frappe.db.commit()
    return get_vehicle_gate_entry(doc.name)


@frappe.whitelist()
def mark_departed(name):
    """One-tap departure: stamps now() as departure time."""
    doc = frappe.get_doc("Vehicle Gate Entry", name)
    doc.departure_datetime = frappe.utils.now_datetime()
    doc.save()
    frappe.db.commit()
    return get_vehicle_gate_entry(doc.name)


@frappe.whitelist()
def get_vehicle_gate_entry(name):
    doc = frappe.get_doc("Vehicle Gate Entry", name)
    doc.check_permission("read")
    out = doc.as_dict()
    out["created_by_name"] = frappe.utils.get_fullname(doc.created_by) if doc.created_by else ""
    out["outward_requests"] = _request_details([r.outward_request for r in doc.outward_requests])
    return out


def _request_details(names):
    """Outward Request summaries in the given order — for the gate entry form."""
    if not names:
        return []
    found = {
        r.name: r for r in frappe.get_all(
            "Outward Request", filters={"name": ["in", names]},
            fields=["name", "date", "to_building", "work_order", "purchase_order",
                    "status", "request_status"],
        )
    }
    counts = dict(frappe.db.sql(
        """select parent, count(*) from `tabOutward Request Item`
           where parenttype = 'Outward Request' and parent in %(n)s group by parent""",
        {"n": tuple(names)},
    ))
    return [dict(found[n], item_count=counts.get(n, 0)) for n in names if n in found]


@frappe.whitelist()
def search_outward_requests(txt=None, gate_entry=None):
    """Outward Requests a Pick Up can take: any not already on a different
    Vehicle Gate Entry, newest first."""
    taken = set(frappe.get_all(
        "Vehicle Gate Entry Outward Request",
        filters={"parenttype": "Vehicle Gate Entry", "parent": ["!=", gate_entry or ""]},
        pluck="outward_request",
    ))
    or_filters = None
    if txt:
        like = f"%{txt}%"
        or_filters = {"name": ["like", like], "to_building": ["like", like],
                      "work_order": ["like", like], "purchase_order": ["like", like]}
    rows = frappe.get_list(
        "Outward Request",
        filters={"name": ["not in", list(taken) or [""]]}, or_filters=or_filters,
        fields=["name"], order_by="creation desc", limit_page_length=30,
    )
    return _request_details([r.name for r in rows])


@frappe.whitelist()
def list_vehicle_gate_entries(txt=None, state=None, limit=50):
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
    rows = frappe.get_list("Vehicle Gate Entry", filters=filters, or_filters=or_filters,
                           fields=LIST_FIELDS, order_by="creation desc",
                           limit_page_length=int(limit or 50))
    users = {r.created_by for r in rows if r.created_by}
    names = {u.name: u.full_name for u in frappe.get_all(
        "User", filters={"name": ["in", list(users) or [""]]}, fields=["name", "full_name"])}
    linked = {}
    if rows:
        for r in frappe.get_all(
            "Vehicle Gate Entry Outward Request",
            filters={"parenttype": "Vehicle Gate Entry", "parent": ["in", [x.name for x in rows]]},
            fields=["parent", "outward_request"], order_by="idx asc",
        ):
            linked.setdefault(r.parent, []).append(r.outward_request)
    for r in rows:
        r["created_by_name"] = names.get(r.created_by, r.created_by)
        r["outward_requests"] = linked.get(r.name, [])
    return rows
