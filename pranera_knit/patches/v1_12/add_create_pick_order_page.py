"""
Seed the "Knit App Page" record for the Create Pick Order page
(key "create-pick-order"). Re-runs the v1_10 seeding, which only adds pages
that are missing and leaves existing roles untouched.
"""
from pranera_knit.patches.v1_10.add_knit_app_page_access import execute as seed_pages


def execute():
    seed_pages()
