"""Whitelisted access check for the Knit App menus / router (see pranera_knit/page_access.py)."""
import frappe

from pranera_knit.job_card_permissions import allowed_uoms, is_supervisor
from pranera_knit.page_access import denied_pages


@frappe.whitelist()
def get_page_access():
    return {
        "user": frappe.session.user,
        "denied": denied_pages(),
        # Role-based: shows the 👤 Assign Employee button on Job Cards.
        "is_supervisor": is_supervisor(),
        # UOMs a scoped supervisor sees (["Kgs"] / ["Pcs"]); null = all.
        "uoms": allowed_uoms(),
    }
