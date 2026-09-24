"""
pranera_knit/api/knit.py
Server-side whitelisted methods called from the Vue PWA.

----------------------------------------------------------------------------
FIX LOG (bug analysis + patch, applied 2026-08-17)
----------------------------------------------------------------------------
submit_roll_packing_list() previously left raw-material row population to
ERPNext's default Stock Entry get_items(), which FIFO-picks batches
across the WHOLE source warehouse — not scoped to the batch that was
actually transferred in for this specific work order.

Confirmed on MF/26/23243 (WO/26/10352): it consumed 49.96 kg of
YRFPP090/GREIGE, blended across THREE batches, even though only
26PTIN1635/PO-18527/BH-GLD99 was ever moved into WIP for that WO via
Material Transfer for Manufacture. ~10.5 kg came from batches never
issued against this work order at all. Scale: 48 of 5,494 GKF
raw-material consumption rows since 1 May 2026 span more than one
batch in their bundle.

Fixed: raw-material rows are now built explicitly from the BOM, with
each item's batch resolved via yarn_consumption._transferred_batch_for_item()
(the same logic already used correctly elsewhere in this app) instead
of letting ERPNext auto-pick. If no transferred batch can be found for
an item, the function now throws instead of silently letting ERPNext
blend batches.
----------------------------------------------------------------------------
"""
import frappe
import json
from frappe import _
from frappe.utils import now_datetime, today, get_datetime, nowtime

from pranera_knit.api.yarn_consumption import _transferred_batch_for_item


# ── App access ────────────────────────────────────────────────────────────────

@frappe.whitelist()
def check_app_permission():
    user = frappe.session.user
    emp = frappe.db.get_value("Employee", {"user_id": user}, "custom_can_access_knitting_app")
    return bool(emp)


@frappe.whitelist()
def get_employee_for_user(user=None):
    user = user or frappe.session.user
    emp = frappe.db.get_value(
        "Employee", {"user_id": user},
        ["name", "employee_name", "designation", "department", "custom_can_access_knitting_app"],
        as_dict=True
    )
    if not emp:
        fullname = frappe.utils.get_fullname(user)
        emp = frappe.db.get_value(
            "Employee", {"employee_name": fullname},
            ["name", "employee_name", "designation", "department", "custom_can_access_knitting_app"],
            as_dict=True
        )
    return emp or {}


# ── Job Cards ─────────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_job_cards_for_knit_app(username=None, designation=None):
    filters = [["Job Card", "docstatus", "!=", 2]]
    if designation in ["Knitting Operator", "Senior Knitting Operator"]:
        filters.append(["Job Card Time Log", "employee", "=", username])
    return frappe.get_list(
        "Job Card", filters=filters,
        fields=[
            "name", "work_order", "production_item", "item_name",
            "commercial_name", "color", "width", "status", "workstation",
            "for_quantity", "produced_qty", "project", "docstatus",
            "stock_uom",
            "quality_inspection as quality_inspection_erp_name"
        ],
        order_by="modified desc", limit=500
    )


# ── Roll Management ───────────────────────────────────────────────────────────

@frappe.whitelist()
def create_knit_roll(job_card, batch_no=None):
    """
    Creates a new Roll entry for the given job card.
    Returns roll info (mirrors createKnitCCRollNoInDB).
    """
    frappe.has_permission("Roll", throw=True)

    # Get existing rolls to compute next idx
    existing = frappe.get_list(
        "Roll",
        filters=[["Roll", "job_card", "=", job_card]],
        fields=["name", "idx"],
        order_by="idx desc",
        limit=1
    )
    next_idx = (existing[0].idx + 1) if existing else 1

    # Get job card details
    jc = frappe.get_doc("Job Card", job_card)

    roll = frappe.new_doc("Roll")
    roll.job_card    = job_card
    roll.idx         = next_idx
    roll.work_order  = jc.work_order
    roll.item_code   = jc.production_item
    roll.item_name   = jc.item_name or ""
    roll.batch       = batch_no or ""
    roll.start_time  = now_datetime()

    roll.insert(ignore_permissions=True)
    frappe.db.commit()

    return [{"name": roll.name, "idx": roll.idx, "start_time": str(roll.start_time), "batch_no": batch_no}]


@frappe.whitelist()
def save_roll_data(
    job_card, work_order, item_code, roll_no, roll_weight,
    batch=None, shift=None, start_time=None, end_time=None,
    total_time_seconds=None, breakdown_time_seconds=None,
    net_production_time_seconds=None, efficiency_percentage=None,
    total_qty=None, mistake_qty=None, stock_uom=None,
    item_name=None, commercial_name=None, color=None, width=None,
    project=None, knitting_machine_no=None, knit_operator_name=None,
    complete_roll=None, next_roll_start_time=None
):
    """
    Updates Roll entry with production data (mirrors updateKnitCCRollNoInDB + insertIntoRollTable).
    roll_no is the idx value.
    """
    frappe.has_permission("Roll", throw=True)

    # Find roll by idx + job_card
    roll_name = frappe.db.get_value(
        "Roll",
        {"job_card": job_card, "idx": int(roll_no)},
        "name"
    )

    if roll_name:
        roll = frappe.get_doc("Roll", roll_name)
    else:
        # Fallback: create if missing
        roll = frappe.new_doc("Roll")
        roll.job_card = job_card
        roll.idx      = int(roll_no)
        roll.work_order = work_order

    roll.work_order          = work_order or roll.work_order
    roll.item_code           = item_code or roll.item_code
    roll.item_name           = item_name or ""
    roll.commercial_name     = commercial_name or ""
    roll.color               = color or ""
    roll.width               = width or ""
    roll.batch               = batch or ""
    roll.shift               = shift or ""
    roll.roll_weight         = float(roll_weight or 0)
    roll.total_qty           = float(total_qty or 0)
    roll.mistake_qty         = float(mistake_qty or 0)
    roll.correct_qty         = float(total_qty or 0) - float(mistake_qty or 0)
    roll.avg_weight_per_pcs  = (float(roll_weight or 0) / float(total_qty)) if total_qty and float(total_qty) > 0 else 0
    roll.stock_uom           = stock_uom or "Kgs"
    roll.project             = project or ""
    roll.knitting_machine_no = knitting_machine_no or ""
    roll.name_of_the_operator = knit_operator_name or ""
    roll.start_time          = get_datetime(start_time) if start_time else roll.start_time
    roll.end_time            = get_datetime(end_time) if end_time else now_datetime()

    if roll_name:
        roll.save(ignore_permissions=True)
    else:
        roll.insert(ignore_permissions=True)

    frappe.db.commit()
    return {"success": True, "name": roll.name, "idx": roll.idx}


@frappe.whitelist()
def check_job_card_rolls(job_card):
    """
    Returns roll count, total weight, total pcs for a job card.
    Mirrors checkJobCardHasRolls.
    """
    rolls = frappe.db.sql("""
        SELECT
            COUNT(*) as roll_count,
            COALESCE(SUM(roll_weight), 0) as total_weight,
            COALESCE(SUM(total_qty), 0) as total_pcs
        FROM `tabRoll`
        WHERE job_card = %(job_card)s
        AND (end_time IS NOT NULL OR roll_weight > 0)
    """, {"job_card": job_card}, as_dict=True)

    r = rolls[0] if rolls else {}
    return {
        "success": True,
        "has_rolls": (r.get("roll_count") or 0) > 0,
        "roll_count": int(r.get("roll_count") or 0),
        "total_weight": round(float(r.get("total_weight") or 0), 3),
        "total_pcs": round(float(r.get("total_pcs") or 0), 3),
    }


@frappe.whitelist()
def get_roll_numbers_for_job_card(job_card):
    """Returns all roll numbers for a job card. Used in QI."""
    rolls = frappe.get_list(
        "Roll",
        filters=[["Roll", "job_card", "=", job_card]],
        fields=["name", "idx", "start_time", "roll_weight"],
        order_by="idx asc"
    )
    return [{"id": r.name, "idx": r.idx} for r in rolls]


# ── Breakdown ─────────────────────────────────────────────────────────────────

@frappe.whitelist()
def record_breakdown(roll_no, job_card, breakdown_start, breakdown_end=None,
                     duration_seconds=None, recorded_by=None):
    """Records breakdown time against a Roll."""
    # roll_no here is the Roll document name
    if frappe.db.exists("Roll", roll_no):
        frappe.db.set_value(
            "Roll", roll_no, "barre",
            f"BD:{breakdown_start}→{breakdown_end or 'active'} ({duration_seconds}s)"
        )
        frappe.db.commit()
    return {"success": True}


# ── MTM / Reconciliation ──────────────────────────────────────────────────────

@frappe.whitelist()
def get_mtm_data(work_order):
    """
    Returns stock data for a work order for reconciliation.
    Mirrors getMTMNoInDB in Ionic app.
    """
    try:
        # NOTE (ERPNext v15): batch info on Stock Ledger Entries lives in the
        # Serial and Batch Bundle, not in sle.batch_no (which is usually NULL).
        # Grouping on sle.batch_no alone returns blank batches, which forces
        # ERPNext to auto-pick batches FIFO on reconciliation submit — and that
        # blows up (BatchNegativeStockError) if any batch in the warehouse has
        # gone negative. Expand the bundle so each batch is reported explicitly.
        items = frappe.db.sql("""
            SELECT
                sle.item_code,
                SUM(COALESCE(sbe.qty, sle.actual_qty)) as qty,
                sle.warehouse as t_warehouse,
                COALESCE(sbe.batch_no, sle.batch_no) as batch_no,
                item.stock_uom
            FROM `tabStock Ledger Entry` sle
            LEFT JOIN `tabSerial and Batch Entry` sbe
                ON sbe.parent = sle.serial_and_batch_bundle
                AND sbe.parenttype = 'Serial and Batch Bundle'
            LEFT JOIN `tabItem` item ON item.name = sle.item_code
            WHERE sle.voucher_type = 'Stock Entry'
            AND sle.is_cancelled = 0
            AND EXISTS (
                SELECT 1 FROM `tabStock Entry` se
                WHERE se.name = sle.voucher_no
                AND se.docstatus = 1
                AND se.work_order = %(work_order)s
                AND se.stock_entry_type IN ('Manufacture', 'Material Transfer for Manufacture')
            )
            GROUP BY sle.item_code, sle.warehouse, COALESCE(sbe.batch_no, sle.batch_no)
            HAVING SUM(COALESCE(sbe.qty, sle.actual_qty)) > 0.0005
            ORDER BY sle.item_code
        """, {"work_order": work_order}, as_dict=True)
        return items or []
    except Exception as e:
        frappe.log_error(str(e), "get_mtm_data")
        return []


@frappe.whitelist()
def submit_reconciliation(work_order, reconcile_items=None):
    """Submits stock reconciliation. Mirrors submitReconciliationToERP."""
    frappe.has_permission("Stock Reconciliation", throw=True)

    if isinstance(reconcile_items, str):
        reconcile_items = json.loads(reconcile_items)

    if not reconcile_items:
        frappe.throw("No reconciliation items provided")

    sr = frappe.new_doc("Stock Reconciliation")
    sr.purpose      = "Stock Reconciliation"
    sr.company      = frappe.defaults.get_user_default("Company")
    sr.posting_date = today()

    for item in reconcile_items:
        item_code = item.get("item_code")
        batch_no  = item.get("batch_no") or None

        # Auto-create the SCRAP/<WO> and LOSS/<WO> batches if they don't exist
        # yet (Stock Reconciliation won't create batches on the fly).
        if batch_no and not frappe.db.exists("Batch", batch_no):
            if frappe.db.get_value("Item", item_code, "has_batch_no"):
                frappe.get_doc({
                    "doctype":  "Batch",
                    "batch_id": batch_no,
                    "item":     item_code,
                }).insert(ignore_permissions=True)
            else:
                batch_no = None  # non-batched item, drop the pseudo batch

        sr.append("items", {
            "item_code": item_code,
            "warehouse": item.get("s_warehouse"),
            "batch_no":  batch_no,
            "qty":       float(item.get("phy_qty") or 0),
            # v15: force ERPNext to reconcile THIS batch specifically instead
            # of auto-building a FIFO bundle across all batches in the
            # warehouse (which fails if any unrelated batch is negative).
            "use_serial_batch_fields": 1,
        })

    sr.insert(ignore_permissions=True)
    sr.submit()
    frappe.db.commit()
    return {"success": True, "stock_entry_name": sr.name}


# ── Stock Entry ───────────────────────────────────────────────────────────────

@frappe.whitelist()
def submit_roll_packing_list(jobcard, work_order):
    """Creates a Stock Entry (Manufacture) in ERPNext, with raw-material
    rows explicitly scoped to the batch actually transferred in for this
    work order — not ERPNext's default FIFO-across-warehouse pick.

    FIX: previously this just set se.bom_no and called se.save(), leaving
    ERPNext's default get_items() to FIFO-pick raw-material batches across
    the whole source warehouse. Confirmed on MF/26/23243 (WO/26/10352):
    it blended in ~10.5 kg from batches never transferred against that
    work order at all. Now the raw-material rows are built explicitly
    from the BOM, with each item's batch resolved via
    yarn_consumption._transferred_batch_for_item() — the same batch
    resolution already used correctly elsewhere in this app. If no
    transferred batch can be found, this throws instead of silently
    letting ERPNext blend batches.
    """
    frappe.has_permission("Stock Entry", throw=True)

    se = frappe.new_doc("Stock Entry")
    se.stock_entry_type = "Manufacture"
    se.work_order = work_order
    se.job_card = jobcard
    se.company = frappe.defaults.get_user_default("Company")
    se.posting_date = today()

    bom_no = frappe.get_value("Work Order", work_order, "bom_no")
    if bom_no:
        se.from_bom = 1
        se.bom_no = bom_no

        bom = frappe.get_doc("BOM", bom_no)
        wip_warehouse = frappe.get_value("Work Order", work_order, "wip_warehouse")

        for bom_item in bom.items:
            batch_no = _transferred_batch_for_item(work_order, bom_item.item_code)
            row = {
                "item_code": bom_item.item_code,
                "s_warehouse": wip_warehouse,
                "qty": bom_item.qty,  # ERPNext scales this from fg_completed_qty on save
                "uom": bom_item.uom,
                "stock_uom": bom_item.stock_uom,
                "conversion_factor": bom_item.conversion_factor or 1,
            }
            if batch_no:
                row["batch_no"] = batch_no
                row["use_serial_batch_fields"] = 1
            else:
                # No transferred batch found for this item/WO — don't
                # silently let ERPNext auto-pick a wrong one; surface it
                # so the operator/planner fixes the Material Transfer
                # step instead of masking a data problem.
                frappe.throw(
                    f"No Material Transfer for Manufacture batch found for "
                    f"{bom_item.item_code} against {work_order}. Cannot "
                    f"determine which batch to consume — check the "
                    f"transfer entries for this work order before "
                    f"submitting this job card."
                )
            se.append("items", row)

    se.save()
    return {"name": se.name, "status": "Draft"}


def _get_warehouse_address(warehouse):
    """
    Looks up the Address linked to a Warehouse. Warehouse has no forward
    Link field to Address — the relationship only exists the other way,
    via a Dynamic Link row on the Address doc (parenttype=Address,
    link_doctype=Warehouse, link_name=<warehouse>) — so this can't be done
    with a simple fetch_from and has to be a real lookup.
    """
    if not warehouse:
        return None
    return frappe.db.get_value(
        "Dynamic Link",
        {"link_doctype": "Warehouse", "link_name": warehouse, "parenttype": "Address"},
        "parent",
    )


def get_batch_warehouse_overrides(roll_pick_assignment):
    """batch -> warehouse map from a Roll Pick Assignment's own Batch Items
    table (the field populated via get_warehouses_for_batch in
    textiles_and_garments's roll_pick_assignment.py, showing each batch's
    actual per-warehouse qty when the supervisor set it up). A batch
    doesn't necessarily sit in the Assignment's single blanket Source
    Warehouse, so anywhere a batch's rolls get attributed to a warehouse —
    at scan time as much as at final Stock Entry creation — should prefer
    this override over the blanket source_warehouse. Only includes
    batches whose row actually has a warehouse set (that field is
    optional); callers fall back to the blanket source_warehouse for any
    batch missing from this map. Returns {} if roll_pick_assignment is
    falsy (a manual, non-Pick-Order fulfillment)."""
    if not roll_pick_assignment:
        return {}
    return {
        r.batch: r.warehouse
        for r in frappe.get_all(
            "Roll Pick Batch Item",
            filters={"parenttype": "Roll Pick Assignment", "parent": roll_pick_assignment},
            fields=["batch", "warehouse"],
        )
        if r.warehouse
    }


@frappe.whitelist()
def create_roll_picking_entry(pick_type=None, document_name=None, document=None,
                               source_warehouse=None, target_warehouse=None,
                               posting_date=None, date=None, project=None,
                               batch_no=None, from_work_order=None,
                               from_subcontracting=None, rolls=None, items=None,
                               required_items=None, scanned_roll=None,
                               roll_pick_assignment=None):
    """
    Creates a Roll Wise Pick List + Stock Entry (Material Transfer) for the
    picked rolls/batches. Exact port of Node's POST /api/createRollPickingEntry
    (knit_app.js), adapted to call ERPNext directly via frappe.get_doc instead
    of proxying HTTP requests:

      STEP 1 — create + submit a "Roll Wise Pick List":
        * batch_wise_pick_item is always populated (one row per item+batch).
        * roll_wise_pick_item is populated only for genuine roll-level picks —
          a "batch transfer" (every roll's roll_no == its batch_no, i.e. the
          GKF "pick the whole batch" flow) skips this child table.

      STEP 2 — create + submit a Stock Entry (Material Transfer):
        * naming_series is "MT/26/" for pick_type == "To Work Order" (Material
          Transfer for Manufacture), otherwise "MT/26/".
        * items are grouped by (item_code, batch_no) so multiple rolls of the
          same item/batch collapse into a single Stock Entry Detail row.
        * custom_batch_wise_packing_summary carries the batch/qty/roll-count
          breakdown for reporting.
        * work_order / purchase_order / subcontracting_order /
          custom_reference_stock_entry / custom_reference_batch is set based
          on pick_type + document, and project / custom_from_work_order /
          custom_from_subcontracting are set when supplied.

    Accepts both the old simplified payload shape (document_name, items,
    scanned_roll, date) and the full Ionic-app payload shape (document,
    posting_date, rolls, required_items, batch_no, from_work_order,
    from_subcontracting) so either caller works unchanged.

    roll_pick_assignment: optional — when a fulfillment comes from the
    Pick Order flow (a supervisor-assigned task, see api/pick_order.py),
    pass the Roll Pick Assignment name here. On success this stamps that
    reference onto the created Roll Wise Pick List (for traceability) and
    marks the Order's status "Completed". Ordinary manual picks (no Pick
    Order behind them) omit this and nothing changes.
    """
    frappe.has_permission("Stock Entry", throw=True)

    # ── Normalize inputs (accept either payload shape / JSON strings) ──────
    document_name = document or document_name
    posting_date  = posting_date or date or today()
    rolls = rolls if rolls is not None else items
    if isinstance(rolls, str):
        rolls = json.loads(rolls)
    if isinstance(required_items, str):
        required_items = json.loads(required_items)
    rolls = rolls or []

    if not posting_date:
        frappe.throw(_("Posting date is required"))
    if not target_warehouse:
        frappe.throw(_("Target warehouse is required"))
    if not source_warehouse:
        frappe.throw(_("Source warehouse is required"))
    if not rolls:
        frappe.throw(_("At least one roll is required"))

    # When fulfilling a Pick Order, the target qty (pick_qty, set by the
    # supervisor) is the authoritative check — validated here rather than
    # only client-side, since this is the one place a Pick Order's
    # fulfillment actually becomes a real Stock Entry. Accounts for
    # whatever was already submitted against this Order in a prior
    # session too, so partial-then-resume fulfillment is checked against
    # the true cumulative total, not just this call's rolls.
    if roll_pick_assignment:
        pick_qty = frappe.db.get_value("Roll Pick Assignment", roll_pick_assignment, "pick_qty")
        pick_qty = float(pick_qty or 0)
        if pick_qty:
            prior_lists = frappe.get_all(
                "Roll Wise Pick List",
                filters={"roll_pick_assignment": roll_pick_assignment, "docstatus": 1},
                pluck="name",
            )
            prior_qty = 0.0
            if prior_lists:
                prior_qty = frappe.db.sql("""
                    select coalesce(sum(qty), 0) from `tabRoll Wise Pick Item`
                    where parenttype = 'Roll Wise Pick List' and parent in %(lists)s
                """, {"lists": prior_lists})[0][0] or 0.0

            this_qty = sum(float(r.get("qty") or 0) for r in rolls)
            total_picked = float(prior_qty) + this_qty
            tolerance = pick_qty * 0.03
            if not (pick_qty - tolerance <= total_picked <= pick_qty + tolerance):
                frappe.throw(_(
                    "Picked quantity {0} is outside the allowed \u00b13% tolerance for the "
                    "target {1} (Pick Order {2})"
                ).format(round(total_picked, 3), pick_qty, roll_pick_assignment))

    try:
        # Per-batch warehouse override, from the Roll Pick Assignment's own
        # Batch Items table (batch -> warehouse), when this fulfillment
        # comes from the Pick Order flow. A batch doesn't necessarily sit
        # in the blanket Source Warehouse selected on the execution page —
        # the supervisor's per-batch warehouse (the one get_warehouses_for_batch
        # in textiles_and_garments showed available qty for when the
        # Assignment was built) is the one actually known to hold that
        # batch's stock, so the Stock Entry rows consuming it need to be
        # built against THAT warehouse — otherwise ERPNext's own
        # insufficient-batch-qty check fires against the wrong warehouse
        # ("Batch X only has 0 kg in <blanket source>, but Y kg was
        # entered"). Falls back to source_warehouse for any batch with no
        # warehouse set on its row (that field is optional) or when this
        # isn't a Pick Order fulfillment at all.
        batch_warehouse_overrides = get_batch_warehouse_overrides(roll_pick_assignment)

        def _warehouse_for_batch(batch_no):
            return batch_warehouse_overrides.get(batch_no) or source_warehouse

        # ── STEP 1: Roll Wise Pick List ─────────────────────────────────────
        batch_wise = {}
        for roll in rolls:
            key = (roll.get("batch_no"), roll.get("item_code"))
            b = batch_wise.setdefault(key, {
                "item_code": roll.get("item_code"),
                "warehouse": _warehouse_for_batch(roll.get("batch_no")),
                "batch":     roll.get("batch_no"),
                "qty":       0.0,
                "uom":       roll.get("uom"),
            })
            b["qty"] += float(roll.get("qty") or 0)

        is_batch_transfer = all(
            r.get("roll_no") == r.get("batch_no") for r in rolls
        )
        primary_batch = batch_no or rolls[0].get("batch_no")

        pick_list = frappe.new_doc("Roll Wise Pick List")
        pick_list.posting_date = posting_date
        pick_list.warehouse    = source_warehouse
        pick_list.batch        = primary_batch

        for b in batch_wise.values():
            pick_list.append("batch_wise_pick_item", {
                "item_code": b["item_code"],
                "warehouse": b["warehouse"],
                "batch":     b["batch"],
                "qty":       b["qty"],
                "uom":       b["uom"],
            })

        if not is_batch_transfer:
            for r in rolls:
                pick_list.append("roll_wise_pick_item", {
                    "item_code": r.get("item_code"),
                    "warehouse": _warehouse_for_batch(r.get("batch_no")),
                    "batch":     r.get("batch_no"),
                    "roll_no":   r.get("roll_no"),
                    "qty":       float(r.get("qty") or 0),
                    "uom":       r.get("uom"),
                })

        pick_list.insert(ignore_permissions=True)
        pick_list.submit()

        # ── STEP 2: Stock Entry ──────────────────────────────────────────────
        stock_entry_items = {}
        for r in rolls:
            key = (r.get("item_code"), r.get("batch_no"))
            se_item = stock_entry_items.setdefault(key, {
                "item_code":   r.get("item_code"),
                "s_warehouse": _warehouse_for_batch(r.get("batch_no")),
                "t_warehouse": target_warehouse,
                "batch_no":    r.get("batch_no"),
                "qty":         0.0,
                "uom":         r.get("uom"),
            })
            se_item["qty"] += float(r.get("qty") or 0)

        naming_series = "MT/26/" if pick_type == "To Work Order" else "BM/26/"

        se = frappe.new_doc("Stock Entry")
        se.naming_series         = naming_series
        se.stock_entry_type      = "Material Transfer"
        se.purpose               = "Material Transfer"
        se.company               = frappe.defaults.get_user_default("Company")
        # Explicitly set both posting_date AND posting_time (with
        # set_posting_time flagged on). Leaving posting_time unset here
        # used to crash with "combine() argument 2 must be datetime.time,
        # not None" — the auto-created Serial and Batch Bundle rows (from
        # use_serial_batch_fields=1 below) build a posting datetime via
        # datetime.combine(posting_date, posting_time) before Stock
        # Entry's own validate() gets a chance to default posting_time
        # to nowtime() for us.
        se.set_posting_time      = 1
        se.posting_date          = posting_date
        se.posting_time          = nowtime()
        se.custom_roll_wise_pick_list = pick_list.name

        # Stock Entry already ships with source_warehouse_address /
        # target_warehouse_address (standard fields, Link -> Address) —
        # normally auto-filled by the Desk form's JS when from_warehouse /
        # to_warehouse change. Since this Stock Entry is built server-side,
        # that JS never runs, so we fetch and set both explicitly here.
        # Applies to every pick_type — _get_warehouse_address() just returns
        # None when a warehouse has no linked Address, so this is harmless
        # for warehouses that don't have one set up.
        se.from_warehouse = source_warehouse
        se.to_warehouse   = target_warehouse
        se.source_warehouse_address = _get_warehouse_address(source_warehouse)
        se.target_warehouse_address = _get_warehouse_address(target_warehouse)

        for item in stock_entry_items.values():
            se.append("items", {
                "s_warehouse":  item["s_warehouse"],
                "t_warehouse":  item["t_warehouse"],
                "item_code":    item["item_code"],
                "qty":          item["qty"],
                "transfer_qty": item["qty"],
                "uom":          item["uom"],
                "stock_uom":    item["uom"],
                "conversion_factor": 1,
                "batch_no":     item["batch_no"],
                "use_serial_batch_fields": 1,
                "allow_zero_valuation_rate": 0,
            })

        for b in batch_wise.values():
            rolls_in_batch = [r for r in rolls if r.get("batch_no") == b["batch"]]
            se.append("custom_batch_wise_packing_summary", {
                "batch": b["batch"],
                "qty":   b["qty"],
                "no_of_rolls": 0 if is_batch_transfer else len(rolls_in_batch),
            })

        if pick_type and pick_type != "Manual Roll Pick" and document_name:
            if pick_type in ("From Work Order", "To Work Order"):
                se.work_order = document_name
                if pick_type == "To Work Order":
                    # Pull straight from the Work Order rather than trust
                    # whatever the caller passed through — the Work Order is
                    # the authoritative record of what's actually being
                    # manufactured (Roll Pick Assignment.project is set once
                    # at Assignment-creation time and can drift from it, and
                    # a caller isn't guaranteed to pass project at all).
                    wo_details = frappe.db.get_value(
                        "Work Order", document_name,
                        ["project", "commercial_name", "color", "required_dia"],
                        as_dict=True,
                    )
                    if wo_details:
                        if wo_details.project:
                            project = wo_details.project
                        se.fabric_name = wo_details.commercial_name
                        se.colour = wo_details.color
                        if wo_details.required_dia:
                            se.finishing_dia = str(wo_details.required_dia)
            elif pick_type == "From Purchase Order":
                se.purchase_order = document_name
            elif pick_type in ("To Subcontracting Order", "From Subcontracting Order"):
                se.subcontracting_order = document_name
            elif pick_type == "From Stock Entry":
                se.custom_reference_stock_entry = document_name
            elif pick_type == "From Batch":
                se.custom_reference_batch = document_name

        if project:
            se.project = project
        if from_work_order:
            se.custom_from_work_order = from_work_order
        if from_subcontracting:
            se.custom_from_subcontracting = from_subcontracting

        se.insert(ignore_permissions=True)
        se.submit()

        # Trace this Stock Entry back to the Pick Order it fulfilled (if any)
        # and close the Order out. Reuses the same Stock Entry, same rules,
        # same warehouse-sync hook — this is not a separate code path, just
        # an extra reference stamped on afterward.
        if roll_pick_assignment:
            pick_list.db_set("roll_pick_assignment", roll_pick_assignment, update_modified=False)
            frappe.db.set_value("Roll Pick Assignment", roll_pick_assignment, "status", "Completed")

        frappe.db.commit()

        total_qty = sum(float(r.get("qty") or 0) for r in rolls)

        return {
            "success": True,
            "message": "Roll Wise Pick List and Stock Entry created successfully",
            "pick_list": pick_list.name,
            "stock_entry": se.name,
            "transfer_type": "batch" if is_batch_transfer else "roll",
            "entry_type": "Material Transfer",
            "data": {
                "posting_date": posting_date,
                "pick_type": pick_type,
                "document": document_name,
                "project": project,
                "target_warehouse": target_warehouse,
                "source_warehouse": source_warehouse,
                "batch_no": primary_batch,
                "rolls_count": 0 if is_batch_transfer else len(rolls),
                "total_weight": round(total_qty, 2),
                "batches": len(batch_wise),
                "items": len(stock_entry_items),
            }
        }

    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "create_roll_picking_entry")
        frappe.throw(str(e))


# ── Cancel Pick + Stock Entry together ─────────────────────────────────────────
# Roll Wise Pick List and its Stock Entry link each other (Roll Wise Pick
# List.stock_entry <-> Stock Entry.custom_roll_wise_pick_list), so Frappe's
# standard "cannot cancel, still linked" guard blocks whichever one you try
# to cancel first — each is still a submitted document referencing the
# other. This cancels both together in the correct order (Stock Entry
# first, so the stock ledger reversal and the Roll.warehouse revert in
# roll_wise_pick_list_events.py both fire correctly; the Pick List second,
# closing out the record once the real stock effect is already undone),
# bypassing the mutual-link check for exactly this pair.
@frappe.whitelist()
def force_cancel_roll_pick_stock_entry(roll_wise_pick_list):
    frappe.only_for(["System Manager", "Knitting Supervisor"])

    pick_list = frappe.get_doc("Roll Wise Pick List", roll_wise_pick_list)

    se_name = pick_list.get("stock_entry")
    if se_name and frappe.db.get_value("Stock Entry", se_name, "docstatus") == 1:
        se = frappe.get_doc("Stock Entry", se_name)
        se.flags.ignore_links = True
        se.cancel()
        frappe.db.commit()  # persist the Stock Entry cancel now, so a retry
                             # after a failure below doesn't re-attempt it

    pick_list.reload()
    if pick_list.docstatus == 1:
        pick_list.flags.ignore_links = True
        pick_list.cancel()

    frappe.db.commit()
    return {"success": True}


# ── Item + QI parameters ──────────────────────────────────────────────────────

@frappe.whitelist()
def get_item_with_qi_parameters(item_code):
    """
    Returns item data + QI template parameters.
    Used by CreateQIPage.
    """
    if not frappe.db.exists("Item", item_code):
        frappe.throw(f"Item {item_code} not found")

    item = frappe.get_doc("Item", item_code)
    inspection_parameters = []

    if item.quality_inspection_template:
        try:
            tpl = frappe.get_doc("Quality Inspection Template", item.quality_inspection_template)
            inspection_parameters = [
                {
                    "idx":                    p.idx,
                    "specification":          p.specification,
                    "parameter_group":        p.parameter_group,
                    "value":                  p.value,
                    "numeric":                p.numeric,
                    "min_value":              p.min_value,
                    "max_value":              p.max_value,
                    "formula_based_criteria": p.formula_based_criteria,
                    "acceptance_formula":     p.acceptance_formula,
                    "parent":                 p.parent,
                    "parentfield":            p.parentfield,
                    "parenttype":             p.parenttype,
                    "creation":               str(p.creation),
                    "modified":               str(p.modified),
                }
                for p in tpl.item_quality_inspection_parameter
            ]
        except Exception as e:
            frappe.log_error(str(e), "get_item_with_qi_parameters")

    return {
        "success": True,
        "data": {
            "item": {
                "name":                        item.name,
                "item_code":                   item.item_code,
                "item_name":                   item.item_name,
                "description":                 item.description,
                "item_group":                  item.item_group,
                "commercial_name":             item.get("commercial_name", ""),
                "color":                       item.get("color", ""),
                "width":                       item.get("width", ""),
                "stock_uom":                   item.stock_uom,
                "has_batch_no":                item.has_batch_no,
                "quality_inspection_template": item.quality_inspection_template,
                "modified":                    str(item.modified),
            },
            "inspectionParameters": inspection_parameters,
        }
    }
