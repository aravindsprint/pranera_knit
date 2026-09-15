// pranera_knit/public/js/roll_pick_assignment.js
//
// Injected into "Roll Pick Assignment" — owned by the Textiles And
// Garments app, not this one — via the doctype_js hook in hooks.py.
// Same non-invasive pattern as roll_wise_pick_list.js. Handles the
// "To Subcontracting Order" pick_type added by
// patches/v1_2/add_subcontract_pick_type.py:
//
//   1. Subcontracting Order is filtered to the selected Purchase Order
//      (and only submitted ones).
//   2. Picking a Subcontracting Order fetches its Job Worker Warehouse
//      (supplier_warehouse) and sets it as this form's Target Warehouse.
//   3. Switching Purchase Order clears a stale Subcontracting Order
//      selection; switching pick_type away from "To Subcontracting
//      Order" clears both, so leftover values can't silently carry
//      into an unrelated pick.

frappe.ui.form.on("Roll Pick Assignment", {
	onload(frm) {
		set_subcontracting_order_query(frm);
	},

	refresh(frm) {
		set_subcontracting_order_query(frm);
	},

	pick_type(frm) {
		if (frm.doc.pick_type !== "To Subcontracting Order") {
			frm.set_value("purchase_order", "");
			frm.set_value("subcontracting_order", "");
		}
	},

	purchase_order(frm) {
		set_subcontracting_order_query(frm);
		if (frm.doc.subcontracting_order) {
			frm.set_value("subcontracting_order", "");
		}
	},

	subcontracting_order(frm) {
		if (!frm.doc.subcontracting_order) {
			return;
		}
		frappe.db.get_value(
			"Subcontracting Order",
			frm.doc.subcontracting_order,
			"supplier_warehouse"
		).then(({ message }) => {
			const warehouse = message && message.supplier_warehouse;
			if (warehouse) {
				frm.set_value("target_warehouse", warehouse);
			} else {
				frappe.show_alert({
					message: __("Selected Subcontracting Order has no Job Worker Warehouse set"),
					indicator: "orange",
				});
			}
		});
	},
});

function set_subcontracting_order_query(frm) {
	frm.set_query("subcontracting_order", () => ({
		filters: {
			purchase_order: frm.doc.purchase_order || "",
			docstatus: 1,
		},
	}));
}
