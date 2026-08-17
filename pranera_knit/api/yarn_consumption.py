"""
pranera_knit/api/yarn_consumption.py

Backend support for the reworked "Actual Yarn Consumption" step.

Design (confirmed with Aravind):
  * Exactly ONE batch is transferred per required-item yarn.
  * Sequence is always: transfer -> Start Job -> produce -> Submit Job Card.
  * At START JOB (first job card of the WO only) we snapshot "Before" — the WIP
    balance of each transferred yarn batch at that moment — onto the Work Order's
    Required Items rows (custom_before_qty).
  * At SUBMIT JOB CARD (first card only) we read "After" (current WIP balance),
    show the editable Actual Consumption modal (Actual = Before - After), then
    build an actuals-based BOM linked to the WO's other job cards.
  * Before / After are tracked on Work Order Item via custom fields:
        custom_before_qty (Float), custom_after_qty (Float)
    (No custom_batch_no — the single transferred batch is resolved on the fly.)
  * The actuals BOM is tagged with BOM.custom_source_work_order (Link -> Work
    Order) so it is created once per WO and reused (idempotent).

Whitelisted aliases used by the Vue PWA:
  knit_is_first_job_card         -> is_first_job_card
  knit_snapshot_before_consumption -> snapshot_before_consumption
  knit_save_before_consumption     -> save_before_consumption
  knit_get_yarn_consumption      -> get_yarn_consumption
  knit_apply_actual_bom          -> apply_actual_bom
(see registration note at the bottom)

----------------------------------------------------------------------------
FIX LOG (bug analysis + patch, applied 2026-08-17)
----------------------------------------------------------------------------
1. apply_actual_bom() was setting bom.quantity = wo.qty (the WHOLE work
   order's target output, e.g. 3492 kg) while the BOM's raw-material row
   held the actual yarn consumed for only the FIRST job card (e.g. 227.36
   kg). That produced a wildly wrong RM:FG ratio (227.36/3492 = 6.5%
   instead of ~100%), which every later Manufacture Stock Entry against
   that Work Order then inherited — confirmed against 80 real Stock
   Entries since 1 May 2026 across 9 auto-generated BOMs (ratios up to
   70x). Fixed: bom.quantity is now the qty actually produced by the SAME
   job card whose actual_consumption is being recorded.

   Verified against live data: SUM(Roll.roll_weight) for job card
   PO-JOB18960 (the first job card of WO/26/10351) = 227.36 — exactly
   the figure that should have been used as bom.quantity instead of
   3492. Cross-checked on 4 more job cards (176.90, 176.70, 176.84,
   177.04) — exact match every time against the independently-tracked
   Roll Packing List total as well.

2. Queried from Roll (SUM(Roll.roll_weight) WHERE job_card=...), not
   Roll Packing List: Roll records are created live on the shop floor as
   each roll comes off the machine, well BEFORE the job card is
   submitted. Roll Packing List, by contrast, is created 1.5-3.5 hours
   AFTER the BOM in every case checked (9 work orders), so a lookup
   against it at BOM-build time would find nothing. Roll is always
   available at the point apply_actual_bom() runs — no frontend change
   needed to pass a produced_qty parameter, only job_card.

3. custom_source_work_order did not exist on this site's BOM doctype
   (confirmed: `Unknown column 'custom_source_work_order'` on direct
   SQL query), so the "idempotent per work order" reuse logic silently
   never fired — every actuals run minted a brand new BOM
   (...-381, -383, -384, -387...) instead of reusing/replacing one.
   Run create_custom_fields_PATCH.py once to add the missing field
   before deploying this file.

FRONTEND CHANGE REQUIRED
-------------------------
apply_actual_bom() now takes job_card as an explicit, required argument
(it's always called in the context of one specific job card — the first
job card of the WO — but the old signature didn't declare it). The Vue
"Submit Job Card" call to knit_apply_actual_bom needs to include it —
it already sends job_card to the sibling endpoint get_yarn_consumption,
so this is a small, consistent addition:

    POST knit_apply_actual_bom
    {
      "work_order": "...",
      "job_card": "...",           # <-- NOW REQUIRED
      "actual_consumption": [...]
    }

No produced_qty needs to be sent — the backend derives it itself from
Roll records for that job_card.
----------------------------------------------------------------------------
"""

import frappe
import json
from frappe.utils import flt, today


# ---------------------------------------------------------------------------
# 1. Is this the first job card of the work order?
# ---------------------------------------------------------------------------
@frappe.whitelist()
def is_first_job_card(work_order, job_card):
    """'First' = no OTHER job card of the same WO was created earlier."""
    this = frappe.db.get_value(
        "Job Card", job_card, ["creation", "work_order"], as_dict=True
    )
    if not this:
        return {"is_first": True}

    wo = this.work_order or work_order
    earlier = frappe.db.count(
        "Job Card",
        {
            "work_order": wo,
            "name": ["!=", job_card],
            "creation": ["<", this.creation],
        },
    )
    return {"is_first": earlier == 0}


# ---------------------------------------------------------------------------
# Stock helpers
# ---------------------------------------------------------------------------
# (Before/After are operator-entered cone weights — no stock reads needed.)


def _transferred_batch_for_item(work_order, item_code):
    """The single batch transferred for this item into WIP for the work order.

    FIX (2026-08-17): ORDER BY qty DESC on the raw signed transfer quantity
    picks the LEAST-negative (smallest magnitude) batch, not the largest
    transfer, because outgoing transfer quantities are stored negative.
    Confirmed against WO/26/9475: a batch with -456 kg transferred was
    picked over one with -2036.8 kg, because -456 > -2036.8 numerically.
    Must compare by ABS(qty) to find the batch that actually received the
    bulk of the transfer.
    """
    row = frappe.db.sql(
        """
        SELECT COALESCE(sbe.batch_no, sed.batch_no) AS batch_no,
               SUM(COALESCE(sbe.qty, sed.transfer_qty)) AS qty
        FROM `tabStock Entry` se
        JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
        LEFT JOIN `tabSerial and Batch Entry` sbe
            ON sbe.parent = sed.serial_and_batch_bundle
            AND sbe.parenttype = 'Serial and Batch Bundle'
        WHERE se.docstatus = 1
          AND se.work_order = %(wo)s
          AND se.stock_entry_type = 'Material Transfer for Manufacture'
          AND sed.item_code = %(item)s
        GROUP BY COALESCE(sbe.batch_no, sed.batch_no)
        ORDER BY ABS(qty) DESC
        LIMIT 1
        """,
        {"wo": work_order, "item": item_code},
        as_dict=True,
    )
    return (row[0].batch_no or "") if row else ""


def _iter_required_yarns(wo):
    """Yield (row, batch_no, transferred) for each transferred required item."""
    for row in wo.required_items:
        transferred = flt(row.transferred_qty)
        if transferred <= 0.0005:
            continue
        batch_no = _transferred_batch_for_item(wo.name, row.item_code)
        yield row, batch_no, transferred


def _get_produced_qty_for_job_card(job_card):
    """
    Resolve the production quantity that the actual_consumption figures
    for this job card correspond to, by summing the individual Roll
    records logged against it on the shop floor.

    This is deliberately queried from `Roll` rather than
    `Roll Packing List.total_roll_weight`: Roll records are created
    live as each roll comes off the machine, so they're already
    complete well before the job card is submitted (verified: 1.5-3.5
    hours ahead of BOM/RPL creation across all 9 affected work orders).
    Roll Packing List is created AFTER the BOM in the current flow, so
    querying it here would find nothing yet.
    """
    total = frappe.db.sql(
        """
        SELECT SUM(roll_weight) FROM `tabRoll` WHERE job_card = %s
        """,
        (job_card,),
    )
    return flt(total[0][0]) if total and total[0][0] else None


# ---------------------------------------------------------------------------
# 2a. START JOB — snapshot Before (read-only display)
# ---------------------------------------------------------------------------
@frappe.whitelist()
def snapshot_before_consumption(work_order, job_card):
    """
    Called on Start Job (first job card). Returns each transferred yarn with its
    transferred qty and any previously stored Before cone weight, so the operator
    can enter/confirm the Before weights in the PWA. No stock reads — Before is a
    manually entered cone weight, stored on the Work Order Item rows.
    """
    wo = frappe.get_doc("Work Order", work_order)
    woi_meta = frappe.get_meta("Work Order Item")
    has_before = woi_meta.has_field("custom_before_qty")

    out = []
    for row, batch_no, transferred in _iter_required_yarns(wo):
        before_qty = flt(getattr(row, "custom_before_qty", 0)) if has_before else 0
        out.append(
            {
                "item_code": row.item_code,
                "batch_no": batch_no,
                "transferred": flt(transferred, 3),
                "before_qty": flt(before_qty, 3),
            }
        )
    return out


@frappe.whitelist()
def save_before_consumption(work_order, job_card, before_data):
    """
    Persist the operator-entered Before cone weights onto the Work Order Item
    rows (custom_before_qty). before_data: JSON list of {item_code, before_qty}.
    Called on 'Confirm & Start Job'.
    """
    if isinstance(before_data, str):
        before_data = json.loads(before_data)
    before_map = {r.get("item_code"): flt(r.get("before_qty")) for r in (before_data or [])}

    wo = frappe.get_doc("Work Order", work_order)
    woi_meta = frappe.get_meta("Work Order Item")
    if not woi_meta.has_field("custom_before_qty"):
        return {"success": False, "reason": "custom_before_qty field missing"}

    dirty = False
    for row in wo.required_items:
        if row.item_code in before_map:
            row.custom_before_qty = before_map[row.item_code]
            dirty = True
    if dirty:
        for row in wo.required_items:
            row.db_update()
        frappe.db.commit()
    return {"success": True}


# ---------------------------------------------------------------------------
# 2b. SUBMIT JOB CARD — return stored Before / After for the actuals modal
# ---------------------------------------------------------------------------
@frappe.whitelist()
def get_yarn_consumption(work_order, job_card):
    """
    For each Required Item yarn, return item_code, batch_no, transferred,
    before_qty, after_qty — using the stored (operator-entered) cone weights.
    After is typically 0 here until the operator enters it in the submit modal;
    Before is whatever was entered at Start Job. Actual is computed in the PWA as
    a split of total roll weight by After, so no stock math is done here.
    """
    wo = frappe.get_doc("Work Order", work_order)
    woi_meta = frappe.get_meta("Work Order Item")
    has_before = woi_meta.has_field("custom_before_qty")
    has_after = woi_meta.has_field("custom_after_qty")

    out = []
    for row, batch_no, transferred in _iter_required_yarns(wo):
        before_qty = flt(getattr(row, "custom_before_qty", 0)) if has_before else 0
        after_qty = flt(getattr(row, "custom_after_qty", 0)) if has_after else 0
        out.append(
            {
                "item_code": row.item_code,
                "batch_no": batch_no,
                "transferred": flt(transferred, 3),
                "before_qty": flt(before_qty, 3),
                "after_qty": flt(after_qty, 3),
            }
        )
    return out


# ---------------------------------------------------------------------------
# 3. Build (or reuse) a BOM from actuals; link WO + its other job cards
# ---------------------------------------------------------------------------
@frappe.whitelist()
def apply_actual_bom(work_order, job_card, actual_consumption):
    """
    job_card: the job card whose actual_consumption is being recorded
        (the first job card of the work order). Required so the BOM's
        basis quantity can be derived from that SAME job card's Roll
        records — not the Work Order's overall target qty.
    actual_consumption: JSON list of {item_code, qty, before_qty, after_qty}.

    Persists the operator's Before/After cone weights onto the Work
    Order Item rows, then builds the actuals BOM. Idempotent per work
    order via BOM.custom_source_work_order:
      - if an active BOM already tagged with this WO exists, cancel it
        and rebuild from the latest actuals;
      - otherwise create a new active BOM.

    Then re-point Work Order.bom_no and every draft Job Card of the WO
    to it.
    Returns {"success": True, "bom_no": <bom>, "reused": bool}.
    """
    if isinstance(actual_consumption, str):
        actual_consumption = json.loads(actual_consumption)
    if not actual_consumption:
        frappe.throw("No actual consumption provided.")
    if not job_card:
        frappe.throw("job_card is required to determine the BOM's basis quantity.")

    wo = frappe.get_doc("Work Order", work_order)
    produced_item = wo.production_item

    qty = _get_produced_qty_for_job_card(job_card)
    if not qty:
        frappe.throw(
            f"Could not determine the production quantity for job card "
            f"{job_card} — no Roll records found against it yet. Make "
            f"sure rolls are logged (create_knit_roll / save_roll_data) "
            f"before Submit Job Card triggers the actuals BOM build."
        )

    # Persist operator-entered Before/After cone weights onto the WO Item rows
    woi_meta = frappe.get_meta("Work Order Item")
    has_before = woi_meta.has_field("custom_before_qty")
    has_after = woi_meta.has_field("custom_after_qty")
    weights = {r.get("item_code"): r for r in actual_consumption}
    dirty = False
    for row in wo.required_items:
        w = weights.get(row.item_code)
        if not w:
            continue
        if has_before and w.get("before_qty") is not None:
            row.custom_before_qty = flt(w.get("before_qty"))
            dirty = True
        if has_after and w.get("after_qty") is not None:
            row.custom_after_qty = flt(w.get("after_qty"))
            dirty = True
    if dirty:
        for row in wo.required_items:
            row.db_update()
        frappe.db.commit()

    has_tag = frappe.get_meta("BOM").has_field("custom_source_work_order")
    if not has_tag:
        frappe.throw(
            "BOM is missing the custom_source_work_order field. Run the "
            "create_custom_fields patch before using apply_actual_bom — "
            "without it, actuals BOMs cannot be reused/replaced per work "
            "order and a new BOM will be minted on every call."
        )

    existing = frappe.db.get_value(
        "BOM",
        {
            "custom_source_work_order": work_order,
            "item": produced_item,
            "docstatus": 1,
            "is_active": 1,
        },
        "name",
    )

    rows = []
    for r in actual_consumption:
        item_code = r.get("item_code")
        act_qty = flt(r.get("qty"))
        if not item_code or act_qty <= 0:
            continue
        uom = frappe.db.get_value("Item", item_code, "stock_uom") or "Kgs"
        rows.append({"item_code": item_code, "qty": act_qty, "uom": uom, "stock_uom": uom})

    if not rows:
        frappe.throw("No valid yarn rows to build the BOM.")

    reused = False
    if existing:
        try:
            frappe.get_doc("BOM", existing).cancel()
            reused = True
        except Exception:
            existing = None  # couldn't cancel; fall through to a plain new BOM

    bom = frappe.new_doc("BOM")
    bom.item = produced_item
    bom.quantity = qty  # FIX: this job card's own production (from Roll), not wo.qty
    bom.company = wo.company
    bom.is_active = 1
    bom.is_default = 0
    bom.rm_cost_as_per = "Valuation Rate"
    bom.custom_source_work_order = work_order
    for row in rows:
        bom.append("items", row)

    bom.insert(ignore_permissions=True)
    bom.submit()

    frappe.db.set_value("Work Order", work_order, "bom_no", bom.name)

    if frappe.get_meta("Job Card").has_field("bom_no"):
        for jc in frappe.get_all(
            "Job Card",
            filters={"work_order": work_order, "docstatus": ["<", 1]},
            pluck="name",
        ):
            frappe.db.set_value("Job Card", jc, "bom_no", bom.name)

    frappe.db.commit()
    return {"success": True, "bom_no": bom.name, "reused": reused, "basis_qty": qty}


# ---------------------------------------------------------------------------
# Registration note
# ---------------------------------------------------------------------------
# Map the short aliases the Vue app calls to these functions using the same
# mechanism as your other knit_* aliases. In hooks.py:
#
#   override_whitelisted_methods = {
#       "knit_is_first_job_card":           "pranera_knit.api.yarn_consumption.is_first_job_card",
#       "knit_snapshot_before_consumption": "pranera_knit.api.yarn_consumption.snapshot_before_consumption",
#       "knit_save_before_consumption":     "pranera_knit.api.yarn_consumption.save_before_consumption",
#       "knit_get_yarn_consumption":        "pranera_knit.api.yarn_consumption.get_yarn_consumption",
#       "knit_apply_actual_bom":            "pranera_knit.api.yarn_consumption.apply_actual_bom",
#   }
