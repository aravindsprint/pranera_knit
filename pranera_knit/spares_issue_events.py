"""
pranera_knit/spares_issue_events.py

Stock Entry before_insert: the Material Issue that ERPNext creates while
submitting an Asset Repair from the knit app's Needle / Sinker Issue page
(pranera_knit/api/spares_issue.py) would otherwise take the first naming
series (ST/<yy>/). Give it the store's Material Issue series MI/<yy>/
instead — only for repairs raised from the app (frappe.flags flag), and
only when that series is one of the Stock Entry naming_series options.
"""
import frappe
from frappe.utils import nowdate


def set_material_issue_series(doc, method=None):
    if not frappe.flags.get("knit_spares_issue"):
        return
    if not doc.get("asset_repair") or doc.purpose != "Material Issue":
        return
    series = f"MI/{nowdate()[2:4]}/"
    options = (frappe.get_meta("Stock Entry").get_field("naming_series").options or "").split("\n")
    if series in options:
        doc.naming_series = series
