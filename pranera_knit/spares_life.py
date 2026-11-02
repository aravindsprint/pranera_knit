"""
pranera_knit/spares_life.py
Needle / sinker life tracking per knitting machine.

Each knitting Workstation has a "Spare Items" table (Workstation.custom_spare_items,
child DocType "Workstation Spare Item", created by patch v1_12):

    item_code            needle / sinker allowed on this machine — the Needle /
                         Sinker Issue page only offers (and the API only accepts)
                         items listed here
    set_qty              pieces in one full set of that item on this machine
    track_life           life is tracked for this item (SJ / IL machines; collar
                         FK machines only replace broken needles, so off there)
    max_production       production allowed on one full set, in the machine's
                         Job Card unit (Kgs on SJ / IL). Default 55,000.
    last_full_set_on     when the full set was last changed — set automatically by
                         a "Full Set Change" issue, or entered by the knitting team
                         as the starting point
    production_since     kg produced since then (refreshed by refresh_workstation)
    alert_level          highest alert already sent for this set: "", Warning, Max

Production = SUM(Job Card.total_completed_qty) of submitted Job Cards on the
workstation with posting_date on/after the date of last_full_set_on. (Job Card has
no reliable end time on this site, so the day of the change is counted in full.)

Alerts: once production reaches WARN_PCT of max_production → "Warning", and at
max_production → "Max". Each level is sent once per set (alert_level), and a Full
Set Change resets it. One message per machine lists every item that crossed a
level, with the spare-store stock against the full-set qty, so the store can
order in time. Sent by Knit App push + WhatsApp (pranera_knit.push.send) and
email, to users with the ALERT_ROLE role.

Triggers: Job Card on_submit (that machine, in the background) and a daily
sweep of every machine (hooks.py scheduler_events).
"""
import frappe
from frappe.utils import cint, flt, get_url, getdate

CHILD_DT = "Workstation Spare Item"
TABLE_FIELD = "custom_spare_items"
ALERT_ROLE = "Needle Life Alert"
SOURCE_WAREHOUSE = "NAP_E1/FF/SPARE STORE  - PSS"
DEFAULT_MAX = 55000
LEVELS = {"": 0, "Warning": 1, "Max": 2}


def warn_pct():
    return flt(frappe.conf.get("knit_needle_warn_pct") or 90)


def is_ready():
    return bool(frappe.db.exists("DocType", CHILD_DT)) and \
        frappe.get_meta("Workstation").has_field(TABLE_FIELD)


def spare_rows(workstation):
    if not is_ready():
        return []
    return frappe.get_all(
        CHILD_DT,
        filters={"parent": workstation, "parenttype": "Workstation", "parentfield": TABLE_FIELD},
        fields=["name", "idx", "item_code", "set_qty", "track_life", "max_production",
                "last_full_set_on", "last_full_set_repair", "production_since", "alert_level"],
        order_by="idx asc",
    )


def production_since(workstation, since):
    if not since:
        return 0.0
    return flt(frappe.db.sql(
        """SELECT COALESCE(SUM(total_completed_qty), 0) FROM `tabJob Card`
           WHERE workstation = %s AND docstatus = 1 AND posting_date >= %s""",
        (workstation, getdate(since)),
    )[0][0])


def store_qty(item_codes):
    if not item_codes:
        return {}
    return dict(frappe.db.sql(
        "SELECT item_code, actual_qty FROM `tabBin` WHERE warehouse = %s AND item_code IN %s",
        (SOURCE_WAREHOUSE, tuple(item_codes)),
    ))


def life_status(workstation, rows=None, refresh=False):
    """Per tracked row: production since the last full set, % of max and level.
    With refresh=True the computed production_since is written back."""
    rows = rows if rows is not None else spare_rows(workstation)
    cache = {}
    out = []
    for r in rows:
        if not cint(r.track_life):
            continue
        maximum = flt(r.max_production) or DEFAULT_MAX
        if r.last_full_set_on:
            key = str(getdate(r.last_full_set_on))
            if key not in cache:
                cache[key] = production_since(workstation, r.last_full_set_on)
            produced = cache[key]
        else:
            produced = None
        pct = (produced / maximum * 100) if produced is not None and maximum else None
        level = ""
        if pct is not None:
            level = "Max" if pct >= 100 else ("Warning" if pct >= warn_pct() else "")
        if refresh and produced is not None and flt(produced, 3) != flt(r.production_since, 3):
            frappe.db.set_value(CHILD_DT, r.name, "production_since", produced, update_modified=False)
        out.append({
            "row": r.name, "item_code": r.item_code, "set_qty": cint(r.set_qty),
            "max_production": maximum, "last_full_set_on": r.last_full_set_on,
            "produced": produced, "pct": pct, "level": level, "alert_level": r.alert_level or "",
        })
    return out


# ── Alerts ────────────────────────────────────────────────────────────────

def refresh_workstation(workstation, notify=True):
    """Recompute life for one machine and alert on newly crossed levels."""
    if not is_ready():
        return []
    rows = spare_rows(workstation)
    status = life_status(workstation, rows, refresh=True)
    crossed = [s for s in status if LEVELS[s["level"]] > LEVELS.get(s["alert_level"], 0)]
    if crossed and notify:
        _send_alert(workstation, crossed)
    for s in crossed:
        frappe.db.set_value(CHILD_DT, s["row"], "alert_level", s["level"], update_modified=False)
    return status


def check_all():
    """Daily sweep (scheduler)."""
    if not is_ready():
        return
    machines = frappe.get_all(
        CHILD_DT, filters={"parenttype": "Workstation", "track_life": 1, "last_full_set_on": ["is", "set"]},
        pluck="parent", distinct=True,
    )
    for ws in sorted(set(machines)):
        try:
            refresh_workstation(ws)
            frappe.db.commit()
        except Exception:
            frappe.db.rollback()
            frappe.log_error(title=f"Needle life check failed for {ws}")


def on_job_card_submit(doc, method=None):
    if not doc.get("workstation") or not is_ready():
        return
    if not frappe.db.exists(CHILD_DT, {"parent": doc.workstation, "track_life": 1}):
        return
    frappe.enqueue(
        "pranera_knit.spares_life.refresh_workstation",
        queue="short", enqueue_after_commit=True, workstation=doc.workstation,
    )


def alert_recipients():
    from pranera_knit.push import users_with_roles
    return users_with_roles([ALERT_ROLE])


def _send_alert(workstation, crossed):
    users = alert_recipients()
    if not users:
        return
    stock = store_qty([s["item_code"] for s in crossed])
    names = dict(frappe.get_all("Item", filters={"name": ["in", [s["item_code"] for s in crossed]]},
                                fields=["name", "item_name"], as_list=True))
    worst = "Max" if any(s["level"] == "Max" for s in crossed) else "Warning"
    title = (f"{workstation}: needle set due for change" if worst == "Max"
             else f"{workstation}: needle life at {int(warn_pct())}%")

    lines, short_lines = [], []
    for s in crossed:
        have = flt(stock.get(s["item_code"]))
        need = cint(s["set_qty"])
        code = s["item_code"].replace("SPARES/KNIT MAC ", "")
        stock_txt = (f"store {int(have)} / set {need}: OK" if not need or have >= need
                     else f"store {int(have)} / set {need}: SHORT {int(need - have)}")
        lines.append(
            f"{code} ({names.get(s['item_code'], '')}): {flt(s['produced'], 0):,.0f} of "
            f"{flt(s['max_production'], 0):,.0f} kg ({s['pct']:.0f}%) since "
            f"{frappe.format(s['last_full_set_on'], {'fieldtype': 'Datetime'})}; {stock_txt}"
        )
        short_lines.append(f"{code} {s['pct']:.0f}% ({stock_txt})")

    body = "; ".join(short_lines)
    path = "/knit-app/spares-issue?machine=" + workstation
    try:
        from pranera_knit.push import send
        send(users, title, body, path=path, tag=f"needle-life-{workstation}",
             ref=("Workstation", workstation), whatsapp=True)
    except Exception:
        frappe.log_error(title=f"Needle life push for {workstation} failed")

    try:
        emails = [e for e in frappe.get_all("User", filters={"name": ["in", users], "enabled": 1},
                                            pluck="email") if e]
        if emails:
            items_html = "".join(f"<li>{frappe.utils.escape_html(l)}</li>" for l in lines)
            frappe.sendmail(
                recipients=emails,
                subject=f"[Knit] {title}",
                message=(
                    f"<p><b>{frappe.utils.escape_html(title)}</b></p><ul>{items_html}</ul>"
                    f"<p>Life is counted from submitted Job Cards on {frappe.utils.escape_html(workstation)} "
                    f"since the last full set change. Record the next full set change in the Knit App: "
                    f"<a href='{get_url(path)}'>Needle / Sinker Issue</a>.</p>"
                ),
                reference_doctype="Workstation", reference_name=workstation,
                now=False,
            )
    except Exception:
        frappe.log_error(title=f"Needle life email for {workstation} failed")


# ── Full set change bookkeeping (called by api/spares_issue.issue_spares) ──

def mark_full_set(workstation, item_codes, when, asset_repair):
    for r in spare_rows(workstation):
        if r.item_code in item_codes and cint(r.track_life):
            frappe.db.set_value(CHILD_DT, r.name, {
                "last_full_set_on": when,
                "last_full_set_repair": asset_repair,
                "production_since": 0,
                "alert_level": "",
            }, update_modified=False)


def on_workstation_validate(doc, method=None):
    """Knitting team editing the Spare Items table in Desk: default Max Production,
    and when Last Full Set Change is entered / changed by hand, start the count
    afresh (production 0, alerts not yet sent, no linked Asset Repair)."""
    if not doc.meta.has_field(TABLE_FIELD):
        return
    before = {}
    if not doc.is_new():
        before = {r.name: r for r in frappe.get_all(
            CHILD_DT, filters={"parent": doc.name, "parenttype": "Workstation"},
            fields=["name", "last_full_set_on", "last_full_set_repair"])}
    seen = set()
    for row in doc.get(TABLE_FIELD) or []:
        if row.item_code in seen:
            frappe.throw(f"Row {row.idx}: {row.item_code} is listed twice in Spare Items")
        seen.add(row.item_code)
        if cint(row.track_life) and not flt(row.max_production):
            row.max_production = DEFAULT_MAX
        old = before.get(row.name)
        old_on = old.last_full_set_on if old else None
        if row.last_full_set_on and str(row.last_full_set_on) != str(old_on or ""):
            row.alert_level = ""
            row.production_since = 0
            if old and row.last_full_set_repair == old.last_full_set_repair:
                row.last_full_set_repair = None
