# Copyright (c) 2026, Pranera Services & Solutions
"""
Row-level visibility of Job Cards and Work Orders by knitting role.

  Role                               Sees
  ---------------------------------  ----------------------------------------
  System Manager, Knitting Supervisor everything (Administrator too)
  Fabric Knitting Supervisor         Work Orders in Kgs + their Job Cards
                                     (single jersey / interlock fabric)
  Collar Cuff Knitting Supervisor    Work Orders in Pcs + their Job Cards
                                     (flat knit collars / cuffs)
  Job Card Operator                  Job Cards where their Employee
                                     (Employee.user_id = the user) is in the
                                     Time Logs table (or the Employee
                                     multi-select, or Assign To), and the
                                     Work Orders of those Job Cards

A user with several of these roles sees the union. Users with none of them
are not restricted here (normal role permissions only).

The UOM is the Work Order's stock_uom; a Job Card follows its Work Order.

Used by the permission_query_conditions / has_permission hooks (Desk lists,
reports, /api/resource, frappe.get_list) and by the knit-app APIs that query
with raw SQL (knit_get_work_orders, Machine Status) via job_card_condition().
It is a filter on top of role permissions: it never grants extra access.
"""

import frappe

OPERATOR_ROLE = "Job Card Operator"
ALL_ACCESS_ROLES = {"System Manager", "Knitting Supervisor"}
UOM_SUPERVISOR_ROLES = {
    "Fabric Knitting Supervisor": "Kgs",
    "Collar Cuff Knitting Supervisor": "Pcs",
}
# Roles that may assign operators to job cards (the 👤 button).
SUPERVISOR_ROLES = ALL_ACCESS_ROLES | set(UOM_SUPERVISOR_ROLES)

# Kept for older imports.
RESTRICTED_ROLE = OPERATOR_ROLE
BYPASS_ROLES = ALL_ACCESS_ROLES


def _roles(user):
    return set(frappe.get_roles(user))


def is_restricted(user=None):
    user = user or frappe.session.user
    if user == "Administrator":
        return False
    roles = _roles(user)
    if roles & ALL_ACCESS_ROLES:
        return False
    return bool(OPERATOR_ROLE in roles or roles & set(UOM_SUPERVISOR_ROLES))


def is_supervisor(user=None):
    user = user or frappe.session.user
    return user == "Administrator" or bool(_roles(user) & SUPERVISOR_ROLES)


def allowed_uoms(user=None):
    """UOMs the user sees in full as a supervisor; None = every UOM."""
    user = user or frappe.session.user
    if not is_restricted(user):
        return None
    roles = _roles(user)
    return sorted({uom for role, uom in UOM_SUPERVISOR_ROLES.items() if role in roles})


def employee_ids(user=None):
    """Employee records linked to this user (Employee.user_id), cached per request."""
    user = user or frappe.session.user
    cache = frappe.local.__dict__.setdefault("_knit_operator_employees", {})
    if user not in cache:
        cache[user] = frappe.get_all("Employee", filters={"user_id": user}, pluck="name")
    return cache[user]


def _sql_list(values):
    return ", ".join(frappe.db.escape(v) for v in values)


def job_card_condition(user=None, table="`tabJob Card`"):
    """SQL condition on a Job Card table/alias limiting rows to what the user
    may see, or "" when the user is not restricted. Contains no literal "%",
    so callers can run it with %s / %(name)s parameters."""
    user = user or frappe.session.user
    if not is_restricted(user):
        return ""

    parts = []
    uoms = allowed_uoms(user)
    if uoms:
        parts.append(
            f"""{table}.work_order IN (
                SELECT wo_uom.name FROM `tabWork Order` wo_uom
                WHERE wo_uom.stock_uom IN ({_sql_list(uoms)}))"""
        )

    if OPERATOR_ROLE in _roles(user):
        quoted_user = frappe.db.escape('"' + user + '"')
        parts.append(f"INSTR(IFNULL({table}._assign, ''), {quoted_user}) > 0")
        emps = employee_ids(user)
        if emps:
            parts.append(
                f"""{table}.name IN (
                    SELECT jctl.parent FROM `tabJob Card Time Log` jctl
                    WHERE jctl.parenttype = 'Job Card' AND jctl.employee IN ({_sql_list(emps)}))"""
            )

    return "(" + " OR ".join(parts) + ")" if parts else "(1 = 0)"


def work_order_condition(user=None, table="`tabWork Order`"):
    """SQL condition on a Work Order table/alias, or "" when not restricted."""
    user = user or frappe.session.user
    if not is_restricted(user):
        return ""
    parts = []
    uoms = allowed_uoms(user)
    if uoms:
        parts.append(f"{table}.stock_uom IN ({_sql_list(uoms)})")
    if OPERATOR_ROLE in _roles(user):
        jc_cond = job_card_condition(user, table="jc_perm")
        parts.append(
            f"""{table}.name IN (
                SELECT jc_perm.work_order FROM `tabJob Card` jc_perm
                WHERE jc_perm.work_order IS NOT NULL AND {jc_cond})"""
        )
    return "(" + " OR ".join(parts) + ")" if parts else "(1 = 0)"


# ── Job Card hooks ─────────────────────────────────────────────────────────

def get_permission_query_conditions(user=None):
    return job_card_condition(user)


def has_permission(doc, ptype=None, user=None):
    user = user or frappe.session.user
    if not is_restricted(user) or doc.get("__islocal"):
        return True

    uoms = allowed_uoms(user)
    if uoms and doc.get("work_order"):
        if frappe.db.get_value("Work Order", doc.work_order, "stock_uom") in uoms:
            return True

    if OPERATOR_ROLE in _roles(user):
        emps = set(employee_ids(user))
        for row in (doc.get("time_logs") or []) + (doc.get("employee") or []):
            if row.get("employee") and row.employee in emps:
                return True
        assigned = frappe.parse_json(doc.get("_assign")) if doc.get("_assign") else []
        if user in (assigned or []):
            return True
    return False


# ── Work Order hooks ───────────────────────────────────────────────────────

def get_work_order_permission_query_conditions(user=None):
    return work_order_condition(user)


def work_order_has_permission(doc, ptype=None, user=None):
    user = user or frappe.session.user
    if not is_restricted(user) or doc.get("__islocal"):
        return True
    cond = work_order_condition(user, table="wo")
    return bool(frappe.db.sql(
        f"SELECT 1 FROM `tabWork Order` wo WHERE wo.name = %s AND {cond} LIMIT 1",
        (doc.name,),
    ))
