"""
pranera_knit/api/warehouse_query.py
Link-field query for Roll Pick Assignment → Batch Items → Warehouse,
attached by public/js/roll_pick_assignment_warehouse.js.

Replaces the Textiles And Garments app's get_warehouses_for_batch in that
dropdown (which lists only warehouses already holding the row's batch, from
any building) with the warehouses of the logged-in user's building:

  * leaf, enabled warehouses whose Building (Warehouse.building) is the
    user's Assigned Building (User.assigned_building)
  * users with no Assigned Building, and System Managers, see every
    warehouse — nobody is left with an empty dropdown
  * the row's batch qty in each warehouse is the description line, as
    before (same Stock Ledger + Serial and Batch Entry balance)
  * warehouses holding the batch come first (most stock first), then the
    rest alphabetically, so a supervisor can still plan a pick from a
    warehouse the batch hasn't reached yet
"""
import frappe
from frappe.utils import cint, flt

BYPASS_ROLES = {"System Manager"}


def user_building(user=None):
    """The user's Assigned Building, or None when they see every building."""
    user = user or frappe.session.user
    if BYPASS_ROLES & set(frappe.get_roles(user)):
        return None
    return frappe.db.get_value("User", user, "assigned_building") or None


def _warehouse_batch_rows(batch_no, building=None, txt="", start=0, page_len=0):
    """[(warehouse, batch qty)] for leaf, enabled warehouses — of `building`
    when given — warehouses holding the batch first (most stock first), then
    the rest alphabetically. page_len 0 = no limit."""
    limit = "limit %(page_len)s offset %(start)s" if cint(page_len) else ""
    return frappe.db.sql(
        f"""
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
        where w.is_group = 0
            and w.disabled = 0
            and (%(building)s = '' or w.building = %(building)s)
            and w.name like %(txt)s
        order by (ifnull(b.qty, 0) > 0) desc, ifnull(b.qty, 0) desc, w.name
        {limit}
        """,
        {
            "batch_no": batch_no or "",
            "building": building or "",
            "txt": f"%{txt}%" if txt else "%",
            "start": cint(start),
            "page_len": cint(page_len),
        },
    )


@frappe.whitelist()
def building_warehouses_for_batch(doctype, txt, searchfield, start, page_len, filters):
    filters = frappe.parse_json(filters) if isinstance(filters, str) else (filters or {})
    rows = _warehouse_batch_rows(
        filters.get("batch"), user_building(), txt, start, cint(page_len) or 20
    )
    return [(name, str(flt(qty, 3)) if flt(qty) > 0 else "0") for name, qty in rows]


@frappe.whitelist()
def get_batch_pick_info(batch):
    """Knit App Create Pick Order → one Batch Items row: the batch's item and
    stock UOM (Roll Pick Batch Item fetches the same on save), plus the
    user's building warehouses with this batch's qty, stock-holding first."""
    info = frappe.db.get_value("Batch", batch, ["item", "stock_uom"], as_dict=True)
    if not info:
        frappe.throw(frappe._("Batch {0} not found").format(batch))
    building = user_building()
    return {
        "batch": batch,
        "item": info.item,
        "stock_uom": info.stock_uom,
        "building": building,
        "warehouses": [
            {"warehouse": name, "qty": flt(qty, 3)}
            for name, qty in _warehouse_batch_rows(batch, building)
        ],
    }


@frappe.whitelist()
def get_pick_order_warehouses():
    """Knit App Create Pick Order warehouse lists: `source` = leaf, enabled
    warehouses of the user's building; `target` = every leaf, enabled
    warehouse (a pick can land in another building, e.g. a subcontractor's
    job-work warehouse)."""
    building = user_building()
    all_wh = frappe.get_all(
        "Warehouse",
        filters={"is_group": 0, "disabled": 0},
        fields=["name", "building"],
        order_by="name asc",
        limit_page_length=0,
    )
    source = [w.name for w in all_wh if not building or w.building == building]
    return {"building": building, "source": source, "target": [w.name for w in all_wh]}
