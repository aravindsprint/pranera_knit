"""
pranera_knit/patches/v1_10/add_knit_app_page_access.py

Creates the DocTypes behind role-based page access (pranera_knit/page_access.py):

  "Knit App Page Role"  child table: role (Link → Role)
  "Knit App Page"       one record per app page, named by page key, with a
                        Roles (Table MultiSelect) field. Empty = open to all.

and seeds one "Knit App Page" per entry in page_access.PAGES (no roles),
so access only changes once an admin sets roles in Desk → Knit App Page.
Re-running adds records for any new pages and leaves existing roles alone.
"""
import frappe

from pranera_knit.page_access import PAGES

MODULE = "Knit Module"


def execute():
    if not frappe.db.exists("DocType", "Knit App Page Role"):
        frappe.get_doc({
            "doctype": "DocType", "name": "Knit App Page Role", "module": MODULE,
            "custom": 1, "istable": 1, "editable_grid": 1,
            "fields": [{"fieldname": "role", "label": "Role", "fieldtype": "Link",
                        "options": "Role", "reqd": 1, "in_list_view": 1}],
        }).insert(ignore_permissions=True)

    if not frappe.db.exists("DocType", "Knit App Page"):
        frappe.get_doc({
            "doctype": "DocType", "name": "Knit App Page", "module": MODULE, "custom": 1,
            "autoname": "field:page_key", "naming_rule": "By fieldname",
            "title_field": "page_title", "show_title_field_in_link": 1,
            "sort_field": "idx_order", "sort_order": "ASC", "track_changes": 1,
            "fields": [
                {"fieldname": "page_title", "label": "Page", "fieldtype": "Data",
                 "reqd": 1, "in_list_view": 1, "bold": 1},
                {"fieldname": "page_key", "label": "Page Key", "fieldtype": "Data",
                 "reqd": 1, "unique": 1, "read_only": 1},
                {"fieldname": "column_break_1", "fieldtype": "Column Break"},
                {"fieldname": "section", "label": "Menu Section", "fieldtype": "Data", "read_only": 1,
                 "in_list_view": 1},
                {"fieldname": "route", "label": "Route", "fieldtype": "Data", "read_only": 1},
                {"fieldname": "idx_order", "label": "Menu Order", "fieldtype": "Int", "read_only": 1,
                 "hidden": 1},
                {"fieldname": "section_roles", "fieldtype": "Section Break", "label": "Access"},
                {"fieldname": "roles", "label": "Roles", "fieldtype": "Table MultiSelect",
                 "options": "Knit App Page Role", "in_list_view": 1,
                 "description": "Only users with at least one of these roles see and can open this "
                                "page in the Knit App. Leave empty to allow everyone. "
                                "System Managers always have access."},
            ],
            "permissions": [
                {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1},
            ],
        }).insert(ignore_permissions=True)

    for order, (key, title, route, section) in enumerate(PAGES, start=1):
        if frappe.db.exists("Knit App Page", key):
            frappe.db.set_value("Knit App Page", key,
                                {"page_title": title, "route": route, "section": section, "idx_order": order},
                                update_modified=False)
            continue
        frappe.get_doc({
            "doctype": "Knit App Page", "page_key": key, "page_title": title,
            "route": route, "section": section, "idx_order": order,
        }).insert(ignore_permissions=True)
