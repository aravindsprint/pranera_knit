"""Continuous Roll numbering and protection against holes in the sequence.

Roll is named from `roll_no` (autoname field:roll_no, no naming series) and
the number must stay continuous: next roll = highest numeric Roll + 1.

Problems this module fixes (24-Nov-2026):

* Concurrency — several tablets ending rolls together all read the same
  MAX(name) and collided; the losers retried up to 8 times. Now every
  allocation first takes a transaction-scoped row lock, so allocations run
  one after another (a few ms each) and each reads the true highest number.
  The lock is released by the caller's commit/rollback, so callers must
  commit right after inserting (create_roll, save_roll_data and
  create_order_rolls all do).

* Holes / reused numbers — the PWA's Reset deleted the job card's empty
  running roll. A deleted roll in the middle left a hole (210068, 210081);
  a deleted *last* roll gave its number to the next roll (210082). Reset no
  longer deletes, create_roll reuses the job card's open empty roll, and
  `validate_roll_delete` refuses deletes that would leave a hole.
"""

import frappe
from frappe import _

LOCK_KEY = "KNIT-ROLL-NO-LOCK"   # row in tabSeries used only as a mutex


def _lock():
    """Serialize roll-number allocation until the current transaction ends."""
    frappe.db.sql(
        "INSERT IGNORE INTO `tabSeries` (`name`, `current`) VALUES (%s, 0)", LOCK_KEY
    )
    frappe.db.sql(
        "SELECT `current` FROM `tabSeries` WHERE `name` = %s FOR UPDATE", LOCK_KEY
    )


def _max_roll_no():
    row = frappe.db.sql("""
        SELECT MAX(CAST(name AS UNSIGNED))
        FROM `tabRoll`
        WHERE name REGEXP '^[0-9]+$'
    """)
    return int((row[0][0] if row else 0) or 0)


def next_roll_no():
    """Next continuous roll number (highest numeric Roll + 1), allocated
    under a lock so concurrent callers never get the same number."""
    _lock()
    n = _max_roll_no() + 1
    while frappe.db.exists("Roll", str(n)):
        n += 1
    return str(n)


def open_empty_roll(job_card):
    """The job card's open roll: created by Start/auto-continue but not yet
    weighed or ended. Reset and double taps reuse it instead of creating
    (and later deleting) another number."""
    rows = frappe.db.sql("""
        SELECT name FROM `tabRoll`
        WHERE job_card = %s
          AND docstatus = 0
          AND IFNULL(roll_weight, 0) = 0
          AND IFNULL(total_qty, 0) = 0
          AND end_time IS NULL
          AND name REGEXP '^[0-9]+$'
        ORDER BY CAST(name AS UNSIGNED) ASC
        LIMIT 1
    """, job_card)
    return rows[0][0] if rows else None


# ── Delete guard (doc_events: Roll.on_trash) ──────────────────────────────────

_LINKS = (
    ("Roll Packing List Item", "roll_no"),
    ("Roll Wise Pick Item", "roll_no"),
    ("Verified Roll Item", "roll_no"),
    ("Roll Tracking Entries", "roll_no"),
    ("Quality Inspection", "custom_roll"),
)


def validate_roll_delete(doc, method=None):
    """Only the last, empty, unused roll may be deleted — anything else
    would leave a hole in the continuous numbering. System Manager can
    override (e.g. cleaning up test data)."""
    if not str(doc.name).isdigit():
        return  # cut rolls (33631-1) etc. are outside the numeric sequence
    if "System Manager" in frappe.get_roles():
        return

    if (doc.roll_weight or 0) > 0 or (doc.total_qty or 0) > 0:
        frappe.throw(
            _("Roll {0} has a weight/qty and cannot be deleted. Correct it instead.").format(doc.name),
            title=_("Roll Cannot Be Deleted"),
        )

    for dt, field in _LINKS:
        ref = frappe.db.get_value(dt, {field: doc.name}, "parent" if frappe.get_meta(dt).istable else "name")
        if ref:
            frappe.throw(
                _("Roll {0} is used in {1} {2} and cannot be deleted.").format(doc.name, dt, ref),
                title=_("Roll Cannot Be Deleted"),
            )

    if int(doc.name) < _max_roll_no():
        frappe.throw(
            _("Roll {0} is not the last roll. Deleting it would leave a gap in roll "
              "numbers — leave it; the job card's next roll will reuse it.").format(doc.name),
            title=_("Roll Cannot Be Deleted"),
        )
