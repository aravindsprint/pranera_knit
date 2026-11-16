# Copyright (c) 2026, Pranera Services & Solutions
"""
Row-level visibility of Job Cards and Work Orders for operators.

Users with the "Job Card Operator" role see only:
  * Job Cards on which they are the operator — their Employee record
    (Employee.user_id = the user) is in the Job Card's Time Logs table
    (or the Employee multi-select); a Job Card explicitly given to them with
    "Assign To" also still counts;
  * Work Orders that have at least one such Job Card.

"Knitting Supervisor", "System Manager" (and Administrator) see everything,
even if they also hold "Job Card Operator".

Used by the permission_query_conditions / has_permission hooks (Desk lists,
reports, /api/resource, frappe.get_list) and by the knit-app APIs that query
with raw SQL (knit_get_work_orders, Machine Status) via job_card_condition().

This is a read/write filter on top of normal role permissions: it never
grants access the role permissions do not already give.
"""

import frappe

RESTRICTED_ROLE = "Job Card Operator"
BYPASS_ROLES = {"System Manager", "Knitting Supervisor"}


def is_restricted(user=None):
    user = user or frappe.session.user
    if user == "Administrator":
        return False
    roles = set(frappe.get_roles(user))
    return RESTRICTED_ROLE in roles and not (roles & BYPASS_ROLES)


def employee_ids(user=None):
    """Employee records linked to this user (Employee.user_id), cached per request."""
    user = user or frappe.session.user
    cache = frappe.local.__dict__.setdefault("_knit_operator_employees", {})
    if user not in cache:
        cache[user] = frappe.get_all("Employee", filters={"user_id": user}, pluck="name")
    return cache[user]


def job_card_condition(user=None, table="`tabJob Card`"):
    """SQL condition on a Job Card table/alias limiting rows to the user's
    Job Cards, or "" when the user is not restricted."""
    user = user or frappe.session.user
    if not is_restricted(user):
        return ""
    # INSTR on the quoted user instead of LIKE '%user%': no literal "%" in the
    # SQL, so callers can still run it with %s / %(name)s parameters.
    quoted_user = frappe.db.escape('"' + user + '"')
    parts = [f"INSTR(IFNULL({table}._assign, ''), {quoted_user}) > 0"]
    emps = employee_ids(user)
    if emps:
        emp_list = ", ".join(frappe.db.escape(e) for e in emps)
        parts.append(
            f"""{table}.name IN (
                SELECT jctl.parent FROM `tabJob Card Time Log` jctl
                WHERE jctl.parenttype = 'Job Card' AND jctl.employee IN ({emp_list}))"""
        )
    return "(" + " OR ".join(parts) + ")"


def work_order_condition(user=None, table="`tabWork Order`"):
    """SQL condition on a Work Order table/alias limiting rows to Work Orders
    that have one of the user's Job Cards, or "" when not restricted."""
    jc_cond = job_card_condition(user, table="jc_perm")
    if not jc_cond:
        return ""
    return f"""{table}.name IN (
        SELECT jc_perm.work_order FROM `tabJob Card` jc_perm
        WHERE jc_perm.work_order IS NOT NULL AND {jc_cond})"""


# ── Job Card hooks ─────────────────────────────────────────────────────────

def get_permission_query_conditions(user=None):
    return job_card_condition(user)


def has_permission(doc, ptype=None, user=None):
    user = user or frappe.session.user
    if not is_restricted(user) or doc.get("__islocal"):
        return True
    emps = set(employee_ids(user))
    for row in (doc.get("time_logs") or []) + (doc.get("employee") or []):
        if row.get("employee") and row.employee in emps:
            return True
    assigned = frappe.parse_json(doc.get("_assign")) if doc.get("_assign") else []
    return user in (assigned or [])


# ── Work Order hooks ───────────────────────────────────────────────────────

def get_work_order_permission_query_conditions(user=None):
    return work_order_condition(user)


def work_order_has_permission(doc, ptype=None, user=None):
    user = user or frappe.session.user
    if not is_restricted(user) or doc.get("__islocal"):
        return True
    cond = job_card_condition(user, table="jc")
    return bool(frappe.db.sql(
        f"SELECT 1 FROM `tabJob Card` jc WHERE jc.work_order = %s AND {cond} LIMIT 1",
        (doc.name,),
    ))
