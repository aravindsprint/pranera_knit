import frappe

def boot_session(bootinfo):
    """Pass ERPNext session info to the Vue app on load."""
    bootinfo.knit_app = {
        "user": frappe.session.user,
        "user_fullname": frappe.utils.get_fullname(frappe.session.user),
    }
