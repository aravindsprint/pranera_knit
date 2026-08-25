// Roll Wise Pick List <-> Stock Entry link each other, so Frappe's standard
// "cannot cancel, still linked" guard blocks a plain Cancel on either side.
// This button cancels both together (Stock Entry first, then the Pick
// List) via force_cancel_roll_pick_stock_entry in api/knit.py.
frappe.ui.form.on('Roll Wise Pick List', {
	refresh(frm) {
		if (frm.doc.docstatus !== 1) return

		frm.add_custom_button('Cancel Pick + Stock Entry', () => {
			frappe.confirm(
				`This will cancel both this Pick List and its linked Stock Entry` +
				(frm.doc.stock_entry ? ` (${frm.doc.stock_entry})` : '') +
				`. This cannot be undone. Continue?`,
				() => {
					frappe.call({
						method: 'pranera_knit.api.knit.force_cancel_roll_pick_stock_entry',
						args: { roll_wise_pick_list: frm.doc.name },
						freeze: true,
						freeze_message: 'Cancelling Pick List and Stock Entry...',
					}).then(() => {
						frappe.show_alert({ message: 'Cancelled successfully', indicator: 'green' })
						frm.reload_doc()
					})
				}
			)
		}, __('Actions'))
	},
})
