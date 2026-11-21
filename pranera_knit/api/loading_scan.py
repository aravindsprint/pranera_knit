"""
pranera_knit/api/loading_scan.py
Whitelisted methods behind the Knit App "Loading Scan" page.

When a vehicle is loaded, security opens its Vehicle Gate Entry (Pick Up)
and scans every roll that goes on it. The rolls expected on the vehicle
come from all its Outward Requests together:

    Vehicle Gate Entry
      └─ Outward Request (gate entry's outward_requests table)
          └─ Roll Pick Assignment (docstatus < 2)
              └─ Roll Wise Pick List (docstatus < 2)
                  ├─ rolls: roll_wise_pick_item (roll_no, batch, qty)
                  │   (a whole-batch pick list has no roll rows: its
                  │   batch_wise_pick_item batches stand in, and every Roll
                  │   of that item + batch is expected)
                  └─ outbound Stock Entry (custom_roll_wise_pick_list;
                      the one NOT moving out of an "IN TRANSIT" warehouse —
                      that later one is the receipt at the destination)

Each scan is saved as a "Loading Scan" record (patches/v1_23):
Matched (roll is expected) or Not in list (wrong roll). Scanning a roll
twice is reported, not saved again. get_checklist combines everything:
per stock entry, per item + batch (stock entry qty vs scanned qty), and
per roll: scanned or not.
"""
import frappe
from frappe import _
from frappe.utils import cint, flt, now_datetime

DOCTYPE = "Loading Scan"
MATCHED, NOT_IN_LIST = "Matched", "Not in list"
IN_TRANSIT = "IN TRANSIT"


def _check_access(gate_entry):
    if not frappe.db.exists("Vehicle Gate Entry", gate_entry):
        frappe.throw(_("Vehicle Gate Entry {0} not found").format(gate_entry))
    frappe.has_permission("Vehicle Gate Entry", "read", gate_entry, throw=True)


def parse_roll_no(value):
    """Roll number from a sticker: item#batch#roll (new) or
    item#batch#lot#roll (old QI) → roll; anything else is a bare roll no."""
    value = (value or "").strip()
    parts = [p.strip() for p in value.split("#")]
    return parts[-1] if len(parts) >= 3 else value


# ── Gate entries ──────────────────────────────────────────────────────────

@frappe.whitelist()
def list_gate_entries(txt=None, limit=30):
    """Recent Pick Up gate entries with outward requests, newest first,
    with how many rolls were scanned so far."""
    like = "%{0}%".format((txt or "").strip())
    rows = frappe.db.sql("""
        SELECT g.name, g.vehicle_no, g.driver_name, g.date, g.arrival_datetime,
               g.departure_datetime, g.to_location,
               GROUP_CONCAT(DISTINCT o.outward_request ORDER BY o.idx SEPARATOR ', ') AS outward_requests
        FROM `tabVehicle Gate Entry` g
        JOIN `tabVehicle Gate Entry Outward Request` o
          ON o.parent = g.name AND o.parenttype = 'Vehicle Gate Entry'
        WHERE g.purpose = 'Pick Up'
          AND (g.name LIKE %(like)s OR g.vehicle_no LIKE %(like)s OR o.outward_request LIKE %(like)s
               OR IFNULL(g.driver_name, '') LIKE %(like)s)
        GROUP BY g.name
        ORDER BY g.creation DESC
        LIMIT %(limit)s
    """, {"like": like, "limit": min(cint(limit) or 30, 100)}, as_dict=True)
    if rows:
        counts = dict(frappe.db.sql("""
            SELECT vehicle_gate_entry, COUNT(*) FROM `tabLoading Scan`
            WHERE vehicle_gate_entry IN %(names)s AND result = %(m)s
            GROUP BY vehicle_gate_entry
        """, {"names": [r.name for r in rows], "m": MATCHED}))
        for r in rows:
            r.scanned = counts.get(r.name, 0)
    return rows


# ── Expected rolls ────────────────────────────────────────────────────────

def _pick_lists(gate_entry):
    """[{pick_list, outward_request, to_building, assignment}]"""
    return frappe.db.sql("""
        SELECT pl.name AS pick_list, o.outward_request, o.to_building, rpa.name AS assignment,
               pl.docstatus AS pick_list_status
        FROM `tabVehicle Gate Entry Outward Request` o
        JOIN `tabRoll Pick Assignment` rpa ON rpa.outward_request = o.outward_request AND rpa.docstatus < 2
        JOIN `tabRoll Wise Pick List` pl ON pl.roll_pick_assignment = rpa.name AND pl.docstatus < 2
        WHERE o.parent = %(g)s AND o.parenttype = 'Vehicle Gate Entry'
        ORDER BY o.idx, pl.creation
    """, {"g": gate_entry}, as_dict=True)


def _outbound_stock_entries(pick_lists):
    """{pick_list: {name, docstatus, lines: [{item_code, batch_no, qty, uom}]}} —
    the stock entry that moves the goods OUT (not the later receipt from
    the IN TRANSIT warehouse)."""
    if not pick_lists:
        return {}
    rows = frappe.db.sql("""
        SELECT se.name, se.docstatus, se.custom_roll_wise_pick_list AS pick_list, se.creation,
               sed.item_code, sed.batch_no, sed.qty, sed.stock_uom, sed.s_warehouse, sed.t_warehouse
        FROM `tabStock Entry` se
        JOIN `tabStock Entry Detail` sed ON sed.parent = se.name AND sed.parenttype = 'Stock Entry'
        WHERE se.custom_roll_wise_pick_list IN %(pl)s AND se.docstatus < 2
        ORDER BY se.creation, sed.idx
    """, {"pl": list(pick_lists)}, as_dict=True)
    by_entry = {}
    for r in rows:
        e = by_entry.setdefault(r.name, frappe._dict(
            name=r.name, docstatus=r.docstatus, pick_list=r.pick_list, creation=r.creation,
            lines=[], inbound=False))
        if IN_TRANSIT in (r.s_warehouse or "").upper():
            e.inbound = True
        e.lines.append(frappe._dict(item_code=r.item_code, batch_no=r.batch_no,
                                    qty=flt(r.qty), uom=r.stock_uom,
                                    from_warehouse=r.s_warehouse, to_warehouse=r.t_warehouse))
    out = {}
    # Earliest outbound entry per pick list; an inbound one only if that's all there is.
    for e in sorted(by_entry.values(), key=lambda e: (e.inbound, e.creation)):
        out.setdefault(e.pick_list, e)
    return out


def _expected_rolls(pick_lists):
    """{pick_list: [{roll_no, item_code, batch, qty, uom}]}"""
    if not pick_lists:
        return {}
    out = {pl: [] for pl in pick_lists}
    for r in frappe.get_all("Roll Wise Pick Item",
                            filters={"parent": ["in", list(pick_lists)],
                                     "parenttype": "Roll Wise Pick List"},
                            fields=["parent", "roll_no", "item_code", "batch", "qty", "roll_weight", "uom"],
                            order_by="parent asc, idx asc"):
        if r.roll_no:
            out[r.parent].append(frappe._dict(
                roll_no=r.roll_no, item_code=r.item_code, batch=r.batch,
                qty=flt(r.qty) or flt(r.roll_weight), uom=r.uom))
    # Whole-batch pick lists: expect every roll of that item + batch.
    batch_only = [pl for pl, rolls in out.items() if not rolls]
    if batch_only:
        for b in frappe.get_all("Batch Wise Pick Item",
                                filters={"parent": ["in", batch_only], "parenttype": "Roll Wise Pick List"},
                                fields=["parent", "item_code", "batch"], order_by="parent asc, idx asc"):
            if not b.batch:
                continue
            for roll in frappe.get_all("Roll", filters={"batch": b.batch, "item_code": b.item_code},
                                       fields=["name", "roll_weight", "total_qty", "stock_uom"],
                                       order_by="name asc"):
                pcs = (roll.stock_uom or "").strip().lower() == "pcs"
                out[b.parent].append(frappe._dict(
                    roll_no=roll.name, item_code=b.item_code, batch=b.batch,
                    qty=flt(roll.total_qty) if pcs else flt(roll.roll_weight),
                    uom=roll.stock_uom, whole_batch=1))
    return out


def _expected_index(gate_entry):
    """(pick_lists, stock_entries, expected, {roll_no: line})"""
    pick_lists = _pick_lists(gate_entry)
    names = [p.pick_list for p in pick_lists]
    entries = _outbound_stock_entries(names)
    expected = _expected_rolls(names)
    index = {}
    for p in pick_lists:
        se = entries.get(p.pick_list)
        for roll in expected.get(p.pick_list, []):
            index.setdefault(roll.roll_no, frappe._dict(
                roll, pick_list=p.pick_list, outward_request=p.outward_request,
                to_building=p.to_building, stock_entry=se.name if se else None))
    return pick_lists, entries, expected, index


# ── Checklist ─────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_checklist(gate_entry):
    _check_access(gate_entry)
    gate = frappe.db.get_value("Vehicle Gate Entry", gate_entry,
                               ["name", "vehicle_no", "driver_name", "mobile_no", "purpose", "date",
                                "to_location", "arrival_datetime", "departure_datetime"], as_dict=True)
    pick_lists, entries, expected, index = _expected_index(gate_entry)

    scans = frappe.get_all(DOCTYPE, filters={"vehicle_gate_entry": gate_entry},
                           fields=["name", "roll_no", "result", "item_code", "batch", "qty", "uom",
                                   "stock_entry", "scanned_by", "scanned_at"],
                           order_by="scanned_at asc")
    users = {s.scanned_by for s in scans if s.scanned_by}
    names = {u: frappe.utils.get_fullname(u) for u in users}
    scanned = {}
    extras = []
    for s in scans:
        s.scanned_by_name = names.get(s.scanned_by, s.scanned_by)
        if s.result == MATCHED and s.roll_no in index:
            scanned.setdefault(s.roll_no, s)
        else:
            extras.append(s)

    rolls = []
    for roll_no, line in index.items():
        s = scanned.get(roll_no)
        rolls.append(dict(line, scanned=bool(s), scan=s.name if s else None,
                          scanned_by_name=s.scanned_by_name if s else None,
                          scanned_at=s.scanned_at if s else None))

    stock_entries = []
    for p in pick_lists:
        se = entries.get(p.pick_list)
        mine = [r for r in rolls if r["pick_list"] == p.pick_list]
        groups = {}
        for r in mine:
            g = groups.setdefault((r["item_code"], r["batch"]), {
                "item_code": r["item_code"], "batch": r["batch"], "uom": r.get("uom"),
                "stock_entry_qty": 0.0, "rolls": 0, "scanned_rolls": 0,
                "picked_qty": 0.0, "scanned_qty": 0.0})
            g["rolls"] += 1
            g["picked_qty"] += flt(r.get("qty"))
            if r["scanned"]:
                g["scanned_rolls"] += 1
                g["scanned_qty"] += flt(r.get("qty"))
        for it in (se.lines if se else []):
            g = groups.setdefault((it.item_code, it.batch_no), {
                "item_code": it.item_code, "batch": it.batch_no, "uom": it.uom,
                "stock_entry_qty": 0.0, "rolls": 0, "scanned_rolls": 0,
                "picked_qty": 0.0, "scanned_qty": 0.0})
            g["stock_entry_qty"] += it.qty
            g["uom"] = g["uom"] or it.uom
        stock_entries.append({
            "stock_entry": se.name if se else None,
            "stock_entry_status": ("Submitted" if se.docstatus == 1 else "Draft") if se else "Not created",
            "pick_list": p.pick_list,
            "outward_request": p.outward_request,
            "to_building": p.to_building,
            "rolls": len(mine),
            "scanned": sum(1 for r in mine if r["scanned"]),
            "lines": [dict(g, scanned_qty=flt(g["scanned_qty"], 3), picked_qty=flt(g["picked_qty"], 3),
                           stock_entry_qty=flt(g["stock_entry_qty"], 3)) for g in groups.values()],
        })

    total = len(rolls)
    done = sum(1 for r in rolls if r["scanned"])
    return {
        "gate_entry": gate,
        "stock_entries": stock_entries,
        "rolls": rolls,
        "extras": extras,
        "totals": {"expected": total, "scanned": done, "pending": total - done,
                   "wrong": len(extras), "complete": total > 0 and done == total and not extras},
    }


# ── Scan / undo ───────────────────────────────────────────────────────────

@frappe.whitelist()
def scan(gate_entry, code):
    """Record one scanned sticker. Returns {result, message, roll_no, checklist}."""
    _check_access(gate_entry)
    roll_no = parse_roll_no(code)
    if not roll_no:
        frappe.throw(_("Nothing scanned"))
    _pick_lists_, _entries, _expected, index = _expected_index(gate_entry)
    line = index.get(roll_no)

    existing = frappe.db.get_value(DOCTYPE, {"vehicle_gate_entry": gate_entry, "roll_no": roll_no},
                                   ["name", "result", "scanned_by", "scanned_at"], as_dict=True)
    if existing:
        who = frappe.utils.get_fullname(existing.scanned_by) if existing.scanned_by else ""
        return {"result": "Duplicate", "roll_no": roll_no,
                "message": _("Roll {0} was already scanned{1}").format(
                    roll_no, f" by {who}" if who else ""),
                "checklist": get_checklist(gate_entry)}

    doc = frappe.new_doc(DOCTYPE)
    doc.vehicle_gate_entry = gate_entry
    doc.roll_no = roll_no
    doc.raw_value = (code or "").strip()[:140]
    doc.scanned_by = frappe.session.user
    doc.scanned_at = now_datetime()
    if line:
        doc.result = MATCHED
        doc.update({"stock_entry": line.stock_entry, "pick_list": line.pick_list,
                    "outward_request": line.outward_request, "item_code": line.item_code,
                    "batch": line.batch, "qty": line.qty, "uom": line.uom})
        message = _("Roll {0} matched ({1})").format(roll_no, line.stock_entry or line.pick_list)
    else:
        doc.result = NOT_IN_LIST
        roll = frappe.db.get_value("Roll", roll_no, ["item_code", "batch", "roll_weight", "stock_uom"],
                                   as_dict=True) if frappe.db.exists("Roll", roll_no) else None
        if roll:
            doc.update({"item_code": roll.item_code, "batch": roll.batch,
                        "qty": flt(roll.roll_weight), "uom": roll.stock_uom})
        message = _("Roll {0} is NOT on this vehicle's stock entries. Take it off the vehicle.") \
            .format(roll_no)
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return {"result": doc.result, "roll_no": roll_no, "message": message,
            "checklist": get_checklist(gate_entry)}


@frappe.whitelist()
def undo_scan(gate_entry, roll_no):
    """Remove a scan (wrong roll taken off the vehicle, or scanned by mistake)."""
    _check_access(gate_entry)
    name = frappe.db.get_value(DOCTYPE, {"vehicle_gate_entry": gate_entry, "roll_no": roll_no}, "name")
    if name:
        frappe.delete_doc(DOCTYPE, name, ignore_permissions=True)
        frappe.db.commit()
    return get_checklist(gate_entry)
