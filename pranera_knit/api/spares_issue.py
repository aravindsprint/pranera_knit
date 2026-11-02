"""
pranera_knit/api/spares_issue.py
Whitelisted methods behind the knit-app "Needle / Sinker Issue" page.

Issuing needles or sinkers to a knitting machine is booked in ERPNext as an
Asset Repair against the machine's Asset, with "Stock Consumed During
Repair" ticked. Submitting that Asset Repair makes ERPNext create and
submit a Material Issue (Stock Entry.asset_repair = the repair) from the
spare store, so the store stock drops and every needle change stays on
the machine's repair history.

Accounting (ERPNext v15 asset_repair.py): with Capitalize Repair Cost OFF
the Asset itself is NOT saved — no change to its value or depreciation
schedule and no GL entry from the repair. Only the Material Issue posts.
We always leave Capitalize Repair Cost off: needles and sinkers are
running consumables, not improvements to the machine.

Machine -> Asset: each knitting Workstation (SJ.., IL.., FK..) carries the
Asset it stands for in the custom field Workstation.custom_asset. The page
lets a user link an asset the first time a machine is used; changing an
existing link needs MANAGER_ROLES.

Permissions: the Asset Repair is inserted / submitted with
ignore_permissions (access is controlled by the "spares-issue" Knit App
Page), but ERPNext inserts the Material Issue inside the repair's
before_submit as the logged-in user, so that user needs Stock Entry
create + submit (e.g. Stock User). We check that first and fail with a
readable message instead of a half-way PermissionError.

Batch-tracked needles: no Serial and Batch Bundle is set on the consumed
rows; Stock Settings "auto create serial and batch bundle for outward"
(FIFO) picks the batches when the Material Issue is submitted.

Restriction + life (pranera_knit/spares_life.py): a machine can only be
issued the needles / sinkers in its Workstation "Spare Items" table. Two
issue types:
  * Broken / Bent Replacement — a few pieces; the life count carries on.
  * Full Set Change — only items with Track Life (SJ / IL machines); resets
    that item's life count (Last Full Set Change = now, alerts re-armed).
"""
import json
import re

import frappe
from frappe import _
from frappe.utils import cint, flt, get_datetime, now_datetime

from pranera_knit import spares_life
from pranera_knit.page_access import denied_pages

PAGE_KEY = "spares-issue"
SOURCE_WAREHOUSE = "NAP_E1/FF/SPARE STORE  - PSS"
COMPANY = "Pranera Services and Solutions Pvt. Ltd.,"
COST_CENTER = "Knitting Unit - PSS"
SPARE_ITEM_PREFIXES = ("SPARES/KNIT MAC NEEDLE/", "SPARES/KNIT MAC SINKER/")
SPARE_ITEM_PATTERNS = tuple(p + "%" for p in SPARE_ITEM_PREFIXES)
MACHINE_RE = re.compile(r"^(SJ|IL|FK)\d", re.IGNORECASE)
MACHINE_ASSET_CATEGORIES = (
    "PLANT & MACHINERY/CIRCULAR KNITTING MACHINE",
    "PLANT & MACHINERY/FLAT BED KNITTING MACHINE",
)
MANAGER_ROLES = {"System Manager", "Manufacturing Manager", "Stock Manager"}
ISSUE_BROKEN = "Broken / Bent Replacement"
ISSUE_FULL_SET = "Full Set Change"
ISSUE_TYPES = [ISSUE_BROKEN, ISSUE_FULL_SET]
REASONS = [
    "Needle breakage",
    "Sinker breakage",
    "Needle and sinker breakage",
    "Track / design change",
    "Preventive replacement",
    "Other",
]


# ── helpers ───────────────────────────────────────────────────────────────

def _check_page_access():
    if PAGE_KEY in denied_pages():
        frappe.throw(_("You do not have access to the Needle / Sinker Issue page."),
                     frappe.PermissionError)


def _is_manager():
    return bool(MANAGER_ROLES & set(frappe.get_roles()))


def _spare_condition(alias=""):
    col = f"{alias}item_code" if alias else "item_code"
    return "(" + " OR ".join(f"{col} LIKE %s" for _p in SPARE_ITEM_PATTERNS) + ")"


def _kind(item_code):
    return "Sinker" if "/SINKER/" in item_code else "Needle"


def _has_custom_field(dt, fieldname):
    return bool(frappe.get_meta(dt).has_field(fieldname))


def _machine_rows():
    fields = ["name", "warehouse", "workstation_type", "status"]
    has_asset = _has_custom_field("Workstation", "custom_asset")
    if has_asset:
        fields.append("custom_asset")
    rows = [w for w in frappe.get_all("Workstation", fields=fields, order_by="name asc", limit_page_length=0)
            if MACHINE_RE.match(w.name or "")]
    asset_names = {}
    asset_ids = [w.custom_asset for w in rows if has_asset and w.get("custom_asset")]
    if asset_ids:
        asset_names = dict(frappe.get_all("Asset", filters={"name": ["in", asset_ids]},
                                          fields=["name", "asset_name"], as_list=True))
    out = []
    for w in rows:
        asset = w.get("custom_asset") if has_asset else None
        out.append({
            "workstation": w.name,
            "warehouse": w.warehouse,
            "workstation_type": w.workstation_type,
            "status": w.status,
            "asset": asset,
            "asset_name": asset_names.get(asset) if asset else None,
        })
    return out


def _stock_rows(warehouse):
    return frappe.db.sql(
        f"""
        SELECT b.item_code, i.item_name, i.stock_uom, i.has_batch_no,
               b.actual_qty AS qty, b.valuation_rate
        FROM `tabBin` b
        JOIN `tabItem` i ON i.name = b.item_code
        WHERE b.warehouse = %s
          AND b.actual_qty > 0
          AND i.disabled = 0
          AND {_spare_condition('b.')}
        ORDER BY b.item_code
        """,
        (warehouse, *SPARE_ITEM_PATTERNS),
        as_dict=True,
    )


# ── page data ─────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_setup():
    """Machines (with their linked asset), reasons and the source warehouse."""
    _check_page_access()
    return {
        "source_warehouse": SOURCE_WAREHOUSE,
        "machines": _machine_rows(),
        "reasons": REASONS,
        "issue_types": ISSUE_TYPES,
        "warn_pct": spares_life.warn_pct(),
        "can_change_asset": _is_manager(),
        "can_issue": bool(frappe.has_permission("Stock Entry", "create")
                          and frappe.has_permission("Stock Entry", "submit")),
    }


@frappe.whitelist()
def get_machine(workstation, warehouse=None):
    """The needles / sinkers this machine may be issued (its Spare Items table),
    with spare-store stock and life status for the tracked ones."""
    _check_page_access()
    if not MACHINE_RE.match(workstation or "") or not frappe.db.exists("Workstation", workstation):
        frappe.throw(_("Workstation {0} not found").format(workstation))
    warehouse = warehouse or SOURCE_WAREHOUSE
    rows = spares_life.spare_rows(workstation)
    life = {st["item_code"]: st for st in spares_life.life_status(workstation, rows)}
    codes = [r.item_code for r in rows]
    items = {}
    if codes:
        for i in frappe.get_all("Item", filters={"name": ["in", codes]},
                                fields=["name", "item_name", "stock_uom", "has_batch_no", "disabled"]):
            items[i.name] = i
    bins = {}
    if codes:
        for b in frappe.get_all("Bin", filters={"warehouse": warehouse, "item_code": ["in", codes]},
                                fields=["item_code", "actual_qty", "valuation_rate"]):
            bins[b.item_code] = b
    out = []
    for r in rows:
        it = items.get(r.item_code) or frappe._dict()
        b = bins.get(r.item_code) or frappe._dict()
        lf = life.get(r.item_code) or {}
        out.append({
            "item_code": r.item_code,
            "item_name": it.item_name,
            "stock_uom": it.stock_uom or "Pcs",
            "has_batch_no": cint(it.has_batch_no),
            "disabled": cint(it.disabled),
            "kind": _kind(r.item_code),
            "qty": max(flt(b.actual_qty), 0),
            "valuation_rate": flt(b.valuation_rate, 4),
            "set_qty": cint(r.set_qty),
            "track_life": cint(r.track_life),
            "max_production": flt(lf.get("max_production") or r.max_production),
            "last_full_set_on": r.last_full_set_on,
            "produced": lf.get("produced"),
            "pct": lf.get("pct"),
            "level": lf.get("level") or "",
        })
    return {
        "workstation": workstation,
        "warehouse": warehouse,
        "mapped": bool(rows),
        "can_full_set": any(cint(r.track_life) for r in rows),
        "items": out,
    }


@frappe.whitelist()
def get_spare_stock(warehouse=None):
    """Needles and sinkers in stock in the source warehouse."""
    _check_page_access()
    warehouse = warehouse or SOURCE_WAREHOUSE
    rows = _stock_rows(warehouse)
    for r in rows:
        r["kind"] = _kind(r.item_code)
        r["qty"] = flt(r.qty)
        r["valuation_rate"] = flt(r.valuation_rate, 4)
    return {"warehouse": warehouse, "items": rows}


@frappe.whitelist()
def search_assets(txt=None):
    """Knitting machine assets, with the workstation each is already linked to."""
    _check_page_access()
    filters = {"docstatus": 1, "asset_category": ["in", MACHINE_ASSET_CATEGORIES],
               "status": ["not in", ["Sold", "Scrapped"]]}
    or_filters = None
    if txt:
        or_filters = {"name": ["like", f"%{txt}%"], "asset_name": ["like", f"%{txt}%"]}
    assets = frappe.get_all(
        "Asset", filters=filters, or_filters=or_filters,
        fields=["name", "asset_name", "location", "asset_category"],
        order_by="name asc", limit_page_length=200,
    )
    linked = {}
    if _has_custom_field("Workstation", "custom_asset"):
        for w in frappe.get_all("Workstation", filters={"custom_asset": ["is", "set"]},
                                fields=["name", "custom_asset"]):
            linked[w.custom_asset] = w.name
    for a in assets:
        a["linked_workstation"] = linked.get(a.name)
    return assets


@frappe.whitelist()
def link_asset(workstation, asset):
    """Set Workstation.custom_asset. First link: anyone with page access;
    changing an existing link: MANAGER_ROLES only."""
    _check_page_access()
    if not _has_custom_field("Workstation", "custom_asset"):
        frappe.throw(_("Custom field Workstation.custom_asset is missing — run bench migrate."))
    if not MACHINE_RE.match(workstation or "") or not frappe.db.exists("Workstation", workstation):
        frappe.throw(_("Workstation {0} not found").format(workstation))
    if not frappe.db.exists("Asset", {"name": asset, "docstatus": 1}):
        frappe.throw(_("Asset {0} not found or not submitted").format(asset))

    current = frappe.db.get_value("Workstation", workstation, "custom_asset")
    if current and current != asset and not _is_manager():
        frappe.throw(_("{0} is already linked to asset {1}. Ask a manager to change it.")
                     .format(workstation, current))
    other = frappe.db.get_value("Workstation", {"custom_asset": asset, "name": ["!=", workstation]}, "name")
    if other:
        frappe.throw(_("Asset {0} is already linked to {1}.").format(asset, other))

    frappe.db.set_value("Workstation", workstation, "custom_asset", asset)
    return {"workstation": workstation, "asset": asset,
            "asset_name": frappe.db.get_value("Asset", asset, "asset_name")}


@frappe.whitelist()
def get_recent_issues(workstation=None, limit=15):
    """Recent Asset Repairs with stock consumption, newest first."""
    _check_page_access()
    has_ws = _has_custom_field("Asset Repair", "custom_workstation")
    filters = {"stock_consumption": 1, "docstatus": 1}
    if workstation:
        if has_ws:
            filters["custom_workstation"] = workstation
        else:
            asset = frappe.db.get_value("Workstation", workstation, "custom_asset") \
                if _has_custom_field("Workstation", "custom_asset") else None
            if not asset:
                return {"issues": [], "frequent_items": []}
            filters["asset"] = asset
    fields = ["name", "asset", "asset_name", "completion_date", "description",
              "total_repair_cost", "owner"]
    if _has_custom_field("Asset Repair", "custom_issue_type"):
        fields.append("custom_issue_type")
    if has_ws:
        fields.append("custom_workstation")
    repairs = frappe.get_all("Asset Repair", filters=filters, fields=fields,
                             order_by="completion_date desc, creation desc",
                             limit_page_length=cint(limit) or 15)
    names = [r.name for r in repairs]
    items_by_repair, stock_entries = {}, {}
    if names:
        for it in frappe.get_all("Asset Repair Consumed Item",
                                 filters={"parent": ["in", names], "parenttype": "Asset Repair"},
                                 fields=["parent", "item_code", "consumed_quantity"],
                                 order_by="idx asc"):
            items_by_repair.setdefault(it.parent, []).append(
                {"item_code": it.item_code, "qty": flt(it.consumed_quantity)})
        for se in frappe.get_all("Stock Entry", filters={"asset_repair": ["in", names], "docstatus": 1},
                                 fields=["name", "asset_repair"]):
            stock_entries[se.asset_repair] = se.name
    user_names = {}
    for r in repairs:
        if r.owner not in user_names:
            user_names[r.owner] = frappe.db.get_value("User", r.owner, "full_name") or r.owner
        r["items"] = items_by_repair.get(r.name, [])
        r["stock_entry"] = stock_entries.get(r.name)
        r["issued_by"] = user_names[r.owner]
        r["workstation"] = r.get("custom_workstation")
        r["issue_type"] = r.get("custom_issue_type") or ISSUE_BROKEN

    frequent = []
    if workstation:
        counts = {}
        for r in repairs:
            for it in r["items"]:
                counts[it["item_code"]] = counts.get(it["item_code"], 0) + 1
        frequent = [k for k, _v in sorted(counts.items(), key=lambda kv: -kv[1])][:8]
    return {"issues": repairs, "frequent_items": frequent}


# ── issue ─────────────────────────────────────────────────────────────────

@frappe.whitelist()
def issue_spares(workstation, items, asset=None, reason=None, remarks=None, failure_date=None,
                 warehouse=None, issue_type=None):
    """Create + submit an Asset Repair (stock consumption) for the machine.

    items: JSON list of {item_code, qty}
    Returns {asset_repair, stock_entry, total_value}.
    """
    _check_page_access()
    if not (frappe.has_permission("Stock Entry", "create") and frappe.has_permission("Stock Entry", "submit")):
        frappe.throw(_("You need permission to create and submit Stock Entries (e.g. the Stock User role) "
                       "to issue needles / sinkers. Please ask the ERP admin."), frappe.PermissionError)

    warehouse = warehouse or SOURCE_WAREHOUSE
    if not MACHINE_RE.match(workstation or "") or not frappe.db.exists("Workstation", workstation):
        frappe.throw(_("Select a knitting machine"))

    linked = frappe.db.get_value("Workstation", workstation, "custom_asset") \
        if _has_custom_field("Workstation", "custom_asset") else None
    asset = linked or asset
    if not asset:
        frappe.throw(_("{0} is not linked to an Asset yet. Link the machine's asset first.").format(workstation))
    if linked and asset != linked:
        frappe.throw(_("{0} is linked to asset {1}").format(workstation, linked))
    asset_doc = frappe.db.get_value("Asset", asset, ["name", "docstatus", "status", "cost_center", "company"],
                                    as_dict=True)
    if not asset_doc or asset_doc.docstatus != 1:
        frappe.throw(_("Asset {0} not found or not submitted").format(asset))
    if asset_doc.status in ("Sold", "Scrapped"):
        frappe.throw(_("Asset {0} is {1}").format(asset, asset_doc.status))

    if isinstance(items, str):
        items = json.loads(items)
    merged = {}
    for row in items or []:
        code = (row.get("item_code") or "").strip()
        qty = flt(row.get("qty"))
        if not code or qty <= 0:
            continue
        if not code.startswith(SPARE_ITEM_PREFIXES):
            frappe.throw(_("{0} is not a knitting needle / sinker item").format(code))
        merged[code] = merged.get(code, 0) + qty
    if not merged:
        frappe.throw(_("Add at least one needle / sinker with a quantity"))

    issue_type = issue_type or ISSUE_BROKEN
    if issue_type not in ISSUE_TYPES:
        frappe.throw(_("Unknown issue type {0}").format(issue_type))
    allowed = {r.item_code: r for r in spares_life.spare_rows(workstation)}
    if not allowed:
        frappe.throw(_("No needles / sinkers are set up for {0}. Ask the knitting team to fill "
                       "Workstation → Spare Items first.").format(workstation))
    for code in merged:
        if code not in allowed:
            frappe.throw(_("{0} is not allowed on {1}. Only the needles / sinkers in its Spare Items "
                           "table can be issued.").format(code, workstation))
        if issue_type == ISSUE_FULL_SET and not cint(allowed[code].track_life):
            frappe.throw(_("{0} on {1} is not a full-set item (Track Life is off) — use {2}.")
                         .format(code, workstation, ISSUE_BROKEN))

    stock = {r.item_code: r for r in _stock_rows(warehouse)}
    for code, qty in merged.items():
        if qty != int(qty):
            frappe.throw(_("{0}: quantity must be a whole number of pieces").format(code))
        available = flt(stock[code].qty) if code in stock else 0
        if qty > available:
            frappe.throw(_("{0}: only {1} in {2}, cannot issue {3}")
                         .format(code, frappe.format(available), warehouse, frappe.format(qty)))

    when = get_datetime(failure_date) if failure_date else now_datetime()
    now = now_datetime()
    if when > now:
        when = now
    reason = reason if reason in REASONS else (reason or "Needle / sinker replacement")
    if issue_type == ISSUE_FULL_SET:
        reason = ISSUE_FULL_SET
    lines = [f"{issue_type}: {reason} on {workstation}" if issue_type != ISSUE_FULL_SET
             else f"{ISSUE_FULL_SET} on {workstation}"]
    if remarks:
        lines.append(remarks.strip())
    lines.append("Issued from Knit App by " + (frappe.db.get_value("User", frappe.session.user, "full_name")
                                               or frappe.session.user))

    repair = frappe.get_doc({
        "doctype": "Asset Repair",
        "asset": asset,
        "company": asset_doc.company or COMPANY,
        "failure_date": when,
        "repair_status": "Completed",
        "completion_date": now,
        "cost_center": COST_CENTER if frappe.db.exists("Cost Center", COST_CENTER) else asset_doc.cost_center,
        "stock_consumption": 1,
        "capitalize_repair_cost": 0,
        "description": "\n".join(lines),
        "actions_performed": "Replaced: " + ", ".join(f"{c} × {int(q)}" for c, q in merged.items()),
        "stock_items": [
            {"item_code": code, "warehouse": warehouse, "consumed_quantity": qty,
             "valuation_rate": flt(stock[code].valuation_rate)}
            for code, qty in merged.items()
        ],
    })
    if _has_custom_field("Asset Repair", "custom_workstation"):
        repair.custom_workstation = workstation
    if _has_custom_field("Asset Repair", "custom_issue_type"):
        repair.custom_issue_type = issue_type

    # Lets the Stock Entry before_insert hook give the Material Issue the
    # MI/<yy>/ series (see spares_issue_events.py).
    frappe.flags.knit_spares_issue = True
    try:
        repair.flags.ignore_permissions = True
        repair.insert()
        repair.submit()
    finally:
        frappe.flags.knit_spares_issue = False

    if issue_type == ISSUE_FULL_SET:
        spares_life.mark_full_set(workstation, list(merged), repair.completion_date, repair.name)

    stock_entry = frappe.db.get_value("Stock Entry", {"asset_repair": repair.name, "docstatus": 1}, "name")
    return {
        "issue_type": issue_type,
        "asset_repair": repair.name,
        "stock_entry": stock_entry,
        "total_value": flt(repair.total_repair_cost, 2),
        "asset": asset,
        "workstation": workstation,
    }
