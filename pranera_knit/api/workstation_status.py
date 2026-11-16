"""
pranera_knit/api/workstation_status.py
Whitelisted method behind the knit-app "Machine Status" page
(key "workstation-status").

For every knitting machine (Workstation SJ.., IL.., FK..) it answers:
  * which Work Order is running on it now,
  * that WO's qty to manufacture / material transferred / manufactured /
    pending, its start date and last production date,
  * which Work Orders are queued (upcoming) on it,
  * and whether the machine is idle — with or without anything queued.

Definitions
-----------
Running WO   A Work Order (Not Started / In Process) with a Job Card in
             "Work In Progress" on that machine. If a machine has more than
             one, the one with the latest roll activity is "current" and the
             rest are returned in `also_running`.
Upcoming WO  Any other open Work Order with an "Open" (not yet started) Job
             Card on that machine. Sorted by planned start date.
Unfinished   Open Work Orders that ran on the machine earlier (only Completed
             Job Cards there) but are below FINISHED_RATIO of qty (same 95 %
             rule as process_loss._is_finished) — leftovers that may come
             back to the machine. Listed separately so old part-done WOs do
             not make a machine look busy.
Idle         No WIP Job Card on the machine. "idle" = has upcoming work,
             "no_work_order" = no running or upcoming Work Order.

Who sees what
-------------
A "Job Card Operator" (without Knitting Supervisor / System Manager) only
sees the machines and Work Orders of their own Job Cards — the ones where
their Employee is in the Time Logs table (job_card_permissions.py).
Supervisors see every machine.

Start / last production date
----------------------------
Job Card actual_start_date / actual_end_date and the time logs are not
filled in on this site (the PWA records times on each Roll), so:
  start date            = earliest Roll.start_time of the WO
                          (= start of its first Job Card)
  last production date  = latest Roll.end_time of the WO
                          (= end of its last Job Card)
falling back to the Job Cards' actual dates / posting dates when a WO has
no rolls yet.
"""
import re

import frappe
from frappe import _
from frappe.utils import flt, get_datetime, now_datetime

from pranera_knit.job_card_permissions import employee_ids, is_restricted, job_card_condition
from pranera_knit.page_access import denied_pages

PAGE_KEY = "workstation-status"
MACHINE_RE = re.compile(r"^(SJ|IL|FK)\d", re.IGNORECASE)
MACHINE_SQL_RE = "^(SJ|IL|FK)[0-9]"
OPEN_WO_STATUSES = ("Not Started", "In Process")
FINISHED_RATIO = 0.95
STALE_HOURS = 24
MACHINE_TYPES = {"SJ": "Single Jersey", "IL": "Interlock", "FK": "Flat Knit"}


def _check_page_access():
    if PAGE_KEY in denied_pages():
        frappe.throw(_("You do not have access to the Machine Status page."),
                     frappe.PermissionError)


def _machine_type(name):
    return MACHINE_TYPES.get((name or "")[:2].upper(), "Other")


def _iso(dt):
    return str(dt) if dt else None


@frappe.whitelist()
def get_workstation_status():
    _check_page_access()

    restricted = is_restricted()
    jc_cond = job_card_condition(table="jc")

    machines = [
        w for w in frappe.get_all(
            "Workstation",
            fields=["name", "workstation_type", "status"],
            order_by="name asc",
            limit_page_length=0,
        )
        if MACHINE_RE.match(w.name or "")
    ]

    # Job Cards on knitting machines for open Work Orders, counted by status.
    jc_rows = frappe.db.sql(
        f"""
        SELECT jc.workstation, jc.work_order, jc.status, COUNT(*) AS cnt
        FROM `tabJob Card` jc
        JOIN `tabWork Order` wo ON wo.name = jc.work_order
        WHERE jc.docstatus < 2
          AND wo.docstatus = 1
          AND wo.status IN %(wo_statuses)s
          AND jc.workstation REGEXP %(ws_re)s
          {"AND " + jc_cond if jc_cond else ""}
        GROUP BY jc.workstation, jc.work_order, jc.status
        """,
        {"wo_statuses": OPEN_WO_STATUSES, "ws_re": MACHINE_SQL_RE},
        as_dict=True,
    )

    # {workstation: {work_order: {status: count}}}
    by_ws = {}
    for r in jc_rows:
        by_ws.setdefault(r.workstation, {}).setdefault(r.work_order, {})[r.status] = r.cnt

    if restricted:
        # Operators only see machines they have a Job Card on.
        machines = [m for m in machines if m.name in by_ws]

    wo_names = sorted({r.work_order for r in jc_rows})
    wos = _work_orders(wo_names)
    dates = _production_dates(wo_names)

    now = now_datetime()
    out = []
    for m in machines:
        ws_wos = by_ws.get(m.name, {})
        running, upcoming, unfinished = [], [], []
        for wo_name, statuses in ws_wos.items():
            wo = wos.get(wo_name)
            if not wo:
                continue
            row = _wo_row(wo, dates.get(wo_name, {}), statuses)
            if statuses.get("Work In Progress"):
                running.append(row)
            elif statuses.get("Open"):
                upcoming.append(row)
            elif not row["finished"]:
                unfinished.append(row)

        running.sort(key=lambda r: r["last_activity"] or "", reverse=True)
        upcoming.sort(key=lambda r: (r["planned_start_date"] or "9999", r["work_order"]))
        unfinished.sort(key=lambda r: r["last_activity"] or "", reverse=True)

        current = running[0] if running else None
        if current:
            state = "running"
            last = get_datetime(current["last_activity"]) if current["last_activity"] else None
            current["stale"] = bool(last and (now - last).total_seconds() > STALE_HOURS * 3600)
        else:
            state = "idle" if upcoming else "no_work_order"

        out.append({
            "workstation": m.name,
            "machine_type": _machine_type(m.name),
            "workstation_type": m.workstation_type,
            "state": state,
            "current": current,
            "also_running": running[1:],
            "upcoming": upcoming,
            "unfinished": unfinished,
        })

    return {
        "generated_at": _iso(now),
        "stale_hours": STALE_HOURS,
        "scope": "assigned" if restricted else "all",
        "employee_linked": bool(employee_ids()) if restricted else True,
        "machines": out,
    }


def _work_orders(names):
    if not names:
        return {}
    rows = frappe.get_all(
        "Work Order",
        filters={"name": ["in", names]},
        fields=[
            "name", "status", "production_item", "item_name", "stock_uom",
            "qty", "material_transferred_for_manufacturing", "produced_qty",
            "planned_start_date", "sales_order", "project",
        ],
        limit_page_length=0,
    )
    return {r.name: r for r in rows}


def _production_dates(names):
    """{work_order: {start, end, last_activity, rolls}} from Rolls, with Job Card fallback."""
    if not names:
        return {}
    out = {}
    for r in frappe.db.sql(
        """
        SELECT work_order,
               MIN(start_time) AS first_start,
               MAX(end_time)   AS last_end,
               MAX(start_time) AS last_start,
               COUNT(*)        AS rolls
        FROM `tabRoll`
        WHERE work_order IN %(names)s
        GROUP BY work_order
        """,
        {"names": names},
        as_dict=True,
    ):
        out[r.work_order] = {
            "start": r.first_start,
            "end": r.last_end,
            "last_activity": max([d for d in (r.last_end, r.last_start) if d], default=None),
            "rolls": r.rolls,
        }

    for r in frappe.db.sql(
        """
        SELECT work_order,
               MIN(actual_start_date) AS jc_start,
               MAX(actual_end_date) AS jc_end,
               MAX(CASE WHEN status = 'Completed' THEN posting_date END) AS jc_last_done
        FROM `tabJob Card`
        WHERE docstatus < 2 AND work_order IN %(names)s
        GROUP BY work_order
        """,
        {"names": names},
        as_dict=True,
    ):
        d = out.setdefault(r.work_order, {"start": None, "end": None, "last_activity": None, "rolls": 0})
        if not d["start"]:
            d["start"] = r.jc_start
        if not d["end"]:
            d["end"] = r.jc_end or r.jc_last_done
    return out


def _wo_row(wo, dates, statuses):
    qty = flt(wo.qty)
    produced = flt(wo.produced_qty)
    transferred = flt(wo.material_transferred_for_manufacturing)
    return {
        "work_order": wo.name,
        "wo_status": wo.status,
        "item_code": wo.production_item,
        "item_name": wo.item_name,
        "uom": wo.stock_uom,
        "sales_order": wo.sales_order,
        "project": wo.project,
        "qty": qty,
        "material_transferred": transferred,
        "produced_qty": produced,
        "pending_qty": max(qty - produced, 0),
        "progress_pct": round(produced / qty * 100, 1) if qty else 0,
        "finished": bool(qty) and produced >= qty * FINISHED_RATIO,
        "planned_start_date": _iso(wo.planned_start_date),
        "start_date": _iso(dates.get("start")),
        "last_production_date": _iso(dates.get("end")),
        "last_activity": _iso(dates.get("last_activity") or dates.get("end")),
        "rolls": dates.get("rolls") or 0,
        "job_cards": {
            "wip": statuses.get("Work In Progress", 0),
            "open": statuses.get("Open", 0),
            "completed": statuses.get("Completed", 0),
        },
    }
