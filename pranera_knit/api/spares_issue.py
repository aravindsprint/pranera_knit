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

RECEIVER ACKNOWLEDGEMENT
------------------------
An issue is not posted until the person receiving the needles / sinkers
confirms it on their own login:

  1. issue_spares   The storekeeper picks a Receiver (an ERP user). The Asset
                    Repair is saved as a DRAFT with custom_ack_status
                    "Pending" -- no stock moves yet. The receiver gets a push.
  2. acknowledge_issue
                    Only that receiver can acknowledge. Stock is re-checked,
                    the repair is marked Completed and submitted, and ERPNext
                    posts the Material Issue (MI/<yy>/) at that moment.
     reject_issue   The receiver rejects with a reason; nothing is posted.
     withdraw_issue The storekeeper withdraws a still-pending issue.

The submit on acknowledgement runs as the storekeeper who raised the issue
(frappe.set_user, restored in `finally`): ERPNext inserts the Material
Issue as the session user, receivers are operators who normally don't have
Stock Entry create + submit, and it is the store that issues the stock.
The receiver and the time of acknowledgement are recorded on the repair
(custom_receiver, custom_acknowledged_on).
"""
import json
import re

import frappe
from frappe import _
from frappe.utils import cint, flt, get_datetime, now_datetime

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
ACK_PENDING, ACK_DONE, ACK_REJECTED, ACK_WITHDRAWN = "Pending", "Acknowledged", "Rejected", "Withdrawn"
ACK_FIELDS = ("custom_receiver", "custom_ack_status", "custom_acknowledged_on", "custom_ack_remarks")
SKIP_RECEIVERS = {"Administrator", "Guest"}
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


def _ack_ready():
    meta = frappe.get_meta("Asset Repair")
    if not all(meta.has_field(f) for f in ACK_FIELDS):
        frappe.throw(_("Acknowledgement fields on Asset Repair are missing — run bench migrate."))


def _full_name(user):
    return frappe.db.get_value("User", user, "full_name") or user


def _page_roles():
    """Roles required for the spares-issue page (empty set = open to all)."""
    if not frappe.db.exists("DocType", "Knit App Page"):
        return set()
    return set(frappe.get_all("Knit App Page Role",
                              filters={"parenttype": "Knit App Page", "parent": PAGE_KEY},
                              pluck="role"))


def _receiver_candidates(txt=None, limit=20):
    """Enabled system users who can open this page (so they can acknowledge)."""
    filters = {"enabled": 1, "user_type": "System User", "name": ["not in", list(SKIP_RECEIVERS)]}
    or_filters = None
    if txt:
        or_filters = {"name": ["like", f"%{txt}%"], "full_name": ["like", f"%{txt}%"]}
    need = _page_roles()
    if need:
        allowed = set(frappe.get_all("Has Role",
                                     filters={"parenttype": "User", "role": ["in", list(need | {"System Manager"})]},
                                     pluck="parent", distinct=True))
        if not allowed:
            return []
        filters["name"] = ["in", list(allowed - SKIP_RECEIVERS)]
    return frappe.get_all("User", filters=filters, or_filters=or_filters,
                          fields=["name", "full_name"], order_by="full_name asc",
                          limit_page_length=cint(limit) or 20)


def _validate_receiver(receiver):
    if not receiver:
        frappe.throw(_("Pick the receiver who will acknowledge this issue"))
    if receiver == frappe.session.user:
        frappe.throw(_("The receiver must be someone else — you can't acknowledge your own issue"))
    if receiver in SKIP_RECEIVERS or not frappe.db.get_value(
            "User", {"name": receiver, "enabled": 1, "user_type": "System User"}, "name"):
        frappe.throw(_("Receiver {0} is not an active ERP user").format(receiver))
    if PAGE_KEY in denied_pages(receiver):
        frappe.throw(_("{0} can't open the Needle / Sinker Issue page, so they can't acknowledge. "
                       "Pick someone else or ask the admin to give them access.").format(_full_name(receiver)))


def _check_stock(merged, warehouse):
    stock = {r.item_code: r for r in _stock_rows(warehouse)}
    for code, qty in merged.items():
        available = flt(stock[code].qty) if code in stock else 0
        if qty > available:
            frappe.throw(_("{0}: only {1} in {2}, cannot issue {3}")
                         .format(code, frappe.format(available), warehouse, frappe.format(qty)))
    return stock


def _repair_items(names):
    out = {}
    for it in frappe.get_all("Asset Repair Consumed Item",
                             filters={"parent": ["in", names], "parenttype": "Asset Repair"},
                             fields=["parent", "item_code", "consumed_quantity", "warehouse", "valuation_rate"],
                             order_by="idx asc"):
        out.setdefault(it.parent, []).append({"item_code": it.item_code, "qty": flt(it.consumed_quantity),
                                              "warehouse": it.warehouse, "rate": flt(it.valuation_rate)})
    return out


def _load_pending(asset_repair, statuses=(ACK_PENDING,)):
    """Lock and return a draft spares-issue repair in one of `statuses`."""
    _ack_ready()
    row = frappe.db.get_value(
        "Asset Repair", asset_repair,
        ["name", "docstatus", "owner", "stock_consumption", "custom_receiver", "custom_ack_status",
         "custom_workstation"],
        as_dict=True, for_update=True)
    if not row or not row.stock_consumption or not row.custom_ack_status:
        frappe.throw(_("{0} is not a Needle / Sinker issue").format(asset_repair))
    if row.docstatus != 0 or row.custom_ack_status not in statuses:
        frappe.throw(_("{0} is already {1}").format(
            asset_repair, row.custom_ack_status if row.docstatus == 0 else _("posted")))
    return row


def _notify(users, title, body, workstation=None, ref=None, tag=None):
    try:
        from pranera_knit.push import send
        path = "/knit-app/spares-issue" + (f"?machine={workstation}" if workstation else "")
        send(users, title, body, path, tag=tag, ref=ref)
    except Exception:
        frappe.log_error(title="Spares issue push could not be queued")


def _pending_rows(filters):
    fields = ["name", "asset", "asset_name", "custom_workstation", "description", "actions_performed",
              "owner", "creation", "custom_receiver", "custom_ack_status", "custom_ack_remarks",
              "total_repair_cost"]
    rows = frappe.get_all("Asset Repair", filters=filters, fields=fields,
                          order_by="creation desc", limit_page_length=50)
    items = _repair_items([r.name for r in rows]) if rows else {}
    names = {}
    for r in rows:
        for u in (r.owner, r.custom_receiver):
            if u and u not in names:
                names[u] = _full_name(u)
        r["workstation"] = r.custom_workstation
        r["items"] = items.get(r.name, [])
        r["issued_by"] = names.get(r.owner)
        r["receiver_name"] = names.get(r.custom_receiver)
        r["total_value"] = sum(i["qty"] * i["rate"] for i in r["items"])
    return rows


# ── page data ─────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_setup():
    """Machines (with their linked asset), reasons and the source warehouse."""
    _check_page_access()
    return {
        "source_warehouse": SOURCE_WAREHOUSE,
        "machines": _machine_rows(),
        "reasons": REASONS,
        "can_change_asset": _is_manager(),
        "user": frappe.session.user,
        "can_issue": bool(frappe.has_permission("Stock Entry", "create")
                          and frappe.has_permission("Stock Entry", "submit")),
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
    if has_ws:
        fields.append("custom_workstation")
    has_ack = _has_custom_field("Asset Repair", "custom_receiver")
    if has_ack:
        fields += ["custom_receiver", "custom_acknowledged_on"]
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
        receiver = r.get("custom_receiver")
        if receiver and receiver not in user_names:
            user_names[receiver] = _full_name(receiver)
        r["received_by"] = user_names.get(receiver) if receiver else None
        r["acknowledged_on"] = r.get("custom_acknowledged_on")

    frequent = []
    if workstation:
        counts = {}
        for r in repairs:
            for it in r["items"]:
                counts[it["item_code"]] = counts.get(it["item_code"], 0) + 1
        frequent = [k for k, _v in sorted(counts.items(), key=lambda kv: -kv[1])][:8]
    return {"issues": repairs, "frequent_items": frequent}


# ── issue (pending) ───────────────────────────────────────────────────────

@frappe.whitelist()
def search_receivers(txt=None):
    """Users who can receive (and acknowledge) an issue: enabled system users
    with access to this page, minus the current user."""
    _check_page_access()
    return [u for u in _receiver_candidates(txt, limit=500) if u.name != frappe.session.user]


@frappe.whitelist()
def issue_spares(workstation, items, receiver=None, asset=None, reason=None, remarks=None, failure_date=None,
                 warehouse=None):
    """Save a DRAFT Asset Repair (stock consumption) for the machine, waiting
    for `receiver` to acknowledge it. No stock moves until then.

    items: JSON list of {item_code, qty}
    Returns {asset_repair, status, receiver, receiver_name, total_value}.
    """
    _check_page_access()
    _ack_ready()
    if not (frappe.has_permission("Stock Entry", "create") and frappe.has_permission("Stock Entry", "submit")):
        frappe.throw(_("You need permission to create and submit Stock Entries (e.g. the Stock User role) "
                       "to issue needles / sinkers. Please ask the ERP admin."), frappe.PermissionError)
    _validate_receiver(receiver)

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
    for code, qty in merged.items():
        if qty != int(qty):
            frappe.throw(_("{0}: quantity must be a whole number of pieces").format(code))
    stock = _check_stock(merged, warehouse)

    when = get_datetime(failure_date) if failure_date else now_datetime()
    now = now_datetime()
    if when > now:
        when = now
    reason = reason if reason in REASONS else (reason or "Needle / sinker replacement")
    receiver_name = _full_name(receiver)
    lines = [f"{reason} on {workstation}"]
    if remarks:
        lines.append(remarks.strip())
    lines.append(f"Issued from Knit App by {_full_name(frappe.session.user)} to {receiver_name}")

    repair = frappe.get_doc({
        "doctype": "Asset Repair",
        "asset": asset,
        "company": asset_doc.company or COMPANY,
        "failure_date": when,
        "repair_status": "Pending",
        "cost_center": COST_CENTER if frappe.db.exists("Cost Center", COST_CENTER) else asset_doc.cost_center,
        "stock_consumption": 1,
        "capitalize_repair_cost": 0,
        "description": "\n".join(lines),
        "actions_performed": "Replaced: " + ", ".join(f"{c} × {int(q)}" for c, q in merged.items()),
        "custom_receiver": receiver,
        "custom_ack_status": ACK_PENDING,
        "stock_items": [
            {"item_code": code, "warehouse": warehouse, "consumed_quantity": qty,
             "valuation_rate": flt(stock[code].valuation_rate)}
            for code, qty in merged.items()
        ],
    })
    if _has_custom_field("Asset Repair", "custom_workstation"):
        repair.custom_workstation = workstation
    repair.flags.ignore_permissions = True
    repair.insert()

    _notify([receiver], "Needles / sinkers to acknowledge",
            f"{_full_name(frappe.session.user)} issued "
            + ", ".join(f"{c.replace('SPARES/KNIT MAC ', '')} × {int(q)}" for c, q in merged.items())
            + f" for {workstation}. Open the app to acknowledge.",
            workstation=workstation, ref=("Asset Repair", repair.name), tag=f"spares-ack:{repair.name}")

    return {
        "asset_repair": repair.name,
        "status": ACK_PENDING,
        "receiver": receiver,
        "receiver_name": receiver_name,
        "total_value": flt(sum(flt(stock[c].valuation_rate) * q for c, q in merged.items()), 2),
        "asset": asset,
        "workstation": workstation,
    }


@frappe.whitelist()
def get_pending_issues(workstation=None):
    """Draft issues waiting for acknowledgement: `for_me` (I'm the receiver),
    `sent_by_me` (I issued them; also the ones rejected back to me)."""
    _check_page_access()
    if not _has_custom_field("Asset Repair", "custom_ack_status"):
        return {"for_me": [], "sent_by_me": []}
    me = frappe.session.user
    base = {"docstatus": 0, "stock_consumption": 1}
    if workstation:
        base["custom_workstation"] = workstation
    for_me = _pending_rows({**base, "custom_ack_status": ACK_PENDING, "custom_receiver": me})
    sent = _pending_rows({**base, "custom_ack_status": ["in", [ACK_PENDING, ACK_REJECTED]], "owner": me})
    return {"for_me": for_me, "sent_by_me": sent}


@frappe.whitelist()
def acknowledge_issue(asset_repair):
    """Receiver confirms they got the needles / sinkers: the repair is
    submitted and ERPNext posts the Material Issue now."""
    _check_page_access()
    row = _load_pending(asset_repair)
    me = frappe.session.user
    if row.custom_receiver != me:
        frappe.throw(_("Only {0} can acknowledge {1}").format(_full_name(row.custom_receiver), asset_repair),
                     frappe.PermissionError)

    repair = frappe.get_doc("Asset Repair", asset_repair)
    merged = {}
    for it in repair.stock_items:
        merged[it.item_code] = merged.get(it.item_code, 0) + flt(it.consumed_quantity)
    warehouse = repair.stock_items[0].warehouse if repair.stock_items else SOURCE_WAREHOUSE
    _check_stock(merged, warehouse)

    issuer = row.owner
    if not frappe.db.get_value("User", {"name": issuer, "enabled": 1}, "name"):
        frappe.throw(_("{0}, who raised this issue, is no longer an active user. Ask the store to raise it again.")
                     .format(issuer))

    now = now_datetime()
    repair.repair_status = "Completed"
    repair.completion_date = now
    repair.custom_ack_status = ACK_DONE
    repair.custom_acknowledged_on = now
    repair.description = (repair.description or "") + f"\nAcknowledged by {_full_name(me)} on {now:%d-%m-%Y %H:%M}"
    repair.flags.ignore_permissions = True

    # Post as the storekeeper who raised it (see module docstring).
    frappe.flags.knit_spares_issue = True
    frappe.set_user(issuer)
    try:
        if not (frappe.has_permission("Stock Entry", "create") and frappe.has_permission("Stock Entry", "submit")):
            frappe.throw(_("{0}, who raised this issue, no longer has permission to post Stock Entries. "
                           "Ask the ERP admin.").format(_full_name(issuer)))
        repair.submit()
    finally:
        frappe.set_user(me)
        frappe.flags.knit_spares_issue = False

    stock_entry = frappe.db.get_value("Stock Entry", {"asset_repair": repair.name, "docstatus": 1}, "name")
    _notify([issuer], "Needles / sinkers acknowledged",
            f"{_full_name(me)} acknowledged {repair.name} for {row.custom_workstation}"
            + (f" — {stock_entry} posted." if stock_entry else "."),
            workstation=row.custom_workstation, ref=("Asset Repair", repair.name), tag=f"spares-ack:{repair.name}")
    return {
        "asset_repair": repair.name,
        "status": ACK_DONE,
        "stock_entry": stock_entry,
        "total_value": flt(repair.total_repair_cost, 2),
        "workstation": row.custom_workstation,
    }


@frappe.whitelist()
def reject_issue(asset_repair, remarks=None):
    """Receiver says they did not get these needles / sinkers. Nothing is posted."""
    _check_page_access()
    row = _load_pending(asset_repair)
    me = frappe.session.user
    if row.custom_receiver != me:
        frappe.throw(_("Only {0} can reject {1}").format(_full_name(row.custom_receiver), asset_repair),
                     frappe.PermissionError)
    remarks = (remarks or "").strip()
    if not remarks:
        frappe.throw(_("Say why you are rejecting it"))
    frappe.db.set_value("Asset Repair", asset_repair, {
        "custom_ack_status": ACK_REJECTED,
        "custom_ack_remarks": remarks,
        "custom_acknowledged_on": now_datetime(),
    })
    _notify([row.owner], "Needle / sinker issue rejected",
            f"{_full_name(me)} rejected {asset_repair} for {row.custom_workstation}: {remarks}",
            workstation=row.custom_workstation, ref=("Asset Repair", asset_repair), tag=f"spares-ack:{asset_repair}")
    return {"asset_repair": asset_repair, "status": ACK_REJECTED}


@frappe.whitelist()
def withdraw_issue(asset_repair):
    """The storekeeper takes back an issue that is still pending (or clears one
    the receiver rejected). Nothing is posted."""
    _check_page_access()
    row = _load_pending(asset_repair, statuses=(ACK_PENDING, ACK_REJECTED))
    if row.owner != frappe.session.user and not _is_manager():
        frappe.throw(_("Only the person who raised {0} can withdraw it").format(asset_repair),
                     frappe.PermissionError)
    frappe.db.set_value("Asset Repair", asset_repair, {
        "custom_ack_status": ACK_WITHDRAWN,
        "custom_ack_remarks": f"Withdrawn by {_full_name(frappe.session.user)}",
    })
    if row.custom_ack_status == ACK_PENDING:
        _notify([row.custom_receiver], "Needle / sinker issue withdrawn",
                f"{asset_repair} for {row.custom_workstation} was withdrawn — no need to acknowledge it.",
                workstation=row.custom_workstation, ref=("Asset Repair", asset_repair),
                tag=f"spares-ack:{asset_repair}")
    return {"asset_repair": asset_repair, "status": ACK_WITHDRAWN}
