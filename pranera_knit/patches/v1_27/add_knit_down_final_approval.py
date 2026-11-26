"""
pranera_knit/patches/v1_27/add_knit_down_final_approval.py

Two-level knit down approval (rules in knit_down_events).

Knit Down Approver Location (Knit Down Settings → Approver Locations):
  level   Select "1" / "2", default "1". Level 1 = first approval at the
          unit (as before). A location with any level-2 row needs a second
          (final) approval by one of its level-2 approvers.

Knit Down Approval:
  status  gains "Pending Final Approval" (level 1 approved, waiting for
          level 2).
  first_approved_by / first_approved_on / first_approver_remarks
          the level-1 approval, kept once the final decision is made.
"""
import frappe

FINAL = "Pending Final Approval"

LEVEL_FIELD = {"fieldname": "level", "label": "Approval Level", "fieldtype": "Select",
               "options": "1\n2", "default": "1", "in_list_view": 1, "columns": 1,
               "description": "1 = first approval at the unit. 2 = final approval: at a location "
                              "with any level-2 approver, a level-1 approval waits for one of them."}

FIRST_FIELDS = [
    {"fieldname": "section_first_approval", "fieldtype": "Section Break", "label": "First Approval",
     "collapsible": 1, "depends_on": "eval:doc.first_approved_by"},
    {"fieldname": "first_approved_by", "label": "First Approved By", "fieldtype": "Link",
     "options": "User", "read_only": 1, "no_copy": 1},
    {"fieldname": "first_approved_on", "label": "First Approved On", "fieldtype": "Datetime",
     "read_only": 1, "no_copy": 1},
    {"fieldname": "column_break_first_approval", "fieldtype": "Column Break"},
    {"fieldname": "first_approver_remarks", "label": "First Approver Remarks", "fieldtype": "Small Text",
     "read_only": 1, "no_copy": 1},
]


def _insert_after(doc, fields, after):
    existing = {f.fieldname for f in doc.fields}
    new = [f for f in fields if f["fieldname"] not in existing]
    if not new:
        return False
    rows = []
    for f in new:
        row = doc.append("fields", f)
        doc.fields.remove(row)
        rows.append(row)
    pos = next((i for i, f in enumerate(doc.fields) if f.fieldname == after), len(doc.fields) - 1)
    doc.fields[pos + 1:pos + 1] = rows
    for i, f in enumerate(doc.fields, start=1):
        f.idx = i
    return True


def execute():
    if frappe.db.exists("DocType", "Knit Down Approver Location"):
        doc = frappe.get_doc("DocType", "Knit Down Approver Location")
        if _insert_after(doc, [LEVEL_FIELD], "location"):
            doc.save(ignore_permissions=True)
        frappe.db.sql("UPDATE `tabKnit Down Approver Location` SET level = '1' WHERE IFNULL(level, '') = ''")

    if frappe.db.exists("DocType", "Knit Down Approval"):
        doc = frappe.get_doc("DocType", "Knit Down Approval")
        changed = _insert_after(doc, FIRST_FIELDS, "approver_remarks")
        status = next(f for f in doc.fields if f.fieldname == "status")
        options = [o for o in (status.options or "").split("\n") if o]
        if FINAL not in options:
            options.insert(options.index("Pending") + 1 if "Pending" in options else 0, FINAL)
            status.options = "\n".join(options)
            changed = True
        if changed:
            doc.save(ignore_permissions=True)
