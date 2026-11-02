"""
pranera_knit/api/warehouse_query.py
Link-field query for Roll Pick Assignment → Batch Items → Warehouse,
attached by public/js/roll_pick_assignment_warehouse.js.

Replaces the Textiles And Garments app's get_warehouses_for_batch in that
dropdown (which lists only warehouses already holding the row's batch,
from any building) with every NAP warehouse:

  * only leaf, enabled warehouses whose name starts with "NAP"
  * the row's batch qty in each one is the description line, as before
    (same Stock Ledger + Serial and Batch Entry balance)
  * warehouses holding the batch come first (most stock first), then the
    rest of the NAP warehouses alphabetically, so a supervisor can still
    plan a pick from a NAP warehouse the batch hasn't reached yet
"""
import frappe
from frappe.utils import cint, flt

WAREHOUSE_PREFIX = "NAP"


@frappe.whitelist()
def nap_warehouses_for_batch(doctype, txt, searchfield, start, page_len, filters):
    filters = frappe.parse_json(filters) if isinstance(filters, str) else (filters or {})
    batch_no = filters.get("batch") or ""

    rows = frappe.db.sql(
        """
        select w.name, ifnull(b.qty, 0) as qty
        from `tabWarehouse` w
        left join (
            select warehouse, sum(qty) as qty
            from (
                select sle.warehouse as warehouse, sle.actual_qty as qty
                from `tabStock Ledger Entry` sle
                where sle.is_cancelled = 0
                    and sle.docstatus = 1
                    and sle.batch_no = %(batch_no)s
                union all
                select sbe.warehouse as warehouse, sbe.qty as qty
                from `tabSerial and Batch Entry` sbe
                inner join `tabStock Ledger Entry` sle on sle.serial_and_batch_bundle = sbe.parent
                where sle.is_cancelled = 0
                    and sle.docstatus = 1
                    and sbe.batch_no = %(batch_no)s
            ) combined
            group by warehouse
        ) b on b.warehouse = w.name
        where w.name like %(prefix)s
            and w.is_group = 0
            and w.disabled = 0
            and w.name like %(txt)s
        order by (ifnull(b.qty, 0) > 0) desc, ifnull(b.qty, 0) desc, w.name
        limit %(page_len)s offset %(start)s
        """,
        {
            "batch_no": batch_no,
            "prefix": WAREHOUSE_PREFIX + "%",
            "txt": f"%{txt}%" if txt else "%",
            "start": cint(start),
            "page_len": cint(page_len) or 20,
        },
    )
    return [(name, str(flt(qty, 3)) if flt(qty) > 0 else "0") for name, qty in rows]
