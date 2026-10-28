"""
pranera_knit/page_access.py
Role-based access to Knit App pages.

Each app page has a "Knit App Page" record in Desk (/app/knit-app-page),
named by its page key, with a Roles field (child table "Knit App Page Role").

  * No roles on a page        → everyone who can log in to the app sees it
                                 (the default, so nothing changes on deploy).
  * One or more roles          → only users with at least one of them.
  * System Manager             → always sees every page.

PAGES must match frontend/src/pages.js (same keys). Sub-screens follow
their parent page there (e.g. Create Roll / Create QI follow "home").

This controls what the app shows and lets a user open. It is not a data
permission: the documents behind each page are still governed by the
normal Frappe role permissions.
"""
import frappe

PAGES = [
    # (key, title, route, section)
    ("work-order", "Work Order", "/knit-app/work-order", "Production"),
    ("home", "Job Cards", "/knit-app/home", "Production"),
    ("roll-wise-pick-list", "Roll-wise Pick List", "/knit-app/roll-wise-pick-list", "Production"),
    ("my-pick-orders", "My Pick Orders", "/knit-app/my-pick-orders", "Production"),
    ("outward-request", "Outward Request", "/knit-app/outward-request", "Production"),
    ("vehicle-gate-entry", "Vehicle Gate Entry", "/knit-app/vehicle-gate-entry", "Production"),
    ("create-rolls", "Create Rolls", "/knit-app/create-rolls", "Production Data"),
    ("rolls", "Rolls", "/knit-app/rolls", "Production Data"),
    ("stock", "Stock", "/knit-app/stock", "Production Data"),
    ("stock-entry", "Stock Entry", "/knit-app/stock-entry", "Production Data"),
    ("production-report", "Production Report", "/knit-app/production-report", "Reports"),
    ("process-loss", "Process Loss", "/knit-app/process-loss", "Reports"),
    ("dashboard", "Dashboard", "/knit-app/dashboard", "Analytics"),
]
BYPASS_ROLES = {"System Manager"}


def denied_pages(user=None):
    """Page keys this user may NOT open. Empty list = everything allowed."""
    user = user or frappe.session.user
    roles = set(frappe.get_roles(user))
    if roles & BYPASS_ROLES or not frappe.db.exists("DocType", "Knit App Page"):
        return []
    required = {}
    for r in frappe.get_all(
        "Knit App Page Role",
        filters={"parenttype": "Knit App Page"},
        fields=["parent", "role"],
    ):
        if r.role:
            required.setdefault(r.parent, set()).add(r.role)
    return sorted(page for page, need in required.items() if not (need & roles))
