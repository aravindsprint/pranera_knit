"""
pranera_knit/patches/v1_25/add_app_settings_page.py

Knit App "Settings" page (api/app_settings.py): Outward Request settings,
Knit Down settings, unit GPS coordinates and page access in one place.
Seeds Knit App Page "app-settings" restricted to System Manager (the API
checks System Manager on every call as well).
"""
import frappe

from pranera_knit.patches.v1_10.add_knit_app_page_access import execute as seed_pages


def execute():
    seed_pages()
    if not frappe.db.exists("Knit App Page", "app-settings"):
        return
    page = frappe.get_doc("Knit App Page", "app-settings")
    if not page.get("roles"):
        page.append("roles", {"role": "System Manager"})
        page.save(ignore_permissions=True)
