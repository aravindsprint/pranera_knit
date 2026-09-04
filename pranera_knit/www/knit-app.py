import os
import frappe


def get_context(context):
	"""Cache-busting version tag for the unhashed index.css / index.js bundle.

	Every other build output (page chunks) already gets a fresh content hash
	in its filename on each `yarn build`, so a new deploy naturally produces
	a new URL and browsers fetch it fresh. index.css and index.js are the
	two exceptions -- Vite always names them the same thing -- and browsers
	were caching them for up to a year (Cache-Control: max-age=31536000,
	immutable), so anyone who'd loaded the app once kept getting the OLD
	index.css/index.js forever, no matter how many times we redeployed.

	Appending ?v=<mtime of index.js> forces a new URL (and therefore a
	fresh fetch) exactly when the build actually changes, and only then --
	unlike a per-request timestamp, which would defeat caching entirely.
	"""
	bundle_path = frappe.get_app_path(
		"pranera_knit", "public", "knit_app", "index.js"
	)
	try:
		context.asset_version = int(os.path.getmtime(bundle_path))
	except OSError:
		# Falls back to "no version tag" if the file is ever missing for
		# some reason -- never let this break the page from loading.
		context.asset_version = ""
