"""Job Card submit from the Knit App: Roll Packing List + Job Card + Manufacture.

Python port of the "knit_submit_roll_packing_list_v2" Server Script, which
the Knit App calls when a Job Card is submitted (CreateRollPage.vue). Routed
here through override_whitelisted_methods in hooks.py, so the app keeps
calling the same method name. Keep the Server Script itself disabled-not-
deleted as a reference backup, like the other ported scripts.

Behaviour is the same as the script, plus one addition:

AUTO TOP-UP (Material Receipt) INSTEAD OF A NEGATIVE-STOCK FAILURE
------------------------------------------------------------------
When the Manufacture entry would consume more of a raw material than is in
the work order's WIP warehouse, the submit used to stop ("Insufficient
transferred batch stock ...", or ERPNext's negative-stock error) and someone
had to post a Material Receipt by hand (MR/26/..., Job Card set) and retry.

Now the shortfall is worked out before the Manufacture entry is built, and
one Material Receipt (series MR/26/) is created and submitted for it:
item, exact short qty, target = the WIP warehouse, batch = the batch being
consumed, Job Card = this job card, rate = the batch's purchase rate (never
negative, see _batch_rate). The Manufacture entry is then posted in the same request.
The audit team gets an email for every such receipt (AUDIT_EMAILS).

Everything runs in one transaction under the Job Card row lock: if any
later step fails, the receipt and its email are rolled back with it.
"""

import json

import frappe
from frappe.utils import flt, get_datetime, now_datetime, nowtime, today

AUDIT_EMAILS = ["manigandan@praneraservices.com"]
TOPUP_SERIES = "MR/26/"
QTY_EPS = 0.0001


@frappe.whitelist()
def submit_roll_packing_list_v2(jobcard=None, work_order=None, actual_consumption=None, **kwargs):
    if not jobcard or not work_order:
        frappe.throw("jobcard and work_order are required")

    # Row-lock the Job Card for the whole request so concurrent submits
    # (double tap / retry) serialize. Held until the final commit -- do NOT
    # add an intermediate commit below, or a second request can slip in and
    # create a duplicate Manufacture Stock Entry.
    frappe.db.get_value("Job Card", jobcard, "name", for_update=True)

    actuals = []
    if actual_consumption:
        try:
            actuals = json.loads(actual_consumption) if isinstance(actual_consumption, str) else actual_consumption
        except Exception:
            actuals = []
    use_actuals = bool(actuals and isinstance(actuals, list) and len(actuals) > 0)

    existing_rpl = frappe.db.get_value("Roll Packing List", {"document_name": jobcard, "docstatus": 1}, "name")
    existing_se = frappe.db.get_value(
        "Stock Entry",
        {"work_order": work_order, "custom_job_card": jobcard, "stock_entry_type": "Manufacture", "docstatus": 1},
        "name",
    )
    existing_jc_submitted = frappe.db.get_value("Job Card", {"name": jobcard, "docstatus": 1}, "name")

    jc_docstatus = frappe.db.get_value("Job Card", jobcard, "docstatus")
    if jc_docstatus == 2:
        frappe.throw("Job Card is cancelled in ERP. Please amend or recreate it before resubmitting.")
    if existing_jc_submitted and existing_rpl and existing_se:
        frappe.throw(
            "Job Card already fully submitted. RPL: " + str(existing_rpl) + ", Stock Entry: " + str(existing_se)
        )

    rolls = frappe.db.sql(
        "SELECT name, item_code, batch, roll_weight, total_qty, stock_uom, start_time, end_time "
        "FROM `tabRoll` WHERE job_card = %(jobcard)s ORDER BY name asc",
        {"jobcard": jobcard},
        as_dict=1,
    )
    if not rolls:
        frappe.throw("No rolls found for this job card")

    total_weight = 0.0
    total_pcs = 0
    batch_no = ""
    for r in rolls:
        total_weight += float(r.roll_weight or 0)
        total_pcs += int(r.total_qty or 0)
        if not batch_no and r.batch:
            batch_no = r.batch
    total_weight = round(total_weight, 3)

    # The Job Card / Item's stock_uom decides what "Manufacture Qty" means.
    # For Pcs-tracked items (collars/cuffs) the BOM is per-Pcs, so the
    # finished qty and the consumption ratio are based on total_pcs.
    item_stock_uom = rolls[0].stock_uom or frappe.db.get_value("Job Card", jobcard, "stock_uom") or "Kgs"
    is_pcs_uom = (item_stock_uom or "").strip().lower() == "pcs"
    fg_qty = round(float(total_pcs), 3) if is_pcs_uom else total_weight

    if use_actuals:
        _check_actuals_within_transferred(work_order, actuals)

    # ── Roll Packing List ───────────────────────────────────────────────────
    if not existing_rpl:
        rpl = frappe.new_doc("Roll Packing List")
        rpl.naming_series = "RPL/.####"
        rpl.document_type = "Job Card"
        rpl.document_name = jobcard
        rpl.posting_date = today()
        rpl.transaction_type = "Outward"
        for r in rolls:
            rpl.append("roll_packing_list_item", {
                "item_code": r.item_code,
                "uom": r.stock_uom or "Kgs",
                "roll_no": r.name,
                "batch": r.batch or "",
                "roll_weight": r.roll_weight or 0,
                "total_qty": int(r.total_qty or 0),
            })
        rpl.total_roll_weight = total_weight
        rpl.total_pcs_qty = total_pcs
        rpl.insert(ignore_permissions=True)
        rpl.submit()
        rpl_name = rpl.name
    else:
        rpl_name = existing_rpl

    # ── Job Card ────────────────────────────────────────────────────────────
    jc = frappe.get_doc("Job Card", jobcard)
    if jc.docstatus == 0:
        if not jc.time_logs:
            from_dt = get_datetime(rolls[0].start_time or now_datetime())
            to_dt = get_datetime(rolls[-1].end_time or now_datetime())
            diff_mins = round((to_dt - from_dt).total_seconds() / 60, 2)
            if diff_mins <= 0:
                diff_mins = 1.0
            jc.append("time_logs", {
                "from_time": from_dt, "to_time": to_dt, "time_in_mins": diff_mins, "completed_qty": fg_qty,
            })
            jc.flags.ignore_validate_update_after_submit = True
            jc.save(ignore_permissions=True)
        jc.total_completed_qty = fg_qty
        jc.for_quantity = fg_qty
        for tl in jc.time_logs:
            tl.completed_qty = fg_qty
        jc.flags.ignore_validate = True
        jc.submit()

    frappe.db.set_value("Job Card", jobcard, "status", "Completed", update_modified=False)
    frappe.db.set_value("Job Card", jobcard, "custom_total_qty_to_manufacture", fg_qty, update_modified=False)

    _sync_work_order_operations(work_order)

    # ── Manufacture Stock Entry (with automatic top-up) ─────────────────────
    topup_name = None
    if not existing_se:
        se_name, topup_name = _create_manufacture_entry(
            jobcard, work_order, fg_qty, batch_no, actuals if use_actuals else None
        )
    else:
        se_name = existing_se

    frappe.db.set_value("Roll Packing List", rpl_name, "stock_entry", se_name, update_modified=False)
    frappe.db.commit()

    return {
        "success": True,
        "rpl": rpl_name,
        "stock_entry": se_name,
        "topup_material_receipt": topup_name,
        "roll_count": len(rolls),
        "total_weight": total_weight,
        "total_pcs": total_pcs,
        "manufacture_qty": fg_qty,
        "used_actuals": use_actuals,
    }


def _check_actuals_within_transferred(work_order, actuals):
    fg_item = frappe.db.get_value("Work Order", work_order, "production_item") or ""
    # Material Receipt top-ups tagged to one of this WO's job cards count as
    # transferred too (fix 2026-10-20).
    trows = frappe.db.sql(
        """
        SELECT sle.item_code, SUM(sle.actual_qty) AS qty
        FROM `tabStock Ledger Entry` sle
        WHERE sle.voucher_type = 'Stock Entry' AND sle.item_code != %(fg)s
          AND sle.actual_qty > 0 AND sle.is_cancelled = 0
          AND EXISTS (SELECT 1 FROM `tabStock Entry` se WHERE se.name = sle.voucher_no
              AND se.docstatus = 1
              AND ((se.work_order = %(wo)s AND se.stock_entry_type = 'Material Transfer for Manufacture')
                   OR (se.stock_entry_type = 'Material Receipt' AND (se.work_order = %(wo)s
                       OR se.custom_job_card IN (SELECT jc.name FROM `tabJob Card` jc WHERE jc.work_order = %(wo)s)))))
        GROUP BY sle.item_code HAVING SUM(sle.actual_qty) > 0
        """,
        {"wo": work_order, "fg": fg_item},
        as_dict=True,
    )
    transferred_map = {tr.item_code: float(tr.qty) for tr in trows}
    for a in actuals:
        ic = a.get("item_code")
        aq = float(a.get("qty") or 0)
        tq = transferred_map.get(ic)
        if tq is None:
            frappe.throw("Item " + str(ic) + " was not transferred for this work order.")
        if aq > tq + QTY_EPS:
            frappe.throw("Actual for " + str(ic) + " (" + str(aq) + ") exceeds transferred (" + str(tq) + ").")


def _sync_work_order_operations(work_order):
    wo_doc = frappe.get_doc("Work Order", work_order)
    required_qty = flt(wo_doc.qty)
    for op in frappe.db.get_all("Work Order Operation", filters={"parent": work_order}, fields=["name", "operation"]):
        # Match by operation name, not operation_id -- some Job Cards have a
        # null operation_id, which silently excluded them from this sum.
        op_total = frappe.db.sql(
            """
            SELECT SUM(total_completed_qty) FROM `tabJob Card`
            WHERE work_order = %s AND operation = %s AND docstatus = 1
            """,
            (work_order, op["operation"]),
        )[0][0] or 0
        new_status = "Completed" if op_total >= required_qty and required_qty > 0 else "Work in Progress"
        frappe.db.set_value(
            "Work Order Operation", op["name"], {"status": new_status, "completed_qty": op_total},
            update_modified=False,
        )


def _create_manufacture_entry(jobcard, work_order, fg_qty, fg_batch_no, actuals):
    wo = frappe.get_doc("Work Order", work_order)
    bom = frappe.get_doc("BOM", wo.bom_no)
    bom_fg_qty = float(bom.quantity) if bom.quantity else 1.0
    src_wh = wo.wip_warehouse or wo.source_warehouse

    # Cumulative rounding baseline (fix 2026-10-09): round the WO's RUNNING
    # total and subtract what earlier Manufacture entries (same BOM) already
    # consumed, so per-entry rounding never accumulates.
    prev_fg_qty = float(frappe.db.sql(
        """
        SELECT COALESCE(SUM(fg_completed_qty), 0) FROM `tabStock Entry`
        WHERE docstatus = 1 AND work_order = %(wo)s
          AND stock_entry_type = 'Manufacture' AND bom_no = %(bom)s
        """,
        {"wo": work_order, "bom": wo.bom_no},
    )[0][0] or 0)
    prev_item_consumed = {
        pr.item_code: float(pr.qty or 0)
        for pr in frappe.db.sql(
            """
            SELECT sed.item_code, COALESCE(SUM(ABS(sed.transfer_qty)), 0) AS qty
            FROM `tabStock Entry` se
            JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
            WHERE se.docstatus = 1 AND se.work_order = %(wo)s
              AND se.stock_entry_type = 'Manufacture' AND se.bom_no = %(bom)s
              AND sed.s_warehouse IS NOT NULL
            GROUP BY sed.item_code
            """,
            {"wo": work_order, "bom": wo.bom_no},
            as_dict=True,
        )
    }

    allocator = _BatchAllocator(work_order, src_wh)

    actual_map = {}
    if actuals:
        for a in actuals:
            actual_map[a.get("item_code")] = float(a.get("qty") or 0)

    rm_rows = []     # (item_code, qty, batch_no or None, bom_item)
    topups = []      # {"item_code", "batch_no", "qty"}
    for bom_item in bom.items:
        if bom_item.item_code in actual_map:
            consumed_qty = round(actual_map[bom_item.item_code], 3)
        else:
            ratio = float(bom_item.qty) / bom_fg_qty
            cum_target = round(ratio * (prev_fg_qty + fg_qty), 3)
            consumed_qty = round(cum_target - prev_item_consumed.get(bom_item.item_code, 0.0), 3)
            if consumed_qty <= QTY_EPS:
                # Earlier entries already covered this job card's share.
                continue

        allocations, short = allocator.allocate(bom_item.item_code, consumed_qty)
        if short > QTY_EPS:
            # Transferred for this WO, but its batches in the WIP don't hold
            # enough. Previously a hard stop; now topped up by a Material
            # Receipt into the batch most recently transferred for this WO.
            topup_batch = allocator.topup_batch(bom_item.item_code)
            topups.append({"item_code": bom_item.item_code, "batch_no": topup_batch, "qty": round(short, 3)})
            allocations.append((topup_batch, round(short, 3)))

        if allocations:
            for alloc_batch, alloc_qty in _merge_allocations(allocations):
                rm_rows.append((bom_item.item_code, alloc_qty, alloc_batch, bom_item))
        else:
            # Never transferred for this WO (non-batch item, or issued some
            # other way): same fallback as before -- no batch pinned.
            rm_rows.append((bom_item.item_code, consumed_qty, None, bom_item))
            if not frappe.db.get_value("Item", bom_item.item_code, "has_batch_no"):
                have = flt(frappe.db.get_value(
                    "Bin", {"item_code": bom_item.item_code, "warehouse": src_wh}, "actual_qty"
                ))
                if consumed_qty > have + QTY_EPS:
                    topups.append({
                        "item_code": bom_item.item_code, "batch_no": None,
                        "qty": round(consumed_qty - max(have, 0.0), 3),
                    })

    topup_name = None
    if topups:
        topup_name = _create_topup_receipt(jobcard, work_order, wo.company, src_wh, topups)

    se = frappe.new_doc("Stock Entry")
    se.naming_series = "MF/26/"
    se.stock_entry_type = "Manufacture"
    se.purpose = "Manufacture"
    se.work_order = work_order
    se.custom_job_card = jobcard
    se.company = wo.company
    se.from_bom = 1
    se.bom_no = wo.bom_no
    se.fg_completed_qty = fg_qty
    se.posting_date = today()
    se.posting_time = nowtime()
    for item_code, qty, rm_batch, bom_item in rm_rows:
        row = {
            "item_code": item_code, "qty": qty, "transfer_qty": qty,
            "uom": bom_item.uom or "Kgs", "stock_uom": bom_item.stock_uom or "Kgs", "conversion_factor": 1.0,
            "s_warehouse": src_wh, "is_finished_item": 0,
            "allow_zero_valuation_rate": 1, "use_serial_batch_fields": 1,
        }
        if rm_batch:
            row["batch_no"] = rm_batch
        se.append("items", row)
    se.append("items", {
        "item_code": wo.production_item, "qty": fg_qty, "transfer_qty": fg_qty,
        "uom": bom.uom or "Kgs", "stock_uom": bom.uom or "Kgs", "conversion_factor": 1.0,
        "t_warehouse": wo.fg_warehouse, "is_finished_item": 1, "batch_no": fg_batch_no,
        "allow_zero_valuation_rate": 1, "use_serial_batch_fields": 1,
    })
    se.flags.ignore_validate = True
    se.insert(ignore_permissions=True)
    se.flags.ignore_validate = True
    se.submit()
    return se.name, topup_name


def _merge_allocations(allocations):
    out, order = {}, []
    for b, q in allocations:
        if b not in out:
            out[b] = 0.0
            order.append(b)
        out[b] += q
    return [(b, round(out[b], 3)) for b in order]


class _BatchAllocator:
    """FIFO allocation from this WO's OWN transferred batches (Material
    Transfer for Manufacture / Material Transfer, plus Material Receipt
    top-ups tagged with one of the WO's job cards), net of what earlier
    Manufacture entries consumed, each capped by its live balance in the
    WIP warehouse. Batches transferred against other WOs are never used."""

    def __init__(self, work_order, wip):
        self.work_order = work_order
        self.wip = wip
        self._wip_cache = {}
        self.transferred_items = set()
        self.last_batch = {}   # item -> batch most recently transferred for this WO
        self.queue = {}

        transfer_rows = frappe.db.sql(
            """
            SELECT sed.item_code, COALESCE(sbe.batch_no, sed.batch_no) AS batch_no,
                   SUM(ABS(sed.transfer_qty)) AS qty,
                   MIN(se.creation) AS first_creation, MAX(se.creation) AS last_creation
            FROM `tabStock Entry` se
            JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
            LEFT JOIN `tabSerial and Batch Entry` sbe
                ON sbe.parent = sed.serial_and_batch_bundle
                AND sbe.parenttype = 'Serial and Batch Bundle'
            WHERE se.docstatus = 1
              AND se.work_order = %(wo)s
              AND se.stock_entry_type IN ('Material Transfer for Manufacture', 'Material Transfer')
            GROUP BY sed.item_code, COALESCE(sbe.batch_no, sed.batch_no)
            ORDER BY sed.item_code, first_creation ASC
            """,
            {"wo": work_order},
            as_dict=True,
        )
        # Material Receipt top-ups into this WO's WIP (fix 2026-10-20): only
        # those tagged with one of this WO's job cards (or legacy receipts
        # stamped with the WO). Untagged receipts never count.
        receipt_rows = frappe.db.sql(
            """
            SELECT sed.item_code, COALESCE(sbe.batch_no, sed.batch_no) AS batch_no,
                   SUM(ABS(sed.transfer_qty)) AS qty, MAX(se.creation) AS last_creation
            FROM `tabStock Entry` se
            JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
            LEFT JOIN `tabSerial and Batch Entry` sbe
                ON sbe.parent = sed.serial_and_batch_bundle
                AND sbe.parenttype = 'Serial and Batch Bundle'
            WHERE se.docstatus = 1
              AND se.stock_entry_type = 'Material Receipt'
              AND sed.t_warehouse = %(wip)s
              AND (se.work_order = %(wo)s
                   OR se.custom_job_card IN (SELECT jc.name FROM `tabJob Card` jc WHERE jc.work_order = %(wo)s))
            GROUP BY sed.item_code, COALESCE(sbe.batch_no, sed.batch_no)
            """,
            {"wo": work_order, "wip": wip},
            as_dict=True,
        )

        merged_qty, merged_order, last_seen = {}, [], {}
        for tr in list(transfer_rows) + list(receipt_rows):
            key = (tr.item_code, tr.batch_no)
            if key not in merged_qty:
                merged_qty[key] = 0.0
                merged_order.append(key)
            merged_qty[key] += float(tr.qty or 0)
            if tr.batch_no and (tr.item_code not in last_seen or tr.last_creation > last_seen[tr.item_code][1]):
                last_seen[tr.item_code] = (tr.batch_no, tr.last_creation)
        self.last_batch = {item: v[0] for item, v in last_seen.items()}

        consumed_map = {
            (cr.item_code, cr.batch_no): float(cr.qty or 0)
            for cr in frappe.db.sql(
                """
                SELECT sed.item_code, COALESCE(sbe.batch_no, sed.batch_no) AS batch_no,
                       SUM(ABS(sed.transfer_qty)) AS qty
                FROM `tabStock Entry` se
                JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
                LEFT JOIN `tabSerial and Batch Entry` sbe
                    ON sbe.parent = sed.serial_and_batch_bundle
                    AND sbe.parenttype = 'Serial and Batch Bundle'
                WHERE se.docstatus = 1 AND se.work_order = %(wo)s
                  AND se.stock_entry_type = 'Manufacture' AND sed.s_warehouse IS NOT NULL
                GROUP BY sed.item_code, COALESCE(sbe.batch_no, sed.batch_no)
                """,
                {"wo": work_order},
                as_dict=True,
            )
        }

        for key in merged_order:
            t_item, t_batch = key
            if not t_batch:
                continue
            self.transferred_items.add(t_item)
            available = min(merged_qty[key] - consumed_map.get(key, 0.0), self._wip_batch_qty(t_item, t_batch))
            if available > QTY_EPS:
                self.queue.setdefault(t_item, []).append({"batch_no": t_batch, "available": available})

    def _wip_batch_balances(self, item_code):
        # Balance in the WIP (source) warehouse, not Batch.batch_qty (global),
        # since sibling WOs share one WIP warehouse (fix 2026-10-09).
        if item_code not in self._wip_cache:
            rows = frappe.db.sql(
                """
                SELECT t.batch_no, SUM(t.q) AS qty FROM (
                    SELECT sbe.batch_no AS batch_no, sbe.qty AS q
                    FROM `tabStock Ledger Entry` sle
                    JOIN `tabSerial and Batch Entry` sbe ON sbe.parent = sle.serial_and_batch_bundle
                    WHERE sle.is_cancelled = 0 AND sle.item_code = %(item)s AND sle.warehouse = %(wh)s
                    UNION ALL
                    SELECT sle.batch_no AS batch_no, sle.actual_qty AS q
                    FROM `tabStock Ledger Entry` sle
                    WHERE sle.is_cancelled = 0 AND sle.item_code = %(item)s AND sle.warehouse = %(wh)s
                      AND IFNULL(sle.serial_and_batch_bundle, '') = '' AND IFNULL(sle.batch_no, '') != ''
                ) t
                GROUP BY t.batch_no
                """,
                {"item": item_code, "wh": self.wip},
                as_dict=True,
            )
            self._wip_cache[item_code] = {r.batch_no: float(r.qty or 0) for r in rows}
        return self._wip_cache[item_code]

    def _wip_batch_qty(self, item_code, batch_no):
        return self._wip_batch_balances(item_code).get(batch_no, 0.0)

    def allocate(self, item_code, required_qty):
        """Returns (allocations, short). `short` > 0 only for items that WERE
        transferred for this WO but whose batches don't cover the need."""
        allocations, remaining = [], required_qty
        for entry in self.queue.get(item_code, []):
            if remaining <= QTY_EPS:
                break
            take = min(entry["available"], remaining)
            if take > QTY_EPS:
                allocations.append((entry["batch_no"], round(take, 3)))
                entry["available"] -= take
                remaining -= take
        short = remaining if (remaining > QTY_EPS and item_code in self.transferred_items) else 0.0
        return allocations, short

    def topup_batch(self, item_code):
        return self.last_batch.get(item_code)


def _batch_rate(item_code, batch_no, warehouse):
    """Rate for an automatic top-up. Never a running average: ERPNext's
    moving-average valuation_rate on a ledger row can drift below zero in
    a WIP warehouse (YRSCC025/GRIEGE showed -0.011 in WIP - FK10 after
    MF/26/27337), which made the receipt fail with "Value cannot be negative
    for Basic Rate" (PO-JOB22508). In order:
      1. the batch's purchase / subcontracting receipt rate
      2. any positive incoming rate the batch was received at
      3. the item's latest positive valuation rate, any warehouse
      4. the Item master valuation rate
    Never negative; 0 only if nothing else exists."""
    if batch_no:
        for voucher_filter in (
            "AND sbb.voucher_type IN ('Purchase Receipt', 'Subcontracting Receipt')",
            "",
        ):
            r = frappe.db.sql(
                f"""
                SELECT sbe.incoming_rate
                FROM `tabSerial and Batch Entry` sbe
                JOIN `tabSerial and Batch Bundle` sbb ON sbb.name = sbe.parent
                WHERE sbe.batch_no = %(batch)s AND sbb.item_code = %(item)s
                  AND sbb.docstatus = 1 AND sbb.is_cancelled = 0
                  AND sbb.type_of_transaction = 'Inward' AND sbe.incoming_rate > 0
                  {voucher_filter}
                ORDER BY sbb.posting_datetime DESC, sbb.creation DESC LIMIT 1
                """,
                {"item": item_code, "batch": batch_no},
            )
            if r and flt(r[0][0]) > 0:
                return flt(r[0][0])
    r = frappe.db.sql(
        """
        SELECT valuation_rate FROM `tabStock Ledger Entry`
        WHERE is_cancelled = 0 AND item_code = %(item)s AND valuation_rate > 0
        ORDER BY posting_datetime DESC, creation DESC LIMIT 1
        """,
        {"item": item_code},
    )
    if r and flt(r[0][0]) > 0:
        return flt(r[0][0])
    return max(flt(frappe.db.get_value("Item", item_code, "valuation_rate")), 0.0)


def _create_topup_receipt(jobcard, work_order, company, wip, topups):
    """One submitted Material Receipt (MR/26/) for all shortfalls of this
    job card, into the WO's WIP, tagged with the job card so the
    Manufacture entry is allowed to consume it. Emails the audit team."""
    for t in topups:
        if t["batch_no"] is None and frappe.db.get_value("Item", t["item_code"], "has_batch_no"):
            frappe.throw(
                "Cannot top up " + t["item_code"] + " for " + work_order +
                ": no batch was transferred for it, so there is no batch to receive into."
            )

    mr = frappe.new_doc("Stock Entry")
    mr.naming_series = TOPUP_SERIES
    mr.stock_entry_type = "Material Receipt"
    mr.purpose = "Material Receipt"
    mr.company = company
    mr.set_posting_time = 1
    mr.posting_date = today()
    mr.posting_time = nowtime()
    mr.custom_job_card = jobcard
    mr.remarks = (
        "Auto top-up on Job Card submit (" + jobcard + " / " + work_order + "): the Manufacture entry "
        "needed more than the WIP held. Created by the Knit App."
    )
    for t in topups:
        stock_uom = frappe.db.get_value("Item", t["item_code"], "stock_uom") or "Kgs"
        rate = _batch_rate(t["item_code"], t["batch_no"], wip)
        t["rate"] = rate
        t["uom"] = stock_uom
        row = {
            "item_code": t["item_code"], "qty": t["qty"], "transfer_qty": t["qty"],
            "uom": stock_uom, "stock_uom": stock_uom, "conversion_factor": 1.0,
            "t_warehouse": wip, "basic_rate": rate, "allow_zero_valuation_rate": 0 if rate else 1,
            "use_serial_batch_fields": 1,
        }
        if t["batch_no"]:
            row["batch_no"] = t["batch_no"]
        mr.append("items", row)
    mr.insert(ignore_permissions=True)
    mr.submit()

    _notify_audit(mr, jobcard, work_order, wip, topups)
    return mr.name


def _notify_audit(mr, jobcard, work_order, wip, topups):
    rows = "".join(
        "<tr><td>{item}</td><td>{batch}</td><td style='text-align:right'>{qty}</td><td>{uom}</td>"
        "<td style='text-align:right'>{rate}</td></tr>".format(
            item=frappe.utils.escape_html(t["item_code"]),
            batch=frappe.utils.escape_html(t["batch_no"] or "-"),
            qty=t["qty"], uom=t.get("uom") or "", rate=round(flt(t.get("rate")), 2),
        )
        for t in topups
    )
    link = frappe.utils.get_url_to_form("Stock Entry", mr.name)
    message = f"""
        <p>A Material Receipt was created and submitted automatically while submitting a Job Card
        in the Knit App, because the Manufacture entry needed more raw material than the WIP held.</p>
        <table cellpadding="4" style="border-collapse:collapse">
          <tr><td><b>Material Receipt</b></td><td><a href="{link}">{mr.name}</a></td></tr>
          <tr><td><b>Job Card</b></td><td>{frappe.utils.escape_html(jobcard)}</td></tr>
          <tr><td><b>Work Order</b></td><td>{frappe.utils.escape_html(work_order)}</td></tr>
          <tr><td><b>Target warehouse</b></td><td>{frappe.utils.escape_html(wip)}</td></tr>
          <tr><td><b>Submitted by</b></td><td>{frappe.utils.escape_html(frappe.session.user)}</td></tr>
          <tr><td><b>Posting</b></td><td>{mr.posting_date} {mr.posting_time}</td></tr>
        </table>
        <br>
        <table border="1" cellpadding="4" style="border-collapse:collapse">
          <tr><th>Item</th><th>Batch</th><th>Qty</th><th>UOM</th><th>Rate</th></tr>
          {rows}
        </table>
    """
    frappe.sendmail(
        recipients=AUDIT_EMAILS,
        subject=f"Auto Material Receipt {mr.name} - Job Card {jobcard} ({work_order})",
        message=message,
        reference_doctype="Stock Entry",
        reference_name=mr.name,
    )
