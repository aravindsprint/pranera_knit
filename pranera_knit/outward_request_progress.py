"""
pranera_knit/outward_request_progress.py

Requested / picked / sent / pending quantities for Outward Requests, shown on
the Knit App Outward Request list and form (api/outward_request.py).

  requested  Outward Request Item qty
  picked     Roll Wise Pick Item rows (the rolls) of every Roll Wise Pick List
             (docstatus < 2) of the request's Roll Pick Assignments. Pick lists
             also carry a Batch Wise Pick Item summary of the same rolls; it
             is not counted again.
  sent       submitted outbound Stock Entry rows of those pick lists — the
             transfer OUT of the "From" building (rows leaving an IN TRANSIT
             warehouse are the receipt at the destination, not counted)
  pending    requested − sent, never below 0

Kgs (fabric) and Pcs (collar / cuff) are kept apart: they can't be added.
Everything is computed for a whole list in three grouped queries.
"""
import frappe
from frappe.utils import add_days, date_diff, flt, getdate, nowdate

IN_TRANSIT = "%IN TRANSIT%"
OVERDUE_DAYS = 2
WHOLE_UOMS = ("pcs", "nos", "unit")

STAGES = {
    # key: (label, Outward Request.status values)
    "not_assigned": ("Not assigned", ("", None)),
    "assigned": ("Assigned", ("Roll Pick Assigned",)),
    "picked": ("Picked", ("Picked",)),
    "completed": ("Completed", ("Completed",)),
}


def stage_of(status):
    for key, (_label, values) in STAGES.items():
        if (status or "") in [v or "" for v in values]:
            return key
    return "not_assigned"


def _uom(u):
    return (u or "").strip()


def progress(names):
    """{request: {"by_uom": [...], "lines": [...]}} for the given requests."""
    names = [n for n in dict.fromkeys(names or []) if n]
    if not names:
        return {}
    params = {"names": names, "in_transit": IN_TRANSIT}

    requested = frappe.db.sql("""
        SELECT i.parent AS request, i.item_code, IFNULL(i.batch, '') AS batch,
               i.stock_uom AS uom, SUM(i.qty) AS qty
        FROM `tabOutward Request Item` i
        WHERE i.parenttype = 'Outward Request' AND i.parent IN %(names)s
        GROUP BY i.parent, i.item_code, IFNULL(i.batch, ''), i.stock_uom
    """, params, as_dict=True)

    picked = frappe.db.sql("""
        SELECT rpa.outward_request AS request, ri.item_code, IFNULL(ri.batch, '') AS batch,
               ri.uom, SUM(ri.qty) AS qty, COUNT(*) AS rolls
        FROM `tabRoll Pick Assignment` rpa
        JOIN `tabRoll Wise Pick List` pl ON pl.roll_pick_assignment = rpa.name AND pl.docstatus < 2
        JOIN `tabRoll Wise Pick Item` ri ON ri.parent = pl.name AND ri.parenttype = 'Roll Wise Pick List'
        WHERE rpa.docstatus < 2 AND rpa.outward_request IN %(names)s
        GROUP BY rpa.outward_request, ri.item_code, IFNULL(ri.batch, ''), ri.uom
    """, params, as_dict=True)

    sent = frappe.db.sql("""
        SELECT rpa.outward_request AS request, sed.item_code, IFNULL(sed.batch_no, '') AS batch,
               sed.stock_uom AS uom, SUM(sed.qty) AS qty
        FROM `tabRoll Pick Assignment` rpa
        JOIN `tabRoll Wise Pick List` pl ON pl.roll_pick_assignment = rpa.name AND pl.docstatus < 2
        JOIN `tabStock Entry` se ON se.custom_roll_wise_pick_list = pl.name AND se.docstatus = 1
        JOIN `tabStock Entry Detail` sed ON sed.parent = se.name AND sed.parenttype = 'Stock Entry'
        WHERE rpa.docstatus < 2 AND rpa.outward_request IN %(names)s
          AND IFNULL(sed.s_warehouse, '') NOT LIKE %(in_transit)s
        GROUP BY rpa.outward_request, sed.item_code, IFNULL(sed.batch_no, ''), sed.stock_uom
    """, params, as_dict=True)

    lines = {}

    def line(r):
        key = (r.request, r.item_code, r.batch or "", _uom(r.uom))
        return lines.setdefault(key, frappe._dict(
            request=r.request, item_code=r.item_code, batch=r.batch or "", uom=_uom(r.uom),
            requested=0.0, picked=0.0, sent=0.0, rolls=0))

    for r in requested:
        line(r).requested += flt(r.qty)
    # Pieces are whole: a request of 3,429.003 Pcs is 3,429.
    for ln in lines.values():
        if ln.uom.lower() in WHOLE_UOMS:
            ln.requested = round(ln.requested)
    for r in picked:
        ln = line(r)
        ln.picked += flt(r.qty)
        ln.rolls += r.rolls or 0
    for r in sent:
        line(r).sent += flt(r.qty)

    out = {n: {"by_uom": [], "lines": []} for n in names}
    totals = {}
    for (request, _item, _batch, uom), ln in lines.items():
        ln.pending = max(ln.requested - ln.sent, 0.0)
        out[request]["lines"].append(_round(ln))
        t = totals.setdefault((request, uom), frappe._dict(
            uom=uom, requested=0.0, picked=0.0, sent=0.0, pending=0.0, rolls=0))
        for f in ("requested", "picked", "sent", "pending", "rolls"):
            t[f] += ln[f]
    for (request, _uom_), t in totals.items():
        t.pick_diff_pct = round((t.picked - t.requested) / t.requested * 100, 1) \
            if t.requested and t.picked else None
        out[request]["by_uom"].append(_round(t))
    for v in out.values():
        # Kgs first, then Pcs, then anything else.
        v["by_uom"].sort(key=lambda t: {"kgs": 0, "pcs": 1}.get(t["uom"].lower(), 2))
        v["lines"].sort(key=lambda ln: ({"kgs": 0, "pcs": 1}.get(ln["uom"].lower(), 2),
                                        ln["item_code"] or "", ln["batch"] or ""))
    return out


def _round(d):
    return {k: (round(v, 3) if isinstance(v, float) else v) for k, v in d.items()}


def age_days(date, request_status):
    """Days past the request date while it's not completed (0 = today or later)."""
    if not date or request_status == "Completed":
        return 0
    return max(date_diff(nowdate(), getdate(date)), 0)


def overdue_before():
    """Requests dated on or before this are 'over 2 days'."""
    return add_days(nowdate(), -OVERDUE_DAYS)


def summary():
    """Open (not completed, not rejected) requests: pending per UOM, count per
    stage, and how many are over 2 days."""
    rows = frappe.db.sql("""
        SELECT name, date, status, request_status FROM `tabOutward Request`
        WHERE IFNULL(request_status, '') != 'Completed'
          AND IFNULL(same_day_approval, '') != 'Rejected'
    """, as_dict=True)
    counts = {k: 0 for k in STAGES}
    counts["completed"] = frappe.db.count("Outward Request", {"request_status": "Completed"})
    cutoff = getdate(overdue_before())
    overdue = 0
    for r in rows:
        counts[stage_of(r.status)] += 1
        if r.date and getdate(r.date) <= cutoff:
            overdue += 1
    pending = {}
    for p in progress([r.name for r in rows]).values():
        for t in p["by_uom"]:
            u = pending.setdefault(t["uom"], {"uom": t["uom"], "pending": 0.0, "requests": 0})
            if t["pending"] > 0:
                u["pending"] += t["pending"]
                u["requests"] += 1
    pending = sorted(({**u, "pending": round(u["pending"], 2)} for u in pending.values()),
                     key=lambda u: {"kgs": 0, "pcs": 1}.get(u["uom"].lower(), 2))
    return {"pending": pending, "stages": [{"key": k, "label": STAGES[k][0], "count": counts[k]}
                                           for k in STAGES],
            "overdue": overdue, "overdue_days": OVERDUE_DAYS, "open": len(rows)}
