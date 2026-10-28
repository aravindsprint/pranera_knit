"""Whitelisted access check for the Knit App menus / router (see pranera_knit/page_access.py)."""
import frappe

from pranera_knit.page_access import denied_pages


@frappe.whitelist()
def get_page_access():
    return {"user": frappe.session.user, "denied": denied_pages()}
