// pranera_knit/public/js/roll_pick_assignment_warehouse.js
//
// Injected into "Roll Pick Assignment" (owned by Textiles And Garments) via
// the doctype_js hook. Batch Items → Warehouse dropdown lists NAP
// warehouses only, with the row's batch qty in each (see
// pranera_knit/api/warehouse_query.py). Runs after the doctype's own
// refresh, so it replaces that app's get_warehouses_for_batch query.

function pk_set_nap_warehouse_query(frm) {
	frm.set_query("warehouse", "batch_items", function (doc, cdt, cdn) {
		const row = locals[cdt][cdn];
		return {
			query: "pranera_knit.api.warehouse_query.nap_warehouses_for_batch",
			filters: { batch: row.batch || "" },
		};
	});
}

frappe.ui.form.on("Roll Pick Assignment", {
	onload(frm) {
		pk_set_nap_warehouse_query(frm);
	},
	refresh(frm) {
		pk_set_nap_warehouse_query(frm);
	},
});
