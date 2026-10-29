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
from frappe.utils import now_datetime, today, get_datetime, nowtime, cint, flt

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


def _next_roll_no():
    """Next free numeric Roll name (max numeric name + 1)."""
    row = frappe.db.sql("""
        SELECT MAX(CAST(name AS UNSIGNED)) AS max_no
        FROM `tabRoll`
        WHERE name REGEXP '^[0-9]+$'
    """, as_dict=True)
    n = int((row[0].max_no if row else 0) or 0) + 1
    while frappe.db.exists("Roll", str(n)):
        n += 1
    return str(n)


def _job_card_lineage(job_card):
    """The job card plus every job card it was amended from. Rolls of a
    cancelled job card are moved to its amendment (job_card_events.
    on_after_cancel), so a save coming from the amendment may legitimately
    target a roll still pointing at an older version."""
    seen = []
    jc = job_card
    while jc and jc not in seen and len(seen) < 20:
        seen.append(jc)
        jc = frappe.db.get_value("Job Card", jc, "amended_from")
    return seen


def _parse_dt(val):
    if not val or str(val) in ("null", "None", ""):
        return None
    s = str(val).strip().replace("T", " ")
    s = s.replace("Z", "")
    for ch in ("+", "-"):
        i = s.rfind(ch)
        if i > 10:
            s = s[:i]
    s = s.split(".")[0].strip()
    try:
        return get_datetime(s)
    except Exception:
        return None


def _num(val):
    return val if val not in (None, "", "null", "None") else None


@frappe.whitelist()
def save_roll_data(**kwargs):
    """Saves a completed roll (weight, times, operator…) from the knit PWA.

    Backs the `knit_save_roll_data` endpoint (see override_whitelisted_methods
    in hooks.py) and replaces the old Server Script of the same name.

    FIX (Roll 38689, 14-Oct-2026): the old script looked the roll up by
    name ONLY. When the PWA sent a roll number that belonged to a different
    job card — a stale page session (PO-JOB21859 / WO/26/12068-1 sending
    JC PO-JOB21862's running roll 38689), or an offline-guessed number that
    collided with a real roll — it silently overwrote that roll's
    work_order, weight and machine, and two physical rolls ended up carrying
    the same roll number on their stickers. Now:
      * a roll is only updated when it belongs to the same job card (or one
        the job card was amended from);
      * an offline-queued roll (has `_localId`) whose guessed number is taken
        by another job card gets a fresh number instead;
      * any other mismatch is refused, so the operator sees an error before
        a wrong sticker is printed.
    """
    frappe.has_permission("Roll", throw=True)
    fd = frappe._dict(kwargs)
    job_card = fd.job_card
    if not job_card:
        frappe.throw(_("job_card is required"))

    roll_no = None
    if fd.roll_no not in (None, "", "null", "None"):
        try:
            roll_no = str(int(str(fd.roll_no)))
        except Exception:
            roll_no = None

    existing = None
    if roll_no:
        existing = frappe.db.get_value(
            "Roll", roll_no, ["name", "job_card", "work_order"], as_dict=True
        )

    if existing and existing.job_card and existing.job_card not in _job_card_lineage(job_card):
        if fd.get("_localId"):
            # Offline roll whose locally-guessed number is already used by a
            # different job card's roll — never touch that roll, create ours.
            frappe.logger("pranera_knit").warning(
                f"knit_save_roll_data: offline roll_no {roll_no} for {job_card} "
                f"collides with Roll {roll_no} of {existing.job_card}; "
                f"allocating a new roll number"
            )
            existing = None
        else:
            frappe.throw(_(
                "Roll {0} belongs to Job Card {1} ({2}), not {3} ({4}). "
                "This screen was showing another job card's roll — nothing "
                "was saved. Tap Reset (⟲) on this job card and start the "
                "roll again."
            ).format(roll_no, existing.job_card, existing.work_order or "-",
                     job_card, fd.work_order or "-"),
                title=_("Roll belongs to another Job Card"))

    if existing:
        roll = frappe.get_doc("Roll", existing.name)
    else:
        roll = frappe.new_doc("Roll")
        roll.roll_no = _next_roll_no()
        roll.job_card = job_card
        roll.work_order = fd.work_order

    roll.work_order = fd.work_order or roll.work_order
    roll.item_code = fd.item_code or ""
    roll.item_name = fd.item_name or ""
    roll.commercial_name = fd.commercial_name or ""
    roll.color = fd.color or ""
    roll.width = fd.width or ""
    roll.batch = fd.batch or ""
    roll.shift = fd.shift or ""
    roll.stock_uom = fd.stock_uom or "Kgs"
    roll.project = fd.project or ""
    roll.knitting_machine_no = fd.knitting_machine_no or ""
    roll.name_of_the_operator = fd.knit_operator_name or ""
    roll.knit_operator_name = fd.knit_operator_name or ""

    rw, tq, mq = _num(fd.roll_weight), _num(fd.total_qty), _num(fd.mistake_qty)
    roll.roll_weight = float(rw) if rw else 0.0
    roll.total_qty = int(float(tq)) if tq else 0
    roll.mistake_qty = int(float(mq)) if mq else 0
    roll.correct_qty = roll.total_qty - roll.mistake_qty
    if roll.total_qty > 0:
        roll.avg_weight_per_pcs = roll.roll_weight / roll.total_qty

    # Keep whichever start is EARLIER: knit_create_roll's creation stamp or
    # the frontend's (auto-continued rolls start at the previous End Roll tap).
    st = _parse_dt(fd.start_time)
    existing_st = get_datetime(roll.start_time) if roll.get("start_time") else None
    if st and existing_st:
        roll.start_time = st if st < existing_st else existing_st
    elif st:
        roll.start_time = st

    roll.end_time = _parse_dt(fd.end_time) or now_datetime()
    roll.datetime = today()

    def _hms(secs):
        secs = int(float(secs)) if _num(secs) else 0
        return f"{secs // 3600:02d}:{(secs % 3600) // 60:02d}:{secs % 60:02d}"

    roll.total_breakdown = _hms(fd.breakdown_time_seconds)
    roll.net_production_time = _hms(fd.net_production_time_seconds)
    eff = _num(fd.efficiency_percentage)
    roll.efficiency = f"{eff}%" if eff else "0.0%"

    roll.warehouse = (
        frappe.db.get_value("Work Order", roll.work_order, "fg_warehouse") or ""
    ) if roll.work_order else ""

    # Batch IDs are deterministic ({project}/{work_order}); make sure it exists
    # before the Roll links to it (covers online saves and offline replays).
    if roll.batch and not frappe.db.exists("Batch", roll.batch):
        try:
            b = frappe.new_doc("Batch")
            b.batch_id = roll.batch
            b.item = roll.item_code
            b.insert(ignore_permissions=True)
        except frappe.DuplicateEntryError:
            pass

    if existing:
        roll.save(ignore_permissions=True)
    else:
        roll.insert(ignore_permissions=True)

    frappe.db.commit()
    return {"success": True, "name": roll.name}


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
    """Always {} — for EVERY pick type, the Source Warehouse the worker
    selects on the Pick Order Execution page (roll-wise-pick-order-execution)
    wins for every roll: scans are recorded against it, changing it
    mid-session moves every already-scanned roll to it, and the Stock Entry
    rows are built from it.

    Previously only "From Batch" behaved this way; To Work Order / To Sales
    Order / To Subcontracting Order used the per-batch Warehouse on the
    Assignment's Batch Items rows instead, so the worker's selection on the
    execution page was silently ignored (e.g. RPA-0679). That per-batch
    Warehouse is now only the supervisor's planning hint (where stock was
    sitting when the Assignment was made), not a binding override.

    Kept as a function (callers still fall back to source_warehouse for any
    batch missing from the map) so a per-type override can be reintroduced
    in one place if ever needed."""
    return {}


def get_pick_qty_targets_by_uom(assignment_doc):
    """Per-UOM breakdown of a Roll Pick Assignment's pick target — {uom:
    target_qty} — derived directly from the Assignment's own Batch Items
    (grouped by stock_uom), NOT from the doctype's own "Pick Qty (by UOM)"
    field. That field's computation logic isn't in any file this app
    ships — it's populated by something outside this codebase, almost
    certainly a Server Script that exists only on production, the exact
    known-risky pattern this app has hit before (see the module docstring
    on why Server Scripts are avoided here). Computing it fresh here also
    fixes the actual bug that prompted this: pick_qty itself is a single
    blended number that naively sums qty across every batch_items row
    regardless of stock_uom — for a mixed Kgs+Pcs Assignment that means
    adding a piece count directly to a weight and calling the sum "kg",
    which is meaningless. Each UOM's target must be checked against its
    own scanned total independently instead.

    Falls back to a single "Kgs" bucket built from pick_qty when there are
    no Batch Items at all (e.g. "From Work Order" / "Manual Roll Pick"
    flows, which are always plain single-UOM weight picks with no batch
    breakdown to derive from)."""
    targets = {}
    for row in (assignment_doc.batch_items or []):
        uom = row.stock_uom or "Kgs"
        targets[uom] = targets.get(uom, 0.0) + flt(row.qty)
    if not targets and assignment_doc.pick_qty:
        targets["Kgs"] = flt(assignment_doc.pick_qty)
    return targets


def _batch_qty_in_warehouse(batch_no, warehouse, item_code=None):
    """Current stock of one batch in one warehouse (ERPNext's own
    batch-qty logic, so Serial and Batch Bundle entries are counted)."""
    from erpnext.stock.doctype.batch.batch import get_batch_qty
    try:
        qty = get_batch_qty(batch_no=batch_no, warehouse=warehouse, item_code=item_code)
    except TypeError:  # older signature without item_code
        qty = get_batch_qty(batch_no=batch_no, warehouse=warehouse)
    if isinstance(qty, list):
        qty = sum(flt(r.get("qty")) for r in qty if r.get("warehouse") == warehouse)
    return flt(qty)


def _split_batch_across_warehouses(item_code, batch_no, qty, preferred_warehouse, plan_warehouses):
    """Splits `qty` of one batch into [(warehouse, qty), ...] so no row
    takes more than that warehouse actually holds.

    Order of preference: the Source Warehouse the worker selected first,
    then the Assignment's Batch Items warehouses for this batch, in plan
    order. Only those warehouses are considered — material is never pulled
    silently from some unrelated warehouse that happens to hold the batch.

    When everything fits in the selected warehouse (the normal case), this
    returns a single row, i.e. exactly the old behaviour."""
    qty = flt(qty, 3)
    if not batch_no or qty <= 0:
        return [(preferred_warehouse, qty)]

    candidates = [preferred_warehouse] + [w for w in plan_warehouses if w and w != preferred_warehouse]
    if len(candidates) == 1:
        return [(preferred_warehouse, qty)]

    splits, remaining, available = [], qty, {}
    for wh in candidates:
        if remaining <= 0.0005:
            break
        available[wh] = _batch_qty_in_warehouse(batch_no, wh, item_code)
        take = flt(min(remaining, available[wh]), 3)
        if take > 0:
            splits.append((wh, take))
            remaining = flt(remaining - take, 3)

    if remaining > 0.0005:
        frappe.throw(_(
            "Batch {0} only has {1} in the planned warehouses ({2}), but {3} was picked."
        ).format(
            batch_no,
            flt(sum(available.values()), 3),
            ", ".join(f"{wh}: {flt(q, 3)}" for wh, q in available.items()),
            qty,
        ))
    return splits


@frappe.whitelist()
def create_roll_picking_entry(pick_type=None, document_name=None, document=None,
                               source_warehouse=None, target_warehouse=None,
                               posting_date=None, date=None, project=None,
                               batch_no=None, from_work_order=None,
                               from_subcontracting=None, rolls=None, items=None,
                               required_items=None, scanned_roll=None,
                               roll_pick_assignment=None, submit_stock_entry=1):
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
          Transfer for Manufacture), "RFB/26/" for "To Sales Order" (ready
          for billing), otherwise "BM/26/".
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
    marks the Order's status "Completed" — or "In Progress" if
    submit_stock_entry is falsy, since the material hasn't actually moved
    yet. Ordinary manual picks (no Pick Order behind them) omit this and
    nothing changes.

    submit_stock_entry: the Roll Wise Pick List is ALWAYS submitted
    regardless — it's just the record of what was picked. This only
    controls the Stock Entry's docstatus: truthy (default) submits it
    immediately as before; falsy inserts it as a draft for someone to
    review and submit manually later.
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

    # When fulfilling a Pick Order, the per-UOM target (from Batch Items,
    # see get_pick_qty_targets_by_uom) is the authoritative check —
    # validated here rather than only client-side, since this is the one
    # place a Pick Order's fulfillment actually becomes a real Stock
    # Entry. Each UOM is checked independently (a Kgs target and a Pcs
    # target are unrelated quantities — see get_pick_qty_targets_by_uom's
    # docstring for why they can't be blended into one number). Accounts
    # for whatever was already submitted against this Order in a prior
    # session too, so partial-then-resume fulfillment is checked against
    # the true cumulative total per UOM, not just this call's rolls.
    if roll_pick_assignment:
        assignment_doc = frappe.get_doc("Roll Pick Assignment", roll_pick_assignment)
        targets_by_uom = get_pick_qty_targets_by_uom(assignment_doc)

        if targets_by_uom:
            prior_lists = frappe.get_all(
                "Roll Wise Pick List",
                filters={"roll_pick_assignment": roll_pick_assignment, "docstatus": 1},
                pluck="name",
            )
            prior_by_uom = {}
            if prior_lists:
                prior_rows = frappe.get_all(
                    "Roll Wise Pick Item",
                    filters={"parenttype": "Roll Wise Pick List", "parent": ["in", prior_lists]},
                    fields=["qty", "uom"],
                )
                for r in prior_rows:
                    u = r.uom or "Kgs"
                    prior_by_uom[u] = prior_by_uom.get(u, 0.0) + flt(r.qty)

            this_by_uom = {}
            for r in rolls:
                u = r.get("uom") or "Kgs"
                this_by_uom[u] = this_by_uom.get(u, 0.0) + flt(r.get("qty"))

            for uom, target in targets_by_uom.items():
                if not target:
                    continue
                total_picked = prior_by_uom.get(uom, 0.0) + this_by_uom.get(uom, 0.0)
                tolerance = target * 0.03
                if not (target - tolerance <= total_picked <= target + tolerance):
                    frappe.throw(_(
                        "Picked quantity {0} {1} is outside the allowed \u00b13% tolerance for "
                        "the {1} target {2} (Pick Order {3})"
                    ).format(round(total_picked, 3), uom, target, roll_pick_assignment))

    try:
        # Stock Entry rows use the Source Warehouse selected on the execution
        # page for every pick type (get_batch_warehouse_overrides returns {}).
        batch_warehouse_overrides = get_batch_warehouse_overrides(roll_pick_assignment)

        def _warehouse_for_batch(batch_no):
            return batch_warehouse_overrides.get(batch_no) or source_warehouse

        # Batch Items warehouses, in plan order — where the supervisor saw
        # each batch's stock when the Assignment was made. Used only to know
        # where to spill over to when the selected warehouse doesn't hold
        # enough of a batch (see _split_batch_across_warehouses).
        plan_warehouses = {}
        if roll_pick_assignment:
            for bi in frappe.get_all(
                "Roll Pick Batch Item",
                filters={"parenttype": "Roll Pick Assignment", "parent": roll_pick_assignment},
                fields=["batch", "warehouse"], order_by="idx asc",
            ):
                if bi.batch and bi.warehouse:
                    plan_warehouses.setdefault(bi.batch, [])
                    if bi.warehouse not in plan_warehouses[bi.batch]:
                        plan_warehouses[bi.batch].append(bi.warehouse)

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

        # One batch can sit in more than one warehouse (e.g. RPA-1033: the
        # same batch planned as 504.66 kg in D01 + 1205.90 kg in FF/A01).
        # Moving the whole picked qty out of the single selected warehouse
        # then fails stock validation, so split each (batch, item) across
        # the warehouses that actually hold it: [(warehouse, qty), ...].
        batch_splits = {
            key: _split_batch_across_warehouses(
                b["item_code"], b["batch"], b["qty"],
                _warehouse_for_batch(b["batch"]),
                plan_warehouses.get(b["batch"]) or [],
            )
            for key, b in batch_wise.items()
        }

        # The split is applied to the Stock Entry ONLY. The Roll Wise Pick
        # List keeps every row on the selected warehouse, as before: a
        # Server Script on it ("Recompute Batch Wise Pick Item from Rolls")
        # requires batch-wise totals to equal roll-wise totals per
        # warehouse, and whole rolls can't be split to match exact kg
        # amounts per warehouse.

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
                row = {
                    "item_code": r.get("item_code"),
                    "warehouse": _warehouse_for_batch(r.get("batch_no")),
                    "batch":     r.get("batch_no"),
                    "roll_no":   r.get("roll_no"),
                    "qty":       float(r.get("qty") or 0),
                    "uom":       r.get("uom"),
                }
                if r.get("qi_report"):
                    # Old roll from a QI Report Details row — no Roll doc
                    # behind it (or an unrelated Roll with the same number),
                    # so its weight is set here, never fetched from Roll.
                    row["qi_report"] = r.get("qi_report")
                    row["roll_weight"] = float(r.get("roll_weight") or 0)
                    row["custom_roll_weight"] = str(row["roll_weight"])
                pick_list.append("roll_wise_pick_item", row)

        # roll_no is a Link to Roll; a QI roll's number either doesn't exist
        # as a Roll or points at an unrelated one. Skip link validation (and
        # with it the roll_no.roll_weight fetch) for picks that include any.
        if any(r.get("qi_report") for r in rolls):
            pick_list.flags.ignore_links = True

        pick_list.insert(ignore_permissions=True)
        pick_list.submit()

        # ── STEP 2: Stock Entry ──────────────────────────────────────────────
        # One row per (item, batch, source warehouse) — see batch_splits.
        stock_entry_items = {}
        for key, b in batch_wise.items():
            for wh, q in batch_splits[key]:
                stock_entry_items[(b["item_code"], b["batch"], wh)] = {
                    "item_code":   b["item_code"],
                    "s_warehouse": wh,
                    "t_warehouse": target_warehouse,
                    "batch_no":    b["batch"],
                    "qty":         q,
                    "uom":         b["uom"],
                }

        if pick_type == "To Work Order":
            naming_series = "MT/26/"
        elif pick_type == "To Sales Order":
            naming_series = "RFB/26/"
        else:
            naming_series = "BM/26/"

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
        if cint(submit_stock_entry):
            se.submit()

        # Trace this Stock Entry back to the Pick Order it fulfilled (if any)
        # and close the Order out. Reuses the same Stock Entry, same rules,
        # same warehouse-sync hook — this is not a separate code path, just
        # an extra reference stamped on afterward.
        #
        # Status only goes to "Completed" once the Stock Entry itself is
        # submitted — a draft Stock Entry means the material hasn't
        # actually moved yet, so the Assignment is still "In Progress"
        # (someone still needs to review and submit that Stock Entry
        # before this pick is truly done).
        if roll_pick_assignment:
            pick_list.db_set("roll_pick_assignment", roll_pick_assignment, update_modified=False)
            frappe.db.set_value(
                "Roll Pick Assignment", roll_pick_assignment, "status",
                "Completed" if cint(submit_stock_entry) else "In Progress",
            )
            # The pick list -> assignment link only exists from this point,
            # so the Outward Request (if any) can't be resolved from the
            # on_submit hooks above — refresh it here instead.
            from pranera_knit.outward_request_events import refresh_for_assignment
            refresh_for_assignment(roll_pick_assignment)

        frappe.db.commit()

        total_qty = sum(float(r.get("qty") or 0) for r in rolls)

        return {
            "success": True,
            "message": (
                "Roll Wise Pick List and Stock Entry created successfully"
                if cint(submit_stock_entry)
                else "Roll Wise Pick List created; Stock Entry saved as draft"
            ),
            "pick_list": pick_list.name,
            "stock_entry": se.name,
            "stock_entry_submitted": bool(cint(submit_stock_entry)),
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


@frappe.whitelist()
def get_packed_rolls(roll_nos):
    """{roll_no: Roll Packing List name} for every roll in `roll_nos` that is
    already on a SUBMITTED Roll Packing List (drafts and cancelled ones don't
    count). The Rolls page refuses to create a new Roll Packing List if any
    selected roll is in this map. Roll Packing List Item is a child
    table (not readable via /api/resource for most users), so this goes
    through the parent's read permission instead."""
    if isinstance(roll_nos, str):
        roll_nos = frappe.parse_json(roll_nos)
    roll_nos = [r for r in (roll_nos or []) if r]
    if not roll_nos:
        return {}
    frappe.has_permission("Roll Packing List", "read", throw=True)
    rows = frappe.db.sql(
        """
        SELECT i.roll_no, i.parent
        FROM `tabRoll Packing List Item` i
        INNER JOIN `tabRoll Packing List` p ON p.name = i.parent
        WHERE i.parenttype = 'Roll Packing List'
          AND p.docstatus = 1
          AND i.roll_no IN %(roll_nos)s
        """,
        {"roll_nos": tuple(roll_nos)},
        as_dict=True,
    )
    return {r.roll_no: r.parent for r in rows}
