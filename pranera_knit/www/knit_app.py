import frappe

no_cache = 1
no_breadcrumbs = 1
no_sitemap = 1

def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/knit-app"
        raise frappe.Redirect
    context.csrf_token = frappe.sessions.get_csrf_token()
    context.no_cache = 1
