from . import __version__ as app_version

app_name        = "pranera_knit"
app_title       = "Pranera Knit"
app_publisher   = "Pranera Services & Solutions"
app_description = "Knitting production floor app for ERPNext"
app_email       = "admin@pranera.in"
app_license     = "MIT"
app_version     = "1.0.0"

setup_wizard_not_required = 1

add_to_apps_screen = [
    {
        "name": "pranera_knit",
        "logo": "data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' viewBox=\'0 0 100 100\'%3E%3Crect width=\'100\' height=\'100\' rx=\'22\' fill=\'%230f6e56\'/%3E%3Ccircle cx=\'30\' cy=\'50\' r=\'12\' fill=\'white\'/%3E%3Ccircle cx=\'70\' cy=\'50\' r=\'12\' fill=\'white\'/%3E%3Cpath d=\'M30 50 Q50 20 70 50 Q50 80 30 50\' fill=\'none\' stroke=\'white\' stroke-width=\'3\'/%3E%3C/svg%3E",
        "title": "Knit App",
        "route": "/knit-app",
    }
]

website_route_rules = [
    {"from_route": "/knit-app/<path:app_path>", "to_route": "knit-app"},
]

fixtures = [
    {"doctype": "Page",      "filters": [["module", "in", ["Knit Module"]]]},
    {"doctype": "Workspace", "filters": [["module", "in", ["Knit Module"]]]},
]
