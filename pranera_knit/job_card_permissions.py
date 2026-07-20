# Copyright (c) 2026, Pranera Services & Solutions
# Restricts Job Card visibility to only records assigned to the user
# (via the standard Frappe "Assign To" -> _assign field), for users
# holding the "Job Card Operator" role. System Manager and Knitting
# Supervisor (and Administrator) bypass this restriction entirely.

import frappe

RESTRICTED_ROLE = "Job Card Operator"
BYPASS_ROLES = {"System Manager", "Knitting Supervisor"}


def get_permission_query_conditions(user=None):
    """
    Called by Frappe for list/report views on Job Card.
    Returns a SQL condition string to append to the WHERE clause.
    """
    user = user or frappe.session.user
    if user == "Administrator":
        return ""

    roles = set(frappe.get_roles(user))
    if RESTRICTED_ROLE not in roles or roles & BYPASS_ROLES:
        return ""

    return f"""(`tabJob Card`._assign like '%{user}%')"""


def has_permission(doc, user=None):
    """
    Called by Frappe when a specific Job Card document is opened directly
    (not just from a list). Must independently enforce the same rule,
    since permission_query_conditions only filters list/report queries.
    """
    user = user or frappe.session.user
    if user == "Administrator":
        return True

    roles = set(frappe.get_roles(user))
    if RESTRICTED_ROLE not in roles or roles & BYPASS_ROLES:
        return True

    assigned = frappe.parse_json(doc._assign) if doc._assign else []
    return user in assigned
