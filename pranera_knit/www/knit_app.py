import json
import os

import frappe

no_cache = 1
no_breadcrumbs = 1
no_sitemap = 1

ASSET_URL = "/assets/pranera_knit/knit_app/"


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/knit-app"
        raise frappe.Redirect
    context.csrf_token = frappe.sessions.get_csrf_token()
    context.no_cache = 1
    context.update(get_entry_assets())


def get_entry_assets():
    """URLs of the current build's entry script and stylesheets, read from
    the Vite manifest (frontend/vite.config.js: build.manifest).

    The page must load the entry under exactly the URL the lazy page chunks
    import it by (`../index-<hash>.js`), with no query string. A different
    URL for the same file (e.g. the old "index.js?v=...") makes the browser
    run the app twice and breaks navigation to every lazily-loaded page.
    Hashed filenames also replace the old ?v= cache-busting."""
    manifest_path = frappe.get_app_path("pranera_knit", "public", "knit_app", ".vite", "manifest.json")
    try:
        with open(manifest_path) as f:
            manifest = json.load(f)
        entry = next(v for v in manifest.values() if v.get("isEntry"))
        return {
            "entry_js": ASSET_URL + entry["file"],
            "entry_css": [ASSET_URL + c for c in entry.get("css", [])],
        }
    except (OSError, ValueError, StopIteration, KeyError):
        # Pre-manifest build: fall back to the old fixed names.
        return {"entry_js": ASSET_URL + "index.js", "entry_css": [ASSET_URL + "index.css"]}
