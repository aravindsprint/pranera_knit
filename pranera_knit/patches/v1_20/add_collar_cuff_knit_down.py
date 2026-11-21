"""
pranera_knit/patches/v1_20/add_collar_cuff_knit_down.py

Splits Knit Down Approval into two Knit App pages:

  "knit-down"             renamed "Fabric Knit Down"   (operation KNITTING)
  "collar-cuff-knit-down" new "Collar Cuff Knit Down"  (COLLAR / CUFF KNITTING)

Both save to the same "Knit Down Approval" doctype, so approval, the
approver role and the list stay in one place. This patch adds:

  knit_type        Fabric / Collar Cuff, set from the Work Order's operation
  Collar / cuff    Size, No of Needles, No of Course, Texture, No of Ply,
                   each next to the Work Order's value (width, no_of_needles,
                   no_of_course, no_of_ply). Gauge and Loop Length are shared
                   with fabric.

Dia and GSM stop being mandatory at doctype level (collars/cuffs have none);
knit_down_events.validate_knit_down still requires them for Fabric.
Existing knit downs are all fabric → knit_type = "Fabric".
"""
import frappe

from pranera_knit.patches.v1_10.add_knit_app_page_access import execute as seed_pages

FABRIC_ONLY = "eval:doc.knit_type != 'Collar Cuff'"
FLAT_ONLY = "eval:doc.knit_type == 'Collar Cuff'"

NEW_FIELDS = [
    # (insert after, field)
    ("job_card", {"fieldname": "knit_type", "label": "Knit Type", "fieldtype": "Select",
                  "options": "Fabric\nCollar Cuff", "default": "Fabric", "read_only": 1,
                  "in_list_view": 1, "in_standard_filter": 1}),
    ("loop_length", {"fieldname": "section_flat", "fieldtype": "Section Break",
                     "label": "Collar / Cuff", "depends_on": FLAT_ONLY}),
    ("section_flat", {"fieldname": "required_size", "label": "Required Size", "fieldtype": "Data",
                      "read_only": 1}),
    ("required_size", {"fieldname": "size", "label": "Size", "fieldtype": "Data"}),
    ("size", {"fieldname": "required_needles", "label": "Required No of Needles", "fieldtype": "Int",
              "read_only": 1}),
    ("required_needles", {"fieldname": "no_of_needles", "label": "No of Needles", "fieldtype": "Int"}),
    ("no_of_needles", {"fieldname": "texture", "label": "Texture", "fieldtype": "Data"}),
    ("texture", {"fieldname": "column_break_flat", "fieldtype": "Column Break"}),
    ("column_break_flat", {"fieldname": "required_course", "label": "Required No of Course",
                           "fieldtype": "Int", "read_only": 1}),
    ("required_course", {"fieldname": "no_of_course", "label": "No of Course", "fieldtype": "Int"}),
    ("no_of_course", {"fieldname": "required_ply", "label": "Required No of Ply", "fieldtype": "Int",
                      "read_only": 1}),
    ("required_ply", {"fieldname": "no_of_ply", "label": "No of Ply", "fieldtype": "Int"}),
]


def execute():
    if not frappe.db.exists("DocType", "Knit Down Approval"):
        return
    doc = frappe.get_doc("DocType", "Knit Down Approval")

    for f in doc.fields:
        if f.fieldname in ("dia", "gsm"):
            f.reqd = 0
            f.depends_on = FABRIC_ONLY
        elif f.fieldname in ("required_dia", "required_gsm"):
            f.depends_on = FABRIC_ONLY
        elif f.fieldname == "gauge":
            f.reqd = 0
        elif f.fieldname == "production_item":
            f.label = "Item"
        elif f.fieldname == "item_name":
            f.label = "Item Name"

    existing = {f.fieldname for f in doc.fields}
    for after, field in NEW_FIELDS:
        if field["fieldname"] in existing:
            continue
        idx = next((i for i, f in enumerate(doc.fields) if f.fieldname == after), len(doc.fields) - 1)
        row = doc.append("fields", field)
        doc.fields.remove(row)
        doc.fields.insert(idx + 1, row)
        existing.add(field["fieldname"])
    for i, f in enumerate(doc.fields, start=1):
        f.idx = i
    doc.save(ignore_permissions=True)

    frappe.db.sql("""UPDATE `tabKnit Down Approval` SET knit_type = 'Fabric'
                     WHERE IFNULL(knit_type, '') = ''""")

    # Renames "knit-down" to Fabric Knit Down and adds "collar-cuff-knit-down".
    new_page = not frappe.db.exists("Knit App Page", "collar-cuff-knit-down")
    seed_pages()
    # Start the new page with the same role restriction as the old one.
    if new_page and frappe.db.exists("Knit App Page", "knit-down"):
        roles = [r.role for r in frappe.get_doc("Knit App Page", "knit-down").get("roles") or []]
        if roles:
            page = frappe.get_doc("Knit App Page", "collar-cuff-knit-down")
            for role in roles:
                page.append("roles", {"role": role})
            page.save(ignore_permissions=True)
