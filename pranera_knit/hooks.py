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

# Injects a form script into the "Roll Wise Pick List" doctype, which
# belongs to a different app — doctype_js works regardless of which app
# owns the doctype. Adds the "Cancel Pick + Stock Entry" button.
doctype_js = {
    "Roll Wise Pick List": "public/js/roll_wise_pick_list.js",
}

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
    },
    # Keeps each Roll's `warehouse` field in sync with where it actually
    # is after a Roll Wise Pick List transfer — scoped to only the Stock
    # Entries that app creates (see roll_wise_pick_list_events.py).
    "Stock Entry": {
        "on_submit": [
            "pranera_knit.roll_wise_pick_list_events.on_stock_entry_submit",
            "pranera_knit.outward_request_events.on_stock_entry_change",
        ],
        "on_cancel": [
            "pranera_knit.roll_wise_pick_list_events.on_stock_entry_cancel",
            "pranera_knit.outward_request_events.on_stock_entry_change",
        ],
    },
    # Roll Pick Assignment is owned by the Textiles And Garments app, not
    # this one (see patches/v1_1/add_pick_qty_summary.py) — a doc_event is
    # how this app reaches into a doctype it doesn't own, same as the
    # Stock Entry hook above. Recomputes the per-UOM pick_qty_summary
    # table (and the pick_qty grand total) from batch_items on every save.
    "Roll Pick Assignment": {
        "validate": "pranera_knit.pick_qty_summary.set_pick_qty_summary",
        # Outward Request status tracking (see outward_request_events.py).
        "on_submit": [
            "pranera_knit.outward_request_events.on_roll_pick_assignment_change",
            "pranera_knit.push.on_roll_pick_assignment_submit",
        ],
        "on_cancel": "pranera_knit.outward_request_events.on_roll_pick_assignment_change",
        "on_update_after_submit": "pranera_knit.outward_request_events.on_roll_pick_assignment_change",
    },
    # Roll Wise Pick List is likewise owned by the Textiles And Garments
    # app — keeps the "weight" Custom Field on batch_wise_pick_item rows
    # in sync with the summed roll_weight of the matching Roll Wise Pick
    # Item rows (grouped by Item Code + Warehouse + Batch).
    # on_submit / on_cancel also refresh the linked Roll Pick Assignment's
    # Pick Qty (by UOM) Total Weight column (see pick_qty_summary.py).
    "Roll Wise Pick List": {
        "validate": "pranera_knit.roll_wise_pick_list_events.set_batch_wise_weight",
        "on_submit": [
            "pranera_knit.pick_qty_summary.refresh_from_pick_list",
            "pranera_knit.outward_request_events.on_roll_wise_pick_list_change",
        ],
        "on_cancel": [
            "pranera_knit.pick_qty_summary.refresh_from_pick_list",
            "pranera_knit.outward_request_events.on_roll_wise_pick_list_change",
        ],
    },
    # Outward Request — app-owned (patches/v1_5/add_outward_request.py).
    # Status is driven by the pick chain via the hooks above.
    "Outward Request": {
        "validate": "pranera_knit.outward_request_events.validate_outward_request",
        "on_trash": "pranera_knit.outward_request_events.on_trash_outward_request",
        "after_insert": "pranera_knit.push.on_outward_request_insert",
    },
    # Vehicle Gate Entry — app-owned (patches/v1_6/add_vehicle_gate_entry.py).
    "Vehicle Gate Entry": {
        "validate": "pranera_knit.vehicle_gate_entry_events.validate_vehicle_gate_entry",
        "on_update": "pranera_knit.push.on_vehicle_gate_entry_update",
    },
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
            [
                "name", "in", [
                    "Work Order Item-custom_before_qty",
                    "Work Order Item-custom_after_qty",
                    "Work Order Item-custom_actual_consumed_qty",
                ],
            ],
        ],
    },
    {
        "doctype": "Server Script",
        "filters": [["name", "in", [
            "knit_submit_roll_packing_list_v2",
            "knit-save-roll-data",
        ]]],
    },
    # Generic worker role for the Roll Pick Assignment flow — deliberately
    # not "Knitting X" named, since the same pick/scan/tolerance procedure
    # is meant to be reused for Dyeing, Stentering, and any other
    # operation that needs the same "supervisor sets a target weight,
    # worker scans until within tolerance" pattern. One shared role means
    # a worker moving between departments doesn't need a different role
    # per department just to use this feature.
    {"doctype": "Role", "filters": [["name", "in", ["Roll Picker"]]]},
]

override_whitelisted_methods = {
    "knit_is_first_job_card": "pranera_knit.api.yarn_consumption.is_first_job_card",
    "knit_snapshot_before_consumption": "pranera_knit.api.yarn_consumption.snapshot_before_consumption",
    "knit_save_before_consumption": "pranera_knit.api.yarn_consumption.save_before_consumption",
    "knit_get_yarn_consumption": "pranera_knit.api.yarn_consumption.get_yarn_consumption",
    "knit_apply_actual_bom": "pranera_knit.api.yarn_consumption.apply_actual_bom",
    # Replaces the "knit-save-roll-data" Server Script: same behaviour, but
    # refuses to overwrite a roll that belongs to a different job card.
    "knit_save_roll_data": "pranera_knit.api.knit.save_roll_data",
}
