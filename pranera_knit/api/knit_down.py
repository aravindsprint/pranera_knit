"""
pranera_knit/api/knit_down.py
Whitelisted methods behind the Knit App "Knit Down Approval" page.
Rules and the roll-submit gate live in knit_down_events.py.

Knitting team: pick a running Work Order + machine, enter the knit down
(Dia, Gauge, GSM, Loop Length, yarn %, photo) → save_knit_down.
Production team (Knit Down Approver): approve_knit_down / reject_knit_down.
"""
import frappe
from frappe import _
from frappe.utils import cint, flt

from pranera_knit.knit_down_events import (
    KNIT_OPERATION, bom_yarns, can_approve, job_card_status, latest_for,
)

DOCTYPE = "Knit Down Approval"
EDITABLE = ("work_order", "workstation", "job_card", "dia", "gauge", "gsm", "loop_length",
            "photo", "knitting_remarks")
LIST_FIELDS = ["name", "status", "work_order", "workstation", "job_card", "item_name",
               "dia", "gauge", "gsm", "loop_length", "required_dia", "required_gg", "required_gsm",
               "required_ll", "requested_by", "requested_on", "approved_by", "approved_on",
               "approver_remarks", "photo"]
OPEN_WO_STATUSES = ("Not Started", "In Process")


@frappe.whitelist()
def get_setup():
    return {
        "can_approve": can_approve(),
        "can_create": frappe.has_permission(DOCTYPE, "create"),
    }


@frappe.whitelist()
def search_work_orders(txt=None):
    """Open knitting Work Orders (with a KNITTING operation) for the knit down
    form: name, fabric, and the machines it's planned on."""
    like = "%{0}%".format((txt or "").strip())
    rows = frappe.db.sql("""
        SELECT wo.name, TRIM(wo.item_name) AS item_name, wo.production_item, wo.status,
               GROUP_CONCAT(DISTINCT op.workstation ORDER BY op.workstation SEPARATOR ', ') AS machines
        FROM `tabWork Order` wo
        JOIN `tabWork Order Operation` op ON op.parent = wo.name AND op.parenttype = 'Work Order'
        WHERE wo.docstatus = 1 AND wo.status IN %(statuses)s
          AND UPPER(op.operation) = %(op)s
          AND (wo.name LIKE %(like)s OR wo.item_name LIKE %(like)s OR wo.production_item LIKE %(like)s
               OR op.workstation LIKE %(like)s)
        GROUP BY wo.name
        ORDER BY wo.creation DESC
        LIMIT 30
    """, {"statuses": OPEN_WO_STATUSES, "op": KNIT_OPERATION, "like": like}, as_dict=True)
    return rows


@frappe.whitelist()
def get_work_order_defaults(work_order):
    """Everything the form needs once a Work Order is picked: the required
    spec, its knitting machines (with job card and latest knit down) and the
    BOM yarns with their %."""
    frappe.has_permission("Work Order", "read", work_order, throw=True)
    meta = frappe.get_meta("Work Order")
    spec_fields = [f for f in ("required_dia", "required_gg", "required_gsm", "required_ll") if meta.has_field(f)]
    wo = frappe.db.get_value("Work Order", work_order,
                             ["name", "production_item", "item_name", "qty", "status", "stock_uom"] + spec_fields,
                             as_dict=True)
    if not wo:
        frappe.throw(_("Work Order {0} not found").format(work_order))
    wo.item_name = (wo.item_name or "").strip()

    machines = {}
    for op in frappe.get_all("Work Order Operation",
                             filters={"parent": work_order, "parenttype": "Work Order"},
                             fields=["operation", "workstation"], order_by="idx asc"):
        if (op.operation or "").upper() == KNIT_OPERATION and op.workstation:
            machines.setdefault(op.workstation, {"workstation": op.workstation, "job_card": None})
    for jc in frappe.get_all("Job Card",
                             filters={"work_order": work_order, "docstatus": ["<", 2]},
                             fields=["name", "workstation", "operation"], order_by="creation asc"):
        if (jc.operation or "").upper() == KNIT_OPERATION and jc.workstation:
            machines.setdefault(jc.workstation, {"workstation": jc.workstation})["job_card"] = jc.name
    for m in machines.values():
        m["knit_down"] = latest_for(work_order, m["workstation"])

    return {"work_order": wo, "machines": list(machines.values()), "yarns": bom_yarns(work_order)}


@frappe.whitelist()
def save_knit_down(name=None, yarns=None, **values):
    doc = frappe.get_doc(DOCTYPE, name) if name else frappe.new_doc(DOCTYPE)
    if name:
        doc.check_permission("write")
    for key in EDITABLE:
        if key in values:
            doc.set(key, values[key] or None)
    if yarns is not None:
        if isinstance(yarns, str):
            yarns = frappe.parse_json(yarns)
        doc.set("yarns", [{"item_code": y.get("item_code"), "actual_percent": flt(y.get("actual_percent"))}
                          for y in yarns or [] if y.get("item_code")])
    doc.save()
    frappe.db.commit()
    return get_knit_down(doc.name)


@frappe.whitelist()
def approve_knit_down(name, remarks=None):
    return _decide(name, "Approved", remarks)


@frappe.whitelist()
def reject_knit_down(name, remarks=None):
    return _decide(name, "Rejected", remarks)


def _decide(name, status, remarks):
    if not can_approve():
        frappe.throw(_("Only a Knit Down Approver can approve or reject a knit down"), frappe.PermissionError)
    doc = frappe.get_doc(DOCTYPE, name)
    if doc.status != "Pending":
        frappe.throw(_("Knit Down {0} is already {1}").format(name, doc.status))
    doc.status = status
    doc.approver_remarks = (remarks or "").strip() or None
    # The approver role may hold only read on the Work Order etc.; the
    # decision itself is permission-checked above.
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return get_knit_down(doc.name)


@frappe.whitelist()
def get_knit_down(name):
    doc = frappe.get_doc(DOCTYPE, name)
    doc.check_permission("read")
    out = doc.as_dict()
    out["item_name"] = (doc.item_name or "").strip()
    out["requested_by_name"] = frappe.utils.get_fullname(doc.requested_by) if doc.requested_by else ""
    out["approved_by_name"] = frappe.utils.get_fullname(doc.approved_by) if doc.approved_by else ""
    out["can_approve"] = doc.status == "Pending" and can_approve()
    out["can_edit"] = doc.status == "Pending" and bool(doc.has_permission("write"))
    return out


@frappe.whitelist()
def list_knit_downs(status=None, txt=None, limit=60):
    filters = {}
    if status:
        filters["status"] = status
    or_filters = None
    if txt:
        like = "%{0}%".format(txt.strip())
        or_filters = {"name": ["like", like], "work_order": ["like", like],
                      "workstation": ["like", like], "item_name": ["like", like]}
    rows = frappe.get_list(DOCTYPE, filters=filters, or_filters=or_filters, fields=LIST_FIELDS,
                           order_by="creation desc", limit_page_length=min(cint(limit) or 60, 200))
    users = {r.requested_by for r in rows} | {r.approved_by for r in rows}
    names = {u: frappe.utils.get_fullname(u) for u in users if u}
    yarns = {}
    if rows:
        for y in frappe.get_all("Knit Down Approval Yarn",
                                filters={"parent": ["in", [r.name for r in rows]], "parenttype": DOCTYPE},
                                fields=["parent", "item_code", "item_name", "bom_percent", "actual_percent"],
                                order_by="parent asc, idx asc"):
            yarns.setdefault(y.pop("parent"), []).append(y)
    for r in rows:
        r.item_name = (r.item_name or "").strip()
        r.requested_by_name = names.get(r.requested_by, "")
        r.approved_by_name = names.get(r.approved_by, "")
        r.yarns = yarns.get(r.name, [])
    return rows


@frappe.whitelist()
def get_job_card_status(job_card):
    """For the Create Roll screen: does this job card need a knit down, and
    is it approved?"""
    frappe.has_permission("Job Card", "read", job_card, throw=True)
    return job_card_status(job_card)
