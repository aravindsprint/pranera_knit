"""
pranera_knit/api/stock.py
Whitelisted methods behind the knit-app "Stock" page.

get_warehouse_stock(warehouse) → one row per roll (or per batch / item when
there's no roll to show), with item_code, commercial_name, batch, roll_no,
qty, stock_uom.

  Quantities come from the Stock Ledger, which is the source of truth:
  balance per (item_code, batch) in that warehouse, reading the batch
  from each entry's Serial and Batch Bundle (or the legacy batch_no
  column on older entries). Only positive balances are shown.

  Each batch is then broken into its Roll records whose `warehouse` is
  this warehouse. Roll.warehouse is only maintained by the Roll Wise Pick
  List flow (see roll_wise_pick_list_events.py), so it can lag reality;
  whatever part of the ledger balance those rolls don't account for is
  shown as one extra batch-level row with no roll_no (unmatched=1). That
  keeps the page's totals equal to the real stock, whatever the roll
  records say. When it's the other way round — rolls recorded here add up
  to more than the ledger holds (some have left without Roll.warehouse
  being updated) — those rows carry over_rolled=<excess> so the page can
  flag them, and ledger_totals gives the true per-UOM totals. Roll qty follows the scan logic in pick_order.py:
  total_qty for Pcs rolls, roll_weight otherwise.

resolve_scan(value) → what a scanned QR points to:
  * a warehouse label  — the full Warehouse name, or the name without the
    " - <company abbr>" suffix (bin/slot labels like "AA-001-001")
  * a roll sticker     — item#batch#roll_no (new) or item#batch#lot#roll_no
    (old QI stickers); returns the roll / batch to filter on and, when
    known, the warehouse the roll is recorded in
"""
import frappe
from frappe import _
from frappe.utils import flt

QTY_EPSILON = 0.001
# Ledger vs roll-total gaps at or below this are rounding noise (roll
# weights are entered to 2 dp), not stock that's missing a roll.
UNMATCHED_TOLERANCE = 0.05


@frappe.whitelist()
def get_warehouse_stock(warehouse):
    if not warehouse or not frappe.db.exists("Warehouse", warehouse):
        frappe.throw(_("Warehouse {0} not found").format(warehouse))
    frappe.has_permission("Warehouse", "read", warehouse, throw=True)

    balances = frappe.db.sql(
        """
        SELECT sle.item_code,
               COALESCE(sbe.batch_no, sle.batch_no, '') AS batch,
               SUM(COALESCE(sbe.qty, sle.actual_qty)) AS qty
        FROM `tabStock Ledger Entry` sle
        LEFT JOIN `tabSerial and Batch Entry` sbe
               ON sbe.parent = sle.serial_and_batch_bundle
        WHERE sle.warehouse = %(warehouse)s
          AND sle.is_cancelled = 0
        GROUP BY sle.item_code, batch
        HAVING qty > %(eps)s
        """,
        {"warehouse": warehouse, "eps": QTY_EPSILON},
        as_dict=True,
    )
    if not balances:
        return {"warehouse": warehouse, "rows": [], "ledger_totals": {}}

    item_codes = list({b.item_code for b in balances})
    items = {
        i.name: i
        for i in frappe.get_all(
            "Item", filters={"name": ["in", item_codes]},
            fields=["name", "item_name", "commercial_name", "stock_uom"],
        )
    }

    batches = [b.batch for b in balances if b.batch]
    rolls_by_key = {}
    if batches:
        for r in frappe.get_all(
            "Roll",
            filters={"batch": ["in", batches], "warehouse": warehouse, "docstatus": ["<", 2]},
            fields=["name", "item_code", "batch", "commercial_name", "stock_uom",
                    "roll_weight", "total_qty"],
            order_by="name asc",
            limit_page_length=0,
        ):
            rolls_by_key.setdefault((r.item_code, r.batch), []).append(r)

    rows = []
    for b in sorted(balances, key=lambda x: (x.item_code, x.batch)):
        item = items.get(b.item_code) or frappe._dict()
        uom = item.stock_uom or ""
        base = {
            "item_code": b.item_code,
            "commercial_name": item.commercial_name or item.item_name or "",
            "batch": b.batch,
            "stock_uom": uom,
        }
        rolls = rolls_by_key.get((b.item_code, b.batch), [])
        rolled = 0.0
        for r in rolls:
            r_uom = r.stock_uom or uom
            qty = flt(r.total_qty) if r_uom.lower() == "pcs" else flt(r.roll_weight)
            rolled += qty
            rows.append({
                **base,
                "commercial_name": r.commercial_name or base["commercial_name"],
                "roll_no": r.name,
                "qty": round(qty, 3),
                "stock_uom": r_uom,
                "unmatched": 0,
            })
        remainder = flt(b.qty) - rolled
        if rolls and remainder < -UNMATCHED_TOLERANCE:
            # More roll qty recorded here than the ledger holds — some of
            # these rolls have moved on without Roll.warehouse catching up.
            for row in rows[len(rows) - len(rolls):]:
                row["over_rolled"] = round(-remainder, 3)
        if not rolls or remainder > UNMATCHED_TOLERANCE:
            rows.append({
                **base,
                "roll_no": "",
                "qty": round(flt(b.qty) if not rolls else remainder, 3),
                "unmatched": 1 if rolls or b.batch else 0,
            })

    ledger_totals = {}
    for b in balances:
        uom = (items.get(b.item_code) or frappe._dict()).stock_uom or ""
        ledger_totals[uom] = round(ledger_totals.get(uom, 0.0) + flt(b.qty), 3)

    return {"warehouse": warehouse, "rows": rows, "ledger_totals": ledger_totals}


@frappe.whitelist()
def resolve_scan(value):
    value = (value or "").strip()
    if not value:
        frappe.throw(_("Empty scan"))

    if "#" in value:
        parts = [p.strip() for p in value.split("#")]
        if len(parts) >= 3:
            item_code, batch, roll_no = parts[0], parts[1], parts[-1]
            roll = frappe.db.get_value(
                "Roll", roll_no, ["name", "warehouse", "batch", "item_code"], as_dict=True
            ) if len(parts) == 3 else None
            return {
                "type": "roll",
                "roll_no": roll.name if roll else (roll_no if len(parts) == 3 else ""),
                "batch": (roll.batch if roll else batch) or "",
                "item_code": (roll.item_code if roll else item_code) or "",
                "warehouse": roll.warehouse if roll else None,
            }

    warehouse = _match_warehouse(value)
    if warehouse:
        return {"type": "warehouse", "warehouse": warehouse}

    if frappe.db.exists("Roll", value):
        roll = frappe.db.get_value("Roll", value, ["name", "warehouse", "batch", "item_code"], as_dict=True)
        return {"type": "roll", "roll_no": roll.name, "batch": roll.batch or "",
                "item_code": roll.item_code or "", "warehouse": roll.warehouse}

    if frappe.db.exists("Batch", value):
        return {"type": "batch", "batch": value, "warehouse": None}

    frappe.throw(_("'{0}' is not a warehouse, roll or batch").format(value))


def _match_warehouse(value):
    if frappe.db.exists("Warehouse", value):
        return value
    matches = frappe.get_all(
        "Warehouse",
        filters={"warehouse_name": value, "disabled": 0},
        pluck="name", limit=2,
    )
    if len(matches) == 1:
        return matches[0]
    matches = frappe.get_all(
        "Warehouse",
        filters={"name": ["like", f"{value} - %"], "disabled": 0},
        pluck="name", limit=2,
    )
    return matches[0] if len(matches) == 1 else None
