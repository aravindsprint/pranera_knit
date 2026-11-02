# pranera_knit/pranera_knit/process_loss.py
#
# Auto-create a "Work Order Process Loss" (PL/.####) when a Work Order is
# completed, submit it, and email the report (HTML table + PDF) to recipients.
#
# Trigger: Stock Entry (Manufacture) on_submit -> background job after commit.
#
# Calculation mirrors existing PL docs (e.g. PL/4949):
#   sent      = Material Transfer for Manufacture + extra issues (Material
#               Transfer into the WO's WIP) per raw item
#   return    = Material Transfer out of the WO's WIP warehouse per raw item
#   received  = raw qty consumed in Manufacture entries per raw item
#   loss      = sent - return - received
#   loss %    = loss / sent * 100

import frappe
from frappe.utils import flt, today

LOSS_DOCTYPE = "Work Order Process Loss"


# ---------------------------------------------------------------------------
# Hook entry point
# ---------------------------------------------------------------------------
def on_stock_entry_submit(doc, method=None):
    if doc.purpose != "Manufacture" or not doc.work_order:
        return

    frappe.enqueue(
        "pranera_knit.process_loss.create_and_email",
        queue="short",
        work_order=doc.work_order,
        enqueue_after_commit=True,  # never block / roll back the Manufacture entry
        job_id=f"process_loss::{doc.work_order}",
        deduplicate=True,
    )


# ---------------------------------------------------------------------------
# Background job
# ---------------------------------------------------------------------------
def create_and_email(work_order, force=False):
    try:
        wo = frappe.get_doc("Work Order", work_order)
        if wo.docstatus != 1:
            return
        if wo.status != "Completed" and not force:
            return  # partial manufacture - wait for the final entry

        if not force and _already_has_process_loss(work_order):
            return

        pl = _build_process_loss(wo)
        if not pl.work_order_process_loss_details:
            frappe.log_error(
                title=f"Process Loss skipped: {work_order}",
                message="No material transfer / consumption rows found for this Work Order.",
            )
            return

        pl.flags.ignore_permissions = True
        pl.insert()
        pl.submit()

        _send_email(pl, wo)
    except Exception:
        frappe.log_error(title=f"Process Loss auto-create failed: {work_order}")
        raise


def _already_has_process_loss(work_order):
    return frappe.db.exists(
        "Work Orders",
        {"parenttype": LOSS_DOCTYPE, "work_order": work_order, "docstatus": ("<", 2)},
    )


# ---------------------------------------------------------------------------
# Build the document
# ---------------------------------------------------------------------------
def _build_process_loss(wo):
    sent = _get_sent(wo)
    returned = _get_returned(wo)
    consumed = _get_consumed(wo)
    produced = _get_produced(wo)

    required = {d.item_code: flt(d.required_qty) for d in wo.required_items}

    pl = frappe.new_doc(LOSS_DOCTYPE)
    pl.naming_series = "PL/.####"
    pl.posting_date = today()
    pl.append("work_orders", {"work_order": wo.name})

    for r in sent:
        pl.append("work_order_sent_details", {
            "work_order": wo.name,
            "item_code": r.item_code,
            "wo_item_code": wo.production_item,
            "wo_qty": wo.qty,
            "sent_qty": flt(r.qty, 3),
            "stock_entry": r.stock_entry,
            "uom": r.uom,
        })

    for r in returned:
        pl.append("work_order_return_details", {
            "work_order": wo.name,
            "item_code": r.item_code,
            "wo_item_code": wo.production_item,
            "wo_qty": wo.qty,
            "return_qty": flt(r.qty, 3),
            "stock_entry": r.stock_entry,
            "uom": r.uom,
        })

    for r in produced:
        pl.append("work_order_received_details", {
            "work_order": wo.name,
            "item_code": r.item_code,
            "wo_qty": wo.qty,
            "received_qty": flt(r.qty, 3),
            "uom": r.uom,
            "stock_entry": r.stock_entry,
        })

    # Summary per raw item
    totals = {}
    for key, rows in (("sent", sent), ("ret", returned), ("rec", consumed)):
        for r in rows:
            t = totals.setdefault(r.item_code, {"sent": 0, "ret": 0, "rec": 0, "uom": r.uom})
            t[key] += flt(r.qty)

    for item_code, t in totals.items():
        sent_qty = flt(t["sent"], 3)
        ret_qty = flt(t["ret"], 3)
        rec_qty = flt(t["rec"], 3)
        loss = flt(sent_qty - ret_qty - rec_qty, 3)
        pct = flt(loss / sent_qty * 100, 2) if sent_qty else 0

        pl.append("work_order_process_loss_details", {
            "work_order": wo.name,
            "item_code": item_code,
            "uom": t["uom"],
            "wo_qty": required.get(item_code, 0),
            "sent_qty": sent_qty,
            "return_qty": ret_qty,
            "received_qty": rec_qty,
            "process_loss_qty": loss,
            "process_loss_percentage": pct,
        })

    return pl


def _get_sent(wo):
    return frappe.db.sql(
        """
        select sed.item_code, sum(sed.transfer_qty) qty, sed.stock_uom uom, se.name stock_entry
        from `tabStock Entry` se
        join `tabStock Entry Detail` sed on sed.parent = se.name
        where se.work_order = %(wo)s and se.docstatus = 1
          and (
            se.purpose = 'Material Transfer for Manufacture'
            -- extra yarn issues (YEI/...) moved into the WIP against this WO
            or (se.purpose = 'Material Transfer' and sed.t_warehouse = %(wip)s)
          )
        group by se.name, sed.item_code, sed.stock_uom
        order by se.posting_date, se.name
        """,
        {"wo": wo.name, "wip": wo.wip_warehouse},
        as_dict=True,
    )


def _get_returned(wo):
    return frappe.db.sql(
        """
        select sed.item_code, sum(sed.transfer_qty) qty, sed.stock_uom uom, se.name stock_entry
        from `tabStock Entry` se
        join `tabStock Entry Detail` sed on sed.parent = se.name
        where se.work_order = %(wo)s and se.docstatus = 1
          and se.purpose = 'Material Transfer'
          and sed.s_warehouse = %(wip)s
        group by se.name, sed.item_code, sed.stock_uom
        order by se.posting_date, se.name
        """,
        {"wo": wo.name, "wip": wo.wip_warehouse},
        as_dict=True,
    )


def _get_consumed(wo):
    return frappe.db.sql(
        """
        select sed.item_code, sum(sed.transfer_qty) qty, sed.stock_uom uom, se.name stock_entry
        from `tabStock Entry` se
        join `tabStock Entry Detail` sed on sed.parent = se.name
        where se.work_order = %(wo)s and se.docstatus = 1
          and se.purpose = 'Manufacture'
          and ifnull(sed.s_warehouse, '') != ''
        group by se.name, sed.item_code, sed.stock_uom
        """,
        {"wo": wo.name},
        as_dict=True,
    )


def _get_produced(wo):
    return frappe.db.sql(
        """
        select sed.item_code, sum(sed.transfer_qty) qty, sed.stock_uom uom, se.name stock_entry
        from `tabStock Entry` se
        join `tabStock Entry Detail` sed on sed.parent = se.name
        where se.work_order = %(wo)s and se.docstatus = 1
          and se.purpose = 'Manufacture'
          and sed.is_finished_item = 1
        group by se.name, sed.item_code, sed.stock_uom
        order by se.posting_date, se.name
        """,
        {"wo": wo.name},
        as_dict=True,
    )


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------
def _get_recipients(wo):
    recipients = list(frappe.conf.get("process_loss_report_recipients") or [])
    if frappe.conf.get("process_loss_email_wo_owner") and wo.owner not in recipients:
        recipients.append(wo.owner)
    return recipients


def _send_email(pl, wo):
    recipients = _get_recipients(wo)
    if not recipients:
        frappe.log_error(
            title="Process Loss email not sent",
            message=f"{pl.name}: set 'process_loss_report_recipients' in site_config.json",
        )
        return

    rows_html = ""
    tot_sent = tot_ret = tot_rec = tot_loss = 0
    for d in pl.work_order_process_loss_details:
        tot_sent += flt(d.sent_qty)
        tot_ret += flt(d.return_qty)
        tot_rec += flt(d.received_qty)
        tot_loss += flt(d.process_loss_qty)
        rows_html += f"""
        <tr>
            <td style="{TD}">{d.item_code}</td>
            <td style="{TD}">{d.uom or ''}</td>
            <td style="{TDR}">{flt(d.wo_qty, 3)}</td>
            <td style="{TDR}">{flt(d.sent_qty, 3)}</td>
            <td style="{TDR}">{flt(d.return_qty, 3)}</td>
            <td style="{TDR}">{flt(d.received_qty, 3)}</td>
            <td style="{TDR}">{flt(d.process_loss_qty, 3)}</td>
            <td style="{TDR}"><b>{flt(d.process_loss_percentage, 2)}%</b></td>
        </tr>"""

    tot_pct = flt(tot_loss / tot_sent * 100, 2) if tot_sent else 0
    pl_link = frappe.utils.get_url_to_form(LOSS_DOCTYPE, pl.name)
    wo_link = frappe.utils.get_url_to_form("Work Order", wo.name)

    message = f"""
    <p>Process loss report for Work Order <a href="{wo_link}">{wo.name}</a>
    ({wo.production_item}, produced {flt(wo.produced_qty, 3)} of {flt(wo.qty, 3)} {wo.stock_uom}).</p>
    <table style="border-collapse:collapse;font-size:13px">
        <tr style="background:#f3f3f3">
            <th style="{TD}">Item</th><th style="{TD}">UOM</th>
            <th style="{TDR}">WO Qty</th><th style="{TDR}">Sent</th>
            <th style="{TDR}">Return</th><th style="{TDR}">Received</th>
            <th style="{TDR}">Loss Qty</th><th style="{TDR}">Loss %</th>
        </tr>
        {rows_html}
        <tr style="background:#f3f3f3;font-weight:bold">
            <td style="{TD}" colspan="3">Total</td>
            <td style="{TDR}">{flt(tot_sent, 3)}</td>
            <td style="{TDR}">{flt(tot_ret, 3)}</td>
            <td style="{TDR}">{flt(tot_rec, 3)}</td>
            <td style="{TDR}">{flt(tot_loss, 3)}</td>
            <td style="{TDR}">{tot_pct}%</td>
        </tr>
    </table>
    <p>Open in ERPNext: <a href="{pl_link}">{pl.name}</a></p>
    """

    attachments = [
        frappe.attach_print(
            LOSS_DOCTYPE,
            pl.name,
            file_name=pl.name.replace("/", "-"),
            print_format=frappe.conf.get("process_loss_print_format"),  # None = default
        )
    ]

    frappe.sendmail(
        recipients=recipients,
        subject=f"Process Loss {tot_pct}% - {wo.name} ({wo.production_item})",
        message=message,
        attachments=attachments,
        reference_doctype=LOSS_DOCTYPE,
        reference_name=pl.name,
    )


TD = "border:1px solid #ccc;padding:4px 8px;text-align:left"
TDR = "border:1px solid #ccc;padding:4px 8px;text-align:right"
