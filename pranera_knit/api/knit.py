"""
pranera_knit/api/knit.py
Server-side whitelisted methods called from the Vue PWA.
"""
import frappe
import json
from frappe import _
from frappe.utils import now_datetime, today, get_datetime


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
    """Creates a Stock Entry (Manufacture) in ERPNext."""
    frappe.has_permission("Stock Entry", throw=True)
    se = frappe.new_doc("Stock Entry")
    se.stock_entry_type = "Manufacture"
    se.work_order   = work_order
    se.job_card     = jobcard
    se.company      = frappe.defaults.get_user_default("Company")
    se.posting_date = today()
    bom = frappe.get_value("Work Order", work_order, "bom_no")
    if bom:
        se.from_bom = 1
        se.bom_no   = bom
    se.save()
    return {"name": se.name, "status": "Draft"}


@frappe.whitelist()
def create_roll_picking_entry(pick_type, document_name, source_warehouse,
                               target_warehouse, items=None, scanned_roll=None, date=None):
    """Creates a Stock Entry for roll picking (Material Transfer)."""
    frappe.has_permission("Stock Entry", throw=True)
    se = frappe.new_doc("Stock Entry")
    se.stock_entry_type = "Material Transfer"
    se.company      = frappe.defaults.get_user_default("Company")
    se.posting_date = date or today()
    se.custom_pick_type = pick_type
    se.custom_reference_document = document_name
    if items:
        if isinstance(items, str):
            items = json.loads(items)
        for item in items:
            se.append("items", {
                "item_code":   item.get("item_code"),
                "qty":         item.get("qty") or item.get("required_qty") or 1,
                "s_warehouse": source_warehouse,
                "t_warehouse": target_warehouse,
                "batch_no":    item.get("batch_no")
            })
    se.save()
    return {"name": se.name, "status": "Saved"}


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
