// NAP In Transit Ageing: goods sent from NAP to an In Transit warehouse,
// how much has been inwarded since and how long the rest has been waiting.
frappe.query_reports["NAP In Transit Ageing"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("Dispatched From"),
			fieldtype: "Date",
			description: __("Leave empty for all history"),
		},
		{
			fieldname: "as_on_date",
			label: __("As On Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "in_transit_warehouse",
			label: __("In Transit Warehouse"),
			fieldtype: "Link",
			options: "Warehouse",
			get_query: () => ({ filters: { is_group: 0, name: ["like", "%transit%"] } }),
		},
		{
			fieldname: "item_code",
			label: __("Item"),
			fieldtype: "Link",
			options: "Item",
		},
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: ["All", "Pending in Transit", "Pending", "Partly Inwarded", "Fully Inwarded"].join("\n"),
			default: "All",
		},
		{
			fieldname: "ageing_ranges",
			label: __("Ageing Ranges (days)"),
			fieldtype: "Data",
			default: "7,15,30,60",
		},
	],

	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (!data) return value;
		if (column.fieldname === "pending_qty" && data.pending_qty > 0) {
			return `<span style="color: var(--red-600); font-weight: 600">${value}</span>`;
		}
		if (column.fieldname === "status") {
			const color = { Pending: "red", "Partly Inwarded": "orange", Inwarded: "green" }[data.status] || "gray";
			return `<span class="indicator-pill ${color}">${value}</span>`;
		}
		if (column.fieldname === "age" && data.age > 15) {
			return `<span style="color: var(--red-600); font-weight: 600">${value}</span>`;
		}
		return value;
	},
};
