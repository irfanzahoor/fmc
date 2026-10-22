import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt

#: Percentages are floats, so compare the total against 100 with a tolerance
#: rather than for equality.
PERCENTAGE_TOLERANCE = 0.01

#: Rounding applied to derived quantities, matching ERPNext's float precision
#: handling for stock quantities.
QTY_PRECISION = 6


class FMRecipe(Document):
	def validate(self):
		self.validate_item()
		self.validate_batch_size()
		self.validate_ingredients()
		self.set_quantities()
		self.validate_total_percentage()

	def before_insert(self):
		self.revision = self.get_next_revision()
		self.status = "Draft"

	def before_submit(self):
		self.status = "Approved"

	def on_submit(self):
		self.create_bom()
		self.supersede_previous()

	def on_cancel(self):
		# Status first, so a cancelled recipe never reads "Approved" even if a
		# later step fails. Everything here shares one transaction, so if
		# cancel_bom raises, this write rolls back with it.
		self.db_set("status", "Cancelled")

		# Cancelling the BOM means ERPNext's own link checks apply: a BOM
		# consumed by a submitted Work Order cannot be cancelled, so an approved
		# recipe that has been used in production cannot be un-approved. That is
		# the behaviour we want - history stays intact.
		self.cancel_bom()
		self.restore_superseded()

	# -- validation ----------------------------------------------------------

	def validate_item(self):
		nature = frappe.db.get_value("Item", self.item, "fm_material_nature")
		if nature and nature != "Bulk Blend":
			frappe.throw(
				_("{0} is classified as {1}. A recipe produces a Bulk Blend.").format(
					frappe.bold(self.item), frappe.bold(_(nature))
				),
				title=_("Wrong Item Nature"),
			)

	def validate_batch_size(self):
		if flt(self.batch_size) <= 0:
			frappe.throw(_("Batch Size must be greater than zero."))

	def validate_ingredients(self):
		if not self.ingredients:
			frappe.throw(_("Add at least one ingredient."))

		seen = {}
		for row in self.ingredients:
			if flt(row.percentage) <= 0:
				frappe.throw(
					_("Row {0}: Percentage must be greater than zero.").format(row.idx),
				)

			if row.item_code in seen:
				frappe.throw(
					_("Row {0}: ingredient {1} is already listed in row {2}.").format(
						row.idx, frappe.bold(row.item_code), seen[row.item_code]
					),
					title=_("Duplicate Ingredient"),
				)

			seen[row.item_code] = row.idx

		self.validate_ingredient_items(list(seen))

	def validate_ingredient_items(self, item_codes: list) -> None:
		"""Ingredients must be stock items, and must not be the blend itself."""
		if self.item in item_codes:
			frappe.throw(
				_("A recipe cannot contain its own output item {0}.").format(frappe.bold(self.item))
			)

		items = frappe.get_all(
			"Item",
			filters={"name": ("in", item_codes)},
			fields=["name", "is_stock_item", "stock_uom", "disabled"],
			order_by="name asc",
		)
		by_code = {item.name: item for item in items}

		for row in self.ingredients:
			item = by_code.get(row.item_code)
			if not item:
				continue

			if not item.is_stock_item:
				frappe.throw(
					_("Row {0}: {1} is not a stock item and cannot be an ingredient.").format(
						row.idx, frappe.bold(row.item_code)
					)
				)

			if item.disabled:
				frappe.throw(
					_("Row {0}: item {1} is disabled.").format(row.idx, frappe.bold(row.item_code))
				)

			if not row.uom:
				row.uom = item.stock_uom

			row.stock_uom = item.stock_uom

	def set_quantities(self):
		"""Turn percentages into explicit quantities in each ingredient's UOM.

		The conversion is deliberately explicit rather than implied: the factor
		used is stored on the row, so an auditor can see how a percentage became
		a quantity.
		"""
		batch_size = flt(self.batch_size)

		for row in self.ingredients:
			# Quantity in the recipe's batch UOM.
			base_qty = batch_size * flt(row.percentage) / 100.0

			factor = self.get_conversion_factor(row)
			row.conversion_factor = factor
			row.qty = flt(base_qty * factor, QTY_PRECISION)

			stock_factor = self.get_stock_conversion_factor(row)
			row.stock_qty = flt(row.qty * stock_factor, QTY_PRECISION)

	def get_conversion_factor(self, row) -> float:
		"""Factor converting the recipe batch UOM into this row's UOM."""
		if row.uom == self.batch_uom:
			return 1.0

		factor = get_uom_conversion_factor(self.batch_uom, row.uom)
		if not factor:
			frappe.throw(
				_(
					"Row {0}: no UOM conversion is defined from {1} to {2}. "
					"Add a UOM Conversion Factor, or enter the ingredient in {1}."
				).format(row.idx, frappe.bold(self.batch_uom), frappe.bold(row.uom)),
				title=_("Missing UOM Conversion"),
			)

		return factor

	def get_stock_conversion_factor(self, row) -> float:
		"""Factor converting this row's UOM into the item's stock UOM."""
		if not row.stock_uom or row.uom == row.stock_uom:
			return 1.0

		# The Item's own conversion table wins, as ERPNext does elsewhere.
		factor = frappe.db.get_value(
			"UOM Conversion Detail",
			{"parent": row.item_code, "uom": row.uom},
			"conversion_factor",
		)
		if factor:
			return flt(factor)

		factor = get_uom_conversion_factor(row.uom, row.stock_uom)
		if not factor:
			frappe.throw(
				_(
					"Row {0}: no UOM conversion is defined from {1} to the stock UOM {2} of item {3}."
				).format(
					row.idx,
					frappe.bold(row.uom),
					frappe.bold(row.stock_uom),
					frappe.bold(row.item_code),
				),
				title=_("Missing UOM Conversion"),
			)

		return factor

	def validate_total_percentage(self):
		total = sum(flt(row.percentage) for row in self.ingredients)
		self.total_percentage = flt(total, 4)

		if abs(total - 100.0) > PERCENTAGE_TOLERANCE:
			frappe.throw(
				_("Ingredient percentages total {0}%. They must total 100%.").format(
					frappe.bold(frappe.format_value(self.total_percentage, {"fieldtype": "Percent"}))
				),
				title=_("Formula Does Not Total 100%"),
			)

	def get_next_revision(self) -> int:
		last = frappe.db.get_value(
			"FM Recipe",
			{"item": self.item, "company": self.company, "docstatus": ("<", 2)},
			"revision",
			order_by="revision desc",
		)
		return cint(last) + 1

	# -- effects -------------------------------------------------------------

	def create_bom(self):
		"""Generate and submit a standard BOM from this approved recipe.

		The BOM is the record of truth for costing and for Work Orders; this
		recipe is the approval and percentage source. A submitted BOM cannot be
		edited by ERPNext, which is what preserves the revision used by
		historical production.
		"""
		currency = frappe.get_cached_value("Company", self.company, "default_currency")

		bom = frappe.new_doc("BOM")
		bom.item = self.item
		bom.company = self.company
		bom.quantity = flt(self.batch_size)
		bom.uom = self.batch_uom
		bom.currency = currency
		bom.is_active = 1
		bom.is_default = 1
		bom.fm_recipe = self.name

		for row in self.ingredients:
			bom.append(
				"items",
				{
					"item_code": row.item_code,
					"qty": flt(row.qty),
					"uom": row.uom,
				},
			)

		bom.insert()
		bom.submit()

		self.db_set("bom", bom.name)

	def cancel_bom(self):
		if not self.bom:
			return

		if frappe.db.get_value("BOM", self.bom, "docstatus") != 1:
			return

		frappe.get_doc("BOM", self.bom).cancel()

	def supersede_previous(self):
		"""Mark the previously approved recipe for this item as superseded."""
		previous = frappe.db.get_value(
			"FM Recipe",
			{
				"item": self.item,
				"company": self.company,
				"status": "Approved",
				"docstatus": 1,
				"name": ("!=", self.name),
			},
			"name",
			order_by="revision desc",
		)
		if not previous:
			return

		frappe.db.set_value("FM Recipe", previous, "status", "Superseded")
		frappe.clear_document_cache("FM Recipe", previous)
		self.db_set("supersedes", previous)

	def restore_superseded(self):
		"""On cancellation, hand approval back to the recipe this one replaced."""
		if not self.supersedes:
			return

		if frappe.db.get_value("FM Recipe", self.supersedes, "docstatus") != 1:
			return

		frappe.db.set_value("FM Recipe", self.supersedes, "status", "Approved")
		frappe.clear_document_cache("FM Recipe", self.supersedes)


def get_uom_conversion_factor(from_uom: str, to_uom: str) -> float:
	"""Look up a global UOM Conversion Factor in either direction."""
	if not from_uom or not to_uom:
		return 0.0

	if from_uom == to_uom:
		return 1.0

	value = frappe.db.get_value(
		"UOM Conversion Factor", {"from_uom": from_uom, "to_uom": to_uom}, "value"
	)
	if value:
		return flt(value)

	# Conversions are usually defined one way round only.
	inverse = frappe.db.get_value(
		"UOM Conversion Factor", {"from_uom": to_uom, "to_uom": from_uom}, "value"
	)
	if inverse:
		return 1.0 / flt(inverse)

	return 0.0


def get_approved_recipe(item: str, company: str) -> str | None:
	"""Name of the currently approved recipe for an item, if any."""
	return frappe.db.get_value(
		"FM Recipe",
		{"item": item, "company": company, "status": "Approved", "docstatus": 1},
		"name",
	)
