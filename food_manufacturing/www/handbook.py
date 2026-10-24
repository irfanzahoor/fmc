"""The Batchwell handbook: three guides, served as pages and as PDFs.

One template per guide, rendered into both the web layout and the print layout,
so a reader on the site and a reader holding the PDF are never told different
things. The same reason the capability document works this way.

Public by design. Everything here is a statement about how the application
behaves - the same material the repository's README carries - and it reads no
site data, so there is nothing here that a login would protect.
"""

import frappe
from frappe.utils import today

#: Guide slug -> its chapter. ``nav`` drives both the sidebar and the landing
#: page, so a new guide is one entry rather than three edits.
GUIDES = {
	"operating": {
		"title": "Operating manual",
		"audience": "Everyone who works a shift",
		"blurb": (
			"The console screen by screen - what each one is for, what it will "
			"let you do, and what it will stop you doing."
		),
		"nav": [
			("The console", "the-console"),
			("A day in the plant", "a-day"),
			("My workspace", "workspace"),
			("Overview", "overview"),
			("Goods in", "goods-in"),
			("Quality", "quality"),
			("Production", "production"),
			("Recipe cost and packaging", "costing"),
			("Dispatch", "dispatch"),
			("Recall", "recall"),
			("Insights", "insights"),
			("The five rules", "rules"),
			("Reading the charts", "charts"),
			("When a screen refuses", "refusals"),
		],
	},
	"admin": {
		"title": "Administrator guide",
		"audience": "Whoever installs and configures the app",
		"blurb": (
			"Install, company policy, items, recipes, roles, the daily alert, "
			"demo data, upgrades and the failures worth recognising."
		),
		"nav": [
			("Before you install", "requirements"),
			("Install", "install"),
			("What the install creates", "install-creates"),
			("Company policy", "policy"),
			("Set up your items", "items"),
			("Recipes and confidentiality", "recipes"),
			("Granting roles", "roles"),
			("The near-expiry alert", "alert"),
			("Demo data", "demo"),
			("Upgrading", "upgrading"),
			("Troubleshooting", "troubleshooting"),
		],
	},
	"developer": {
		"title": "Developer reference",
		"audience": "Anyone changing or extending the code",
		"blurb": (
			"Architecture, the module map, document events, the data model, "
			"the HTTP surface, the permission model and how to run the tests."
		),
		"nav": [
			("How it is put together", "architecture"),
			("Module map", "modules"),
			("Document events", "doc-events"),
			("Data model", "data-model"),
			("The HTTP surface", "api"),
			("The permission model", "permissions"),
			("The frontend", "frontend"),
			("Running the tests", "tests"),
			("House rules", "house-rules"),
		],
	},
}

#: Figures quoted across the handbook, counted from the source rather than
#: remembered. Changing one is one edit.
FACTS = {
	"frappe_version": "16",
	"erpnext_version": "16",
	"tests": 347,
	"test_modules": 30,
	# frontend/src/router.js, excluding the catch-all NotFound route.
	"screens": 10,
	"roles": 6,
	# food_manufacturing/setup/custom_fields.py
	"custom_fields": 31,
	"doctypes": 4,
	"endpoints": 26,
}

no_cache = 1


def get_context(context):
	context.no_cache = 1
	context.facts = FACTS
	context.guides = GUIDES
	context.generated_on = today()

	slug = frappe.form_dict.get("guide")
	if slug and slug not in GUIDES:
		# A mistyped chapter should 404, not render an empty shell.
		raise frappe.DoesNotExistError

	context.slug = slug
	context.guide = GUIDES.get(slug)
	context.body = f"templates/handbook/{slug}.html" if slug else "templates/handbook/index.html"
	context.title = GUIDES[slug]["title"] if slug else "Batchwell handbook"
	return context


@frappe.whitelist(allow_guest=True)
def download(guide: str):
	"""One guide as a branded PDF.

	The print template is rendered, not the body: the body has no ``<head>``,
	and rendering it alone produces a correct but completely unstyled document.
	"""
	if guide not in GUIDES:
		raise frappe.DoesNotExistError

	from frappe.utils.pdf import get_pdf

	context = frappe._dict(
		facts=FACTS,
		guides=GUIDES,
		slug=guide,
		guide=GUIDES[guide],
		body=f"templates/handbook/{guide}.html",
		generated_on=today(),
		for_print=True,
	)
	html = frappe.render_template("templates/handbook/print.html", context)

	frappe.local.response.filename = f"Batchwell-{guide}-guide.pdf"
	frappe.local.response.filecontent = get_pdf(
		html,
		options={
			"page-size": "A4",
			# Measured: wkhtmltopdf holds ~15mm at the top whatever this and
			# @page say, so the masthead sits in a white band rather than
			# bleeding. Kept at zero to match the capability document exactly.
			"margin-top": "0mm",
			"margin-bottom": "16mm",
			"margin-left": "0mm",
			"margin-right": "0mm",
			"print-media-type": None,
			"encoding": "UTF-8",
		},
	)
	frappe.local.response.type = "pdf"
