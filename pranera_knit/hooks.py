from . import __version__ as app_version

app_name        = "pranera_knit"
app_title       = "Pranera Knit"
app_publisher   = "Pranera Services & Solutions"
app_description = "Knitting production floor app for ERPNext"
app_email       = "admin@pranera.in"
app_license     = "MIT"
app_version     = "1.0.0"

add_to_apps_screen = [
    {
        "name": "pranera_knit",
        "logo": "data:image/svg+xml,%3Csvg%20xmlns=%22http://www.w3.org/2000/svg%22%20viewBox=%220%200%20100%20100%22%3E%3Crect%20width=%22100%22%20height=%22100%22%20rx=%2222%22%20fill=%22%230f6e56%22/%3E%3Cline%20x1=%2220%22%20y1=%2218%22%20x2=%2256%22%20y2=%2254%22%20stroke=%22white%22%20stroke-width=%225.5%22%20stroke-linecap=%22round%22/%3E%3Ccircle%20cx=%2220%22%20cy=%2218%22%20r=%225%22%20fill=%22white%22/%3E%3Crect%20x=%2253%22%20y=%2251%22%20width=%2230%22%20height=%227%22%20rx=%223.5%22%20fill=%22white%22%20transform=%22rotate(45%2068%2054)%22/%3E%3Cline%20x1=%2280%22%20y1=%2218%22%20x2=%2244%22%20y2=%2254%22%20stroke=%22white%22%20stroke-width=%225.5%22%20stroke-linecap=%22round%22/%3E%3Ccircle%20cx=%2280%22%20cy=%2218%22%20r=%225%22%20fill=%22white%22/%3E%3Crect%20x=%2217%22%20y=%2251%22%20width=%2230%22%20height=%227%22%20rx=%223.5%22%20fill=%22white%22%20transform=%22rotate(-45%2032%2054)%22/%3E%3Cpath%20d=%22M35%2060%20Q50%2044%2065%2060%20Q57%2072%2050%2068%20Q43%2072%2035%2060Z%22%20fill=%22none%22%20stroke=%22white%22%20stroke-width=%223.5%22%20stroke-linejoin=%22round%22%20opacity=%220.9%22/%3E%3Cpath%20d=%22M35%2060%20Q24%2068%2022%2080%22%20fill=%22none%22%20stroke=%22white%22%20stroke-width=%223.5%22%20stroke-linecap=%22round%22%20opacity=%220.9%22/%3E%3Cpath%20d=%22M65%2060%20Q76%2068%2078%2080%22%20fill=%22none%22%20stroke=%22white%22%20stroke-width=%223.5%22%20stroke-linecap=%22round%22%20opacity=%220.9%22/%3E%3C/svg%3E",
        "title": "Knit App",
        "route": "/knit-app",
    }
]

website_route_rules = [
    {"from_route": "/knit-app/<path:app_path>", "to_route": "knit-app"},
]

# ── Document event hooks ──────────────────────────────────────────────────────
# These replace the three DB Server Scripts:
#   knit-jobcard-qi-cancel   (Before Cancel) — auto-cancel QI + rejected guard
#   knit-jobcard-on-cancel   (After Cancel)  — reassign rolls to amended JC
#   knit-jobcard-qi-recreate (After Insert)  — auto-create draft QI on amendment
# Keep those Server Scripts disabled (not deleted) as a reference backup.
doc_events = {
    "Job Card": {
        "before_cancel": "pranera_knit.job_card_events.on_before_cancel",
        "after_cancel":  "pranera_knit.job_card_events.on_after_cancel",
        "after_insert":  "pranera_knit.job_card_events.on_after_insert",
    }
}

# ── Job Card visibility restriction ───────────────────────────────────────────
# Users with the "Job Card Operator" role only see Job Cards assigned to them
# (via standard Frappe "Assign To"). System Manager, Knitting Supervisor and
# Administrator bypass this restriction. See job_card_permissions.py.
permission_query_conditions = {
    "Job Card": "pranera_knit.job_card_permissions.get_permission_query_conditions",
}

has_permission = {
    "Job Card": "pranera_knit.job_card_permissions.has_permission",
}

fixtures = [
    {"doctype": "Page",      "filters": [["module", "in", ["Knit Module"]]]},
    {"doctype": "Workspace", "filters": [["module", "in", ["Knit Module"]]]},
    {
        "doctype": "Custom Field",
        "filters": [
            ["dt", "=", "Work Order Item"],
            ["fieldname", "in", [
                "custom_before_qty",
                "custom_after_qty",
                "custom_actual_consumed_qty",
            ]],
        ],
    },
]

override_whitelisted_methods = {
    "knit_is_first_job_card": "pranera_knit.api.yarn_consumption.is_first_job_card",
    "knit_snapshot_before_consumption": "pranera_knit.api.yarn_consumption.snapshot_before_consumption",
    "knit_save_before_consumption": "pranera_knit.api.yarn_consumption.save_before_consumption",
    "knit_get_yarn_consumption": "pranera_knit.api.yarn_consumption.get_yarn_consumption",
    "knit_apply_actual_bom": "pranera_knit.api.yarn_consumption.apply_actual_bom",
}
