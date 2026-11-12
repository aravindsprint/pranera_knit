"""
pranera_knit/api/order_rolls.py
Create Rolls page → "Purchase Order" / "Subcontract Order" tabs.

Rolls for bought-in or subcontracted fabric are only scannable on a Pick
Order when their batch was received on a submitted Purchase Receipt /
Subcontracting Receipt (pick_order._is_received_external_roll). So this
module only lets a roll be created against such a batch:

  get_received_batches  — the batches of one item actually received
      against the chosen order, with received qty, rolls already made and
      what's still left to roll.
        Purchase Order      → Purchase Receipt Items with purchase_order =
                              the PO, plus Subcontracting Receipt Items with
                              purchase_order = the PO (subcontracted POs).
        Subcontracting Order→ Subcontracting Receipt Items with
                              subcontracting_order = the SCO.
      Only submitted, non-return receipts. The batch comes from the row's
      Serial and Batch Bundle when set (normal on this site), else batch_no.

  create_order_rolls    — creates one or many Rolls on one received batch,
      numbered from the same "next numeric roll_no" sequence the
      knit_create_po_so_roll / knit-create-roll Server Scripts use.

Project: same as the old Server Scripts — the PO row's Material Request
(a numbered sub-project such as 26PTIN1731-1), else its Project; the SCO
row's Project for Subcontracting Orders. The Pick Order scan treats
26PTIN1731-<n> as matching a Work Order on 26PTIN1731
(pick_order._same_project).
"""
import frappe
from frappe import _
from frappe.utils import flt, now_datetime

MAX_ROLLS_PER_CALL = 200


# ── Received batches ──────────────────────────────────────────────────────

def _order_rows(item_code, purchase_order=None, subcontracting_order=None):
    """Submitted, non-return receipt rows for this item + order."""
    rows = []
    if purchase_order:
        rows += frappe.db.sql(
            """
            select pri.batch_no, pri.serial_and_batch_bundle, pri.stock_qty as qty,
                   pri.stock_uom, pri.parent as receipt, 'Purchase Receipt' as receipt_type,
                   pr.posting_date
            from `tabPurchase Receipt Item` pri
            inner join `tabPurchase Receipt` pr on pr.name = pri.parent
            where pri.purchase_order = %(po)s and pri.item_code = %(item)s
              and pr.docstatus = 1 and pr.is_return = 0
            """,
            {"po": purchase_order, "item": item_code}, as_dict=True,
        )
    sr_filter = "sri.subcontracting_order = %(sco)s" if subcontracting_order else "sri.purchase_order = %(po)s"
    if subcontracting_order or purchase_order:
        rows += frappe.db.sql(
            f"""
            select sri.batch_no, sri.serial_and_batch_bundle, sri.qty,
                   sri.stock_uom, sri.parent as receipt, 'Subcontracting Receipt' as receipt_type,
                   sr.posting_date
            from `tabSubcontracting Receipt Item` sri
            inner join `tabSubcontracting Receipt` sr on sr.name = sri.parent
            where {sr_filter} and sri.item_code = %(item)s
              and sr.docstatus = 1 and sr.is_return = 0
            """,
            {"po": purchase_order, "sco": subcontracting_order, "item": item_code}, as_dict=True,
        )
    return rows


def _received(item_code, purchase_order=None, subcontracting_order=None):
    """{batch: {batch, received_qty, stock_uom, receipts, last_received}}"""
    rows = _order_rows(item_code, purchase_order, subcontracting_order)
    bundles = [r.serial_and_batch_bundle for r in rows if r.serial_and_batch_bundle]
    entries = {}
    if bundles:
        for e in frappe.get_all(
            "Serial and Batch Entry",
            filters={"parent": ["in", bundles]},
            fields=["parent", "batch_no", "qty"],
        ):
            if e.batch_no:
                entries.setdefault(e.parent, []).append(e)

    out = {}
    for r in rows:
        parts = [(e.batch_no, abs(flt(e.qty))) for e in entries.get(r.serial_and_batch_bundle, [])]
        if not parts and r.batch_no:
            parts = [(r.batch_no, flt(r.qty))]
        for batch, qty in parts:
            b = out.setdefault(batch, {
                "batch": batch, "received_qty": 0.0, "stock_uom": r.stock_uom,
                "receipts": [], "last_received": r.posting_date,
            })
            b["received_qty"] += qty
            if r.receipt not in b["receipts"]:
                b["receipts"].append(r.receipt)
            if r.posting_date and (not b["last_received"] or r.posting_date > b["last_received"]):
                b["last_received"] = r.posting_date
    return out


def _check_order(purchase_order, subcontracting_order):
    if bool(purchase_order) == bool(subcontracting_order):
        frappe.throw(_("Pass either a Purchase Order or a Subcontracting Order"))


@frappe.whitelist()
def get_received_batches(item_code, purchase_order=None, subcontracting_order=None):
    """Batches of `item_code` received against the order, newest first, each
    with received_qty, rolls already created on it (count, weight, qty) and
    remaining = received − already rolled (weight for Kgs, qty for Pcs)."""
    _check_order(purchase_order, subcontracting_order)
    if not item_code:
        return []
    received = _received(item_code, purchase_order, subcontracting_order)
    if not received:
        return []

    rolled = {
        r.batch: r for r in frappe.db.sql(
            """
            select batch, count(*) as rolls, sum(roll_weight) as weight, sum(total_qty) as qty
            from `tabRoll`
            where item_code = %(item)s and batch in %(batches)s
            group by batch
            """,
            {"item": item_code, "batches": tuple(received)}, as_dict=True,
        )
    }
    out = []
    for b in received.values():
        r = rolled.get(b["batch"]) or {}
        is_pcs = (b["stock_uom"] or "").lower() == "pcs"
        done = flt(r.get("qty")) if is_pcs else flt(r.get("weight"))
        out.append({
            **b,
            "received_qty": flt(b["received_qty"], 3),
            "rolls": int(r.get("rolls") or 0),
            "rolled_weight": flt(r.get("weight"), 3),
            "rolled_qty": flt(r.get("qty"), 3),
            "remaining": flt(b["received_qty"] - done, 3),
        })
    out.sort(key=lambda b: (str(b["last_received"] or ""), b["batch"]), reverse=True)
    return out


# ── Create rolls ──────────────────────────────────────────────────────────

def _order_item(item_code, purchase_order=None, subcontracting_order=None):
    if purchase_order:
        row = frappe.db.get_value(
            "Purchase Order Item", {"parent": purchase_order, "item_code": item_code},
            ["project", "material_request"], as_dict=True,
        )
        if not row:
            frappe.throw(_("Item {0} is not on Purchase Order {1}").format(item_code, purchase_order))
        return row.material_request or row.project or ""
    row = frappe.db.get_value(
        "Subcontracting Order Item", {"parent": subcontracting_order, "item_code": item_code},
        ["project"], as_dict=True,
    )
    if not row:
        frappe.throw(_("Item {0} is not on Subcontracting Order {1}").format(item_code, subcontracting_order))
    return row.project or frappe.db.get_value("Subcontracting Order", subcontracting_order, "project") or ""


def _next_roll_no():
    """Same sequence as the knit_create_po_so_roll / knit-create-roll
    Server Scripts: highest all-digit Roll name + 1."""
    max_no = frappe.db.sql(
        "select max(cast(name as unsigned)) from `tabRoll` where name regexp '^[0-9]+$'"
    )[0][0] or 0
    next_no = int(max_no) + 1
    while frappe.db.exists("Roll", str(next_no)):
        next_no += 1
    return str(next_no)


@frappe.whitelist()
def create_order_rolls(item_code, batch, rolls, purchase_order=None, subcontracting_order=None,
                       actual_width=None):
    """Creates one Roll per entry in `rolls` ([{roll_weight, total_qty,
    mistake_qty, ok_qty}]) on a batch received against the order. Returns
    the created rolls (for printing stickers)."""
    _check_order(purchase_order, subcontracting_order)
    frappe.has_permission("Roll", "create", throw=True)

    rolls = frappe.parse_json(rolls) if isinstance(rolls, str) else (rolls or [])
    if not rolls:
        frappe.throw(_("Enter at least one roll"))
    if len(rolls) > MAX_ROLLS_PER_CALL:
        frappe.throw(_("At most {0} rolls at a time").format(MAX_ROLLS_PER_CALL))
    if not batch:
        frappe.throw(_("Select the received batch — a roll without one can't be scanned"))

    received = _received(item_code, purchase_order, subcontracting_order)
    if batch not in received:
        order = purchase_order or subcontracting_order
        frappe.throw(_(
            "Batch {0} was not received for {1} on {2}. Pick a batch from a submitted "
            "Purchase / Subcontracting Receipt of this order."
        ).format(batch, item_code, order), title=_("Batch Not Received"))

    item = frappe.db.get_value(
        "Item", item_code, ["item_name", "commercial_name", "color", "width", "stock_uom"], as_dict=True
    ) or frappe._dict()
    stock_uom = item.stock_uom or received[batch]["stock_uom"] or ""
    is_pcs = stock_uom.lower() == "pcs"
    project = _order_item(item_code, purchase_order, subcontracting_order)

    clean = []
    for i, r in enumerate(rolls, start=1):
        weight, qty = flt(r.get("roll_weight"), 3), flt(r.get("total_qty"))
        if is_pcs and qty <= 0:
            frappe.throw(_("Roll {0}: enter the Roll Qty (pcs)").format(i))
        if not is_pcs and weight <= 0:
            frappe.throw(_("Roll {0}: enter the Roll Weight (kg)").format(i))
        mistake = flt(r.get("mistake_qty"))
        ok = flt(r.get("ok_qty")) if r.get("ok_qty") not in (None, "") else max(0, qty - mistake)
        clean.append({
            "roll_weight": weight, "total_qty": qty, "mistake_qty": mistake, "correct_qty": ok,
            "avg_weight_per_pcs": flt(weight / qty, 4) if weight and qty else 0,
        })

    now, user, created = now_datetime(), frappe.session.user, []
    for r in clean:
        for attempt in range(5):
            roll = frappe.new_doc("Roll")
            roll.update({
                "roll_no": _next_roll_no(),
                "purchase_order": purchase_order or "",
                "subcontracting_order": subcontracting_order or "",
                "item_code": item_code,
                "item_name": item.item_name or "",
                "commercial_name": item.commercial_name or "",
                "color": item.color or "",
                "width": item.width or "",
                "actual_width": actual_width or "",
                "project": project,
                "stock_uom": stock_uom,
                "batch": batch,
                "name_of_the_operator": user,
                "datetime": now,
                **r,
            })
            try:
                roll.insert(ignore_permissions=True)
                break
            except frappe.DuplicateEntryError:
                # Another device took this number between our check and
                # insert — take the next one.
                if attempt == 4:
                    raise
        created.append(roll.as_dict())
    frappe.db.commit()
    return created
