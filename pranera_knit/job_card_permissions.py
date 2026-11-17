# Copyright (c) 2026, Pranera Services & Solutions
"""
Row-level visibility of Job Cards and Work Orders by knitting role.

  Role                               Sees
  ---------------------------------  ----------------------------------------
  System Manager, Knitting Supervisor everything (Administrator too)
  Fabric Knitting Supervisor         knitting (GKF...) Work Orders in Kgs, and
                                     their Job Cards on SJ / IL machines
  Collar Cuff Knitting Supervisor    knitting (GKF...) Work Orders in Pcs, and
                                     their Job Cards on FK machines
  Job Card Operator                  Job Cards where their Employee
                                     (Employee.user_id = the user) is in the
                                     Time Logs table (or the Employee
                                     multi-select, or Assign To), and the
                                     Work Orders of those Job Cards

A user with several of these roles sees the union. Users with none of them
are not restricted here (normal role permissions only).

The UOM is the Work Order's stock_uom and "knitting" means its production
item starts with GKF (dyeing / process work orders - DKF, SKF, ... - are not
shown to the knitting supervisors); a Job Card follows its Work Order.

Used by the permission_query_conditions / has_permission hooks (Desk lists,
reports, /api/resource, frappe.get_list) and by the knit-app APIs that query
with raw SQL (knit_get_work_orders, Machine Status) via job_card_condition().
It is a filter on top of role permissions: it never grants extra access.
"""

import re

import frappe

OPERATOR_ROLE = "Job Card Operator"
ALL_ACCESS_ROLES = {"System Manager", "Knitting Supervisor"}
UOM_SUPERVISOR_ROLES = {
    "Fabric Knitting Supervisor": "Kgs",
    "Collar Cuff Knitting Supervisor": "Pcs",
}
# Production item prefix of knitting work orders (greige fabric, collar, cuff).
KNITTING_ITEM_PREFIX = "GKF"
# Knitting machines per supervisor UOM (workstation name prefix + digit).
# Job cards of GKF work orders on other workstations (Sub Contracting, the old
# "KNITTING01 - WORK IN PROGRESS", dyeing machines) are not shown to them.
UOM_MACHINE_REGEX = {"Kgs": "^(SJ|IL)[0-9]", "Pcs": "^FK[0-9]"}

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
    # frappe.local is a werkzeug Local: it has no __dict__, so keep the
    # per-request cache as a plain attribute on it.
    cache = getattr(frappe.local, "knit_operator_employees", None)
    if cache is None:
        cache = {}
        frappe.local.knit_operator_employees = cache
    if user not in cache:
        cache[user] = frappe.get_all("Employee", filters={"user_id": user}, pluck="name")
    return cache[user]


def _sql_list(values):
    return ", ".join(frappe.db.escape(v) for v in values)


def _knitting_wo_sql(table, uoms):
    """Work Order rows that are knitting (GKF...) in one of the UOMs.
    LEFT() instead of LIKE 'GKF%': no literal "%" in the SQL."""
    prefix = frappe.db.escape(KNITTING_ITEM_PREFIX)
    return (f"({table}.stock_uom IN ({_sql_list(uoms)}) "
            f"AND LEFT({table}.production_item, {len(KNITTING_ITEM_PREFIX)}) = {prefix})")


def job_card_condition(user=None, table="`tabJob Card`"):
    """SQL condition on a Job Card table/alias limiting rows to what the user
    may see, or "" when the user is not restricted. Contains no literal "%",
    so callers can run it with %s / %(name)s parameters."""
    user = user or frappe.session.user
    if not is_restricted(user):
        return ""

    parts = []
    for uom in allowed_uoms(user) or []:
        parts.append(
            f"""({table}.workstation REGEXP {frappe.db.escape(UOM_MACHINE_REGEX[uom])}
                AND {table}.work_order IN (
                    SELECT wo_uom.name FROM `tabWork Order` wo_uom
                    WHERE {_knitting_wo_sql("wo_uom", [uom])}))"""
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
        parts.append(_knitting_wo_sql(table, uoms))
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
        wo = frappe.db.get_value("Work Order", doc.work_order, ["stock_uom", "production_item"], as_dict=True)
        if (wo and wo.stock_uom in uoms
                and (wo.production_item or "").startswith(KNITTING_ITEM_PREFIX)
                and re.match(UOM_MACHINE_REGEX[wo.stock_uom], doc.get("workstation") or "")):
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
