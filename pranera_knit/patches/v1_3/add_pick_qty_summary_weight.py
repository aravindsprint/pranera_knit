"""
pranera_knit/patches/v1_3/add_pick_qty_summary_weight.py

1. Adds "Total Weight" (total_weight, Float, kg) to the custom child
   doctype "Roll Pick Qty Summary" (created by patches/v1_1), shown next
   to Total Qty in Roll Pick Assignment's "Pick Qty (by UOM)" table.
   The doctype is custom=1, so the field goes on the DocType itself
   rather than through a Custom Field.

2. One-time data fix: Batch Wise Pick Item.weight used to be the summed
   Qty (so Pcs items showed piece counts as weight). Recompute it from
   the summed roll_weight of the matching Roll Wise Pick Item rows —
   the same rule roll_wise_pick_list_events.set_batch_wise_weight now
   applies on save. Batch-transfer picks (no roll rows) are untouched.

3. Backfills total_weight on every existing Roll Pick Assignment's
   summary rows from its submitted pick lists.
"""
import frappe

from pranera_knit.pick_qty_summary import refresh_summary_weight


def execute():
    _add_total_weight_field()
    _fix_batch_wise_weights()
    _backfill_summary_weights()


def _add_total_weight_field():
    if not frappe.db.exists("DocType", "Roll Pick Qty Summary"):
        return
    dt = frappe.get_doc("DocType", "Roll Pick Qty Summary")
    if any(f.fieldname == "total_weight" for f in dt.fields):
        return
    dt.append("fields", {
        "fieldname": "total_weight",
        "label": "Total Weight",
        "fieldtype": "Float",
        "in_list_view": 1,
        "read_only": 1,
        "description": "Picked weight (kg) from submitted Roll Wise Pick Lists",
    })
    dt.save(ignore_permissions=True)
    frappe.clear_cache(doctype="Roll Pick Qty Summary")
    frappe.clear_cache(doctype="Roll Pick Assignment")


def _fix_batch_wise_weights():
    if not frappe.db.has_column("Batch Wise Pick Item", "weight"):
        return
    frappe.db.sql(
        """
        UPDATE `tabBatch Wise Pick Item` b
        JOIN (
            SELECT parent, item_code, warehouse, batch,
                   ROUND(SUM(IFNULL(roll_weight, 0)), 3) AS w
            FROM `tabRoll Wise Pick Item`
            WHERE parenttype = 'Roll Wise Pick List'
            GROUP BY parent, item_code, warehouse, batch
        ) r
          ON  r.parent    = b.parent
          AND r.item_code = b.item_code
          AND r.warehouse = b.warehouse
          AND r.batch     = b.batch
        SET b.weight = r.w
        WHERE b.parenttype = 'Roll Wise Pick List'
          AND ABS(IFNULL(b.weight, 0) - r.w) > 0.005
        """
    )


def _backfill_summary_weights():
    names = frappe.db.sql_list(
        """
        SELECT DISTINCT parent FROM `tabRoll Pick Qty Summary`
        WHERE parenttype = 'Roll Pick Assignment'
        """
    )
    for name in names:
        refresh_summary_weight(name)
