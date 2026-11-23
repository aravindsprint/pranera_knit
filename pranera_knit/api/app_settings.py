"""
pranera_knit/api/app_settings.py
Whitelisted methods behind the Knit App "Settings" page (System Manager only).

One place in the app for what otherwise lives in Desk:

  Outward Request   Outward Request Settings: order deadline (day before),
                    require approval, daily Kgs limit, approvers
  Knit Down         Knit Down Settings: approver locations, Require GPS,
                    GPS range (metres)
  Unit GPS          Location → Latitude / Longitude for every location used
                    on Work Orders or in the approver table ("use my
                    current location" on the page)
  Page Access       Knit App Page → roles allowed to open each page

Every method checks System Manager on the server; the page's menu entry is
also restricted (patches/v1_25).
"""
import frappe
from frappe import _
from frappe.utils import cint, flt, get_time

ADMIN_ROLE = "System Manager"
OR_SETTINGS = "Outward Request Settings"
KD_SETTINGS = "Knit Down Settings"


def _require_admin():
    if ADMIN_ROLE not in frappe.get_roles():
        frappe.throw(_("Only a System Manager can change the Knit App settings"), frappe.PermissionError)


def _full_names(users):
    users = [u for u in set(users) if u]
    if not users:
        return {}
    return {u.name: u.full_name or u.name
            for u in frappe.get_all("User", filters={"name": ["in", users]}, fields=["name", "full_name"])}


def _json(value):
    return frappe.parse_json(value) if isinstance(value, str) else (value or {})


# ── Read everything ───────────────────────────────────────────────────────

@frappe.whitelist()
def get_settings():
    _require_admin()
    out = {"outward_request": None, "knit_down": None}

    if frappe.db.exists("DocType", OR_SETTINGS):
        s = frappe.get_single(OR_SETTINGS)
        users = [r.user for r in s.get("approvers") or []]
        names = _full_names(users)
        cutoff = str(s.same_day_cutoff_time or "23:30:00")
        out["outward_request"] = {
            "deadline": cutoff[:5].rjust(5, "0"),
            "require_approval": cint(s.require_same_day_approval),
            "daily_kgs_limit": flt(s.get("daily_kgs_limit")),
            "approvers": [{"user": u, "full_name": names.get(u, u)} for u in users if u],
        }

    if frappe.db.exists("DocType", KD_SETTINGS):
        s = frappe.get_single(KD_SETTINGS)
        rows = s.get("approver_locations") or []
        names = _full_names([r.user for r in rows])
        out["knit_down"] = {
            "require_gps": cint(s.get("require_gps")),
            "gps_radius_m": cint(s.get("gps_radius_m")) or 200,
            "approver_locations": [{"user": r.user, "full_name": names.get(r.user, r.user),
                                    "location": r.location} for r in rows if r.user],
        }

    out["locations"] = _unit_locations(out)
    out["pages"] = _pages()
    return out


def _unit_locations(current):
    """Locations that matter for GPS: used on open Work Orders or in the
    approver table, with their coordinates and open Work Order count."""
    counts = dict(frappe.db.sql("""
        SELECT custom_location, COUNT(*) FROM `tabWork Order`
        WHERE docstatus = 1 AND status IN ('Not Started', 'In Process')
          AND IFNULL(custom_location, '') != ''
        GROUP BY custom_location
    """)) if frappe.get_meta("Work Order").has_field("custom_location") else {}
    names = set(counts)
    for r in ((current.get("knit_down") or {}).get("approver_locations") or []):
        if r.get("location"):
            names.add(r["location"])
    if not names:
        return []
    rows = frappe.get_all("Location", filters={"name": ["in", list(names)]},
                          fields=["name", "latitude", "longitude"], order_by="name asc")
    return [{"name": r.name, "latitude": flt(r.latitude), "longitude": flt(r.longitude),
             "has_coordinates": bool(flt(r.latitude) or flt(r.longitude)),
             "open_work_orders": counts.get(r.name, 0)} for r in rows]


def _pages():
    if not frappe.db.exists("DocType", "Knit App Page"):
        return []
    roles = {}
    for r in frappe.get_all("Knit App Page Role", filters={"parenttype": "Knit App Page"},
                            fields=["parent", "role"], order_by="idx asc"):
        if r.role:
            roles.setdefault(r.parent, []).append(r.role)
    return [{"page": p.name, "title": p.page_title, "section": p.section, "roles": roles.get(p.name, [])}
            for p in frappe.get_all("Knit App Page", fields=["name", "page_title", "section", "idx_order"],
                                    order_by="idx_order asc")]


# ── Pickers ───────────────────────────────────────────────────────────────

@frappe.whitelist()
def search_users(txt=None):
    _require_admin()
    like = "%{0}%".format((txt or "").strip())
    return frappe.db.sql("""
        SELECT name AS user, full_name FROM `tabUser`
        WHERE enabled = 1 AND user_type = 'System User' AND name NOT IN ('Administrator', 'Guest')
          AND (name LIKE %(l)s OR full_name LIKE %(l)s)
        ORDER BY full_name LIMIT 20
    """, {"l": like}, as_dict=True)


@frappe.whitelist()
def search_locations(txt=None):
    _require_admin()
    return frappe.get_all("Location", filters={"is_group": 0, "name": ["like", f"%{(txt or '').strip()}%"]},
                          pluck="name", order_by="name asc", limit=20)


@frappe.whitelist()
def search_roles(txt=None):
    _require_admin()
    return frappe.get_all("Role", filters={"disabled": 0, "desk_access": 1,
                                           "name": ["like", f"%{(txt or '').strip()}%"]},
                          pluck="name", order_by="name asc", limit=20)


# ── Save ──────────────────────────────────────────────────────────────────

@frappe.whitelist()
def save_outward_request_settings(data):
    _require_admin()
    data = _json(data)
    s = frappe.get_single(OR_SETTINGS)
    deadline = (data.get("deadline") or "").strip()
    try:
        s.same_day_cutoff_time = get_time(deadline).strftime("%H:%M:%S")
    except Exception:
        frappe.throw(_("Deadline must be a time like 23:30"))
    s.require_same_day_approval = 1 if data.get("require_approval") else 0
    if s.meta.has_field("daily_kgs_limit"):
        limit = flt(data.get("daily_kgs_limit"))
        if limit < 0:
            frappe.throw(_("Daily Kgs Limit can't be negative (use 0 for no limit)"))
        s.daily_kgs_limit = limit
    s.set("approvers", [])
    for u in dict.fromkeys(r.get("user") for r in data.get("approvers") or [] if r.get("user")):
        s.append("approvers", {"user": u})
    s.save(ignore_permissions=True)
    frappe.clear_cache(doctype=OR_SETTINGS)
    return get_settings()


@frappe.whitelist()
def save_knit_down_settings(data):
    _require_admin()
    data = _json(data)
    s = frappe.get_single(KD_SETTINGS)
    if s.meta.has_field("require_gps"):
        s.require_gps = 1 if data.get("require_gps") else 0
        radius = cint(data.get("gps_radius_m"))
        if radius < 20 or radius > 5000:
            frappe.throw(_("GPS range must be between 20 and 5,000 metres"))
        s.gps_radius_m = radius
    s.set("approver_locations", [])
    seen = set()
    for r in data.get("approver_locations") or []:
        key = (r.get("user"), r.get("location"))
        if not all(key) or key in seen:
            continue
        seen.add(key)
        s.append("approver_locations", {"user": key[0], "location": key[1]})
    s.save(ignore_permissions=True)
    frappe.clear_cache(doctype=KD_SETTINGS)
    return get_settings()


@frappe.whitelist()
def save_location_coordinates(location, latitude, longitude):
    _require_admin()
    lat, lng = flt(latitude), flt(longitude)
    if not (-90 <= lat <= 90 and -180 <= lng <= 180) or (not lat and not lng):
        frappe.throw(_("Enter a valid latitude and longitude"))
    if not frappe.db.exists("Location", location):
        frappe.throw(_("Location {0} not found").format(location))
    # db.set_value: Location's own validate rebuilds its map shape and may
    # refuse a record with no area; only the coordinates change here.
    frappe.db.set_value("Location", location, {"latitude": lat, "longitude": lng})
    return get_settings()


@frappe.whitelist()
def save_page_roles(page, roles):
    _require_admin()
    roles = [r for r in dict.fromkeys(frappe.parse_json(roles) if isinstance(roles, str) else roles or []) if r]
    if page == "app-settings" and roles and ADMIN_ROLE not in roles:
        roles.append(ADMIN_ROLE)
    doc = frappe.get_doc("Knit App Page", page)
    doc.set("roles", [])
    for r in roles:
        if not frappe.db.exists("Role", r):
            frappe.throw(_("Role {0} not found").format(r))
        doc.append("roles", {"role": r})
    doc.save(ignore_permissions=True)
    return _pages()
