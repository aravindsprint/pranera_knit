"""
pranera_knit/api/operator_job_cards.py
Whitelisted method behind the knit-app "Operator Job Cards" page
(key "operator-job-cards").

Groups knitting Job Cards (workstation SJ.., IL.., FK..) by operator, the
Employee in the Job Card's Time Logs table:

  current   Job Card status "Work In Progress"
  upcoming  Job Card status "Open" (not started) on an open Work Order
  finished  Job Card "Completed" whose last roll ended in the chosen period

Open Job Cards with no operator yet come back in `unassigned`, so a
supervisor can see what still has to be handed out (👤 on Job Cards).

Visibility follows job_card_permissions.py: an operator sees only their own
Job Cards, a Fabric supervisor Kgs ones, a Collar Cuff supervisor Pcs ones,
Knitting Supervisor / System Manager everything.

A current Job Card is flagged `stale` when it has had no roll activity for
STALE_HOURS (forgotten "Work In Progress" job cards).

Times come from the Rolls (start of the first roll, end of the last roll),
because Job Card actual dates / time logs are not filled in on this site.
Produced qty = sum of roll weight (Kgs work orders) or roll pcs (Pcs).
"""
import frappe
from frappe import _
from frappe.utils import add_days, flt, get_datetime, getdate, now_datetime, today

from pranera_knit.job_card_permissions import job_card_condition
from pranera_knit.page_access import denied_pages

PAGE_KEY = "operator-job-cards"
MACHINE_SQL_RE = "^(SJ|IL|FK)[0-9]"
OPEN_WO_STATUSES = ("Not Started", "In Process")
MAX_RANGE_DAYS = 62
STALE_HOURS = 24


def _check_page_access():
    if PAGE_KEY in denied_pages():
        frappe.throw(_("You do not have access to the Operator Job Cards page."),
                     frappe.PermissionError)


def _iso(dt):
    return str(dt) if dt else None


@frappe.whitelist()
def get_operator_job_cards(from_date=None, to_date=None):
    _check_page_access()

    to_d = getdate(to_date or today())
    from_d = getdate(from_date or to_d)
    if from_d > to_d:
        from_d, to_d = to_d, from_d
    if (to_d - from_d).days > MAX_RANGE_DAYS:
        frappe.throw(_("Choose a period of at most {0} days.").format(MAX_RANGE_DAYS))

    jc_cond = job_card_condition(table="jc")
    extra = f"AND {jc_cond}" if jc_cond else ""

    # Completed job cards are only candidates if touched since the start of the
    # period (submitting a job card updates `modified`); the period itself is
    # applied below on the last roll's end time.
    jcs = frappe.db.sql(
        f"""
        SELECT jc.name, jc.status, jc.docstatus, jc.work_order, jc.workstation,
               jc.production_item, jc.item_name, jc.for_quantity, jc.total_completed_qty,
               jc.posting_date, jc.modified,
               wo.stock_uom AS uom, wo.status AS wo_status, wo.planned_start_date
        FROM `tabJob Card` jc
        JOIN `tabWork Order` wo ON wo.name = jc.work_order
        WHERE jc.docstatus < 2
          AND jc.workstation REGEXP %(ws_re)s
          AND (
                (jc.status = 'Work In Progress')
             OR (jc.status = 'Open' AND jc.docstatus = 0 AND wo.docstatus = 1
                 AND wo.status IN %(wo_statuses)s)
             OR (jc.status = 'Completed' AND jc.modified >= %(from_dt)s)
          )
          {extra}
        """,
        {"ws_re": MACHINE_SQL_RE, "wo_statuses": OPEN_WO_STATUSES, "from_dt": from_d},
        as_dict=True,
    )
    if not jcs:
        return _empty(from_d, to_d)

    names = [j.name for j in jcs]
    rolls = {
        r.job_card: r
        for r in frappe.db.sql(
            """
            SELECT job_card, COUNT(*) AS rolls,
                   MIN(start_time) AS start_time, MAX(end_time) AS end_time,
                   SUM(roll_weight) AS weight, SUM(total_qty) AS pcs
            FROM `tabRoll`
            WHERE job_card IN %(names)s
            GROUP BY job_card
            """,
            {"names": names},
            as_dict=True,
        )
    }
    operators_by_jc = {}
    for r in frappe.db.sql(
        """
        SELECT parent, employee, custom_employee_name
        FROM `tabJob Card Time Log`
        WHERE parenttype = 'Job Card' AND parent IN %(names)s
          AND IFNULL(employee, '') != ''
        ORDER BY idx
        """,
        {"names": names},
        as_dict=True,
    ):
        lst = operators_by_jc.setdefault(r.parent, [])
        if r.employee not in [e for e, _n in lst]:
            lst.append((r.employee, r.custom_employee_name))

    now = now_datetime()
    period_start = get_datetime(from_d)
    period_end = get_datetime(add_days(to_d, 1))

    operators = {}
    unassigned = []
    for j in jcs:
        rl = rolls.get(j.name) or frappe._dict()
        row = _jc_row(j, rl)

        if j.status == "Work In Progress":
            bucket = "current"
            last = rl.get("end_time") or rl.get("start_time")
            row["stale"] = (not last) or (now - get_datetime(last)).total_seconds() > STALE_HOURS * 3600
        elif j.status == "Open":
            bucket = "upcoming"
        else:
            finished_at = get_datetime(rl.end_time) if rl.get("end_time") else get_datetime(j.modified)
            if not (period_start <= finished_at < period_end):
                continue
            row["finished_at"] = _iso(finished_at)
            bucket = "finished"

        ops = operators_by_jc.get(j.name) or []
        if not ops:
            if bucket == "upcoming":
                unassigned.append(row)
            continue
        for emp, emp_name in ops:
            op = operators.setdefault(emp, {
                "employee": emp, "employee_name": emp_name,
                "current": [], "upcoming": [], "finished": [],
            })
            op[bucket].append(row)

    _fill_employee_details(operators)
    out = []
    for op in operators.values():
        op["current"].sort(key=lambda r: r["start_time"] or "")
        op["upcoming"].sort(key=lambda r: (r["planned_start_date"] or "9999", r["job_card"]))
        op["finished"].sort(key=lambda r: r["finished_at"] or "", reverse=True)
        op["finished_totals"] = _totals(op["finished"])
        out.append(op)
    # Busy operators first, then by name.
    out.sort(key=lambda o: (-len(o["current"]), -len(o["upcoming"]), (o["employee_name"] or "").lower()))
    unassigned.sort(key=lambda r: (r["planned_start_date"] or "9999", r["job_card"]))

    return {
        "from_date": str(from_d),
        "to_date": str(to_d),
        "stale_hours": STALE_HOURS,
        "operators": out,
        "unassigned": unassigned,
    }


def _empty(from_d, to_d):
    return {"from_date": str(from_d), "to_date": str(to_d), "operators": [], "unassigned": []}


def _jc_row(j, rl):
    pcs_uom = (j.uom or "").strip().lower() in ("pcs", "nos")
    produced = flt(rl.get("pcs")) if pcs_uom else flt(rl.get("weight"))
    if not rl.get("rolls"):
        produced = flt(j.total_completed_qty)
    return {
        "job_card": j.name,
        "status": j.status,
        "work_order": j.work_order,
        "workstation": j.workstation,
        "item_code": j.production_item,
        "item_name": j.item_name,
        "uom": j.uom,
        "for_quantity": flt(j.for_quantity),
        "produced": round(produced, 3),
        "rolls": rl.get("rolls") or 0,
        "progress_pct": round(produced / flt(j.for_quantity) * 100, 1) if flt(j.for_quantity) else 0,
        "start_time": _iso(rl.get("start_time")),
        "end_time": _iso(rl.get("end_time")),
        "planned_start_date": _iso(j.planned_start_date),
        "posting_date": _iso(j.posting_date),
    }


def _totals(rows):
    tot = {}
    for r in rows:
        u = r["uom"] or "-"
        t = tot.setdefault(u, {"uom": u, "qty": 0.0, "rolls": 0, "job_cards": 0})
        t["qty"] = round(t["qty"] + r["produced"], 3)
        t["rolls"] += r["rolls"]
        t["job_cards"] += 1
    return list(tot.values())


def _fill_employee_details(operators):
    if not operators:
        return
    for e in frappe.get_all(
        "Employee",
        filters={"name": ["in", list(operators)]},
        fields=["name", "employee_name", "designation"],
    ):
        op = operators[e.name]
        op["employee_name"] = e.employee_name or op["employee_name"]
        op["designation"] = e.designation
