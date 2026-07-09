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
    """The single batch transferred for this item into WIP for the work order."""
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
        ORDER BY qty DESC
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
def apply_actual_bom(work_order, actual_consumption):
    """
    actual_consumption: JSON list of {item_code, qty, before_qty, after_qty}.

    Persists the operator's Before/After cone weights onto the Work Order Item
    rows, then builds the actuals BOM. Idempotent per work order via
    BOM.custom_source_work_order:
      - if an active BOM already tagged with this WO exists, cancel it and
        rebuild from the latest actuals;
      - otherwise create a new active BOM.

    Then re-point Work Order.bom_no and every draft Job Card of the WO to it.
    Returns {"success": True, "bom_no": <bom>, "reused": bool}.
    """
    if isinstance(actual_consumption, str):
        actual_consumption = json.loads(actual_consumption)
    if not actual_consumption:
        frappe.throw("No actual consumption provided.")

    wo = frappe.get_doc("Work Order", work_order)
    produced_item = wo.production_item
    qty = flt(wo.qty) or 1.0

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

    existing = None
    if has_tag:
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
    bom.quantity = qty
    bom.company = wo.company
    bom.is_active = 1
    bom.is_default = 0
    bom.rm_cost_as_per = "Valuation Rate"
    if has_tag:
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
    return {"success": True, "bom_no": bom.name, "reused": reused}


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
