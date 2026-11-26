"""
NAP In Transit Ageing

Goods leave NAP (any NAP_* warehouse) for a dyeing / processing unit as a
Material Transfer into that unit's In Transit warehouse, and are "inwarded"
when the unit moves them out of In Transit into its own warehouses (lot
section, QR, direct delivery ...). This report shows, for every NAP ->
In Transit dispatch row (stock entry + item + batch):

  * how much was sent,
  * how much has left In Transit since (inwarded), where to and when,
  * how much is still sitting in In Transit, and for how many days.

Matching: per (In Transit warehouse, item, batch), every movement in that
warehouse is replayed in posting order. Outward movements are matched to
inward ones first-in-first-out, so stock that reached the same In Transit
warehouse from somewhere else (dyeing returns, JV, ...) is not mistaken for
NAP stock and vice versa. Only batches that came from NAP are read, which
keeps the ledger scan small even though the In Transit warehouses hold years
of history.

Quantities are in the item's stock UOM (Kgs for fabric, Pcs for collar /
cuff); totals are therefore shown per UOM. A leftover under 0.01 (or under
one piece for Pcs / Nos) is rounding dust and counts as inwarded.
"""
from datetime import datetime, timedelta

import frappe
from frappe import _
from frappe.utils import cint, date_diff, flt, getdate, today

NAP_PREFIX = "NAP"
QTY_EPS = 0.0005
CHUNK = 400
DEFAULT_RANGES = "7,15,30,60"
STATUSES = ("Pending", "Partly Inwarded", "Inwarded")
# Leftovers smaller than this are rounding dust from old transfers (e.g.
# 0.001 kg, or 0.48 of a collar), not goods waiting in transit: count the
# dispatch as fully inwarded. Counted units (Pcs / Nos) need a whole piece.
WHOLE_UNITS = {"pcs", "nos", "unit", "piece", "pieces"}
RESIDUE = 0.01


def execute(filters=None):
    filters = frappe._dict(filters or {})
    as_on = getdate(filters.get("as_on_date") or today())
    from_date = getdate(filters.from_date) if filters.get("from_date") else None
    ranges = _ranges(filters.get("ageing_ranges"))

    warehouses = _transit_warehouses(filters.get("in_transit_warehouse"))
    if not warehouses:
        return _columns(), [], None, None, []

    lots = _nap_lots(warehouses, as_on, filters.get("item_code"))
    if lots:
        _allocate(lots, warehouses, as_on)

    rows = []
    for lot in lots:
        if from_date and lot.posting_date < from_date:
            continue
        row = _row(lot, as_on, ranges)
        if not _status_ok(row, filters.get("status")):
            continue
        rows.append(row)
    rows.sort(key=lambda r: (r["pending_qty"] <= QTY_EPS, r["posting_date"], r["stock_entry"]))

    return _columns(), rows, None, _chart(rows, ranges), _summary(rows)


# ── data ─────────────────────────────────────────────────────────────────────

def _transit_warehouses(only=None):
    if only:
        return [only]
    return frappe.get_all(
        "Warehouse",
        filters={"is_group": 0},
        or_filters={"warehouse_type": "Transit", "name": ["like", "%transit%"]},
        pluck="name",
    )


def _nap_lots(warehouses, as_on, item_code=None):
    """NAP -> In Transit receipts, one row per ledger entry + batch."""
    conditions = ""
    params = {"whs": tuple(warehouses), "as_on": as_on, "nap": NAP_PREFIX + "%"}
    if item_code:
        conditions = " AND sle.item_code = %(item)s"
        params["item"] = item_code
    rows = frappe.db.sql(
        f"""
        SELECT sle.name AS sle, sle.posting_date, sle.posting_time, sle.creation,
               sle.warehouse, sle.item_code, sle.stock_uom, sle.voucher_no AS stock_entry,
               sed.s_warehouse AS from_warehouse,
               COALESCE(sbe.batch_no, sle.batch_no) AS batch_no,
               COALESCE(sbe.qty, sle.actual_qty) AS qty
        FROM `tabStock Ledger Entry` sle
        JOIN `tabStock Entry Detail` sed ON sed.name = sle.voucher_detail_no
        LEFT JOIN `tabSerial and Batch Entry` sbe ON sbe.parent = sle.serial_and_batch_bundle
        WHERE sle.is_cancelled = 0
          AND sle.voucher_type = 'Stock Entry'
          AND sle.actual_qty > 0
          AND sle.warehouse IN %(whs)s
          AND sle.posting_date <= %(as_on)s
          AND sed.s_warehouse LIKE %(nap)s
          {conditions}
        """,
        params,
        as_dict=True,
    )
    lots = []
    for r in rows:
        if flt(r.qty) <= QTY_EPS:
            continue
        r.qty = flt(r.qty)
        r.left = r.qty
        r.inwarded = 0.0
        r.last_inward = None
        r.entries = []
        r.destinations = []
        lots.append(r)
    return lots


def _movements(lots, as_on):
    """Every movement of the NAP batches in their In Transit warehouses."""
    keys = {(l.warehouse, l.item_code, l.batch_no) for l in lots}
    batches = sorted({k[2] for k in keys if k[2]})
    no_batch = sorted({(k[0], k[1]) for k in keys if not k[2]})
    whs = tuple(sorted({k[0] for k in keys}))
    cols = """
        sle.name AS sle, sle.posting_date, sle.posting_time, sle.creation,
        sle.warehouse, sle.item_code, sle.voucher_type, sle.voucher_no,
        sed.s_warehouse, sed.t_warehouse
    """
    sed_join = """LEFT JOIN `tabStock Entry Detail` sed
               ON sed.name = sle.voucher_detail_no AND sle.voucher_type = 'Stock Entry'"""
    base = "sle.is_cancelled = 0 AND sle.warehouse IN %(whs)s AND sle.posting_date <= %(as_on)s"
    out = []
    # Starting from the batch (indexed) instead of scanning the In Transit
    # ledger keeps this to ~1 s for ~3,000 batches; an OR across the bundle
    # and legacy batch columns can't use the index and took over 30 s.
    for i in range(0, len(batches), CHUNK):
        params = {"whs": whs, "as_on": as_on, "b": tuple(batches[i:i + CHUNK])}
        # v15 rows: batch quantities live in the Serial and Batch Bundle
        out += frappe.db.sql(f"""
            SELECT {cols}, sbe.batch_no, sbe.qty
            FROM `tabSerial and Batch Entry` sbe
            JOIN `tabStock Ledger Entry` sle ON sle.serial_and_batch_bundle = sbe.parent
            {sed_join}
            WHERE sbe.batch_no IN %(b)s AND {base}""", params, as_dict=True)
        # older rows: batch on the ledger entry itself
        out += frappe.db.sql(f"""
            SELECT {cols}, sle.batch_no, sle.actual_qty AS qty
            FROM `tabStock Ledger Entry` sle
            {sed_join}
            WHERE sle.batch_no IN %(b)s AND IFNULL(sle.serial_and_batch_bundle, '') = '' AND {base}""",
            params, as_dict=True)
    for wh, item in no_batch:
        out += frappe.db.sql(f"""
            SELECT {cols}, NULL AS batch_no, sle.actual_qty AS qty
            FROM `tabStock Ledger Entry` sle
            {sed_join}
            WHERE {base} AND sle.warehouse = %(wh)s AND sle.item_code = %(item)s
              AND IFNULL(sle.serial_and_batch_bundle, '') = '' AND IFNULL(sle.batch_no, '') = ''""",
            {"whs": whs, "as_on": as_on, "wh": wh, "item": item}, as_dict=True)
    return [m for m in out if (m.warehouse, m.item_code, m.batch_no) in keys]


def _allocate(lots, warehouses, as_on):
    """FIFO-match outward movements to inward ones per (warehouse, item, batch)."""
    by_sle = {(l.sle, l.batch_no): l for l in lots}
    streams = {}
    seen = set()
    for m in _movements(lots, as_on):
        ident = (m.sle, m.batch_no)
        if ident in seen:
            continue
        seen.add(ident)
        streams.setdefault((m.warehouse, m.item_code, m.batch_no), []).append(m)

    for moves in streams.values():
        moves.sort(key=_sort_key)
        queue = []  # [left, lot or None]
        for m in moves:
            qty = flt(m.qty)
            if qty > QTY_EPS:
                lot = by_sle.get((m.sle, m.batch_no))
                queue.append([qty, lot])
                continue
            need = -qty
            dest = m.t_warehouse or (m.voucher_type if m.voucher_type != "Stock Entry" else _("Consumed / issued"))
            while need > QTY_EPS and queue:
                head = queue[0]
                take = min(head[0], need)
                head[0] -= take
                need -= take
                lot = head[1]
                if lot is not None:
                    lot.inwarded += take
                    lot.left -= take
                    lot.last_inward = m.posting_date
                    if m.voucher_no not in lot.entries:
                        lot.entries.append(m.voucher_no)
                    if dest and dest not in lot.destinations:
                        lot.destinations.append(dest)
                if head[0] <= QTY_EPS:
                    queue.pop(0)


def _sort_key(m):
    # posting_time comes back as a timedelta: compare it as one. As text,
    # "9:05:00" sorts after "15:20:00", which put same-day movements out of
    # In Transit before the movement in and lost them.
    t = m.posting_time
    if not isinstance(t, timedelta):
        t = timedelta(0)
    return (m.posting_date, t, m.creation or datetime.min, m.sle)


# ── output ───────────────────────────────────────────────────────────────────

def _ranges(text):
    vals = []
    for part in str(text or DEFAULT_RANGES).split(","):
        n = cint(part.strip())
        if n > 0 and n not in vals:
            vals.append(n)
    return sorted(vals) or [7, 15, 30, 60]


def _bucket(age, ranges):
    lower = 0
    for upper in ranges:
        if age <= upper:
            return f"{lower}-{upper} days"
        lower = upper + 1
    return f"Above {ranges[-1]} days"


def _bucket_labels(ranges):
    labels, lower = [], 0
    for upper in ranges:
        labels.append(f"{lower}-{upper} days")
        lower = upper + 1
    labels.append(f"Above {ranges[-1]} days")
    return labels


def _row(lot, as_on, ranges):
    pending = round(max(lot.left, 0.0), 3)
    tolerance = 1 if (lot.stock_uom or "").strip().lower() in WHOLE_UNITS else RESIDUE
    if pending < tolerance:
        pending, status = 0.0, "Inwarded"
    elif lot.inwarded > QTY_EPS:
        status = "Partly Inwarded"
    else:
        status = "Pending"
    age = date_diff(as_on, lot.posting_date)
    return {
        "posting_date": lot.posting_date,
        "stock_entry": lot.stock_entry,
        "from_warehouse": lot.from_warehouse,
        "in_transit_warehouse": lot.warehouse,
        "item_code": lot.item_code,
        "item_name": frappe.get_cached_value("Item", lot.item_code, "item_name"),
        "batch_no": lot.batch_no,
        "uom": lot.stock_uom,
        "sent_qty": round(lot.qty, 3),
        "inwarded_qty": round(lot.qty - pending, 3),
        "pending_qty": pending,
        "status": status,
        "age": age if pending else None,
        "ageing": _bucket(age, ranges) if pending else "",
        "last_inward_date": lot.last_inward,
        "days_to_inward": date_diff(lot.last_inward, lot.posting_date) if status == "Inwarded" and lot.last_inward else None,
        "inwarded_to": ", ".join(lot.destinations),
        "inward_entries": ", ".join(lot.entries),
    }


def _status_ok(row, wanted):
    if not wanted or wanted == "All":
        return True
    if wanted == "Pending in Transit":
        return row["pending_qty"] > QTY_EPS
    if wanted == "Fully Inwarded":
        return row["status"] == "Inwarded"
    return row["status"] == wanted


def _columns():
    return [
        {"label": _("Dispatch Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
        {"label": _("NAP Stock Entry"), "fieldname": "stock_entry", "fieldtype": "Link", "options": "Stock Entry", "width": 130},
        {"label": _("From (NAP)"), "fieldname": "from_warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 160},
        {"label": _("In Transit Warehouse"), "fieldname": "in_transit_warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 230},
        {"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 190},
        {"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 200},
        {"label": _("Batch"), "fieldname": "batch_no", "fieldtype": "Link", "options": "Batch", "width": 190},
        {"label": _("UOM"), "fieldname": "uom", "fieldtype": "Link", "options": "UOM", "width": 60},
        {"label": _("Sent Qty"), "fieldname": "sent_qty", "fieldtype": "Float", "precision": 3, "width": 100},
        {"label": _("Inwarded Qty"), "fieldname": "inwarded_qty", "fieldtype": "Float", "precision": 3, "width": 110},
        {"label": _("Pending in Transit"), "fieldname": "pending_qty", "fieldtype": "Float", "precision": 3, "width": 120},
        {"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 120},
        {"label": _("Age (Days)"), "fieldname": "age", "fieldtype": "Int", "width": 85},
        {"label": _("Ageing"), "fieldname": "ageing", "fieldtype": "Data", "width": 110},
        {"label": _("Last Inward Date"), "fieldname": "last_inward_date", "fieldtype": "Date", "width": 110},
        {"label": _("Days to Inward"), "fieldname": "days_to_inward", "fieldtype": "Int", "width": 100},
        {"label": _("Inwarded To"), "fieldname": "inwarded_to", "fieldtype": "Data", "width": 220},
        {"label": _("Inward Entries"), "fieldname": "inward_entries", "fieldtype": "Data", "width": 200},
    ]


def _chart(rows, ranges):
    labels = _bucket_labels(ranges)
    uoms = sorted({r["uom"] for r in rows if r["pending_qty"] > QTY_EPS})
    if not uoms:
        return None
    datasets = []
    for uom in uoms:
        totals = dict.fromkeys(labels, 0.0)
        for r in rows:
            if r["uom"] == uom and r["pending_qty"] > QTY_EPS:
                totals[r["ageing"]] += r["pending_qty"]
        datasets.append({"name": f"Pending ({uom})", "values": [round(totals[l], 2) for l in labels]})
    return {"data": {"labels": labels, "datasets": datasets}, "type": "bar",
            "title": _("Pending in Transit by ageing"), "barOptions": {"stacked": 0}}


def _summary(rows):
    out = []
    for uom in sorted({r["uom"] for r in rows}):
        sel = [r for r in rows if r["uom"] == uom]
        sent = sum(r["sent_qty"] for r in sel)
        inward = sum(r["inwarded_qty"] for r in sel)
        pending = sum(r["pending_qty"] for r in sel)
        out += [
            {"value": round(sent, 2), "label": _("Sent from NAP ({0})").format(uom), "datatype": "Float", "indicator": "Blue"},
            {"value": round(inward, 2), "label": _("Inwarded ({0})").format(uom), "datatype": "Float", "indicator": "Green"},
            {"value": round(pending, 2), "label": _("Pending in Transit ({0})").format(uom), "datatype": "Float",
             "indicator": "Red" if pending > QTY_EPS else "Green"},
        ]
    ages = [r["age"] for r in rows if r["pending_qty"] > QTY_EPS and r["age"] is not None]
    if ages:
        out.append({"value": max(ages), "label": _("Oldest pending (days)"), "datatype": "Int", "indicator": "Orange"})
    return out
