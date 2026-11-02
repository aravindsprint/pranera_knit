"""
pranera_knit/patches/v1_12/add_spare_life_tracking.py

Needle / sinker restriction per machine + life tracking (pranera_knit/spares_life.py):

1. Child DocType "Workstation Spare Item" and the Table field
   Workstation.custom_spare_items ("Spare Items (Needles / Sinkers)").
2. Asset Repair.custom_issue_type: "Broken / Bent Replacement" or "Full Set Change".
3. Role "Needle Life Alert" (who gets the life alerts) assigned to ALERT_USERS.
4. Seeds each knitting machine's Spare Items from the needle audit of 30-10-2026
   (machine → needle / sinker items, full-set qty = machine capacity split equally
   across tracks; interlock dial and cylinder each = machine capacity). SJ / IL rows
   track life with max 55,000 kg; collar FK rows don't (broken-needle replacement
   only). Machines that already have rows are left alone, so re-running is safe.

Life tracking starts once a row has "Last Full Set Change" — set automatically by
a Full Set Change issue in the Knit App, or entered by the knitting team in Desk.
"""
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

MODULE = "Knit Module"
CHILD_DT = "Workstation Spare Item"
ROLE = "Needle Life Alert"
ALERT_USERS = ["seetharam@praneraservices.com", "sakravarthi@pss.com"]
PREFIX = "SPARES/KNIT MAC "
MAX_KG = 55000

SEED = {
    "FK01/6014/PL/KH": [["NEEDLE/007", 1680, 0]],
    "FK02/6014/PL/KH": [["NEEDLE/007", 1680, 0]],
    "FK03/6014/PL/KH": [["NEEDLE/007", 1680, 0]],
    "FK04/6014/PL/KH": [["NEEDLE/007", 1680, 0]],
    "FK05/6014/PL/KH": [["NEEDLE/007", 1680, 0]],
    "FK06/6014/PL/KH": [["NEEDLE/007", 1680, 0]],
    "FK07/6014/PL/KH": [["NEEDLE/007", 840, 0], ["NEEDLE/028", 840, 0]],
    "FK08/6014/PL/KH": [["NEEDLE/007", 1260, 0], ["NEEDLE/028", 420, 0]],
    "FK09/8014/PL/KH": [["NEEDLE/007", 1680, 0]],
    "FK10/8014/PL/KH": [["NEEDLE/007", 1680, 0]],
    "FK11/4014/SJ/KH": [["NEEDLE/007", 1260, 0], ["NEEDLE/028", 420, 0]],
    "FK12/4014/SJ/KH": [["NEEDLE/007", 1260, 0], ["NEEDLE/028", 420, 0]],
    "FK13/6014/SJ/KH": [["NEEDLE/007", 1260, 0], ["NEEDLE/028", 420, 0]],
    "FK14/6014/SJ/KH": [["NEEDLE/007", 1260, 0], ["NEEDLE/028", 420, 0]],
    "FK15/6014/SJ/KH": [["NEEDLE/007", 1260, 0], ["NEEDLE/028", 420, 0]],
    "FK16/6014/SJ/KH": [["NEEDLE/007", 1260, 0], ["NEEDLE/028", 420, 0]],
    "FK17/6014/SJ/KH": [["NEEDLE/007", 1260, 0], ["NEEDLE/028", 420, 0]],
    "FK18/6014/SJ/KH": [["NEEDLE/007", 1260, 0], ["NEEDLE/028", 420, 0]],
    "FK19/6014/SJ/KH": [["NEEDLE/007", 840, 0], ["NEEDLE/028", 280, 0]],
    "FK20/6014/SJ/KH": [["NEEDLE/007", 840, 0], ["NEEDLE/028", 280, 0]],
    "FK21/6014/SJ/KH": [["NEEDLE/007", 2240, 0]],
    "FK22/6014/SJ/KH": [["NEEDLE/007", 2240, 0]],
    "IL01/3428/FK": [["NEEDLE/023", 1494, 1], ["NEEDLE/024", 1494, 1], ["NEEDLE/019", 747, 1], ["NEEDLE/020", 747, 1], ["NEEDLE/021", 747, 1], ["NEEDLE/022", 747, 1]],
    "IL02/3432/FK": [["NEEDLE/013", 1740, 1], ["NEEDLE/014", 1740, 1], ["NEEDLE/011", 870, 1], ["NEEDLE/012", 870, 1], ["NEEDLE/041", 870, 1], ["NEEDLE/042", 870, 1]],
    "IL03/3028/FK": [["NEEDLE/023", 1320, 1], ["NEEDLE/024", 1320, 1], ["NEEDLE/019", 660, 1], ["NEEDLE/020", 660, 1], ["NEEDLE/021", 660, 1], ["NEEDLE/022", 660, 1]],
    "IL04/3028/FK": [["NEEDLE/023", 1320, 1], ["NEEDLE/024", 1320, 1], ["NEEDLE/019", 660, 1], ["NEEDLE/020", 660, 1], ["NEEDLE/021", 660, 1], ["NEEDLE/022", 660, 1]],
    "SJ01/2828/PL": [["NEEDLE/001", 615, 1], ["NEEDLE/002", 615, 1], ["NEEDLE/015", 615, 1], ["NEEDLE/016", 615, 1]],
    "SJ02/2624/TR": [["NEEDLE/035", 972, 1], ["NEEDLE/036", 972, 1]],
    "SJ03/2624/TR": [["NEEDLE/031", 972, 1], ["NEEDLE/032", 972, 1]],
    "SJ04/2828/FK": [["NEEDLE/017", 1230, 1], ["NEEDLE/018", 1230, 1], ["SINKER/002", 2460, 1]],
    "SJ05/2828/FK": [["NEEDLE/008", 820, 1], ["NEEDLE/010", 820, 1], ["NEEDLE/051", 820, 1], ["SINKER/002", 2460, 1]],
    "SJ06/2828/FK": [["NEEDLE/017", 1230, 1], ["NEEDLE/018", 1230, 1], ["SINKER/002", 2460, 1]],
    "SJ07/2828/UT": [["NEEDLE/043", 824, 1], ["NEEDLE/044", 824, 1], ["NEEDLE/045", 824, 1], ["SINKER/004", 2472, 1]],
    "SJ08/3028/UT": [["NEEDLE/043", 880, 1], ["NEEDLE/044", 880, 1], ["NEEDLE/045", 880, 1], ["SINKER/004", 2640, 1]],
    "SJ09/3224/UT": [["NEEDLE/039", 1188, 1], ["NEEDLE/040", 1188, 1], ["SINKER/004", 2376, 1]],
    "SJ10/3428/UT": [["NEEDLE/048", 1000, 1], ["NEEDLE/049", 1000, 1], ["NEEDLE/050", 1000, 1], ["SINKER/004", 3000, 1]],
    "SJ11/3432/JG": [["NEEDLE/046", 1704, 1], ["NEEDLE/047", 1704, 1], ["SINKER/005", 3408, 1]],
    "SJ12/3026/JG": [["NEEDLE/001", 615, 1], ["NEEDLE/002", 615, 1], ["NEEDLE/015", 615, 1], ["NEEDLE/016", 615, 1], ["SINKER/007", 2460, 1]],
    "SJ13/3026/JG": [["NEEDLE/001", 615, 1], ["NEEDLE/002", 615, 1], ["NEEDLE/015", 615, 1], ["NEEDLE/016", 615, 1], ["SINKER/007", 2460, 1]],
    "SJ14/3428/FK": [["NEEDLE/008", 992, 1], ["NEEDLE/010", 992, 1], ["NEEDLE/051", 992, 1], ["SINKER/002", 2976, 1]],
    "SJ15/3428/FK": [["NEEDLE/008", 992, 1], ["NEEDLE/010", 992, 1], ["NEEDLE/051", 992, 1], ["SINKER/002", 2976, 1]],
}


def execute():
    _child_doctype()
    _custom_fields()
    _role()
    _seed()


def _child_doctype():
    if frappe.db.exists("DocType", CHILD_DT):
        return
    frappe.get_doc({
        "doctype": "DocType", "name": CHILD_DT, "module": MODULE, "custom": 1,
        "istable": 1, "editable_grid": 1,
        "fields": [
            {"fieldname": "item_code", "label": "Needle / Sinker", "fieldtype": "Link", "options": "Item",
             "reqd": 1, "in_list_view": 1, "columns": 3},
            {"fieldname": "item_name", "label": "Item Name", "fieldtype": "Data", "read_only": 1,
             "fetch_from": "item_code.item_name"},
            {"fieldname": "set_qty", "label": "Full Set Qty", "fieldtype": "Int", "in_list_view": 1,
             "columns": 1, "description": "Pieces of this item in one full set on this machine"},
            {"fieldname": "track_life", "label": "Track Life", "fieldtype": "Check", "in_list_view": 1,
             "columns": 1, "description": "Alert when production since the last full set change nears Max Production"},
            {"fieldname": "max_production", "label": "Max Production (Kg)", "fieldtype": "Float",
             "default": str(MAX_KG), "in_list_view": 1, "columns": 2,
             "depends_on": "eval:doc.track_life"},
            {"fieldname": "last_full_set_on", "label": "Last Full Set Change", "fieldtype": "Datetime",
             "in_list_view": 1, "columns": 2, "depends_on": "eval:doc.track_life",
             "description": "Life is counted from this date. Set automatically by a Full Set Change in the Knit App"},
            {"fieldname": "column_break_life", "fieldtype": "Column Break"},
            {"fieldname": "last_full_set_repair", "label": "Full Set Change (Asset Repair)", "fieldtype": "Link",
             "options": "Asset Repair", "read_only": 1},
            {"fieldname": "production_since", "label": "Produced Since (Kg)", "fieldtype": "Float",
             "read_only": 1, "in_list_view": 1, "columns": 1},
            {"fieldname": "alert_level", "label": "Alert Sent", "fieldtype": "Select",
             "options": "\nWarning\nMax", "read_only": 1},
        ],
    }).insert(ignore_permissions=True)


def _custom_fields():
    create_custom_fields({
        "Workstation": [
            {"fieldname": "custom_spare_items_section", "label": "Needles / Sinkers", "fieldtype": "Section Break",
             "insert_after": "warehouse", "collapsible": 1},
            {"fieldname": "custom_spare_items", "label": "Spare Items (Needles / Sinkers)", "fieldtype": "Table",
             "options": CHILD_DT, "insert_after": "custom_spare_items_section",
             "description": "Only these needles / sinkers can be issued to this machine from the Knit App."},
        ],
        "Asset Repair": [
            {"fieldname": "custom_issue_type", "label": "Needle Issue Type", "fieldtype": "Select",
             "options": "\nBroken / Bent Replacement\nFull Set Change", "insert_after": "asset_name",
             "in_standard_filter": 1},
        ],
    }, ignore_validate=True)


def _role():
    if not frappe.db.exists("Role", ROLE):
        frappe.get_doc({"doctype": "Role", "role_name": ROLE, "desk_access": 1}).insert(ignore_permissions=True)
    for user in ALERT_USERS:
        if not frappe.db.exists("User", user):
            continue
        u = frappe.get_doc("User", user)
        if ROLE not in [r.role for r in u.roles]:
            u.append("roles", {"role": ROLE})
            u.save(ignore_permissions=True)


def _seed():
    for ws, rows in SEED.items():
        if not frappe.db.exists("Workstation", ws):
            continue
        if frappe.db.exists(CHILD_DT, {"parent": ws, "parenttype": "Workstation"}):
            continue
        doc = frappe.get_doc("Workstation", ws)
        for code, set_qty, track in rows:
            item = PREFIX + code
            if not frappe.db.exists("Item", item):
                continue
            doc.append("custom_spare_items", {
                "item_code": item, "set_qty": set_qty, "track_life": track,
                "max_production": MAX_KG if track else 0,
            })
        doc.flags.ignore_permissions = True
        doc.flags.ignore_mandatory = True
        doc.save()
