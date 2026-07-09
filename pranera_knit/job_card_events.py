# Copyright (c) 2025, Pranera Services & Solutions
# Job Card document event handlers for Pranera Knit
# Registered via hooks.py → doc_events

import frappe
from frappe import _


def on_before_cancel(doc, method=None):
    """
    Before a Job Card is cancelled:
    1. Block cancellation if any linked Quality Inspection is REJECTED
       (needs a QC decision first).
    2. Auto-cancel ACCEPTED/Pending submitted Quality Inspections so the
       Job Card can proceed with cancellation.
    """
    linked = frappe.get_all(
        "Quality Inspection",
        filters={
            "reference_type": "Job Card",
            "reference_name": doc.name,
            "docstatus": 1,
        },
        fields=["name", "status"],
    )

    rejected = [q["name"] for q in linked if q["status"] == "Rejected"]

    if rejected:
        frappe.throw(
            _(
                "Cannot cancel Job Card {0}: linked Quality Inspection(s) {1} are "
                "REJECTED. A Quality user must review and cancel these manually before "
                "this Job Card can be cancelled."
            ).format(doc.name, ", ".join(rejected))
        )

    # Auto-cancel non-rejected submitted QIs
    for q in linked:
        qi = frappe.get_doc("Quality Inspection", q["name"])
        qi.flags.ignore_permissions = True
        qi.add_comment(
            "Comment",
            f"Auto-cancelled because Job Card {doc.name} was cancelled "
            f"(by {frappe.session.user}).",
        )
        qi.cancel()


def on_after_cancel(doc, method=None):
    """
    After a Job Card is cancelled:
    Automatically reassign all linked Rolls to the amended Job Card (if one exists).
    This ensures roll data is preserved across the cancel → amend workflow.
    """
    rolls = frappe.get_all(
        "Roll",
        filters={"job_card": doc.name},
        fields=["name"],
    )

    if not rolls:
        return

    # Find the amended version of this Job Card
    amended = frappe.get_all(
        "Job Card",
        filters={
            "amended_from": doc.name,
            "docstatus": ["!=", 2],
        },
        fields=["name"],
        order_by="creation desc",
        limit=1,
    )

    if amended:
        amended_name = amended[0]["name"]
        roll_names = [r["name"] for r in rolls]
        for roll_name in roll_names:
            frappe.db.set_value(
                "Roll", roll_name, "job_card", amended_name, update_modified=False
            )
        frappe.db.commit()
        frappe.logger("pranera_knit").info(
            f"Knit: Reassigned {len(roll_names)} rolls from {doc.name} to {amended_name}"
        )
    else:
        frappe.logger("pranera_knit").warning(
            f"Knit: Job Card {doc.name} cancelled but no amendment found — "
            f"{len(rolls)} rolls still linked to cancelled JC"
        )


def on_after_insert(doc, method=None):
    """
    After a Job Card is inserted:
    When an AMENDED Job Card is created, auto-create a DRAFT Quality Inspection,
    pre-filled (including readings) from the QI of the original Job Card.
    """
    if not doc.amended_from:
        return

    # Check if a QI already exists for this new JC
    already = frappe.get_all(
        "Quality Inspection",
        filters={
            "reference_type": "Job Card",
            "reference_name": doc.name,
            "docstatus": ["<", 2],
        },
        limit=1,
    )
    if already:
        return

    # Find the most recent QI from the original Job Card
    src = frappe.get_all(
        "Quality Inspection",
        filters={"reference_type": "Job Card", "reference_name": doc.amended_from},
        fields=["name"],
        order_by="creation desc",
        limit=1,
    )
    if not src:
        return

    old = frappe.get_doc("Quality Inspection", src[0]["name"])

    reading_fields = [
        "specification", "status", "numeric", "manual_inspection",
        "min_value", "max_value", "formula_based_criteria", "acceptance_formula",
        "parameter_group", "reading_value",
        "reading_1", "reading_2", "reading_3", "reading_4", "reading_5",
        "reading_6", "reading_7", "reading_8", "reading_9", "reading_10",
    ]
    rows = [{f: r.get(f) for f in reading_fields} for r in old.readings]

    new_qi = frappe.get_doc({
        "doctype":                     "Quality Inspection",
        "inspection_type":             old.get("inspection_type"),
        "reference_type":              "Job Card",
        "reference_name":              doc.name,
        "item_code":                   old.get("item_code"),
        "item_name":                   old.get("item_name"),
        "description":                 old.get("description"),
        "sample_size":                 old.get("sample_size"),
        "quality_inspection_template": old.get("quality_inspection_template"),
        "batch_no":                    old.get("batch_no"),
        "custom_roll":                 old.get("custom_roll"),
        "custom_knitting_machine_no":  old.get("custom_knitting_machine_no"),
        "inspected_by":                old.get("inspected_by"),
        "company":                     old.get("company"),
        "letter_head":                 old.get("letter_head"),
        "remarks":                     old.get("remarks"),
        "status":                      old.get("status"),
        "readings":                    rows,
    })
    new_qi.flags.ignore_permissions = True
    new_qi.insert()
    new_qi.add_comment(
        "Comment",
        f"Draft auto-created from {old.name} for amended Job Card {doc.name}. "
        "Readings copied from the previous inspection — verify before submitting.",
    )
