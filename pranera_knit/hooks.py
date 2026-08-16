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
        "logo": "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Crect width='100' height='100' rx='22' fill='%230f6e56'/%3E%3Ccircle cx='30' cy='50' r='12' fill='white'/%3E%3Ccircle cx='70' cy='50' r='12' fill='white'/%3E%3Cpath d='M30 50 Q50 20 70 50 Q50 80 30 50' fill='none' stroke='white' stroke-width='3'/%3E%3C/svg%3E",
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
    # "Page" intentionally excluded: the "knit-app" desk Page already exists
    # in production (created once, back when developer_mode was on). Frappe
    # blocks ANY insert/update of a standard=Yes Page outside developer
    # mode — even a no-op re-sync of an already-identical record — which
    # made `bench migrate` fail on production with "Not in Developer Mode".
    # Since this Page never needs to be created again, simply not fixture-
    # syncing it avoids the check entirely with no functional change; the
    # record itself is untouched and the app keeps working exactly as
    # before. If the Page ever needs to change, edit it directly via the
    # UI with developer_mode on temporarily, rather than through fixtures.
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
    {
        "doctype": "Server Script",
        "filters": [["name", "in", [
            "knit_submit_roll_packing_list_v2",
            "knit-save-roll-data",
        ]]],
    },
]

override_whitelisted_methods = {
    "knit_is_first_job_card": "pranera_knit.api.yarn_consumption.is_first_job_card",
    "knit_snapshot_before_consumption": "pranera_knit.api.yarn_consumption.snapshot_before_consumption",
    "knit_save_before_consumption": "pranera_knit.api.yarn_consumption.save_before_consumption",
    "knit_get_yarn_consumption": "pranera_knit.api.yarn_consumption.get_yarn_consumption",
    "knit_apply_actual_bom": "pranera_knit.api.yarn_consumption.apply_actual_bom",
}
