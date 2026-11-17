"""
Create the "Fabric Knitting Supervisor" and "Collar Cuff Knitting Supervisor"
roles (see job_card_permissions.py: Fabric sees Kgs work orders / job cards,
Collar Cuff sees Pcs ones).

Each new role gets the same extra access the existing "Knitting Supervisor"
role has outside Job Card / Work Order: its Custom DocPerm rows (Roll, Roll
Pick Assignment, ...) and the Reports / Pages it is allowed on. Job Card and
Work Order access itself comes from the users' other roles (e.g.
Manufacturing User), exactly as it does for Knitting Supervisor today.

No user is moved: assign the new roles in Desk and remove "Knitting
Supervisor" from users who should be limited to one side. Re-running is safe.
"""
import frappe

SOURCE_ROLE = "Knitting Supervisor"
NEW_ROLES = ("Fabric Knitting Supervisor", "Collar Cuff Knitting Supervisor")
PERM_FIELDS = (
    "permlevel", "if_owner", "select", "read", "write", "create", "delete",
    "submit", "cancel", "amend", "report", "export", "import", "share",
    "print", "email",
)


def execute():
    for role in NEW_ROLES:
        if not frappe.db.exists("Role", role):
            frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(
                ignore_permissions=True
            )
        _copy_docperms(role)
        _copy_has_roles(role)
    frappe.clear_cache()


def _copy_docperms(role):
    for src in frappe.get_all("Custom DocPerm", filters={"role": SOURCE_ROLE},
                              fields=["parent", *PERM_FIELDS]):
        if frappe.db.exists("Custom DocPerm",
                            {"parent": src.parent, "role": role, "permlevel": src.permlevel}):
            continue
        doc = frappe.new_doc("Custom DocPerm")
        doc.parent = src.parent
        doc.parenttype = "DocType"
        doc.parentfield = "permissions"
        doc.role = role
        for f in PERM_FIELDS:
            doc.set(f, src.get(f))
        doc.insert(ignore_permissions=True)


def _copy_has_roles(role):
    for src in frappe.get_all("Has Role",
                              filters={"role": SOURCE_ROLE, "parenttype": ["in", ["Report", "Page"]]},
                              fields=["parent", "parenttype"]):
        if frappe.db.exists("Has Role", {"parent": src.parent, "parenttype": src.parenttype, "role": role}):
            continue
        parent = frappe.get_doc(src.parenttype, src.parent)
        parent.append("roles", {"role": role})
        parent.flags.ignore_permissions = True
        try:
            parent.save()
        except Exception:
            # e.g. a standard Report/Page outside developer mode: add the row directly.
            frappe.get_doc({
                "doctype": "Has Role", "parent": src.parent, "parenttype": src.parenttype,
                "parentfield": "roles", "role": role,
            }).insert(ignore_permissions=True)
