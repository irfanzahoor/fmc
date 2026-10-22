from frappe.model.document import Document


class FMRecipeIngredient(Document):
	"""One line of a recipe formula.

	Quantities are derived by the parent FM Recipe from the percentage and the
	recipe batch size, so there is no logic here.
	"""
