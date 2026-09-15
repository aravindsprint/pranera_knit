"""
pranera_knit/patches/v1_2/add_subcontract_pick_type.py

Extends Roll Pick Assignment — owned by the Textiles And Garments app,
not this one — via Custom Fields + a Property Setter only. Same
non-invasive pattern as patches/v1_1/add_pick_qty_summary.py, so this
app never forks another app's DocType source.

Adds a new "To Subcontracting Order" pick_type:
  1. Property Setter appending "To Subcontracting Order" to the
     pick_type Select field's options.
  2. Two Custom Fields, both visible only when
     pick_type == "To Subcontracting Order":
       - "purchase_order" (Link -> Purchase Order) — picked first.
       - "subcontracting_order" (Link -> Subcontracting Order) — the
         form JS (public/js/roll_pick_assignment.js) filters this by
         purchase_order, then on selection fetches that Subcontracting
         Order's Job Worker Warehouse (supplier_warehouse) into
         target_warehouse.
     Fieldnames are unprefixed (no "custom_") to match this doctype's
     existing convention (work_order, sales_order, ...) and because
     api/pick_order.py's create_pick_order() / _resolve_document_name()
     and api/knit.py's create_roll_picking_entry() read/write them
     directly as doc.purchase_order / doc.subcontracting_order.
"""
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def execute():
    _add_pick_type_option()
    _add_custom_fields()


def _add_pick_type_option():
    current = frappe.db.get_value(
        "Property Setter",
        {"doc_type": "Roll Pick Assignment", "field_name": "pick_type", "property": "options"},
        "value",
    ) or frappe.db.get_value("DocField", {"parent": "Roll Pick Assignment", "fieldname": "pick_type"}, "options")

    options = [o for o in (current or "").split("\n") if o]
    if "To Subcontracting Order" not in options:
        options.append("To Subcontracting Order")

    make_property_setter(
        "Roll Pick Assignment", "pick_type", "options",
        "\n".join(options), "Text",
    )


def _add_custom_fields():
    create_custom_fields({
        "Roll Pick Assignment": [
            {
                "fieldname": "purchase_order",
                "label": "Purchase Order",
                "fieldtype": "Link",
                "options": "Purchase Order",
                "insert_after": "sales_order",
                "depends_on": "eval:doc.pick_type=='To Subcontracting Order'",
                "mandatory_depends_on": "eval:doc.pick_type=='To Subcontracting Order'",
                "description": "Subcontracting Purchase Order this pick is fulfilling",
            },
            {
                "fieldname": "subcontracting_order",
                "label": "Subcontracting Order",
                "fieldtype": "Link",
                "options": "Subcontracting Order",
                "insert_after": "purchase_order",
                "depends_on": "eval:doc.pick_type=='To Subcontracting Order'",
                "mandatory_depends_on": "eval:doc.pick_type=='To Subcontracting Order'",
                "description": (
                    "Filtered to the selected Purchase Order. Target Warehouse "
                    "is auto-set from this Subcontracting Order's Job Worker "
                    "Warehouse."
                ),
            },
        ],
    }, ignore_validate=True, update=True)
